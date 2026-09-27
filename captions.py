"""Caption timing: rebuild the sequence audio, find when each word is spoken,
and compare/realign the captions against it."""
import hashlib
import json
import os
import re
import subprocess
from difflib import SequenceMatcher
from statistics import median

import numpy as np

from prproj import TICKS

RATE = 16000  # Whisper wants 16 kHz mono


# -- 1. timeline audio --------------------------------------------------------
def timeline_audio(seq, log=print):
    """Mix every audio clip into one mono array laid out on the sequence timeline."""
    items = sorted(seq.audio, key=lambda a: a.start)
    if not items:
        raise SystemExit("This sequence has no audio clips.")
    for a in items:
        if not a.speed_ok:
            log("  ! clip at %s has a speed change - its timing is approximated" % fmt(a.start / TICKS))
        if not a.path or not os.path.exists(a.path):
            raise SystemExit("Media offline: %s" % a.path)
    # Merge runs that are contiguous in both timeline and source: one ffmpeg call each.
    runs = []
    for a in items:
        r = runs[-1] if runs else None
        if r and r["path"] == a.path and r["track"] == a.track and r["end"] == a.start \
                and r["src_out"] == a.src_in:
            r["end"], r["src_out"] = a.end, a.src_out
        else:
            runs.append(dict(path=a.path, track=a.track, start=a.start, end=a.end,
                             src_in=a.src_in, src_out=a.src_out))
    total = max(a.end for a in items) / TICKS
    buf = np.zeros(int(total * RATE) + RATE, dtype=np.float32)
    log("  decoding %d audio run(s) (%s of timeline)" % (len(runs), fmt(total)))
    for r in runs:
        dur = (r["end"] - r["start"]) / TICKS
        pcm = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.6f" % (r["src_in"] / TICKS), "-t", "%.6f" % dur,
             "-i", r["path"], "-vn", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
            capture_output=True, check=True).stdout
        x = np.frombuffer(pcm, dtype=np.float32)
        i = int(round(r["start"] / TICKS * RATE))
        n = min(len(x), len(buf) - i)
        buf[i:i + n] += x[:n]
    return buf


# -- 2. words with timestamps ---------------------------------------------------
def transcribe(audio, cache_dir, model="small", log=print):
    """faster-whisper word timestamps, cached by audio content + model."""
    key = hashlib.sha1(audio.tobytes()).hexdigest()[:16] + "-" + model
    cache = os.path.join(cache_dir, "words-%s.json" % key)
    if os.path.exists(cache):
        log("  using cached transcript %s" % os.path.basename(cache))
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    from faster_whisper import WhisperModel
    log("  transcribing with Whisper '%s' on CPU - this is the slow step" % model)
    wm = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    segments, _ = wm.transcribe(audio, language="en", word_timestamps=True, vad_filter=True,
                                condition_on_previous_text=False)
    words, last = [], -60
    for seg in segments:
        for w in seg.words:
            words.append([round(w.start, 3), round(w.end, 3), w.word.strip(), round(w.probability, 3)])
        if seg.end - last >= 60:
            last = seg.end
            log("    ... %s" % fmt(seg.end))
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(words, f)
    return words


# -- 3. match caption text to spoken words -----------------------------------
def norm(word):
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'"))


def align(captions, words, max_shift=8.0):
    """Return per-caption dicts: matched speech start/end (seconds) and match ratio."""
    cap_tok, cap_of, cap_pos = [], [], []
    for c in captions:
        toks = [norm(t) for t in c.text.split() if norm(t)]
        for p, t in enumerate(toks):
            cap_tok.append(t)
            cap_of.append(c.index)
            cap_pos.append((p, len(toks)))
    w_tok = [norm(w[2]) for w in words]
    hits = {c.index: [] for c in captions}   # (word, length of the matching run it came from)
    sm = SequenceMatcher(None, cap_tok, w_tok, autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            c = captions[cap_of[a + k]]
            w = words[b + k]
            if abs(w[0] - c.start_s) <= max_shift:
                hits[c.index].append((w, n, cap_pos[a + k]))
    expected = local_offsets(captions, hits)
    out = []
    for c in captions:
        ntok = sum(1 for t in c.text.split() if norm(t))
        # Only words heard where the neighbours say this caption's speech is.
        # Stops a common word ("I'm", "Oh") matching the same word said elsewhere.
        e = expected[c.index]
        lo, hi = c.start_s + e - WINDOW, c.end_s + e + WINDOW
        inside = [(w, n, pos) for w, n, pos in hits[c.index] if lo <= w[0] <= hi]
        h = [fix_stretched(w) for w, n, pos in inside]
        out.append(dict(
            ratio=(len(h) / ntok) if ntok else 0.0,
            run=max((n for w, n, pos in inside), default=0),
            # an edge can only be judged if the word AT that edge was heard
            first_heard=any(pos[0] == 0 for w, n, pos in inside),
            last_heard=any(pos[0] == pos[1] - 1 for w, n, pos in inside),
            speech_start=min(w[0] for w in h) if h else None,
            speech_end=max(w[1] for w in h) if h else None))
    reject_outliers(captions, out)
    return out


WINDOW = 0.75  # seconds either side of where a caption's words are expected


def local_offsets(captions, hits, strong_run=3, window=15):
    """Expected (speech - caption) offset around each caption, from strong
    anchors only: words matched as part of a 3+ word run, which are very
    unlikely to be coincidences."""
    anchors = []
    for c in captions:
        strong = [w for w, n, _ in hits[c.index] if n >= strong_run]
        if strong:
            anchors.append((c.index, min(w[0] for w in strong) - c.start_s))
    out = {}
    pos = 0
    for c in captions:
        while pos < len(anchors) and anchors[pos][0] < c.index:
            pos += 1
        near = [o for _, o in anchors[max(0, pos - window):pos + window]]
        out[c.index] = median(near) if near else 0.0
    return out


def fix_stretched(w):
    """Whisper often stretches the first word of a phrase back into the pause
    before it ("You" lasting 0.5s). Pull an implausibly long word's start
    forward to a normal speaking length for its size."""
    start, end, text = w[0], w[1], w[2]
    typical = 0.12 + 0.07 * len(norm(text))
    if end - start > 2.0 * typical:
        start = end - typical
    return [start, end] + list(w[2:])


def reject_outliers(captions, matches, window=12, max_dev=0.75, strong_run=3):
    """Drop matches that disagree with their neighbours.

    Short common phrases ("Oh.", "Yeah,") can match the same words said seconds
    away. A real timing error is only believed if the caption's offset agrees
    with nearby captions, or is backed by a run of 3+ consecutive matched words.
    """
    offs = {i: m["speech_start"] - captions[i].start_s
            for i, m in enumerate(matches) if m["speech_start"] is not None and m["ratio"] >= 0.5}
    keys = sorted(offs)
    for pos, i in enumerate(keys):
        near = [offs[j] for j in keys[max(0, pos - window):pos + window + 1] if j != i]
        if not near:
            continue
        if abs(offs[i] - median(near)) > max_dev and matches[i]["run"] < strong_run:
            matches[i].update(ratio=0.0, speech_start=None, speech_end=None, rejected=True)


# -- 4. decide new timing ------------------------------------------------------
def retime(captions, matches, frame, min_ratio=0.5, tail=0.25, min_dur=0.5, close_gap=0.2):
    """Return {index: (start_ticks, end_ticks)} for every caption, plus the offsets used."""
    snap = lambda s: int(round(s * TICKS / frame)) * frame
    good = [i for i, m in enumerate(matches) if m["ratio"] >= min_ratio]
    offsets = {i: matches[i]["speech_start"] - captions[i].start_s for i in good}
    starts = []
    for i, c in enumerate(captions):
        if i in offsets:
            starts.append(matches[i]["speech_start"])
        else:
            # not enough matched words: shift by what its confident neighbours needed
            near = sorted(good, key=lambda j: abs(j - i))[:6]
            off = median(offsets[j] for j in near) if near else 0.0
            starts.append(c.start_s + off)
    new = {}
    ends = []
    for i, c in enumerate(captions):
        if i in offsets:
            end = max(matches[i]["speech_end"] + tail, starts[i] + min_dur)
        else:
            end = starts[i] + (c.end_s - c.start_s)
        ends.append(end)
    for i in range(len(captions)):
        if i + 1 < len(captions):
            nxt = starts[i + 1]
            if ends[i] > nxt or 0 < nxt - ends[i] < close_gap:
                ends[i] = nxt
        s, e = snap(starts[i]), snap(ends[i])
        if i and s < new[i - 1][1]:
            s = new[i - 1][1]
        if e <= s:
            e = s + frame
        new[i] = (max(0, s), e)
    return new, offsets


def fmt(sec):
    sign = "-" if sec < 0 else ""
    sec = abs(sec)
    return "%s%d:%02d:%05.2f" % (sign, sec // 3600, sec % 3600 // 60, sec % 60)
