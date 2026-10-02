"""Load a project once, the same way for every command: sequence, audio, words,
voice, captions (Premiere's, or made from speech) and the project's settings."""
import os
import re
from types import SimpleNamespace

import captions as cap
import config
from clip import open_project
from prproj import Marker


class ProjectError(Exception):
    """A problem with the project itself (shown to you as a plain message)."""


def outdir_for(project_path):
    base = re.sub(r"_captions-synced(-v\d+)?$", "", os.path.splitext(project_path)[0])
    return base, base + "_captions"


def pick_sequence(proj, wanted=None):
    seqs = proj.sequences()
    if not seqs:
        raise ProjectError("This project has no sequences yet - add your footage to a timeline in Premiere and save.")
    if wanted:
        for s in seqs:
            if s.name == wanted:
                return s
        raise ProjectError("No sequence named %r. Sequences: %s" % (wanted, ", ".join(repr(s.name) for s in seqs)))
    with_caps = [s for s in seqs if s.captions]
    if with_caps:
        return with_caps[0]
    with_audio = [s for s in seqs if s.audio]
    return (with_audio or seqs)[0]


def with_toolkit_markers(markers, cfg):
    """The sequence's own markers plus the ones the toolkit placed (step 1), as range
    markers. A toolkit marker already put into Premiere (same start) isn't doubled."""
    out = list(markers)
    for m in cfg.get("markers", []):
        if not any(abs(x.start_s - m["start"]) < 0.1 for x in markers):
            out.append(Marker(m["start"], m["end"] - m["start"], m["name"]))
    return sorted(out, key=lambda m: m.start_s)


def caption_list(project_path, start=None, end=None):
    """Captions as the app shows them for editing - fast: no audio. Premiere's own, or the
    toolkit's made from the cached transcript (the same ones a render uses)."""
    import glob
    import json
    base, outdir = outdir_for(project_path)
    cfg = config.load(outdir)
    seq = pick_sequence(open_project(project_path), cfg.get("sequence"))
    if seq.captions:
        caps, source = seq.captions, "premiere"
    else:
        cached = sorted(glob.glob(os.path.join(outdir, "words-*.json")), key=os.path.getmtime)
        if not cached:
            return dict(source="none", captions=[])
        with open(cached[-1], encoding="utf-8") as f:
            words = json.load(f)
        voice = sorted(glob.glob(os.path.join(outdir, "voice-*.json")), key=os.path.getmtime)
        regions = None
        if voice:
            with open(voice[-1], encoding="utf-8") as f:
                regions = json.load(f)
        caps, _ = cap.auto_captions(cap.clean_loops(words, regions, cap.retyped(cfg)))   # the same words a render uses
        source = "toolkit"
    edits = cfg.get("caption_edits") or {}
    words = _cached_words(outdir)
    missing = cap.missing_words(caps, words, cfg, start, end) if words else []
    out = []
    for n, a in enumerate(cfg.get("caption_adds") or []):
        if (start is not None and a["end"] < start) or (end is not None and a["start"] > end):
            continue
        out.append(dict(key="add:%d" % n, start=a["start"], end=a["end"], orig=a["text"], text=a["text"],
                        hidden=False, added=True))
    for c in caps:
        if (start is not None and c.end_s < start) or (end is not None and c.start_s > end):
            continue
        k = cap.caption_key(c)
        e = edits.get(k) or {}
        out.append(dict(key=k, start=round(c.start_s, 3), end=round(c.end_s, 3), orig=c.text,
                        text=e.get("text") if e.get("text") is not None else c.text, hidden=bool(e.get("hide")),
                        new_start=e.get("start"), new_end=e.get("end")))
    out.sort(key=lambda x: x["new_start"] if x.get("new_start") is not None else x["start"])
    return dict(source=source, captions=out, missing=missing)


def _cached_words(outdir):
    """The newest cached Whisper words for this project, loops cleaned, or []."""
    import glob
    import json
    cached = sorted(glob.glob(os.path.join(outdir, "words-*.json")), key=os.path.getmtime)
    if not cached:
        return []
    with open(cached[-1], encoding="utf-8") as f:
        return json.load(f)


def load(project_path, sequence=None, model="small", log=print, need_words=True):
    base, outdir = outdir_for(project_path)
    os.makedirs(outdir, exist_ok=True)
    cfg = config.load(outdir)
    proj = open_project(project_path)
    seq = pick_sequence(proj, sequence or cfg.get("sequence"))
    own_markers = seq.markers
    seq.markers = with_toolkit_markers(own_markers, cfg)
    log("Sequence %r: %d captions, %d video / %d audio clips" % (seq.name, len(seq.captions), len(seq.video), len(seq.audio)))
    log("[audio] rebuilding the sequence audio")
    audio = cap.timeline_audio(seq, log=log)
    ctx = SimpleNamespace(path=project_path, base=base, outdir=outdir, cfg=cfg, proj=proj, seq=seq, audio=audio,
                          own_markers=own_markers)
    if not need_words:
        return ctx
    log("[speech] words and voice")
    ctx.words = cap.transcribe(audio, outdir, model=model, log=log)
    ctx.regions = cap.voice_regions(audio, outdir, log=log)
    ctx.words = cap.clean_loops(ctx.words, ctx.regions, cap.retyped(cfg))   # Whisper's repetition loops out
    import sounds
    ctx.sounds = sounds.detect(seq, outdir, audio, log=log)      # None if not installed
    if seq.captions:
        ctx.captions, ctx.auto = seq.captions, False
        ctx.matches = cap.align(seq.captions, ctx.words)
    else:
        log("  no captions in this sequence - making them from speech")
        ctx.captions, ctx.matches = cap.auto_captions(ctx.words)
        ctx.auto = True
    adds = cap.added_captions(cfg, len(ctx.captions))       # captions you added in the app
    if adds:
        order = sorted(list(zip(ctx.captions, ctx.matches)) + adds, key=lambda cm: cm[0].start)
        ctx.captions, ctx.matches = [c for c, _ in order], [m for _, m in order]
    return ctx
