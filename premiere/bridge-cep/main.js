// Shorts Toolkit - Captions (CEP panel). Checks in with the Shorts Toolkit apps on this
// PC every 1.5 s; when one has caption lines ready (an .srt), lays them on the
// sequence as a real Premiere caption track (host.jsx) and saves the project.
// Node's http is used, not fetch: a CEP page is a file:// page, and the browser would
// block its requests to the app.
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");

const VERSION = "1.0.6";

// what the panel did, in %TEMP%\shorts-toolkit-captions-panel.log (Premiere's own CEP logs
// don't say why a panel stops)
const LOGFILE = path.join(os.tmpdir(), "shorts-toolkit-captions-panel.log");
function trace(line) {
  try { fs.appendFileSync(LOGFILE, new Date().toISOString() + " " + line + "\n"); } catch (e) { /* ignore */ }
}
trace("panel loaded v" + VERSION + " pid " + process.pid);
window.addEventListener("error", (e) => trace("error: " + e.message + " @ " + e.filename + ":" + e.lineno));
window.addEventListener("unhandledrejection", (e) => trace("unhandled: " + (e.reason && e.reason.stack || e.reason)));
window.addEventListener("beforeunload", () => trace("page unloading"));
process.on("uncaughtException", (e) => trace("node exception: " + (e && e.stack || e)));
process.on("exit", (c) => trace("node exit " + c));
// where the apps listen: the Shorts Toolkit window uses the first free one of the first four
// (app.BRIDGE_PORTS), Shorts Auto Run one of the last three (autorun.PORTS). Both can be open.
const PORTS = [8765, 8767, 8768, 8769, 8772, 8773, 8774];
const live = new Set();       // ports that answered the last time they were asked
const todo = [];              // what the apps asked for, one at a time: {port, cmd}
let ticks = 0;
let busy = false;
const lines = [];

function show(state, cls) {
  const el = document.getElementById("state");
  el.textContent = state;
  el.className = cls;
}
function log(line) {
  lines.push(line);
  while (lines.length > 12) lines.shift();
  document.getElementById("log").textContent = lines.join("\n");
}

function post(port, path, body, ms) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(Object.assign({ kind: "cep" }, body));
    const req = http.request({
      host: "127.0.0.1", port, path, method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
    }, (res) => {
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { buf += c; });
      res.on("end", () => { try { resolve(JSON.parse(buf || "{}")); } catch (e) { resolve({}); } });
    });
    req.on("error", reject);
    req.setTimeout(ms || 5000, () => req.destroy(new Error("timeout")));
    req.end(data);
  });
}

// run a host.jsx function; arguments go in as JSON literals (valid ExtendScript strings)
function host(fn, ...args) {
  return new Promise((resolve) => {
    window.__adobe_cep__.evalScript(`${fn}(${args.map((a) => JSON.stringify(a)).join(",")})`, resolve);
  });
}

function baseName(p) { return String(p || "").split(/[\\/]/).pop(); }

// Premiere loads host.jsx once, when the panel first opens, and keeps that copy through page
// reloads - so load it again ourselves: an updated panel then works without restarting Premiere.
async function loadHost() {
  const ext = decodeURI(window.__adobe_cep__.getSystemPath("extension")).replace(/^file:\/+/, "");
  const r = await new Promise((resolve) => window.__adobe_cep__.evalScript(
    `try { $.evalFile(new File(${JSON.stringify(ext + "/host.jsx")})); "ok" } catch (e) { "ERR " + e + " (line " + e.line + ")" }`, resolve));
  trace("host.jsx load: " + r);
  return r;
}

async function importCaptions(port, cmd) {
  log("Adding caption track from " + baseName(cmd.srt));
  show("Adding captions…", "busy");
  const r = String(await host("shortsImportCaptions", cmd.srt, cmd.sequence || "", cmd.project || ""));
  if (r.indexOf("OK:") === 0) {
    log(r.slice(3));
    return post(port, "/api/bridge/report", { job: cmd.job, done: true, message: r.slice(3) });
  }
  const msg = r.indexOf("ERR:") === 0 ? r.slice(4) : "Premiere didn't answer the script (" + r + ")";
  log(msg);
  return post(port, "/api/bridge/report", { job: cmd.job, error: msg });
}

async function runScript(port, cmd) {
  log("Running " + baseName(cmd.script));
  show("Running " + baseName(cmd.script) + "…", "busy");
  const r = String(await host("shortsRunScript", cmd.script, cmd.sequence || "", cmd.project || ""));
  const ok = r.indexOf("OK:") === 0;
  const message = ok ? r.slice(3) : r.indexOf("ERR:") === 0 ? r.slice(4) : "Premiere didn't answer the script (" + r + ")";
  log(message);
  return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message });
}

let lastState = "";
function state(s) { if (s !== lastState) { trace(s); lastState = s; } }

// ExtendScript answers through a callback that never comes if host.jsx didn't load
function hostWithin(ms, fn, ...args) {
  return Promise.race([host(fn, ...args), new Promise((res) => setTimeout(() => res("TIMEOUT"), ms))]);
}

function work() {
  if (busy || !todo.length) return;
  const { port, cmd } = todo.shift();
  if (cmd.op !== "import" && cmd.op !== "script") return work();
  trace("running " + cmd.op + " " + (cmd.script || cmd.srt || "") + " for the app on " + port);
  busy = true;
  (cmd.op === "import" ? importCaptions(port, cmd) : runScript(port, cmd))
    .catch((e) => post(port, "/api/bridge/report", { job: cmd.job, rid: cmd.rid, error: "Captions panel error: " + e, message: String(e) }).catch(() => {}))
    .finally(() => { busy = false; work(); });
}

async function tick() {
  ticks++;
  try {
    let i = {};
    const info = await hostWithin(5000, "shortsInfo");
    if (info === "TIMEOUT") state("ExtendScript (host.jsx) not answering");
    try { i = JSON.parse(info); } catch (e) { /* Premiere busy */ }
    // the apps that are there, every time; the other ports now and then (a closed port takes
    // Windows a couple of seconds to refuse, so nothing waits for it)
    const ask = PORTS.filter((p) => live.has(p) || ticks % 4 === 1);
    await Promise.all(ask.map((p) => post(p, "/api/bridge/hello", Object.assign({ plugin: VERSION }, i), 1200).then((r) => {
      live.add(p);
      if (r && r.command) todo.push({ port: p, cmd: r.command });
    }, () => { live.delete(p); })));
    state(live.size ? "connected to the apps on " + [...live].join(", ") : "no Shorts Toolkit app found");
    if (!busy) {
      if (live.size) show(i.project ? `Connected · ${baseName(i.project)}` : "Connected · no project open", "on");
      else show("Shorts Toolkit isn't open", "off");
    }
    work();
  } catch (e) {
    state("check-in failed: " + e);
  }
  setTimeout(tick, live.size ? 1500 : 3000);
}

loadHost().finally(tick);
