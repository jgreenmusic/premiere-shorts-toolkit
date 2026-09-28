"""Censor mode (OFF unless switched on per project): curse words become comic-book
symbols in the captions ("$#!%") and a TV beep in the sound - the early-2000s
reality-TV / Robot Chicken joke.

toolkit.json "bleep": {"on": false, "level": "strong", "look": "grawlix", "sound": "beep", "extra": ""}
  level  strong = f/s/b/c-words and friends; all = also ass, damn, hell, dick, piss...
  look   grawlix = "#$@&%!"; stars = "f**k"; none = leave the caption text alone
  sound  beep = 1 kHz tone over the word; mute = silence; none = leave the sound alone
  extra  your own words to bleep too, comma separated (names, running jokes)

The beep uses Whisper's own time for each spoken word, so it lands on the word itself
even when the caption line was typed by hand.
"""
import re

import captions as cap

STRONG = [r"f+u+c+k\w*", r"motherf+u+c+k\w*", r"\w*sh+i+t+\w*", r"b+i+t+c+h\w*", r"c+u+n+t\w*",
          r"bastards?", r"wh+o+r+e+s?", r"sluts?", r"dickheads?", r"cocks?(?:suck\w*)?", r"pricks?",
          r"wank\w*", r"twats?", r"goddamn\w*", r"god-damn\w*"]
MILD = [r"ass(?:es|hole\w*|hat\w*|wipe\w*)?", r"dumbass\w*", r"badass\w*", r"jackass\w*", r"damn\w*", r"dammit",
        r"hell", r"dicks?", r"piss\w*", r"crap\w*", r"bloody", r"bollocks", r"tits?", r"boobs?", r"douche\w*"]
NOT = {"shitake", "shiitake", "hello", "shell", "cocktail", "cockpit", "peacock", "hancock", "scunthorpe",
       "assassin", "assist", "assume", "class", "pass", "passes", "mass", "bass", "grass", "glass", "brass"}

GRAWLIX = "#$@&%!*"
DEFAULTS = {"on": False, "level": "strong", "look": "grawlix", "sound": "beep", "extra": ""}


def settings(cfg):
    b = dict(DEFAULTS)
    b.update((cfg or {}).get("bleep") or {})
    return b


def matcher(b):
    pats = STRONG + (MILD if b.get("level") == "all" else [])
    pats += [re.escape(w.strip().lower()) for w in (b.get("extra") or "").split(",") if w.strip()]
    rx = re.compile(r"^(?:%s)$" % "|".join(pats))
    return lambda word: (lambda w: bool(w) and w not in NOT and bool(rx.match(w)))(cap.norm(word).replace("'", ""))


def disguise(word, look):
    """The shown word, censored: keeps any punctuation around it ("fuck?!" -> "#$@&?!")."""
    m = re.match(r"^(\W*)(.*?)(\W*)$", word)
    pre, core, post = m.groups() if m else ("", word, "")
    if look == "stars":
        mid = core[1:-1] if len(core) > 2 else core[1:]
        core = core[0] + "*" * len(mid) + (core[-1] if len(core) > 2 else "")
    else:
        n = max(3, min(len(core), 6))
        start = sum(map(ord, core.lower())) % len(GRAWLIX)          # same word -> same symbols
        core = "".join(GRAWLIX[(start + i) % len(GRAWLIX)] for i in range(n))
    return pre + core + post


def caption_words(shown, b):
    """Caption words with curses disguised (no change when bleeping is off or look = none)."""
    if not b.get("on") or b.get("look") == "none":
        return shown
    bad = matcher(b)
    return [disguise(w, b.get("look")) if bad(w) else w for w in shown]


def spans(words, b, a, bb, pad=0.04):
    """[(start, end)] of spoken curses between a and bb, relative to a, merged."""
    if not b.get("on") or b.get("sound") == "none":
        return []
    bad = matcher(b)
    out = []
    for w in words or []:
        s, e, text = w[0], w[1], w[2]
        if e > a and s < bb and bad(text):
            s, e = max(0.0, s - pad - a), min(bb - a, e + pad - a)
            if out and s <= out[-1][1] + 0.05:
                out[-1] = (out[-1][0], max(out[-1][1], e))
            else:
                out.append((s, e))
    return out


def audio_filter(src, dst, sp, sound, dur):
    """ffmpeg graph lines: [src] -> [dst] with the spans beeped (or muted)."""
    if not sp:
        return ["%sanull%s" % (src, dst)]
    on = "+".join("between(t,%.3f,%.3f)" % (s, e) for s, e in sp)
    lines = ["%svolume=0:enable='%s'[bl_dry]" % (src, on)]
    if sound == "mute":
        return lines + ["[bl_dry]anull%s" % dst]
    return lines + [
        "sine=frequency=1000:sample_rate=48000:duration=%.3f,aformat=channel_layouts=stereo,"
        "volume='if(%s,0.32,0)':eval=frame[bl_tone]" % (dur, on),
        "[bl_dry]aformat=channel_layouts=stereo[bl_dry2]",
        "[bl_dry2][bl_tone]amix=inputs=2:normalize=0:duration=first%s" % dst]
