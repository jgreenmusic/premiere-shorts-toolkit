// Shorts Toolkit - Captions (CEP panel). Checks in with the Shorts Toolkit app on this
// PC every 1.5 s; when the app has caption lines ready (an .srt), lays them on the
// sequence as a real Premiere caption track (host.jsx) and saves the project.
// Node's http is used, not fetch: a CEP page is a file:// page, and the browser would
// block its requests to the app.
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");

const VERSION = "1.0.3";

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
// the toolkit uses the first free one of these (app.BRIDGE_PORTS)
const PORTS = [8765, 8767, 8768, 8769];
let port = 0;
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

function post(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(Object.assign({ kind: "cep" }, body));
    const req = http.request({
      host: "127.0.0.1", port: PORTS[port], path, method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
    }, (res) => {
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { buf += c; });
      res.on("end", () => { try { resolve(JSON.parse(buf || "{}")); } catch (e) { resolve({}); } });
    });
    req.on("error", reject);
    req.setTimeout(5000, () => req.destroy(new Error("timeout")));
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

async function importCaptions(cmd) {
  log("Adding caption track from " + baseName(cmd.srt));
  show("Adding captions…", "busy");
  const r = String(await host("shortsImportCaptions", cmd.srt, cmd.sequence || "", cmd.project || ""));
  if (r.indexOf("OK:") === 0) {
    log(r.slice(3));
    return post("/api/bridge/report", { job: cmd.job, done: true, message: r.slice(3) });
  }
  const msg = r.indexOf("ERR:") === 0 ? r.slice(4) : "Premiere didn't answer the script (" + r + ")";
  log(msg);
  return post("/api/bridge/report", { job: cmd.job, error: msg });
}

async function runScript(cmd) {
  log("Running " + baseName(cmd.script));
  show("Running " + baseName(cmd.script) + "…", "busy");
  const r = String(await host("shortsRunScript", cmd.script, cmd.sequence || "", cmd.project || ""));
  const ok = r.indexOf("OK:") === 0;
  const message = ok ? r.slice(3) : r.indexOf("ERR:") === 0 ? r.slice(4) : "Premiere didn't answer the script (" + r + ")";
  log(message);
  return post("/api/bridge/report", { rid: cmd.rid, ok, message });
}

let lastState = "";
function state(s) { if (s !== lastState) { trace(s); lastState = s; } }

// ExtendScript answers through a callback that never comes if host.jsx didn't load
function hostWithin(ms, fn, ...args) {
  return Promise.race([host(fn, ...args), new Promise((res) => setTimeout(() => res("TIMEOUT"), ms))]);
}

async function tick() {
  let wait = 1500;
  try {
    let i = {};
    const info = await hostWithin(5000, "shortsInfo");
    if (info === "TIMEOUT") state("ExtendScript (host.jsx) not answering");
    try { i = JSON.parse(info); } catch (e) { /* Premiere busy */ }
    const r = await post("/api/bridge/hello", Object.assign({ plugin: VERSION }, i));
    state("connected to toolkit on " + PORTS[port]);
    if (!busy) show(i.project ? `Connected · ${baseName(i.project)}` : "Connected · no project open", "on");
    const cmd = r.command;
    if (cmd && !busy && (cmd.op === "import" || cmd.op === "script")) {
      trace("running " + cmd.op + " " + (cmd.script || cmd.srt || ""));
      busy = true;
      (cmd.op === "import" ? importCaptions(cmd) : runScript(cmd))
        .catch((e) => post("/api/bridge/report", { job: cmd.job, rid: cmd.rid, error: "Captions panel error: " + e, message: String(e) }).catch(() => {}))
        .finally(() => { busy = false; });
    }
  } catch (e) {
    if (!busy) port = (port + 1) % PORTS.length;        // look on the next port
    if (port === 0) state("toolkit not found: " + e);
    show("Shorts Toolkit isn't open", "off");
    wait = port === 0 ? 4000 : 300;
  }
  setTimeout(tick, wait);
}

loadHost().finally(tick);
