"""Sound events (laughs, giggles, chuckles, ...) from an AudioSet classifier.

PANNs Cnn14 (sound-event detection version) labels every 10 ms of the timeline with
527 AudioSet classes. We keep only the ones the toolkit uses, cached per audio.
On this footage it hears laughter well; it rates gamer yelling as ~0 "Screaming",
so screams are still found the old way - this only takes laughs OUT of the scream
suggestions.

Optional: without torch + panns_inference installed, everything else still works.
"""
import hashlib
import os

import numpy as np

import captions as cap

RATE = 32000                     # the model's sample rate
FPS = 100                        # frames per second it outputs
CLASSES = ["Laughter", "Giggle", "Snicker", "Belly laugh", "Chuckle, chortle",
           "Screaming", "Yell", "Shout"]
LAUGH = CLASSES[:5]
MODEL = os.path.join(os.path.expanduser("~"), "panns_data", "Cnn14_DecisionLevelMax.pth")


def available():
    try:
        import panns_inference  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(MODEL)


def detect(seq, cache_dir, audio16, log=print):
    """{class name: np.array of per-frame probability} for CLASSES, or None if unavailable."""
    key = hashlib.sha1(audio16.tobytes()).hexdigest()[:16]
    cache = os.path.join(cache_dir, "sounds-%s.npz" % key)
    if os.path.exists(cache):
        d = np.load(cache)
        return {c: d[c].astype(np.float32) for c in CLASSES}
    if not available():
        log("  (laugh detection off: install torch + panns_inference and the Cnn14 model - see README)")
        return None
    import torch
    from panns_inference import SoundEventDetection, labels
    torch.set_num_threads(os.cpu_count() or 4)
    log("  listening for laughs (sound-event model)")
    audio = cap.timeline_audio(seq, log=lambda *a: None, rate=RATE)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):            # it prints its checkpoint path
        model = SoundEventDetection(checkpoint_path=MODEL, device="cpu")
    ix = [labels.index(c) for c in CLASSES]
    chunk = 60 * RATE
    parts = []
    for i in range(0, len(audio), chunk):
        seg = audio[i:i + chunk]
        if len(seg) < RATE:
            parts.append(np.zeros((len(seg) * FPS // RATE, len(ix)), np.float32))
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            fw = model.inference(seg[None, :])[0]
        parts.append(fw[:len(seg) * FPS // RATE, ix])
    fw = np.concatenate(parts)
    out = {c: fw[:, j] for j, c in enumerate(CLASSES)}
    os.makedirs(cache_dir, exist_ok=True)
    np.savez_compressed(cache, **{c: v.astype(np.float16) for c, v in out.items()})
    return out


def laugh_score(ev, smooth=0.3):
    """Smoothed 'someone is laughing' probability per frame, and which kind wins."""
    if "_score" not in ev:                           # computed once per project
        stack = np.stack([ev[c] for c in LAUGH], 1)
        k = np.ones(int(smooth * FPS)) / int(smooth * FPS)
        ev["_score"] = (np.convolve(stack.max(1), k, mode="same"), stack)
    return ev["_score"]


def laugh_at(ev, a, b):
    """Mean laugh score over [a, b) seconds (0 if no data)."""
    if ev is None:
        return 0.0
    score, _ = laugh_score(ev)
    seg = score[int(a * FPS):int(b * FPS)]
    return float(seg.mean()) if len(seg) else 0.0
