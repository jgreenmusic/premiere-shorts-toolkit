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


OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
BRAIN = os.path.join(os.path.expanduser("~"), "ALBERT", "bin", "brain.cmd")      # Albert's model switch (has a RAM guard)


def ai_status():
    """Is the local AI (Ollama) up? Plain HTTP - never starts or loads anything."""
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=2) as r:
            loaded = [m["name"] for m in json.load(r).get("models", [])]
        return dict(up=True, loaded=loaded, can_start=os.path.isfile(BRAIN))
    except OSError:
        return dict(up=False, loaded=[], can_start=os.path.isfile(BRAIN))


def start_ai():
    """`brain ada` - loads the 12B model, refusing (exit 2) if RAM won't fit or a stream/game is live."""
    if not os.path.isfile(BRAIN):
        return dict(ok=False, message="Start Ollama yourself, then try again.")
    p = subprocess.run(["cmd", "/c", BRAIN, "ada"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, creationflags=NOWIN)
    lines = [x.strip() for x in (p.stdout + p.stderr).splitlines() if x.strip()]
    msg = " ".join(lines[-4:])[:600]
    if p.returncode == 2:
        msg = "Not started - the RAM guard refused (something is streaming or a game server is up). " + msg
    return dict(ok=p.returncode == 0, code=p.returncode, message=msg)


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
    segs = []
    for c in caps:
        if c["hidden"] or not c["text"].strip():
            continue
        a, b, t = round(max(0.0, c["start"] - start), 2), round(min(end, c["end"]) - start, 2), c["text"].strip()
        # Shorts captions are 1-3 word chunks; joined back into sentences so quotes come out whole
        # (otherwise the AI quoted "Well," "at least it" "starts us right" as separate lines)
        if segs and a - segs[-1][1] <= 0.8 and not segs[-1][2].endswith((".", "?", "!")) and len(segs[-1][2].split()) < 25:
            segs[-1][1], segs[-1][2] = b, segs[-1][2] + " " + t
        else:
            segs.append([a, b, t])
    fd, path = tempfile.mkstemp(prefix="short-transcript-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False)
    return path, len(segs)


ANGLES = ["quote", "reaction", "question", "deadpan", "tease", "story", "hot_take"]


def plain(posts):
    """{platform: {field: {value, warnings}}} -> {platform: {field: value}} (what siblings look like)."""
    return {pid: {k: v.get("value") if isinstance(v, dict) else v for k, v in (f or {}).items()} for pid, f in (posts or {}).items()}


def write_cmd(video, transcript, subject="", notes="", platform_ids=None, fresh=False, background="", siblings=None, angle=None,
              avoid="", clean=False, quick=True, base_tags=""):
    """The command that writes posts for one Short (slow: runs the local AI model).
    notes = about THIS Short; background = the channel (same for every Short);
    siblings = a JSON file of the other Shorts' posts so this one doesn't repeat them."""
    a = ["from-short", video, "--platforms", ",".join(platform_ids or PLATFORMS), "--json", "--no-screen-text"]
    if background:
        a += ["--background", background]
    if siblings:
        a += ["--siblings", siblings]
    if angle:
        a += ["--angle", angle]
    if avoid:
        a += ["--avoid", avoid]
    if clean:
        a.append("--clean")
    if quick:
        a.append("--quick")
    if base_tags:
        a += ["--base-tags", base_tags]
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
