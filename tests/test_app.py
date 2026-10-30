"""Tests for the app as a whole: does every part still load, does the server answer, does a
video go in one end and a finished Short come out the other.

    .venv\\Scripts\\python.exe tests\\test_app.py           everything (about a minute)
    .venv\\Scripts\\python.exe tests\\test_app.py Quick     the fast ones only (a few seconds)

No Premiere and none of your projects are touched: the test video is made by ffmpeg in a
temporary folder, and the app's settings file is swapped for a temporary one.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app
import shorts

PY = sys.executable
MODULES = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "*.py")))


def cli(*argv, timeout=600):
    """Run shorts.py like the app does. Returns (exit code, output)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    r = subprocess.run([PY, os.path.join(ROOT, "shorts.py")] + list(argv), cwd=ROOT, env=env,
                       capture_output=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def commands():
    """The command names shorts.py accepts, read from its own help."""
    code, out = cli("-h")
    return set(re.search(r"\{([a-z,-]+)\}", out).group(1).split(","))


class Served:
    """The app's server on a spare port, with a throwaway settings file."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="shorts-toolkit-test-")
        cls.keep = (app.SETTINGS, app.ERROR_LOG)
        app.SETTINGS = os.path.join(cls.tmp, "settings.json")
        app.ERROR_LOG = os.path.join(cls.tmp, "errors.log")
        cls.server = app.make_server(0)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        app.SETTINGS, app.ERROR_LOG = cls.keep
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path, headers=None):
        """(status, headers, body bytes) - an error status is returned, not raised."""
        req = urllib.request.Request(self.url + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def json(self, path):
        code, _, body = self.get(path)
        return code, json.loads(body)


class QuickParts(unittest.TestCase):
    def test_every_module_loads(self):
        for m in MODULES:
            if m in ("desktop", "shorts_cli"):       # these start the app when imported as a program
                continue
            with self.subTest(module=m):
                __import__(m)

    def test_every_command_has_help(self):
        names = commands()
        self.assertIn("make", names)
        for name in sorted(names):
            with self.subTest(command=name):
                code, out = cli(name, "-h")
                self.assertEqual(code, 0, out)

    def test_version_is_the_same_everywhere(self):
        with open(os.path.join(ROOT, "packaging", "installer.iss"), encoding="utf-8") as f:
            iss = re.search(r'#define AppVersion "([^"]+)"', f.read()).group(1)
        self.assertEqual(iss, shorts.__version__, "packaging\\installer.iss and shorts.py disagree")
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            self.assertIn("## %s " % shorts.__version__, f.read(), "CHANGELOG.md has no entry for this version")

    def test_every_button_runs_a_real_command(self):
        """Each action the interface asks for must become a command shorts.py knows."""
        with open(os.path.join(ROOT, "ui", "index.html"), encoding="utf-8") as f:
            actions = set(re.findall(r'\brun\("([a-z-]+)"', f.read()))
        self.assertTrue(actions)
        names = commands()
        sample = dict(path="x.mp4", at=1, start=1, end=2, plan_file="p.json", video="v.mp4")
        for a in sorted(actions - {"quick"}):         # "quick" is markers, then make
            with self.subTest(action=a):
                self.assertIn(app.command(a, sample)[0], names)

    def test_documented_commands_exist(self):
        with open(os.path.join(ROOT, "docs", "commands.md"), encoding="utf-8") as f:
            documented = set(re.findall(r"^\| `([a-z-]+)[ `]", f.read(), flags=re.M)) - {"python"}
        names = commands()
        self.assertFalse(documented - names, "docs\\commands.md lists commands that do not exist")
        self.assertFalse(names - documented, "commands missing from docs\\commands.md")

    def test_premiere_scripts_have_no_es3_regex_error(self):
        """A '/' inside [...] in a regex is a syntax error in Premiere's script engine, and one
        such error stops the whole panel answering (0.11.4)."""
        bad = re.compile(r"/[^/\n]*\[[^\]\n]*(?<!\\)/[^\]\n]*\][^/\n]*/[gim]*\s*[,.;)]")
        for p in glob.glob(os.path.join(ROOT, "premiere", "**", "*.jsx"), recursive=True):
            with open(p, encoding="utf-8", errors="replace") as f:
                for n, line in enumerate(f, 1):
                    if line.lstrip().startswith(("//", "*")):
                        continue
                    self.assertIsNone(bad.search(line), "%s line %d" % (os.path.basename(p), n))


class QuickPremiereExport(unittest.TestCase):
    """Send to Premiere (0.34.0): the pieces that decide what lands on each track."""

    def test_caption_clips_join_the_steps_of_one_caption(self):
        import premiere_export as px
        ev = [(10.0, 10.4, "Main", r"{\fad(70,0)}{\1c&H00FF5C7B}Walk{\1c&H00FFFFFF} away"),   # highlight on word 1
              (10.4, 10.9, "Main", r"{\fscx100}Walk {\1c&H00FF5C7B}away{\1c&H00FFFFFF}"),        # ...then word 2
              (10.9, 11.5, "Main", r"{\fad(70,0)}Next line"),                                     # a new caption
              (12.0, 12.2, "Scream", r"{\frz1}AA"), (12.2, 12.5, "Scream", r"{\frz-1}AAAH"),      # a scream growing
              (30.0, 31.0, "Main", "after the Short")]
        clips = lambda a, b: [(round(s, 3), round(e, 3), t) for s, e, t in px.caption_clips(ev, a, b)]
        self.assertEqual(clips(9.0, 20.0),
                         [(1.0, 1.9, "Walk away"), (1.9, 2.5, "Next line"), (3.0, 3.5, "AAAH")])
        self.assertEqual(clips(10.5, 11.0), [(0.0, 0.4, "Walk away"), (0.4, 0.5, "Next line")])

    def test_sound_is_cut_around_each_censored_word(self):
        import premiere_export as px
        from types import SimpleNamespace
        from prproj import TICKS
        item = SimpleNamespace(start=0, end=100 * TICKS, path="r.mp4", src_in=0)
        got = [(round(t0, 2), round(t1, 2), cen) for _, t0, t1, cen in
               px.audio_pieces(SimpleNamespace(audio=[item]), 10.0, 20.0, [(2.0, 2.5), (9.8, 11.0)])]
        self.assertEqual(got, [(10.0, 12.0, False), (12.0, 12.5, True), (12.5, 19.8, False), (19.8, 20.0, True)])

    def test_a_file_premiere_holds_gets_a_new_name(self):
        import premiere_export as px
        d = tempfile.mkdtemp(prefix="shorts-premiere-test-")
        try:
            p = os.path.join(d, "captions.mov")
            for name, text in (("captions.mov", b"old"), ("a.part", b"new"), ("b.part", b"newer")):
                with open(os.path.join(d, name), "wb") as f:
                    f.write(text)
            with open(p, "rb"):                          # open without share-delete, like Premiere
                got = px.place(os.path.join(d, "a.part"), p)
            self.assertEqual(got, os.path.join(d, "captions 2.mov"))
            self.assertEqual(px.place(os.path.join(d, "b.part"), p), p)     # free again: the plain name
            with open(p, "rb") as f:
                self.assertEqual(f.read(), b"newer")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_xml_has_a_stereo_track_as_premiere_writes_it(self):
        import premiere_export as px
        import xml.etree.ElementTree as ET
        px._INFO["r.mp4"] = dict(w=3072, h=1728, fps="60/1", dur=100.0, channels=2, rate=48000)
        x = px.Xml(px.Rate("60/1"))
        seq = px.sequence(x, "S & 1", 5.0, [px.track([x.clip("r", "r.mp4", 0, 5, 10, scale=58.0)])],
                          x.sound([("r", "r.mp4", 0, 2, 10, True), ("censored", "r.mp4", 2, 2.5, 12, False)], 1))
        s = ET.fromstring(seq)
        self.assertEqual(s.findtext("name"), "S & 1")
        self.assertEqual(s.findtext("media/video/format/samplecharacteristics/width"), "1080")
        self.assertEqual(s.find("media/video/track/clipitem/filter/effect/parameter/value").text, "58.000")
        left, right = s.findall("media/audio/track")
        self.assertEqual([c.findtext("sourcetrack/trackindex") for c in left.findall("clipitem")], ["1", "1"])
        self.assertEqual([c.findtext("sourcetrack/trackindex") for c in right.findall("clipitem")], ["2", "2"])
        self.assertEqual([c.findtext("enabled") for c in left.findall("clipitem")], ["TRUE", "FALSE"])
        self.assertEqual(left.findall("clipitem")[1].findtext("start"), "120")          # 2 s at 60 fps
        pair = [l.findtext("linkclipref") for l in left.findall("clipitem")[1].findall("link")]
        self.assertEqual(pair, [left.findall("clipitem")[1].get("id"), right.findall("clipitem")[1].get("id")])
        self.assertEqual(len(s.findall(".//file[pathurl]")), 1)                       # the file in full once


class QuickPublish(unittest.TestCase):
    """Step 8: where each Short stands on YouTube. No network - the channel and queue are faked."""

    def state(self, uploads, jobs):
        import posting
        import youtube_step
        from types import SimpleNamespace
        keep = (posting.engine, posting.show)
        posting.engine = lambda: {"publish": SimpleNamespace(jobs=lambda: jobs, DONE=("posted", "scheduled_on_platform"))}
        posting.show = lambda files: []
        try:
            shorts_ = [(i, {"name": "Short %d" % i}, r"C:\x_shorts\Short %d.mp4" % i) for i in range(4)]
            return [r["youtube"] for r in youtube_step.state("x.prproj", shorts_, None, uploads)]
        finally:
            posting.engine, posting.show = keep

    def test_status_of_each_short(self):
        video = lambda id, **k: dict(dict(id=id, title="t", file_name="", privacy="private", publish_at=None, unfinished=False), **k)
        job = lambda i, status, id=None: dict(platform="youtube_shorts", file=r"C:\x_shorts\Short %d.mp4" % i, id="j%d" % i,
                                              status=status, when="2026-10-29T19:00:00Z", result={"id": id} if id else None)
        uploads = [video("drafted", file_name="Short 0.mp4", unfinished=True),      # a draft uploaded by hand in Studio
                   video("sent1", publish_at="2026-10-29T19:00:00Z"),                # uploaded by the toolkit: no file name
                   video("sent2", privacy="public")]
        jobs = [job(1, "scheduled_on_platform", "sent1"), job(2, "scheduled_on_platform", "sent2"), job(3, "scheduled")]
        self.assertEqual(self.state(uploads, jobs), ["draft", "scheduled", "public", "queued"])
        # uploaded, but the channel list doesn't show it (yet): never "uploading", never uploaded twice
        self.assertEqual(self.state([], jobs[:1])[1], "sent")
        self.assertEqual(self.state([], [])[1], "not_uploaded")
        self.assertEqual(self.state(None, [])[1], "unknown")


class QuickServer(Served, unittest.TestCase):
    def test_page_and_state(self):
        code, _, body = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"Shorts Toolkit", body)
        code, d = self.json("/api/state")
        self.assertEqual(d["version"], shorts.__version__)
        self.assertFalse(d["remote"])
        self.assertIn("cut-at-markers.jsx", d["scripts"])

    def test_job_and_copy_log(self):
        code, d = self.json("/api/job")
        self.assertTrue(d["done"])
        code, d = self.json("/api/diag")
        self.assertIn("Shorts Toolkit %s" % shorts.__version__, d["text"])
        self.assertNotIn(os.path.expanduser("~"), d["text"])      # the Windows user name stays out

    def test_looks_and_fonts(self):
        code, d = self.json("/api/look-options")
        self.assertGreaterEqual(len(d["presets"]), 12)
        self.assertTrue(d["fonts"])
        from urllib.parse import quote
        served = 0
        for name in d["fonts"]:
            code, headers, body = self.get("/font?name=" + quote(name))
            if code == 200:
                served += 1
                self.assertGreater(len(body), 1000, name)
        self.assertGreater(served, 0)
        self.assertEqual(self.get("/font?name=nope")[0], 404)

    def test_unknown_address(self):
        self.assertEqual(self.get("/api/nope")[0], 404)

    def test_only_toolkit_media_is_served(self):
        secret = os.path.join(self.tmp, "private.mp4")
        with open(secret, "wb") as f:
            f.write(b"x" * 10)
        from urllib.parse import quote
        self.assertEqual(self.get("/media?path=" + quote(secret))[0], 403)
        self.assertEqual(self.get("/media?path=" + quote(app.SETTINGS))[0], 403)

    def test_video_byte_ranges(self):
        """What a phone's player asks for (0.24.1)."""
        from urllib.parse import quote
        folder = os.path.join(self.tmp, "x_shorts")
        os.makedirs(folder, exist_ok=True)
        data = bytes(range(256)) * 4
        p = os.path.join(folder, "a.mp4")
        with open(p, "wb") as f:
            f.write(data)
        u = "/media?path=" + quote(p)
        code, h, body = self.get(u)
        self.assertEqual((code, body), (200, data))
        code, h, body = self.get(u, {"Range": "bytes=10-19"})
        self.assertEqual((code, body), (206, data[10:20]))
        self.assertEqual(h["Content-Range"], "bytes 10-19/%d" % len(data))
        code, h, body = self.get(u, {"Range": "bytes=-16"})                 # the last 16 bytes
        self.assertEqual((code, body), (206, data[-16:]))
        code, h, body = self.get(u, {"Range": "bytes=1000-99999"})          # runs past the end
        self.assertEqual((code, body), (206, data[1000:]))
        self.assertEqual(self.get(u, {"Range": "bytes=5000-"})[0], 416)     # wholly past the end

    def test_render_replaces_a_video_the_player_is_streaming(self):
        """0.33.0: Re-render failed with "Access is denied" because the player still had the old
        video open through /media. A stalled stream must not stop the new render going in."""
        import socket
        import time
        import render
        from urllib.parse import quote
        folder = os.path.join(self.tmp, "y_shorts")
        os.makedirs(folder, exist_ok=True)
        p, part = os.path.join(folder, "Short 01.mp4"), os.path.join(folder, "Short 01.part.mp4")
        with open(p, "wb") as f:
            f.write(b"o" * (8 << 20))                # big enough that the server can't send it all at once
        with open(part, "wb") as f:
            f.write(b"new")
        port = self.server.server_address[1]
        s = socket.create_connection(("127.0.0.1", port))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        s.sendall(("GET /media?path=%s HTTP/1.1\r\nHost: x\r\n\r\n" % quote(p)).encode())
        s.recv(1024)                                 # the stream has started; now stop reading, like a paused player
        time.sleep(0.5)
        try:
            render.put_in_place(part, p, wait=2)
            with open(p, "rb") as f:
                self.assertEqual(f.read(), b"new")
            self.assertFalse(os.path.exists(part))
        finally:
            s.close()
        for _ in range(20):                          # the moved-aside old one goes once the server lets go
            if not glob.glob(os.path.join(folder, "*.old.part.mp4")):
                break
            time.sleep(0.25)
        self.assertEqual(sorted(os.listdir(folder)), ["Short 01.mp4"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg and ffprobe on PATH")
class WholeRun(Served, unittest.TestCase):
    """A video file in, a finished vertical Short out - the same commands the buttons run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clip = os.path.join(cls.tmp, "recording.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440", "-t", "12", "-pix_fmt", "yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", cls.clip], check=True)

    def test_clip_to_finished_short(self):
        from urllib.parse import quote
        q = "?path=" + quote(self.clip)

        code, out = cli("shorts", self.clip, "--add", "0:02", "0:08", "--name", "Test short")
        self.assertEqual(code, 0, out)

        code, info = self.json("/api/info" + q)
        self.assertEqual(code, 200, info)
        self.assertTrue(info["clip"])
        self.assertEqual([s["name"] for s in info["config"]["shorts"]], ["Test short"])
        self.assertAlmostEqual(info["sequences"][0]["seconds"], 12, delta=0.5)

        code, out = cli("make", self.clip, "--preset", "ultrafast")
        self.assertEqual(code, 0, out)
        made = glob.glob(os.path.join(info["shorts_dir"], "*.mp4"))
        self.assertEqual(len(made), 1, out)
        self.assertFalse(made[0].endswith(".part.mp4"))
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
             "-of", "json", made[0]], capture_output=True, check=True).stdout)
        video = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
        self.assertEqual((video["width"], video["height"]), (1080, 1920))
        self.assertTrue(any(s["codec_type"] == "audio" for s in probe["streams"]))
        self.assertAlmostEqual(float(probe["format"]["duration"]), 6, delta=0.3)

        code, caps = self.json("/api/captions" + q + "&start=2&end=8")      # a tone has no words: must not fail
        self.assertEqual(code, 200, caps)
        code, h, body = self.get("/media?path=" + quote(made[0]), {"Range": "bytes=0-99"})
        self.assertEqual((code, len(body)), (206, 100))

        # the same Short sent to Premiere: a timeline file + its own media (Premiere itself not needed)
        import xml.etree.ElementTree as ET
        code, out = cli("to-premiere", self.clip)
        self.assertEqual(code, 0, out)
        folder = info["premiere_dir"]
        with open(os.path.join(folder, "import.txt"), encoding="utf-8") as f:
            listed = f.read().splitlines()
        seq = ET.parse(os.path.join(folder, "Test short.xml")).getroot().find("bin/children/sequence")
        self.assertEqual(seq.findtext("name"), "Test short")
        self.assertEqual(int(seq.findtext("duration")), 180)                    # 6 s at 30 fps
        files = [urllib.request.url2pathname(u.text[len("file://localhost/"):]) for u in seq.iter("pathurl")]
        self.assertTrue(all(os.path.exists(p) for p in files), files)
        bg = os.path.join(folder, "Test short", "background.mp4")
        self.assertIn(os.path.normcase(bg), [os.path.normcase(p) for p in files])
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,sample_aspect_ratio",
                                           "-of", "json", bg], capture_output=True, check=True).stdout)["streams"][0]
        self.assertEqual((probe["width"], probe["height"], probe.get("sample_aspect_ratio", "1:1")), (1080, 1920, "1:1"))
        self.assertEqual(len(seq.findall("media/audio/track")), 2)            # the recording's sound, left + right
        self.assertEqual(listed[0], os.path.join(folder, "Test short.xml"))


if __name__ == "__main__":
    unittest.main()
