"""Load a project once, the same way for every command: sequence, audio, words,
voice, captions (Premiere's, or made from speech) and the project's settings."""
import os
import re
from types import SimpleNamespace

import captions as cap
import config
from prproj import Project


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


def load(project_path, sequence=None, model="small", log=print, need_words=True):
    base, outdir = outdir_for(project_path)
    os.makedirs(outdir, exist_ok=True)
    cfg = config.load(outdir)
    proj = Project(project_path)
    seq = pick_sequence(proj, sequence or cfg.get("sequence"))
    log("Sequence %r: %d captions, %d video / %d audio clips" % (seq.name, len(seq.captions), len(seq.video), len(seq.audio)))
    log("[audio] rebuilding the sequence audio")
    audio = cap.timeline_audio(seq, log=log)
    ctx = SimpleNamespace(path=project_path, base=base, outdir=outdir, cfg=cfg, proj=proj, seq=seq, audio=audio)
    if not need_words:
        return ctx
    log("[speech] words and voice")
    ctx.words = cap.transcribe(audio, outdir, model=model, log=log)
    ctx.regions = cap.voice_regions(audio, outdir, log=log)
    import sounds
    ctx.sounds = sounds.detect(seq, outdir, audio, log=log)      # None if not installed
    if seq.captions:
        ctx.captions, ctx.auto = seq.captions, False
        ctx.matches = cap.align(seq.captions, ctx.words)
    else:
        log("  no captions in this sequence - making them from speech")
        ctx.captions, ctx.matches = cap.auto_captions(ctx.words)
        ctx.auto = True
    return ctx
