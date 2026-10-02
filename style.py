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
import sys

import numpy as np

import bleep
import captions as cap
import screams as sc

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(getattr(sys, "_MEIPASS", HERE), "fonts")     # bundled in the installed app

# Caption fonts: family name (what libass looks for) -> file. Bundled ones are free
# (OFL / Apache, licences in fonts/); the Windows ones are used only if this PC has them.
FONT_FILES = {
    "Montserrat Black": "Montserrat-Black.ttf", "Montserrat ExtraBold": "Montserrat-ExtraBold.ttf",
    "Poppins Black": "Poppins-Black.ttf", "Poppins ExtraBold": "Poppins-ExtraBold.ttf",
    "Anton": "Anton-Regular.ttf", "Bebas Neue": "BebasNeue-Regular.ttf", "Archivo Black": "ArchivoBlack-Regular.ttf",
    "Bangers": "Bangers-Regular.ttf", "Luckiest Guy": "LuckiestGuy-Regular.ttf", "Lilita One": "LilitaOne-Regular.ttf",
    "Titan One": "TitanOne-Regular.ttf", "Rubik Mono One": "RubikMonoOne-Regular.ttf",
    "Permanent Marker": "PermanentMarker-Regular.ttf",
}
SYSTEM_FONTS = {"Impact": "impact.ttf", "Arial Black": "ariblk.ttf", "Segoe UI Black": "seguibl.ttf",
                "Comic Sans MS": "comicbd.ttf"}
WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font_path(family):
    if family in FONT_FILES:
        return os.path.join(FONTS, FONT_FILES[family])
    if family in SYSTEM_FONTS and os.path.exists(os.path.join(WINFONTS, SYSTEM_FONTS[family])):
        return os.path.join(WINFONTS, SYSTEM_FONTS[family])
    return None


def font_list():
    """Every font the Look tab can offer on this PC."""
    return [f for f in list(FONT_FILES) + list(SYSTEM_FONTS) if font_path(f)]


def copy_fonts(dst, st=None):
    """Put the bundled fonts (and the look's Windows font, if it uses one) where libass looks."""
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(FONTS):
        if f.endswith(".ttf"):
            shutil.copy2(os.path.join(FONTS, f), dst)
    p = font_path((st or {}).get("font", ""))
    if p and not p.startswith(FONTS):
        shutil.copy2(p, dst)

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


def main_style(st):
    """The caption line's style. With a background box, libass draws an opaque box
    (BorderStyle 3) in the box colour, padded by the outline width."""
    if st.get("box"):
        alpha = "%02X" % int(round((1 - float(st.get("box_opacity", 0.75))) * 255))
        border, outline, shadow = 3, max(8, int(st["size"] * .18)), 0
        out_col = back = ass_color(st.get("box_col", "000000"), alpha)
    else:
        border, outline, shadow = 1, st["outline"], st["shadow"]
        out_col, back = ass_color(st["outline_col"]), ass_color("000000", "80")
    return "Style: Main,%s,%d,%s,%s,%s,%s,0,0,0,0,100,100,%d,0,%d,%d,%d,2,%d,%d,%d,1" % (
        st["font"], st["size"], ass_color(st["text"]), ass_color(st["highlight"]), out_col, back,
        int(st.get("spacing", 0)), border, outline, shadow, st["margin_h"], st["margin_h"], st["margin_v"])


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
        main_style(st),
        "Style: Scream,%s,%d,%s,%s,%s,%s,0,0,0,0,100,100,2,0,1,%d,%d,2,%d,%d,%d,1" % (
            st["font"], st["scream_size"], ass_color(st["scream_col"]), ass_color(st["scream_col"]),
            ass_color(st["outline_col"]), ass_color("000000", "80"),
            st["outline"] + 1, st["shadow"] + 1, 40, 40, st["margin_v"]),
        "Style: Laugh,%s,%d,%s,%s,%s,%s,0,0,0,0,100,100,1,0,1,%d,%d,2,%d,%d,%d,1" % (
            st["font"], int(st["size"] * 1.12), ass_color(st.get("laugh_col", "8AE3FF")),
            ass_color(st.get("laugh_col", "8AE3FF")), ass_color(st["outline_col"]), ass_color("000000", "80"),
            st["outline"], st["shadow"], 40, 40, st["margin_v"]),
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
    if st.get("punct", "keep") != "keep":            # drop punctuation, keep each word's time
        kept = [(cap.strip_punct(w, st["punct"]), t) for w, t in zip(shown, times)]
        kept = [(w, t) for w, t in kept if w]
        shown, times = [w for w, _ in kept], [t for _, t in kept]
    shown = bleep.caption_words(shown, st.get("bleep") or {})     # censor mode, off by default
    if not shown:
        return []
    case = st.get("case", "as_said")
    if loud or case == "upper":
        shown = [w.upper() for w in shown]
    elif case == "lower":
        shown = [w.lower() for w in shown]
    n = int(st.get("words") or 0)                    # words on screen at once (0 = the whole caption)
    if not n or n >= len(shown):
        return line_events(shown, times, start, end, loud, st, highlight)
    ev = []
    for i in range(0, len(shown), n):
        a = start if i == 0 else times[i]
        b = times[i + n] if i + n < len(shown) else end
        if b - a > 0.01:
            ev += line_events(shown[i:i + n], times[i:i + n], a, b, loud, st, highlight)
    return ev


def anim_in(st, scale):
    """Tags that bring a line on screen, ending at `scale` %."""
    kind, p, f = st.get("anim", "pop"), st["pop_ms"], st["fade_in_ms"]
    if kind == "none":
        return "\\fscx%d\\fscy%d" % (scale, scale)
    if kind == "fade":
        return "\\fad(%d,0)\\fscx%d\\fscy%d" % (f * 2, scale, scale)
    if kind == "bounce":
        p = int(p * 1.4)
        return ("\\fad(%d,0)\\fscx70\\fscy70\\t(0,%d,\\fscx%d\\fscy%d)\\t(%d,%d,\\fscx%d\\fscy%d)\\t(%d,%d,\\fscx%d\\fscy%d)"
                % (f, int(p * .45), scale * 1.16, scale * 1.16, int(p * .45), int(p * .75), scale * .95, scale * .95,
                   int(p * .75), p, scale, scale))
    return ("\\fad(%d,0)\\fscx88\\fscy88\\t(0,%d,\\fscx104\\fscy104)\\t(%d,%d,\\fscx%d\\fscy%d)"
            % (f, int(p * .6), int(p * .6), p, scale, scale))


def word_tags(w, on, col, st, scale):
    """One word, lit up (`on`) the way the look's highlight style says."""
    w = esc(w)
    if not on:
        return w
    mode, text = st.get("hl_mode", "color"), ass_color(st["text"])
    if mode == "bigger":
        big = int(scale * 1.18)
        return "{\\1c%s\\fscx%d\\fscy%d}%s{\\1c%s\\fscx%d\\fscy%d}" % (ass_color(col), big, big, w, text, scale, scale)
    if mode == "box":          # a thick outline in the highlight colour reads as a rounded box behind the word
        pad = max(10, int(st["size"] * .16))
        return "{\\3c%s\\bord%d\\shad0\\1c%s}%s{\\3c%s\\bord%d\\shad%d\\1c%s}" % (
            ass_color(col), pad, ass_color(st.get("hl_text", st["text"])), w,
            ass_color(st["outline_col"]), st["outline"], st["shadow"], text)
    return "{\\1c%s}%s{\\1c%s}" % (ass_color(col), w, text)


def line_events(shown, times, start, end, loud, st, highlight=True):
    """One line on screen from start to end, re-drawn at each spoken word to move the highlight."""
    col = st["loud_col"] if loud else st["highlight"]
    mode = st.get("hl_mode", "color") if highlight else "none"
    scale = st["loud_scale"] if loud else 100
    intro = anim_in(st, scale)
    base = "\\fscx%d\\fscy%d" % (scale, scale)
    out = "\\fad(0,%d)" % st["fade_out_ms"]
    if mode == "none":
        steps = [(start, end, None)]
    else:
        steps = [(times[k], times[k + 1] if k + 1 < len(times) else end, k) for k in range(len(times))]
        steps = [s for s in steps if s[1] - s[0] > 0.01] or [(start, end, None)]
        steps[0] = (start, steps[0][1], steps[0][2])
    ev = []
    for n, (a, b, k) in enumerate(steps):
        words = [word_tags(w, k is not None and (i == k or (mode == "fill" and i < k)), col, st, scale)
                 for i, w in enumerate(shown)]
        d = int((a - start) * 1000)
        # a highlight step that starts mid-pop continues the pop instead of snapping
        if n == 0:
            head = intro
        elif st.get("anim", "pop") == "pop" and d < st["pop_ms"]:
            head = pop_from(d, st, loud)
        else:
            head = base
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


def held_events(cues, st):
    """A soft drawn-out sound in the Main style, one more letter per cue, no wobble."""
    ev = []
    for n, (a, b, text) in enumerate(cues):
        tags = ""
        if n == 0:
            tags += "\\fad(%d,0)" % st["fade_in_ms"]
        if n == len(cues) - 1:
            tags += "\\fad(0,%d)" % st["fade_out_ms"]
        ev.append((a, b, "Main", ("{%s}" % tags if tags else "") + esc(text)))
    return ev


def look(cfg):
    """STYLE with the project's own settings (toolkit.json "look") on top."""
    lk = (cfg or {}).get("look", {})
    st = dict(STYLE)
    st.update(size=int(lk.get("size", st["size"])), margin_v=int(lk.get("position", st["margin_v"])),
              text=lk.get("text", st["text"]), highlight=lk.get("highlight_col", st["highlight"]),
              loud_col=lk.get("loud_col", st["loud_col"]), scream_col=lk.get("scream_col", st["scream_col"]),
              laugh_col=lk.get("laugh_col", "8AE3FF"))
    if font_path(lk.get("font", "")):
        st["font"] = lk["font"]
    for key in ("case", "hl_mode", "anim", "box_col", "outline_col", "hl_text"):
        if lk.get(key):
            st[key] = lk[key]
    for key, kind in (("words", int), ("outline", int), ("shadow", int), ("spacing", int), ("box_opacity", float)):
        if lk.get(key) is not None:
            st[key] = kind(lk[key])
    st["box"] = bool(lk.get("box", False))
    st["scream_size"] = int(round(st["size"] * 1.32))
    st["punct"] = lk.get("punct", "keep")
    st["bleep"] = bleep.settings(cfg)
    return st


# Ready-made looks, styled after what's common on Shorts / TikTok / Reels. A preset only
# sets these keys - position, scream/laugh colours, punctuation and censoring stay yours.
PRESET_KEYS = ("font", "size", "case", "words", "text", "highlight", "highlight_col", "hl_mode", "hl_text",
               "outline", "outline_col", "shadow", "box", "box_col", "box_opacity", "anim", "spacing", "loud_lines")
_BASE = dict(font="Montserrat Black", size=76, case="as_said", words=0, text="FFFFFF", highlight=True,
             highlight_col="FFD23C", hl_mode="color", hl_text="FFFFFF", outline=7, outline_col="000000",
             shadow=3, box=False, box_col="000000", box_opacity=0.75, anim="pop", spacing=0, loud_lines=True)
PRESETS = [
    ("Classic", "The toolkit's original: bold white, yellow spoken word, soft pop.", {}),
    ("Bold Pop", "Big capitals, 2 words at a time, the spoken word grows in green. The podcast-clip look.",
     dict(size=96, case="upper", words=2, highlight_col="3CFF6E", hl_mode="bigger", outline=9, anim="bounce")),
    ("One Word", "One huge word at a time, punched in. Fast and hypnotic.",
     dict(font="Anton", size=130, case="upper", words=1, highlight=False, outline=10, anim="bounce", spacing=2)),
    ("Word Box", "3 words, the spoken word sits in a coloured box.",
     dict(font="Poppins Black", size=80, words=3, highlight_col="7B5CFF", hl_mode="box", outline=6, shadow=0)),
    ("Karaoke", "Words fill in yellow as they're said.",
     dict(font="Poppins Black", size=80, words=4, highlight_col="FFE14D", hl_mode="fill", anim="fade")),
    ("TikTok Box", "Black text on a white box, like TikTok's own text.",
     dict(font="Montserrat ExtraBold", size=66, text="111111", highlight=False, box=True, box_col="FFFFFF",
          box_opacity=1.0, anim="fade", outline_col="FFFFFF", shadow=0)),
    ("Dark Box", "White text on a see-through black box. Easy to read over busy gameplay.",
     dict(font="Montserrat ExtraBold", size=70, box=True, box_col="000000", box_opacity=0.6, hl_mode="color", anim="fade")),
    ("Meme", "Classic meme caps: white, heavy black outline, no animation.",
     dict(font="Impact" if font_path("Impact") else "Anton", size=96, case="upper", highlight=False,
          outline=10, shadow=0, anim="none", spacing=1)),
    ("Comic", "Comic-book yellow capitals that bounce.",
     dict(font="Bangers", size=104, case="upper", words=3, text="FFE14D", highlight_col="FFFFFF",
          outline=9, anim="bounce", spacing=3)),
    ("Gamer", "Chunky rounded capitals, cyan spoken word.",
     dict(font="Luckiest Guy", size=88, case="upper", words=3, highlight_col="3CF0FF", outline=9, anim="pop")),
    ("Minimal", "Small, clean, no outline - just a soft shadow and a fade.",
     dict(font="Poppins ExtraBold", size=60, highlight=False, outline=0, shadow=5, anim="fade", loud_lines=False)),
    ("Marker", "Hand-written marker, white with an orange spoken word.",
     dict(font="Permanent Marker", size=84, highlight_col="FF8A3C", outline=6, anim="pop")),
]


def preset_look(name, presets=None):
    """The look keys a preset sets (built-in or one of yours: {name: keys})."""
    for n, _, keys in PRESETS:
        if n == name:
            return dict(_BASE, **keys, preset_name=n)
    if presets and name in presets:
        return dict(_BASE, **{k: v for k, v in presets[name].items() if k in PRESET_KEYS}, preset_name=name)
    return None


def laugh_events(cues, st):
    """Each new syllable gives the laugh a small bounce (106% -> 100%)."""
    ev = []
    for n, (a, b, text) in enumerate(cues):
        tags = "\\fscx106\\fscy106\\t(0,110,\\fscx100\\fscy100)"
        first, last = n == 0, n == len(cues) - 1
        if first or last:
            tags += "\\fad(%d,%d)" % (60 if first else 0, 90 if last else 0)
        ev.append((a, b, "Laugh", "{%s}%s" % (tags, esc(text))))
    return ev


def build(ctx, plan):
    """All caption events for the sequence (timeline seconds), from the loaded project
    (pipeline.load) and its scream plan (screams.plan_screams)."""
    import laughs as lg
    st = look(ctx.cfg)
    lk = ctx.cfg.get("look", {})
    normal = sc.talk_level(ctx.audio, ctx.regions)
    lplan = lg.plan_laughs(ctx.captions, ctx.audio, getattr(ctx, "sounds", None), ctx.regions,
                           ctx.cfg.get("laughs", {}), screams_on=[(p["start"], p["end"]) for p in plan if p["on"]])
    hidden = sc.replaced_captions(ctx.captions, plan) | lg.hidden_by(ctx.captions, lplan)
    events = []
    for p in lplan:
        if p["on"]:
            events += laugh_events(lg.cues_for(ctx.audio, p), st)
    edits = ctx.cfg.get("caption_edits") or {}
    for c, m in zip(ctx.captions, ctx.matches):
        if c.index in hidden:
            continue
        cm = cap.edited(c, m, edits)                  # your fixes from the app
        if cm is None:
            continue
        c, m = cm
        if not c.text:
            continue
        loud = bool(lk.get("loud_lines", True) and normal
                    and sc.loudness(ctx.audio, c.start_s, c.end_s) / normal >= st["loud_ratio"])
        events += caption_events(c, m, c.start_s, c.end_s, loud, st, lk.get("highlight", True))
    on = [p for p in plan if p["on"]]
    for i, p in enumerate(on):
        cues = sc.cues_for(ctx.audio, p["start"], p["end"], p["tpl"], p["bang"])
        if p.get("soft"):                    # a held "Ohhhh": the normal caption look, stretching
            events += held_events(sc.soften(cues), st)
        else:
            events += scream_events(cues, st, seed=i)
    events.sort(key=lambda x: x[0])
    for i in range(len(events) - 1):         # one caption on screen at a time
        a, b = events[i], events[i + 1]
        if a[1] > b[0]:
            events[i] = (a[0], b[0], a[2], a[3])
    return [e for e in events if e[1] - e[0] > 0.005]


def write_ass(path, events, st=STYLE, shift=0.0):
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(header(st))
        for a, b, style, text in events:
            if b - shift <= 0:
                continue
            f.write("Dialogue: 0,%s,%s,%s,,0,0,0,,%s\n" % (ass_time(a - shift), ass_time(b - shift), style, text))


def burn(video_in, ass_path, video_out, preset="medium", crf=18, extra_in=(), vf_before="", st=None):
    """Render the .ass onto a video. Audio is copied untouched."""
    work = os.path.dirname(os.path.abspath(ass_path))
    copy_fonts(os.path.join(work, "fonts"), st)
    vf = (vf_before + "," if vf_before else "") + "ass=%s:fontsdir=fonts" % os.path.basename(ass_path)
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", *extra_in, "-i", os.path.abspath(video_in),
           "-vf", vf, "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-c:a", "copy", os.path.abspath(video_out)]
    subprocess.run(cmd, cwd=work, check=True)
