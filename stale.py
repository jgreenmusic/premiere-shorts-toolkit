"""Is a rendered Short still what the project says it should be?

Every render writes down what it was made from, in <project>_captions\\renders.json: the
Short's range, the timeline and captions inside it, your caption fixes there, the scream and
laugh choices there, and the look. Compare that with the project as it is now and you know
which Shorts changed since they were rendered, and why - so only those are rendered again.

A Short is known by its name (that is also its file name). A renamed Short is a new file.
"""
import hashlib
import json
import os
import time

from prproj import TICKS

# the parts of a Short's fingerprint, and how a change in each is described
PARTS = [("trim", "start or end moved"),
         ("captions", "captions changed"),
         ("reactions", "screams or laughs changed"),
         ("look", "look or layout changed"),
         ("sound", "sound effects or music changed"),
         ("timeline", "the timeline changed here")]
WHY = dict(PARTS)
PAD = 5.0             # a caption fix this close outside the Short can still show inside it (fitted timing)


def _h(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parts(cfg, short, seq=None):
    """{part: fingerprint} of everything a render of this Short depends on.
    seq: the read sequence (app.project / pipeline.load) - without it "timeline" is left out."""
    a, b = float(short["start"]), float(short["end"])
    near = lambda t: t is not None and a - PAD <= t <= b + PAD
    over = lambda x: _num(x.get("end")) is not None and _num(x.get("start")) is not None and float(x["end"]) > a and float(x["start"]) < b

    edits = {k: v for k, v in sorted((cfg.get("caption_edits") or {}).items())
             if v and (near(_num(k)) or near(_num(v.get("start"))) or near(_num(v.get("end"))))}
    adds = [x for x in cfg.get("caption_adds") or [] if over(x)]
    sc, lg = cfg.get("screams") or {}, cfg.get("laughs") or {}
    pick = lambda d, key: sorted(t for t in d.get(key) or [] if near(_num(t)))
    keyed = lambda d, key: {k: v for k, v in sorted((d.get(key) or {}).items()) if near(_num(k))}
    out = dict(
        trim=_h([round(a, 3), round(b, 3)]),
        captions=_h([edits, adds, bool(cfg.get("fit_timing", True))]),
        reactions=_h([sc.get("loud"), pick(sc, "on"), pick(sc, "off"), [x for x in sc.get("add") or [] if over(x)], keyed(sc, "letters"),
                      pick(lg, "on"), pick(lg, "off"), [x for x in lg.get("add") or [] if over(x)], keyed(lg, "style")]),
        look=_h([cfg.get("look"), cfg.get("layout"), cfg.get("bleep"), cfg.get("kind"), cfg.get("music")]
                + ([cfg.get("speakers")] if (cfg.get("speakers") or {}).get("on") else [])))
    sf, bd = cfg.get("sfx") or {}, cfg.get("bed") or {}
    out["sound"] = _h([{k: v for k, v in sf.items() if k not in ("add", "off")},
                       [x for x in sf.get("add") or [] if near(_num(x.get("t")))],
                       [k for k in sf.get("off") or [] if near(_num(k.rpartition("@")[2]))],
                       {k: v for k, v in bd.items() if k != "skip"}, short.get("name") in (bd.get("skip") or [])])
    if seq is not None:
        ta, tb = a * TICKS, b * TICKS
        items = sorted((it.track, it.start, it.end, it.src_in, os.path.normcase(it.path or ""))
                       for it in list(seq.video) + list(seq.audio) if it.end > ta and it.start < tb)
        pa, pb = (a - PAD) * TICKS, (b + PAD) * TICKS
        caps = [(c.start, c.end, c.text) for c in seq.captions if c.end > pa and c.start < pb]
        out["timeline"] = _h([seq.name, items, caps])
    return out


def path_for(outdir):
    return os.path.join(outdir, "renders.json")


def load(outdir):
    try:
        with open(path_for(outdir), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def record(outdir, name, fingerprint):
    """Called right after a Short is rendered."""
    d = load(outdir)
    d[name] = dict(parts=fingerprint, when=time.time())
    tmp = path_for(outdir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, path_for(outdir))


def status(cfg, short, video, seq=None, records=None):
    """Where one Short's render stands:
        rendered  the video file exists
        known     the toolkit wrote down what it was made from (renders before 0.29.0 did not)
        changed   [part ids] that differ now - empty means the video is up to date
        why       the same, in words"""
    if not os.path.exists(video):
        return dict(rendered=False, known=False, changed=[], why=[], when=None)
    rec = (records or {}).get(short["name"])
    when = os.path.getmtime(video)
    if not rec or not rec.get("parts"):
        return dict(rendered=True, known=False, changed=[], why=[], when=when)
    now = parts(cfg, short, seq)
    changed = [k for k, _ in PARTS if k in now and k in rec["parts"] and now[k] != rec["parts"][k]]
    return dict(rendered=True, known=True, changed=changed, why=[WHY[k] for k in changed], when=when)
