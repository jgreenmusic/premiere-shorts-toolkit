// Shorts Toolkit - Captions (CEP panel). Checks in with the Shorts Toolkit app on this
// PC every 1.5 s; when the app has caption lines ready (an .srt), lays them on the
// sequence as a real Premiere caption track (host.jsx) and saves the project.
// Node's http is used, not fetch: a CEP page is a file:// page, and the browser would
// block its requests to the app.
const http = require("http");

const VERSION = "1.0.0";
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

async function tick() {
  let wait = 1500;
  try {
    let i = {};
    try { i = JSON.parse(await host("shortsInfo")); } catch (e) { /* Premiere busy */ }
    const r = await post("/api/bridge/hello", Object.assign({ plugin: VERSION }, i));
    if (!busy) show(i.project ? `Connected · ${baseName(i.project)}` : "Connected · no project open", "on");
    if (r.command && !busy && r.command.op === "import") {
      busy = true;
      importCaptions(r.command)
        .catch((e) => post("/api/bridge/report", { job: r.command.job, error: "Captions panel error: " + e }).catch(() => {}))
        .finally(() => { busy = false; });
    }
  } catch (e) {
    if (!busy) port = (port + 1) % PORTS.length;        // look on the next port
    show("Shorts Toolkit isn't open", "off");
    wait = port === 0 ? 4000 : 300;
  }
  setTimeout(tick, wait);
}

tick();
