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
]
binaries, hidden = [], []
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers", "webview", "qrcode", "psutil"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += ["app", "shorts", "captions", "prproj", "pipeline", "config", "screams", "laughs", "sounds",
           "style", "render", "timeline", "runtime", "remote", "posting", "clr"]
excludes = ["torch", "torchaudio", "torchlibrosa", "librosa", "matplotlib", "panns_inference", "numba",
            "llvmlite", "scipy", "onnx", "tkinter", "IPython", "pytest", "pandas", "sympy"]


def analysis(script):
    return Analysis([os.path.join(ROOT, script)], pathex=[ROOT], binaries=binaries, datas=datas,
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
