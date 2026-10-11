"""Tests for Shorts Auto Run (autorun.py), for knowing which Shorts changed since they were
rendered (stale.py), and for the two windows knowing about each other (peer.py).

    .venv\\Scripts\\python.exe tests\\test_autorun.py           everything (about twenty seconds)
    .venv\\Scripts\\python.exe tests\\test_autorun.py Quick     the fast ones only

Nothing of yours is touched and nothing is ever sent to YouTube: the recording is made-up music
in a temporary folder, the settings file is a temporary one, and the publish step is a stand-in.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np

import app
import autorun
import captions
import config
import peer
import stale
from prproj import TICKS

PY = sys.executable
SR = captions.RATE


class Sandbox:
    """Throwaway settings and a throwaway place for the "who is open" files."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="shorts-autorun-test-")
        cls.keep = (app.SETTINGS, app.ERROR_LOG, peer.DIR, app.ME)
        app.SETTINGS = os.path.join(cls.tmp, "settings.json")
        app.ERROR_LOG = os.path.join(cls.tmp, "errors.log")
        peer.DIR = os.path.join(cls.tmp, "open")
        app.ME = "autorun"

    @classmethod
    def tearDownClass(cls):
        app.SETTINGS, app.ERROR_LOG, peer.DIR, app.ME = cls.keep
        shutil.rmtree(cls.tmp, ignore_errors=True)


def seq_with(captions_=(), clips=((0, 600),)):
    """A sequence as prproj.py reads it, small enough to write by hand (times in seconds)."""
    item = lambda a, b: SimpleNamespace(track=0, start=int(a * TICKS), end=int(b * TICKS), src_in=0, path=r"C:\x\rec.mp4")
    cap = lambda a, b, text: SimpleNamespace(start=int(a * TICKS), end=int(b * TICKS), text=text)
    return SimpleNamespace(name="Seq", video=[item(*c) for c in clips], audio=[item(*c) for c in clips],
                           captions=[cap(*c) for c in captions_])


class QuickStale(unittest.TestCase):
    """Which Shorts changed since they were rendered, and why."""

    def setUp(self):
        self.cfg = config.load(os.path.join(tempfile.gettempdir(), "no-such-folder"))
        self.short = dict(name="Short 01", start=100.0, end=120.0)
        self.seq = seq_with([(101, 103, "hello there"), (300, 302, "far away")])

    def changed(self, cfg=None, short=None, seq=None):
        was = stale.parts(self.cfg, self.short, self.seq)
        now = stale.parts(cfg or self.cfg, short or self.short, seq or self.seq)
        return sorted(k for k in was if was[k] != now[k])

    def patched(self, **patch):
        return config._merge(self.cfg, patch)

    def test_nothing_changed(self):
        self.assertEqual(self.changed(), [])

    def test_trim(self):
        self.assertEqual(self.changed(short=dict(self.short, end=118.0)), ["trim"])

    def test_a_caption_fix_inside_the_short(self):
        self.assertEqual(self.changed(self.patched(caption_edits={"101.00": {"text": "hello THERE"}})), ["captions"])
        self.assertEqual(self.changed(self.patched(caption_adds=[dict(start=110, end=112, text="added")])), ["captions"])

    def test_a_caption_fix_somewhere_else_changes_nothing(self):
        self.assertEqual(self.changed(self.patched(caption_edits={"300.00": {"text": "FAR away"}})), [])
        self.assertEqual(self.changed(self.patched(caption_adds=[dict(start=400, end=402, text="added")])), [])

    def test_screams_and_laughs(self):
        self.assertEqual(self.changed(self.patched(screams={"off": [105.2]})), ["reactions"])
        self.assertEqual(self.changed(self.patched(laughs={"on": [111.0]})), ["reactions"])
        self.assertEqual(self.changed(self.patched(screams={"off": [505.2]})), [])

    def test_look_touches_every_short(self):
        self.assertEqual(self.changed(self.patched(look={"size": 90})), ["look"])
        self.assertEqual(self.changed(self.patched(layout={"blur_trim": 0.5})), ["look"])

    def test_the_premiere_timeline(self):
        self.assertEqual(self.changed(seq=seq_with([(101, 103, "hello you"), (300, 302, "far away")])), ["timeline"])
        self.assertEqual(self.changed(seq=seq_with([(101, 103, "hello there"), (300, 302, "FAR away")])), [])
        self.assertEqual(self.changed(seq=seq_with([(101, 103, "hello there"), (300, 302, "far away")], clips=((0, 110), (110, 600)))), ["timeline"])

    def test_record_and_status(self):
        tmp = tempfile.mkdtemp(prefix="shorts-stale-test-")
        try:
            video = os.path.join(tmp, "Short 01.mp4")
            st = stale.status(self.cfg, self.short, video, self.seq, stale.load(tmp))
            self.assertFalse(st["rendered"])
            with open(video, "wb") as f:
                f.write(b"x")
            st = stale.status(self.cfg, self.short, video, self.seq, stale.load(tmp))
            self.assertEqual((st["rendered"], st["known"], st["changed"]), (True, False, []))     # rendered by an older version
            stale.record(tmp, "Short 01", stale.parts(self.cfg, self.short, self.seq))
            st = stale.status(self.cfg, self.short, video, self.seq, stale.load(tmp))
            self.assertEqual((st["known"], st["changed"]), (True, []))
            st = stale.status(self.patched(look={"size": 90}), dict(self.short, start=99.0), video, self.seq, stale.load(tmp))
            self.assertEqual(st["changed"], ["trim", "look"])
            self.assertEqual(st["why"], ["start or end moved", "look or layout changed"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class QuickPeer(Sandbox, unittest.TestCase):
    """The toolkit and Auto Run never run a job at the same time."""

    def other_program(self, who, job):
        code = ("import sys, time; sys.path.insert(0, %r); import peer; peer.DIR = %r; "
                "peer.announce(%r, 1); peer.set_job(%r, %r); print('up', flush=True); time.sleep(60)") % (ROOT, peer.DIR, who, who, job)
        p = subprocess.Popen([PY, "-c", code], stdout=subprocess.PIPE)
        p.stdout.readline()
        return p

    def test_the_other_program_is_seen_while_it_runs(self):
        import psutil
        self.assertIsNone(peer.read("toolkit"))
        p = self.other_program("toolkit", "Rendering 3 Shorts")
        real = peer.read("toolkit")["pid"]               # not p.pid: a venv's python.exe starts the real one
        try:
            self.assertEqual(peer.busy_with("autorun"), "Rendering 3 Shorts")
            self.assertIsNone(app.run_job("should not start", ["shorts", "x.mp4"]))        # refused: the toolkit is working
            self.assertIn("Shorts Toolkit is busy (Rendering 3 Shorts)", app.busy_message())
            with self.assertRaises(ValueError):
                autorun._free("x.mp4")
        finally:
            for pid in (real, p.pid):
                try:
                    psutil.Process(pid).kill()
                except psutil.NoSuchProcess:
                    pass
            p.wait()
            p.stdout.close()
            psutil.wait_procs([psutil.Process(real)] if psutil.pid_exists(real) else [], timeout=5)
        self.assertIsNone(peer.read("toolkit"), "a file left by a program that has gone must be ignored")
        self.assertIsNone(peer.busy_with("autorun"))

    def test_this_program_does_not_see_itself(self):
        peer.announce("autorun", 1)
        peer.set_job("autorun", "an auto run")
        self.assertIsNone(peer.read("autorun"))
        peer.gone("autorun")
        self.assertFalse(os.path.exists(peer._path("autorun")))


class QuickPages(Sandbox, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = autorun.make_server(0)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def ask(self, path, body=None, headers=None):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=dict({"Content-Type": "application/json"}, **(headers or {})))
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_both_pages_are_served(self):
        code, body = self.ask("/auto")
        self.assertEqual(code, 200)
        self.assertIn(b"Shorts Auto Run", body)
        code, body = self.ask("/")                       # the toolkit's own page, shown inside Auto Run for editing a step
        self.assertEqual(code, 200)
        self.assertIn(b"Shorts Toolkit", body)

    def test_only_the_apps_own_page_may_start_things(self):
        self.assertEqual(self.ask("/api/auto/start", dict(path="x.mp4"))[0], 403)
        self.assertEqual(self.ask("/api/auto/publish", dict(path="x.mp4"))[0], 403)
        self.assertEqual(self.ask("/api/auto/nope", {}, {"X-Shorts-Toolkit": "1"})[0], 404)

    def test_every_address_the_page_uses_exists(self):
        import re
        with open(os.path.join(ROOT, "ui", "auto.html"), encoding="utf-8") as f:
            page = f.read()
        with open(os.path.join(ROOT, "autorun.py"), encoding="utf-8") as f:
            mine = f.read()
        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as f:
            base = f.read()
        used = set(re.findall(r'"(/api/[a-z/-]+)', page))
        self.assertIn("/api/auto/start", used)
        for a in sorted(used):
            with self.subTest(address=a):
                self.assertIn('"%s"' % a, mine if a.startswith("/api/auto/") else base)

    def test_each_stage_is_a_toolkit_step(self):
        """Edit opens the toolkit's tab of the same name."""
        with open(os.path.join(ROOT, "ui", "index.html"), encoding="utf-8") as f:
            page = f.read()
        for sid in autorun.ORDER:
            self.assertIn('["%s", "' % sid, page)
            self.assertIn(sid, app.STEPS)
        self.assertIn('id="autoBtn"', page)
        self.assertIn("window.gotoProject", page)


def clicks(seconds, bpm, level=0.5):
    t = np.arange(int(seconds * SR)) / SR
    return (level * np.sin(2 * np.pi * 220 * t) * np.exp(-np.mod(t, 60.0 / bpm) * 30)).astype(np.float32)


@unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg on PATH")
class WholeAutoRun(Sandbox, unittest.TestCase):
    """A music recording in; every step done; review, sign-off, an edit carried through; and the
    last sign-off - with a stand-in where YouTube would be."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clip = os.path.join(cls.tmp, "set.mp4")
        raw = os.path.join(cls.tmp, "set.f32")
        np.concatenate([clicks(12, 120, 0.12), clicks(40, 120), np.zeros(2 * SR, np.float32), clicks(40, 100)]).tofile(raw)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                        "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", raw, "-shortest", "-pix_fmt", "yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", cls.clip], check=True)
        cls.outdir = os.path.join(cls.tmp, "set_captions")
        config.update(cls.outdir, {"kind": "music"})
        cls.real_plan = autorun.make_plan
        cls.plans = []

        def plan(path, I, run):
            """Where YouTube would be asked: every Short of the run is ready to upload."""
            day = 1 + len(cls.plans) if cls.shift else 1
            rows = [dict(i=i, name=s["name"], action="upload", why="", when="2031-01-%02dT19:00:00Z" % (day + n), title="a title",
                         youtube="not_uploaded", problems=[]) for n, (i, s, v) in enumerate(autorun.scope(I, run))]
            cls.plans.append(rows)
            slim = dict(when=time.time(), rows=rows, error=None, account=dict(connected=True, who="test channel"), label="12:00 PM",
                        ready=len(rows), visibility="schedule")
            return slim, [dict(r, fields={}) for r in rows], dict(settings={}, visibility="schedule")
        cls.shift = False
        autorun.make_plan = plan

    @classmethod
    def tearDownClass(cls):
        autorun.make_plan = cls.real_plan
        super().tearDownClass()

    def wait(self):
        for _ in range(600):
            s = autorun.state(self.clip)
            if s["run"]["status"] != "running" and s["job"]["done"] and not autorun.ACTIVE["path"]:
                return s
            time.sleep(0.2)
        self.fail("the run never finished: %s" % json.dumps(autorun.state(self.clip)["stages"]))

    def stage(self, s, sid):
        return next(x for x in s["stages"] if x["id"] == sid)

    def test_run_review_edit_and_sign_off(self):
        o = autorun.options(self.clip)
        self.assertEqual((o["kind"], o["defaults"]["min"], o["defaults"]["max"]), ("music", 20, 45))

        # -- the run
        autorun.start(self.clip, dict(count=2, min=10, max=20, preset="ultrafast", posts=False))
        with self.assertRaises(ValueError):
            autorun.start(self.clip, {})                 # one run at a time
        s = self.wait()
        self.assertEqual(s["run"]["status"], "review", s["stages"])
        states = {x["id"]: x["state"] for x in s["stages"]}
        self.assertEqual(states, dict(markers="done", captions="na", shorts="done", screams="na", look="done", render="done",
                                      post="skipped", publish="ready"), s["stages"])
        self.assertFalse(self.stage(s, "captions")["applies"])          # music: no captions, no screams & laughs
        self.assertEqual(s["run"]["count"], 2)
        self.assertEqual(s["pending"], dict(render=[], post=[]))
        r = autorun.review(self.clip)
        self.assertEqual(len(r["shorts"]), 2)
        for x in r["shorts"]:
            self.assertTrue(x["rendered"] and x["known"] and x["new"], x)
            self.assertEqual(x["changed"], [])
            self.assertTrue(os.path.exists(x["video"]))
        self.assertEqual(r["plan"]["ready"], 2)

        # -- nothing goes out unsigned
        with self.assertRaises(ValueError) as e:
            autorun.publish(self.clip)
        self.assertIn("Sign off first", str(e.exception))
        s = autorun.sign(self.clip, "all")
        self.assertTrue(all(x["signed"] for x in s["stages"] if x["sign"]))
        self.assertFalse(self.stage(s, "post")["sign"])                 # a skipped step has nothing to sign
        self.assertFalse(self.stage(s, "publish")["sign"])              # pressing Publish is its sign-off

        # -- an edit, made the way the toolkit saves it
        cfg = config.load(self.outdir)
        first = cfg["shorts"][0]["name"]
        cfg["shorts"][0]["end"] = round(cfg["shorts"][0]["end"] - 2, 3)
        config.update(self.outdir, {"shorts": cfg["shorts"]})
        s = autorun.state(self.clip)
        self.assertEqual([(x["name"], x["why"]) for x in s["pending"]["render"]], [(first, ["start or end moved"])])
        self.assertTrue(self.stage(s, "shorts")["changed"] and not self.stage(s, "shorts")["signed"])
        self.assertTrue(self.stage(s, "look")["signed"])                # what you didn't touch stays signed
        with self.assertRaises(ValueError) as e:
            autorun.publish(self.clip)
        self.assertIn("Sign off first", str(e.exception))
        autorun.sign(self.clip, "all")
        with self.assertRaises(ValueError) as e:
            autorun.publish(self.clip)
        self.assertIn("Apply my edits", str(e.exception))

        # -- carried through: only that Short is rendered again
        before = {x["name"]: x["when"] for x in autorun.review(self.clip)["shorts"]}
        time.sleep(1.1)
        autorun.apply_edits(self.clip)
        s = self.wait()
        self.assertEqual(s["run"]["status"], "review")
        self.assertEqual(s["pending"], dict(render=[], post=[]))
        after = {x["name"]: x["when"] for x in autorun.review(self.clip)["shorts"]}
        self.assertGreater(after[first], before[first])
        self.assertEqual([n for n in after if after[n] == before[n]], [n for n in after if n != first])
        self.assertTrue(self.stage(s, "render")["changed"])             # new video: look at it again

        # -- the last sign-off, with a stand-in for the upload
        autorun.sign(self.clip, "all")
        sent = []
        keep = app.run_job

        def stand_in(title, argv, after=None):
            sent.append((title, argv))
            after(0)
            return 1
        app.run_job = stand_in
        try:
            type(self).shift = True                      # the channel moved on since the plan was looked at
            self.assertEqual(autorun.publish(self.clip), dict(changed=True))
            self.assertEqual(sent, [], "a plan that changed must not be sent")
            type(self).shift = False
            autorun.refresh_plan(self.clip)              # Check again -> look -> publish
            res = autorun.publish(self.clip)
            self.assertEqual(res["count"], 2)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0][1][0], "publish")
            with open(sent[0][1][sent[0][1].index("--plan") + 1], encoding="utf-8") as f:
                self.assertEqual([x["action"] for x in json.load(f)["rows"]], ["upload", "upload"])
        finally:
            app.run_job = keep
            type(self).shift = False
        s = autorun.state(self.clip)
        self.assertEqual(s["run"]["status"], "published")
        self.assertEqual(self.stage(s, "publish")["state"], "done")

        # -- a second run leaves the first run's Shorts alone unless asked - and the Short that was
        #    trimmed does not come back as a second Short made from its old marker
        autorun.start(self.clip, dict(count=1, min=10, max=20, preset="ultrafast", posts=False))
        s = self.wait()
        self.assertEqual(s["run"]["status"], "review", s["stages"])
        self.assertEqual(s["run"]["count"], 1)
        names = [x["name"] for x in config.load(self.outdir)["shorts"]]
        self.assertEqual(len(names), 3, names)
        self.assertEqual(len(set(names)), 3, names)


if __name__ == "__main__":
    unittest.main()
