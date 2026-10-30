"""The long video: the project's Shorts as chapters of a longer watch, from the same recording.

Each Short keeps some of the recording around it (long "before" / "after"), moved to the nearest gap in
the talking so a chapter never starts mid-word. Shorts close together in the recording join into one
stretch. The order, titles and which Shorts are in come from toolkit.json "long".

  outline()   the framework: stretches, chapter times, nothing rendered
  describe()  that framework as text, with the chapter lines for the YouTube description
  make()      renders it to <project>_long\\<title>.mp4 (1920x1080): one file per stretch, then joined
              without re-encoding. A stretch whose settings didn't change is not rendered again.

Premiere gets the same outline as one timeline (premiere_export.export_long).
"""
import os
import subprocess

import render
import stale
import style


def _cap(sec):
    sec = int(round(sec))
    return "%d:%02d:%02d" % (sec // 3600, sec // 60 % 60, sec % 60) if sec >= 3600 else "%d:%02d" % (sec // 60, sec % 60)


def title_of(cfg, short):
    return ((cfg.get("long") or {}).get("titles") or {}).get(short["name"]) or short["name"]


def ordered(cfg):
    """The Shorts that are in, in the order you set; anything new goes where it falls in the recording."""
    lg = cfg.get("long") or {}
    skip = set(lg.get("skip") or [])
    rest = sorted((s for s in cfg.get("shorts") or [] if s["name"] not in skip), key=lambda s: float(s["start"]))
    by_name = {s["name"]: s for s in rest}
    first = [by_name[n] for n in lg.get("order") or [] if n in by_name]
    seen = {s["name"] for s in first}
    return first + [s for s in rest if s["name"] not in seen]


def snap_start(t, voice, reach=3.0):
    """t, or the start of the talking it lands in if that is close enough."""
    for s, e in voice or []:
        if s < t < e:
            return max(s - 0.1, 0.0) if t - s <= reach else t
    return t


def snap_end(t, voice, end, reach=3.0):
    for s, e in voice or []:
        if s < t < e:
            return min(e + 0.1, end) if e - t <= reach else t
    return t


def outline(cfg, m, end):
    """[{start, end, title, shorts: [names], at: where it begins in the long video, seconds}]."""
    lg = cfg.get("long") or {}
    before, after, join = (float(lg.get(k) or 0) for k in ("before", "after", "join"))
    voice = (m or {}).get("voice")
    out = []
    for s in ordered(cfg):
        a = snap_start(max(0.0, float(s["start"]) - before), voice)
        b = snap_end(min(end, float(s["end"]) + after), voice, end)
        a, b = min(a, float(s["start"])), max(b, min(end, float(s["end"])))
        last = out[-1] if out else None
        if last and -0.001 <= a - last["end"] <= join or last and a < last["end"] and b > last["start"] and a >= last["start"]:
            last["end"] = max(last["end"], b)        # next to each other in the recording: one stretch, one chapter
            last["shorts"].append(s["name"])
        else:
            out.append(dict(start=round(a, 3), end=round(b, 3), title=title_of(cfg, s), shorts=[s["name"]]))
    at = 0.0
    for p in out:
        p["at"] = round(at, 3)
        at += p["end"] - p["start"]
    return out


def total(parts):
    return sum(p["end"] - p["start"] for p in parts)


def chapters(parts):
    """The lines for a YouTube description."""
    return ["%s %s" % (_cap(p["at"]), p["title"]) for p in parts]


def problems(parts):
    """Why YouTube wouldn't show these as chapters."""
    out = []
    if len(parts) < 3:
        out.append("YouTube needs at least 3 chapters to show them; this has %d." % len(parts))
    short = [p["title"] for p in parts if p["end"] - p["start"] < 10]
    if short:
        out.append("YouTube needs every chapter to be 10 s or longer: " + ", ".join(short))
    return out


def describe(cfg, parts):
    lines = ["%d chapters, %s long, from %d Shorts" % (len(parts), _cap(total(parts)), sum(len(p["shorts"]) for p in parts))]
    return "\n".join(lines + chapters(parts) + problems(parts))


def folder(ctx):
    d = ctx.base + "_long"
    os.makedirs(d, exist_ok=True)
    return d


def safe(name):
    import re
    return re.sub(r'[<>:"/\\|?*]+', "-", name).strip(" .") or "long video"


def _key(ctx, p, lg):
    """A stretch's render depends on these; same key = the file from last time is still right."""
    c = ctx.cfg
    return stale._h([p["start"], p["end"], p["title"], p["at"] == 0, lg.get("captions"), lg.get("chapter_cards"), lg.get("fade"), lg.get("music"),
                     c.get("look"), c.get("bleep"), c.get("sfx"), c.get("bed"), c.get("caption_edits"), c.get("caption_adds"),
                     c.get("screams"), c.get("laughs"), c.get("speakers"), c.get("fit_timing")])


def cards(p, lg, st):
    if not lg.get("chapter_cards", True):
        return []
    return [style.card_event(p["start"] + 0.3, min(p["end"], p["start"] + 4.0), p["title"], st)]


def make(ctx, events, parts, log=print, preset="medium"):
    """Render the long video. Returns its path."""
    lg = ctx.cfg.get("long") or {}
    d = folder(ctx)
    work = os.path.join(d, "parts")
    os.makedirs(work, exist_ok=True)
    st = style.wide_look(style.look(ctx.cfg))
    fade = float(lg.get("fade") or 0)
    files = []
    for n, p in enumerate(parts, 1):
        f = os.path.join(work, "part-%s.mp4" % _key(ctx, p, lg))
        files.append(f)
        if os.path.exists(f):
            log("[%d/%d] %s - unchanged" % (n, len(parts), p["title"]))
            continue
        log("[%d/%d] %s  (%s)" % (n, len(parts), p["title"], _cap(p["end"] - p["start"])))
        render.make_short(ctx, p["start"], p["end"], f, events, preset=preset, name=p["title"], log=log,
                          wide=dict(fade=fade, cards=cards(p, lg, st), captions=lg.get("captions", True)))
    listing = os.path.join(work, "join.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("".join("file '%s'\n" % os.path.basename(x) for x in files))
    out = os.path.join(d, safe(lg.get("title") or os.path.basename(ctx.base) + " - long video") + ".mp4")
    part = os.path.splitext(out)[0] + ".part.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "join.txt", "-c", "copy",
                    "-movflags", "+faststart", os.path.abspath(part)], cwd=work, check=True)
    render.put_in_place(part, out)
    with open(os.path.join(d, "chapters.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(chapters(parts)) + "\n")
    for old in os.listdir(work):                 # stretches no longer in this version of the video
        if old.startswith("part-") and os.path.join(work, old) not in files:
            os.remove(os.path.join(work, old))
    return out
