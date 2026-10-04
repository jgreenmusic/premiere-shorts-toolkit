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


if __name__ == "__main__":
    unittest.main()
