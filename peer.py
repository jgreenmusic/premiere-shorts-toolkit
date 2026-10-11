"""The Shorts Toolkit and Shorts Auto Run are two windows over the same project files.
This is how each knows the other is open (to hand a project over) and busy (so the two never
run a job at the same time on the same files).

Each program keeps one small file while it is open:
    %LOCALAPPDATA%\\ShortsToolkit\\open-toolkit.json / open-autorun.json
    {"pid": ..., "born": ..., "port": ..., "job": "Rendering 3 Shorts" or null}
A file left behind by a crash is ignored: the process it names is checked.
"""
import json
import os
import time

DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ShortsToolkit")
NAMES = {"toolkit": "Shorts Toolkit", "autorun": "Shorts Auto Run"}


def other(me):
    return "autorun" if me == "toolkit" else "toolkit"


def _path(who):
    return os.path.join(DIR, "open-%s.json" % who)


def _born(pid):
    """When that process started, or None if there is no such process."""
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:
        return None


def _write(who, d):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = _path(who) + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _path(who))
    except OSError:
        pass                                   # never worth stopping the app for


def _mine(who):
    """This process's own file, or a new one."""
    try:
        with open(_path(who), encoding="utf-8") as f:
            d = json.load(f)
        if d.get("pid") == os.getpid():
            return d
    except (OSError, ValueError):
        pass
    return dict(pid=os.getpid(), born=_born(os.getpid()), port=None, job=None, since=time.time())


def announce(who, port):
    """Say this program is open and where it listens."""
    d = _mine(who)
    d.update(port=port, job=None)
    _write(who, d)


def set_job(who, title):
    """Say what this program is working on (None = nothing)."""
    d = _mine(who)
    if d.get("job") != title:
        d["job"] = title
        _write(who, d)


def gone(who):
    """Called when the program closes."""
    try:
        with open(_path(who), encoding="utf-8") as f:
            if json.load(f).get("pid") != os.getpid():
                return                         # a second copy's file - leave it
        os.remove(_path(who))
    except (OSError, ValueError):
        pass


def read(who):
    """{pid, port, job} of that program if it is really running (and isn't this process), else None."""
    try:
        with open(_path(who), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    pid = d.get("pid")
    if not pid or pid == os.getpid():
        return None
    born = _born(pid)
    if born is None or (d.get("born") and abs(born - d["born"]) > 2):     # gone, or the number was reused
        return None
    return d


def busy_with(me):
    """What the OTHER program is working on right now, or None."""
    d = read(other(me))
    return (d.get("job") or None) if d else None


def tell(who, address, body, timeout=4):
    """POST to that program if it is open. Returns its answer, or None if it isn't there."""
    import urllib.request
    d = read(who)
    if not d or not d.get("port"):
        return None
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (d["port"], address), data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Shorts-Toolkit": "1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None
