#!/usr/bin/env python3
"""
MTGA auto-export watcher
------------------------
Runs quietly in the background. While MTG Arena is open it exports your
collection automatically, so your files are always current:

  * first export a few minutes after Arena starts (time to log in and load)
  * then every 15 minutes while Arena stays open
  * never mid-match (it waits and tries again)
  * when Arena closes it stops the daemon and goes back to waiting

The exporter reads Arena's memory, so it can only run while Arena is open -
your files are at most one interval old when you close the game.

'New' cards are counted from the start of each Arena session.

Use "Auto-export ON.bat" / "Auto-export OFF.bat" rather than running this
directly. Everything it does is written to auto_export.log in this folder.

Options (for testing / tuning):
  --interval-min 15     minutes between exports while Arena is open
  --first-delay-min 3   wait after Arena starts before the first export
  --poll-s 20           how often to check whether Arena is running
  --stop                stop a running watcher
  --status              say whether a watcher is running
  --soon                if Arena is already open, export straight away (the ArcVault switch uses this)

The ArcVault window talks to the watcher on the control port: "status" (JSON),
"now" (export as soon as possible) and "stop".
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime

import arcvault_paths as paths
from arcvault_paths import L as P     # every file location comes from here

HERE = P.program_dir                   # where the scripts live (working directory for the exporter)
EXPORTER = P.program("mtga_collection_export.py")
LOG = P.log("auto_export.log")
CONTROL_PORT = 6851            # local-only; also makes sure only one watcher runs
DAEMON_PORT = 6842
ARENA_EXE = "MTGA.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# What the watcher is doing, for the ArcVault switch ("status" on the control port).
STATE = {"state": "starting", "arena": False, "next_export": None, "note": "",
         "last_ok": None, "last_result": "", "started": time.time()}
STATE_LOCK = threading.Lock()
WAKE = threading.Event()        # "now"/"stop" wake the main loop instead of waiting a full poll
EXPORT_NOW = threading.Event()


def set_state(**kw):
    with STATE_LOCK:
        STATE.update(kw)


def state_json():
    with STATE_LOCK:
        s = dict(STATE)
    s["now"] = time.time()
    return json.dumps(s)


# --------------------------------------------------------------------------- #
def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.isfile(LOG) and os.path.getsize(LOG) > 1_000_000:   # keep the log small
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if sys.stdout and not sys.executable.lower().endswith("pythonw.exe"):
        try:
            print(line, flush=True)
        except Exception:
            pass


def arena_running():
    fake = os.environ.get("MTGA_WATCH_FAKE")          # testing hook: a file that means "Arena is open"
    if fake:
        return os.path.isfile(fake)
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {ARENA_EXE}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW).stdout
        return ARENA_EXE.lower() in out.lower()
    except Exception:
        return False


def daemon_get(path, timeout=5):
    with urllib.request.urlopen(f"http://localhost:{DAEMON_PORT}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def daemon_up():
    try:
        daemon_get("/status", 3)
        return True
    except Exception:
        return False


def find_daemon_exe():
    return P.daemon_exe()


def start_daemon():
    exe = find_daemon_exe()
    if not exe:
        log("Can't find mtga-tracker-daemon.exe in this folder - run Build Daemon.bat.")
        return None
    proc = subprocess.Popen([exe, "-p", str(DAEMON_PORT)], cwd=os.path.dirname(exe),
                            creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(1)
        if daemon_up():
            log("Daemon started.")
            return proc
    log("Daemon didn't answer after 20 s.")
    return proc


def stop_daemon(proc):
    try:
        urllib.request.urlopen(urllib.request.Request(f"http://localhost:{DAEMON_PORT}/shutdown", method="POST"), timeout=5)
    except Exception:
        pass
    if proc:
        try:
            proc.wait(5)
        except Exception:
            proc.terminate()
    log("Daemon stopped.")


def in_match():
    """True while a match is being played. The daemon errors when there is no match."""
    try:
        m = daemon_get("/matchState", 5)
    except Exception:
        return False
    if not isinstance(m, dict) or m.get("error"):
        return False
    mid = next((v for k, v in m.items() if k.lower() == "matchid"), None)
    return bool(mid)


def run_export(baseline):
    # a normal interpreter (output captured below); compiled: ArcVault.exe --export
    cmd = paths.launch("export", "--port", str(DAEMON_PORT), windowless=False)
    if baseline and os.path.isfile(baseline):
        cmd += ["--baseline", baseline]
    env = {k: v for k, v in os.environ.items() if k != "MTGA_PAUSE"}
    try:
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=900,
                           creationflags=NO_WINDOW, env=env)
    except subprocess.TimeoutExpired:
        log("Export took over 15 minutes - stopped it.")
        return False, "export took too long"
    out = (r.stdout or "") + (r.stderr or "")
    keep = [l.strip() for l in out.splitlines()
            if any(w in l for w in ("Owned:", "Gold", "Changes since", "No changes", "collection_full.csv (",
                                    "Site exports", "printings matched", "isn't ready",
                                    "ERROR", "NOTE", "WARNING", "failed", "Traceback", "Error"))]
    for l in keep[-8:]:
        log("    " + l)
    ok = r.returncode == 0 and "ERROR" not in out
    if not ok and "isn't ready" in out:
        log("Arena busy (collection not readable right now) - will retry.")
    else:
        log("Export done." if ok else f"Export didn't complete (exit {r.returncode}) - will retry.")
    # one short line for the ArcVault switch
    m = re.search(r"Changes since last run: (\d+) cards \(\+(-?\d+) copies\)", out)
    if not ok:
        # the reader couldn't read the collection: Arena loading, or busy mid-session (deck builder, events...)
        result = "Arena busy" if "isn't ready" in out else "export didn't complete"
    elif m:
        result = f"+{m.group(2)} new" if int(m.group(2)) > 0 else f"{m.group(1)} changed"
    elif "No changes" in out:
        result = "no new cards"
    else:
        result = ""
    return ok, result


# --------------------------------------------------------------------------- #
SHORTCUT_NAME = "MTGA Auto-Export.lnk"


def pythonw_path():
    return paths.python_exe(windowless=True)


def powershell(script):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)


def startup_path():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", SHORTCUT_NAME)


def startup_enabled():
    return os.name == "nt" and os.path.isfile(startup_path())


def set_startup(on):
    """Start the watcher with Windows (shortcut in the Startup folder), or not. Returns (ok, message)."""
    if os.name != "nt":
        return False, "Start-with-Windows only works on Windows."
    if not on:
        try:
            if os.path.isfile(startup_path()):
                os.remove(startup_path())
            return True, "Auto-export will no longer start with Windows."
        except OSError as e:
            return False, f"Couldn't remove the Startup shortcut: {e}"
    q = lambda x: x.replace("'", "''")               # PowerShell single-quote escaping
    cmd = paths.launch("watcher")
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"[Environment]::GetFolderPath('Startup') + '\\{SHORTCUT_NAME}'); "
        f"$s.TargetPath = '{q(cmd[0])}'; "
        f"$s.Arguments = '{q(subprocess.list2cmdline(cmd[1:]))}'; "
        f"$s.WorkingDirectory = '{q(HERE)}'; "
        "$s.Description = 'Exports your MTG Arena collection while Arena is open'; "
        "$s.Save()")
    r = powershell(script)
    if r.returncode != 0:
        return False, "Couldn't create the Startup shortcut:\n" + (r.stderr or r.stdout)
    return True, "Auto-export will now start with Windows."


def start_watcher(soon=False):
    """Start a background watcher unless one is running. True once it answers."""
    if send_control(b"ping"):
        return True
    args = paths.launch("watcher", *(["--soon"] if soon else []))
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(args, cwd=HERE, creationflags=flags, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.5)
        if send_control(b"ping"):
            return True
    return False


def install():
    """Start with Windows (shortcut in the Startup folder) and start now."""
    ok, msg = set_startup(True)
    print(msg)
    if send_control(b"ping"):
        print("The watcher is already running.")
    elif start_watcher():
        print("Watcher started. It runs in the background - see auto_export.log for what it does.")
    else:
        print("Started the watcher, but it didn't answer yet - check auto_export.log.")


def uninstall():
    ok, msg = set_startup(False)
    print(msg)
    print("Stopped the watcher." if send_control(b"stop") else "The watcher wasn't running.")


def control_server(sock, stop_event):
    sock.settimeout(1)
    while not stop_event.is_set():
        try:
            conn, _ = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            return
        with conn:
            try:
                msg = conn.recv(64)
                if msg.startswith(b"stop"):
                    conn.sendall(b"stopping")
                    stop_event.set()
                    WAKE.set()
                elif msg.startswith(b"status"):
                    conn.sendall(state_json().encode())
                elif msg.startswith(b"now"):
                    EXPORT_NOW.set()
                    WAKE.set()
                    conn.sendall(b"ok")
                else:
                    conn.sendall(b"running")
            except OSError:
                pass


def send_control(msg):
    try:
        with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=3) as s:
            s.sendall(msg)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if not msg.startswith(b"status"):
                    break
            return data.decode()
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description="Export your MTGA collection automatically while Arena is open.")
    ap.add_argument("--interval-min", type=float, default=15)
    ap.add_argument("--first-delay-min", type=float, default=3)
    ap.add_argument("--poll-s", type=float, default=20)
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--soon", action="store_true", help="if Arena is already open, export straight away")
    ap.add_argument("--install", action="store_true", help="start with Windows, and start now")
    ap.add_argument("--uninstall", action="store_true", help="don't start with Windows, and stop now")
    a = ap.parse_args()

    if a.install:
        return install()
    if a.uninstall:
        return uninstall()
    if a.stop:
        print("Stopped the auto-export watcher." if send_control(b"stop") else "Auto-export watcher wasn't running.")
        return
    if a.status:
        print("Auto-export watcher is running." if send_control(b"ping") else "Auto-export watcher is NOT running.")
        return

    # one watcher only: the control port doubles as a lock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", CONTROL_PORT))
        sock.listen(2)
    except OSError:
        print("Auto-export watcher is already running.")
        return
    stop = threading.Event()
    threading.Thread(target=control_server, args=(sock, stop), daemon=True).start()

    interval, first, retry = a.interval_min * 60, a.first_delay_min * 60, min(120, a.interval_min * 60)
    baseline = P.cache("session_baseline.csv")
    log(f"Watcher started (export every {a.interval_min:g} min while Arena is open).")
    was_running, next_export, proc = False, None, None
    soon = a.soon
    try:
        while not stop.is_set():
            running = arena_running()
            now = time.time()
            if running and not was_running:
                delay = 0 if soon else first
                log("Arena open - exporting now." if soon else "Arena started - first export in %g min." % a.first_delay_min)
                latest = P.file("collection")
                try:
                    os.makedirs(os.path.dirname(baseline), exist_ok=True)
                    if os.path.isfile(latest):
                        shutil.copyfile(latest, baseline)        # 'New' = gained this session
                except OSError as e:
                    log(f"Couldn't save session baseline: {e}")
                next_export = now + delay
            elif not running and was_running:
                log("Arena closed.")
                if proc is not None or daemon_up():
                    stop_daemon(proc)
                proc, next_export = None, None
            soon = False
            if EXPORT_NOW.is_set():
                EXPORT_NOW.clear()
                if running:
                    log("Export requested from ArcVault.")
                    next_export = now
                else:
                    set_state(note="Arena isn't open")
            with STATE_LOCK:
                STATE.update(arena=running, next_export=next_export)
                if not running:
                    STATE["state"] = "waiting"
                elif STATE["state"] in ("waiting", "starting"):
                    STATE.update(state="scheduled", note="")
            if running and next_export and now >= next_export:
                if not daemon_up():
                    proc = start_daemon() or proc
                if not daemon_up():
                    next_export = now + retry
                elif in_match():
                    log("In a match - trying again in 2 min.")
                    next_export = now + retry
                    set_state(state="retry", note="in a match", next_export=next_export)
                else:
                    try:
                        st = daemon_get("/status", 5)
                    except Exception:
                        st = {}
                    if not st.get("isRunning") or st.get("updating"):
                        log("Arena is still loading/updating - trying again in 2 min.")
                        next_export = now + retry
                        set_state(state="retry", note="Arena loading", next_export=next_export)
                    else:
                        log("Exporting...")
                        set_state(state="exporting", note="")
                        ok, result = run_export(baseline)
                        next_export = time.time() + (interval if ok else retry)
                        if ok:
                            set_state(state="scheduled", last_ok=time.time(), last_result=result,
                                      next_export=next_export, note="")
                        else:
                            set_state(state="retry", note=result or "export didn't complete",
                                      next_export=next_export)
            was_running = running
            WAKE.wait(a.poll_s)
            WAKE.clear()
    finally:
        if proc is not None:
            stop_daemon(proc)
        log("Watcher stopped.")
        sock.close()


if __name__ == "__main__":
    main()
