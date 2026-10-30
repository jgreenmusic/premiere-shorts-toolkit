"""Tests for the sound library, sound-effect rules, music under a Short and the long video.

    .venv\\Scripts\\python.exe tests\\test_sound.py           everything (renders a few seconds of test video)
    .venv\\Scripts\\python.exe tests\\test_sound.py Quick     the fast ones only

The test clip is made by ffmpeg in a temp folder and %LOCALAPPDATA% points at that folder, so neither
your projects nor your own sound library are touched.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bleep
import config
import longform
import premiere_export as px
import render
import sfx
import soundlib
import stale
from prproj import TICKS

SR = soundlib.SR


def cfg_with(**over):
    c = copy.deepcopy(config.DEFAULTS)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(c.get(k), dict):
            c[k].update(v)
        else:
            c[k] = v
    return c


def rule(**over):
    return dict(sfx.RULE, id="r1", sounds=["fx:bonk"], gap=0, **over)


class Lib(unittest.TestCase):
    """A private %LOCALAPPDATA% for tests that add sounds."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sound-test-")
        self.keep = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.tmp

    def tearDown(self):
        os.environ["LOCALAPPDATA"] = self.keep
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tone(self, name="tone.mp3", seconds=1):
        p = os.path.join(self.tmp, name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=500:duration=%s" % seconds, p], check=True)
        return p


class QuickLibrary(Lib):
    def test_every_built_in_sound_is_listed_and_readable(self):
        fx = soundlib.listing()["effects"]
        self.assertGreaterEqual(len(fx), 30)
        for s in fx:
            self.assertGreater(s["seconds"], 0.05, s["id"])
            x = sfx.read(soundlib.path_of(s["id"]))
            self.assertEqual(x.shape[1], 2)
            self.assertGreater(np.abs(x).max(), 0.1, s["id"] + " is nearly silent")
            self.assertLessEqual(np.abs(x).max(), 1.0)

    def test_built_in_sounds_are_about_as_loud_as_each_other(self):
        for s in soundlib.listing()["effects"]:
            with wave.open(soundlib.path_of(s["id"]), "rb") as w:
                self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (48000, 2, 2), s["id"])

    def test_an_added_mp3_becomes_a_library_sound(self):
        e = soundlib.add(self.tone(), "effect", "My Honk.mp3")
        self.assertEqual(e["id"], "my:My Honk.wav")
        self.assertEqual(e["group"], "yours")
        self.assertAlmostEqual(e["seconds"], 1.0, delta=0.15)
        self.assertIn(e["id"], [s["id"] for s in soundlib.listing()["effects"]])

    def test_the_same_name_twice_keeps_both(self):
        a, b = soundlib.add(self.tone(), "effect", "x.mp3"), soundlib.add(self.tone(), "effect", "x.mp3")
        self.assertNotEqual(a["id"], b["id"])

    def test_a_file_without_sound_is_refused_and_leaves_nothing(self):
        bad = os.path.join(self.tmp, "notes.txt")
        with open(bad, "w") as f:
            f.write("not audio")
        with self.assertRaises(ValueError):
            soundlib.add(bad, "effect", "notes.txt")
        self.assertEqual(os.listdir(soundlib.folder("effect")), [])

    def test_an_id_cannot_climb_out_of_the_library(self):
        secret = os.path.join(self.tmp, "ShortsToolkit", "secret.wav")
        os.makedirs(os.path.dirname(secret), exist_ok=True)
        with open(secret, "wb") as f:
            f.write(b"x")
        self.assertIsNone(soundlib.path_of("my:..\\..\\secret.wav"))
        self.assertIsNone(soundlib.path_of("nonsense"))
        self.assertIsNone(soundlib.path_of(None))

    def test_built_in_sounds_cannot_be_removed(self):
        with self.assertRaises(ValueError):
            soundlib.remove("fx:bonk")
        self.assertTrue(soundlib.path_of("fx:bonk"))

    def test_removing_your_own_sound(self):
        e = soundlib.add(self.tone(), "music", "song.mp3")
        soundlib.remove(e["id"])
        self.assertIsNone(soundlib.path_of(e["id"]))


class QuickRules(unittest.TestCase):
    def plan(self, rules, m, a=0, b=30, **sf):
        return sfx.plan(cfg_with(sfx=dict(on=True, rules=rules, spacing=0, **sf)), m, a, b)

    def test_nothing_happens_unless_switched_on(self):
        self.assertEqual(sfx.plan(cfg_with(sfx=dict(rules=[rule(when="start")])), {}, 0, 30), [])
        self.assertFalse(sfx.wanted(config.DEFAULTS))

    def test_a_music_project_gets_no_effects_or_bed(self):
        c = cfg_with(kind="music", sfx=dict(on=True, rules=[rule(when="start")]), bed=dict(on=True, tracks=["music:a.wav"]))
        self.assertFalse(sfx.wanted(c))
        self.assertEqual(sfx.plan(c, {}, 0, 30), [])

    def test_start_scream_laugh_and_loud(self):
        m = dict(scream=[5.0, 50.0], laugh=[6.0], loud=[7.0])
        got = {w: [h["t"] for h in self.plan([rule(when=w)], m)] for w in ("start", "scream", "laugh", "loud")}
        self.assertEqual(got, dict(start=[0], scream=[5.0], laugh=[6.0], loud=[7.0]))

    def test_end_lands_so_the_sound_finishes_with_the_short(self):
        t = self.plan([rule(when="end")], {})[0]["t"]
        self.assertAlmostEqual(t + soundlib.duration(soundlib.path_of("fx:bonk")), 30, places=2)

    def test_a_word_or_phrase(self):
        words = [[1, 1.2, "oh"], [1.2, 1.5, "no!"], [4, 4.2, "Oh"], [4.2, 4.4, "well"], [8, 8.2, "bruh"]]
        hits = self.plan([rule(when="word", words="oh no, bruh")], dict(words=words))
        self.assertEqual([h["t"] for h in hits], [1, 8])

    def test_a_long_pause_fires_once_at_its_start(self):
        hits = self.plan([rule(when="pause", secs=3)], dict(voice=[[0, 2], [2.5, 4], [9, 10], [29, 30]]))
        self.assertEqual([round(h["t"], 1) for h in hits], [4.2, 10.2])

    def test_every_n_seconds(self):
        self.assertEqual([h["t"] for h in self.plan([rule(when="every", secs=10)], {})], [10.0, 20.0])

    def test_gap_and_most_per_short(self):
        m = dict(scream=[1.0, 2.0, 3.0, 7.0, 12.0])
        self.assertEqual([h["t"] for h in self.plan([dict(rule(when="scream"), gap=5)], m)], [1.0, 7.0, 12.0])
        self.assertEqual([h["t"] for h in self.plan([dict(rule(when="scream"), max=2)], m)], [1.0, 2.0])

    def test_chance_keeps_about_that_share_and_the_same_ones_every_time(self):
        m = dict(scream=[float(t) / 2 for t in range(400)])
        one = self.plan([rule(when="scream", chance=30)], m, 0, 400)
        two = self.plan([rule(when="scream", chance=30)], m, 0, 400)
        self.assertEqual(one, two)
        self.assertTrue(60 < len(one) < 180, len(one))

    def test_several_sounds_are_shared_out_and_stay_put(self):
        m = dict(scream=[float(t) for t in range(40)])
        hits = self.plan([dict(rule(when="scream"), sounds=["fx:bonk", "fx:pop", "fx:quack"])], m)
        self.assertEqual({h["sound"] for h in hits}, {"fx:bonk", "fx:pop", "fx:quack"})

    def test_a_sound_removed_from_the_library_is_skipped_not_a_crash(self):
        self.assertEqual(self.plan([dict(rule(when="start"), sounds=["my:gone.wav"])], {}), [])

    def test_spacing_keeps_effects_apart_and_hand_placed_ones_win(self):
        c = cfg_with(sfx=dict(on=True, spacing=1.0, rules=[rule(when="scream")], add=[dict(t=5.2, sound="fx:pop", volume=1)]))
        got = sfx.plan(c, dict(scream=[5.0, 8.0]), 0, 30)
        self.assertEqual([(h["t"], h.get("hand", False)) for h in got], [(5.2, True), (8.0, False)])

    def test_a_hit_you_skip_stays_listed_but_does_not_block_others(self):
        m = dict(scream=[5.0])
        c = cfg_with(sfx=dict(on=True, spacing=0, rules=[rule(when="scream")], off=["r1@5.00"]))
        h = sfx.plan(c, m, 0, 30)
        self.assertEqual([x["on"] for x in h], [False])
        self.assertIsNone(sfx.mix(h, None, SR))

    def test_each_short_only_gets_its_own_hits(self):
        m = dict(scream=[5.0, 25.0])
        self.assertEqual([h["t"] for h in self.plan([rule(when="scream")], m, 20, 30)], [25.0])

    def test_censor_sound_replaces_the_beep(self):
        c = cfg_with(bleep=dict(on=True, sound="effect", effects=["fx:quack"]))
        h = sfx.plan(c, dict(words=[[3, 3.3, "fuck"], [9, 9.3, "hello"]]), 0, 30)
        self.assertEqual([(round(x["t"], 2), x["sound"], x["cut"]) for x in h], [(2.96, "fx:quack", None)])
        self.assertTrue(sfx.wanted(c))

    def test_censor_sound_can_stop_with_the_word(self):
        c = cfg_with(bleep=dict(on=True, sound="effect", effects=["fx:sad-trombone"], fit="word"))
        h = sfx.plan(c, dict(words=[[3, 3.3, "fuck"]]), 0, 30)[0]
        self.assertAlmostEqual(len(sfx.clip_audio(h)) / SR, 0.38, places=2)

    def test_short_start_and_end_rules_do_not_fire_on_every_chapter(self):
        c = cfg_with(sfx=dict(on=True, spacing=0, rules=[rule(when="start"), dict(rule(when="scream"), id="r2")]))
        self.assertEqual(len(sfx.plan(c, dict(scream=[5.0]), 0, 30)), 2)
        self.assertEqual([h["key"] for h in sfx.plan(c, dict(scream=[5.0]), 0, 30, wide=True)], ["r2@5.00"])

    def test_the_old_beep_setting_is_unchanged(self):
        self.assertEqual(bleep.audio_filter("[a]", "[b]", [(1, 2)], "effect", 5)[-1], "[bl_dry]anull[b]")
        self.assertIn("sine=frequency=1000", " ".join(bleep.audio_filter("[a]", "[b]", [(1, 2)], "beep", 5)))


class QuickBed(Lib):
    def track(self, seconds=2):
        return soundlib.add(self.tone(seconds=seconds), "music", "song.mp3")["id"]

    def test_the_level_dips_while_someone_talks_without_a_step(self):
        g = sfx.gain_curve(6 * SR, [[2, 4]], 0, 0.2, 0.5, 0, 0)
        self.assertAlmostEqual(g[int(0.5 * SR)], 0.2, places=3)
        self.assertAlmostEqual(g[3 * SR], 0.1, places=3)
        self.assertLess(np.abs(np.diff(g)).max(), 0.001)         # eased, never a click

    def test_fades_reach_silence(self):
        g = sfx.gain_curve(4 * SR, [], 0, 0.2, 0.5, 0.5, 1.0)
        self.assertLess(g[0], 1e-3)
        self.assertLess(g[-1], 1e-3)
        self.assertAlmostEqual(g[2 * SR], 0.2, places=3)

    def test_a_short_track_goes_round_to_fill_the_short(self):
        c = cfg_with(bed=dict(on=True, tracks=[self.track(2)], fade_in=0, fade_out=0, duck=1))
        x = sfx.bed_audio(c, {}, 10, 17, "a Short")
        self.assertEqual(len(x), 7 * SR)
        self.assertGreater(np.abs(x[-SR:]).max(), 0.01)

    def test_one_short_can_go_without(self):
        c = cfg_with(bed=dict(on=True, tracks=[self.track()], skip=["quiet one"]))
        self.assertIsNone(sfx.bed_audio(c, {}, 0, 5, "quiet one"))
        self.assertIsNotNone(sfx.bed_audio(c, {}, 0, 5, "loud one"))

    def test_the_long_video_only_gets_music_if_you_ask(self):
        c = cfg_with(bed=dict(on=True, tracks=[self.track()]))
        self.assertIsNone(sfx.bed_for(c, {}, 0, 5, "a", wide=True))
        self.assertIsNotNone(sfx.bed_for(c, {}, 0, 5, "a"))
        c["long"]["music"] = True
        self.assertIsNotNone(sfx.bed_for(c, {}, 0, 5, "a", wide=True))

    def test_mix_puts_a_sound_where_it_belongs_and_clips_at_the_end(self):
        x = sfx.mix([dict(sound="fx:pop", volume=1, t0=1.0, on=True)], None, 2 * SR)
        self.assertEqual(np.abs(x[:SR]).max(), 0)
        self.assertGreater(np.abs(x[SR:]).max(), 0.1)
        self.assertEqual(len(sfx.mix([dict(sound="fx:gong", volume=1, t0=1.9, on=True)], None, 2 * SR)), 2 * SR)


class QuickStaleness(unittest.TestCase):
    s = dict(name="A", start=10.0, end=20.0)

    def test_old_renders_are_not_flagged_by_this_update(self):
        old = {k: v for k, v in stale.parts(config.DEFAULTS, self.s).items() if k != "sound"}
        d = tempfile.mkdtemp()
        v = os.path.join(d, "a.mp4")
        with open(v, "wb") as f:
            f.write(b"x")
        self.assertEqual(stale.status(config.DEFAULTS, self.s, v, None, dict(A=dict(parts=old)))["changed"], [])
        shutil.rmtree(d)

    def test_the_new_settings_did_not_change_the_look_fingerprint(self):
        self.assertNotIn("effects", config.DEFAULTS["bleep"])    # or every Short on every project reads "changed"

    def test_a_sound_placed_in_one_short_only_marks_that_short(self):
        base = cfg_with()
        inside = cfg_with(sfx=dict(add=[dict(t=15.0, sound="fx:pop", volume=1)]))
        far = cfg_with(sfx=dict(add=[dict(t=500.0, sound="fx:pop", volume=1)]))
        self.assertNotEqual(stale.parts(base, self.s)["sound"], stale.parts(inside, self.s)["sound"])
        self.assertEqual(stale.parts(base, self.s)["sound"], stale.parts(far, self.s)["sound"])

    def test_a_rule_or_the_music_marks_every_short(self):
        base = stale.parts(cfg_with(), self.s)["sound"]
        self.assertNotEqual(base, stale.parts(cfg_with(sfx=dict(on=True)), self.s)["sound"])
        self.assertNotEqual(base, stale.parts(cfg_with(bed=dict(on=True)), self.s)["sound"])

    def test_no_music_on_this_short_only_marks_this_short(self):
        c = cfg_with(bed=dict(skip=["A"]))
        self.assertNotEqual(stale.parts(cfg_with(), self.s)["sound"], stale.parts(c, self.s)["sound"])
        self.assertEqual(stale.parts(cfg_with(), dict(self.s, name="B"))["sound"], stale.parts(c, dict(self.s, name="B"))["sound"])


class QuickLong(unittest.TestCase):
    shorts = [dict(name="B", start=300.0, end=320.0), dict(name="A", start=100.0, end=120.0), dict(name="C", start=330.0, end=350.0)]

    def out(self, m=None, end=1000.0, **lg):
        return longform.outline(cfg_with(shorts=self.shorts, long=lg), m or {}, end)

    def test_shorts_become_chapters_in_recording_order_with_the_recording_around_them(self):
        p = self.out(before=5, after=5, join=0)
        self.assertEqual([(x["start"], x["end"], x["shorts"]) for x in p], [(95, 125, ["A"]), (295, 355, ["B", "C"])])

    def test_with_no_extra_it_is_just_the_shorts_end_to_end(self):
        p = self.out(before=0, after=0, join=0)
        self.assertEqual([x["end"] - x["start"] for x in p], [20, 20, 20])
        self.assertEqual([x["at"] for x in p], [0, 20, 40])

    def test_close_shorts_join_into_one_chapter_with_the_part_between_kept(self):
        p = self.out(before=0, after=0, join=15)
        self.assertEqual([x["shorts"] for x in p], [["A"], ["B", "C"]])
        self.assertEqual((p[1]["start"], p[1]["end"]), (300, 350))

    def test_your_order_and_skips_win(self):
        p = self.out(before=0, after=0, join=0, order=["C", "A"], skip=["B"])
        self.assertEqual([x["shorts"] for x in p], [["C"], ["A"]])

    def test_a_new_short_still_shows_up_after_you_set_an_order(self):
        p = self.out(before=0, after=0, join=0, order=["C", "A"])
        self.assertEqual([x["shorts"][0] for x in p], ["C", "A", "B"])

    def test_edges_move_to_a_gap_in_the_talking(self):
        p = self.out(dict(voice=[[93, 96], [124, 127]]), before=5, after=5, join=0, skip=["B", "C"])
        self.assertEqual((p[0]["start"], p[0]["end"]), (92.9, 127.1))

    def test_a_chapter_never_runs_past_the_recording(self):
        p = longform.outline(cfg_with(shorts=[dict(name="Z", start=2.0, end=8.0)]), {}, 9.0)
        self.assertEqual((p[0]["start"], p[0]["end"]), (0, 9.0))

    def test_chapter_lines_start_at_zero(self):
        p = self.out(before=0, after=0, join=0, titles=dict(A="The start"))
        self.assertEqual(longform.chapters(p), ["0:00 The start", "0:20 B", "0:40 C"])

    def test_problems_youtube_would_have_with_the_chapters(self):
        self.assertEqual(longform.problems(self.out(before=0, after=0, join=0)), [])
        p = longform.outline(cfg_with(shorts=[dict(name="Z", start=0, end=5.0)], long=dict(before=0, after=0)), {}, 100.0)
        self.assertEqual(len(longform.problems(p)), 2)


class QuickXml(unittest.TestCase):
    def test_overlapping_sounds_get_their_own_tracks(self):
        c = lambda s, e: ("x", "x.wav", s, e, 0, True, None, 1.0)
        got = px.lanes([c(0, 2), c(1, 3), c(2.5, 4), c(3.5, 5)])
        self.assertEqual([[x[2] for x in lane] for lane in got], [[0, 2.5], [1, 3.5]])

    def test_a_clip_carries_its_level(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.wav")
        sfx.write(p, np.zeros((SR, 2)))
        px._INFO.clear()
        x = px.Xml(px.Rate("30/1"))
        got = "".join(x.sound([("a", p, 0, 1, 0, True, None, 0.5)], 1))
        self.assertIn("<parameterid>level</parameterid>", got)
        self.assertIn("<value>0.50000</value>", got)
        self.assertNotIn("audiolevels", "".join(x.sound([("a", p, 0, 1, 0, True, None)], 1)))
        shutil.rmtree(d)


@unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg on PATH")
class Renders(Lib):
    def setUp(self):
        super().setUp()
        self.clip = os.path.join(self.tmp, "clip.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30", "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-t", "40", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", self.clip], check=True)
        self.outdir = os.path.join(self.tmp, "clip_captions")
        os.makedirs(self.outdir)

    def ctx(self, **over):
        it = lambda tr: SimpleNamespace(start=0, end=40 * TICKS, src_in=0, path=self.clip, track=tr, name="clip", source_track=0, channel=0)
        seq = SimpleNamespace(video=[it(0)], audio=[it(0)], captions=[], end_s=40.0, name="clip", markers=[])
        c = cfg_with(**over)
        return SimpleNamespace(seq=seq, cfg=c, outdir=self.outdir, base=os.path.join(self.tmp, "clip"), words=[], regions=[],
                               moments=dict(scream=[], laugh=[], loud=[], words=[[2.0, 2.4, "shit"]], voice=[[1, 3]]),
                               captions=[], matches=[], fit={}, auto=False)

    def peak_at(self, video, a, b):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", video, "-f", "f32le", "-ac", "2", "-ar", "48000", "-"],
                             capture_output=True, check=True).stdout
        return float(np.abs(np.frombuffer(raw, np.float32)).max()) if raw else 0.0

    def size_of(self, video):
        import av
        with av.open(video) as c:
            v = c.streams.video[0]
            return v.codec_context.width, v.codec_context.height

    def test_censor_sound_effects_and_music_are_in_the_render(self):
        music = soundlib.add(self.tone(seconds=3), "music", "m.mp3")["id"]
        ctx = self.ctx(bleep=dict(on=True, sound="effect", effects=["fx:bonk"]),
                       sfx=dict(on=True, rules=[rule(when="every", secs=5)], spacing=0, volume=1),
                       bed=dict(on=True, tracks=[music], volume=0.05, duck=1, fade_in=0, fade_out=0))
        out = os.path.join(self.tmp, "short.mp4")
        render.make_short(ctx, 0, 8, out, [], preset="ultrafast", name="A", log=lambda *_: None)
        self.assertEqual(self.size_of(out), (1080, 1920))
        music_only = self.peak_at(out, 3.5, 4.5)
        self.assertTrue(0.002 < music_only < 0.02, music_only)          # the bed, quiet (ffmpeg's tone peaks at 1/8)
        self.assertGreater(self.peak_at(out, 1.9, 2.4), music_only * 3)  # the censor bonk over it
        self.assertGreater(self.peak_at(out, 4.95, 5.4), music_only * 3)  # the rule's bonk at 5 s

    def test_with_it_all_off_the_render_has_no_added_sound(self):
        out = os.path.join(self.tmp, "plain.mp4")
        render.make_short(self.ctx(), 0, 4, out, [], preset="ultrafast", name="A", log=lambda *_: None)
        self.assertLess(self.peak_at(out, 0, 4), 0.001)
        self.assertFalse(os.path.exists(os.path.join(self.outdir, "work", "sound-layer.wav")))

    def test_long_video_is_wide_joins_its_chapters_and_reuses_unchanged_ones(self):
        shorts = [dict(name="One", start=5.0, end=8.0), dict(name="Two", start=20.0, end=23.0), dict(name="Three", start=30.0, end=33.0)]
        ctx = self.ctx(shorts=shorts, long=dict(before=1, after=1, join=0, fade=0.1, title="Long test"))
        parts = longform.outline(ctx.cfg, ctx.moments, 40.0)
        self.assertEqual(len(parts), 3)
        lines = []
        out = longform.make(ctx, [], parts, log=lines.append, preset="ultrafast")
        self.assertEqual(os.path.basename(out), "Long test.mp4")
        self.assertEqual(self.size_of(out), (1920, 1080))
        import av
        with av.open(out) as c:
            self.assertAlmostEqual(c.duration / 1e6, 15.0, delta=0.4)
        with open(os.path.join(os.path.dirname(out), "chapters.txt")) as f:
            self.assertEqual(f.read().splitlines(), ["0:00 One", "0:05 Two", "0:10 Three"])
        lines.clear()
        longform.make(ctx, [], parts, log=lines.append, preset="ultrafast")
        self.assertEqual(sum("unchanged" in x for x in lines), 3)

    def test_premiere_gets_sound_effects_music_and_a_wide_long_timeline(self):
        music = soundlib.add(self.tone(seconds=3), "music", "m.mp3")["id"]
        ctx = self.ctx(shorts=[dict(name="One", start=5.0, end=10.0)], long=dict(before=0, after=0, join=0),
                       sfx=dict(on=True, rules=[rule(when="every", secs=1)], spacing=0, volume=1), bed=dict(on=True, tracks=[music]))
        ev = [(6.0, 7.0, "Main", "hello")]
        path = px.export(ctx, ev, [("One", 5.0, 10.0)], log=lambda *_: None)
        with open(path, encoding="utf-8") as f:
            xml = f.read()
        self.assertIn("Audio Levels", xml)
        self.assertIn("music.wav", xml)
        self.assertIn("SOUND: bonk", xml)
        self.assertTrue(os.path.exists(os.path.join(ctx.base + "_premiere", "sounds", "bonk.wav")))
        path = px.export_long(ctx, ev, longform.outline(ctx.cfg, ctx.moments, 40.0), log=lambda *_: None)
        with open(path, encoding="utf-8") as f:
            xml = f.read()
        self.assertIn("<width>1920</width><height>1080</height>", xml)
        self.assertIn("CHAPTER: One", xml)
        self.assertNotIn("Blurred background", xml)
        with open(os.path.join(ctx.base + "_premiere", "animated.txt"), encoding="utf-8") as f:
            self.assertEqual([x for x in f.read().splitlines() if not x.startswith("BIN\t")], [])   # no captions re-placed


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "Quick":
        sys.argv[1:] = ["QuickLibrary", "QuickRules", "QuickBed", "QuickStaleness", "QuickLong", "QuickXml"]
    unittest.main(verbosity=1)
