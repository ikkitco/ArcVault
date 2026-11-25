"""Copy the licence files of the Python parts bundled into ArcVault.exe into one folder.

build.bat runs this while it assembles dist\\ArcVault, so every installed copy carries the
licence texts of what it contains:

    python tools\\collect_licences.py dist\\ArcVault\\licenses

It starts from ArcVault's own Python packages, follows their requirements, and copies each
package's LICENSE / COPYING / NOTICE files, plus Python's own licence and Nuitka's. It also
writes licenses\\README.txt listing every part and its licence.
"""
import importlib.metadata as md
import os
import re
import shutil
import sys

TOP = ["pywebview", "pystray", "pillow"]           # what build.bat installs for ArcVault itself
ALSO = ["nuitka"]                                   # the compiler, whose runtime helpers are in the exe
LICENCE_FILE = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors)[^/]*$", re.I)


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements(dist):
    """Names of the packages this one needs on Windows (extras and other platforms skipped)."""
    out = []
    for req in dist.requires or []:
        name, _, marker = req.partition(";")
        marker = marker.strip()
        if "extra ==" in marker:
            continue
        if marker and ("sys_platform" in marker or "platform_system" in marker or "os_name" in marker):
            m = marker.replace(" ", "")
            if not any(x in m for x in ('=="win32"', "=='win32'", '=="Windows"', "=='Windows'", '=="nt"', "=='nt'")):
                continue
        out.append(re.split(r"[\s<>=!~\[(]", name.strip(), 1)[0])
    return out


def licence_name(dist):
    meta = dist.metadata
    for key in ("License-Expression", "License"):
        v = (meta.get(key) or "").strip()
        if v and v.upper() != "UNKNOWN" and len(v) < 80 and "\n" not in v:
            return v
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License ::"):
            return c.split("::")[-1].strip()
    return "see the files in this folder"


def main(out):
    os.makedirs(out, exist_ok=True)
    seen, todo, rows = set(), [norm(n) for n in TOP + ALSO], []
    while todo:
        name = todo.pop(0)
        if name in seen:
            continue
        seen.add(name)
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            continue                     # only needed on other Python versions, so not bundled
        pkg = f"{dist.metadata['Name']}-{dist.version}"
        dest = os.path.join(out, pkg)
        copied = 0
        for f in dist.files or []:
            if LICENCE_FILE.search(str(f).replace("\\", "/")):
                src = f.locate()
                if os.path.isfile(src):
                    os.makedirs(dest, exist_ok=True)
                    shutil.copyfile(src, os.path.join(dest, os.path.basename(str(f))))
                    copied += 1
        rows.append((dist.metadata["Name"], dist.version, licence_name(dist) + ("" if copied else " (no licence file in the package)")))
        if name not in [norm(n) for n in ALSO]:
            todo += [norm(r) for r in requirements(dist)]
    # Python itself (its runtime is inside the program folder)
    for cand in ("LICENSE.txt", "LICENSE"):
        p = os.path.join(sys.base_prefix, cand)
        if os.path.isfile(p):
            os.makedirs(os.path.join(out, "Python"), exist_ok=True)
            shutil.copyfile(p, os.path.join(out, "Python", "LICENSE.txt"))
            break
    rows.append(("Python", sys.version.split()[0], "PSF License"))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("Licences of the parts bundled with ArcVault\n")
        f.write("ArcVault itself is licensed under the GNU GPL v3: see LICENSE.txt in the program folder.\n")
        f.write("The reader (daemon folder) is GPL v3 too: see daemon\\LICENSE-mtga-tracker-daemon.txt.\n")
        f.write("Each folder here holds the licence files of one bundled Python part.\n\n")
        for n, v, lic in sorted(rows, key=lambda r: r[0].lower()):
            f.write(f"{n} {v}: {lic}\n")
    print(f"Licences: {len(rows)} parts listed in {os.path.join(out, 'README.txt')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("dist", "ArcVault", "licenses"))
