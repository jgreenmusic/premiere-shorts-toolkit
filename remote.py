"""Phone & tablet companion: a second, separate listener for your other devices.

Off until you switch it on in the desktop app. It listens on port 8766 on your home
network / Tailscale; the app window keeps its own private loopback listener.

Every request on the remote listener must come from a PAIRED device: you pair a phone
by entering the 6-digit code (or scanning the QR code) shown on the PC. The phone then
gets a long random key in a cookie; only a hash of it is stored here, and you can
revoke any device. Remote devices can use the toolkit but can't open file dialogs,
open files or folders on the PC, or change these settings.
"""
import hashlib
import ipaddress
import secrets
import socket
import threading
import time

PORT = 8766
COOKIE = "stk"
_server = None
_fails = []                      # times of wrong codes (brute-force brake)
LOCK = threading.Lock()


def _settings():
    import app
    s = app.load_settings()
    r = s.setdefault("remote", {})
    r.setdefault("enabled", False)
    r.setdefault("devices", [])
    if not r.get("code"):
        r["code"] = "%06d" % secrets.randbelow(1_000_000)
    return s, r


def _save(s):
    import app
    app.save_settings(s)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def addresses():
    """[(kind, ip)] this PC can be reached at: Tailscale (100.64/10) and home network."""
    out = []
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        ips = []
    for ip in ips:
        a = ipaddress.ip_address(ip)
        if a in ipaddress.ip_network("100.64.0.0/10"):
            out.append(("Tailscale", ip))
        elif a.is_private and not a.is_loopback and not ip.startswith("169.254."):
            out.append(("Home network", ip))
    return sorted(set(out), key=lambda x: x[0] != "Home network")


def running():
    return _server is not None


def start(handler_cls):
    global _server
    with LOCK:
        if _server:
            return True
        from http.server import ThreadingHTTPServer
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", PORT), handler_cls)
        except OSError:
            return False
        srv.remote = True                       # the handler enforces pairing on this one
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        _server = srv
        return True


def stop():
    global _server
    with LOCK:
        if _server:
            _server.shutdown()
            _server.server_close()
            _server = None


def autostart(handler_cls):
    s, r = _settings()
    if r["enabled"]:
        start(handler_cls)


def set_enabled(on, handler_cls):
    s, r = _settings()
    r["enabled"] = bool(on)
    _save(s)
    if on:
        ok = start(handler_cls)
        if not ok:
            r["enabled"] = False
            _save(s)
            raise RuntimeError("Port %d is already in use on this PC." % PORT)
    else:
        stop()


def new_code():
    s, r = _settings()
    r["code"] = "%06d" % secrets.randbelow(1_000_000)
    _save(s)
    return r["code"]


def info():
    s, r = _settings()
    _save(s)
    urls = [dict(kind=k, url="http://%s:%d/" % (ip, PORT)) for k, ip in addresses()]
    qr = None
    if urls:
        try:
            import qrcode
            import qrcode.image.svg
            img = qrcode.make(urls[0]["url"] + "#code=" + r["code"], image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
            qr = img.to_string(encoding="unicode")
        except ImportError:
            pass
    return dict(enabled=r["enabled"], running=running(), port=PORT, code=r["code"], urls=urls, qr=qr,
                devices=[dict(id=d["id"], name=d["name"], added=d["added"], seen=d.get("seen")) for d in r["devices"]])


def pair(code, name):
    """Trade the 6-digit code for a device key. None if wrong (with a brake on guessing)."""
    now = time.time()
    _fails[:] = [t for t in _fails if now - t < 300]
    if len(_fails) >= 10:
        raise PermissionError("Too many wrong codes - wait 5 minutes.")
    s, r = _settings()
    if not secrets.compare_digest(str(code).strip(), r["code"]):
        _fails.append(now)
        return None
    token = secrets.token_urlsafe(32)
    r["devices"].append(dict(id=secrets.token_hex(4), name=name[:80], added=now, seen=now, hash=_hash(token)))
    r["code"] = "%06d" % secrets.randbelow(1_000_000)     # a code works once
    _save(s)
    return token


def check(token):
    if not token:
        return False
    s, r = _settings()
    h = _hash(token)
    for d in r["devices"]:
        if secrets.compare_digest(d["hash"], h):
            if time.time() - (d.get("seen") or 0) > 600:
                d["seen"] = time.time()
                _save(s)
            return True
    return False


def revoke(device_id):
    s, r = _settings()
    r["devices"] = [d for d in r["devices"] if d["id"] != device_id]
    _save(s)
