"""Sound effects and music under a Short (OFF unless switched on per project; soundlib.py has the sounds).

toolkit.json "sfx": {"on", "volume", "spacing", "rules": [...], "add": [...], "off": [...]}
  a rule   {"id", "on", "when", "sounds": [ids], "chance" %, "gap" s, "max" per Short (0 = any),
            "volume", "secs", "words"}
  add      [{"t": timeline s, "sound": id, "volume"}]: placed by hand
  off      ["<rule id>@<time>"]: one rule hit you switched off
toolkit.json "bed": {"on", "tracks": [ids], "volume", "duck", "fade_in", "fade_out", "vary", "skip": [Short names]}
bleep sound = "effect": each censored word gets a sound from bleep "effects" (bleep.py).

Same project, same rules, same result: chance and "which sound" come from a hash of the rule and the
time, never a dice roll, so a render matches what the app listed and a re-render doesn't change.

What a rule looks at is the project's "moments" (screams, laughs, shouted lines, words, voice), saved in
<project>_captions\\sound-moments.json so the app can list hits without loading the audio.
"""
import hashlib
import json
import os
import wave

import numpy as np

import bleep
import config
import soundlib

SR = soundlib.SR
# what can set off a rule; the page offers these (reactions: only where screams and laughs exist)
WHEN = {"start": "When a Short starts", "end": "When a Short ends", "scream": "On a scream", "laugh": "On a laugh",
        "loud": "On a shouted line", "word": "When someone says...", "pause": "On an awkward pause", "every": "Every so often"}
NEEDS_MOMENTS = ("scream", "laugh", "loud", "word", "pause")
RULE = dict(on=True, when="scream", sounds=[], chance=100, gap=4.0, max=0, volume=1.0, secs=3.0, words="")


def active(cfg):
    """Effects and music are for talking / gaming projects; a music stream's sound stays as it is."""
    return config.reactions_on(cfg)


def wanted(cfg):
    """Is there any point working out moments and mixing for this project?"""
    if not active(cfg):
        return False
    s, b, bl = cfg.get("sfx") or {}, cfg.get("bed") or {}, bleep.settings(cfg)
    return bool(s.get("on") or (b.get("on") and b.get("tracks")) or (bl.get("on") and bl.get("sound") == "effect"))


# ---------- moments ----------

def moments(ctx, events):
    """Everything a rule can react to, in timeline seconds."""
    import premiere_export
    import screams as sc
    import style
    st = style.look(ctx.cfg)
    clips = premiere_export.caption_clips(events, 0, 10 ** 7, with_style=True)
    normal = sc.talk_level(ctx.audio, ctx.regions) if getattr(ctx, "regions", None) else 0
    loud = [round(s, 3) for s, e, _, sty in clips if sty == "Main" and normal
            and sc.loudness(ctx.audio, s, e) / normal >= st["loud_ratio"]]
    return dict(scream=[round(x[0], 3) for x in clips if x[3] == "Scream"],
                laugh=[round(x[0], 3) for x in clips if x[3] == "Laugh"], loud=loud,
                words=[[w[0], w[1], w[2]] for w in getattr(ctx, "words", None) or []],
                voice=list(getattr(ctx, "regions", None) or []))


def moments_path(outdir):
    return os.path.join(outdir, "sound-moments.json")


def save_moments(outdir, m):
    tmp = moments_path(outdir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f)
    os.replace(tmp, moments_path(outdir))


def load_moments(outdir):
    try:
        with open(moments_path(outdir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------- which sounds go where ----------

def _hash(*parts):
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8], 16)


def pick(sounds, *seed):
    return sounds[_hash(*seed) % len(sounds)] if sounds else None


def said(words, phrases, a, b):
    """Start times of each phrase (comma separated) in the spoken words between a and b."""
    from captions import norm
    wanted_ = [[norm(w) for w in p.split()] for p in (phrases or "").split(",") if p.strip()]
    wanted_ = [p for p in wanted_ if all(p)]
    inside = [w for w in words or [] if a <= w[0] < b]
    heard = [norm(w[2]) for w in inside]
    out = []
    for i in range(len(heard)):
        if any(heard[i:i + len(p)] == p for p in wanted_):
            out.append(inside[i][0])
    return out


def pauses(voice, a, b, secs):
    """Start of each stretch of at least secs with nobody talking between a and b."""
    out, at = [], a
    for s, e in sorted(voice or []):
        if e <= a:
            continue
        if s >= b:
            break
        if s - at >= secs:
            out.append(at)
        at = max(at, e)
    if b - at >= secs:
        out.append(at)
    return out


def candidates(rule, m, a, b, length=0.0):
    """Times this rule could fire inside a..b, before chance, gap and max."""
    when, secs = rule.get("when"), max(0.5, float(rule.get("secs") or 3))
    m = m or {}
    if when == "start":
        return [a]
    if when == "end":
        return [max(a, b - length)]
    if when in ("scream", "laugh", "loud"):
        return [t for t in m.get(when) or [] if a <= t < b]
    if when == "word":
        return said(m.get("words"), rule.get("words"), a, b)
    if when == "pause":
        return [t + 0.2 for t in pauses(m.get("voice"), a, b, secs)]
    if when == "every":
        return [float(t) for t in np.arange(a + secs, b - 0.5, secs)]
    return []


def rule_hits(rule, m, a, b, index):
    """[(time, sound id)] after the rule's own limits."""
    rid = rule.get("id") or index
    sounds = [s for s in rule.get("sounds") or [] if soundlib.path_of(s)]
    if not sounds:
        return []
    first = pick(sounds, rid, "end")
    length = soundlib.duration(soundlib.path_of(first)) if rule.get("when") == "end" else 0.0
    chance, gap, most = float(rule.get("chance", 100)), float(rule.get("gap") or 0), int(rule.get("max") or 0)
    out, last = [], None
    for t in sorted(candidates(rule, m, a, b, length)):
        if last is not None and t - last < gap:
            continue
        if _hash(rid, "%.2f" % t) % 100 >= chance:
            continue
        if most and len(out) >= most:
            break
        out.append((t, first if rule.get("when") == "end" else pick(sounds, rid, "%.2f" % t)))
        last = t
    return out


def censor_hits(cfg, words, a, b):
    """The sounds over censored words, when censor mode's sound is "effect"."""
    bl = bleep.settings(cfg)
    if not bl.get("on") or bl.get("sound") != "effect":
        return []
    sounds = [s for s in bl.get("effects") or [] if soundlib.path_of(s)]
    out = []
    for s, e in bleep.spans(words, bl, a, b):
        cut = e - s if bl.get("fit") == "word" else None
        out.append(dict(t=a + s, sound=pick(sounds, "censor", "%.2f" % (a + s)), volume=float(bl.get("volume", 0.5)),
                        why="Censored word", key="censor@%.2f" % (a + s), on=True, cut=cut, censor=True))
    return [h for h in out if h["sound"]]


def plan(cfg, m, a, b, wide=False):
    """Every sound for a..b, sorted: [{t, sound, volume, why, key, on, cut, hand/censor}].
    Hits you switched off stay in the list (on False) so the app can switch them back.
    wide: a chapter of the long video, where "a Short starts / ends" means nothing."""
    hits = censor_hits(cfg, (m or {}).get("words"), a, b)
    if not active(cfg):
        return hits
    s = cfg.get("sfx") or {}
    if not s.get("on"):
        return hits
    master = float(s.get("volume", 0.5))
    off = set(s.get("off") or [])
    mine = []
    for n, h in enumerate(s.get("add") or []):
        if a <= float(h["t"]) < b and soundlib.path_of(h.get("sound")):
            mine.append(dict(t=float(h["t"]), sound=h["sound"], volume=master * float(h.get("volume", 1)), why="Placed by you",
                             key="add:%d" % n, on=True, hand=True))
    spacing = float(s.get("spacing") or 0)
    taken = [h["t"] for h in mine]
    ruled = []
    for i, r in enumerate(s.get("rules") or []):
        if not r.get("on", True) or (wide and r.get("when") in ("start", "end")):
            continue
        for t, snd in rule_hits(r, m, a, b, i):
            key = "%s@%.2f" % (r.get("id") or i, t)
            on = key not in off
            if on and any(abs(t - x) < spacing for x in taken):
                continue                             # never two effects on top of each other
            if on:
                taken.append(t)
            ruled.append(dict(t=t, sound=snd, volume=master * float(r.get("volume", 1)), why=WHEN.get(r.get("when"), "Rule"),
                              key=key, on=on))
    return sorted(hits + mine + ruled, key=lambda h: h["t"])


# ---------- the sound itself ----------

def read(path, start=0, frames=None):
    """float32 [n, 2] from one of the library's wav files."""
    with wave.open(path, "rb") as w:
        w.setpos(min(start, w.getnframes()))
        raw = w.readframes(w.getnframes() if frames is None else frames)
        ch = w.getnchannels()
    x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    x = x.reshape(-1, ch)
    return np.repeat(x, 2, axis=1) if ch == 1 else x[:, :2]


def write(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def clip_audio(h):
    """One hit's samples: its level applied, cut to the word if asked, without a click at the cut."""
    x = read(soundlib.path_of(h["sound"])) * float(h.get("volume", 1))
    if h.get("cut"):
        n = max(1, int(h["cut"] * SR))
        x = x[:n].copy()
        tail = min(len(x), int(0.015 * SR))
        x[-tail:] *= np.linspace(1, 0, tail)[:, None]
    return x


def bed_on(cfg, name):
    b = cfg.get("bed") or {}
    return bool(active(cfg) and b.get("on") and b.get("tracks") and name not in (b.get("skip") or []))


def bed_track(cfg, name):
    tracks = [t for t in (cfg.get("bed") or {}).get("tracks") or [] if soundlib.path_of(t)]
    return pick(tracks, "bed", name)


def _looped(path, start, frames):
    """frames of a track from start, going round to the top (short crossfade) if it runs out."""
    with wave.open(path, "rb") as w:
        total = w.getnframes()
    start = start % max(1, total)
    x = read(path, start, frames)
    fade = int(0.03 * SR)
    while len(x) < frames:
        more = read(path, 0, frames - len(x) + fade)
        n = min(fade, len(x), len(more))
        ramp = np.linspace(0, 1, n)[:, None]
        x[-n:] = x[-n:] * (1 - ramp) + more[:n] * ramp
        x = np.concatenate([x, more[n:]])
    return x[:frames]


def gain_curve(n, voice, a, level, duck, fade_in, fade_out):
    """Per-sample level of the music: lower while someone talks (eased, not stepped), with fades."""
    hz = 100
    steps = max(2, int(n / SR * hz) + 2)
    g = np.ones(steps)
    for s, e in voice or []:
        i, j = int((s - a - 0.08) * hz), int((e - a + 0.15) * hz)
        if j > 0 and i < steps:
            g[max(0, i):max(0, j)] = duck
    width = int(0.2 * hz)
    edge = np.r_[np.full(width, g[0]), g, np.full(width, g[-1])]
    g = np.convolve(edge, np.ones(width) / width, "same")[width:-width]
    out = np.interp(np.arange(n), np.arange(steps) * SR / hz, g) * level
    t = np.arange(n) / SR
    d = n / SR
    if fade_in > 0:
        out *= np.minimum(1, t / fade_in)
    if fade_out > 0:
        out *= np.minimum(1, (d - t) / fade_out)
    return out


def bed_audio(cfg, m, a, b, name):
    """The Short's music, levelled, ducked and faded, as float32 [n, 2]; None if it has none."""
    if not bed_on(cfg, name):
        return None
    path = soundlib.path_of(bed_track(cfg, name))
    if not path:
        return None
    bd = cfg.get("bed") or {}
    n = int(round((b - a) * SR))
    with wave.open(path, "rb") as w:
        total = w.getnframes()
    start = _hash("start", name) % max(1, total - n) if bd.get("vary", True) and total > n else 0
    x = _looped(path, start, n)
    duck = float(bd.get("duck", 0.45)) if bd.get("duck") is not None else 1.0
    g = gain_curve(n, (m or {}).get("voice"), a, float(bd.get("volume", 0.15)), duck,
                   float(bd.get("fade_in", 0.4)), float(bd.get("fade_out", 1.0)))
    return x * g[:, None].astype(np.float32)


def mix(hits, bed, n):
    """Every live hit and the music on one stereo line of n samples; None if there is nothing."""
    live = [h for h in hits if h.get("on", True)]
    if not live and bed is None:
        return None
    x = np.zeros((n, 2), np.float32)
    if bed is not None:
        x[:len(bed)] += bed[:n]
    for h in live:
        y = clip_audio(h)
        i = int(round(h["t0"] * SR))
        if 0 <= i < n:
            y = y[:n - i]
            x[i:i + len(y)] += y
    return x


def ensure_moments(ctx, events):
    """The project's moments, worked out once per run and saved for the app."""
    m = getattr(ctx, "moments", None)
    if m is None:
        m = ctx.moments = moments(ctx, events)
        save_moments(ctx.outdir, m)
    return m


def bed_for(cfg, m, a, b, name, wide=False):
    """bed_audio, or None for a chapter of the long video unless music is on there too."""
    if wide and not (cfg.get("long") or {}).get("music"):
        return None
    return bed_audio(cfg, m, a, b, name)


def layer(ctx, events, a, b, name, path, wide=False):
    """The Short's added sound as one wav at path, for render.make_short. Returns path, or None."""
    if not wanted(ctx.cfg):
        return None
    m = ensure_moments(ctx, events)
    hits = [dict(h, t0=h["t"] - a) for h in plan(ctx.cfg, m, a, b, wide)]
    x = mix(hits, bed_for(ctx.cfg, m, a, b, name or "preview", wide), int(round((b - a) * SR)))
    if x is None:
        return None
    write(path, x)
    return path
