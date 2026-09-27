"""Premiere Shorts Toolkit - main script.

    python shorts.py markers  "Project.prproj" (or "clip.mp4")   markers where the best Shorts are
    python shorts.py captions "Project.prproj" [--fix]   check caption timing / write a synced COPY
    python shorts.py screams  "Project.prproj"           growing-letter scream captions
    python shorts.py shorts   "Project.prproj" --from-markers   list of Shorts from your markers
    python shorts.py make     "Project.prproj"           render every Short in the list
    python shorts.py prepare  "Project.prproj"           loud/scream data for animate-captions.jsx
    python shorts.py style    "Project.prproj" --preview 6:18   try the look on a few seconds
    python shorts.py speech   "Project.prproj"           words for Premiere captions (the app's bridge)
Or just double-click "Shorts Toolkit.cmd" for the app.

Save the project in Premiere (Ctrl+S) first - this reads the file on disk.
The original .prproj is never modified.
"""
import argparse
import csv
import os
import re
import sys
from statistics import median

import captions as cap
from prproj import TICKS, Project

__version__ = "0.11.3"

# What counts as "off". Seconds.
START_TOL = 0.5       # caption appears this much before/after the first word.
                      # Measured on real footage: Whisper packs words end to end, so a
                      # pause is absorbed into the next word's start. Under ~0.5s the
                      # measurement is not trustworthy, so it is not called an error.
CUTOFF_TOL = 0.3      # caption disappears this much before the last word ends
LINGER_TOL = 1.5      # caption stays up this long after the last word


def classify(c, m):
    if not c.text:
        return ["empty"]
    if m["speech_start"] is None or m["ratio"] < 0.5:
        return ["no-match"]
    issues = []
    d = c.start_s - m["speech_start"]
    if m.get("first_heard"):
        if d < -START_TOL:
            issues.append("early")
        elif d > START_TOL:
            issues.append("late")
    if m.get("last_heard"):
        if c.end_s < m["speech_end"] - CUTOFF_TOL:
            issues.append("cut-off")
        elif c.end_s - m["speech_end"] > LINGER_TOL:
            issues.append("lingers")
    return issues or ["ok"]


def open_sequence(args):
    """(project, sequence, stem, base, outdir) for the one sequence with captions."""
    proj = Project(args.project)
    seqs = [s for s in proj.sequences() if s.captions]
    if args.sequence:
        seqs = [s for s in seqs if s.name == args.sequence]
    if not seqs:
        sys.exit("No sequence with captions found%s." % (" named %r" % args.sequence if args.sequence else ""))
    if len(seqs) > 1:
        sys.exit("Several sequences have captions - pick one with --sequence: %s"
                 % ", ".join(repr(s.name) for s in seqs))
    stem = os.path.splitext(args.project)[0]
    # a synced copy shares the original's cache/report folder (same audio)
    base = re.sub(r"_captions-synced(-v\d+)?$", "", stem)
    outdir = base + "_captions"
    os.makedirs(outdir, exist_ok=True)
    return proj, seqs[0], stem, base, outdir


def parse_time(t):
    """'50:05', '1:02:03.5' or '3005' -> seconds."""
    sec = 0.0
    for part in str(t).strip().split(":"):
        sec = sec * 60 + float(part)
    return sec


def load_ctx(args, need_words=True):
    import pipeline
    return pipeline.load(args.project, sequence=getattr(args, "sequence", None),
                         model=getattr(args, "model", "small"), need_words=need_words)


def scream_plan(ctx, args=None):
    import screams as sc
    cfg = dict(ctx.cfg["screams"])
    if args is not None and getattr(args, "loud", None) is not None:
        cfg["loud"] = args.loud
    return sc.plan_screams(ctx.captions, ctx.regions, ctx.words, ctx.audio, cfg,
                           sound_events=getattr(ctx, "sounds", None))


def laugh_plan(ctx, screams):
    import laughs
    on = [(p["start"], p["end"]) for p in screams if p["on"]]
    return laughs.plan_laughs(ctx.captions, ctx.audio, getattr(ctx, "sounds", None), ctx.regions,
                              ctx.cfg["laughs"], screams_on=on)


def cmd_screams(args):
    """Screams + laughs -> screams.json / laughs.json (for the app) and
    captions-with-screams.srt (a full caption track for Premiere)."""
    import json
    import laughs as lg
    import screams as sc
    ctx = load_ctx(args)
    plan = scream_plan(ctx, args)
    lplan = laugh_plan(ctx, plan)
    hidden = sc.replaced_captions(ctx.captions, plan) | lg.hidden_by(ctx.captions, lplan)
    cues = [[c.start_s, c.end_s, c.text] for c in ctx.captions if c.text and c.index not in hidden]
    listing = []
    for p in plan:
        grow = sc.cues_for(ctx.audio, p["start"], p["end"], p["tpl"], p["bang"])
        if p["on"]:
            cues += grow
        listing.append(dict(start=round(p["start"], 2), end=round(p["end"], 2), at=cap.fmt(p["start"]),
                            seconds=round(p["end"] - p["start"], 2), loud=round(p["loud"], 2),
                            spelled=grow[-1][2], source=p["source"], on=p["on"], was=p["was"],
                            letters=p.get("letters"), check=p["end"] - p["start"] > 3.0))
    llisting = []
    for p in lplan:
        grow = lg.cues_for(ctx.audio, p)
        if p["on"]:
            cues += grow
        llisting.append(dict(start=round(p["start"], 2), end=round(p["end"], 2), at=cap.fmt(p["start"]),
                             seconds=round(p["end"] - p["start"], 2), loud=round(p["loud"], 2),
                             peak=round(p["peak"], 2), kind=p["kind"], style=p["style"],
                             spelled=grow[-1][2] if grow else "", source=p["source"], on=p["on"]))
    cues.sort(key=lambda c: c[0])
    for a, b in zip(cues, cues[1:]):
        if a[1] > b[0]:
            a[1] = b[0]
    cues = [c for c in cues if c[1] - c[0] > 0.001]
    sc.write_srt(os.path.join(ctx.outdir, "captions-with-screams.srt"), cues)
    with open(os.path.join(ctx.outdir, "screams.json"), "w", encoding="utf-8") as f:
        json.dump(listing, f, indent=1)
    with open(os.path.join(ctx.outdir, "laughs.json"), "w", encoding="utf-8") as f:
        json.dump(llisting if getattr(ctx, "sounds", None) is not None else None, f, indent=1)
    on = [x for x in listing if x["on"]]
    print("\n%d scream(s) on, %d suggestion(s) off:" % (len(on), len(listing) - len(on)))
    for x in on:
        print("  %s  %.1fs  %-28s %s%s" % (x["at"], x["seconds"], x["spelled"], x["source"],
                                           "  <- CHECK: long" if x["check"] else ""))
    lon = [x for x in llisting if x["on"]]
    if getattr(ctx, "sounds", None) is None:
        print("\nLaughs: detection not installed (see README).")
    else:
        print("\n%d laugh(s) on, %d suggestion(s) off:" % (len(lon), len(llisting) - len(lon)))
        for x in lon:
            print("  %s  %.1fs  %-22s %s" % (x["at"], x["seconds"], x["spelled"], x["kind"]))
    print("Switch suggestions on/off in the app (Screams & laughs tab) or in toolkit.json.")


def loud_lines(ctx, plan):
    import screams as sc
    import style
    normal = sc.talk_level(ctx.audio, ctx.regions)
    hidden = sc.replaced_captions(ctx.captions, plan)
    return [(c.start_s, c.end_s) for c in ctx.captions
            if c.text and c.index not in hidden and normal
            and sc.loudness(ctx.audio, c.start_s, c.end_s) / normal >= style.STYLE["loud_ratio"]]


def write_marker_csv(outdir, shorts):
    """shorts-markers.csv for premiere/shorts-to-markers.jsx (ExtendScript has no JSON)."""
    path = os.path.join(outdir, "shorts-markers.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("start,end,name\n")
        for s in shorts:
            f.write("%.3f,%.3f,%s\n" % (float(s["start"]), float(s["end"]), s["name"].replace(",", " ").replace("\n", " ")))
    return path


def write_suggested_csv(outdir, markers):
    """suggested-markers.csv for premiere/suggested-markers.jsx."""
    path = os.path.join(outdir, "suggested-markers.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("start,end,name\n")
        for m in markers:
            label = "%s (%s)" % (m["name"], m["why"].replace(", ", "; ")) if m.get("why") else m["name"]
            f.write("%.3f,%.3f,%s\n" % (float(m["start"]), float(m["end"]), label.replace(",", " ").replace("\n", " ")))
    return path


def analyse(ctx, args):
    """The per-second picture of the video (screams, laughs, loud lines, excitement)."""
    import timeline
    plan = scream_plan(ctx, args)
    lplan = laugh_plan(ctx, plan)
    print("[timeline] scoring every second")
    return timeline.summary(ctx, plan, lplan, loud_lines(ctx, plan))


def taken(cfg):
    """Ranges never to suggest again: Shorts, placed markers, anything you dismissed."""
    return ([(s["start"], s["end"]) for s in cfg["shorts"]] + [(m["start"], m["end"]) for m in cfg.get("markers", [])]
            + [tuple(d) for d in cfg.get("dismissed", [])])


def save_timeline(ctx, summ, args):
    import json
    import timeline
    summ["suggestions"] = timeline.suggest(summ, count=args.count, length=(args.min, args.max), avoid=taken(ctx.cfg))
    summ["settings"] = dict(count=args.count, min=args.min, max=args.max)
    with open(os.path.join(ctx.outdir, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f)
    write_marker_csv(ctx.outdir, ctx.cfg["shorts"])
    return summ


def cmd_timeline(args):
    """timeline.json: per-second picture of the video + predicted Shorts, for the app."""
    ctx = load_ctx(args)
    # never re-suggest what's already a Short, a marker, or dismissed - "More" digs further down
    summ = save_timeline(ctx, analyse(ctx, args), args)
    print("\n%d suggested Short(s), best first:" % len(summ["suggestions"]))
    for s in summ["suggestions"]:
        print("  %3d  %s - %s  (%2.0fs)  %s" % (s["score"], cap.fmt(s["start"]), cap.fmt(s["end"]),
                                              s["end"] - s["start"], s["why"]))


def cmd_speech(args):
    """Timeline words for the Premiere bridge: <outdir>/premiere-words.json. The app
    turns them into caption lines and has Premiere lay them on a caption track."""
    import json
    import pipeline
    ctx = pipeline.load(args.project, args.sequence, need_words=False)
    words = cap.transcribe(ctx.audio, ctx.outdir, model=args.model)
    out = os.path.join(ctx.outdir, "premiere-words.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump([w[:3] for w in words], f)
    print("%d words -> %s" % (len(words), out))


def cmd_markers(args):
    """Step 1: place range markers where the best Shorts are. Run again for more -
    it skips every marker already placed, every Short and everything you removed."""
    import config
    import timeline
    import pipeline
    ctx = load_ctx(args)
    cfg = ctx.cfg
    if args.replace:
        print("Starting over: removing %d suggested marker(s)" % len(cfg["markers"]))
        cfg["markers"] = []
    summ = analyse(ctx, args)
    found = timeline.suggest(summ, count=args.count, length=(args.min, args.max), avoid=taken(cfg))
    n0 = len(cfg["markers"])
    for s in found:
        cfg["markers"].append(dict(start=s["start"], end=s["end"], score=s["score"], why=s["why"]))
    cfg["markers"].sort(key=lambda m: m["start"])
    for k, m in enumerate(cfg["markers"]):          # numbered in time order, whenever they were found
        m["name"] = "Marker %02d - %s" % (k + 1, cap.fmt(m["start"])[:-3])
    config.save(ctx.outdir, cfg)
    write_suggested_csv(ctx.outdir, cfg["markers"])
    # the timeline (step 3) shows the new markers and suggests around them
    ctx.seq.markers = pipeline.with_toolkit_markers(ctx.own_markers, cfg)
    summ["markers"] = [dict(t=round(m.start_s, 3), dur=round(m.dur_s, 3), name=m.name) for m in ctx.seq.markers]
    save_timeline(ctx, summ, argparse.Namespace(count=12, min=args.min, max=args.max))
    if not found:
        print("\nNo more good moments left at %g-%gs long - try a different length, or remove markers you don't want." % (args.min, args.max))
        return
    print("\nPlaced %d marker(s)%s, best first:" % (len(found), " (%d in total)" % len(cfg["markers"]) if n0 else ""))
    for s in found:
        print("  %3d  %s - %s  (%2.0fs)  %s" % (s["score"], cap.fmt(s["start"]), cap.fmt(s["end"]),
                                              s["end"] - s["start"], s["why"]))


def cmd_prepare(args):
    """premiere-emphasis.csv: loud lines and screams for premiere/animate-captions.jsx."""
    import screams as sc
    import style
    ctx = load_ctx(args)
    plan = scream_plan(ctx, args)
    normal = sc.talk_level(ctx.audio, ctx.regions)
    hidden = sc.replaced_captions(ctx.captions, plan)
    rows = []
    for c in ctx.captions:
        if not c.text or c.index in hidden:
            continue
        r = sc.loudness(ctx.audio, c.start_s, c.end_s) / normal if normal else 0
        if r >= style.STYLE["loud_ratio"]:
            rows.append((c.start_s, c.end_s, "loud", r, c.text))
    for p in plan:
        if p["on"]:
            rows.append((p["start"], p["end"], "scream", p["loud"], ""))
    for p in laugh_plan(ctx, plan):
        if p["on"]:
            rows.append((p["show"][0], p["show"][1], "laugh", p["peak"], ""))
    rows.sort()
    path = os.path.join(ctx.outdir, "premiere-emphasis.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("start,end,kind,strength,text\n")
        for s, e, kind, r, text in rows:
            f.write("%.3f,%.3f,%s,%.2f,%s\n" % (s, e, kind, r, text.replace("\n", " ")))
    kinds = {k: sum(1 for r in rows if r[2] == k) for k in ("loud", "scream", "laugh")}
    print("\n%d loud line(s), %d scream(s), %d laugh(s) marked for Premiere -> %s"
          % (kinds["loud"], kinds["scream"], kinds["laugh"], path))
    print("Now run premiere/animate-captions.jsx - it finds this file next to your project.")


def shorts_dir(ctx):
    d = ctx.base + "_shorts"
    os.makedirs(d, exist_ok=True)
    return d


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip() or "short"


def cmd_make(args):
    """Render finished vertical Shorts straight from the project."""
    import render
    import style
    ctx = load_ctx(args)
    plan = scream_plan(ctx, args)
    events = style.build(ctx, plan)
    jobs = []
    if args.start is not None:
        a, b = parse_time(args.start), parse_time(args.end)
        jobs.append((args.name or "short %s" % cap.fmt(a).replace(":", "-"), a, b))
    else:
        items = ctx.cfg["shorts"]
        if args.index is not None:
            items = [items[args.index]]
        elif args.indexes:
            items = [items[int(i)] for i in args.indexes.split(",") if i.strip() and int(i) < len(items)]
        jobs = [(s["name"], float(s["start"]), float(s["end"])) for s in items]
    if not jobs:
        sys.exit("No Shorts to render - add some in the app, or pass --start and --end.")
    out = args.out or shorts_dir(ctx)
    os.makedirs(out, exist_ok=True)
    import glob
    for leftover in glob.glob(os.path.join(out, "*.part.mp4")):   # from a stopped render
        try:
            os.remove(leftover)
        except OSError:
            pass
    for n, (name, a, b) in enumerate(jobs, 1):
        if b <= a:
            print("  skipping %r: end is before start" % name)
            continue
        print("[%d/%d] %s  (%s - %s)" % (n, len(jobs), name, cap.fmt(a), cap.fmt(b)))
        path = os.path.join(out, safe_name(name) + ".mp4")
        render.make_short(ctx, a, b, path, events, preset=args.preset)
        print("  -> %s" % path)
    print("\nDone. Shorts are in %s" % out)


def cmd_shorts(args):
    """List / add / import the project's Shorts (kept in toolkit.json)."""
    import config
    ctx = load_ctx(args, need_words=False)
    cfg = ctx.cfg
    if args.from_markers:
        seq = ctx.seq
        cuts = [m.start_s for m in seq.markers] + [seq.end_s]
        have = {(round(s["start"], 1), round(s["end"], 1)) for s in cfg["shorts"]}
        added = 0
        for a, b in zip(cuts, cuts[1:]):
            if not (args.min <= b - a <= args.max) or (round(a, 1), round(b, 1)) in have:
                continue
            cfg["shorts"].append(dict(name="Clip %02d - %s" % (len(cfg["shorts"]) + 1, cap.fmt(a)[:-3]),
                                      start=round(a, 3), end=round(b, 3)))
            added += 1
        print("Added %d Short(s) from %d markers (segments %g-%gs long)." % (added, len(seq.markers), args.min, args.max))
    if args.add:
        a, b = parse_time(args.add[0]), parse_time(args.add[1])
        cfg["shorts"].append(dict(name=args.name or "Short - %s" % cap.fmt(a)[:-3], start=a, end=b))
        print("Added %s - %s" % (cap.fmt(a), cap.fmt(b)))
    config.save(ctx.outdir, cfg)
    for i, s in enumerate(cfg["shorts"]):
        print("  %2d  %-32s %s - %s  (%.0fs)" % (i, s["name"], cap.fmt(s["start"]), cap.fmt(s["end"]), s["end"] - s["start"]))


def cmd_style(args):
    """Preview the burned-in look, or burn it onto a Premiere export."""
    import render
    import style
    ctx = load_ctx(args)
    if args.no_highlight:
        ctx.cfg["look"]["highlight"] = False
    plan = scream_plan(ctx, args)
    events = style.build(ctx, plan)
    if args.preview is not None:
        t0 = parse_time(args.preview)
        out = os.path.join(ctx.outdir, "preview-%s.mp4" % cap.fmt(t0).replace(":", "-"))
        render.make_short(ctx, t0, min(t0 + args.seconds, ctx.seq.end_s), out, events, preset="veryfast", crf=20)
        print("Preview (%.0fs from %s) -> %s" % (args.seconds, cap.fmt(t0), out))
        return
    ass = os.path.join(ctx.outdir, "styled-captions.ass")
    style.write_ass(ass, events, st=style.look(ctx.cfg), shift=parse_time(args.start))
    print("Styled captions -> %s" % ass)
    if args.video:
        out = os.path.splitext(args.video)[0] + "_captioned.mp4"
        print("Burning onto %s (audio copied untouched) ..." % args.video)
        style.burn(args.video, ass, out)
        print("Done -> %s" % out)
    else:
        print("Export the sequence from Premiere with captions OFF, then run again with --video <export.mp4>")


def cmd_captions(args):
    proj, seq, stem, base, outdir = open_sequence(args)
    print("Sequence %r: %d captions, %d audio clips" % (seq.name, len(seq.captions), len(seq.audio)))

    print("[1/4] rebuilding the sequence audio")
    audio = cap.timeline_audio(seq)
    print("[2/4] finding spoken words")
    words = cap.transcribe(audio, outdir, model=args.model)
    print("  %d words heard" % len(words))
    regions = cap.voice_regions(audio, outdir)
    print("  %d stretches of voice" % len(regions))
    print("[3/4] matching captions to speech")
    matches = cap.align(seq.captions, words)
    proposed, offsets = cap.retime(seq.captions, matches, seq.caption_frame)

    rows, counts = [], {}
    for c, m in zip(seq.captions, matches):
        issues = classify(c, m)
        for i in issues:
            counts[i] = counts.get(i, 0) + 1
        ns, ne = proposed[c.index]
        rows.append(dict(
            n=c.index + 1, text=c.text, status="+".join(issues),
            caption_start=round(c.start_s, 3), caption_end=round(c.end_s, 3),
            caption_dur=round(c.end_s - c.start_s, 3),
            speech_start=m["speech_start"], speech_end=m["speech_end"],
            speech_dur=round(m["speech_end"] - m["speech_start"], 3) if m["speech_start"] is not None else None,
            start_off=round(c.start_s - m["speech_start"], 3) if m["speech_start"] is not None else None,
            match=round(m["ratio"], 2),
            new_start=round(ns / TICKS, 3), new_end=round(ne / TICKS, 3)))

    uncaptioned = uncaptioned_speech(seq.captions, words)
    no_audio = [c for c in seq.captions if not any(a.start <= c.start < a.end for a in seq.audio)]

    print("[4/4] writing the report")
    csv_path = os.path.join(outdir, "caption-report.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = summarize(seq, rows, counts, offsets, uncaptioned, no_audio)
    with open(os.path.join(outdir, "last-check.txt"), "w", encoding="utf-8") as f:
        f.write(os.path.abspath(args.project))       # which version this report describes
    txt_path = os.path.join(outdir, "caption-report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print()
    print(summary)
    print("Full per-caption table: %s" % csv_path)

    if args.fix:
        changes = {}
        for c, r in zip(seq.captions, rows):
            st = r["status"].split("+")
            if "no-match" in st or "empty" in st:
                continue                    # no evidence - never move these
            ps, pe = proposed[c.index]
            if args.all:
                changes[c.index] = (ps, pe)
                continue
            # change only the edge that is wrong
            s = ps if ("early" in st or "late" in st) else c.start
            e = pe if ("cut-off" in st or "lingers" in st) else c.end
            if e <= s:
                e = pe
            if (s, e) != (c.start, c.end):
                changes[c.index] = (s, e)
        if not args.no_durations:
            changes, _ = fit_durations(seq, matches, regions, changes, words)
        new = settle(seq.captions, changes, seq.caption_frame)
        old = {c.index: c for c in seq.captions}
        print("\nChanges: %d start(s) moved, %d caption(s) made longer, %d made shorter" % (
            sum(1 for i, (s, e) in new.items() if s != old[i].start),
            sum(1 for i, (s, e) in new.items() if e > old[i].end),
            sum(1 for i, (s, e) in new.items() if e < old[i].end)))
        final = [new.get(c.index, (c.start, c.end)) for c in seq.captions]
        flash = [(c, (e - s) / TICKS) for c, (s, e) in zip(seq.captions, final)
                 if c.text and (e - s) / TICKS < 0.3]
        if flash:
            path = os.path.join(outdir, "too-short-captions.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Captions on screen < 0.3 s with no room to extend (the next caption\n"
                        "starts right after). Merge each into its neighbour in Premiere.\n\n")
                for c, d in flash:
                    f.write("%s  %.2fs  %s\n" % (cap.fmt(c.start_s), d, c.text))
            print("%d caption(s) too short to read with no room to extend - listed in %s"
                  % (len(flash), path))
        out = next_output(base, stem)
        changed = proj.write_patched(seq.captions, new, out)
        verify(out, seq.name, new)
        print("\nFixed %d caption(s) -> %s" % (changed, out))
        print("Open that file in Premiere. Your original project is untouched.")


def fit_durations(seq, matches, regions, changes, words):
    """Merge sound-fitted end times into the start/end changes."""
    frame = seq.caption_frame
    snap = lambda sec: int(round(sec * TICKS / frame)) * frame
    times = {c.index: tuple(t / TICKS for t in changes.get(c.index, (c.start, c.end)))
             for c in seq.captions}
    ends, notes = cap.fit_durations(seq.captions, matches, regions, times, words)
    kinds = {}
    for i, e in ends.items():
        c = seq.captions[i]
        s = changes.get(i, (c.start, c.end))[0]
        e = max(snap(e), s + frame)
        old_end = changes.get(i, (c.start, c.end))[1]
        if e != old_end:
            changes[i] = (s, e)
            k = ("longer" if e > old_end else "shorter") + " (%s)" % notes[i]
            kinds[k] = kinds.get(k, 0) + 1
    # Any caption too short to read gets extended into EMPTY space only
    # (never pushes the next caption), including ones we had no evidence for.
    cur = [changes.get(c.index, (c.start, c.end)) for c in seq.captions]
    for i, c in enumerate(seq.captions):
        s, e = cur[i]
        need = min(1.5, max(0.5, len(c.text) / 20.0)) if c.text else 0
        limit = cur[i + 1][0] if i + 1 < len(cur) else e + TICKS * 10
        want = min(snap(s / TICKS + need), limit)
        if want > e:
            cur[i] = (s, want)
            changes[i] = (s, want)
            kinds["longer (readable minimum)"] = kinds.get("longer (readable minimum)", 0) + 1
    return changes, kinds


def next_output(base, stem):
    """V0.4.prproj -> V0.4_captions-synced.prproj; a synced copy -> -v2, -v3 ..."""
    m = re.search(r"_captions-synced(?:-v(\d+))?$", stem)
    n = (int(m.group(1) or 1) + 1) if m else None
    while True:
        out = base + "_captions-synced" + ("-v%d" % n if n else "") + ".prproj"
        if not os.path.exists(out):
            return out
        n = (n or 1) + 1


def settle(captions, changes, frame):
    """Apply changes and push neighbours just enough that nothing overlaps."""
    times = [changes.get(c.index, (c.start, c.end)) for c in captions]
    for i in range(1, len(times)):
        ps, pe = times[i - 1]
        s, e = times[i]
        if s < pe:
            if s - ps >= frame:
                times[i - 1] = (ps, s)          # shorten the previous caption
            else:
                s = pe                           # or start this one right after it
                times[i] = (s, max(e, s + frame))
    return {c.index: t for c, t in zip(captions, times) if t != (c.start, c.end)}


def verify(path, seq_name, new):
    """Re-read what we wrote and check it says what we meant."""
    seq = [s for s in Project(path).sequences() if s.name == seq_name][0]
    by_start = {(c.start, c.end) for c in seq.captions}
    missing = [i for i, t in new.items() if t not in by_start]
    overlaps = sum(1 for a, b in zip(seq.captions, seq.captions[1:]) if b.start < a.end)
    if missing or overlaps:
        os.replace(path, path + ".FAILED")
        sys.exit("Verification failed (%d not written, %d overlaps) - output renamed to .FAILED"
                 % (len(missing), overlaps))


def uncaptioned_speech(captions, words, min_len=1.0):
    """Stretches of confidently heard speech with no caption on screen."""
    spans, cur = [], None
    ci = 0
    for w in words:
        if w[3] < 0.5:
            continue
        while ci < len(captions) and captions[ci].end_s <= w[0]:
            ci += 1
        covered = ci < len(captions) and captions[ci].start_s <= w[0] < captions[ci].end_s
        if covered:
            cur = None
            continue
        if cur and w[0] - cur[1] < 1.0:
            cur[1] = w[1]
            cur[2].append(w[2])
        else:
            cur = [w[0], w[1], [w[2]]]
            spans.append(cur)
    return [s for s in spans if s[1] - s[0] >= min_len]


def summarize(seq, rows, counts, offsets, uncaptioned, no_audio):
    n = len(rows)
    L = []
    L.append("CAPTION TIMING REPORT - %s" % seq.name)
    L.append("=" * 60)
    L.append("Captions checked:           %d" % n)
    order = [("ok", "In sync"), ("early", "Appear too EARLY"), ("late", "Appear too LATE"),
             ("cut-off", "Disappear before speech ends"), ("lingers", "Stay up long after speech"),
             ("no-match", "Could not match to speech"), ("empty", "Empty (no text)")]
    for k, label in order:
        if counts.get(k):
            L.append("  %-28s %5d  (%.0f%%)" % (label, counts[k], 100.0 * counts[k] / n))
    if offsets:
        vals = sorted(-v for v in offsets.values())
        L.append("")
        L.append("How far captions start from the first spoken word (+ = caption late):")
        L.append("  median %+.2fs   middle 90%%: %+.2fs to %+.2fs"
                 % (median(vals), vals[int(len(vals) * .05)], vals[int(len(vals) * .95)]))
        L.append("  Over the timeline (median per 5 minutes) - a steady climb means drift:")
        buckets = {}
        for i, off in offsets.items():
            buckets.setdefault(int(rows[i]["caption_start"] // 300), []).append(-off)
        for b in sorted(buckets):
            v = median(buckets[b])
            bar = ("#" * min(30, int(abs(v) * 20))) or "."
            L.append("   %s  %+.2fs %s" % (cap.fmt(b * 300)[:-3], v, bar))
    if uncaptioned:
        L.append("")
        L.append("Speech with NO caption on screen (%d spans of 1s+):" % len(uncaptioned))
        for s in uncaptioned[:15]:
            L.append("   %s  \"%s\"" % (cap.fmt(s[0]), " ".join(s[2])[:60]))
        if len(uncaptioned) > 15:
            L.append("   ... and %d more" % (len(uncaptioned) - 15))
    if no_audio:
        L.append("")
        L.append("Captions sitting where there is no audio clip: %d (first at %s)"
                 % (len(no_audio), cap.fmt(no_audio[0].start_s)))
    empties = [r for r in rows if r["status"] == "empty"]
    if empties:
        L.append("")
        L.append("Empty captions at: " + ", ".join(cap.fmt(r["caption_start"]) for r in empties[:12])
                 + (" ..." if len(empties) > 12 else ""))
    L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Premiere Shorts Toolkit v%s" % __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("captions", help="check caption timing against the audio (and --fix it)")
    c.add_argument("project", help="saved .prproj file")
    c.add_argument("--sequence", help="sequence name, if more than one has captions")
    c.add_argument("--model", default="small",
                   help="Whisper model: tiny, base, small (default), medium, large-v3")
    c.add_argument("--fix", action="store_true", help="write <project>_captions-synced.prproj")
    c.add_argument("--all", action="store_true", help="with --fix: retime every caption, not just flagged ones")
    c.add_argument("--no-durations", action="store_true",
                   help="with --fix: don't fit caption lengths to the sound, only fix timing errors")
    c.set_defaults(func=cmd_captions)
    def common(p, words=True):
        p.add_argument("project", help="saved .prproj file, or any video clip (.mp4 .mov .mkv ...)")
        p.add_argument("--sequence", help="sequence name (default: the one with captions)")
        if words:
            p.add_argument("--model", default="small", help="Whisper model (must match the cached transcript)")

    k = sub.add_parser("screams", help="growing-letter scream captions (plan + .srt)")
    common(k)
    k.add_argument("--loud", type=float, help="how much louder than normal talk a scream must be (project setting if omitted)")
    k.set_defaults(func=cmd_screams)

    r = sub.add_parser("prepare", help="mark loud lines + screams for premiere/animate-captions.jsx")
    common(r)
    r.add_argument("--loud", type=float, help="scream threshold (project setting if omitted)")
    r.set_defaults(func=cmd_prepare)

    m = sub.add_parser("make", help="render finished vertical Shorts straight from the project")
    common(m)
    m.add_argument("--start", help="render one range: start (e.g. 6:18)")
    m.add_argument("--end", help="...and end (e.g. 6:45)")
    m.add_argument("--name", help="file name for --start/--end")
    m.add_argument("--index", type=int, help="render only this Short from the project's list")
    m.add_argument("--indexes", help="render these Shorts, e.g. 0,3,5")
    m.add_argument("--out", help="folder for the videos (default: <project>_shorts)")
    m.add_argument("--preset", default="medium", help="x264 speed: veryfast (quick) ... slow (smaller file)")
    m.add_argument("--loud", type=float, help="scream threshold (project setting if omitted)")
    m.set_defaults(func=cmd_make)

    t = sub.add_parser("shorts", help="list / add Shorts, or import them from sequence markers")
    common(t, words=False)
    t.add_argument("--from-markers", action="store_true", help="add every marker-to-marker segment")
    t.add_argument("--min", type=float, default=5, help="with --from-markers: shortest segment, s")
    t.add_argument("--max", type=float, default=180, help="with --from-markers: longest segment, s")
    t.add_argument("--add", nargs=2, metavar=("START", "END"), help="add one Short, e.g. --add 6:18 6:45")
    t.add_argument("--name", help="name for --add")
    t.set_defaults(func=cmd_shorts)

    mk = sub.add_parser("markers", help="step 1: place markers where the best Shorts are (run again for more)")
    common(mk)
    mk.add_argument("--count", type=int, default=10, help="how many new markers to place (default 10)")
    mk.add_argument("--min", type=float, default=20, help="shortest, s (default 20)")
    mk.add_argument("--max", type=float, default=45, help="longest, s (default 45)")
    mk.add_argument("--replace", action="store_true", help="start over: remove the markers placed before")
    mk.add_argument("--loud", type=float, help="scream threshold (project setting if omitted)")
    mk.set_defaults(func=cmd_markers)

    tl = sub.add_parser("timeline", help="whole-video picture + predicted best Shorts (for the app)")
    common(tl)
    tl.add_argument("--count", type=int, default=12, help="how many Shorts to suggest (default 12)")
    tl.add_argument("--min", type=float, default=20, help="shortest suggestion, s (default 20)")
    tl.add_argument("--max", type=float, default=45, help="longest suggestion, s (default 45)")
    tl.add_argument("--loud", type=float, help="scream threshold (project setting if omitted)")
    tl.set_defaults(func=cmd_timeline)

    sp = sub.add_parser("speech", help="words for Premiere captions (used by the app's Premiere bridge)")
    common(sp)
    sp.set_defaults(func=cmd_speech)

    y = sub.add_parser("style", help="preview the burned-in look, or burn it onto a Premiere export")
    common(y)
    y.add_argument("--video", help="the sequence exported from Premiere WITH CAPTIONS OFF")
    y.add_argument("--start", default="0", help="timeline time the export starts at, if not 0 (e.g. 12:30)")
    y.add_argument("--preview", help="render a short test clip from this timeline time (e.g. 50:05)")
    y.add_argument("--seconds", type=float, default=12, help="preview length (default 12)")
    y.add_argument("--no-highlight", action="store_true", help="no spoken-word highlight")
    y.add_argument("--loud", type=float, help="scream threshold (project setting if omitted)")
    y.set_defaults(func=cmd_style)
    args = ap.parse_args()
    from pipeline import ProjectError
    try:
        args.func(args)
    except ProjectError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
