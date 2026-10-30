// Shorts Toolkit - Speech (UXP panel for Premiere 26.5+).
// Checks in with the Shorts Toolkit apps on this PC every 1.5 s. When one asks, it
//   - opens a project, or makes one from a recording (this panel is alive even on
//     Premiere's Home screen, with no project open - the Captions panel is not),
//   - runs Adobe's Speech to Text on every audible clip of the sequence and sends the
//     transcripts back, with where each clip sits on the timeline. The app turns them
//     into caption lines; its other panel (Shorts Toolkit - Captions) adds the track,
//   - places markers.
const ppro = require("premierepro");
const uxp = require("uxp");

// where the apps listen: the Shorts Toolkit window uses the first free one of the first four
// (app.BRIDGE_PORTS), Shorts Auto Run one of the last three (autorun.PORTS). Both can be open.
const PORTS = [8765, 8767, 8768, 8769, 8772, 8773, 8774];
const VERSION = "1.0.6";
const live = new Set();       // ports that answered the last time they were asked
const todo = [];              // what the apps asked for, one at a time: {port, cmd}
let busy = false;
let doing = "";               // the step a job is at, told to the apps (so "Premiere didn't answer" can say where)
let ticks = 0;
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
  const ask = fetch(`http://127.0.0.1:${port}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ kind: "uxp" }, body)),
  }).then((r) => r.json());
  if (!ms) return ask;
  // a closed port takes Windows a couple of seconds to refuse: don't hold the check-in up for it
  return Promise.race([ask, new Promise((_, no) => setTimeout(() => no(new Error("timeout")), ms))]);
}

// one way of writing a path (Premiere 26 reports project paths with the \\?\ long-path prefix)
const norm = (p) => String(p || "").replace(/\//g, "\\").replace(/^\\\\\?\\/, "").toLowerCase();
// the project the toolkit means, or a copy saved from it next to it ("Name.prproj" ->
// "NameV0.1.prproj", "Name_captions-synced.prproj")
function same(open, wanted) {
  const o = norm(open), w = norm(wanted);
  if (o === w) return true;
  const dir = (p) => p.slice(0, p.lastIndexOf("\\"));
  const stem = (p) => p.slice(p.lastIndexOf("\\") + 1).replace(/\.prproj$/, "");
  return dir(o) === dir(w) && stem(o).startsWith(stem(w).replace(/_captions-synced(-v\d+)?$/, ""));
}
function baseName(p) { return String(p || "").split(/[\\/]/).pop(); }

// what the app sees: which project/sequence is open, and which Adobe calls exist
async function info() {
  const i = {
    plugin: VERSION,
    doing,
    host: (uxp.host && uxp.host.version) || "",
    apis: {
      transcribe: !!(ppro.Transcript && ppro.Transcript.transcribeClipProjectItem),
      exportJSON: !!(ppro.Transcript && ppro.Transcript.exportToJSON),
      open: !!(ppro.Project && ppro.Project.open),
      create: !!(ppro.Project && ppro.Project.createProject),
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

// every clip you can hear, and where it sits on the timeline
async function audioClips(seq) {
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
  return { items, clips };
}

// who talks when: the transcripts Premiere already has (made in its Text panel with Speaker
// labeling on, speakers named there). Nothing is transcribed here - that would be without labels.
async function speakers(port, cmd) {
  const reply = (ok, message, extra) => { log(message); return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message, ...(extra || {}) }); };
  if (!ppro.Transcript || !ppro.Transcript.exportToJSON) return reply(false, "This Premiere can't hand out transcripts to a script (needs Premiere 26.5 or newer).");
  const project = await ppro.Project.getActiveProject();
  if (!project) return reply(false, "No project is open in Premiere.");
  if (cmd.project && !same(project.path, cmd.project)) {
    return reply(false, `Premiere has "${project.name}" open - open ${baseName(cmd.project)} in Premiere, then try again.`);
  }
  const seqs = await project.getSequences();
  const seq = seqs.find((s) => s.name === cmd.sequence) || (await project.getActiveSequence());
  if (!seq) return reply(false, `No sequence named "${cmd.sequence}" in this project.`);
  const { items, clips } = await audioClips(seq);
  const transcripts = {};
  const missing = [];
  for (const [key, clip] of clips) {
    let has = false;
    try { has = await ppro.Transcript.hasTranscript(clip); } catch (e) { /* treat as missing */ }
    if (!has) { missing.push(baseName(key)); continue; }
    transcripts[key] = await ppro.Transcript.exportToJSON(clip);
  }
  if (!Object.keys(transcripts).length) {
    return reply(false, `"${seq.name}" has no transcript yet. In Premiere's Text panel, transcribe it with Speaker labeling on, then try again.`);
  }
  return reply(true, `${Object.keys(transcripts).length} transcript(s) read` + (missing.length ? ` (none yet for ${missing.join(", ")})` : ""),
               { transcripts, items });
}

async function transcribe(port, cmd) {
  const say = (line) => { log(line); return post(port, "/api/bridge/report", { job: cmd.job, line }); };
  const fail = (error, click) => { log(error); return post(port, "/api/bridge/report", { job: cmd.job, error, click: !!click }); };

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

  const { items, clips } = await audioClips(seq);
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
      doing = "transcribing " + name;
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
  await post(port, "/api/bridge/report", { job: cmd.job, transcripts, items });
}

// markers the toolkit placed: replace the ones with this name prefix, keep everything else
async function placeMarkers(port, cmd) {
  const reply = (ok, message) => { log(message); return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message }); };
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

// open a project - Auto Run does this before it asks for captions. Exactly that file, not a
// copy saved from it.
async function openProject(port, cmd) {
  const reply = (ok, message) => { log(message); return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message }); };
  const active = await ppro.Project.getActiveProject();
  if (active && norm(active.path) === norm(cmd.project)) return reply(true, `${baseName(cmd.project)} is open.`);
  show("Opening the project…", "busy");
  doing = "opening " + baseName(cmd.project);
  const p = await ppro.Project.open(cmd.project);
  if (!p) return reply(false, `Premiere couldn't open ${baseName(cmd.project)}.`);
  return reply(true, `Opened ${baseName(cmd.project)}.`);
}

// every item in the project's top bin, with its name
async function rootItems(project) {
  const root = await project.getRootItem();
  const out = [];
  for (const it of await root.getItems()) out.push({ it, name: String(it.name) });
  return out;
}

// a recording with no Premiere project yet: make the project next to it, put the recording
// on a timeline of its own, save. Nothing else is added.
async function projectFromClip(port, cmd) {
  const reply = (ok, message) => { log(message); return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message }); };
  show("Making the project…", "busy");
  let project = await ppro.Project.getActiveProject();
  if (!project || norm(project.path) !== norm(cmd.project)) {
    doing = (cmd.exists ? "opening " : "making ") + baseName(cmd.project);
    project = cmd.exists ? await ppro.Project.open(cmd.project) : await ppro.Project.createProject(cmd.project);
  }
  if (!project) return reply(false, `Premiere couldn't make ${baseName(cmd.project)}.`);
  const have = (await project.getSequences()).find((s) => s.name === cmd.sequence);
  if (have) {
    await project.save();
    return reply(true, `The timeline "${cmd.sequence}" was already there.`);
  }
  const file = baseName(cmd.clip), stem = file.replace(/\.[^.]+$/, "");
  const find = async () => (await rootItems(project)).find((x) => x.name === file || x.name === stem);
  let item = await find();
  if (!item) {
    log("Importing " + file);
    doing = "importing " + file;
    const ok = await project.importFiles([cmd.clip], true);
    if (!ok) return reply(false, `Premiere couldn't import ${file}.`);
    for (let n = 0; n < 40 && !item; n++) {          // the item shows up a moment after the import returns
      item = await find();
      if (!item) await new Promise((r) => setTimeout(r, 250));
    }
  }
  if (!item) return reply(false, `Imported ${file}, but it isn't in the Project panel.`);
  const clip = ppro.ClipProjectItem.cast(item.it);
  if (!clip) return reply(false, `${file} came in as something Premiere can't put on a timeline.`);
  doing = "making the timeline";
  const seq = await project.createSequenceFromMedia(cmd.sequence, [clip]);
  if (!seq) return reply(false, `Premiere couldn't make a timeline from ${file}.`);
  try { await project.setActiveSequence(seq); } catch (e) { /* it is usually active already */ }
  doing = "saving the project";
  await project.save();
  return reply(true, `Made ${baseName(cmd.project)} with the timeline "${cmd.sequence}".`);
}

// Shorts sent to Premiere: make (or open) "<name> - Shorts.prproj", import the timeline file - each
// Short becomes a timeline - and the plain-text captions into a bin of their own, open the first
// new timeline, save
async function shortsProject(port, cmd) {
  const reply = (ok, message) => { log(message); return post(port, "/api/bridge/report", { rid: cmd.rid, ok, message }); };
  show("Making the Shorts project…", "busy");
  let project = await ppro.Project.getActiveProject();
  if (!project || norm(project.path) !== norm(cmd.project)) {
    doing = (cmd.exists ? "opening " : "making ") + baseName(cmd.project);
    project = cmd.exists ? await ppro.Project.open(cmd.project) : await ppro.Project.createProject(cmd.project);
  }
  if (!project) return reply(false, `Premiere couldn't make ${baseName(cmd.project)}.`);
  const before = new Set((await project.getSequences()).map((s) => s.guid.toString()));
  doing = "importing the Shorts";
  log("Importing " + cmd.xml);
  if (!(await project.importFiles([cmd.xml], true))) return reply(false, `Premiere couldn't import ${baseName(cmd.xml)}.`);
  let added = [];
  for (let n = 0; n < 120 && added.length < cmd.count; n++) {     // the timelines show up a moment after the import returns
    added = (await project.getSequences()).filter((s) => !before.has(s.guid.toString()));
    if (added.length < cmd.count) await new Promise((r) => setTimeout(r, 250));
  }
  if (!added.length) return reply(false, `Premiere read ${baseName(cmd.xml)} but no timeline showed up.`);
  if (cmd.srts && cmd.srts.length) {
    doing = "importing the caption files";
    const BIN = "Shorts Toolkit captions (text)";
    const root = await project.getRootItem();
    let bin = (await rootItems(project)).find((x) => x.name === BIN);
    if (!bin) {
      try {
        project.lockedAccess(() => project.executeTransaction((ca) => ca.addAction(root.createBinAction(BIN, true)), "Add caption bin"));
        bin = (await rootItems(project)).find((x) => x.name === BIN);
      } catch (e) { log("No caption bin: " + e); }
    }
    const folder = bin && ppro.FolderItem.cast(bin.it);
    try { await project.importFiles(cmd.srts, true, folder || root); }
    catch (e) { log("Caption files not imported: " + e); }
  }
  try { await project.setActiveSequence(added[0]); } catch (e) { /* stays on whatever was open */ }
  doing = "saving the project";
  await project.save();
  return reply(true, `${baseName(cmd.project)} has ${added.length} new timeline${added.length === 1 ? "" : "s"}.`);
}

const OPS = { transcribe, markers: placeMarkers, open: openProject, newproject: projectFromClip, shortsproject: shortsProject, speakers };

function work() {
  if (busy || !todo.length) return;
  const { port, cmd } = todo.shift();
  // run it without holding up check-ins, so the apps keep seeing this panel
  busy = true;
  show("Working…", "busy");
  Promise.resolve().then(() => (OPS[cmd.op] ? OPS[cmd.op](port, cmd) : null))
    .catch((e) => {
      log("Error: " + e);
      return post(port, "/api/bridge/report", { job: cmd.job, rid: cmd.rid, ok: false, message: "Speech panel error: " + e,
                                                  error: "Speech panel error: " + e }).catch(() => {});
    })
    .finally(() => { busy = false; doing = ""; work(); });
}

async function tick() {
  ticks++;
  try {
    const i = await info();
    // the apps that are there, every time; the other ports now and then
    const ask = PORTS.filter((p) => live.has(p) || ticks % 4 === 1);
    await Promise.all(ask.map((p) => post(p, "/api/bridge/hello", i, 1200).then((r) => {
      live.add(p);
      if (r && r.command) todo.push({ port: p, cmd: r.command });
    }, () => { live.delete(p); })));
    if (!busy) {
      if (live.size) show(i.project ? `Connected · ${baseName(i.project)}` : "Connected · no project open", "on");
      else show("Shorts Toolkit isn't open", "off");
    }
    work();
  } catch (e) {
    log("Error: " + e);
  }
  setTimeout(tick, live.size ? 1500 : 3000);
}

tick();
