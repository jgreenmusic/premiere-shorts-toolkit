# PyInstaller recipe for the Windows app.   Build:  packaging\build-windows.cmd
#
# Two programs share one folder of libraries:
#   Shorts Toolkit.exe  - the app window (no console)
#   shorts-cli.exe      - the same engine on the command line; the window runs its
#                         background jobs through it
# Bundled: the UI, fonts, Premiere scripts, the laugh model (models/panns_sed.onnx),
# and ffmpeg.exe (gyan.dev "essentials": libass + x264) in bin/.
# Not bundled: the Whisper speech model - downloaded on first use (~500 MB).
import glob
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
# Post Studio's engine (writing posts, YouTube publishing) is built into the app - one program.
# Its source is the post-studio repo next to this one.
PS = os.path.abspath(os.path.join(ROOT, "..", "post-studio"))
assert os.path.isfile(os.path.join(PS, "poststudio.py")), "post-studio repo not found at " + PS
FFMPEG = glob.glob(os.path.join(ROOT, "build", "ffmpeg", "ffmpeg-*-essentials_build"))[0]

datas = [
    (os.path.join(ROOT, "ui"), "ui"),
    (os.path.join(ROOT, "fonts"), "fonts"),
    (os.path.join(ROOT, "premiere"), "premiere"),
    (os.path.join(ROOT, "models"), "models"),
    (os.path.join(FFMPEG, "bin", "ffmpeg.exe"), "bin"),
    (os.path.join(FFMPEG, "LICENSE"), "bin"),
    (os.path.join(ROOT, "README.md"), "."),
    (os.path.join(ROOT, "CHANGELOG.md"), "."),
    (os.path.join(PS, "platforms"), "platforms"),
    (os.path.join(PS, "voices"), "voices"),
    (os.path.join(PS, "models", "audioset_labels.csv"), "models"),
]
binaries, hidden = [], []
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers", "webview", "qrcode", "psutil"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += ["app", "shorts", "captions", "prproj", "pipeline", "config", "screams", "laughs", "sounds",
           "style", "render", "timeline", "bleep", "runtime", "remote", "posting", "youtube_step", "clr",
           # the Post Studio engine
           "poststudio", "generate", "llm", "quick", "store", "publish", "publish.accounts", "publish.net", "publish.youtube", "publish.stats",
           "publish.tiktok", "publish.meta", "publish.postiz", "publish.studio", "analyzers", "analyzers.probe",
           "analyzers.document", "analyzers.speech", "analyzers.sound", "analyzers.visual", "analyzers.understand"]
excludes = ["torch", "torchaudio", "torchlibrosa", "librosa", "matplotlib", "panns_inference", "numba",
            "llvmlite", "scipy", "onnx", "tkinter", "IPython", "pytest", "pandas", "sympy"]


def analysis(script):
    return Analysis([os.path.join(ROOT, script)], pathex=[ROOT, PS], binaries=binaries, datas=datas,
                    hiddenimports=hidden, excludes=excludes, noarchive=False)


gui = analysis("desktop.py")
cli = analysis("shorts_cli.py")
icon = os.path.join(ROOT, "ui", "icon.ico")

gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="Shorts Toolkit",
              console=False, icon=icon, upx=False)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="shorts-cli",
              console=True, icon=icon, upx=False)
COLLECT(gui_exe, gui.binaries, gui.datas, cli_exe, cli.binaries, cli.datas,
        name="Shorts Toolkit", upx=False)
