"""Sound events (laughs, giggles, chuckles, ...) from an AudioSet classifier.

PANNs Cnn14 (sound-event detection version) labels every 10 ms of the timeline with
527 AudioSet classes. We keep only the ones the toolkit uses, cached per audio.
On this footage it hears laughter well; it rates gamer yelling as ~0 "Screaming",
so screams are still found the old way - this only takes laughs OUT of the scream
suggestions.

Runs on onnxruntime + numpy (no PyTorch): the log-mel front end is computed here with
the model's own mel filterbank, and the network is models/panns_sed.onnx (made once by
tools/export_panns_onnx.py). Without the model file, laugh detection is simply skipped.
"""
import hashlib
import os
import sys

import numpy as np

import captions as cap

RATE = 32000                     # the model's sample rate
FPS = 100                        # frames per second it outputs (hop 320)
N_FFT, HOP = 1024, 320
# AudioSet class indices (class_labels_indices.csv)
CLASS_INDEX = {"Laughter": 16, "Giggle": 18, "Snicker": 19, "Belly laugh": 20, "Chuckle, chortle": 21,
               "Screaming": 14, "Yell": 11, "Shout": 8}
CLASSES = list(CLASS_INDEX)
LAUGH = CLASSES[:5]


def _res(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


MODEL = _res("models", "panns_sed.onnx")
MELW = _res("models", "panns_melW.npy")
_session = None


def available():
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(MODEL) and os.path.exists(MELW)


def _logmel(audio):
    """Same front end as torchlibrosa: centred reflect-padded STFT, periodic Hann,
    power spectrum, the model's mel filterbank, 10*log10 (amin 1e-10, ref 1)."""
    pad = N_FFT // 2
    x = np.pad(audio.astype(np.float32), (pad, pad), mode="reflect")
    n = 1 + (len(x) - N_FFT) // HOP
    frames = np.lib.stride_tricks.as_strided(x, shape=(n, N_FFT), strides=(x.strides[0] * HOP, x.strides[0]))
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)
    spec = np.abs(np.fft.rfft(frames * win, axis=1)) ** 2
    mel = spec.astype(np.float32) @ np.load(MELW)
    return (10.0 * np.log10(np.maximum(mel, 1e-10))).astype(np.float32)


def infer(audio):
    """(frames, 527) probabilities for 32 kHz mono audio, 100 frames/s."""
    global _session
    if _session is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = os.cpu_count() or 4
        _session = ort.InferenceSession(MODEL, opts, providers=["CPUExecutionProvider"])
    lm = _logmel(audio)
    probs = _session.run(None, {"logmel": lm[None, None]})[0][0]     # (T/32, 527)
    out = np.repeat(probs, 32, axis=0)[:len(lm)]
    if len(out) < len(lm):                                            # pad with the last frame
        out = np.concatenate([out, np.repeat(out[-1:], len(lm) - len(out), axis=0)])
    return out


def detect(seq, cache_dir, audio16, log=print, classes=None, tag="sounds", what="for laughs"):
    """{class name: np.array of per-frame probability} for CLASSES, or None if unavailable.
    classes / tag: another set of AudioSet classes kept in its own cache file (music mode)."""
    index = classes or CLASS_INDEX
    names = list(index)
    key = cap.audio_key(audio16)
    cache = os.path.join(cache_dir, "%s-%s.npz" % (tag, key))
    if os.path.exists(cache):
        d = np.load(cache)
        return {c: d[c].astype(np.float32) for c in names}
    if not available():
        log("  (sound-event model off: models/panns_sed.onnx is missing)")
        return None
    log("  listening %s (sound-event model)" % what)
    audio = cap.timeline_audio(seq, log=lambda *a: None, rate=RATE)
    ix = [index[c] for c in names]
    chunk = 60 * RATE
    parts = []
    for i in range(0, len(audio), chunk):
        seg = audio[i:i + chunk]
        frames = len(seg) * FPS // RATE
        if len(seg) < RATE:
            parts.append(np.zeros((frames, len(ix)), np.float32))
            continue
        parts.append(infer(seg)[:frames, ix])
    fw = np.concatenate(parts)
    out = {c: fw[:, j] for j, c in enumerate(names)}
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
