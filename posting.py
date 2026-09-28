"""Steps 7 and 8 - posting: writing each Short's title/description/tags/hashtags, and getting
them onto YouTube (filling drafts already uploaded in Studio, or uploading + scheduling).

The engine is Post Studio's code (github.com/jgreenmusic/post-studio), used IN-PROCESS: the
installed app bundles it, and from source it's imported from its folder ("post_studio" in
~/.shorts-toolkit.json, default ~/post-studio). One program, one data folder
(%LOCALAPPDATA%\\PostStudio: written posts, logins, the queue, the posting plan).
"""
import json
import os
import subprocess
import sys
import tempfile

SETTINGS = os.path.join(os.path.expanduser("~"), ".shorts-toolkit.json")
DEFAULT = os.path.join(os.path.expanduser("~"), "post-studio")
PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels", "facebook"]
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FROZEN = getattr(sys, "frozen", False)


class PostStudioMissing(Exception):
    pass


def home():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            p = json.load(f).get("post_studio")
    except (OSError, ValueError):
        p = None
    return p or DEFAULT


_ENGINE = {}


def engine():
    """The Post Studio modules: {poststudio, publish, store, generate, studio}."""
    if _ENGINE:
        return _ENGINE
    if not FROZEN:
        h = home()
        if not os.path.isfile(os.path.join(h, "poststudio.py")):
            raise PostStudioMissing("Post Studio's engine isn't at %s - set its folder in step 7." % h)
        if h not in sys.path:
            sys.path.append(h)             # appended: the toolkit's own modules (app, config...) win any name clash
    import generate
    import poststudio
    import publish
    import store
    from publish import studio
    _ENGINE.update(poststudio=poststudio, publish=publish, store=store, generate=generate, studio=studio)
    return _ENGINE


def status():
    try:
        engine()
        return dict(ok=True, home="built in" if FROZEN else home())
    except (PostStudioMissing, ImportError) as e:
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
    """`brain ada` - loads the 12B model; exit 2 = the RAM guard refused."""
    if not os.path.isfile(BRAIN):
        return dict(ok=False, message="Start Ollama yourself, then try again.")
    p = subprocess.run(["cmd", "/c", BRAIN, "ada"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, creationflags=NOWIN)
    lines = [x.strip() for x in (p.stdout + p.stderr).splitlines() if x.strip()]
    msg = " ".join(lines[-4:])[:600]
    if p.returncode == 2:
        msg = "Not started - the RAM guard refused (not enough free RAM). " + msg
    return dict(ok=p.returncode == 0, code=p.returncode, message=msg)


# -- what's written ----------------------------------------------------------------------
def readiness():
    E = engine()
    publish = E["publish"]
    acc = publish.accounts_status(check=False)
    st = publish.settings()
    out = {}
    for pid in publish.DIRECT:
        be = publish.backend_for(pid)
        a = acc.get(be.NAME, {})
        out[pid] = dict(account=bool(a.get("connected")), who=a.get("who"), account_name=be.TITLE, route=publish.route(pid),
                        plan=st["plan"].get(pid) or [], native=be.NATIVE_SCHEDULE)
    return dict(platforms=out, task=publish.task_status())


def missing(ready, plats):
    """Plain-English list of what stops these platforms being scheduled."""
    out = []
    for pid in plats:
        r = (ready.get("platforms") or {}).get(pid)
        if not r:
            continue
        name = {"youtube_shorts": "YouTube Shorts", "tiktok": "TikTok", "instagram_reels": "Instagram Reels", "facebook": "Facebook"}.get(pid, pid)
        if not r["plan"]:
            out.append("%s: no posting times set (step 8 > Posting times)" % name)
        if not r["account"]:
            out.append("%s: %s isn't connected (step 8)" % (name, r["account_name"]))
    return out


def platforms():
    E = engine()
    out = []
    for k, p in E["generate"].platforms(E["store"].ROOT).items():
        if k in PLATFORMS:
            out.append(dict(id=k, name=p["name"], upload=p.get("upload") or [], postable=k in E["publish"].DIRECT,
                            fields=[{x: f.get(x) for x in ("key", "label", "type", "max")} for f in p["fields"]]))
    return out


def show(files):
    E = engine()
    return [E["poststudio"].show(f) for f in files]


def queue(project=None):
    js = engine()["publish"].jobs()
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


def write(video, transcript, subject="", notes="", platform_ids=None, fresh=False, background="", siblings=None, angle=None,
          avoid="", clean=False, quick=True, base_tags="", examples="", log=print):
    """Write the posts for one Short (the slow part: the local AI model)."""
    ps = engine()["poststudio"]
    split = lambda s: [w.strip() for w in str(s or "").split(",") if w.strip()]
    return ps.from_short(video, platform_ids or PLATFORMS, subject, notes, transcript, None, fresh, log=log, background=background,
                         siblings=siblings, angle=angle, screen_text=False, avoid=split(avoid), clean=clean, quick=quick,
                         base_tags=split(base_tags), examples=[e.strip() for e in str(examples or "").splitlines() if e.strip()])


def set_field(video, platform, key, value):
    try:
        return engine()["poststudio"].set_field(video, platform, key, value)
    except SystemExit as e:
        raise ValueError(str(e))


def add(video, platform, fields, settings=None, when=None, source=None, schedule=True):
    publish = engine()["publish"]
    if when == "next":
        when = publish.next_slot(platform)
        if not when:
            raise ValueError("No posting times for %s yet (step 8)." % platform)
    job = publish.add(video, platform, fields, settings, when, source)
    return publish.edit(job["id"], status="scheduled") if schedule else job
