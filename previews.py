"""Look previews: every render gets its own file, the last few stay to compare, old ones go.

Each preview is preview-<when>.mp4 with a preview-<when>.json beside it saying where it
starts and which look it used. A new file name each time also means the app's player
never shows an older render that had the same name.

Clean-up: the newest preview is always kept (you can still watch it until you render
another). Of the rest, only the newest KEEP stay, and none older than MAX_AGE_H hours.
"""
import glob
import json
import os
import time

KEEP = 5                 # previews kept to swap between
MAX_AGE_H = 24           # older previews are deleted (except the newest one)


def new_path(outdir):
    return os.path.join(outdir, "preview-%s.mp4" % time.strftime("%Y%m%d-%H%M%S"))


def describe(cfg):
    """A short summary of the look this preview used, shown on its button."""
    lk = cfg.get("look", {})
    parts = [lk.get("preset_name") or "", lk.get("font") or "", "%s px" % lk.get("size", "")]
    return " · ".join(p for p in parts if p.strip())


def save_info(path, at, seconds, cfg):
    info = dict(at=at, seconds=seconds, when=time.time(), look=describe(cfg))
    with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(info, f)


def listing(outdir):
    """Newest first: [{file, at, seconds, when, look}]."""
    out = []
    for p in glob.glob(os.path.join(outdir, "preview-*.mp4")):
        if p.endswith(".part.mp4"):
            continue
        info = {}
        side = os.path.splitext(p)[0] + ".json"
        if os.path.exists(side):
            try:
                with open(side, encoding="utf-8") as f:
                    info = json.load(f)
            except (OSError, ValueError):
                info = {}
        info.setdefault("when", os.path.getmtime(p))
        info["file"] = os.path.basename(p)
        out.append(info)
    return sorted(out, key=lambda i: -i["when"])


def prune(outdir, keep=KEEP, max_age_h=MAX_AGE_H):
    """Delete previews past the limits. Returns how many went."""
    items = listing(outdir)
    gone = 0
    now = time.time()
    for n, it in enumerate(items):
        if n == 0:
            continue                                  # the newest always stays
        if n >= keep or now - it["when"] > max_age_h * 3600:
            for p in (it["file"], os.path.splitext(it["file"])[0] + ".json"):
                try:
                    os.remove(os.path.join(outdir, p))
                except OSError:
                    pass                              # in use by the player: next time
            gone += 1
    return gone
