"""Music mode: Shorts from a music stream, a set or a recorded performance.

Speech rules don't work on music - there are no pauses in talking to cut at, and the loudest
second is not automatically the best one. This listens for three things instead:

    beats      - note and drum attacks. A Short starts ON one and ends just before one.
    sections   - where the music changes (something comes in, drops out, a new part starts).
    silences   - gaps between pieces.

Every second gets a score from how loud and busy it is and whether something just came in;
suggest() builds each Short around a high point, starts it at a section change or a beat,
and - when the music has a steady pulse - makes it a whole number of four-beat bars long.
Music with no pulse (drones, textures, free playing) is cut at section changes and at the
quietest nearby moment instead.

Only numpy: the same 16 kHz timeline audio every other command uses. With the sound-event
model installed (models/panns_sed.onnx) it also hears where somebody is just talking, so the
chat between pieces is not suggested.
"""
import os

import numpy as np

import captions as cap

N_FFT, HOP, N_MELS = 1024, 320, 40
FPS = cap.RATE / HOP             # 50 feature frames a second
SEC_FPS = 2                      # section finding works on half-second steps
KERNEL = 16                      # half-width of the section kernel, in those steps (8 s each side)
BIN = 1.0                        # the timeline's seconds per bin (same as timeline.BIN)
LEAD_IN = 0.3                    # share of a suggestion before its high point
PRE_ROLL = 0.03                  # a Short starts this long before the beat, so the attack is whole
PULSE = 0.3                      # beat_period confidence from which the bars are counted. Measured: songs with
                                 # a beat 0.12-0.66 (9 of 12 over 0.3), beat-less pieces 0.03-0.29, talk 0.08
MUSIC_CLASSES = {"Music": 137, "Singing": 27, "Speech": 0}


# -- 1. what the music is doing --------------------------------------------------------------
def _mel_filters():
    hz2mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)
    mel2hz = lambda m: 700.0 * (10.0 ** (m / 2595.0) - 1.0)
    edges = mel2hz(np.linspace(hz2mel(30.0), hz2mel(cap.RATE / 2), N_MELS + 2))
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / cap.RATE)
    fb = np.zeros((len(freqs), N_MELS), np.float32)
    for m in range(N_MELS):
        lo, mid, hi = edges[m:m + 3]
        fb[:, m] = np.clip(np.minimum((freqs - lo) / (mid - lo), (hi - freqs) / (hi - mid)), 0, None)
    return fb


def features(audio, cache_dir=None, log=print):
    """{onset, db: one value per frame (50 a second); mel: log-mel averaged per half second}.
    Kept as music-<audio>.npz next to the other caches."""
    cache = os.path.join(cache_dir, "music-%s.npz" % cap.audio_key(audio)) if cache_dir else None
    if cache and os.path.exists(cache):
        d = np.load(cache)
        return {k: d[k].astype(np.float32) for k in ("onset", "db", "mel")}
    log("  listening to the music (beats, sections)")
    fb = _mel_filters()
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)
    x = np.pad(audio.astype(np.float32), (N_FFT // 2, N_FFT // 2))
    n = 1 + (len(x) - N_FFT) // HOP
    step = int(60 * FPS)                             # a minute at a time: 2 h of audio stays under 100 MB
    mels, dbs = [], []
    for i in range(0, n, step):
        m = min(step, n - i)
        seg = x[i * HOP:i * HOP + (m - 1) * HOP + N_FFT]
        frames = np.lib.stride_tricks.as_strided(seg, shape=(m, N_FFT), strides=(seg.strides[0] * HOP, seg.strides[0]))
        spec = np.abs(np.fft.rfft(frames * win, axis=1)).astype(np.float32) ** 2
        mels.append(10.0 * np.log10(np.maximum(spec @ fb, 1e-10)))
        dbs.append(10.0 * np.log10(np.maximum((frames ** 2).mean(1), 1e-10)))
    mel = np.concatenate(mels)
    mel = np.maximum(mel, max(float(mel.max()) - 70.0, -80.0))   # 70 dB under the loudest sound is the floor:
                                                     # below it is rounding noise, and its flicker is not a note
    db = np.concatenate(dbs).astype(np.float32)
    onset = np.zeros(n, np.float32)
    onset[1:] = np.maximum(mel[1:] - mel[:-1], 0).mean(1)       # how much new sound arrived in this frame
    per = int(FPS / SEC_FPS)
    k = n // per
    out = dict(onset=onset, db=db, mel=mel[:k * per].reshape(k, per, N_MELS).mean(1).astype(np.float32))
    if cache:
        try:
            np.savez_compressed(cache, **out)
        except OSError:
            pass
    return out


def _peaks(x, min_sep, floor):
    """Indices of local maxima at or above floor (a number or an array), strongest first kept,
    none closer than min_sep to a stronger one."""
    mid = x[1:-1]
    cand = np.flatnonzero((mid > x[:-2]) & (mid >= x[2:]) & (mid >= (floor[1:-1] if np.ndim(floor) else floor))) + 1
    taken = np.zeros(len(x), bool)
    keep = []
    for i in cand[np.argsort(-x[cand])]:
        if not taken[max(0, i - min_sep):i + min_sep + 1].any():
            keep.append(i)
            taken[i] = True
    return np.array(sorted(keep), int)


def _smooth(x, n):
    return np.convolve(x, np.ones(n) / n, mode="same") if n > 1 else x


def beats(feat):
    """(times s, strength 0-1) of the clear attacks - notes, drum hits."""
    on = feat["onset"]
    if not len(on) or on.max() <= 0:
        return np.zeros(0), np.zeros(0)
    top = np.percentile(on, 99.5) or on.max()
    floor = 1.5 * _smooth(on, int(2 * FPS)) + 0.04 * top        # stands out from the two seconds around it
    idx = _peaks(on, int(0.1 * FPS), floor)
    return idx / FPS, np.clip(on[idx] / top, 0, 1)


def sections(feat):
    """(times s, strength 0-1) where the music changes: the sound of the 8 s after differs from
    the 8 s before, and each side is alike within itself."""
    X = feat["mel"]
    n = len(X)
    if n < 4 * KERNEL:
        return np.zeros(0), np.zeros(0)
    X = X - X.mean(1, keepdims=True)                 # the shape of the spectrum, not its level...
    X = np.hstack([X, feat_level(feat)[:n, None]])   # ...plus the level as one more column
    X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    g = np.exp(-0.5 * (np.arange(-KERNEL, KERNEL) + 0.5) ** 2 / (KERNEL / 2.0) ** 2)
    sign = np.sign(np.arange(-KERNEL, KERNEL) + 0.5)
    K = np.outer(g * sign, g * sign)                 # checkerboard: same side +, across the change -
    nov = np.zeros(n)
    for t in range(KERNEL, n - KERNEL):
        w = X[t - KERNEL:t + KERNEL]
        nov[t] = ((w @ w.T) * K).sum()
    nov = np.maximum(nov, 0)
    if nov.max() <= 0:
        return np.zeros(0), np.zeros(0)
    top = np.percentile(nov, 99) or nov.max()
    idx = _peaks(nov, 6 * SEC_FPS, 0.25 * top)
    return idx / SEC_FPS, np.clip(nov[idx] / top, 0, 1)


def feat_level(feat):
    """Loudness (dB) per half second."""
    per = int(FPS / SEC_FPS)
    k = len(feat["db"]) // per
    return feat["db"][:k * per].reshape(k, per).mean(1)


def silences(feat, min_len=1.0):
    """[(start, end)] stretches at least 35 dB under the loud parts: gaps between pieces.
    A second or more - the dry space between two drum hits is not a gap."""
    db = feat["db"]
    if not len(db):
        return []
    quiet = db < max(np.percentile(db, 95) - 35.0, -70.0)
    edges = np.flatnonzero(np.diff(np.concatenate([[0], quiet.view(np.int8), [0]])))
    return [(a / FPS, b / FPS) for a, b in zip(edges[::2], edges[1::2]) if (b - a) / FPS >= min_len]


def beat_period(feat, a, b):
    """(seconds per beat, confidence 0-1) between a and b, from how regularly the attacks repeat.
    Confidence under PULSE means there is no steady pulse to count."""
    on = feat["onset"][int(a * FPS):int(b * FPS)]
    if len(on) < 4 * FPS or on.max() < 0.5:          # under half a dB of new sound per frame: nothing is being struck
        return 0.0, 0.0
    on = on - on.mean()
    full = np.correlate(on, on, mode="full")[len(on) - 1:]
    if full[0] <= 0:
        return 0.0, 0.0
    lo, hi = int(0.3 * FPS), int(1.0 * FPS)          # 60 to 200 beats a minute
    lags = np.arange(lo - 1, hi + 1)
    acf = full[lo - 1:hi + 1] / (full[0] * (1 - lags / len(on)))
    prior = np.exp(-0.5 * (np.log2(lags / FPS / 0.5)) ** 2)     # leans towards 120 a minute, gently
    # a pulse shows as a bump at its own spacing; sound that only swells and fades has none
    bump = np.flatnonzero((acf[1:-1] > acf[:-2]) & (acf[1:-1] >= acf[2:])) + 1
    if not len(bump):
        return 0.0, 0.0
    i = bump[int(np.argmax((acf * prior)[bump]))]
    return lags[i] / FPS, float(max(0.0, acf[i]))


def where_music(seq, cache_dir, audio, log=print):
    """Per second, 1 = fine to suggest, 0 = somebody is just talking (between pieces, to chat).
    None when the sound-event model is not installed - then nothing is ruled out.

    It rules talk OUT rather than asking for music IN, on purpose: measured on real recordings,
    the model calls pop songs "music" at 0.5-0.6 but electroacoustic pieces at 0.02-0.05, while
    plain talking reads "speech" 0.5 / "music" 0.01. Requiring "music" would throw away
    everything that isn't a song."""
    import sounds
    ev = sounds.detect(seq, cache_dir, audio, log=log, classes=MUSIC_CLASSES, tag="musicev",
                       what="for talking between the music")
    if ev is None:
        return None
    per = sounds.FPS
    k = len(ev["Speech"]) // per
    sec = lambda x: _smooth(x[:k * per].reshape(k, per).mean(1).astype(float), 5)
    speech, mus = sec(ev["Speech"]), sec(np.maximum(ev["Music"], ev["Singing"]))
    talk = np.clip((speech - 0.1) / 0.15, 0, 1) * (mus < 0.2)
    return 1.0 - talk


def listen(ctx, log=print):
    """Everything music mode knows about the timeline, worked out once per command."""
    feat = features(ctx.audio, ctx.outdir, log=log)
    bt, bs = beats(feat)
    st, ss = sections(feat)
    return dict(feat=feat, beats=bt, beat_strength=bs, sections=st, section_strength=ss,
                silences=silences(feat), where=where_music(ctx.seq, ctx.outdir, ctx.audio, log=log))


# -- 2. the per-second picture -----------------------------------------------------------------
def _norm(x, lo_pct=10, hi_pct=98):
    lo, hi = np.percentile(x, lo_pct), np.percentile(x, hi_pct)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


def _per_second(x, n, per):
    out = np.zeros(n * per, np.float32)
    out[:min(len(x), n * per)] = x[:n * per]
    return out.reshape(n, per)


def cut_points(m):
    """Where a Short may start or end, for snapping in the app: section changes, the middle of
    each silence, and the strong beats (at most about one a second, so dragging stays easy)."""
    strong = m["beats"][m["beat_strength"] >= 0.35]
    keep, last = [], -9.0
    for t in strong:
        if t - last >= 0.9:
            keep.append(t)
            last = t
    pts = sorted(set(round(float(t), 2) for t in list(m["sections"]) + keep + [(a + b) / 2 for a, b in m["silences"]]))
    return pts


def summary(ctx, m):
    """The same picture timeline.summary() makes for talk - loud / excite / pauses - for music."""
    feat = m["feat"]
    dur = ctx.seq.end_s
    n = int(np.ceil(dur / BIN))
    per = int(FPS * BIN)
    db = _per_second(np.where(feat["db"] > -100, feat["db"], -100), n, per).mean(1)
    loud = _norm(db)
    busy = _norm(_per_second(feat["onset"], n, per).mean(1), 5, 99)
    # something just came in: the 4 s from here are louder than the 4 s before
    k = np.ones(4) / 4
    after = np.convolve(loud, k, mode="full")[3:3 + n]
    before = np.concatenate([[0], np.convolve(loud, k, mode="full")[:n - 1]])
    rise = np.clip((after - before) * 2.5, 0, 1)
    rise[:4] = 0                                       # the very start of the recording is not an entrance
    change = np.zeros(n)
    for t, s in zip(m["sections"], m["section_strength"]):
        i = int(t // BIN)
        change[max(0, i):i + 6] = np.maximum(change[max(0, i):i + 6], s)
    excite = 0.55 * loud + 0.35 * busy + 0.6 * np.maximum(rise, 0.5 * change * (loud > 0.3))
    excite = _smooth(excite, 3)
    where = np.ones(n)
    if m["where"] is not None:
        where[:min(n, len(m["where"]))] = m["where"][:n]
        excite = excite * where                        # talking between pieces is not a moment
    for a, b in m["silences"]:
        excite[int(a // BIN) + 1:int(b // BIN)] = 0
    ex = _norm(excite, 5, 99.5)
    r2 = lambda v: [round(float(x), 2) for x in v]
    return dict(
        kind="music", duration=round(dur, 2), bin=BIN,
        loud=r2(loud), speech=r2(np.zeros(n)), excite=r2(ex), music=r2(where), rise=r2(rise),
        markers=[dict(t=round(x.start_s, 3), dur=round(x.dur_s, 3), name=x.name) for x in ctx.seq.markers],
        pauses=cut_points(m),
        sections=[dict(t=round(float(t), 2), strength=round(float(s), 2)) for t, s in zip(m["sections"], m["section_strength"])],
        screams=[], laughs=[], loud_lines=[],
        video=[dict(start=round(v.start / cap.TICKS, 4), end=round(v.end / cap.TICKS, 4), track=v.track,
                    src=round(v.src_in / cap.TICKS, 4), path=v.path) for v in ctx.seq.video],
    )


# -- 3. Shorts ---------------------------------------------------------------------------------
def _nearest(t, times, window):
    if not len(times):
        return None
    i = int(np.argmin(np.abs(times - t)))
    return float(times[i]) if abs(times[i] - t) <= window else None


def _strongest(t, times, strength, window):
    """The strongest beat within window of t (a downbeat or a big hit rather than a passing note)."""
    near = np.flatnonzero(np.abs(times - t) <= window)
    if not len(near):
        return None
    return float(times[near[np.argmax(strength[near] - 0.3 * np.abs(times[near] - t) / window)]])


def _quietest(feat, t, window):
    a, b = max(0, int((t - window) * FPS)), int((t + window) * FPS)
    db = _smooth(feat["db"][a:b], 5)
    return (a + int(np.argmin(db))) / FPS if len(db) else t


def _after_gap(m, gap_end):
    """The first note after a silence."""
    b = _strongest(gap_end + 0.3, m["beats"], m["beat_strength"], 0.5)
    return max(0.0, (b if b is not None else gap_end) - PRE_ROLL)


def snap_start(m, t, markers=()):
    """(time, how). A marker, then a section change or the end of a silence, then a strong beat,
    then - music with no beats - the quietest moment nearby."""
    mk = _nearest(t, np.array(markers, float), 2.0) if len(markers) else None
    if mk is not None:
        return mk, "marker"
    ends = np.array([b for a, b in m["silences"]], float)
    s = _nearest(t, ends, 4.0)
    if s is not None:
        return _after_gap(m, s), "after a gap"
    s = _nearest(t, m["sections"], 4.0)
    if s is not None:                                  # sections are found to half a second: land on the beat there
        b = _strongest(s, m["beats"], m["beat_strength"], 0.6)
        return max(0.0, (b if b is not None else s) - PRE_ROLL), "section"
    b = _strongest(t, m["beats"], m["beat_strength"], 1.5)
    if b is not None:
        return max(0.0, b - PRE_ROLL), "beat"
    return _quietest(m["feat"], t, 2.0), "quiet moment"


def snap_end(m, start, t, lo, hi, markers=()):
    """(time, how). A marker or a silence if one is close; else a whole number of bars after the
    start when there is a steady pulse; else just before a section change or a strong beat."""
    mk = _nearest(t, np.array(markers, float), 2.0) if len(markers) else None
    if mk is not None and lo <= mk - start <= hi:
        return mk, "marker"
    starts = np.array([a for a, b in m["silences"]], float)
    s = _nearest(t, starts, 4.0)
    if s is not None and lo <= s + 0.25 - start <= hi:
        return s + 0.25, "into a gap"                  # let the last note ring a moment
    period, sure = beat_period(m["feat"], start, t)
    if sure >= PULSE:
        bar = 4 * period
        bars = max(1, int(round((t - start) / bar)))
        while bars > 1 and bars * bar > hi:
            bars -= 1
        want = start + PRE_ROLL + bars * bar           # the downbeat of the bar after the last one kept
        b = _nearest(want, m["beats"], period / 2)
        end = (b if b is not None else want) - PRE_ROLL
        if lo <= end - start <= hi:
            return end, "%d bars" % bars
    s = _nearest(t, m["sections"], 3.0)
    if s is not None and lo <= s - start <= hi:
        b = _strongest(s, m["beats"], m["beat_strength"], 0.6)
        return (b if b is not None else s) - PRE_ROLL, "section"
    b = _strongest(t, m["beats"], m["beat_strength"], 1.5)
    if b is not None and lo <= b - PRE_ROLL - start <= hi:
        return b - PRE_ROLL, "beat"
    q = _quietest(m["feat"], t, 2.0)
    return (q, "quiet moment") if lo <= q - start <= hi else (min(max(t, start + lo), start + hi), None)


def _open(m, start, how):
    """Never open on a gap: start with its first note instead."""
    for a, b in m["silences"]:
        if how != "marker" and a - 2.0 <= start < b:
            return _after_gap(m, b), "after a gap"
    return start, how


def _gap_inside(m, start, end):
    """Where the first gap inside start..end begins, or None."""
    for a, b in m["silences"]:
        if start + 2 < a < end - 0.5:
            return a
    return None


def suggest(summ, m, count=10, length=(20, 45), avoid=(), gap=5.0, floor=0.2):
    """Ranked Short suggestions, same shape as timeline.suggest: [{start, end, score, why, ...}]."""
    ex = np.array(summ["excite"])
    rise = np.array(summ["rise"])
    ok = np.array(summ["music"])                       # 0 where somebody is just talking
    lo_len, hi_len = length
    target = (lo_len + hi_len) / 2
    markers = [x["t"] for x in summ["markers"]]
    dur = summ["duration"]
    taken = [tuple(x) for x in avoid]
    out = []
    for peak in np.argsort(-ex):
        if len(out) >= count or ex[peak] < floor:
            break
        t = (peak + 0.5) * BIN
        if any(a - gap <= t <= b + gap for a, b in taken):
            continue
        start, how_s = snap_start(m, max(0.0, t - LEAD_IN * target), markers)
        start, how_s = _open(m, start, how_s)
        end, how_e = snap_end(m, start, min(dur, start + target), lo_len, hi_len, markers)
        end = min(end, dur)
        cut = _gap_inside(m, start, end)               # never run through a gap between two pieces
        if cut is not None:
            end, how_e = cut + 0.25, "into a gap"
            if end - start < lo_len:                   # too short now: reach back from the gap instead
                start, how_s = _open(m, *snap_start(m, max(0.0, end - target), markers))
                if _gap_inside(m, start, end) is not None:
                    continue
        if end - start < lo_len - 0.5 or any(not (end + gap <= a or start - gap >= b) for a, b in taken):
            continue
        i0, i1 = int(start // BIN), max(int(start // BIN) + 1, int(end // BIN))
        if not start <= t <= end or float(ok[i0:i1].mean()) < 0.7:     # lost its high point, or mostly talking
            continue
        hook = float(ex[i0:i0 + 2].mean())
        score = 0.5 * float(ex[i0:i1].mean()) + 0.3 * float(ex[i0:i1].max()) + 0.2 * hook
        why = []
        if rise[i0:i1].max() >= 0.6:
            why.append("something big comes in")
        n_sec = int(((m["sections"] > start + 2) & (m["sections"] < end - 2)).sum())
        if n_sec:
            why.append("%d change%s" % (n_sec, "s" if n_sec > 1 else ""))
        if hook >= 0.6:
            why.append("strong opening")
        if how_e and how_e.endswith("bars"):
            why.append(how_e)
        if not why:
            why.append("full, busy stretch")
        out.append(dict(start=round(start, 2), end=round(end, 2), peak=round(t, 1),
                        score=int(round(100 * score)), hook=int(round(100 * hook)), why=", ".join(why),
                        snapped="%s / %s" % (how_s or "free", how_e or "free")))
        taken.append((start, end))
    out.sort(key=lambda s: -s["score"])
    return out
