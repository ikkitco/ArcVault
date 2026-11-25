"""
ArcVault - where every file lives.

Every script asks this module for file locations instead of building paths
itself, so the layout can change in one place.

Two modes:

  folder mode     (default) ArcVault runs from a plain folder, like ikkitco's dev
                  folder. Everything stays in that folder with today's names:
                  mtga_collection.csv, cache\\, exports\\, auto_export.log ...

  installed mode  the installer puts a marker file named "arcvault.installed"
                  next to the program. Then:
                    your files    -> Documents\\ArcVault  (arc_collection.csv ...)
                    working files -> %LOCALAPPDATA%\\ArcVault  (cache, window, logs)
                  On Linux the same split uses the XDG folders:
                    your files    -> ~/Documents/ArcVault (or XDG_DOCUMENTS_DIR)
                    cache         -> ~/.cache/arcvault
                    window, logs  -> ~/.local/share/arcvault

Overrides (both modes): ARCVAULT_DATA_DIR in the environment, or "data_dir" in
the settings file, moves your files (the "Save files to..." setting, later).
The exporter's --out option still wins for a single run.

Nothing here creates folders on import; call ensure_dirs() before writing.
"""

import json
import os
import sys

# Compiled into ArcVault.exe (Nuitka) or run as plain Python scripts?
# Careful: in a Nuitka build sys.executable is NOT the exe (it names a python.exe that doesn't
# exist), so the running exe comes from Nuitka's __compiled__.process_exe.
FROZEN = bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def _own_exe():
    c = globals().get("__compiled__")
    exe = getattr(c, "process_exe", None) or getattr(c, "original_argv0", None) or sys.argv[0]
    return os.path.abspath(exe)


EXE = _own_exe() if FROZEN else None
PROGRAM_DIR = os.path.dirname(EXE) if FROZEN else os.path.dirname(os.path.abspath(__file__))
INSTALLED_MARKER = "arcvault.installed"
APP_NAME = "ArcVault"

if sys.platform.startswith("win"):
    PLATFORM = "windows"
elif sys.platform.startswith("linux"):
    PLATFORM = "linux"
else:
    PLATFORM = "other"          # not supported (Windows and Linux only); treated like Linux

# Your files, by role. Folder mode keeps today's names; installed mode uses the arc_ names.
_NAMES = {
    "folder": {
        "collection": "mtga_collection.csv",
        "collection_full": "mtga_collection_full.csv",
        "collection_txt": "mtga_collection.txt",
        "inventory": "mtga_inventory.csv",
    },
    "installed": {
        "collection": "arc_collection.csv",
        "collection_full": "arc_collection_full.csv",
        "collection_txt": "arc_collection.txt",
        "inventory": "arc_inventory.csv",
    },
}


# ---------------------------------------------------------------- platform folders

def _windows_documents():
    """The real Documents folder, even when OneDrive or the user has moved it."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        fid = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                   (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
            path = out.value
            ctypes.windll.ole32.CoTaskMemFree(out)
            if path:
                return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _linux_documents(env):
    """XDG_DOCUMENTS_DIR from ~/.config/user-dirs.dirs, else ~/Documents."""
    home = os.path.expanduser("~")
    cfg = os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"), "user-dirs.dirs")
    try:
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("XDG_DOCUMENTS_DIR="):
                    val = line.split("=", 1)[1].strip().strip('"').replace("$HOME", home)
                    if val and os.path.abspath(val) != os.path.abspath(home):
                        return val
    except OSError:
        pass
    return os.path.join(home, "Documents")


def _installed_layout(platform, env):
    """(data_dir, work_dir, cache_dir) for an installed copy."""
    home = os.path.expanduser("~")
    if platform == "windows":
        local = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        work = os.path.join(local, APP_NAME)
        return os.path.join(_windows_documents(), APP_NAME), work, os.path.join(work, "cache")
    data_home = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    cache_home = env.get("XDG_CACHE_HOME") or os.path.join(home, ".cache")
    return (os.path.join(_linux_documents(env), APP_NAME),
            os.path.join(data_home, "arcvault"),
            os.path.join(cache_home, "arcvault"))


# ---------------------------------------------------------------- the layout

class Layout:
    """Every location ArcVault uses. Built once at import as `paths.L`; tests build their own."""

    def __init__(self, program_dir=PROGRAM_DIR, mode=None, platform=PLATFORM, env=None, data_default=None):
        self._args = (program_dir, mode, platform, env, data_default)
        env = os.environ if env is None else env
        self.program_dir = program_dir
        self.mode = mode or ("installed" if os.path.isfile(os.path.join(program_dir, INSTALLED_MARKER)) else "folder")
        self.platform = platform
        if self.mode == "installed":
            data, work, cache = _installed_layout(platform, env)
            self.work_dir = work
            self.cache_dir = cache
            self.window_dir = os.path.join(work, "window")
            self.log_dir = os.path.join(work, "logs")
            self.settings_file = os.path.join(work, "settings.json")
        else:
            data = program_dir
            self.work_dir = program_dir
            self.cache_dir = os.path.join(program_dir, "cache")
            self.window_dir = os.path.join(program_dir, "cache", "window")
            self.log_dir = program_dir
            self.settings_file = os.path.join(self.window_dir, "arcvault_settings.json")
        data = data_default or data
        self.default_data_dir = data
        override = env.get("ARCVAULT_DATA_DIR") or self._setting("data_dir")
        self.data_dir = os.path.abspath(os.path.expanduser(override)) if override else data
        self.names = dict(_NAMES[self.mode])

    def reload(self):
        """Read the settings again (after "Save files to..." changed). Updates this object in place,
        so every module holding `L` sees the new locations."""
        self.__init__(*self._args)
        return self

    def synced_by(self, path=None):
        """'OneDrive', 'Dropbox', ... if `path` (default: your files) is inside a syncing folder, else None."""
        p = os.path.abspath(path or self.data_dir).lower()
        roots = [os.environ.get(k) for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
        if any(r and p.startswith(os.path.abspath(r).lower()) for r in roots):
            return "OneDrive"
        parts = p.replace("\\", "/").split("/")
        for name, label in (("onedrive", "OneDrive"), ("dropbox", "Dropbox"), ("google drive", "Google Drive"),
                            ("icloud drive", "iCloud"), ("icloudrive", "iCloud")):
            if any(x == name or x.startswith(name + " -") for x in parts):
                return label
        return None

    def _setting(self, key):
        try:
            with open(self.settings_file, encoding="utf-8") as f:
                return json.load(f).get(key)
        except (OSError, ValueError, AttributeError):
            return None

    # your files
    def file(self, role, data_dir=None):
        """Full path of one of your files: collection, collection_full, collection_txt, inventory."""
        return os.path.join(data_dir or self.data_dir, self.names[role])

    def exports_dir(self, data_dir=None):
        return os.path.join(data_dir or self.data_dir, "exports")

    def snapshots_dir(self, data_dir=None):
        return os.path.join(data_dir or self.data_dir, "snapshots")

    def changes_dir(self, data_dir=None):
        return os.path.join(data_dir or self.data_dir, "changes")

    def decks_dir(self, data_dir=None):
        """Decks you save in the Decks tab, one Arena-format .txt file each."""
        return os.path.join(data_dir or self.data_dir, "decks")

    # working files
    def cache(self, name=""):
        return os.path.join(self.cache_dir, name) if name else self.cache_dir

    def log(self, name):
        """auto_export.log, arcvault_app.log, ..."""
        return os.path.join(self.log_dir, name)

    def program(self, *parts):
        """Something shipped with ArcVault: ArcVault.html, brand\\arcvault.ico, the exporter..."""
        return os.path.join(self.program_dir, *parts)

    def daemon_exe(self):
        """The reader's executable, newest published build first; None if missing."""
        import glob
        exe = "mtga-tracker-daemon.exe" if self.platform == "windows" else "mtga-tracker-daemon"
        if self.mode == "installed":
            p = os.path.join(self.program_dir, "daemon", exe)
            return p if os.path.isfile(p) else None
        cand = [p for p in glob.glob(os.path.join(self.program_dir, "**", exe), recursive=True)
                if os.path.isfile(p)]
        cand.sort(key=lambda p: ("publish" not in p.lower(), -os.path.getmtime(p)))
        return cand[0] if cand else None

    def ensure_dirs(self):
        for d in (self.data_dir, self.cache_dir, self.window_dir, self.log_dir):
            os.makedirs(d, exist_ok=True)

    def describe(self):
        """For logs and --where: one line per location."""
        synced = self.synced_by()
        return "\n".join([
            f"mode:      {self.mode} ({self.platform})" + (" - TEST SANDBOX" if os.environ.get("ARCVAULT_SANDBOX") else ""),
            f"program:   {self.program_dir}" + (f"   (running {os.path.basename(EXE)})" if FROZEN else ""),
            f"files:     {self.data_dir}" + (f"   (synced by {synced})" if synced else ""),
            f"cache:     {self.cache_dir}",
            f"window:    {self.window_dir}",
            f"logs:      {self.log_dir}",
            f"settings:  {self.settings_file}",
        ])


# ---------------------------------------------------------------- starting ArcVault's parts

SCRIPTS = {"app": "arcvault_app.py", "watcher": "mtga_auto_export.py", "export": "mtga_collection_export.py"}


def python_exe(windowless):
    """pythonw.exe (no console window) or python.exe next to the running interpreter."""
    d = os.path.dirname(sys.executable)
    names = ("pythonw.exe", "python.exe") if windowless else ("python.exe", "pythonw.exe")
    for n in names:
        p = os.path.join(d, n)
        if os.path.isfile(p):
            return p
    return sys.executable


def launch(role, *args, windowless=True):
    """The command line that starts one part of ArcVault: role 'app', 'watcher' or 'export'.
    As scripts:  [pythonw.exe, <folder>\\mtga_auto_export.py, ...]
    Compiled:    [<folder>\\ArcVault.exe, --watcher, ...]   (one exe holds every part)"""
    if FROZEN:
        return [EXE] + ([] if role == "app" else ["--" + role]) + list(args)
    return [python_exe(windowless), os.path.join(PROGRAM_DIR, SCRIPTS[role])] + list(args)


def sandbox(root, platform=PLATFORM):
    """An installed layout rooted inside one test folder, so nothing touches the real
    Documents or LocalAppData:  root/Documents/ArcVault  and  root/LocalAppData/ArcVault."""
    root = os.path.abspath(root)
    env = {"LOCALAPPDATA": os.path.join(root, "LocalAppData"),
           "XDG_CACHE_HOME": os.path.join(root, "LocalAppData", "cache"),
           "XDG_DATA_HOME": os.path.join(root, "LocalAppData")}
    return Layout(mode="installed", platform=platform, env=env,
                  data_default=os.path.join(root, "Documents", APP_NAME))


# ARCVAULT_SANDBOX=<test folder>: run as an installed copy inside that folder (for testing the
# first-run screen and the history import without touching the real Documents / LocalAppData).
L = sandbox(os.environ["ARCVAULT_SANDBOX"]) if os.environ.get("ARCVAULT_SANDBOX") else Layout()

if __name__ == "__main__":
    # python arcvault_paths.py              -> where this copy keeps its files
    # python arcvault_paths.py --installed  -> where an installed copy would (checks the real Documents folder)
    # Prints only; never creates anything.
    if "--installed" in sys.argv:
        print(Layout(mode="installed").describe())
    else:
        print(L.describe())
