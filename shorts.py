"""Premiere Shorts Toolkit - main script.

    python shorts.py captions "My Project.prproj"          check caption timing, write a report
    python shorts.py captions "My Project.prproj" --fix    ...and write a synced COPY of the project

Save the project in Premiere (Ctrl+S) first - this reads the file on disk.
The original .prproj is never modified.
"""
import argparse
import csv
import os
import sys
from statistics import median

import captions as cap
from prproj import TICKS, Project

__version__ = "0.1.0"

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


def cmd_captions(args):
    proj = Project(args.project)
    seqs = [s for s in proj.sequences() if s.captions]
    if args.sequence:
        seqs = [s for s in seqs if s.name == args.sequence]
    if not seqs:
        sys.exit("No sequence with captions found%s." % (" named %r" % args.sequence if args.sequence else ""))
    if len(seqs) > 1:
        sys.exit("Several sequences have captions - pick one with --sequence: %s"
                 % ", ".join(repr(s.name) for s in seqs))
    seq = seqs[0]
    stem = os.path.splitext(args.project)[0]
    outdir = stem + "_captions"
    os.makedirs(outdir, exist_ok=True)
    print("Sequence %r: %d captions, %d audio clips" % (seq.name, len(seq.captions), len(seq.audio)))

    print("[1/4] rebuilding the sequence audio")
    audio = cap.timeline_audio(seq)
    print("[2/4] finding spoken words")
    words = cap.transcribe(audio, outdir, model=args.model)
    print("  %d words heard" % len(words))
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
        new = settle(seq.captions, changes, seq.caption_frame)
        out = stem + "_captions-synced.prproj"
        if os.path.exists(out) and not args.overwrite:
            sys.exit("%s already exists - delete it or pass --overwrite" % out)
        changed = proj.write_patched(seq.captions, new, out)
        verify(out, seq.name, new)
        print("\nFixed %d caption(s) -> %s" % (changed, out))
        print("Open that file in Premiere. Your original project is untouched.")


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
    c.add_argument("--overwrite", action="store_true", help="replace an existing synced copy")
    c.set_defaults(func=cmd_captions)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
