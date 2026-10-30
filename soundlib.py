"""The sound library: the built-in effects (soundfx\\) plus the sounds and music you added.

What you add is copied into %LOCALAPPDATA%\\ShortsToolkit\\sounds\\effect or \\music and shared by every
project. Each file is converted to 48 kHz stereo .wav on the way in, so an mp3, an m4a or a video's sound
all work, and the render and Premiere only ever meet one shape of file.

A sound is known by an id: fx:cuckoo (built in), my:Name.wav (your effect), music:Name.wav (your music).
"""
import json
import os
import re
import subprocess
import tempfile
import wave

from runtime import RES

SR = 48000
KINDS = {"effect": "my", "music": "music"}          # what you can add -> its id prefix
MAX_UPLOAD = 1 << 30                                # 1 GB: a whole album or a long video's sound


def home():
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ShortsToolkit", "sounds")


def folder(kind):
    d = os.path.join(home(), kind)
    os.makedirs(d, exist_ok=True)
    return d


def builtin_dir():
    return os.path.join(RES, "soundfx")


def duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _entry(sid, name, path, group):
    try:
        return dict(id=sid, name=name, seconds=round(duration(path), 2), group=group)
    except (OSError, EOFError, wave.Error):
        return None                                  # a damaged or half-copied file isn't offered


def listing():
    """{effects: [...], music: [...]}; each {id, name, seconds, group}. group: short / moment / yours."""
    effects = []
    try:
        with open(os.path.join(builtin_dir(), "index.json"), encoding="utf-8") as f:
            for s in json.load(f):
                effects.append(_entry("fx:" + s["file"], s["name"], os.path.join(builtin_dir(), s["file"] + ".wav"), s["group"]))
    except (OSError, ValueError):
        pass
    mine = lambda kind: [_entry("%s:%s" % (KINDS[kind], f), os.path.splitext(f)[0], os.path.join(folder(kind), f), "yours")
                         for f in sorted(os.listdir(folder(kind)), key=str.lower) if f.lower().endswith(".wav")]
    return dict(effects=[e for e in mine("effect") + effects if e], music=[e for e in mine("music") if e], folder=home())


def path_of(sid):
    """The file behind an id, or None if there is no such sound (removed since a rule was made)."""
    prefix, _, name = (sid or "").partition(":")
    name = os.path.basename(name)                    # an id can never climb out of the folder
    if not name:
        return None
    if prefix == "fx":
        p = os.path.join(builtin_dir(), name + ".wav")
    elif prefix == "my":
        p = os.path.join(folder("effect"), name)
    elif prefix == "music":
        p = os.path.join(folder("music"), name)
    else:
        return None
    return p if os.path.isfile(p) else None


def clean_name(name):
    name = os.path.splitext(os.path.basename(name or ""))[0]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", name).strip(" .")
    return name[:80] or "sound"


def add(src, kind, name):
    """Convert a file into the library. Returns its listing entry; ValueError says what's wrong with it."""
    if kind not in KINDS:
        raise ValueError("Unknown kind of sound.")
    d = folder(kind)
    base = clean_name(name)
    dst, n = os.path.join(d, base + ".wav"), 1
    while os.path.exists(dst):
        n += 1
        dst = os.path.join(d, "%s %d.wav" % (base, n))
    part = dst + ".part.wav"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(SR),
                        "-c:a", "pcm_s16le", part], capture_output=True, text=True, errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode or not os.path.exists(part) or os.path.getsize(part) < 1024:
        if os.path.exists(part):
            os.remove(part)
        raise ValueError("%s has no sound the toolkit can read." % (name or "That file"))
    os.replace(part, dst)
    return _entry("%s:%s" % (KINDS[kind], os.path.basename(dst)), os.path.splitext(os.path.basename(dst))[0], dst, "yours")


def add_stream(stream, size, kind, name):
    """add() for an upload: the bytes go to a temp file first."""
    if size <= 0 or size > MAX_UPLOAD:
        raise ValueError("That file is empty or over 1 GB.")
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(name or "")[1] or ".bin")
    try:
        with os.fdopen(fd, "wb") as f:
            left = size
            while left > 0:
                chunk = stream.read(min(1 << 16, left))
                if not chunk:
                    raise ValueError("The upload stopped early.")
                f.write(chunk)
                left -= len(chunk)
        return add(tmp, kind, name)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def remove(sid):
    """Take one of YOUR sounds out of the library (the file you added it from is not touched)."""
    p = path_of(sid)
    if not p or sid.startswith("fx:"):
        raise ValueError("Built-in sounds can't be removed.")
    os.remove(p)
