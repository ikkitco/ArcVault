"""
ArcVault - "bring in your history".

Copies a folder-mode ArcVault (or the old MTGA Collection Exporter folder) into
an installed ArcVault's places:

    mtga_collection.csv        -> Documents\\ArcVault\\arc_collection.csv
    mtga_collection_full.csv   -> Documents\\ArcVault\\arc_collection_full.csv
    mtga_collection.txt        -> Documents\\ArcVault\\arc_collection.txt
    mtga_inventory.csv         -> Documents\\ArcVault\\arc_inventory.csv   (merged if one exists)
    snapshots\\, changes\\, exports\\  -> the same folders under Documents\\ArcVault
    cache\\ (Scryfall card data) -> %LOCALAPPDATA%\\ArcVault\\cache  (saves the first download)
    cache\\window\\ (theme etc.)  -> %LOCALAPPDATA%\\ArcVault\\window
    cache\\window\\arcvault_settings.json -> %LOCALAPPDATA%\\ArcVault\\settings.json (merged)

Rules:
  * COPY only. The old folder is never changed, moved or deleted.
  * Never overwrite your newer data: a collection file that is newer in the new
    place is kept; history (inventory) is merged row by row; snapshots and change
    files that already exist are skipped.
  * Every copied CSV is checked afterwards (same number of rows); other files by size.
  * A report is written to Documents\\ArcVault\\import_report.txt.

Command line (for testing; ArcVault's window will offer a button later):
    python arcvault_migrate.py --from "D:\\old\\folder" --dry-run
    python arcvault_migrate.py --from "D:\\old\\folder" --sandbox "D:\\test"
    python arcvault_migrate.py --from "D:\\old\\folder" --real   (the installed places)
    python arcvault_migrate.py --find          (lists old folders ArcVault can see)
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time

import arcvault_paths as paths

OLD_NAMES = paths._NAMES["folder"]
ROLES = ("collection", "collection_full", "collection_txt", "inventory")
FOLDERS = ("snapshots", "changes", "exports")
CACHE_SKIP = {"window", "session_baseline.csv"}          # per-session or copied separately


# ---------------------------------------------------------------- finding old folders

def looks_like_old_folder(folder):
    """True if `folder` holds a folder-mode export (collection or inventory file)."""
    return bool(folder) and any(os.path.isfile(os.path.join(folder, OLD_NAMES[r]))
                                for r in ("collection", "inventory"))


def _shortcut_folders():
    """Working folders of ArcVault / MTGA shortcuts on the Desktop and in Startup (Windows)."""
    if paths.PLATFORM != "windows":
        return []
    ps = (
        "$sh = New-Object -ComObject WScript.Shell; "
        "$places = @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Desktop')); "
        "foreach ($p in $places) { Get-ChildItem -LiteralPath $p -Filter *.lnk -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -match 'ArcVault|MTGA' } | "
        "ForEach-Object { $sh.CreateShortcut($_.FullName).WorkingDirectory } }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


def find_old_folders(layout=None):
    """Old folders worth offering, newest export first. Never includes the new data folder."""
    layout = layout or paths.L
    seen, found = set(), []
    for f in _shortcut_folders() + [layout.program_dir]:
        f = os.path.abspath(f)
        if f.lower() in seen or os.path.abspath(layout.data_dir).lower() == f.lower():
            continue
        seen.add(f.lower())
        if looks_like_old_folder(f):
            found.append(f)
    def newest(f):
        ts = [os.path.getmtime(os.path.join(f, OLD_NAMES[r])) for r in ROLES
              if os.path.isfile(os.path.join(f, OLD_NAMES[r]))]
        return max(ts, default=0)
    return sorted(found, key=newest, reverse=True)


# ---------------------------------------------------------------- helpers

def _csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1          # minus the header


def _copy(src, dst):
    """Copy via a temporary name so a half-written file never appears under the real name."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".importing"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def _verify(src, dst):
    if not os.path.isfile(dst):
        return "missing after copy"
    if src.lower().endswith(".csv"):
        a, b = _csv_rows(src), _csv_rows(dst)
        return None if a == b else f"row count differs ({a} vs {b})"
    a, b = os.path.getsize(src), os.path.getsize(dst)
    return None if a == b else f"size differs ({a} vs {b} bytes)"


def _merge_inventory(src, dst):
    """History rows from both files, no duplicates, oldest first. Returns rows added."""
    def read(p):
        with open(p, encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            return list(r.fieldnames or []), list(r)
    s_cols, s_rows = read(src)
    d_cols, d_rows = read(dst)
    cols = d_cols + [c for c in s_cols if c not in d_cols]
    key = lambda row: tuple((c, row.get(c, "") or "") for c in cols)
    have = {key(r) for r in d_rows}
    new = [r for r in s_rows if key(r) not in have]
    if not new:
        return 0
    merged = sorted(d_rows + new, key=lambda r: r.get("Date", ""))
    tmp = dst + ".importing"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged)
    os.replace(tmp, dst)
    return len(new)


# ---------------------------------------------------------------- the import

def plan(src, layout=None):
    """What an import would do, without doing it: a list of (action, source, destination, note)."""
    layout = layout or paths.L
    src = os.path.abspath(src)
    steps = []
    if os.path.abspath(layout.data_dir).lower() == src.lower():
        raise ValueError("That folder is already where ArcVault keeps your files.")
    if not looks_like_old_folder(src):
        raise ValueError(f"No ArcVault files found in {src} (looked for {OLD_NAMES['collection']}).")

    for role in ROLES:
        s, d = os.path.join(src, OLD_NAMES[role]), layout.file(role)
        if not os.path.isfile(s):
            continue
        if role == "inventory" and os.path.isfile(d):
            steps.append(("merge", s, d, "history rows merged"))
        elif os.path.isfile(d) and os.path.getmtime(d) >= os.path.getmtime(s):
            steps.append(("keep", s, d, "the new place already has a newer copy"))
        else:
            steps.append(("copy", s, d, ""))

    for name in FOLDERS:
        sd = os.path.join(src, name)
        dd = os.path.join(layout.data_dir, name)
        for root, _, files in os.walk(sd):
            for fn in files:
                s = os.path.join(root, fn)
                d = os.path.join(dd, os.path.relpath(s, sd))
                if name == "exports":            # rebuilt by every export: take them only if missing or older
                    if os.path.isfile(d) and os.path.getmtime(d) >= os.path.getmtime(s):
                        continue
                elif os.path.isfile(d):
                    continue                     # snapshots / changes are dated: never replace one
                steps.append(("copy", s, d, ""))

    sc = os.path.join(src, "cache")
    if os.path.isdir(sc):
        for fn in sorted(os.listdir(sc)):
            s = os.path.join(sc, fn)
            if fn in CACHE_SKIP or not os.path.isfile(s):
                continue
            d = layout.cache(fn)
            if not os.path.isfile(d):
                steps.append(("copy", s, d, "cached card data (saves the first download)"))

    sw = os.path.join(sc, "window")
    if os.path.isdir(sw):
        # The window may be open (importing from the first-run screen), so its profile can't be
        # replaced now: copy next to it, and ArcVault swaps it in the next time it starts.
        staged = layout.window_dir + ".imported"
        if not os.path.isdir(layout.window_dir):
            steps.append(("copytree", sw, layout.window_dir, "window settings (theme etc.)"))
        elif not os.path.isdir(staged) and not os.path.isfile(os.path.join(layout.work_dir, "window.from_import")):
            steps.append(("copytree", sw, staged, "window settings (theme etc.), used from the next start"))
    ss = os.path.join(sw, "arcvault_settings.json")
    if os.path.isfile(ss):
        steps.append(("settings", ss, layout.settings_file, "settings merged (yours in the new place win)"))
    return steps


def summary(steps):
    """Counts for the first-run screen: files, snapshots, changes, exports, cache, window."""
    c = {"files": 0, "snapshots": 0, "changes": 0, "exports": 0, "cache": 0, "window": 0, "kept": 0}
    for action, s, d, _ in steps:
        if action == "keep":
            c["kept"] += 1
        elif action in ("copytree", "settings"):
            c["window"] = 1
        else:
            parts = s.replace("\\", "/").split("/")
            kind = parts[-2] if len(parts) > 1 else ""
            c[kind if kind in ("snapshots", "changes", "exports", "cache") else "files"] += 1
    return c


def run(src, layout=None, dry_run=False, log=print, progress=None):
    """Do the import. Returns (ok, report_text). progress(done, total) is called after each step."""
    layout = layout or paths.L
    steps = plan(src, layout)
    lines = [f"ArcVault - bring in your history ({time.strftime('%Y-%m-%d %H:%M')})",
             f"From: {os.path.abspath(src)}", f"To:   {layout.data_dir}", f"      {layout.work_dir}", ""]
    problems, copied, merged = [], 0, 0
    for i, (action, s, d, note) in enumerate(steps):
        if progress and not dry_run:
            progress(i, len(steps))
        label = f"{os.path.relpath(s, src)} -> {d}"
        if dry_run:
            lines.append(f"[would {action}] {label}" + (f"  ({note})" if note else ""))
            continue
        try:
            if action == "copy":
                _copy(s, d)
                err = _verify(s, d)
                if err:
                    problems.append(f"{label}: {err}")
                copied += 1
            elif action == "merge":
                n = _merge_inventory(s, d)
                merged += n
                lines.append(f"[merged] {label}  (+{n} history rows)")
                continue
            elif action == "copytree":
                shutil.copytree(s, d, ignore=shutil.ignore_patterns("arcvault_settings.json", "*.lock",
                                                                   "lockfile", "LOCK"))
                copied += 1
            elif action == "settings":
                try:
                    with open(s, encoding="utf-8") as f:
                        old = json.load(f)
                except (OSError, ValueError):
                    old = {}
                try:
                    with open(d, encoding="utf-8") as f:
                        new = json.load(f)
                except (OSError, ValueError):
                    new = {}
                old.pop("data_dir", None)            # a folder-mode location means nothing here
                os.makedirs(os.path.dirname(d), exist_ok=True)
                with open(d, "w", encoding="utf-8") as f:
                    json.dump({**old, **new}, f)
            lines.append(f"[{action}] {label}")
        except Exception as e:
            problems.append(f"{label}: {e}")
            lines.append(f"[FAILED] {label}: {e}")
    keep = sum(1 for a, *_ in steps if a == "keep")
    lines += ["", f"{len(steps)} steps: {copied} copied, {merged} history rows merged, {keep} kept as they were."]
    if problems:
        lines += ["", "Problems (your old folder is untouched, so nothing is lost):"] + ["  " + p for p in problems]
    lines.append("Your old folder was not changed. Once you're happy, you can delete it yourself.")
    report = "\n".join(lines)
    if not dry_run:
        try:
            os.makedirs(layout.data_dir, exist_ok=True)
            with open(os.path.join(layout.data_dir, "import_report.txt"), "w", encoding="utf-8") as f:
                f.write(report + "\n")
        except OSError:
            pass
    log(report)
    return not problems, report


def main():
    ap = argparse.ArgumentParser(description="Copy an old ArcVault folder's history into the installed places.")
    ap.add_argument("--from", dest="src", help="the old folder (holds mtga_collection.csv)")
    ap.add_argument("--sandbox", help="test: import into this folder instead of the real Documents/LocalAppData")
    ap.add_argument("--dry-run", action="store_true", help="only list what would happen")
    ap.add_argument("--real", action="store_true",
                    help="import into the real Documents/LocalAppData places (only once ArcVault is installed)")
    ap.add_argument("--find", action="store_true", help="list old folders ArcVault can find")
    a = ap.parse_args()
    layout = paths.sandbox(a.sandbox) if a.sandbox else paths.Layout(mode="installed")
    if a.find or not a.src:
        found = find_old_folders(layout)
        print("Old ArcVault folders found:" if found else "No old ArcVault folders found.")
        for f in found:
            print("  " + f)
        if not a.src:
            return
    if not (a.sandbox or a.real or a.dry_run):
        sys.exit("Add --sandbox <test folder> to try it safely, or --real to import into the real places.")
    try:
        ok, _ = run(a.src, layout, dry_run=a.dry_run)
    except ValueError as e:
        sys.exit(str(e))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
