"""Premiere, driven for you: have Adobe's Speech to Text write a project's captions with
nobody at the keyboard. Shorts Auto Run uses this for its Captions step.

    captions(path)  ->  the Premiere project that now has the captions

What it does, in order:
    1. puts the toolkit's two Premiere panels in place if they are missing or old
    2. starts Premiere if it isn't running, and waits for the Speech panel to answer
       (that panel is alive even on Premiere's Home screen, with no project open)
    3. opens the project there - or, for a plain recording (an .mp4 with no project),
       has Premiere make  <recording name>.prproj  next to it with the recording on a
       timeline of its own. The recording itself is never changed.
    4. the same steps as the toolkit's "Make captions" button (bridge.py): Premiere
       transcribes, the toolkit cuts the words into caption lines, the Captions panel
       lays them on the timeline as a real caption track and saves the project
    5. reads the saved project back to make sure the captions are really in it

Anything only you can sort out (Premiere not installed, a panel closed, a language pack
missing) comes back as Problem, with what to do in its text.
"""
import glob
import json
import os
import subprocess
import time

import bridge

EXE = "Adobe Premiere Pro.exe"
# how long each wait may take, in seconds (the tests shorten these)
WAIT = dict(premiere=300,        # Premiere starting, until its Speech panel answers
            panel=25,            # the Speech panel, when Premiere was open already
            ask=240,             # Premiere opening or making a project
            settle=15,           # ...and, if no answer came, for the result to show up anyway
            opened=90,           # the project being the one in front
            captions_panel=120,  # the Captions panel, which only starts once a project is open
            quiet=120,           # a panel gone silent in the middle of the captions
            saved=60)            # the saved project showing its captions
SPEECH_HELP = ("Premiere is open, but the toolkit's Speech panel in it isn't answering. In Premiere open "
               "Window > UXP Plugins > Shorts Toolkit - Speech, leave it docked, then press Continue. "
               "If it is open already (or the toolkit was just updated), close Premiere and press Continue - "
               "it is started again for you with the right panels.")
CAPTIONS_HELP = ("Premiere has the project open, but the toolkit's Captions panel in it isn't answering. In Premiere open "
                 "Window > Extensions > Shorts Toolkit - Captions and leave it docked, then press Continue. "
                 "If it is open already, close Premiere and press Continue - it is started again for you.")


class Problem(Exception):
    """Something in the way that only you can sort out. The text says what to do."""


class Stopped(Exception):
    """You pressed Stop."""


def launch(argv):
    """Start Premiere on its own. A child of the installed app otherwise inherits the app's DLL
    folder and loads its VCRUNTIME & co, then an update can't replace those files and the
    installer tries to close Premiere (found 2026-10-30, with unsaved work open)."""
    import ctypes
    import runtime
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                  if not os.path.normcase(p).startswith(os.path.normcase(runtime.RES)))
    if os.name != "nt" or not runtime.FROZEN:
        return subprocess.Popen(argv, env=env)
    k = ctypes.windll.kernel32
    was = ctypes.create_unicode_buffer(1024)
    k.GetDllDirectoryW(1024, was)
    k.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(argv, env=env)
    finally:
        k.SetDllDirectoryW(was.value)


def exe():
    """Where Premiere is installed (the newest, if there are several), or None."""
    roots = {os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"} - {None, ""}
    found = [p for r in roots for p in glob.glob(os.path.join(r, "Adobe", "Adobe Premiere Pro*", EXE))]
    return max(found, key=os.path.getmtime) if found else None


def running():
    import psutil
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == EXE.lower():
            return True
    return False


def status():
    """For the set-up card: can Premiere write the captions on this PC?"""
    return dict(installed=bool(exe()), running=running())


def project_for(path):
    """The Premiere project a recording's captions go into: the project itself, or - for a
    plain video file - a project of the same name next to it (so both share one toolkit folder)."""
    from clip import is_clip
    return os.path.splitext(path)[0] + ".prproj" if is_clip(path) else path


def _norm(p):
    p = str(p or "").replace("/", "\\")
    return (p[4:] if p.startswith("\\\\?\\") else p).lower()


def _read(project, sequence=None):
    """(timelines with something on them, captions on the wanted one) as saved on disk right now."""
    from prproj import Project
    try:
        seqs = Project(project).sequences()
    except Exception:                                # being written this very moment, or not there yet
        return 0, 0
    used = [s for s in seqs if s.video or s.audio]
    one = next((s for s in seqs if s.name == sequence), None) or (used[0] if used else None)
    return len(used), len(one.captions) if one else 0


def captions(path, sequence=None, style="premiere", punct="keep", say=print, stopped=lambda: False, start=None):
    """Have Premiere write the captions for this project or recording.
    path: a .prproj, or a video file. sequence: the timeline's name (a recording's is its file name).
    say(text): called with what is happening. stopped(): True once you have pressed Stop.
    start: how Premiere is started (tests put a stand-in here).
    Returns the Premiere project that has the captions now."""
    from clip import is_clip
    import premiere_install

    def wait(test, seconds):
        end = time.time() + seconds
        while True:
            if stopped():
                bridge.cancel()
                raise Stopped()
            got = test()
            if got or time.time() >= end:
                return got
            time.sleep(min(0.5, max(0.02, seconds / 20)))

    program = exe()
    if not program and start is None:
        raise Problem("Premiere isn't installed on this PC, so it can't write the captions. "
                      "Skip this step to let the toolkit write them from the speech it hears.")
    if start is None:
        if not premiere_install.current():
            say("Putting the toolkit's two panels into Premiere…")
            r = premiere_install.install()
            if not r["ok"]:
                raise Problem("The toolkit's Premiere panels couldn't be put in place: " + " ".join(r["lines"][:-1]))
        start = lambda project: launch([program] + ([project] if project else []))

    path = os.path.normpath(os.path.abspath(path))   # Premiere wants C:\this\kind: with / it reports its scratch disks unavailable
    clip = is_clip(path)
    project = project_for(path)
    name = os.path.basename(project)
    sequence = sequence or os.path.splitext(os.path.basename(path))[0]
    opened = lambda: any(_norm((bridge.panel(k) or {}).get("project")) == _norm(project) for k in ("uxp", "cep"))

    def why(msg):
        """A panel's answer, or - when none came - where Premiere was at (usually a question on its screen)."""
        at = (bridge.panel("uxp") or {}).get("doing")
        if msg and "didn't answer" in msg and at:
            return "Premiere stopped while %s - it may be showing a question that needs an answer. Look at Premiere, then press Continue." % at
        return msg or SPEECH_HELP

    # 1. Premiere, with the Speech panel answering
    fresh = not running() and not bridge.connected("uxp")
    if fresh:
        say("Starting Premiere…")
        start(project if os.path.exists(project) else None)
    if not wait(lambda: bridge.panel("uxp"), WAIT["premiere"] if fresh else WAIT["panel"]):
        raise Problem(SPEECH_HELP if running() else "Premiere didn't start. Open it yourself, then press Continue.")

    # 2. the project, open in Premiere
    if clip and not _read(project, sequence)[0]:
        say("Premiere is making %s from the recording…" % name)
        ok, msg = bridge.call("uxp", dict(op="newproject", project=project, clip=path, sequence=sequence,
                                          exists=os.path.exists(project)), WAIT["ask"])
        if not ok and not wait(lambda: _read(project, sequence)[0], WAIT["settle"]):
            raise Problem("Premiere couldn't make a project from the recording. %s" % why(msg))
        say(msg or "Made %s." % name)
    elif not opened():
        say("Opening %s in Premiere…" % name)
        ok, msg = bridge.call("uxp", dict(op="open", project=project), WAIT["ask"])
        if not ok and not wait(opened, WAIT["settle"]):
            raise Problem("Premiere couldn't open %s. %s" % (name, why(msg)))
    if not wait(opened, WAIT["opened"]):
        raise Problem("Premiere doesn't have %s in front. Open it in Premiere, then press Continue." % name)

    have = _read(project, sequence)[1]
    if have:                                         # made on an earlier try, or by hand in the meantime
        say("%s already has %d captions." % (name, have))
        return project

    # 3. the Captions panel - it only exists once a project is open
    if not wait(lambda: bridge.panel("cep"), WAIT["captions_panel"]):
        raise Problem(CAPTIONS_HELP)

    # 4. transcribe -> caption lines -> caption track -> save (the "Make captions" button's steps)
    if bridge.status()["job"]["step"] in ("speech", "words", "srt", "import"):
        bridge.cancel()                              # left over from a try that never finished
    err = bridge.start(project, bridge.outdir_of(project), sequence, "adobe", style, punct)
    if err:
        raise Problem(err)
    shown, lost, began = 0, None, time.time()
    while True:
        if stopped():
            bridge.cancel()
            raise Stopped()
        job = bridge.status()["job"]
        for line in job["lines"][shown:]:
            say(line.split(" ", 1)[-1])
        shown = len(job["lines"])
        last = job["lines"][-1].split(" ", 1)[-1] if job["lines"] else ""
        if job["step"] == "done":
            break
        if job["step"] in ("failed", "click"):
            raise Problem("Premiere couldn't finish the captions: " + last.replace("Failed: ", "", 1))
        if job["step"] == "idle":
            raise Stopped()
        waiting_on = "uxp" if job["step"] == "speech" else "cep"
        lost = (lost or time.time()) if not bridge.connected(waiting_on) else None
        if lost and time.time() - lost > WAIT["quiet"]:
            bridge.cancel()
            raise Problem("Premiere stopped answering in the middle of the captions. Check that it is still open "
                          "(a dialog may be waiting for you), then press Continue.")
        if time.time() - began > 3 * 3600:
            bridge.cancel()
            raise Problem("Premiere has been at the captions for three hours - stopped waiting. Press Continue to try again.")
        time.sleep(0.5)

    # 5. the saved project really has them
    n = wait(lambda: _read(project, sequence)[1], WAIT["saved"])
    if not n:
        raise Problem("Premiere said the caption track was added, but the saved project has no captions in it. "
                      "Save the project in Premiere (Ctrl+S), then press Continue.")
    say("%d captions written by Premiere." % n)
    return project


def shorts_project(folder, name, say=print, start=None):
    """Shorts sent to Premiere (premiere_export) as a project of their own: "<name> - Shorts.prproj" in that folder,
    made the first time, opened after that. The Shorts listed in its import.txt are imported
    as timelines (earlier ones in that project stay) and the project is saved.
    Returns (project path, Premiere's message)."""
    import premiere_install
    with open(os.path.join(folder, "import.txt"), encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        raise Problem("Nothing has been sent to Premiere yet.")
    program = exe()
    if not program and start is None:
        raise Problem("Premiere isn't installed on this PC. The timeline file is " + lines[0])
    if start is None:
        if not premiere_install.current():
            say("Putting the toolkit's Premiere panels in place…")
            r = premiere_install.install()
            if not r["ok"]:
                raise Problem("The toolkit's Premiere panels couldn't be put in place: " + " ".join(r["lines"][:-1]))
        start = lambda: launch([program])
    project = os.path.normpath(os.path.join(folder, "%s - Shorts.prproj" % name))
    with open(lines[0], encoding="utf-8") as f:
        count = f.read().count("<sequence ")         # Shorts in the timeline file

    fresh = not running() and not bridge.connected("uxp")
    if fresh:
        say("Starting Premiere…")
        start()
    end = time.time() + (WAIT["premiere"] if fresh else WAIT["panel"])
    while not bridge.panel("uxp") and time.time() < end:
        time.sleep(0.5)
    if not bridge.panel("uxp"):
        raise Problem(SPEECH_HELP if running() else "Premiere didn't start. Open it yourself, then try again.")
    say("Premiere is putting the Shorts into %s…" % os.path.basename(project))
    ok, msg = bridge.call("uxp", dict(op="shortsproject", project=project, exists=os.path.exists(project),
                                      xml=lines[0], srts=lines[1:], count=count), WAIT["ask"] + 300)
    if not ok:
        raise Problem("Premiere couldn't make the Shorts project. " + (msg or SPEECH_HELP))
    return project, place_animated(folder, project, say) or msg


def place_animated(folder, project, say=print):
    """Put the animated captions on the timelines just imported (premiere/place-captions.jsx,
    about a quarter of a second per caption). Returns Premiere's message, or None if this send
    has none. The small wrapper script carries the paths: panel scripts take no arguments."""
    import ae_template
    import runtime
    listing = os.path.join(folder, "animated.txt")
    if not os.path.exists(listing):
        return None
    with open(listing, encoding="utf-8") as f:
        rows = [l.rstrip("\r\n").split("\t") for l in f if l.strip() and not l.startswith("BIN\t")]
    if not rows:
        return None
    end = time.time() + WAIT["captions_panel"]
    while not bridge.panel("cep") and time.time() < end:
        time.sleep(0.5)
    if not bridge.panel("cep"):
        raise Problem(CAPTIONS_HELP)
    n = 0
    for _, p in rows:
        with open(p, encoding="utf-8") as f:
            n += len(json.load(f))
    say("Premiere is placing %d animated captions (about %d min)…" % (n, n // 240 + 1))
    wrapper = os.path.join(folder, "place.jsx")
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write("var SHORTS_LIST = %s;\nvar SHORTS_MOGRT = %s;\n$.evalFile(File(%s));\n" % (
            json.dumps(listing), json.dumps(ae_template.MOGRT),
            json.dumps(os.path.join(runtime.RES, "premiere", "place-captions.jsx"))))
    ok, msg = bridge.call("cep", dict(op="script", project=project, sequence=rows[0][0], script=wrapper), 60 + n)
    if not ok:
        raise Problem("Premiere made the Shorts project, but couldn't place the animated captions. " + (msg or CAPTIONS_HELP))
    return msg
