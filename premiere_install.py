"""Put the two Premiere bridge panels (premiere/bridge-uxp, premiere/bridge-cep) where
Premiere loads them. Per-user, no admin rights:

  Captions panel (CEP)  -> %APPDATA%\\Adobe\\CEP\\extensions\\<id>, plus Adobe's documented
                           PlayerDebugMode switch so Premiere loads a panel that isn't from
                           the Adobe Exchange (HKCU\\Software\\Adobe\\CSXS.<n>).
  Speech panel (UXP)    -> packed as a .ccx and handed to Adobe's own plugin installer
                           (UnifiedPluginInstallerAgent, part of Creative Cloud).

Restart Premiere afterwards: it only looks for panels at start-up.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, "_MEIPASS", HERE)
CEP_ID = "com.jgreenmusic.shortstoolkit.captions"
UXP_NAME = "Shorts Toolkit - Speech"
CEP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Adobe", "CEP", "extensions", CEP_ID)
UPIA = os.path.join(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"), "Adobe",
                    "Adobe Desktop Common", "RemoteComponents", "UPI", "UnifiedPluginInstallerAgent",
                    "UnifiedPluginInstallerAgent.exe")
CSXS = (9, 10, 11, 12, 13)          # Premiere 2019 ... 2026+ read one of these
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def src(name):
    return os.path.join(RES, "premiere", name)


def _debug_mode(on=True):
    import winreg
    for v in CSXS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Adobe\CSXS.%d" % v) as k:
            winreg.SetValueEx(k, "PlayerDebugMode", 0, winreg.REG_SZ, "1" if on else "0")


def _debug_mode_on():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Adobe\CSXS.12") as k:
            return winreg.QueryValueEx(k, "PlayerDebugMode")[0] == "1"
    except OSError:
        return False


def _uxp_listed():
    if not os.path.exists(UPIA):
        return False
    try:
        out = subprocess.run([UPIA, "/list", "all"], capture_output=True, text=True, timeout=60,
                             creationflags=NOWIN).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return UXP_NAME in out


def installed():
    """Cheap check (no Adobe installer call): is the captions panel in place?
    Whether the speech panel works is shown by it checking in from Premiere."""
    return dict(cep=os.path.exists(os.path.join(CEP_DIR, "CSXS", "manifest.xml")) and _debug_mode_on())


def install():
    lines, ok = [], True
    # 1. captions panel (CEP)
    try:
        if os.path.exists(CEP_DIR):
            shutil.rmtree(CEP_DIR)
        shutil.copytree(src("bridge-cep"), CEP_DIR)
        _debug_mode(True)
        lines.append("Captions panel: installed")
    except Exception as e:                              # noqa: BLE001 - shown to the user
        ok = False
        lines.append("Captions panel: FAILED - %s" % e)
    # 2. speech panel (UXP) through Adobe's installer
    if not os.path.exists(UPIA):
        ok = False
        lines.append("Speech panel: Adobe's plugin installer isn't on this PC (it comes with the Creative Cloud app)."
                     " Use 'Toolkit speech' instead, or load premiere\\bridge-uxp with Adobe's UXP Developer Tool.")
    else:
        ccx = os.path.join(tempfile.gettempdir(), "shorts-toolkit-speech.ccx")
        with zipfile.ZipFile(ccx, "w", zipfile.ZIP_DEFLATED) as z:
            root = src("bridge-uxp")
            for dp, _, files in os.walk(root):
                for f in files:
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, root).replace(os.sep, "/"))
        # Adobe's installer keeps an installed copy of the same version, so take it out first
        subprocess.run([UPIA, "/remove", UXP_NAME], capture_output=True, text=True, timeout=300, creationflags=NOWIN)
        r = subprocess.run([UPIA, "/install", ccx], capture_output=True, text=True, timeout=300, creationflags=NOWIN)
        said = " ".join((r.stdout + " " + r.stderr).split())[-300:]
        if _uxp_listed():
            lines.append("Speech panel: installed")
        else:
            ok = False
            lines.append("Speech panel: Adobe's installer didn't take it (%s). Use 'Toolkit speech' for now, or load "
                         "premiere\\bridge-uxp with Adobe's UXP Developer Tool." % (said or "no message"))
    lines.append("Restart Premiere, then open Window > Extensions (or Plugins) > Shorts Toolkit.")
    return dict(ok=ok, lines=lines, installed=installed())


if __name__ == "__main__":
    for line in install()["lines"]:
        print(line)
