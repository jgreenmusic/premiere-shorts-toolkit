"""Step 7 - posting: hands finished Shorts to Post Studio, which writes the titles,
descriptions, tags and hashtags per platform and does the uploading/scheduling.

Post Studio is a separate app (github.com/jgreenmusic/post-studio). This module only runs
its command line, so either app can change inside without breaking the other:

    poststudio.py from-short <video> --subject .. --transcript t.json --json   write posts
    poststudio.py show <videos...>                                              what's written
    poststudio.py queue-add <video> <platform> --fields .. --settings .. --when .. --schedule
    poststudio.py queue --json                                                  the queue

Where Post Studio lives: "post_studio" in ~/.shorts-toolkit.json (default ~/post-studio).
"""
import json
import os
import subprocess
import tempfile

SETTINGS = os.path.join(os.path.expanduser("~"), ".shorts-toolkit.json")
DEFAULT = os.path.join(os.path.expanduser("~"), "post-studio")
PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels", "facebook"]
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PostStudioMissing(Exception):
    pass


def home():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            p = json.load(f).get("post_studio")
    except (OSError, ValueError):
        p = None
    return p or DEFAULT


def python():
    h = home()
    exe = os.path.join(h, ".venv", "Scripts", "python.exe")
    if not (os.path.isfile(exe) and os.path.isfile(os.path.join(h, "poststudio.py"))):
        raise PostStudioMissing("Post Studio isn't at %s - set its folder in step 7 (it does the writing and posting)." % h)
    return exe


def _cmd(args):
    return [python(), "-X", "utf8", os.path.join(home(), "poststudio.py")] + args


def run(args, timeout=120):
    """Quick Post Studio commands; returns parsed JSON."""
    p = subprocess.run(_cmd(args), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=home(),
                       timeout=timeout, creationflags=NOWIN, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "Post Studio failed")
    return json.loads(p.stdout)


def status():
    try:
        python()
        return dict(ok=True, home=home())
    except PostStudioMissing as e:
        return dict(ok=False, home=home(), error=str(e))


def platforms():
    return [p for p in run(["platforms", "--json"]) if p["id"] in PLATFORMS]


def show(files):
    return run(["show"] + list(files)) if files else []


def queue(project=None):
    js = run(["queue", "--json"])
    if project:
        js = [j for j in js if (j.get("source") or {}).get("project") == project]
    return js


def transcript_file(project_path, start, end):
    """The Short's captions (with your caption edits), times from the Short's own start."""
    import pipeline
    caps = pipeline.caption_list(project_path, start, end)["captions"]
    segs = [[round(max(0.0, c["start"] - start), 2), round(min(end, c["end"]) - start, 2), c["text"]]
            for c in caps if not c["hidden"] and c["text"].strip()]
    fd, path = tempfile.mkstemp(prefix="short-transcript-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False)
    return path, len(segs)


def write_cmd(video, transcript, subject="", notes="", platform_ids=None, fresh=False):
    """The command that writes posts for one Short (slow: runs the local AI model)."""
    a = ["from-short", video, "--platforms", ",".join(platform_ids or PLATFORMS), "--json"]
    if transcript:
        a += ["--transcript", transcript]
    if subject:
        a += ["--subject", subject]
    if notes:
        a += ["--notes", notes]
    if fresh:
        a.append("--fresh")
    return _cmd(a)


def add(video, platform, fields, settings=None, when=None, source=None, schedule=True):
    a = ["queue-add", video, platform, "--fields", json.dumps(fields, ensure_ascii=False), "--json"]
    if settings:
        a += ["--settings", json.dumps(settings, ensure_ascii=False)]
    if when:
        a += ["--when", when]
    if source:
        a += ["--source", json.dumps(source, ensure_ascii=False)]
    if schedule:
        a.append("--schedule")
    return run(a)
