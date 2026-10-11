"""Shorts Toolkit as a desktop app: the same interface in its own window.

    desktop.py                               the Shorts Toolkit
    desktop.py --autorun                     Shorts Auto Run (autorun.py): every step in one go, then your review
    desktop.py [--autorun] --project X [--tab render]     open on that project (and step)

Starts the local server on a free port and shows it in a native window (Windows: Edge
WebView2, built into Windows 10/11). Closing the window quits.
"""
import json
import os
import socket
import sys
import threading
from urllib.parse import quote

import runtime

runtime.setup()

import app  # noqa: E402
import peer  # noqa: E402


def free_port(wanted):
    """The first of these ports that's free; any free port only if all are taken.
    (The Premiere panels look for the toolkit on app.BRIDGE_PORTS.)"""
    for p in wanted:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def arguments(argv):
    """--autorun, --project PATH, --tab NAME. Anything else is ignored (never a crash on start)."""
    out = dict(autorun=False, project=None, tab=None)
    it = iter(argv)
    for a in it:
        if a == "--autorun":
            out["autorun"] = True
        elif a in ("--project", "--tab"):
            out[a[2:]] = next(it, None)
    if out["project"]:
        out["project"] = os.path.normpath(os.path.abspath(out["project"]))
    return out


def main():
    import webview
    a = arguments(sys.argv[1:])
    who = "autorun" if a["autorun"] else "toolkit"
    app.ME = who
    # already open? Show the project there instead of opening a second window.
    if (a["project"] or a["autorun"]) and peer.tell(who, "/api/goto", dict(path=a["project"], tab=a["tab"])) is not None:
        return 0
    if a["project"]:
        app.remember(a["project"])

    if a["autorun"]:
        import autorun
        port = int(os.environ.get("SHORTS_AUTO_PORT") or free_port(autorun.PORTS))
        server = autorun.make_server(port)
        title, page = "Shorts Auto Run", "auto"
    else:
        port = int(os.environ.get("SHORTS_PORT") or free_port(app.BRIDGE_PORTS))
        server = app.make_server(port)
        title, page = "Shorts Toolkit", ""
        import remote
        remote.autostart(app.Handler)                   # phone/tablet access, if you switched it on
    threading.Thread(target=server.serve_forever, daemon=True).start()
    peer.announce(who, port)

    url = "http://127.0.0.1:%d/%s" % (port, page)
    if a["project"]:
        url += "?project=" + quote(a["project"]) + ("#" + a["tab"] if a["tab"] in app.STEPS else "")
    window = webview.create_window(title, url, width=1480, height=940, min_size=(960, 640), background_color="#0E1014",
                                   text_select=True)     # pywebview blocks selecting text by default - the log must be copyable

    def dialog(kind):
        FD = getattr(webview, "FileDialog", None)
        if kind == "folder":
            mode = FD.FOLDER if FD else webview.FOLDER_DIALOG
            types = ()
        else:
            mode = FD.OPEN if FD else webview.OPEN_DIALOG
            types = (("Premiere project (*.prproj)",) if kind == "project" else
                     ("Video (*.mp4;*.mov;*.mkv;*.m4v;*.webm;*.avi;*.flv;*.ts)", "All files (*.*)"))
        res = window.create_file_dialog(mode, file_types=types)
        if not res:
            return None
        p = res[0] if isinstance(res, (list, tuple)) else res
        return os.path.normpath(p)

    def show(path, tab=None, reload=False):
        """The other window hands a project over (bring this window forward), or says it changed
        something in the project this window shows (just read it again)."""
        try:
            if reload:
                window.evaluate_js("(window.projectChanged && projectChanged(%s), null)" % json.dumps(path))
                return
            if path:
                window.evaluate_js("(window.gotoProject && gotoProject(%s, %s), null)" % (json.dumps(path), json.dumps(tab)))
            window.restore()
            window.show()
            window.on_top = True                         # Windows only lets a window jump forward this way
            window.on_top = False
        except Exception:
            app.note_error("showing a project from the other window")

    app.DIALOG = dialog
    app.SHOW = show
    data = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ShortsToolkit",
                        "webview-autorun" if a["autorun"] else "webview")
    os.makedirs(data, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=data)    # keep theme, tab and last project between runs
    finally:
        peer.gone(who)
    app.stop_job()                                            # closing the window stops a running render
    server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
