"""Where things live, for both 'run from source' and the installed app.

The installed app (PyInstaller) unpacks its bundled files - ui, fonts, Premiere scripts,
models and its own ffmpeg - next to the executable. setup() puts that ffmpeg first on
PATH so every `ffmpeg`/`ffprobe` call uses it.
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
RES = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def setup():
    b = os.path.join(RES, "bin")
    if os.path.isdir(b):
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
