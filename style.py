"""Styled, subtly animated captions as an .ass subtitle file, burned in with ffmpeg.

Premiere's caption tracks can't animate, so the look lives here instead:
  - each caption pops in (fade + slight scale overshoot) and fades out
  - the word being spoken is highlighted (Whisper word times; estimated when unheard)
  - loud lines are a little bigger and warmer
  - screams grow letter by letter (screams.py), bigger, with a slight wobble
Everything is tunable in STYLE below.
"""
import os
import random
import shutil
import subprocess

import numpy as np

import captions as cap
import screams as sc

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

STYLE = dict(
    font="Montserrat Black",
    size=76,                 # px on a 1080x1920 frame
    outline=7, shadow=3,
    margin_v=560,            # distance from the bottom: clears the Shorts UI buttons
    margin_h=90,
    text="FFFFFF",           # RGB
    outline_col="000000",
    highlight="FFD23C",      # spoken word
    loud_col="FF8A3C",       # spoken word on a loud line
    loud_ratio=1.8,          # louder than normal talk by this -> "loud line"
    loud_scale=112,          # % size of loud lines
    scream_size=100,
    scream_col="FF5A3C",
    pop_ms=170,              # pop-in duration
    fade_in_ms=70, fade_out_ms=60,
)


def ass_color(rgb, alpha="00"):
    r, g, b = rgb[0:2], rgb[2:4], rgb[4:6]
    return "&H%s%s%s%s" % (alpha, b, g, r)


def ass_time(sec):
    sec = max(0.0, sec)
    cs = int(round(sec * 100))
    return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def header(st):
    return "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Main,%s,%d,%s,%s,%s,%s,0,0,0,0,100,100,0,0,1,%d,%d,2,%d,%d,%d,1" % (
            st["font"], st["size"], ass_color(st["text"]), ass_color(st["highlight"]),
            ass_color(st["outline_col"]), ass_color("000000", "80"),
            st["outline"], st["shadow"], st["margin_h"], st["margin_h"], st["margin_v"]),
        "Style: Scream,%s,%d,%s,%s,%s,%s,0,0,0,0,100,100,2,0,1,%d,%d,2,%d,%d,%d,1" % (
            st["font"], st["scream_size"], ass_color(st["scream_col"]), ass_color(st["scream_col"]),
            ass_color(st["outline_col"]), ass_color("000000", "80"),
            st["outline"] + 1, st["shadow"] + 1, 40, 40, st["margin_v"]),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]) + "\n"


def esc(text):
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def word_times(c, m, start, end):
    """Start time of each display word: heard words use Whisper's time, the rest are
    spread between them by length."""
    shown = c.text.split()
    pos_of, p = [], 0
    for w in shown:                          # same token numbering as captions.align
        if cap.norm(w):
            pos_of.append(p)
            p += 1
        else:
            pos_of.append(None)
    heard = {pos: s for pos, s, e in (m.get("words") or [])}
    t = [heard.get(pos) if pos is not None else None for pos in pos_of]
    t = [None if x is None or not (start - 0.05 <= x < end) else x for x in t]
    if t and t[0] is None:
        t[0] = start
    # fill gaps by character length between known anchors
    i = 0
    while i < len(t):
        if t[i] is None:
            j = i
            while j < len(t) and t[j] is None:
                j += 1
            a = t[i - 1]
            b = t[j] if j < len(t) else end - 0.15 * (end - start)
            weights = [len(shown[k]) + 1 for k in range(i - 1, j)]
            total = sum(weights)
            acc = 0
            for k in range(i, j):
                acc += weights[k - i]
                t[k] = a + (b - a) * acc / total
            i = j
        i += 1
    for k in range(1, len(t)):               # never go backwards
        t[k] = max(t[k], t[k - 1])
    return shown, t


def caption_events(c, m, start, end, loud, st, highlight=True):
    shown, times = word_times(c, m, start, end)
    if not shown:
        return []
    col = st["loud_col"] if loud else st["highlight"]
    base = ""
    if loud:
        base += "\\fscx%d\\fscy%d" % (st["loud_scale"], st["loud_scale"])
        shown = [w.upper() for w in shown]
    pop = ("\\fad(%d,0)\\fscx88\\fscy88\\t(0,%d,\\fscx104\\fscy104)\\t(%d,%d,\\fscx%d\\fscy%d)"
           % (st["fade_in_ms"], int(st["pop_ms"] * .6), int(st["pop_ms"] * .6), st["pop_ms"],
              st["loud_scale"] if loud else 100, st["loud_scale"] if loud else 100))
    out = "\\fad(0,%d)" % st["fade_out_ms"]
    if not highlight:
        steps = [(start, end, None)]
    else:
        steps = [(times[k], times[k + 1] if k + 1 < len(times) else end, k) for k in range(len(times))]
        steps = [s for s in steps if s[1] - s[0] > 0.01] or [(start, end, None)]
        steps[0] = (start, steps[0][1], steps[0][2])
    ev = []
    for n, (a, b, k) in enumerate(steps):
        words = []
        for i, w in enumerate(shown):
            w = esc(w)
            words.append("{\\1c%s}%s{\\1c%s}" % (ass_color(col), w, ass_color(st["text"])) if i == k else w)
        d = int((a - start) * 1000)
        # a highlight step that starts mid-pop continues the pop instead of snapping
        head = pop if n == 0 else (pop_from(d, st, loud) if d < st["pop_ms"] else base)
        tags = head + (out if n == len(steps) - 1 else "")
        ev.append((a, b, "Main", "{%s}%s" % (tags, " ".join(words))))
    return ev


def pop_from(d, st, loud):
    """Pop-in tags for a step that starts d ms into the pop animation."""
    end = st["loud_scale"] if loud else 100
    peak_t = int(st["pop_ms"] * .6)
    if d < peak_t:
        now = 88 + (104 - 88) * d / peak_t
        tags = "\\fscx%d\\fscy%d\\t(0,%d,\\fscx104\\fscy104)\\t(%d,%d,\\fscx%d\\fscy%d)" % (
            now, now, peak_t - d, peak_t - d, st["pop_ms"] - d, end, end)
    else:
        now = 104 + (end - 104) * (d - peak_t) / (st["pop_ms"] - peak_t)
        tags = "\\fscx%d\\fscy%d\\t(0,%d,\\fscx%d\\fscy%d)" % (now, now, st["pop_ms"] - d, end, end)
    if d < st["fade_in_ms"]:
        tags += "\\fad(%d,0)" % (st["fade_in_ms"] - d)
    return tags


def scream_events(cues, st, seed):
    rnd = random.Random(seed)
    ev = []
    for n, (a, b, text) in enumerate(cues):
        grow = 100 + int(12 * n / max(1, len(cues) - 1))
        tags = "\\frz%.1f\\fscx%d\\fscy%d" % (rnd.uniform(-2.0, 2.0), grow, grow)
        if n == 0:
            tags += "\\fad(50,0)"
        if n == len(cues) - 1:
            tags += "\\t(0,120,\\fscx%d\\fscy%d)\\fad(0,80)" % (grow + 6, grow + 6)
        ev.append((a, b, "Scream", "{%s}%s" % (tags, esc(text))))
    return ev


def build(seq, matches, words, regions, audio, st=STYLE, highlight=True, scream_loud=sc.LOUD_RATIO):
    """All events for the sequence, timeline seconds."""
    normal = sc.talk_level(audio, regions)
    found = sc.find_screams(seq, regions, words, audio, loud_ratio=scream_loud)
    replaced = {j for f in found for j in f[4]}
    events = []
    for c, m in zip(seq.captions, matches):
        if not c.text or c.index in replaced:
            continue
        loud = normal and sc.loudness(audio, c.start_s, c.end_s) / normal >= st["loud_ratio"]
        events += caption_events(c, m, c.start_s, c.end_s, loud, st, highlight)
    for i, (s, e, tpl, bang, idx, ratio) in enumerate(found):
        events += scream_events(sc.cues_for(audio, s, e, tpl, bang), st, seed=i)
    events.sort(key=lambda x: x[0])
    for i in range(len(events) - 1):         # one caption on screen at a time
        a, b = events[i], events[i + 1]
        if a[1] > b[0]:
            events[i] = (a[0], b[0], a[2], a[3])
    return [e for e in events if e[1] - e[0] > 0.005], len(found)


def write_ass(path, events, st=STYLE, shift=0.0):
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(header(st))
        for a, b, style, text in events:
            if b - shift <= 0:
                continue
            f.write("Dialogue: 0,%s,%s,%s,,0,0,0,,%s\n" % (ass_time(a - shift), ass_time(b - shift), style, text))


def burn(video_in, ass_path, video_out, preset="medium", crf=18, extra_in=(), vf_before=""):
    """Render the .ass onto a video. Audio is copied untouched."""
    work = os.path.dirname(os.path.abspath(ass_path))
    fonts = os.path.join(work, "fonts")
    os.makedirs(fonts, exist_ok=True)
    for f in os.listdir(FONTS):
        if f.endswith(".ttf"):
            shutil.copy2(os.path.join(FONTS, f), fonts)
    vf = (vf_before + "," if vf_before else "") + "ass=%s:fontsdir=fonts" % os.path.basename(ass_path)
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", *extra_in, "-i", os.path.abspath(video_in),
           "-vf", vf, "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-c:a", "copy", os.path.abspath(video_out)]
    subprocess.run(cmd, cwd=work, check=True)
