"""Laugh captions: "heh heh", "hahaha", "HAHAHA" - one syllable per laugh burst.

Where: the sound-event model's laughter score (sounds.py).
How many syllables: the laugh's own rhythm - laughs pulse 4-8 times a second, so we
count the loudness peaks inside it.
Which spelling: by kind and loudness - a quiet snicker/chuckle is "heh heh", a giggle
"hehe", a laugh "hahaha", a big or belly laugh "HAHAHA". You can change any of them.

Laughs never cover someone talking by default: a confident laugh is only switched on
where there's room between captions. Laughs under speech are suggested (off).
"""
import numpy as np

import captions as cap
import sounds

ON_SCORE = 0.12          # a frame is "laughing" above this (smoothed probability)
CONFIDENT = 0.25         # peak score for a laugh to be on by default
SUGGEST = 0.15           # peak score to be suggested at all
MIN_LAUGH = 0.4          # seconds
MERGE_GAP = 0.3
MIN_ROOM = 0.5           # free space between captions needed to show a laugh by default
MAX_SYLLABLES = 10
PAD = 0.2

STYLES = {               # syllable, joined with a space?
    "heh": ("heh", True), "huh": ("huh", True), "hehe": ("he", False),
    "ha": ("ha", False), "HA": ("HA", False),
}


def regions(ev):
    score, stack = sounds.laugh_score(ev)
    hot = score >= ON_SCORE
    out, i, n = [], 0, len(score)
    while i < n:
        if not hot[i]:
            i += 1
            continue
        j = i
        while j < n and hot[j]:
            j += 1
        a, b = i / sounds.FPS, j / sounds.FPS
        if out and a - out[-1][1] < MERGE_GAP:
            out[-1][1] = b
        else:
            out.append([a, b])
        i = j
    res = []
    for a, b in out:
        if b - a < MIN_LAUGH:
            continue
        f0, f1 = int(a * sounds.FPS), int(b * sounds.FPS)
        peak = float(score[f0:f1].max())
        kind = sounds.LAUGH[int(np.argmax(stack[f0:f1].mean(0)))]
        res.append(dict(start=a, end=b, peak=peak, kind=kind))
    return res


def bursts(audio, a, b, hop=0.02):
    """Times of the laugh's pulses (loudness peaks at least 0.11 s apart)."""
    x = audio[int(a * cap.RATE):int(b * cap.RATE)]
    h = int(hop * cap.RATE)
    n = len(x) // h
    if n < 5:
        return [a]
    env = np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1))
    env = np.convolve(env, np.ones(3) / 3, mode="same")
    floor, top = np.percentile(env, 30), env.max()
    peaks = []
    for i in range(1, n - 1):
        if env[i] >= env[i - 1] and env[i] > env[i + 1] and env[i] > floor + 0.35 * (top - floor):
            if not peaks or (i - peaks[-1]) * hop >= 0.11:
                peaks.append(i)
            elif env[i] > env[peaks[-1]]:
                peaks[-1] = i
    return [a + p * hop for p in peaks] or [a]


def default_style(kind, loud):
    if kind == "Belly laugh" or loud >= 2.0:
        return "HA"
    if kind == "Giggle":
        return "hehe"
    if kind in ("Snicker", "Chuckle, chortle") or loud < 0.8:
        return "heh"
    return "ha"


def spell(style, n):
    syl, spaced = STYLES.get(style, STYLES["ha"])
    parts = [syl] * max(1, n)
    return (" " if spaced else "").join(parts)


def free_space(a, b, spans):
    """Largest stretch of [a, b) with no caption on screen."""
    edges = [(a, b)]
    for s, e in spans:
        nxt = []
        for x, y in edges:
            if e <= x or s >= y:
                nxt.append((x, y))
                continue
            if s > x:
                nxt.append((x, s))
            if e < y:
                nxt.append((e, y))
        edges = nxt
    return max(edges, key=lambda r: r[1] - r[0], default=(a, a))


def plan_laughs(captions, audio, ev, regions_voice, cfg, screams_on=()):
    """Every laugh candidate with on/off, spelling and the window it would show in."""
    if ev is None:
        return []
    import screams as sc
    normal = sc.talk_level(audio, regions_voice) or 1.0
    spans = [(c.start_s, c.end_s) for c in captions if c.text]
    def near(t, lst):
        return any(abs(t - x) < 0.3 for x in lst)
    plan = []
    for r in regions(ev):
        if r["peak"] < SUGGEST:
            continue
        if any(s - 0.2 < r["start"] < e for s, e in screams_on):
            continue
        a, b = r["start"], r["end"]
        fa, fb = free_space(a, b, spans)
        roomy = fb - fa >= MIN_ROOM
        loud = sc.loudness(audio, a, b) / normal
        auto = r["peak"] >= CONFIDENT and roomy
        on = (auto and not near(a, cfg.get("off", []))) or (not auto and near(a, cfg.get("on", [])))
        style = cfg.get("style", {}).get("%.2f" % a) or default_style(r["kind"], loud)
        show = (fa, fb) if roomy else (a, b)       # switched on under speech: full window
        plan.append(dict(start=a, end=b, show=show, peak=r["peak"], kind=r["kind"], loud=loud,
                         style=style, on=on, source="detected" if auto else ("under speech" if not roomy else "unsure")))
    for m in cfg.get("add", []):
        a, b = float(m["start"]), float(m["end"])
        plan.append(dict(start=a, end=b, show=(a, b), peak=0.0, kind="added", loud=0.0,
                         style=m.get("style", "ha"), on=True, source="added"))
    plan.sort(key=lambda p: p["start"])
    return plan


def cues_for(audio, p):
    """Growing cues: one more syllable at each laugh burst."""
    a, b = p["show"]
    beats = [t for t in bursts(audio, p["start"], p["end"]) if a - 0.05 <= t < b] or [a]
    # one syllable per pulse, but never faster than ~5 a second (reads as noise)
    n = min(MAX_SYLLABLES, max(2, len(beats)), max(2, int(round((b - a) * 5))))
    if len(beats) < n:                               # too few clear pulses: spread evenly
        beats = list(np.linspace(a, max(a, b - 0.15), n))
    beats = beats[:n]
    beats[0] = a
    cues = []
    for k in range(n):
        s = beats[k]
        e = beats[k + 1] if k + 1 < n else b + PAD
        if e - s > 0.001:
            cues.append([s, e, spell(p["style"], k + 1)])
    return cues


def hidden_by(captions, plan):
    """Captions hidden because a laugh switched on under speech covers them."""
    hide = set()
    for p in plan:
        if p["on"] and p["source"] in ("under speech", "added"):
            a, b = p["show"]
            for c in captions:
                if a - 0.05 <= c.start_s < b:
                    hide.add(c.index)
    return hide
