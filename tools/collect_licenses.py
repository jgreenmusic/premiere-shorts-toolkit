"""Build step: copy the licence text of every Python library the app ships into build/licenses.

MIT, BSD and Apache libraries ask that their licence text goes along with any copy of
them, and the app is a copy. PyInstaller keeps only some of the libraries' own
licence files, so this gathers them all, one folder per library:

    build/licenses/<library>-<version>/<the library's own licence files>
    build/licenses/INDEX.txt          library, version, licence, folder

The spec bundles build/licenses as licenses/ next to THIRD-PARTY-NOTICES.md.
Libraries are found from the modules the last PyInstaller run actually packed
(build/pyi/ShortsToolkit/PYZ-00.toc and PYZ-01.toc), so nothing the app does not
ship is listed. Run by packaging/build-windows.cmd after PyInstaller's analysis;
by hand:

    .venv\\Scripts\\python tools\\collect_licenses.py
"""
import glob
import importlib.metadata as md
import os
import re
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "licenses")
EXTRA = os.path.join(ROOT, "packaging", "licenses-extra")   # texts for packages that ship none
TOCS = glob.glob(os.path.join(ROOT, "build", "pyi", "ShortsToolkit", "PYZ-*.toc"))
LICENSE_NAME = re.compile(r"(licen[cs]e|copying|notice|authors|copyright)", re.I)


def packed_modules():
    names = set()
    for toc in TOCS:
        with open(toc, encoding="utf-8") as f:
            names |= set(re.findall(r"\('([A-Za-z0-9_]+)(?:\.[^']*)?',\s*'", f.read()))
    # Libraries with compiled parts sit in folders next to the archive, not in it.
    internal = os.path.join(ROOT, "dist", "Shorts Toolkit", "_internal")
    if os.path.isdir(internal):
        names |= {n for n in os.listdir(internal) if os.path.isdir(os.path.join(internal, n))}
    return names


def licence_of(dist):
    m = dist.metadata
    text = m.get("License-Expression") or ""
    if not text:
        first = (m.get("License") or "").strip().splitlines()
        if first and len(first[0]) < 80:
            text = first[0]
    if not text:
        kinds = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License")]
        text = ", ".join(kinds)
    return text or "see the files in this folder"


def main():
    if not TOCS:
        sys.exit("No PyInstaller build found in build/pyi - build the app first.")
    owners = md.packages_distributions()
    modules = packed_modules()
    dists = {}
    for mod in modules:
        for name in owners.get(mod, []):
            try:
                d = md.distribution(name)
            except md.PackageNotFoundError:
                continue
            dists[d.metadata["Name"].lower()] = d
    for skip in ("pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile"):
        # The build tool itself. Only its small start-up code goes into the app, and its
        # licence (GPL with an exception) explicitly allows that in any program.
        dists.pop(skip, None)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    rows, missing = [], []
    for key in sorted(dists):
        d = dists[key]
        folder = "%s-%s" % (d.metadata["Name"], d.version)
        target = os.path.join(OUT, folder)
        os.makedirs(target)
        copied = 0
        for f in d.files or []:
            base = os.path.basename(str(f))
            in_meta = ".dist-info" in str(f) or "/licenses/" in str(f).replace("\\", "/")
            if in_meta and LICENSE_NAME.search(base) and not base.endswith((".py", ".pyc")):
                src = f.locate()
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(target, base))
                    copied += 1
        if not copied:
            # Some wheels keep the licence inside the package folder instead (onnxruntime).
            tops = {str(f).replace("\\", "/").split("/")[0] for f in d.files or []}
            for top in tops:
                pkg = os.path.join(str(d.locate_file(top)))
                if not os.path.isdir(pkg) or top.endswith((".dist-info", ".libs", "__pycache__")):
                    continue
                for base in os.listdir(pkg):
                    src = os.path.join(pkg, base)
                    if os.path.isfile(src) and LICENSE_NAME.search(base) and not base.endswith((".py", ".pyc")):
                        shutil.copy2(src, os.path.join(target, base))
                        copied += 1
        extra = os.path.join(EXTRA, d.metadata["Name"].lower().replace("-", "_"))
        if not copied and os.path.isdir(extra):
            for base in os.listdir(extra):
                shutil.copy2(os.path.join(extra, base), os.path.join(target, base))
                copied += 1
        if not copied:
            missing.append(folder)
        rows.append((d.metadata["Name"], d.version, licence_of(d), folder))
    with open(os.path.join(OUT, "INDEX.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("Python libraries inside Shorts Toolkit, with their licences.\n")
        f.write("Each folder here holds that library's own licence files.\n\n")
        for name, ver, lic, folder in rows:
            f.write("%-28s %-12s %s\n" % (name, ver, lic))
    print("licences of %d libraries copied to %s" % (len(rows), OUT))
    if missing:
        print("no licence file found in the package metadata of: " + ", ".join(missing))
        print("(their licence is still named in INDEX.txt; add the text by hand before a sale)")


if __name__ == "__main__":
    main()
