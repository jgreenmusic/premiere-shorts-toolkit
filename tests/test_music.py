"""Tests for music mode: beats, bars, sections, silences, the Shorts it suggests, the fade.

    .venv\\Scripts\\python.exe tests\\test_music.py           everything (makes a test video, renders one Short)
    .venv\\Scripts\\python.exe tests\\test_music.py Quick     the fast ones only

The "music" is made here with numpy (clicks at a known tempo, a hum, silence) so the right
answers are known. None of your projects are touched.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import captions
import config
import music
import render

PY = sys.executable
SR = captions.RATE


def clicks(seconds, bpm, level=0.5):
    """A drum-like tick on every beat."""
    t = np.arange(int(seconds * SR)) / SR
    phase = np.mod(t, 60.0 / bpm)
    return (level * np.sin(2 * np.pi * 220 * t) * np.exp(-phase * 30)).astype(np.float32)


def hum(seconds, hz=110, level=0.2):
    """A steady tone: sound, but nothing to count."""
    t = np.arange(int(seconds * SR)) / SR
    return (level * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def piece(bpm, intro=20, body=50):
    """A quiet opening, then the full thing - real music is never the same loudness throughout."""
    return np.concatenate([clicks(intro, bpm, 0.12), clicks(body, bpm, 0.5)])


def silence(seconds):
    return np.zeros(int(seconds * SR), np.float32)


def heard(audio):
    """What music.listen() returns, without the sound-event model."""
    feat = music.features(audio)
    bt, bs = music.beats(feat)
    st, ss = music.sections(feat)
    return dict(feat=feat, beats=bt, beat_strength=bs, sections=st, section_strength=ss,
                silences=music.silences(feat), where=None)


def picture(audio, m):
    seq = SimpleNamespace(end_s=len(audio) / SR, markers=[], video=[])
    return music.summary(SimpleNamespace(seq=seq), m)


class QuickListening(unittest.TestCase):
    def test_tempo_of_a_steady_beat(self):
        for bpm in (90, 120, 150):
            with self.subTest(bpm=bpm):
                period, sure = music.beat_period(music.features(clicks(30, bpm)), 1, 29)
                self.assertAlmostEqual(period, 60.0 / bpm, delta=0.03)
                self.assertGreaterEqual(sure, music.PULSE)

    def test_no_pulse_in_a_hum(self):
        period, sure = music.beat_period(music.features(hum(30)), 1, 29)
        self.assertLess(sure, music.PULSE)

    def test_beats_land_on_the_clicks(self):
        bt, strength = music.beats(music.features(clicks(20, 120)))
        self.assertGreater(len(bt), 30)                       # 40 clicks in 20 s
        off = np.abs(bt / 0.5 - np.round(bt / 0.5)) * 0.5     # distance to the nearest click
        self.assertLess(np.median(off), 0.04)

    def test_gap_between_two_pieces(self):
        gaps = music.silences(music.features(np.concatenate([clicks(20, 120), silence(2), clicks(20, 100)])))
        self.assertEqual(len(gaps), 1, gaps)
        self.assertAlmostEqual(gaps[0][0], 20.0, delta=0.6)   # the last click rings out a little
        self.assertAlmostEqual(gaps[0][1], 22.0, delta=0.1)

    def test_section_where_the_sound_changes(self):
        st, strength = music.sections(music.features(np.concatenate([hum(40), clicks(40, 120)])))
        self.assertTrue(any(abs(t - 40) <= 1.5 for t in st), st)


class QuickSuggestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # two pieces with a gap, then a third that starts with a quiet hum
        cls.audio = np.concatenate([piece(120), silence(2), piece(100), silence(2), hum(20, level=0.05), piece(140, 10, 50)])
        cls.m = heard(cls.audio)
        cls.summ = picture(cls.audio, cls.m)
        cls.found = music.suggest(cls.summ, cls.m, count=6, length=(20, 45))

    def test_some_are_found(self):
        self.assertGreaterEqual(len(self.found), 3, self.found)

    def test_lengths_are_respected(self):
        for s in self.found:
            self.assertGreaterEqual(s["end"] - s["start"], 19.5, s)
            self.assertLessEqual(s["end"] - s["start"], 45.0, s)

    def test_none_runs_through_a_gap_or_opens_on_one(self):
        for s in self.found:
            for a, b in self.m["silences"]:
                self.assertFalse(s["start"] + 2 < a < s["end"] - 0.5, (s, a, b))
                self.assertFalse(a <= s["start"] < b - 0.1, (s, a, b))

    def test_none_overlap_and_taken_ranges_are_skipped(self):
        order = sorted(self.found, key=lambda s: s["start"])
        for x, y in zip(order, order[1:]):
            self.assertLessEqual(x["end"], y["start"])
        again = music.suggest(self.summ, self.m, count=6, length=(20, 45), avoid=[(s["start"], s["end"]) for s in self.found])
        for s in again:
            for t in self.found:
                self.assertFalse(s["start"] < t["end"] and t["start"] < s["end"], (s, t))

    def test_a_steady_beat_gives_whole_bars(self):
        audio = np.concatenate([clicks(30, 120, 0.12), clicks(60, 120, 0.5), clicks(30, 120, 0.12)])   # seamless: beats stay on the grid
        m = heard(audio)
        got = music.suggest(picture(audio, m), m, count=2, length=(20, 45))
        self.assertTrue(got)
        for s in got:
            bars = (s["end"] - s["start"]) / 2.0              # 120 a minute: a bar of four is 2 s
            self.assertAlmostEqual(bars, round(bars), delta=0.08, msg=str(s))

    def test_talking_is_left_out(self):
        m = dict(self.m, where=np.ones(int(len(self.audio) / SR)))
        m["where"][:72] = 0                                   # "somebody is talking" over the first piece
        got = music.suggest(picture(self.audio, m), m, count=6, length=(20, 45))
        self.assertTrue(got)
        for s in got:
            self.assertGreaterEqual(s["start"], 70, s)

    def test_the_picture_has_what_the_app_draws(self):
        for key in ("duration", "bin", "loud", "speech", "excite", "markers", "pauses", "screams", "laughs", "loud_lines", "video"):
            self.assertIn(key, self.summ)
        self.assertEqual(self.summ["kind"], "music")
        json.dumps(self.summ)                                 # plain numbers only: it is saved as timeline.json


class QuickSettings(unittest.TestCase):
    def test_kinds(self):
        gaming, mus = config._merge(config.DEFAULTS, {}), config._merge(config.DEFAULTS, {"kind": "music"})
        self.assertEqual(config.kind(gaming), "gaming")        # every existing project
        self.assertTrue(config.speech_on(gaming) and config.reactions_on(gaming))
        self.assertFalse(config.speech_on(mus) or config.reactions_on(mus))
        mus["music"]["captions"] = True
        self.assertTrue(config.speech_on(mus))
        self.assertFalse(config.reactions_on(mus))
        self.assertEqual(config.kind({"kind": "something from a newer version"}), "gaming")

    def test_fade_only_for_music(self):
        self.assertEqual(render.fade_filter(config._merge(config.DEFAULTS, {}), 30), "anull")
        f = render.fade_filter(config._merge(config.DEFAULTS, {"kind": "music"}), 30)
        self.assertEqual(f, "afade=t=out:st=29.650:d=0.350")
        f = render.fade_filter(config._merge(config.DEFAULTS, {"kind": "music", "music": {"fade_in": 1, "fade_out": 0}}), 30)
        self.assertEqual(f, "afade=t=in:st=0:d=1.000")


def cli(*argv):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    r = subprocess.run([PY, os.path.join(ROOT, "shorts.py")] + list(argv), cwd=ROOT, env=env, capture_output=True, timeout=600)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg and ffprobe on PATH")
class WholeRun(unittest.TestCase):
    """A music recording in, a finished Short out, and nothing transcribed on the way."""

    def test_music_clip_to_finished_short(self):
        tmp = tempfile.mkdtemp(prefix="shorts-toolkit-music-")
        try:
            wav, clip = os.path.join(tmp, "set.f32"), os.path.join(tmp, "set.mp4")
            np.concatenate([clicks(40, 120), silence(2), clicks(40, 100)]).tofile(wav)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                            "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", wav, "-shortest", "-pix_fmt", "yuv420p",
                            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", clip], check=True)
            code, out = cli("kind", clip, "music")
            self.assertEqual(code, 0, out)
            code, out = cli("markers", clip, "--count", "3", "--min", "10", "--max", "20")
            self.assertEqual(code, 0, out)
            outdir = os.path.join(tmp, "set_captions")
            with open(os.path.join(outdir, "toolkit.json"), encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertEqual(cfg["kind"], "music")
            self.assertTrue(cfg["markers"], out)
            self.assertEqual(glob.glob(os.path.join(outdir, "words-*.json")), [], "music mode must not transcribe")
            with open(os.path.join(outdir, "timeline.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["kind"], "music")
            m = cfg["markers"][0]
            code, out = cli("make", clip, "--start", str(m["start"]), "--end", str(m["end"]), "--name", "one", "--preset", "ultrafast")
            self.assertEqual(code, 0, out)
            made = os.path.join(tmp, "set_shorts", "one.mp4")
            probe = json.loads(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                 "-of", "json", made], capture_output=True, check=True).stdout)
            video = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
            self.assertEqual((video["width"], video["height"]), (1080, 1920))
            self.assertAlmostEqual(float(probe["format"]["duration"]), m["end"] - m["start"], delta=0.3)
            # the fade: the last tenth of a second is far quieter than the second before it
            pcm = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", made, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                               capture_output=True, check=True).stdout, np.float32)
            rms = lambda x: float(np.sqrt((x ** 2).mean()))
            self.assertLess(rms(pcm[-1600:]), 0.4 * rms(pcm[-32000:-16000]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
