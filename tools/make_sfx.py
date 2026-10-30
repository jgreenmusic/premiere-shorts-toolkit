"""Makes the built-in sound effects in soundfx\\ - synthesised from scratch here, so they carry no
licence and no Content ID claim. Run it only to change the pack; the .wav files ship with the app:

    .venv\\Scripts\\python.exe tools\\make_sfx.py

Every sound is one small function below. Add one, add a line to SOUNDS, run this, and the Sound step
lists it. Needs numpy + scipy (only this tool does; the app reads plain .wav files).
Files: 48 kHz stereo 16-bit, levelled to about the same loudness.
"""
import json
import os
import wave

import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "soundfx")
SR = 48000
rng = np.random.default_rng(7)                     # same sounds every run


def times(d):
    return np.arange(int(d * SR)) / SR


def line(d, *points):
    """Straight lines through (time, value) points, d seconds long."""
    t = times(d)
    return np.interp(t, [p[0] for p in points], [p[1] for p in points])


def _blep(ph, dt):
    out = np.zeros_like(ph)
    m = ph < dt
    x = ph[m] / dt[m]
    out[m] = x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]
    out[m] = x * x + x + x + 1
    return out


def sine(f):
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def saw(f):
    dt = np.maximum(f / SR, 1e-6)
    ph = np.cumsum(dt) % 1.0
    return 2 * ph - 1 - _blep(ph, dt)


def square(f, duty=0.5):
    dt = np.maximum(f / SR, 1e-6)
    ph = np.cumsum(dt) % 1.0
    s = np.where(ph < duty, 1.0, -1.0)
    return s + _blep(ph, dt) - _blep((ph + 1 - duty) % 1.0, dt)


def noise(d):
    return rng.standard_normal(int(d * SR))


def decay(d, tau, attack=0.002):
    t = times(d)
    return np.exp(-t / tau) * np.minimum(1, t / max(attack, 1e-5))


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, f, q=3.0):
    b, a = signal.iirpeak(f, q, fs=SR)
    return signal.lfilter(b, a, x)


def sweep_bp(x, f, q=3.0):
    """Band-pass whose centre moves (state-variable filter): f is one value per sample."""
    out = np.zeros_like(x)
    low = band = 0.0
    k = 1.0 / q
    g = 2 * np.sin(np.pi * np.clip(f, 20, SR / 6.5) / SR)
    for i in range(len(x)):
        low += g[i] * band
        high = x[i] - low - k * band
        band += g[i] * high
        out[i] = band
    return out


def modes(d, parts, strike=0.0):
    """Struck metal or wood: [(frequency, level, decay seconds)], plus a click."""
    t = times(d)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in parts)
    if strike:
        x = x + strike * lp(noise(d), 5000) * np.exp(-t / 0.004)
    return x


def at(d, *hits):
    """Lay sounds on a silent line: (start seconds, array)."""
    x = np.zeros(int(d * SR))
    for s, y in hits:
        i = int(s * SR)
        n = min(len(y), len(x) - i)
        x[i:i + n] += y[:n]
    return x


def room(x, tail=0.5, wet=0.2, tone=3500):
    """Mono in, stereo out: a small space (decaying noise, a different one per side)."""
    n = int(tail * SR)
    t = np.arange(n) / SR
    out = []
    for _ in (0, 1):
        ir = lp(rng.standard_normal(n), tone) * np.exp(-t * 6.9 / tail)
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        y = signal.fftconvolve(x, ir)
        dry = np.concatenate([x, np.zeros(len(y) - len(x))])
        out.append(dry + wet * y)
    return np.stack(out, 1)


def brass(f, d, bright=1.0):
    """A breathy horn note: the sound opens up as it gets louder."""
    amp = line(d, (0, 0), (0.03, 1), (d * 0.75, 0.85), (d, 0))
    f = f * np.ones(len(amp))
    x = saw(f) + 0.4 * saw(f * 1.004)
    return sweep_bp(x, (500 + 1700 * amp * bright), 1.2) * amp


# ---------- short ones, good over a word ----------

def cuckoo():
    def call(f, d):
        t = times(d)
        return (sine(np.full(len(t), f)) + 0.25 * sine(np.full(len(t), f * 2)) + 0.12 * bp(noise(d), f, 8)) \
            * line(d, (0, 0), (0.015, 1), (d * 0.45, 0.7), (d, 0))
    return room(at(0.62, (0, call(659.3, 0.26)), (0.29, call(523.3, 0.33))), 0.4, 0.14)


def quack():
    def one(d, f0):
        f = line(d, (0, f0 * 1.25), (d * 0.3, f0), (d, f0 * 0.72))
        x = saw(f)
        x = bp(x, 1050, 4) + 0.9 * bp(x, 1900, 5) + 0.25 * bp(x, 3100, 6)
        return x * line(d, (0, 0), (0.012, 1), (d * 0.6, 0.8), (d, 0))
    return room(at(0.46, (0, one(0.17, 245)), (0.21, one(0.22, 225))), 0.25, 0.07)


def squeak():
    def one(d, lo, hi):
        f = line(d, (0, lo), (d * 0.4, hi), (d, hi * 0.82))
        f = f * (1 + 0.012 * np.sin(2 * np.pi * 41 * times(d)))
        x = sine(f) + 0.35 * sine(f * 2) + 0.12 * square(f * 0.5)
        return x * line(d, (0, 0), (0.02, 1), (d * 0.7, 0.85), (d, 0))
    return room(at(0.42, (0, one(0.19, 1700, 2900)), (0.21, one(0.2, 2300, 1500))), 0.15, 0.05)


def honk():
    def one(d, f0):
        f = line(d, (0, f0 * 0.82), (0.035, f0), (d, f0 * 1.03))
        x = square(f, 0.32)
        x = bp(x, 1150, 2.5) + 0.8 * bp(x, 2500, 3)
        return np.tanh(2.5 * x) * line(d, (0, 0), (0.012, 1), (d - 0.03, 0.9), (d, 0))
    return room(at(0.56, (0, one(0.2, 362)), (0.25, one(0.3, 362))), 0.3, 0.1)


def boing():
    d = 0.8
    t = times(d)
    f = 190 + 230 * (1 - np.exp(-t * 7)) + 120 * np.sin(2 * np.pi * 13 * t) * np.exp(-t * 2.4)
    x = sine(f) + 0.3 * sine(f * 2.76) + 0.12 * sine(f * 5.4)
    return room(x * decay(d, 0.28, 0.004), 0.2, 0.08)


def bonk():
    d = 0.32
    t = times(d)
    x = modes(d, [(410, 1, 0.075), (1010, 0.5, 0.03), (1730, 0.22, 0.016)], 0.5)
    body = sine(line(d, (0, 190), (0.05, 120), (d, 100))) * np.exp(-t / 0.05)
    return room(x + 0.9 * body, 0.18, 0.08)


def whistle(lo, hi, d=0.62):
    f = line(d, (0, lo), (d, hi)) * (1 + 0.012 * np.sin(2 * np.pi * 7.5 * times(d)))
    x = sine(f) + 0.05 * sine(f * 2) + 0.05 * sweep_bp(noise(d), f, 7)
    return room(x * line(d, (0, 0), (0.03, 1), (d - 0.05, 0.9), (d, 0)), 0.25, 0.1)


def raspberry():
    d = 0.78
    t = times(d)
    f = line(d, (0, 105), (0.5, 88), (d, 62)) * (1 + 0.11 * np.sin(2 * np.pi * 9 * t + 1) + 0.05 * rng.standard_normal(len(t)))
    x = saw(np.maximum(f, 30))
    flutter = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * np.cumsum(line(d, (0, 34), (d, 22))) / SR))
    x = lp(x * lp(flutter, 300), 1000) + 0.8 * bp(x, 340, 3)
    return room(np.tanh(1.8 * x) * line(d, (0, 0), (0.015, 1), (d * 0.7, 0.9), (d, 0)), 0.14, 0.05)


def bike_bell():
    def ring():
        return modes(0.8, [(2093, 1, 0.3), (2141, 0.7, 0.26), (4720, 0.32, 0.14), (6930, 0.14, 0.07)], 0.2)
    return room(at(1.05, (0, ring()), (0.17, 0.85 * ring())), 0.3, 0.1, 6000)


def cowbell():
    d = 0.42
    x = square(np.full(int(d * SR), 545.0)) + square(np.full(int(d * SR), 815.0))
    return room(bp(x, 830, 1.7) * (0.75 * decay(d, 0.022) + 0.45 * decay(d, 0.14)), 0.2, 0.08, 5000)


def pop():
    d = 0.09
    t = times(d)
    return room(sine(line(d, (0, 1250), (0.03, 340), (d, 180))) * np.exp(-t / 0.018) * np.minimum(1, t / 0.0006), 0.08, 0.05)


def buzzer():
    d = 0.75
    n = np.full(int(d * SR), 1.0)
    x = square(n * 108) + 0.9 * square(n * 146) + 0.5 * square(n * 217)
    return room(np.tanh(1.4 * lp(x, 2600)) * line(d, (0, 0), (0.006, 1), (d - 0.012, 1), (d, 0)), 0.12, 0.05)


def correct():
    def tone(f, d):
        t = times(d)
        return np.sin(2 * np.pi * f * t + 1.1 * np.exp(-t / 0.05) * np.sin(2 * np.pi * f * 2.01 * t)) * decay(d, 0.3)
    return room(at(0.95, (0, tone(1318.5, 0.75)), (0.13, tone(1661.2, 0.82))), 0.35, 0.14, 7000)


def kazoo():
    d = 0.55
    t = times(d)
    f = line(d, (0, 300), (0.05, 352), (0.33, 352), (0.42, 300), (d, 268)) * (1 + 0.016 * np.sin(2 * np.pi * 6 * t))
    x = saw(f) * (1 + 0.5 * bp(noise(d), 320, 2))
    x = bp(x, 1150, 2.2) + 0.7 * bp(x, 2700, 3) + 0.3 * x
    return room(np.tanh(1.8 * x) * line(d, (0, 0), (0.02, 1), (d - 0.05, 0.9), (d, 0)), 0.14, 0.05)


def laser():
    d = 0.3
    f = 3100 * np.exp(-times(d) * 12) + 170
    return room((square(f, 0.3) * 0.5 + sine(f)) * line(d, (0, 0), (0.002, 1), (d, 0)), 0.3, 0.14)


# ---------- longer ones, for a moment ----------

def sad_trombone():
    notes = [(233.1, 0.31), (220.0, 0.31), (207.7, 0.31), (196.0, 1.25)]
    parts, s = [], 0.0
    for i, (f, d) in enumerate(notes):
        t = times(d)
        last = i == 3
        bend = 1 + (0.03 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.3) if last else 0.0) - (0.05 * t if last else 0.0)
        parts.append((s, brass(f * bend, d, 0.75)))
        s += d + 0.02
    return room(at(s + 0.1, *parts), 0.5, 0.16)


def _snare(d=0.2, level=1.0):
    t = times(d)
    return level * (hp(noise(d), 900) * 0.38 * np.exp(-t / 0.06) + sine(line(d, (0, 280), (0.03, 190), (d, 170))) * np.exp(-t / 0.05))


def rimshot():
    d = 0.3
    t = times(d)
    tom = sine(line(d, (0, 180), (0.04, 105), (d, 88))) * np.exp(-t / 0.09)
    cy_d = 1.4
    tt = times(cy_d)
    cym = hp(noise(cy_d), 6000) * 0.34 * (np.exp(-tt / 0.32) + 0.5 * np.exp(-tt / 0.03))
    return room(at(2.0, (0, _snare(0.2, 0.75)), (0.15, tom), (0.31, _snare(0.2, 0.5)), (0.31, 0.9 * tom), (0.31, cym)), 0.5, 0.12, 6000)


def crickets():
    d = 3.2
    def voice(f, offset, gap):
        x = np.zeros(int(d * SR))
        s = offset
        while s < d - 0.3:
            for k in range(3):
                pd = 0.024
                tt = times(pd)
                x[int((s + k * 0.038) * SR):][:len(tt)] += np.sin(2 * np.pi * f * tt) * np.sin(np.pi * tt / pd) ** 2
            s += gap + rng.uniform(-0.02, 0.02)
        return x
    l = voice(4650, 0.05, 0.55) + 0.45 * voice(4380, 0.31, 0.71)
    r = 0.7 * voice(4650, 0.05, 0.55) + 0.8 * voice(4380, 0.31, 0.71)
    f = line(d, (0, 0), (0.1, 1), (d - 0.4, 1), (d, 0))
    return np.stack([l * f, r * f], 1)


def record_scratch():
    d = 0.5
    src = bp(noise(1.2), 1500, 0.8) + 0.5 * saw(np.full(int(1.2 * SR), 210.0))
    t = times(d)
    pos = 0.3 + 0.13 * np.sin(2 * np.pi * 4.2 * t + 0.4) * (1 + 1.3 * t) + 0.45 * t
    x = np.interp(np.clip(pos, 0, 1.19) * SR, np.arange(len(src)), src)
    speed = np.abs(np.gradient(pos, 1 / SR))
    return room(lp(x, 4200) * np.minimum(1, speed) * line(d, (0, 0), (0.008, 1), (d - 0.06, 1), (d, 0)), 0.14, 0.05)


def deep_boom():
    d = 1.9
    t = times(d)
    x = sine(line(d, (0, 150), (0.05, 62), (0.4, 47), (d, 40))) * np.exp(-t / 0.55) * np.minimum(1, t / 0.002)
    x = np.tanh(3.2 * x) + 0.55 * lp(noise(d), 1400) * np.exp(-t / 0.02)    # the grit is what a phone speaker plays
    return room(x, 1.6, 0.2, 1100)


def whoosh():
    d = 0.75
    f = line(d, (0, 280), (0.36, 2600), (d, 420))
    x = sweep_bp(noise(d), f, 1.4) * np.sin(np.pi * times(d) / d) ** 1.6
    pan = line(d, (0, 0.18), (d, 0.82))
    return np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1)


def air_horn():
    def blast(d):
        n = np.full(int(d * SR), 1.0)
        x = sum(saw(n * f) for f in (468, 474, 589, 595, 702))
        x = hp(x, 300) + 0.8 * bp(x, 2400, 2)
        return np.tanh(0.8 * x) * line(d, (0, 0), (0.01, 1), (d - 0.03, 1), (d, 0))
    return room(at(1.3, (0, blast(0.13)), (0.19, blast(0.13)), (0.38, blast(0.85))), 0.5, 0.16)


def ring_bell():
    def ring():
        return modes(1.3, [(1046, 1, 0.5), (1527, 0.55, 0.36), (2469, 0.38, 0.22), (3410, 0.2, 0.13)], 0.3)
    return room(at(2.0, (0, ring()), (0.32, ring()), (0.64, 1.1 * ring())), 0.5, 0.14, 6000)


def drum_roll():
    d = 1.75
    x = np.zeros(int(2.4 * SR))
    s, n = 0.0, 0
    while s < d:
        level = 0.16 + 0.55 * (s / d) ** 1.6
        x[int(s * SR):][:int(0.06 * SR)] += _snare(0.06, level * (0.8 + 0.2 * (n % 2)))[:len(x[int(s * SR):][:int(0.06 * SR)])]
        s += 0.038
        n += 1
    cy = times(0.65)
    x = x + at(2.4, (d, _snare(0.2, 1.0)), (d, hp(noise(0.65), 5000) * 0.45 * np.exp(-cy / 0.2)))
    return room(x, 0.5, 0.12, 6000)


def falling_bonk():
    w = whistle(2300, 420, 1.15)
    b = bonk()
    out = np.zeros((int(1.6 * SR), 2))
    out[:len(w)] += 0.6 * w
    i = int(1.1 * SR)
    out[i:i + len(b)] += b[:len(out) - i]
    return out


def ta_da():
    short = brass(np.full(int(0.14 * SR), 523.3), 0.14)
    def chord(d):
        n = np.full(int(d * SR), 1.0)
        return sum(brass(n * f * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * times(d))), d, 1.1) for f in (523.3, 659.3, 784.0, 1046.5))
    return room(at(1.3, (0, short), (0.19, chord(1.0))), 0.6, 0.18)


def gong():
    d = 3.4
    t = times(d)
    parts = [(98, 1, 1.5), (147, 0.7, 1.2), (211, 0.6, 1.0), (279, 0.5, 0.8), (368, 0.5, 0.55), (486, 0.42, 0.45), (644, 0.3, 0.3), (902, 0.2, 0.2)]
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) * (1 - np.exp(-t / (0.01 + 0.07 * (1 - tau / 1.5))))
            for f, a, tau in parts)
    return room(x, 1.0, 0.12, 2500)


def clock():
    d = 3.0
    tick = modes(0.04, [(2300, 1, 0.005), (3900, 0.5, 0.003)], 0.4)
    tock = modes(0.04, [(1650, 1, 0.006), (2850, 0.4, 0.004)], 0.4)
    return room(at(d, *[(k * 0.5, tick if k % 2 == 0 else 0.85 * tock) for k in range(6)]), 0.2, 0.06)


def lonely_wind():
    d = 3.2
    f = 620 + 240 * np.sin(2 * np.pi * 0.42 * times(d) + 0.6) + 90 * np.sin(2 * np.pi * 1.1 * times(d))
    x = sweep_bp(noise(d), f, 6) + 0.5 * lp(noise(d), 500) * 0.3
    return room(x * line(d, (0, 0), (0.7, 1), (d - 1.0, 0.8), (d, 0)), 0.6, 0.15, 3000)


# (file name, name in the app, group, how it is made)
SOUNDS = [
    ("cuckoo", "Cuckoo clock", "short", cuckoo),
    ("quack", "Duck quack", "short", quack),
    ("squeak", "Squeaky toy", "short", squeak),
    ("honk", "Clown horn", "short", honk),
    ("boing", "Boing", "short", boing),
    ("bonk", "Bonk", "short", bonk),
    ("slide-up", "Slide whistle up", "short", lambda: whistle(620, 2100)),
    ("slide-down", "Slide whistle down", "short", lambda: whistle(2100, 620)),
    ("raspberry", "Raspberry", "short", raspberry),
    ("kazoo", "Kazoo", "short", kazoo),
    ("bike-bell", "Bike bell", "short", bike_bell),
    ("cowbell", "Cowbell", "short", cowbell),
    ("pop", "Pop", "short", pop),
    ("buzzer", "Wrong-answer buzzer", "short", buzzer),
    ("correct", "Right-answer ding", "short", correct),
    ("laser", "Laser", "short", laser),
    ("sad-trombone", "Sad trombone", "moment", sad_trombone),
    ("rimshot", "Ba-dum-tss", "moment", rimshot),
    ("crickets", "Crickets", "moment", crickets),
    ("record-scratch", "Record scratch", "moment", record_scratch),
    ("deep-boom", "Deep boom", "moment", deep_boom),
    ("whoosh", "Whoosh", "moment", whoosh),
    ("air-horn", "Air horn", "moment", air_horn),
    ("ring-bell", "Boxing bell", "moment", ring_bell),
    ("drum-roll", "Drum roll", "moment", drum_roll),
    ("falling-bonk", "Falling... bonk", "moment", falling_bonk),
    ("ta-da", "Ta-da", "moment", ta_da),
    ("gong", "Gong", "moment", gong),
    ("clock", "Clock ticking", "moment", clock),
    ("lonely-wind", "Lonely wind", "moment", lonely_wind),
]

TARGET = 10 ** (-15 / 20)                          # loudness of the sounding part, about -15 dB
PEAK = 10 ** (-1.5 / 20)


def level(x):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    x = x - x.mean(axis=0)
    env = np.abs(x).max(axis=1)
    frames = np.array_split(env, max(1, len(env) // 960))
    loud = np.array([np.sqrt(np.mean(f ** 2)) for f in frames])
    rms = np.sqrt(np.mean(loud[loud > loud.max() * 0.1] ** 2))
    x = x * min(TARGET / rms, PEAK / env.max())
    tail = min(len(x), 240)                        # never end on a click
    x[-tail:] *= np.linspace(1, 0, tail)[:, None]
    return x


def write(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main():
    os.makedirs(OUT, exist_ok=True)
    index = []
    for file, name, group, make in SOUNDS:
        x = level(make())
        write(os.path.join(OUT, file + ".wav"), x)
        index.append(dict(file=file, name=name, group=group))
        print("%-16s %.2f s  peak %.2f" % (file, len(x) / SR, np.abs(x).max()))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)


if __name__ == "__main__":
    main()
