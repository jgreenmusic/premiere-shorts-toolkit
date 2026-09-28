"""The whole-video picture for the app's timeline, and predicted Shorts.

summary(): per-second loudness / talking / word rate / excitement, plus markers,
pauses (for snapping), screams, laughs and loud lines - everything the timeline draws.

suggest(): the best Shorts for this video. Every second gets an excitement score
(loudness, talk, screams, laughs, shouted lines). The biggest moments are "payoffs";
each suggestion is built around one - a short setup before it, the reaction after -
then its start and end are snapped to a pause in the talking (or a marker, if one is
close), so a Short never starts or stops mid-word. Shorts viewers swipe in the first
second or two, so a quiet opening is trimmed to a later pause and a strong opening
(the "hook") scores higher.
"""
import numpy as np

import captions as cap

BIN = 1.0                 # seconds per timeline bin


def _norm(x, lo_pct=10, hi_pct=98):
    lo, hi = np.percentile(x, lo_pct), np.percentile(x, hi_pct)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


def summary(ctx, screams, laughs, loud_lines):
    dur = ctx.seq.end_s
    n = int(np.ceil(dur / BIN))
    a = ctx.audio
    per = int(cap.RATE * BIN)
    padded = np.zeros(n * per, np.float32)
    padded[:min(len(a), n * per)] = a[:n * per]
    rms = np.sqrt((padded.reshape(n, per) ** 2).mean(1))
    loud = _norm(20 * np.log10(rms + 1e-6))

    speech = np.zeros(n)
    for s, e in ctx.regions:
        for i in range(int(s // BIN), min(n, int(e // BIN) + 1)):
            lo, hi = max(s, i * BIN), min(e, (i + 1) * BIN)
            if hi > lo:
                speech[i] += (hi - lo) / BIN
    speech = np.clip(speech, 0, 1)

    words = np.zeros(n)
    for w in ctx.words:
        i = int(w[0] // BIN)
        if 0 <= i < n:
            words[i] += 1
    wrate = _norm(np.convolve(words, np.ones(3) / 3, mode="same"), 5, 99)

    events = np.zeros(n)
    def bump(t0, t1, weight):
        for i in range(max(0, int(t0 // BIN) - 1), min(n, int(t1 // BIN) + 2)):
            events[i] += weight
    for p in screams:
        if p["on"]:
            bump(p["start"], p["end"], 1.2)
    for p in laughs:
        bump(p["start"], p["end"], 1.0 if p["on"] else 0.4 * min(1.0, p["peak"] / 0.25))
    for s, e in loud_lines:
        bump(s, e, 0.35)

    excite = 0.8 * loud + 0.4 * speech + 0.3 * wrate + np.minimum(events, 2.5)
    excite = np.convolve(excite, np.ones(3) / 3, mode="same")
    ex = _norm(excite, 5, 99.5)

    pauses = []
    regs = sorted(ctx.regions)
    for (s0, e0), (s1, e1) in zip(regs, regs[1:]):
        if s1 - e0 >= 0.35:
            pauses.append(round((e0 + s1) / 2, 2))

    r2 = lambda v: [round(float(x), 2) for x in v]
    return dict(
        duration=round(dur, 2), bin=BIN,
        loud=r2(loud), speech=r2(speech), excite=r2(ex),
        markers=[dict(t=round(m.start_s, 3), dur=round(m.dur_s, 3), name=m.name) for m in ctx.seq.markers],
        pauses=pauses,
        screams=[dict(start=round(p["start"], 2), end=round(p["end"], 2), on=p["on"]) for p in screams],
        laughs=[dict(start=round(p["start"], 2), end=round(p["end"], 2), on=p["on"]) for p in laughs],
        loud_lines=[[round(s, 2), round(e, 2)] for s, e in loud_lines],
        video=[dict(start=round(v.start / cap.TICKS, 4), end=round(v.end / cap.TICKS, 4), track=v.track,
                    src=round(v.src_in / cap.TICKS, 4), path=v.path) for v in ctx.seq.video],
    )


def _snap(t, pauses, markers, window, prefer_marker=2.0):
    """Nearest marker within prefer_marker s, else the nearest pause within window s."""
    m = [x for x in markers if abs(x - t) <= prefer_marker]
    if m:
        return min(m, key=lambda x: abs(x - t)), "marker"
    p = [x for x in pauses if abs(x - t) <= window]
    if p:
        return min(p, key=lambda x: abs(x - t)), "pause"
    return t, None


HOOK = 2.0               # seconds of opening that decide whether a viewer swipes away
SETUP = 0.45             # share of a suggestion before its payoff (the rest is the reaction)


def _hook(ex, start, bin_):
    i = int(start // bin_)
    return float(ex[i:i + max(1, int(round(HOOK / bin_)))].mean()) if i < len(ex) else 0.0


def suggest(summ, count=10, length=(15, 30), avoid=(), gap=5.0, floor=0.2):
    """Ranked Short suggestions: [{start, end, score (0-100), why, peak}]."""
    ex = np.array(summ["excite"])
    n = len(ex)
    lo_len, hi_len = length
    target = (lo_len + hi_len) / 2
    markers = [m["t"] for m in summ["markers"]]
    pauses = summ["pauses"]
    taken = [tuple(x) for x in avoid]
    out = []
    order = np.argsort(-ex)
    for peak in order:
        if len(out) >= count or ex[peak] < floor:
            break
        t = (peak + 0.5) * summ["bin"]
        if any(a - gap <= t <= b + gap for a, b in taken):
            continue
        # payoff a little under halfway in: short setup before, reaction after
        start, how_s = _snap(max(0.0, t - SETUP * target), pauses, markers, 4.0)
        end, how_e = _snap(min(summ["duration"], t + (1 - SETUP) * target), pauses, markers, 3.0)
        # dead opening: move the start to a later pause, but keep the payoff and the minimum length
        for p in pauses:
            if _hook(ex, start, summ["bin"]) >= 0.35:
                break
            if start < p <= min(start + 6.0, t - 2.0, end - lo_len):
                start, how_s = p, "pause"
        if end - start < lo_len:
            end, how_e = _snap(min(summ["duration"], start + lo_len + 1), pauses, markers, 3.0)
        if end - start > hi_len:
            end = start + hi_len
            how_e = None
        if end - start < min(lo_len, 8) or any(not (end + gap <= a or start - gap >= b) for a, b in taken):
            continue
        i0, i1 = int(start // summ["bin"]), max(int(start // summ["bin"]) + 1, int(end // summ["bin"]))
        hook = _hook(ex, start, summ["bin"])
        score = 0.5 * float(ex[i0:i1].mean()) + 0.3 * float(ex[i0:i1].max()) + 0.2 * hook
        inside = lambda lst: sum(1 for x in lst if x.get("on", True) and start <= x["start"] < end)
        sc, lg = inside(summ["screams"]), inside(summ["laughs"])
        ll = sum(1 for s, e in summ["loud_lines"] if start <= s < end)
        why = []
        if sc:
            why.append("%d scream%s" % (sc, "s" if sc > 1 else ""))
        if lg:
            why.append("%d laugh%s" % (lg, "s" if lg > 1 else ""))
        if ll >= 3:
            why.append("lots of shouting")
        if hook >= 0.6:
            why.append("strong opening")
        if not why:
            why.append("loud, busy moment")
        out.append(dict(start=round(start, 2), end=round(end, 2), peak=round(t, 1),
                        score=int(round(100 * score)), hook=int(round(100 * hook)), why=", ".join(why),
                        snapped="%s / %s" % (how_s or "free", how_e or "free")))
        taken.append((start, end))
    out.sort(key=lambda s: -s["score"])
    return out
