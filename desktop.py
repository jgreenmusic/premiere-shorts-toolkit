"""Shorts Toolkit as a desktop app: the same interface in its own window.

Starts the toolkit's local server on a free port and shows it in a native window
(Windows: Edge WebView2, built into Windows 10/11). Closing the window quits.
"""
import os
import socket
import sys
import threading

import runtime

runtime.setup()

import app  # noqa: E402


def free_port():
    """The Premiere panels look for the toolkit on app.BRIDGE_PORTS, so use the first of
    those that's free; any free port only if all are taken."""
    for p in app.BRIDGE_PORTS:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    import webview
    port = int(os.environ.get("SHORTS_PORT") or free_port())
    server = app.make_server(port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    import remote
    remote.autostart(app.Handler)                       # phone/tablet access, if you switched it on

    window = webview.create_window("Shorts Toolkit", "http://127.0.0.1:%d/" % port,
                                   width=1480, height=940, min_size=(960, 640), background_color="#0E1014",
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

    app.DIALOG = dialog
    data = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ShortsToolkit", "webview")
    os.makedirs(data, exist_ok=True)
    webview.start(private_mode=False, storage_path=data)    # keep theme, tab and last project between runs
    app.stop_job()                                            # closing the window stops a running render
    server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
