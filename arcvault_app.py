"""
ArcVault - desktop window
-------------------------
Opens ArcVault.html in its own window (no browser) and feeds it the latest export
from this folder. While the window is open it checks every 20 seconds for a newer
export (e.g. from the auto-export watcher) and reloads it.

Tray icon (by the clock): while auto-export is on, closing the window keeps ArcVault
running there. The icon's dot shows the auto-export state; right-click for Open,
Export now, Auto-export on/off and Quit. Quit turns auto-export off.

  python arcvault_app.py             open the window
  python arcvault_app.py --tray      start in the tray with auto-export on (Start with Windows uses this)
  python arcvault_app.py --shortcut  add an "ArcVault" shortcut to the Desktop and this folder

Needs: pywebview, pystray, pillow (ArcVault setup.bat installs them). Windows draws
the page with WebView2, which is part of Windows 10/11.
"""
import ctypes
import json
import os
import socket
import threading
import subprocess
import sys
import time
import traceback
from pathlib import Path

VERSION = "0.5.1"
import arcvault_paths as paths
from arcvault_paths import L as P                         # every file location comes from here

HERE = P.program_dir                                      # where ArcVault's own files live
PAGE = P.program("ArcVault.html")
ICON = P.program("brand", "arcvault.ico")
LOG = P.log("arcvault_app.log")
STORAGE = P.window_dir                                    # theme choice etc. survive restarts
TITLE = "ArcVault"
APP_ID = "ArcVault.Desktop"
APP_PORT = 6852                                           # one ArcVault at a time: a 2nd start shows the 1st
SETTINGS = P.settings_file
STARTUP_LNK = "ArcVault.lnk"                              # in the Windows Startup folder
OLD_STARTUP_LNK = "MTGA Auto-Export.lnk"                  # what Auto-export ON.bat used to create
# newest file wins; the full list first because it powers Sets / Missing / Deck check
FILES = {"collection": ["collection_full", "collection"],     # roles in arcvault_paths
         "inventory": ["inventory"]}


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + msg + "\n")
    except OSError:
        pass


def message_box(text):
    """A visible error even when started without a console (pythonw)."""
    log(text)
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10)
    else:
        print(text)


def _pick(roles):
    for r in roles:
        p = P.file(r)
        if os.path.isfile(p):
            return p
    return None


def _when(ts):
    t = time.localtime(ts)
    return f"{t.tm_mday} {time.strftime('%b, %H:%M', t)}"


def _watcher():
    import mtga_auto_export as w                         # same folder
    return w


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    s = load_settings()
    s.update(kw)
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except OSError:
        pass


def _startup_dir():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def _make_lnk(path, cmd, desc):
    """A Windows shortcut that runs `cmd` (a list from arcvault_paths.launch)."""
    q = lambda x: x.replace("'", "''")
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(path)}'); "
              f"$s.TargetPath = '{q(cmd[0])}'; "
              f"$s.Arguments = '{q(subprocess.list2cmdline(cmd[1:]))}'; "
              f"$s.WorkingDirectory = '{q(HERE)}'; "
              f"$s.IconLocation = '{q(ICON)}'; "
              f"$s.Description = '{q(desc)}'; "
              "$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0, (r.stderr or r.stdout)


def startup_enabled():
    d = _startup_dir()
    return os.name == "nt" and (os.path.isfile(os.path.join(d, STARTUP_LNK)) or os.path.isfile(os.path.join(d, OLD_STARTUP_LNK)))


def set_startup(on):
    """Start with Windows = open ArcVault in the tray with auto-export on. Returns (ok, message)."""
    if os.name != "nt":
        return False, "Start with Windows only works on Windows."
    d = _startup_dir()
    try:
        if os.path.isfile(os.path.join(d, OLD_STARTUP_LNK)):
            os.remove(os.path.join(d, OLD_STARTUP_LNK))  # the watcher-only shortcut from the .bat
    except OSError:
        pass
    if not on:
        try:
            if os.path.isfile(os.path.join(d, STARTUP_LNK)):
                os.remove(os.path.join(d, STARTUP_LNK))
            return True, "ArcVault won't start with Windows."
        except OSError as e:
            return False, f"Couldn't remove the Startup shortcut: {e}"
    ok, err = _make_lnk(os.path.join(d, STARTUP_LNK), paths.launch("app", "--tray"),
                        "ArcVault - starts in the tray with auto-export on")
    return (True, "ArcVault will start with Windows, in the tray, with auto-export on.") if ok \
        else (False, "Couldn't create the Startup shortcut:\n" + err)


def migrate_startup():
    """An old watcher-only Startup shortcut becomes the ArcVault (tray) one, once."""
    if os.name == "nt" and os.path.isfile(os.path.join(_startup_dir(), OLD_STARTUP_LNK)):
        ok, msg = set_startup(True)
        log("startup shortcut moved to ArcVault --tray: " + msg)


# A one-off export run by the window itself (auto-export off). Shown in the page like the switch.
ONEOFF = {"running": False, "step": "", "error": "", "error_at": None, "done_at": None, "result": ""}
ONEOFF_LOCK = threading.Lock()


def _oneoff_set(**kw):
    with ONEOFF_LOCK:
        ONEOFF.update(kw)


IMPORT = {}                     # "bring in your history" progress, for the first-run screen
IMPORT_LOCK = threading.Lock()


_BAD_NAME = '<>:"/\\|?*'


def _deck_path(name):
    """decks\\<name>.txt with characters Windows won't allow in a file name removed; None if nothing is left."""
    name = "".join("_" if (c in _BAD_NAME or ord(c) < 32) else c for c in str(name or "")).strip().rstrip(". ")[:80]
    if not name or name.upper().split(".")[0] in ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"):
        return None
    return os.path.join(P.decks_dir(), name + ".txt")


def _clipboard_text():
    if sys.platform == "win32":
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        u.GetClipboardData.restype = ctypes.c_void_p
        k.GlobalLock.argtypes = [ctypes.c_void_p]; k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [ctypes.c_void_p]
        for _ in range(10):                              # another program may have it open for a moment
            if u.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return None
        try:
            h = u.GetClipboardData(13)                   # CF_UNICODETEXT
            if not h:
                return ""
            p = k.GlobalLock(h)
            try:
                return ctypes.wstring_at(p) if p else ""
            finally:
                k.GlobalUnlock(h)
        finally:
            u.CloseClipboard()
    for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=True).stdout
        except (OSError, subprocess.SubprocessError):
            continue
    return None


# Card pictures. The page asks for one by Arena ID (or set + collector number); ArcVault looks the
# card up on Scryfall, downloads its picture once into cache\cards and hands back the local file,
# so each picture is fetched at most once and later views work offline. Requests go one at a time
# with a short gap, inside Scryfall's published limits.
_IMG_LOCK = threading.Lock()
_IMG_LAST = [0.0]
_IMG_HEADERS = {"User-Agent": f"ArcVault/{VERSION} (MTG Arena collection viewer)", "Accept": "application/json;q=0.9,*/*;q=0.8"}
_IMG_NONE_DAYS = 7                      # how long to remember "Scryfall has no picture for this card"


def _scryfall_get(url, timeout=12):
    import urllib.request
    wait = 0.11 - (time.time() - _IMG_LAST[0])
    if wait > 0:
        time.sleep(wait)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_IMG_HEADERS), timeout=timeout) as r:
            return r.read()
    finally:
        _IMG_LAST[0] = time.time()


def _card_image(aid, set_code, number):
    import re
    import urllib.error
    import urllib.parse
    key = re.sub(r"[^A-Za-z0-9_-]", "_", aid or f"{set_code}_{number}")
    if not key.strip("_"):
        return {"ok": False, "offline": False}
    folder = P.cache("cards")
    path = os.path.join(folder, key + ".jpg")
    none = path + ".none"
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return {"ok": True, "url": Path(path).as_uri()}
    if os.path.isfile(none) and time.time() - os.path.getmtime(none) < _IMG_NONE_DAYS * 86400:
        return {"ok": False, "offline": False}
    with _IMG_LOCK:
        if os.path.isfile(path) and os.path.getsize(path) > 0:          # fetched while we waited
            return {"ok": True, "url": Path(path).as_uri()}
        lookups = []
        if aid:
            lookups.append(f"https://api.scryfall.com/cards/arena/{urllib.parse.quote(aid)}")
        if set_code and number:
            lookups.append(f"https://api.scryfall.com/cards/{urllib.parse.quote(set_code.lower())}/{urllib.parse.quote(number)}")
        try:
            for u in lookups:
                try:
                    card = json.loads(_scryfall_get(u))
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        continue
                    log(f"card picture: Scryfall answered {e.code} for {u}")
                    return {"ok": False, "offline": True}
                img = (card.get("image_uris") or {}).get("normal") or \
                      ((card.get("card_faces") or [{}])[0].get("image_uris") or {}).get("normal")
                if not img:
                    continue
                data = _scryfall_get(img, timeout=20)
                os.makedirs(folder, exist_ok=True)
                with open(path + ".tmp", "wb") as f:
                    f.write(data)
                os.replace(path + ".tmp", path)
                return {"ok": True, "url": Path(path).as_uri()}
        except (urllib.error.URLError, OSError, ValueError) as e:
            if not getattr(_card_image, "warned", False):
                log(f"card picture: couldn't reach Scryfall ({e}); showing ArcVault's own cards")
                _card_image.warned = True
            return {"ok": False, "offline": True}
        os.makedirs(folder, exist_ok=True)
        open(none, "w").close()
        return {"ok": False, "offline": False}


class Api:
    """Called from the page as window.pywebview.api.<name>(). Methods starting with _ stay private."""

    # ----- the big auto-export switch: controls the background watcher -----
    def auto_status(self):
        """{'on': bool, 'startup': bool, ...watcher state} for the switch."""
        w = _watcher()
        reply = w.send_control(b"status")
        out = {"on": False, "startup": startup_enabled()}
        with ONEOFF_LOCK:
            out["oneoff"] = dict(ONEOFF)
        if not reply:
            out["arena"] = w.arena_running()             # for the welcome screen and Export now
        if reply:
            try:
                out.update(json.loads(reply))
            except ValueError:                           # an older watcher that only says "running"
                out["state"] = "running"
            out["on"] = True
        return out

    def auto_set(self, on):
        w = _watcher()
        if on:
            # Arena already open: export straight away (unless a one-off export is running right now)
            ok = w.start_watcher(soon=not ONEOFF["running"])
            log("auto-export switched on" + ("" if ok else " (watcher didn't answer)"))
        else:
            w.send_control(b"stop")
            log("auto-export switched off")
            for _ in range(10):                          # let it finish stopping
                if not w.send_control(b"ping"):
                    break
                time.sleep(0.3)
        return self.auto_status()

    def auto_now(self):
        """Export now: through the watcher if auto-export is on, else a one-off export here."""
        w = _watcher()
        if w.send_control(b"ping"):
            w.send_control(b"now")
            time.sleep(0.6)
            return {"ok": True, "mode": "watcher", **self.auto_status()}
        if ONEOFF["running"]:
            return {"ok": True, "mode": "oneoff", **self.auto_status()}
        if not w.arena_running():
            return {"ok": False, "message": "Open MTG Arena first, then try again.", **self.auto_status()}
        _oneoff_set(running=True, step="Starting…", error="", error_at=None)
        threading.Thread(target=self._oneoff, daemon=True).start()
        return {"ok": True, "mode": "oneoff", **self.auto_status()}

    def _oneoff(self):
        w = _watcher()
        proc, started = None, False

        def fail(msg):
            _oneoff_set(error=msg, error_at=time.time())
            log("one-off export: " + msg)

        try:
            w.log("One-off export from ArcVault (auto-export off).")
            if not w.daemon_up():
                _oneoff_set(step="Starting ArcVault's reader…")
                if not w.find_daemon_exe():
                    return fail("ArcVault's reader (mtga-tracker-daemon.exe) is missing. Reinstall ArcVault.")
                proc, started = w.start_daemon(), True
                if not w.daemon_up():
                    return fail("ArcVault's reader didn't start. If your antivirus blocked "
                                "mtga-tracker-daemon.exe, allow it and try again.")
            if w.in_match():
                return fail("You're in a match. Export again once it's over.")
            try:
                st = w.daemon_get("/status", 5)
            except Exception:
                st = {}
            if not st.get("isRunning") or st.get("updating"):
                return fail("Arena is still loading. Wait for the Home screen, then try again.")
            first = not os.path.isfile(P.cache("scryfall_oracle.json"))
            _oneoff_set(step="Reading your collection from Arena…" + (
                " First export: also downloading card data from Scryfall (about a minute)." if first else ""))
            baseline = P.cache("session_baseline.csv")
            ok, result = w.run_export(baseline if os.path.isfile(baseline) else None)
            if ok:
                _oneoff_set(done_at=time.time(), result=result, step="")
            elif result == "Arena busy":
                fail("Arena is busy and the collection can't be read right now. "
                     "Go to Arena's Home screen, then try again.")
            else:
                fail(f"The export didn't finish. The details are in {w.LOG}")
        except Exception as e:
            fail(f"The export stopped with an error: {e}")
        finally:
            if started:
                w.stop_daemon(proc)
            _oneoff_set(running=False, step="")

    # ----- first run of an installed copy: where files go + bring in your history -----
    def where(self):
        """Where your files are kept, whether a sync service holds them, and old folders to import."""
        import arcvault_migrate as m
        old = []
        if P.mode == "installed":
            try:
                old = m.find_old_folders(P)
            except Exception as e:
                log(f"finding old folders failed: {e}")
        return {"mode": P.mode, "platform": P.platform, "data_dir": P.data_dir,
                "default_dir": P.default_data_dir, "synced": P.synced_by(),
                "names": dict(P.names), "old_folders": old,
                "sandbox": bool(os.environ.get("ARCVAULT_SANDBOX"))}

    def pick_folder(self, title="Choose a folder"):
        """A folder chooser; returns the path or None."""
        try:
            import webview
            kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
            res = self._window.create_file_dialog(kind)
        except Exception as e:
            log(f"folder dialog failed: {e}")
            return None
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def set_data_dir(self, path):
        """"Change..." on the first-run screen: keep your files in another folder."""
        path = os.path.abspath(os.path.expanduser(path or ""))
        try:
            os.makedirs(path, exist_ok=True)
            test = os.path.join(path, ".arcvault_write_test")
            with open(test, "w") as f:
                f.write("ok")
            os.remove(test)
        except OSError as e:
            return {"ok": False, "error": f"ArcVault can't save files there ({e.strerror or e})."}
        same = os.path.normcase(path) == os.path.normcase(os.path.abspath(P.default_data_dir))
        was_on = bool(self.auto_status().get("on"))
        if was_on:
            self.auto_set(False)                          # the watcher reads the location when it starts
        save_settings(data_dir=None if same else path)
        P.reload()
        log(f"files will be kept in {P.data_dir}")
        if was_on:
            self.auto_set(True)
        return {"ok": True, **self.where()}

    def import_plan(self, src):
        """What 'bring in your history' would copy from `src`, as counts."""
        import arcvault_migrate as m
        try:
            steps = m.plan(src, P)
        except Exception as e:
            return {"ok": False, "error": str(e), "src": src}
        return {"ok": True, "src": src, "total": len(steps), "counts": m.summary(steps)}

    def import_start(self, src):
        """Copy in the background; the page polls import_status()."""
        import arcvault_migrate as m
        with IMPORT_LOCK:
            if IMPORT.get("running"):
                return {"ok": False, "error": "Already bringing in your history."}
            IMPORT.clear()
            IMPORT.update(running=True, done=0, total=0, src=src, started=time.time())

        def prog(i, n):
            IMPORT.update(done=i, total=n)

        def work():
            try:
                ok, report = m.run(src, P, log=log, progress=prog)
                IMPORT.update(ok=ok, report=report, report_file=os.path.join(P.data_dir, "import_report.txt"))
            except Exception as e:
                IMPORT.update(ok=False, error=str(e))
                log(f"import failed: {e}")
            finally:
                IMPORT.update(running=False, finished=time.time(), done=IMPORT.get("total", 0))
        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def import_status(self):
        with IMPORT_LOCK:
            return dict(IMPORT)

    # ----- Decks tab: saved decks are plain Arena-format .txt files in <data>\\decks -----
    def decks_list(self):
        """{'dir': the decks folder, 'decks': [{'name', 'modified'}] by name}."""
        d = P.decks_dir()
        out = []
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith(".txt"):
                    out.append({"name": f[:-4], "modified": os.path.getmtime(os.path.join(d, f))})
        out.sort(key=lambda x: x["name"].lower())
        return {"dir": d, "decks": out}

    def deck_load(self, name):
        path = _deck_path(name)
        if not path or not os.path.isfile(path):
            return {"ok": False, "message": "That deck file isn't there any more."}
        with open(path, encoding="utf-8-sig") as f:
            return {"ok": True, "name": name, "text": f.read()}

    def deck_save(self, name, text):
        path = _deck_path(name)
        if not path:
            return {"ok": False, "message": "Give the deck a name first." if not str(name or "").strip()
                    else "Windows can't use that as a file name. Try another name."}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\r\n" if os.name == "nt" else "\n") as f:
            f.write(text.replace("\r\n", "\n").rstrip("\n") + "\n")
        os.replace(tmp, path)
        log(f"deck saved: {os.path.basename(path)}")
        return {"ok": True, "name": os.path.basename(path)[:-4], **self.decks_list()}

    def deck_delete(self, name):
        path = _deck_path(name)
        if path and os.path.isfile(path):
            os.remove(path)
            log(f"deck deleted: {os.path.basename(path)}")
        return {"ok": True, **self.decks_list()}

    # ----- Card pictures: downloaded once from Scryfall, then kept in the cache folder -----
    def card_image(self, arena_id, set_code, number):
        """{'ok': True, 'url': file:///.../cache/cards/<id>.jpg} or {'ok': False, 'offline': bool}."""
        return _card_image(str(arena_id or "").strip(), str(set_code or "").strip(), str(number or "").strip())

    def clipboard_text(self):
        """Text on the clipboard (for Import), or None if it can't be read."""
        try:
            return _clipboard_text()
        except Exception as e:
            log(f"clipboard read failed: {e}")
            return None

    def startup_set(self, on):
        ok, msg = set_startup(bool(on))
        log(msg)
        return {"ok": ok, "message": msg, **self.auto_status()}

    def stamp(self):
        """Newest modification time of the export files (0 if none)."""
        times = [os.path.getmtime(p) for p in (_pick(v) for v in FILES.values()) if p]
        return max(times, default=0)

    def latest(self):
        out = {"stamp": self.stamp(), "version": VERSION}
        for key, names in FILES.items():
            p = _pick(names)
            if not p:
                continue
            # an export may be writing this file right now: wait until it has settled
            for _ in range(10):
                if time.time() - os.path.getmtime(p) > 2:
                    break
                time.sleep(1)
            try:
                with open(p, encoding="utf-8-sig") as f:
                    text = f.read()
            except OSError as e:
                log(f"couldn't read {p}: {e}")
                continue
            out[key] = {"name": os.path.basename(p), "text": text, "when": _when(os.path.getmtime(p)),
                        "mtime": os.path.getmtime(p)}
        # The inventory file only gains a row when something changed, so its date is "last
        # change". Every export rewrites the collection file, so that date is "last checked".
        inv, col = out.get("inventory"), out.get("collection")
        if inv and col and col["mtime"] - inv["mtime"] > 60:
            same_day = time.localtime(col["mtime"])[:3] == time.localtime(inv["mtime"])[:3]
            inv["checked"] = time.strftime("%H:%M", time.localtime(col["mtime"])) if same_day else col["when"]
        return out


def set_window_icon():
    """WinForms windows take the icon of python.exe; swap in the ArcVault icon."""
    if os.name != "nt" or not os.path.isfile(ICON):
        return
    try:
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        u.LoadImageW.restype = ctypes.c_void_p
        u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = None
        for _ in range(20):
            hwnd = u.FindWindowW(None, TITLE)
            if hwnd:
                break
            time.sleep(0.25)
        if not hwnd:
            return
        IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x10, 0x80
        big = u.LoadImageW(None, ICON, IMAGE_ICON, u.GetSystemMetrics(11), u.GetSystemMetrics(12), LR_LOADFROMFILE)
        small = u.LoadImageW(None, ICON, IMAGE_ICON, u.GetSystemMetrics(49), u.GetSystemMetrics(50), LR_LOADFROMFILE)
        if big:
            u.SendMessageW(hwnd, WM_SETICON, 1, big)
        if small:
            u.SendMessageW(hwnd, WM_SETICON, 0, small)
    except Exception as e:                                # cosmetic only: never stop the app for it
        log(f"icon: {e}")


# --------------------------------------------------------------------------- #
# Tray icon
STATE_COLOURS = {"off": (138, 143, 153), "waiting": (232, 163, 61), "retry": (232, 163, 61),
                 "soon": (90, 141, 255), "exporting": (90, 141, 255), "done": (73, 194, 124)}


def classify(st):
    """The same states as the switch in the window."""
    if not st.get("on"):
        return "off", "Auto-export off"
    if not st.get("arena"):
        return "waiting", "Auto-export on · waiting for Arena"
    if st.get("state") == "exporting":
        return "exporting", "Exporting now…"
    if st.get("state") == "retry":
        return "retry", f"Retrying ({st.get('note') or 'waiting'})"
    if st.get("last_ok"):
        mins = int((time.time() - st["last_ok"]) // 60)
        res = f" · {st['last_result']}" if st.get("last_result") else ""
        return "done", ("Exported just now" if mins < 1 else f"Exported {mins} min ago") + res
    return "soon", "Arena open · exporting soon"


def tray_mark(size=64):
    """The small ArcVault mark (solid hexagon, A cut out, arc through it), drawn with Pillow."""
    from PIL import Image, ImageDraw
    S = 256                                               # draw big, shrink smooth
    k = S / 100
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gold, dark = (213, 174, 88, 255), (15, 18, 24, 255)
    hexagon = [(50, 2), (91.6, 26), (91.6, 74), (50, 98), (8.4, 74), (8.4, 26)]
    d.polygon([(x * k, y * k) for x, y in hexagon], fill=gold)
    a_shape = [(50, 12), (76, 90), (64, 90), (50, 48), (36, 90), (24, 90)]
    d.polygon([(x * k, y * k) for x, y in a_shape], fill=dark)
    arc = [((1 - t) ** 2 * 8 + 2 * (1 - t) * t * 50 + t * t * 92,
            (1 - t) ** 2 * 67 + 2 * (1 - t) * t * 43 + t * t * 67) for t in [i / 40 for i in range(41)]]
    d.line([(x * k, y * k) for x, y in arc], fill=gold, width=int(8 * k))
    return im.resize((size, size), Image.LANCZOS)


class Tray:
    """pystray icon, run on its own thread. Talks to the window through pywebview's thread-safe calls."""

    def __init__(self, window, api):
        import pystray
        from PIL import Image
        self.pystray, self.window, self.api = pystray, window, api
        self.status = {"on": False}
        self.kind = None
        self.quitting = False
        self.visible = True
        self.base = tray_mark()
        M = pystray.MenuItem
        self.icon = pystray.Icon("ArcVault", self.image("off"), "ArcVault", pystray.Menu(
            M("Open ArcVault", self.open, default=True),
            M("Export now", self.export_now, enabled=lambda i: bool(self.status.get("on") and self.status.get("arena"))),
            M("Auto-export", self.toggle, checked=lambda i: bool(self.status.get("on"))),
            pystray.Menu.SEPARATOR,
            M("Quit ArcVault", self.quit)))

    def image(self, kind):
        from PIL import ImageDraw
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        d.ellipse((34, 34, 64, 64), fill=(15, 18, 24, 255))         # dark ring so the dot reads on any taskbar
        d.ellipse((39, 39, 59, 59), fill=STATE_COLOURS[kind] + (255,))
        return im

    def start(self):
        threading.Thread(target=self.icon.run, daemon=True).start()
        threading.Thread(target=self.poll, daemon=True).start()

    def poll(self):
        while not self.quitting:
            try:
                st = self.api.auto_status()
            except Exception as e:
                log(f"tray status: {e}")
                st = {"on": False}
            self.status = st
            kind, text = classify(st)
            try:
                if kind != self.kind:
                    self.icon.icon = self.image(kind)
                    self.kind = kind
                self.icon.title = f"ArcVault · {text}"[:127]
                self.icon.update_menu()
            except Exception:
                pass
            time.sleep(4)

    # menu actions (pystray thread)
    def open(self, *_):
        self.visible = True
        self.window.show()
        self.window.restore()

    def export_now(self, *_):
        self.api.auto_now()

    def toggle(self, *_):
        self.status = self.api.auto_set(not self.status.get("on"))
        self.icon.update_menu()

    def quit(self, *_):
        """Quit = auto-export off, tray gone, window closed."""
        self.quitting = True
        try:
            self.api.auto_set(False)
        except Exception as e:
            log(f"quit: {e}")
        try:
            self.icon.stop()
        except Exception:
            pass
        self.window.destroy()

    def notify_once(self):
        if load_settings().get("tray_notice_shown"):
            return
        save_settings(tray_notice_shown=True)
        try:
            self.icon.notify("ArcVault is still running here and auto-export stays on. "
                             "Right-click the icon to quit.", "ArcVault")
        except Exception:
            pass


def instance_server(window):
    """A second ArcVault start sends 'show' here; this one comes to the front instead."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", APP_PORT))
        srv.listen(2)
    except OSError:
        return None

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                try:
                    if conn.recv(16).startswith(b"show"):
                        conn.sendall(b"ok")
                        window.show()
                        window.restore()
                except OSError:
                    pass
    threading.Thread(target=loop, daemon=True).start()
    return srv


def other_instance_shown():
    try:
        with socket.create_connection(("127.0.0.1", APP_PORT), timeout=2) as c:
            c.sendall(b"show")
            return c.recv(16) == b"ok"
    except OSError:
        return False


def swap_in_imported_window():
    """'Bring in your history' copies the old window profile (theme etc.) next to the current one,
    because the open window is using it. Swap it in now, before the window starts."""
    staged = STORAGE + ".imported"
    if not os.path.isdir(staged):
        return
    try:
        if os.path.isdir(STORAGE):
            os.replace(STORAGE, STORAGE + ".before_import")   # kept, not deleted
        os.replace(staged, STORAGE)
        with open(os.path.join(P.work_dir, "window.from_import"), "w") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M"))
        log("window settings brought in from the old folder")
    except OSError as e:
        log(f"couldn't swap in the imported window settings: {e}")


WEBVIEW2_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"     # Microsoft Edge WebView2 Runtime


def webview2_installed():
    """True if the WebView2 Runtime (what draws ArcVault's window) is installed, per Microsoft's
    documented registry check. Windows 11 and up-to-date Windows 10 have it; some PCs don't."""
    if os.name != "nt":
        return True
    import winreg
    places = [(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}"),
              (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}"),
              (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}")]
    for root, key in places:
        try:
            with winreg.OpenKey(root, key) as k:
                pv, _ = winreg.QueryValueEx(k, "pv")
                if pv and pv != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


WEBVIEW2_SETUP = P.program("redist", "MicrosoftEdgeWebview2Setup.exe")   # shipped by the installer
_wv2_failed = threading.Event()


def webview2_failed():
    """WebView2 is registered but won't start (damaged install, or a stripped-down Windows like
    Windows Sandbox): the window would stay blank. Say so, and offer Microsoft's repair."""
    if _wv2_failed.is_set():
        return
    _wv2_failed.set()
    log("WebView2 failed to start - offering repair")
    link = "https://developer.microsoft.com/microsoft-edge/webview2/"
    can_repair = os.name == "nt" and os.path.isfile(WEBVIEW2_SETUP)
    text = ("ArcVault can't show its window: the Microsoft Edge WebView2 Runtime on this PC isn't working.\n\n"
            + ("Repair it now? ArcVault will run Microsoft's WebView2 installer (needs internet), "
               "then open again." if can_repair else
               f"Install or repair it with the free \"Evergreen Bootstrapper\" from\n{link}\nthen open ArcVault again."))
    answer = 7
    try:
        flags = (0x04 | 0x30) if can_repair else (0x00 | 0x30)          # Yes/No or OK, warning icon
        answer = ctypes.windll.user32.MessageBoxW(None, text, TITLE, flags)
    except Exception:
        pass
    if can_repair and answer == 6:                                   # Yes
        try:
            subprocess.run([WEBVIEW2_SETUP, "/install"], timeout=900)
            log("WebView2 installer finished - reopening")
            subprocess.Popen(paths.launch("app"), close_fds=True)
        except Exception as e:
            log(f"WebView2 repair failed: {e}")
            message_box(f"The WebView2 installer didn't finish ({e}).\n\nYou can get it from\n{link}")
    os._exit(1)                                                      # never leave a blank window behind


def run(start_in_tray=False):
    if not webview2_installed():
        message_box("ArcVault needs the Microsoft Edge WebView2 Runtime to show its window, "
                    "and it isn't installed on this PC.\n\n"
                    "Download the free \"Evergreen Bootstrapper\" from\n"
                    "https://developer.microsoft.com/microsoft-edge/webview2/\n"
                    "run it, then open ArcVault again. (The ArcVault installer normally does this for you.)")
        return 1
    try:
        import webview
    except ImportError:
        message_box("ArcVault needs one extra component.\n\nRun \"ArcVault setup.bat\" in this folder, then open ArcVault again.")
        return 1
    if not os.path.isfile(PAGE):
        message_box(f"ArcVault.html is missing from:\n{HERE}")
        return 1
    if other_instance_shown():                           # already running (maybe in the tray): show it
        return 0
    if os.name == "nt":
        try:                                              # own taskbar button, not grouped with Python
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    swap_in_imported_window()
    os.makedirs(STORAGE, exist_ok=True)
    api = Api()
    window = webview.create_window(TITLE, url=Path(PAGE).as_uri() + "#app", js_api=api,
                                   width=1440, height=900, min_size=(960, 600),
                                   background_color="#0F1218", text_select=True, hidden=start_in_tray)
    api._window = window                                 # for the folder chooser
    try:
        tray = Tray(window, api)
    except Exception as e:                                # pystray / pillow missing: no tray, close = quit
        log(f"no tray icon ({e}) - run ArcVault setup.bat")
        tray = None

    def on_closing():
        # auto-export on + tray available: hide to the tray instead of quitting
        if tray and not tray.quitting and tray.status.get("on"):
            window.hide()
            tray.visible = False
            tray.notify_once()
            return False
        if tray:
            tray.quitting = True
            try:
                tray.icon.stop()
            except Exception:
                pass
        return True

    window.events.closing += on_closing
    window.events.shown += set_window_icon

    def after_start():
        log(f"window drawn by: {getattr(webview, 'renderer', '?')}")
        instance_server(window)
        migrate_startup()
        if start_in_tray:
            api.auto_set(True)                            # Start with Windows: auto-export on
        if tray:
            tray.status = api.auto_status()
            tray.start()
        elif start_in_tray:
            window.show()                                 # no tray to live in: show the window

    # pywebview reports its own problems (e.g. WebView2 failing to start) through Python logging,
    # which goes nowhere in a windowless exe: send it to arcvault_app.log too.
    try:
        import logging

        class _ToLog(logging.Handler):
            def emit(self, record):
                msg = record.getMessage()
                log(f"pywebview {record.levelname.lower()}: {msg}")
                if "WebView2 initialization failed" in msg or "compatible Webview2 Runtime" in msg:
                    threading.Thread(target=webview2_failed, daemon=True).start()
        logging.getLogger("pywebview").addHandler(_ToLog(level=logging.INFO))
    except Exception:
        pass
    log(f"window v{VERSION} opening{' in the tray' if start_in_tray else ''} (pywebview {getattr(webview, '__version__', '?')}, "
        f"WebView2 {'found' if webview2_installed() else 'missing'})")
    # the user agent marks the page as running in the ArcVault window (backup for the #app marker)
    webview.start(after_start, private_mode=False, storage_path=STORAGE,
                  user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/150.0 ArcVaultApp/{VERSION}")
    return 0


def make_shortcuts():
    if os.name != "nt":
        print("Shortcuts are Windows only.")
        return 1
    cmd = paths.launch("app")
    q = lambda x: x.replace("'", "''")
    places = [("[Environment]::GetFolderPath('Desktop')", "Desktop"), (f"'{q(HERE)}'", "this folder")]
    ok = True
    for where, label in places:
        script = (
            f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({where} + '\\ArcVault.lnk'); "
            f"$s.TargetPath = '{q(cmd[0])}'; "
            f"$s.Arguments = '{q(subprocess.list2cmdline(cmd[1:]))}'; "
            f"$s.WorkingDirectory = '{q(HERE)}'; "
            f"$s.IconLocation = '{q(ICON)}'; "
            "$s.Description = 'ArcVault - collection intelligence for MTG Arena'; "
            "$s.Save()")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, text=True, timeout=60)
        if r.returncode:
            ok = False
            print(f"Couldn't create the shortcut in {label}:\n{r.stderr or r.stdout}")
        else:
            print(f"ArcVault shortcut added to {label}.")
    return 0 if ok else 1


def cli():
    try:
        sys.exit(make_shortcuts() if "--shortcut" in sys.argv else run(start_in_tray="--tray" in sys.argv))
    except Exception:
        message_box("ArcVault stopped with an error:\n\n" + traceback.format_exc()[-1500:])
        sys.exit(1)


if __name__ == "__main__":
    cli()
