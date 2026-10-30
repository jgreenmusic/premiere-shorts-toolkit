"""The animated caption template (.mogrt) for Premiere, built in After Effects.

Premiere's caption tracks can't animate, so a caption that animates AND stays editable in
Premiere is one clip of a Motion Graphics Template. premiere/ae/build-caption-mogrt.jsx makes
it; this file installs the fonts it can pick from and runs After Effects.

Learned on After Effects / Premiere 26.5 (2026-10-30):
- AfterFX.com -r script runs a script, starting After Effects if needed; AfterFX.exe -r does
  nothing in an open After Effects and quits a cold start.
- Edit > Preferences > Scripting & Expressions > "Allow Scripts to Write Files and Access
  Network" must be ticked by you: the script has to write the template.
- Sliders are 0-100 in Premiere whatever After Effects holds, and the font lock on a text
  control lives inside the template - so size is a scaled slider and font a dropdown.
"""
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

import style

USER_FONTS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
REG = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
HERE = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "premiere", "ae")
MOGRT = os.path.join(HERE, "Shorts Toolkit Caption.mogrt")
FONT_LIST = os.path.join(HERE, "fonts.json")      # the Font dropdown of that template, in order
HIGHLIGHT = dict(color=0, bigger=1, box=2, fill=3, none=4)      # the template's dropdowns, from 0
ANIMATION = dict(pop=0, bounce=1, fade=2, none=3)
SIZE = 2.4                                        # px per step of the template's Size slider
GAP = 0.03                                        # shorter than this isn't worth a clip


def template_fonts():
    with open(FONT_LIST, encoding="utf-8") as f:
        return json.load(f)


def clips(events, record, a, b, cfg):
    """One Short's captions as clips of the template: [{start, end (seconds in the Short), text,
    times, and every Essential Graphics value}]. record = what style.build recorded for spoken
    lines, events = its final events (screams and laughs come from those). One caption at a
    time, like a render: a clip ends where the next starts."""
    st = style.look(cfg)
    fonts = template_fonts()
    font = fonts.index(st["font"]) if st["font"] in fonts else 0
    base = dict(font=font, size=round(st["size"] / SIZE, 2), outline=st["outline"], outline_col=st["outline_col"],
                shadow=st["shadow"], height=round(100.0 * st["margin_v"] / 1920, 3), anim=ANIMATION.get(st.get("anim", "pop"), 0))
    items = []
    for r in record:
        if r["end"] > a and r["start"] < b:
            items.append(dict(base, start=r["start"], end=r["end"], text=" ".join(r["words"]), abs_times=r["times"],
                              hl=HIGHLIGHT.get(r["mode"], 0), hl_col=r["col"], text_col=r["text_col"], hl_text=r["hl_text"],
                              loud=bool(r["loud"])))
    for s, e, kind, text in events:
        if kind in ("Scream", "Laugh") and e > a and s < b:
            col = st["scream_col"] if kind == "Scream" else st["laugh_col"]
            px = st["scream_size"] if kind == "Scream" else int(st["size"] * 1.12)
            items.append(dict(base, start=s, end=e, text=re.sub(r"\{[^}]*\}", "", text), abs_times=[], hl=HIGHLIGHT["none"], anim=ANIMATION["none"],
                              size=round(px / SIZE, 2), hl_col=col, text_col=col, hl_text=col, loud=False))
    items.sort(key=lambda x: x["start"])
    out = []
    for i, c in enumerate(items):
        s, e = max(c["start"], a), min(c["end"], b)
        if i + 1 < len(items):
            e = min(e, items[i + 1]["start"])
        if e - s < GAP or not c["text"].strip():
            continue
        times = [max(0.0, t - s) for t in c.pop("abs_times")]
        c.update(start=round(s - a, 3), end=round(e - a, 3), times=" ".join("%.3f" % t for t in times + [e - s]))
        out.append(c)
    return out


def after_effects():
    """AfterFX.com of the newest After Effects, or None."""
    roots = {os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"} - {None, ""}
    found = [p for r in roots for p in glob.glob(os.path.join(r, "Adobe", "Adobe After Effects*", "Support Files", "AfterFX.com"))]
    return max(found, key=os.path.getmtime) if found else None


def build(log=print, wait=120):
    """Build the template again in the After Effects that is open (only needed to change the
    template or its font list). Writes MOGRT and FONT_LIST next to the build script."""
    com = after_effects()
    if not com:
        raise SystemExit("After Effects isn't installed on this PC.")
    work = tempfile.mkdtemp(prefix="shorts-ae-")
    script = os.path.join(work, "build-caption-mogrt.jsx")
    shutil.copy2(os.path.join(HERE, "build-caption-mogrt.jsx"), script)
    fl = fonts()
    done = os.path.join(work, "done.txt")
    with open(os.path.join(work, "build-caption-mogrt.json"), "w", encoding="utf-8") as f:
        # aep: After Effects only exports a template from a saved project
        json.dump(dict(out=work, done=done, aep=os.path.join(work, "caption.aep"), font=fl[0][1],
                       font_names=[x[0] for x in fl], font_ps=[x[1] for x in fl]), f)
    subprocess.Popen([com, "-r", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    end = time.time() + wait
    while not os.path.exists(done) and time.time() < end:
        time.sleep(1)
    if not os.path.exists(done):
        raise SystemExit("After Effects didn't answer. Open it, tick Edit > Preferences > Scripting & Expressions > "
                         "Allow Scripts to Write Files and Access Network, then try again.")
    with open(done, encoding="utf-8") as f:
        result = f.read()
    log(result)
    if not result.startswith("OK"):
        raise SystemExit("After Effects couldn't build the template.")
    shutil.copy2(os.path.join(work, "Shorts Toolkit Caption.mogrt"), MOGRT)
    with open(FONT_LIST, "w", encoding="utf-8") as f:
        json.dump([x[0] for x in fl], f, indent=0)
    return MOGRT


def postscript_name(path):
    """The font's PostScript name (name table id 6): what After Effects calls it."""
    with open(path, "rb") as f:
        data = f.read()
    tables = struct.unpack(">H", data[4:6])[0]
    for i in range(tables):
        tag, _, offset, _ = struct.unpack(">4sLLL", data[12 + i * 16:28 + i * 16])
        if tag != b"name":
            continue
        _, count, strings = struct.unpack(">HHH", data[offset:offset + 6])
        for n in range(count):
            pid, _, _, nid, length, pos = struct.unpack(">6H", data[offset + 6 + n * 12:offset + 18 + n * 12])
            if nid == 6:
                raw = data[offset + strings + pos:offset + strings + pos + length]
                return raw.decode("utf-16-be" if pid in (0, 3) else "latin-1")
    return None


def fonts():
    """[(name shown, PostScript name, file)] of every caption font the toolkit offers."""
    out = []
    for name in style.font_list():
        p = style.font_path(name)
        ps = postscript_name(p) if p else None
        if ps:
            out.append((name, ps, p))
    return out


def install_fonts(log=print):
    """Put the toolkit's own fonts in Windows for this user (no admin rights), so After Effects
    and Premiere can draw them. Fonts Windows already has are left alone."""
    import winreg
    os.makedirs(USER_FONTS, exist_ok=True)
    new = 0
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG, 0, winreg.KEY_SET_VALUE) as key:
        for name, _, path in fonts():
            if not path.startswith(style.FONTS):
                continue                             # a Windows font already
            dst = os.path.join(USER_FONTS, os.path.basename(path))
            if not os.path.exists(dst):
                shutil.copy2(path, dst)
                new += 1
            winreg.SetValueEx(key, name + " (TrueType)", 0, winreg.REG_SZ, dst)
    log("  %d font(s) installed for this user" % new)
    return new
