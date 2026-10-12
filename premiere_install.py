"""Put the two Premiere bridge panels (premiere/bridge-uxp, premiere/bridge-cep) where
Premiere loads them. Per-user, no admin rights:

  Captions panel (CEP)  -> %APPDATA%\\Adobe\\CEP\\extensions\\<id>, plus Adobe's documented
                           PlayerDebugMode switch so Premiere loads a panel that isn't from
                           the Adobe Exchange (HKCU\\Software\\Adobe\\CSXS.<n>).
  Speech panel (UXP)    -> packed as a .ccx and handed to Adobe's own plugin installer
                           (UnifiedPluginInstallerAgent, part of Creative Cloud). That
                           installer refuses when the Creative Cloud app isn't signed in
                           (status -631); then the panel is put where the installer would
                           have put it: %APPDATA%\\Adobe\\UXP\\Plugins\\External\\<id>_<version>,
                           listed in ...\\UXP\\PluginsInfo\\v1\\premierepro.json.

Restart Premiere afterwards: it only looks for panels at start-up.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, "_MEIPASS", HERE)
CEP_ID = "com.jgreenmusic.shortstoolkit.captions"
UXP_ID = "com.jgreenmusic.shortstoolkit.speech"
UXP_NAME = "Shorts Toolkit - Speech"
CEP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Adobe", "CEP", "extensions", CEP_ID)
UXP_ROOT = os.path.join(os.environ.get("APPDATA", ""), "Adobe", "UXP")
UXP_INFO = os.path.join(UXP_ROOT, "PluginsInfo", "v1", "premierepro.json")
UPIA = os.path.join(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"), "Adobe",
                    "Adobe Desktop Common", "RemoteComponents", "UPI", "UnifiedPluginInstallerAgent",
                    "UnifiedPluginInstallerAgent.exe")
CSXS = (9, 10, 11, 12, 13)          # Premiere 2019 ... 2026+ read one of these
PANELS = "1.0.4"                    # the version both panels carry (their manifests and main.js)
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


def installed():
    """Cheap check (no Adobe installer call): is the captions panel in place?
    Whether the speech panel works is shown by it checking in from Premiere."""
    return dict(cep=os.path.exists(os.path.join(CEP_DIR, "CSXS", "manifest.xml")) and _debug_mode_on())


def _text(path):
    try:
        with open(path, "rb") as f:
            return b"\n".join(f.read().splitlines())
    except OSError:
        return None


def _same(folder, source, names):
    return all(_text(os.path.join(folder, n)) == _text(os.path.join(source, n)) for n in names)


def _uxp_listing():
    """Premiere's list of plugins put in from outside the Adobe Exchange: {"plugins": [...]}."""
    try:
        with open(UXP_INFO, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d.get("plugins"), list) else {"plugins": []}
    except (OSError, ValueError, AttributeError):
        return {"plugins": []}


def _uxp_folder(entry):
    return os.path.normpath(str(entry.get("path", "")).replace("$localPlugins", os.path.join(UXP_ROOT, "Plugins")))


def _uxp_current():
    """Is the Speech panel Premiere will load the one this version ships?"""
    for e in _uxp_listing()["plugins"]:
        if e.get("pluginId") == UXP_ID:
            return (e.get("status") == "enabled" and e.get("versionString") == PANELS
                    and _same(_uxp_folder(e), src("bridge-uxp"), ("main.js", "manifest.json", "index.html")))
    return False


def current():
    """Are the panels Premiere loads the ones this version of the toolkit ships? (Auto Run puts
    them in by itself when they aren't.)"""
    return (installed()["cep"] and _uxp_current()
            and _same(CEP_DIR, src("bridge-cep"), ("main.js", "host.jsx", "index.html", os.path.join("CSXS", "manifest.xml"))))


def _uxp_by_hand():
    """What Adobe's installer does, done here: copy the panel in and list it for Premiere.
    Used when that installer is missing or refuses (it needs the Creative Cloud app signed in)."""
    with open(os.path.join(src("bridge-uxp"), "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    name = "%s_%s" % (UXP_ID, m["version"])
    dest = os.path.join(UXP_ROOT, "Plugins", "External", name)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(src("bridge-uxp"), dest)
    d = _uxp_listing()
    older = [e for e in d["plugins"] if e.get("pluginId") == UXP_ID]
    d["plugins"] = [e for e in d["plugins"] if e.get("pluginId") != UXP_ID] + [dict(
        hostMinVersion=m["host"]["minVersion"], name=m["name"], path="$localPlugins\\External\\" + name,
        pluginId=UXP_ID, status="enabled", type="uxp", versionString=m["version"])]
    os.makedirs(os.path.dirname(UXP_INFO), exist_ok=True)
    with open(UXP_INFO, "w", encoding="utf-8") as f:
        json.dump(d, f, separators=(",", ":"))
    for e in older:                                     # this panel's earlier version: no longer listed, so no longer loaded
        old = _uxp_folder(e)
        if os.path.normcase(old) != os.path.normcase(dest) and os.path.basename(old).startswith(UXP_ID + "_"):
            shutil.rmtree(old, ignore_errors=True)


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
    # 2. speech panel (UXP): Adobe's installer first, by hand if it won't
    said = "Adobe's plugin installer isn't on this PC"
    if os.path.exists(UPIA):
        ccx = os.path.join(tempfile.gettempdir(), "shorts-toolkit-speech.ccx")
        with zipfile.ZipFile(ccx, "w", zipfile.ZIP_DEFLATED) as z:
            root = src("bridge-uxp")
            for dp, _, files in os.walk(root):
                for f in files:
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, root).replace(os.sep, "/"))
        try:
            # Adobe's installer keeps an installed copy of the same version, so take it out first
            subprocess.run([UPIA, "/remove", UXP_NAME], capture_output=True, text=True, timeout=300, creationflags=NOWIN)
            r = subprocess.run([UPIA, "/install", ccx], capture_output=True, text=True, timeout=300, creationflags=NOWIN)
            said = " ".join((r.stdout + " " + r.stderr).split())[-300:] or "no message"
        except (OSError, subprocess.TimeoutExpired) as e:
            said = str(e)
    if _uxp_current():
        lines.append("Speech panel: installed")
    else:
        try:
            _uxp_by_hand()
        except Exception as e:                          # noqa: BLE001 - shown to the user
            said += "; and copying it in by hand failed: %s" % e
        if _uxp_current():
            lines.append("Speech panel: installed")
        else:
            ok = False
            lines.append("Speech panel: couldn't be installed (%s). Use 'Toolkit speech' for now, or load "
                         "premiere\\bridge-uxp with Adobe's UXP Developer Tool." % said)
    lines.append("Restart Premiere, then open Window > Extensions (or Plugins) > Shorts Toolkit.")
    return dict(ok=ok, lines=lines, installed=installed())


if __name__ == "__main__":
    for line in install()["lines"]:
        print(line)
