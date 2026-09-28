"""Per-project settings: <project>_captions/toolkit.json.

Everything the app lets you change lives here, so each project keeps its own look,
its list of Shorts and your scream decisions. Missing keys fall back to DEFAULTS.
"""
import copy
import json
import os

DEFAULTS = {
    "sequence": None,             # which sequence to use (None = the one with captions / the first)
    "look": {
        "size": 76,               # caption text size, px on 1080x1920
        "position": 560,          # distance from the bottom, px (clears the Shorts buttons)
        "highlight": True,        # colour the word being spoken
        "text": "FFFFFF",
        "highlight_col": "FFD23C",
        "loud_col": "FF8A3C",
        "scream_col": "FF5A3C",
        "laugh_col": "8AE3FF",
        "loud_lines": True,       # shouted lines bigger + capitals
        "punct": "keep",          # punctuation on screen: keep / soft (no . , ; :) / all (no ? ! either)
    },
    "layout": {
        "blur_trim": 0.25,        # 0 = whole gameplay visible with tall blur bands above/below;
                                  # 1 = gameplay fills the screen (sides cropped).
                                  # 0.25 = blur bands a quarter smaller than "whole gameplay"
    },
    "screams": {
        "loud": 1.6,              # how much louder than normal talk counts as a scream
        "on": [],                 # starts (s) of suggested screams you switched ON
        "off": [],                # starts (s) of detected screams you switched OFF
        "add": [],                # [{"start": s, "end": s, "letters": "AH"}] added by hand
        "letters": {},            # {"start": "OH"} letter choice for a suggestion
    },
    "laughs": {
        "on": [], "off": [],      # starts (s) of laughs you switched on / off
        "add": [],                # [{"start": s, "end": s, "style": "ha"}]
        "style": {},              # {"start": "heh"} spelling choice: heh, huh, hehe, ha, HA
    },
    "shorts": [],                 # [{"name": "...", "start": s, "end": s}]
    "markers": [],                # step 1: suggested range markers placed by the toolkit
                                  # [{"name", "start", "end", "score", "why"}]
    "dismissed": [],              # [[start, end]] suggestions you removed - never suggested again
    "post": {                     # step 7 - posting through Post Studio
        "subject": "",            # what it is, named exactly (e.g. the game) - posts only name what's here
        "notes": "",              # context the AI can trust (who's in it, channel, schedule...)
        "platforms": ["youtube_shorts", "tiktok", "instagram_reels", "facebook"],
        "settings": {},           # {platform: {upload setting: value}} e.g. made for kids, TikTok privacy
        "auto": False,            # after a render: write posts + schedule into the posting plan
    },
    "caption_edits": {},          # {"<start s, 2 decimals>": {"text": "..."} or {"hide": true}} - fixes
                                  # made in the app; null = back to the original
}


def path_for(outdir):
    return os.path.join(outdir, "toolkit.json")


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(outdir):
    try:
        with open(path_for(outdir), encoding="utf-8") as f:
            return _merge(DEFAULTS, json.load(f))
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)


def save(outdir, cfg):
    os.makedirs(outdir, exist_ok=True)
    tmp = path_for(outdir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path_for(outdir))


def update(outdir, patch):
    """Deep-merge a partial change (lists are replaced whole) and save."""
    cfg = _merge(load(outdir), patch)
    save(outdir, cfg)
    return cfg
