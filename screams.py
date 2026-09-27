"""Animated scream captions: "A" -> "AA" -> ... -> "AAAAAHHHH", growing with the voice.

Finds drawn-out interjection captions (AAAH, OHHH, NOOO, WHOAAA ...), measures how
long the voice really lasts and how loud it is, and writes an .srt where each cue
adds one letter. Letters arrive in step with loudness: louder = faster.
Import the .srt into Premiere as its own caption track.
"""
import numpy as np

import captions as cap
from prproj import TICKS

# Each sound is a list of (letter, share). share=0 means "exactly once, not stretched";
# stretched letters split the extra length by their share.
TEMPLATES = [
    (r"a+h*",          [("A", .6), ("H", .4)]),
    (r"a+w+",          [("A", .6), ("W", .4)]),
    (r"o+h+|o+o+h*",   [("O", .6), ("H", .4)]),
    (r"n+o+",          [("N", 0), ("O", 1)]),
    (r"w+h*o+a+h*|w+o+a+h*", [("W", 0), ("H", 0), ("O", .5), ("A", .5)]),
    (r"y+e+a+h+",      [("Y", 0), ("E", 0), ("A", .5), ("H", .5)]),
]

LETTERS_PER_SEC = 7      # final length grows with scream length...
MIN_LETTERS, MAX_LETTERS = 5, 28
MIN_SCREAM = 0.7         # seconds of voice before a sound counts as drawn out
MAX_SCREAM = 6.0
PAD = 0.15               # final spelling stays up this long after the voice stops
HOP = 0.02               # loudness resolution, seconds


def template_for(text):
    import re
    words = [cap.norm(w) for w in text.split() if cap.norm(w)]
    if len(words) != 1:
        return None
    for pattern, tpl in TEMPLATES:
        if re.fullmatch(pattern, words[0]):
            return tpl
    return None


def spell(tpl, n):
    """The full spelling with about n letters, as a list in reveal order.
    Fixed letters appear once; stretched ones share the rest by their weight."""
    fixed = sum(1 for _, share in tpl if share == 0)
    shares = [share for _, share in tpl if share > 0]
    extra = max(len(shares), n - fixed)
    counts, left = [], extra
    for i, share in enumerate(shares):
        c = left if i == len(shares) - 1 else round(extra * share / sum(shares))
        counts.append(max(1, c))
        left -= c
    out, it = [], iter(counts)
    for letter, share in tpl:
        out += [letter] * (1 if share == 0 else next(it))
    return out


LOUD_RATIO = 1.6        # a scream is this much louder than the recording's normal talking


def loudness(audio, a, b):
    seg = audio[int(a * cap.RATE):int(b * cap.RATE)]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def talk_level(audio, regions):
    """Median loudness of voiced audio - 'normal talking' for this recording."""
    levels = [loudness(audio, r[0], r[1]) for r in regions if r[1] - r[0] > 0.3]
    return float(np.median(levels)) if levels else 0.0


def find_screams(captions, regions, words, audio, loud_ratio=LOUD_RATIO, max_gap=0.25):
    """[(start_s, end_s, template, bang, [caption indexes], loudness_ratio)].

    The scream is the voice from the caption's start until (a) the voice stops or
    (b) anyone says another word - so a calm "Yeah." followed by more talking is
    not stretched into a scream. It must also be loud (loud_ratio x normal talk).
    """
    import bisect
    starts = [r[0] for r in regions]
    word_starts = [w[0] for w in words]
    normal = talk_level(audio, regions)

    def voice_end(t):
        """End of the continuous voice that is sounding at (or just after) t."""
        i = bisect.bisect_right(starts, t + 0.3) - 1
        if i < 0 or regions[i][1] < t - 0.1:
            return None
        end = regions[i][1]
        k = i + 1
        while k < len(regions) and regions[k][0] - end < max_gap:
            end = regions[k][1]
            k += 1
        return end

    found = []
    for c in captions:
        tpl = template_for(c.text)
        if not tpl:
            continue
        bang = "!" in c.text
        # "AH!" (0.08 s) straight into "AH!" is one scream split by Premiere: merge
        if found and found[-1][2] == tpl and c.start_s - found[-1][5] < 0.3:
            s, e, t, b, idx, _ = found[-1]
            found[-1] = (s, e, t, b or bang, idx + [c.index], c.end_s)
            continue
        found.append((c.start_s, None, tpl, bang, [c.index], c.end_s))

    screams = []
    for s, _, tpl, bang, idx, _ in found:
        e = voice_end(s)
        if e is None:
            continue
        # the first word after the scream begins that is NOT the scream itself
        i = bisect.bisect_right(word_starts, s + 0.15)
        while i < len(words) and word_starts[i] < e:
            if template_for(words[i][2]) != tpl:
                e = word_starts[i]
                break
            i += 1
        e = min(e, s + MAX_SCREAM)
        if e - s < MIN_SCREAM:
            continue
        ratio = loudness(audio, s, e) / normal if normal else 0.0
        if ratio < loud_ratio:
            continue
        screams.append((s, e, tpl, bang, idx, ratio))
    return screams


def cues_for(audio, start, end, tpl, bang):
    """(start_s, end_s, text) cues: one more letter each, paced by loudness."""
    n = max(MIN_LETTERS, min(MAX_LETTERS, round((end - start) * LETTERS_PER_SEC)))
    letters = spell(tpl, n)
    a, b = int(start * cap.RATE), int(end * cap.RATE)
    hop = int(HOP * cap.RATE)
    seg = audio[a:b]
    frames = max(1, len(seg) // hop)
    rms = np.sqrt(np.mean(seg[:frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-6
    progress = np.cumsum(rms) / np.sum(rms)            # 0..1, climbs faster when loud
    times = start + (np.arange(frames) + 1) * HOP
    cues = []
    shown = 0
    t_prev = start
    for k in range(1, len(letters) + 1):
        # the moment enough loudness has passed to earn k letters
        i = int(np.searchsorted(progress, (k - 1) / len(letters)))
        t = start if k == 1 else float(times[min(i, frames - 1)])
        if k > 1 and t - t_prev < 1 / 30:
            continue                                   # faster than a frame: skip a step
        if shown:
            cues[-1][1] = t
        cues.append([t, None, "".join(letters[:k])])
        shown, t_prev = k, t
    if cues[-1][2] != "".join(letters):
        cues.append([t_prev + 1 / 30, None, "".join(letters)])
        cues[-2][1] = cues[-1][0]
    cues[-1][1] = end + PAD
    if bang:
        cues[-1][2] += "!"
    return cues


def srt_time(sec):
    ms = int(round(sec * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_srt(path, all_cues):
    with open(path, "w", encoding="utf-8") as f:
        for n, (s, e, text) in enumerate(all_cues, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (n, srt_time(s), srt_time(e), text))


# -- the full plan: detected + suggested + your own ------------------------------
LETTER_CHOICES = {"AH": "aah", "OH": "ohh", "NO": "noo", "WHOA": "whoa", "YEAH": "yeah", "AW": "aww"}
BURST_MIN = 0.8          # wordless voice must last this long to be suggested
BURST_PEAK = 0.7         # ...and peak at least this loud vs normal talk


def template_from_letters(letters):
    return template_for(LETTER_CHOICES.get((letters or "AH").upper(), "aah"))


def peak_level(audio, a, b, hop=0.05):
    x = audio[int(a * cap.RATE):int(b * cap.RATE)]
    h = int(hop * cap.RATE)
    n = len(x) // h
    return float(np.percentile(np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)), 90)) if n else 0.0


def find_bursts(captions, regions, words, audio):
    """Wordless voice with no caption over it: screams Premiere never transcribed
    (also laughs and groans - so these are only SUGGESTED, off until you switch them on)."""
    import bisect
    spans = [(c.start_s, c.end_s) for c in captions if c.text]
    word_starts = [w[0] for w in words]
    base = np.median([peak_level(audio, r[0], r[1]) for r in regions if r[1] - r[0] > 0.3] or [0]) or 1.0
    out = []
    for a, b in regions:
        if b - a < BURST_MIN:
            continue
        covered = sum(max(0.0, min(b, e) - max(a, s)) for s, e in spans) / (b - a)
        i, j = bisect.bisect_left(word_starts, a), bisect.bisect_left(word_starts, b)
        real_words = [w for w in words[i:j] if not template_for(w[2])]
        if covered > 0.3 or len(real_words) > 1:
            continue
        peak = peak_level(audio, a, b) / base
        if peak >= BURST_PEAK:
            out.append((a, min(b, a + MAX_SCREAM), peak))
    return out


def plan_screams(captions, regions, words, audio, cfg, sound_events=None):
    """Every scream candidate, each with on/off, as dicts. cfg = the project's "screams" settings."""
    def near(t, lst):
        return any(abs(t - x) < 0.3 for x in lst)
    plan = []
    for s, e, tpl, bang, idx, ratio in find_screams(captions, regions, words, audio, loud_ratio=0.0):
        auto = ratio >= cfg.get("loud", LOUD_RATIO)
        on = (auto and not near(s, cfg.get("off", []))) or (not auto and near(s, cfg.get("on", [])))
        plan.append(dict(start=s, end=e, tpl=tpl, bang=bang, replaces=idx, loud=ratio,
                         source="caption" if auto else "quiet caption", on=on,
                         was=", ".join(captions[j].text for j in idx if j < len(captions))))
    taken = [(p["start"], p["end"]) for p in plan]
    import sounds
    for s, e, peak in find_bursts(captions, regions, words, audio):
        if any(a - 0.3 < s < b for a, b in taken):
            continue
        if sounds.laugh_at(sound_events, s, e) >= 0.12:
            continue                      # the sound model hears laughing: it's a laugh, not a scream
        letters = cfg.get("letters", {}).get("%.2f" % s, "AH")
        plan.append(dict(start=s, end=e, tpl=template_from_letters(letters), bang=False, replaces=[],
                         loud=peak, source="no caption", letters=letters, on=near(s, cfg.get("on", [])), was=""))
    for m in cfg.get("add", []):
        plan.append(dict(start=float(m["start"]), end=float(m["end"]), tpl=template_from_letters(m.get("letters")),
                         bang=True, replaces=[], loud=0.0, source="added", letters=m.get("letters", "AH"),
                         on=True, was=""))
    plan.sort(key=lambda p: p["start"])
    return plan


def replaced_captions(captions, plan):
    """Captions hidden by the screams that are on: the ones they replace, plus any
    caption that starts while a scream is on screen (it would flash for a frame)."""
    hide = set()
    for p in plan:
        if not p["on"]:
            continue
        hide.update(p["replaces"])
        for c in captions:
            if p["start"] - 0.05 <= c.start_s < p["end"]:
                hide.add(c.index)
    return hide
