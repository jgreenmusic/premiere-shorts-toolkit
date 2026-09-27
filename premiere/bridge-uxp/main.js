// Shorts Toolkit - Speech (UXP panel for Premiere 26.5+).
// Checks in with the Shorts Toolkit app on this PC every 1.5 s. When the app asks,
// runs Adobe's Speech to Text on every audible clip of the sequence and sends the
// transcripts back, with where each clip sits on the timeline. The app turns them
// into caption lines; its other panel (Shorts Toolkit - Captions) adds the track.
const ppro = require("premierepro");
const uxp = require("uxp");

// the toolkit uses the first free one of these (app.BRIDGE_PORTS)
const PORTS = [8765, 8767, 8768, 8769];
let port = 0;
const VERSION = "1.0.2";
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

async function post(path, body) {
  const r = await fetch(`http://127.0.0.1:${PORTS[port]}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ kind: "uxp" }, body)),
  });
  return r.json();
}

function same(a, b) {
  // Premiere 26 reports project paths with the \\?\ long-path prefix
  const n = (p) => String(p || "").replace(/\//g, "\\").replace(/^\\\\\?\\/, "").toLowerCase();
  return n(a) === n(b);
}
function baseName(p) { return String(p || "").split(/[\\/]/).pop(); }

// what the app sees: which project/sequence is open, and which Adobe calls exist
async function info() {
  const i = {
    plugin: VERSION,
    host: (uxp.host && uxp.host.version) || "",
    apis: {
      transcribe: !!(ppro.Transcript && ppro.Transcript.transcribeClipProjectItem),
      exportJSON: !!(ppro.Transcript && ppro.Transcript.exportToJSON),
      // Premiere's own Text panel uses these. Not public - only reported, not used yet.
      speechInternal: !!(uxp.mediaCoreSpeechToText && uxp.mediaCoreSpeechToText.AutoCaptioningAPI),
      captionInternal: !!(uxp.hSLScripting && uxp.hSLScripting.CaptioningScriptAPI),
    },
  };
  try {
    const p = await ppro.Project.getActiveProject();
    if (p) {
      i.project = p.path;
      const s = await p.getActiveSequence();
      if (s) {
        i.sequence = s.name;
        i.captionTracks = await s.getCaptionTrackCount();
      }
    }
  } catch (e) {
    i.error = String(e);
  }
  return i;
}

async function transcribe(cmd) {
  const say = (line) => { log(line); return post("/api/bridge/report", { job: cmd.job, line }); };
  const fail = (error, click) => { log(error); return post("/api/bridge/report", { job: cmd.job, error, click: !!click }); };

  if (!ppro.Transcript || !ppro.Transcript.transcribeClipProjectItem) {
    return fail("This Premiere can't transcribe from a script (needs Premiere 26.5 or newer). Use 'Toolkit speech' in the app instead.");
  }
  const project = await ppro.Project.getActiveProject();
  if (!project) return fail("No project is open in Premiere.");
  if (cmd.project && !same(project.path, cmd.project)) {
    return fail(`Premiere has "${project.name}" open - open ${baseName(cmd.project)} in Premiere, then try again.`);
  }
  const seqs = await project.getSequences();
  const seq = seqs.find((s) => s.name === cmd.sequence) || (await project.getActiveSequence());
  if (!seq) return fail(`No sequence named "${cmd.sequence}" in this project.`);

  // every clip you can hear, and where it sits on the timeline
  const items = [];
  const clips = new Map();
  const tracks = await seq.getAudioTrackCount();
  for (let t = 0; t < tracks; t++) {
    const track = await seq.getAudioTrack(t);
    if (!track || (await track.isMuted())) continue;
    const tis = await track.getTrackItems(ppro.Constants.TrackItemType.CLIP, false);
    for (const ti of tis) {
      const pi = await ti.getProjectItem();
      const clip = pi && ppro.ClipProjectItem.cast(pi);
      if (!clip) continue;
      let key = "";
      try { key = await clip.getMediaFilePath(); } catch (e) { /* not a media file */ }
      key = key || pi.name;
      clips.set(key, clip);
      items.push({
        key,
        start: (await ti.getStartTime()).seconds,
        end: (await ti.getEndTime()).seconds,
        in: (await ti.getInPoint()).seconds,
        out: (await ti.getOutPoint()).seconds,
      });
    }
  }
  if (!clips.size) return fail(`"${seq.name}" has no audio clips that aren't muted.`);
  await say(`${clips.size} clip${clips.size === 1 ? "" : "s"} to transcribe in "${seq.name}"`);

  const transcripts = {};
  for (const [key, clip] of clips) {
    const name = baseName(key);
    let has = false;
    try { has = await ppro.Transcript.hasTranscript(clip); } catch (e) { /* treat as missing */ }
    if (has) {
      await say(`${name}: already transcribed - reusing it`);
    } else {
      await say(`${name}: Adobe Speech to Text is listening (long recordings take a few minutes)…`);
      show("Transcribing…", "busy");
      let ok = false;
      try {
        ok = await ppro.Transcript.transcribeClipProjectItem(clip);
      } catch (e) {
        return fail(`${name}: transcription failed - ${e}`);
      }
      if (!ok) return fail(`${name}: Premiere said transcription didn't finish. Check the language pack in Premiere's Text panel.`);
    }
    transcripts[key] = await ppro.Transcript.exportToJSON(clip);
  }
  await say("Transcript done - sending it to the toolkit");
  await post("/api/bridge/report", { job: cmd.job, transcripts, items });
}

// markers the toolkit placed: replace the ones with this name prefix, keep everything else
async function placeMarkers(cmd) {
  const reply = (ok, message) => { log(message); return post("/api/bridge/report", { rid: cmd.rid, ok, message }); };
  const project = await ppro.Project.getActiveProject();
  if (!project) return reply(false, "No project is open in Premiere.");
  if (cmd.project && !same(project.path, cmd.project)) {
    return reply(false, `Premiere has "${project.name}" open - open ${baseName(cmd.project)} in Premiere, then try again.`);
  }
  const seqs = await project.getSequences();
  const seq = seqs.find((s) => s.name === cmd.sequence) || (await project.getActiveSequence());
  if (!seq) return reply(false, `No sequence named "${cmd.sequence}".`);
  show("Placing markers…", "busy");
  const markers = await ppro.Markers.getMarkers(seq);
  const all = () => { try { return markers.getMarkers() || []; } catch (e) { return markers.getMarkers(["Comment", "Chapter", "Segmentation", "WebLink"]) || []; } };
  const old = all().filter((m) => String(m.getName()).indexOf(cmd.prefix) === 0);
  const rows = cmd.rows.filter((r) => r.end > r.start);
  project.lockedAccess(() => {
    project.executeTransaction((ca) => {
      for (const m of old) ca.addAction(markers.createRemoveMarkerAction(m));
      for (const r of rows) {
        ca.addAction(markers.createAddMarkerAction(cmd.prefix + r.name, "Comment",
          ppro.TickTime.createWithSeconds(r.start), ppro.TickTime.createWithSeconds(r.end - r.start), ""));
      }
    }, "Shorts Toolkit markers");
  });
  // colour them (a marker has to exist before it can be coloured)
  let coloured = 0;
  try {
    const mine = all().filter((m) => String(m.getName()).indexOf(cmd.prefix) === 0);
    project.lockedAccess(() => {
      project.executeTransaction((ca) => {
        for (const m of mine) if (ca.addAction(m.createSetColorByIndexAction(cmd.color))) coloured++;
      }, "Shorts Toolkit marker colours");
    });
  } catch (e) { log("Couldn't colour the markers: " + e); }
  return reply(true, `Added ${rows.length} marker(s) to "${seq.name}", replaced ${old.length} old one(s)${coloured ? "" : " (colour not set)"}.`);
}

async function tick() {
  let wait = 1500;
  try {
    const i = await info();
    const r = await post("/api/bridge/hello", i);
    if (!busy) show(i.project ? `Connected · ${baseName(i.project)}` : "Connected · no project open", "on");
    if (r.command && !busy) {
      // run it without holding up check-ins, so the app keeps seeing this panel
      busy = true;
      show("Working…", "busy");
      const cmd = r.command;
      (cmd.op === "transcribe" ? transcribe(cmd) : cmd.op === "markers" ? placeMarkers(cmd) : Promise.resolve())
        .catch((e) => {
          log("Error: " + e);
          return post("/api/bridge/report", { job: cmd.job, rid: cmd.rid, ok: false, message: "Speech panel error: " + e,
                                              error: "Speech panel error: " + e }).catch(() => {});
        })
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
