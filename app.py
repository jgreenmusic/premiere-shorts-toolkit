"""Shorts Toolkit app - a local web UI over shorts.py.

    .venv\\Scripts\\pythonw app.py      (or double-click "Shorts Toolkit.cmd")

Runs only on this PC (127.0.0.1). Opens in your browser. Every button runs the same
shorts.py command you could type yourself; the log panel shows its output.
The server closes itself a minute after the browser tab is closed.
"""
import csv
import glob
import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)                 # running as the installed app
RES = getattr(sys, "_MEIPASS", HERE)                   # bundled files (ui, fonts, scripts, models)
APPDIR = os.path.dirname(sys.executable) if FROZEN else HERE
PORT = 8765
PY = sys.executable.replace("pythonw.exe", "python.exe")
SETTINGS = os.path.join(os.path.expanduser("~"), ".shorts-toolkit.json")
DEFAULT_DIRS = [os.path.join(os.path.expanduser("~"), "Desktop", "Projects")]

sys.path.insert(0, HERE)
from shorts import __version__  # noqa: E402


# -- settings (remembered folders) ------------------------------------------------
def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"dirs": DEFAULT_DIRS}


def save_settings(s):
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


# -- project discovery + outputs -------------------------------------------------------
SYNCED = re.compile(r"_captions-synced(?:-v(\d+))?$")


def base_of(path):
    return SYNCED.sub("", os.path.splitext(path)[0])


def list_projects():
    seen, out = set(), []
    for d in load_settings().get("dirs", DEFAULT_DIRS):
        for p in glob.glob(os.path.join(d, "*.prproj")):
            p = os.path.normpath(p)
            if p in seen:
                continue
            seen.add(p)
            stem = os.path.splitext(os.path.basename(p))[0]
            m = SYNCED.search(stem)
            out.append(dict(path=p, name=stem, base=os.path.basename(base_of(p)),
                            version=("synced v%s" % (m.group(1) or "1")) if m else "original",
                            modified=os.path.getmtime(p)))
    out.sort(key=lambda x: -x["modified"])
    return out


_proj_cache = {}


def project(path):
    """Parsed project, cached until the file changes."""
    key = (path, os.path.getmtime(path))
    if key not in _proj_cache:
        from prproj import Project
        _proj_cache.clear()
        _proj_cache[key] = Project(path).sequences()
    return _proj_cache[key]


def pick(seqs, cfg):
    import pipeline
    if not seqs:
        raise pipeline.ProjectError("This project has no sequences yet - add your footage to a timeline in Premiere and save.")
    name = cfg.get("sequence")
    for s in seqs:
        if s.name == name:
            return s
    return pipeline.pick_sequence(type("P", (), {"sequences": lambda self: seqs})())


def project_info(path):
    import config
    outdir = base_of(path) + "_captions"
    cfg = config.load(outdir)
    seqs = project(path)
    cur = pick(seqs, cfg)
    return dict(path=path, outdir=outdir, shorts_dir=base_of(path) + "_shorts", config=cfg,
                sequence=cur.name,
                sequences=[dict(name=s.name, captions=len(s.captions), video=len(s.video), audio=len(s.audio),
                                markers=len(s.markers), seconds=round(s.end_s, 1)) for s in seqs],
                results=results(outdir, base_of(path) + "_shorts", cfg))


def marker_segments(path):
    import config
    cfg = config.load(base_of(path) + "_captions")
    seq = pick(project(path), cfg)
    have = {(round(s["start"], 1), round(s["end"], 1)) for s in cfg["shorts"]}
    seg = lambda a, b, name, kind: dict(start=round(a, 3), end=round(b, 3), seconds=round(b - a, 1), name=name,
                                        kind=kind, added=(round(a, 1), round(b, 1)) in have)
    # range markers (made in Premiere, or by shorts-to-markers.jsx) are Shorts already
    ranges = [seg(m.start_s, m.start_s + m.dur_s, m.name.replace("Short: ", ""), "range")
              for m in seq.markers if m.dur_s > 0.5]
    cuts = [m.start_s for m in seq.markers if m.dur_s <= 0.5] + [seq.end_s]
    between = [seg(a, b, "", "between") for a, b in zip(cuts, cuts[1:]) if b - a >= 1]
    return ranges + between


def results(outdir, shorts_dir, cfg):
    r = {}
    rep = os.path.join(outdir, "caption-report.csv")
    if os.path.exists(rep):
        counts, total = {}, 0
        with open(rep, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                total += 1
                for s in row["status"].split("+"):
                    counts[s] = counts.get(s, 0) + 1
        drift = []
        txt = os.path.join(outdir, "caption-report.txt")
        if os.path.exists(txt):
            for line in open(txt, encoding="utf-8"):
                m = re.match(r"\s+(\d+:\d\d:\d\d)\s+([+-]\d+\.\d+)s", line)
                if m:
                    drift.append([m.group(1), float(m.group(2))])
        of = ""
        lc = os.path.join(outdir, "last-check.txt")
        if os.path.exists(lc):
            m = SYNCED.search(os.path.splitext(open(lc, encoding="utf-8").read().strip())[0])
            of = ("synced v%s" % (m.group(1) or "1")) if m else "original"
        r["check"] = dict(total=total, counts=counts, drift=drift, when=os.path.getmtime(rep), of=of)
    sj = os.path.join(outdir, "screams.json")
    if os.path.exists(sj):
        with open(sj, encoding="utf-8") as f:
            items = json.load(f)
        r["screams"] = dict(items=items, srt=os.path.join(outdir, "captions-with-screams.srt"),
                            when=os.path.getmtime(sj),
                            stale=os.path.getmtime(os.path.join(outdir, "toolkit.json")) > os.path.getmtime(sj)
                            if os.path.exists(os.path.join(outdir, "toolkit.json")) else False)
    lj = os.path.join(outdir, "laughs.json")
    if os.path.exists(lj):
        with open(lj, encoding="utf-8") as f:
            items = json.load(f)
        r["laughs"] = dict(items=items, installed=items is not None, when=os.path.getmtime(lj))
    short = os.path.join(outdir, "too-short-captions.txt")
    if os.path.exists(short):
        r["too_short"] = max(0, sum(1 for _ in open(short, encoding="utf-8")) - 3)
    em = os.path.join(outdir, "premiere-emphasis.csv")
    if os.path.exists(em):
        kinds = {}
        with open(em, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        r["prepare"] = dict(loud=kinds.get("loud", 0), scream=kinds.get("scream", 0), when=os.path.getmtime(em))
    r["previews"] = sorted((os.path.basename(p) for p in glob.glob(os.path.join(outdir, "preview-*.mp4"))),
                           key=lambda n: -os.path.getmtime(os.path.join(outdir, n)))
    from shorts import safe_name
    r["renders"] = {}
    for s in cfg.get("shorts", []):
        f = os.path.join(shorts_dir, safe_name(s["name"]) + ".mp4")
        if os.path.exists(f):
            r["renders"][s["name"]] = dict(path=f, when=os.path.getmtime(f))
    return r


# -- jobs ------------------------------------------------------------------------------
JOB = {"id": 0, "lines": [], "done": True, "code": None, "title": "", "started": 0}
LOCK = threading.Lock()


def command(action, o):
    p = o["path"]
    if action == "check":
        return ["captions", p]
    if action == "fix":
        return ["captions", p, "--fix"]
    if action == "screams":
        return ["screams", p]
    if action == "prepare":
        return ["prepare", p]
    if action == "preview":
        return ["style", p, "--preview", str(o["at"]), "--seconds", str(o.get("seconds", 10))]
    if action == "make":
        c = ["make", p, "--preset", o.get("preset", "medium")]
        return c + (["--index", str(int(o["index"]))] if o.get("index") is not None else [])
    if action == "timeline":
        return ["timeline", p, "--count", str(int(o.get("count", 12))), "--min", str(o.get("min", 20)),
                "--max", str(o.get("max", 45))]
    if action == "burn":
        return ["style", p, "--video", o["video"], "--start", str(o.get("start") or "0")]
    raise ValueError("unknown action %s" % action)


def run_job(title, argv):
    with LOCK:
        if not JOB["done"]:
            return None
        JOB.update(id=JOB["id"] + 1, lines=["$ shorts.py " + " ".join(argv)],
                   done=False, code=None, title=title, started=time.time())
        jid = JOB["id"]

    def work():
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        # the installed app ships a console twin, shorts-cli.exe; from source we run shorts.py
        cmd = [os.path.join(APPDIR, "shorts-cli.exe")] if FROZEN else [PY, os.path.join(HERE, "shorts.py")]
        proc = subprocess.Popen(cmd + argv, cwd=APPDIR, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        buf = b""
        while True:
            ch = proc.stdout.read(1)
            if not ch:
                break
            if ch in (b"\n", b"\r"):
                if buf.strip():
                    line = buf.decode("utf-8", "replace")
                    with LOCK:
                        # ffmpeg progress rewrites one line: keep only the latest
                        if line.startswith("frame=") and JOB["lines"] and JOB["lines"][-1].startswith("frame="):
                            JOB["lines"][-1] = line
                        else:
                            JOB["lines"].append(line)
                buf = b""
            else:
                buf += ch
        proc.wait()
        with LOCK:
            JOB.update(done=True, code=proc.returncode)

    threading.Thread(target=work, daemon=True).start()
    return jid


def make_snippet(path, a, b):
    """mp3 of the timeline audio around a scream candidate (0.5 s either side)."""
    import config
    import render
    from types import SimpleNamespace
    outdir = base_of(path) + "_captions"
    seq = pick(project(path), config.load(outdir))
    d = os.path.join(outdir, "snippets")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "%.2f-%.2f.mp3" % (a, b))
    if not os.path.exists(out):
        render.snippet(SimpleNamespace(seq=seq), max(0, a - 0.5), b + 0.5, out)
    return out


# -- native file dialog --------------------------------------------------------------------
DIALOG = None          # set by desktop.py: native dialogs from the app window


def browse(kind):
    if DIALOG:
        return DIALOG(kind)
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    if kind == "project":
        p = filedialog.askopenfilename(title="Choose a Premiere project",
                                       filetypes=[("Premiere project", "*.prproj")])
    elif kind == "video":
        p = filedialog.askopenfilename(title="Choose the video you exported from Premiere",
                                       filetypes=[("Video", "*.mp4 *.mov *.mkv"), ("All files", "*.*")])
    else:
        p = filedialog.askdirectory(title="Choose a folder with Premiere projects")
    root.destroy()
    return os.path.normpath(p) if p else None


def open_path(path, how):
    if how == "vscode":
        subprocess.Popen(["cmd", "/c", "code", path], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    elif how == "folder":
        subprocess.Popen(["explorer", "/select,", path] if os.path.isfile(path) else ["explorer", path])
    else:
        os.startfile(path)


# -- HTTP -------------------------------------------------------------------------------------
LAST_SEEN = [time.time()]
# installable-app files (phones fetch these before pairing)
STATIC = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
          "/sw.js": ("sw.js", "text/javascript"), "/icon-192.png": ("icon-192.png", "image/png"),
          "/icon-512.png": ("icon-512.png", "image/png"), "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png")}
PUBLIC = set(STATIC) | {"/api/pair"}
PC_ONLY = {"/api/browse", "/api/open"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        # a video player cancels downloads whenever it seeks - that's normal, not an error
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # -- the phone/tablet listener (remote.py) -----------------------------------------
    @property
    def remote(self):
        return getattr(self.server, "remote", False)

    def cookie(self, name):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def guard(self, path):
        """True if the request may go on. On the remote listener: paired devices only,
        and never the things that act on the PC itself."""
        if not self.remote:
            return True
        import remote
        if path in PUBLIC:
            return True
        if not remote.check(self.cookie(remote.COOKIE)):
            if path == "/":
                self.send_file(os.path.join(RES, "ui", "pair.html"))
            else:
                self.send_json({"error": "This device isn't paired - open the toolkit's address again to pair."}, 401)
            return False
        if path in PC_ONLY or path.startswith("/api/remote"):
            self.send_json({"error": "That only works on the PC itself."}, 403)
            return False
        return True

    def known_project(self, p):
        """Remote devices may only work on projects the toolkit already lists."""
        if not self.remote or not p:
            return True
        want = os.path.normcase(os.path.normpath(p))
        return any(os.path.normcase(x["path"]) == want for x in list_projects())

    def do_GET(self):
        LAST_SEEN[0] = time.time()
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if not self.guard(u.path):
                return
            if not self.known_project(q.get("path") if u.path != "/media" else q.get("project")):
                return self.send_json({"error": "Unknown project."}, 403)
            if u.path == "/":
                return self.send_file(os.path.join(RES, "ui", "index.html"))
            if u.path in STATIC:
                return self.send_file(os.path.join(RES, "ui", STATIC[u.path][0]), STATIC[u.path][1])
            if u.path == "/api/remote":
                import remote
                return self.send_json(remote.info())
            if u.path == "/api/state":
                return self.send_json(dict(version=__version__, projects=list_projects(), remote=self.remote,
                                           dirs=load_settings().get("dirs", DEFAULT_DIRS),
                                           scripts=sorted(os.path.basename(p) for p in
                                                          glob.glob(os.path.join(RES, "premiere", "*.jsx")))))
            if u.path == "/api/info":
                return self.send_json(project_info(q["path"]))
            if u.path == "/api/markers":
                return self.send_json(marker_segments(q["path"]))
            if u.path == "/api/timeline":
                tj = os.path.join(base_of(q["path"]) + "_captions", "timeline.json")
                if not os.path.exists(tj):
                    return self.send_json({"missing": True})
                with open(tj, encoding="utf-8") as f:
                    d = json.load(f)
                d["when"] = os.path.getmtime(tj)
                return self.send_json(d)
            if u.path == "/api/job":
                start = int(q.get("from", 0))
                with LOCK:
                    return self.send_json(dict(id=JOB["id"], title=JOB["title"], done=JOB["done"],
                                               code=JOB["code"], lines=JOB["lines"][start:],
                                               total=len(JOB["lines"]), started=JOB["started"]))
            if u.path == "/media":
                p = os.path.normpath(q["path"])
                folder = os.path.basename(os.path.dirname(p))
                allowed = ((folder.endswith("_captions") or folder.endswith("_shorts") or folder == "snippets")
                           and p.lower().endswith((".mp4", ".mp3")))
                if not allowed and q.get("project"):      # source footage of the open project, for the player
                    seqs = project(q["project"])
                    allowed = any(os.path.normcase(os.path.normpath(v.path or "")) == os.path.normcase(p)
                                  for sq in seqs for v in sq.video + sq.audio)
                if not allowed:
                    return self.send_json({"error": "not allowed"}, 403)
                return self.send_file(p)
        except (Exception, SystemExit) as e:  # show errors in the UI instead of a dead page
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        LAST_SEEN[0] = time.time()
        u = urlparse(self.path)
        try:
            if not self.guard(u.path):
                return
            b = self.body()
            if not self.known_project(b.get("path")):
                return self.send_json({"error": "Unknown project."}, 403)
            if u.path == "/api/pair":
                import remote
                token = remote.pair(b.get("code", ""), self.headers.get("User-Agent") or "device")
                if not token:
                    return self.send_json({"error": "That code didn't match - check the code on the PC."}, 403)
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", "%s=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax" % (remote.COOKIE, token))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if u.path == "/api/remote":
                import remote
                if "enabled" in b:
                    remote.set_enabled(b["enabled"], Handler)
                if b.get("new_code"):
                    remote.new_code()
                if b.get("revoke"):
                    remote.revoke(b["revoke"])
                return self.send_json(remote.info())
            if u.path == "/api/run":
                jid = run_job(b.get("title", b["action"]), command(b["action"], b))
                return self.send_json({"id": jid} if jid else {"error": "Something is already running."},
                                      200 if jid else 409)
            if u.path == "/api/browse":
                p = browse(b.get("kind", "project"))
                if p and b.get("kind") == "folder":
                    s = load_settings()
                    s["dirs"] = [p] + [d for d in s.get("dirs", DEFAULT_DIRS) if d != p]
                    save_settings(s)
                return self.send_json({"path": p})
            if u.path == "/api/open":
                p = b["path"]
                if b.get("script"):
                    p = os.path.join(RES, "premiere", os.path.basename(b["script"]))
                open_path(p, b.get("how", "file"))
                return self.send_json({"ok": True})
            if u.path == "/api/config":
                import config
                cfg = config.update(base_of(b["path"]) + "_captions", b["patch"])
                if "shorts" in b["patch"]:                 # keep Premiere's marker list in step
                    from shorts import write_marker_csv
                    write_marker_csv(base_of(b["path"]) + "_captions", cfg["shorts"])
                return self.send_json(cfg)
            if u.path == "/api/snippet":
                return self.send_json({"path": make_snippet(b["path"], float(b["start"]), float(b["end"]))})
            if u.path == "/api/ping":
                return self.send_json({"ok": True})
        except (Exception, SystemExit) as e:
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "not found"}, 404)

    def send_file(self, path, ctype=None):
        size = os.path.getsize(path)
        ctype = ctype or mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:                                  # video seeking needs byte ranges
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                start = int(m.group(1) or 0)
                end = int(m.group(2)) if m.group(2) else size - 1
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (ConnectionResetError, BrokenPipeError):
                    return
                left -= len(chunk)


def make_server(port, host="127.0.0.1"):
    return ThreadingHTTPServer((host, port), Handler)


def already_running():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def main():
    url = "http://127.0.0.1:%d/" % PORT
    if already_running():
        webbrowser.open(url)
        return
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    import remote
    remote.autostart(Handler)

    def reaper():                                # quit once the tab has been closed for a minute
        while True:
            time.sleep(10)
            if JOB["done"] and time.time() - LAST_SEEN[0] > 60:
                server.shutdown()
                return
    threading.Thread(target=reaper, daemon=True).start()
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
