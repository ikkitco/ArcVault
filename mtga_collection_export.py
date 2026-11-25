#!/usr/bin/env python3
"""
ArcVault - collection exporter (formerly MTGA Collection Exporter)
------------------------------------------------------------------
Exports every card you own in MTG Arena to a CSV you can open in Excel /
Google Sheets / LibreOffice.

How it works
  1. Asks mtga-tracker-daemon (a small local helper that reads Arena's memory,
     read-only) for your owned cards:  GET http://localhost:6842/cards
     -> [{grpId, owned}, ...]
  2. Turns each grpId (Arena's card ID) into a name, set, collector number,
     rarity, colours and type using Arena's OWN card database file
     (Raw_CardDatabase_*.mtga), whose location the daemon reports.
     If that file can't be read, it falls back to the daemon's /allCards list
     (name + set only).
  3. Writes:
       mtga_collection.csv              <- always the latest; point your sheet here
       snapshots/collection_YYYY-MM-DD_HHMM.csv
       changes/changes_YYYY-MM-DD_HHMM.csv   <- what changed since last run

Requirements: Python 3.8+ (standard library only, nothing to pip install),
MTG Arena running and logged in (sitting on the Home screen is ideal),
mtga-tracker-daemon running.

Usage:
  python mtga_collection_export.py
  python mtga_collection_export.py --port 6842 --out "D:\\MTG"
  python mtga_collection_export.py --daemon "C:\\Tools\\mtga-tracker-daemon\\mtga-tracker-daemon.exe"
  python mtga_collection_export.py --db "D:\\...\\Raw_CardDatabase_xxx.mtga"
  python mtga_collection_export.py --force      (skip the safety checks)
"""

import argparse
import csv
import glob
import gzip
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime

from arcvault_paths import L as P     # every file location comes from here

VERSION = "2.2.0"

# Rules-text columns from Scryfall. They go at the end so spreadsheets that
# point at the older columns keep working.
ORACLE_COLUMNS = [
    "Mana Cost", "Mana Value", "Color Identity", "Power", "Toughness", "Loyalty",
    "Keywords", "Mechanics", "Oracle Text",
]

CSV_COLUMNS = [
    "Name", "Alternate Name", "Set", "Set Name", "Set Released", "Collector Number",
    "Rarity", "Colors", "Type", "Owned",
    # format legality columns are inserted here (see LEGAL_FORMATS)
    "Arena ID", "Digital Only", "Rebalanced (Alchemy)",
] + ORACLE_COLUMNS + ["New"]   # v1.7: copies gained since the previous export

# Extra columns only in mtga_collection_full.csv (every Arena set card, owned or not)
FULL_EXTRA = ["In Set", "Owned (any printing)"]

# Scryfall legality keys -> column names. Only formats Scryfall actually
# reports get a column. Values: Legal / Not legal / Banned / Restricted.
LEGAL_FORMATS = [
    ("standard", "Standard"), ("alchemy", "Alchemy"), ("explorer", "Explorer"),
    ("historic", "Historic"), ("timeless", "Timeless"), ("pioneer", "Pioneer"),
    ("standardbrawl", "Standard Brawl"), ("brawl", "Brawl"),
]
LEGAL_WORDS = {"legal": "Legal", "not_legal": "Not legal", "banned": "Banned",
               "restricted": "Restricted"}

# Fallbacks if Arena's DB has no Enums table we can use.
RARITY_FALLBACK = {0: "", 1: "Basic Land", 2: "Common", 3: "Uncommon", 4: "Rare", 5: "Mythic"}
COLOR_FALLBACK = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}
COLOR_ORDER = "WUBRG"


# --------------------------------------------------------------------------- #
# Daemon
# --------------------------------------------------------------------------- #
class Daemon:
    def __init__(self, port):
        self.base = f"http://localhost:{port}"

    def get(self, path, timeout=60):
        req = urllib.request.Request(self.base + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"daemon {path} returned error: {data['error']}")
        return data

    def reachable(self):
        try:
            self.get("/status", timeout=3)
            return True
        except Exception:
            return False


def start_daemon(exe_path, port):
    if not exe_path or not os.path.isfile(exe_path):
        return None
    print(f"Starting daemon: {exe_path} -p {port}")
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen([exe_path, "-p", str(port)],
                            cwd=os.path.dirname(exe_path), creationflags=flags)


def wait_for_arena(daemon, tries=10):
    """Wait until the daemon sees Arena running and not updating."""
    for i in range(tries):
        try:
            st = daemon.get("/status", timeout=5)
        except Exception as e:
            st = {"isRunning": False, "_err": str(e)}
        if st.get("isRunning") and not st.get("updating"):
            return st
        msg = "Arena is updating" if st.get("updating") else "Arena not detected"
        print(f"  {msg} - waiting ({i + 1}/{tries})...")
        time.sleep(3)
    return None


# --------------------------------------------------------------------------- #
# Arena card database
# --------------------------------------------------------------------------- #
def path_from_connection_string(cs):
    """'Data Source=C:\\...\\x.mtga;Version=3' -> 'C:\\...\\x.mtga'
    The daemon strips the drive letter ('/SteamLibrary/...'), so on Windows
    we try each drive until the file exists."""
    if not cs:
        return None
    m = re.search(r"(?:Data Source|DataSource|Filename)\s*=\s*([^;]+)", cs, re.I)
    p = (m.group(1) if m else cs).strip().strip('"')
    if p.lower().startswith("file:"):
        p = p[5:].split("?")[0]
    if os.name == "nt" and not re.match(r"^[A-Za-z]:", p) and not os.path.isfile(p):
        for drive in "CDEFGHIJ":
            cand = os.path.normpath(f"{drive}:{p}")
            if os.path.isfile(cand):
                return cand
    return p


def guess_db_paths():
    """Common install locations, in case the daemon can't tell us."""
    roots = []
    for drive in "CDEFGH":
        roots += [
            rf"{drive}:\Program Files\Wizards of the Coast\MTGA",
            rf"{drive}:\Program Files (x86)\Wizards of the Coast\MTGA",
            rf"{drive}:\Program Files\Epic Games\MagicTheGathering",
            rf"{drive}:\Epic Games\MagicTheGathering",
            rf"{drive}:\Program Files (x86)\Steam\steamapps\common\MTGA",
            rf"{drive}:\SteamLibrary\steamapps\common\MTGA",
            rf"{drive}:\Games\MTGA",
        ]
    hits = []
    for r in roots:
        hits += glob.glob(os.path.join(r, "MTGA_Data", "Downloads", "Raw", "Raw_CardDatabase_*.mtga"))
    hits.sort(key=os.path.getmtime, reverse=True)
    return hits


def table_columns(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def pick(cols, *names):
    low = {c.lower(): c for c in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def colors_to_letters(raw):
    """Arena stores colours as '1,2' (1=W 2=U 3=B 4=R 5=G). -> 'WU'"""
    if raw is None:
        return ""
    letters = set()
    for p in re.split(r"[,\s]+", str(raw)):
        if p.isdigit() and int(p) in COLOR_FALLBACK:
            letters.add(COLOR_FALLBACK[int(p)])
    return "".join(c for c in COLOR_ORDER if c in letters)


def parse_mana(raw):
    """Arena 'o2oBoB' -> ('{2}{B}{B}', 4). X counts as 0; hybrid '(R/G)' -> {R/G}.
    Used when Scryfall has no entry (Arena-only cards)."""
    if not raw:
        return "", 0
    cost, mv = "", 0
    for t in (x for x in str(raw).split("o") if x):
        t = t.strip("()")
        cost += "{" + t + "}"
        if t.isdigit():
            mv += int(t)
        elif t not in ("X", "Y", "Z"):
            mv += 1
    return cost, mv


def strip_markup(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


class CardDB:
    """Reads Arena's Raw_CardDatabase, discovering the schema at runtime so a
    renamed column doesn't break everything."""

    def __init__(self, path):
        # Copy first: Arena may hold the file open.
        self.tmp = os.path.join(tempfile.gettempdir(), "mtga_carddb_copy.sqlite")
        shutil.copyfile(path, self.tmp)
        self.con = sqlite3.connect(self.tmp)
        self.tables = [r[0] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        self.loc = self._load_localizations()
        self.enums = self._load_enums()

    def close(self):
        self.con.close()
        try:
            os.remove(self.tmp)
        except OSError:
            pass

    # --- localisation (LocId -> English text) ---
    def _load_localizations(self):
        loc = {}
        # Newer layout: Localizations_enUS(LocId, Formatted, Loc)
        t = next((t for t in self.tables if t.lower() == "localizations_enus"), None)
        if t:
            cols = table_columns(self.con, t)
            idc, txt = pick(cols, "LocId", "Id"), pick(cols, "Loc", "Text", "enUS")
            fmt = pick(cols, "Formatted")
            order = f' ORDER BY "{fmt}" ASC' if fmt else ""
            for lid, text in self.con.execute(f'SELECT "{idc}", "{txt}" FROM "{t}"{order}'):
                if lid not in loc and text:
                    loc[lid] = strip_markup(text)
            return loc
        # Older layout: Localizations(LocId, enUS, ...)
        t = next((t for t in self.tables if t.lower() == "localizations"), None)
        if t:
            cols = table_columns(self.con, t)
            idc, txt = pick(cols, "LocId", "Id"), pick(cols, "enUS", "en-US", "EN")
            if idc and txt:
                for lid, text in self.con.execute(f'SELECT "{idc}", "{txt}" FROM "{t}"'):
                    if lid not in loc and text:
                        loc[lid] = strip_markup(text)
        return loc

    # --- enums (e.g. CardType 2 -> "Creature") ---
    def _load_enums(self):
        enums = {}
        t = next((t for t in self.tables if t.lower() == "enums"), None)
        if not t:
            return enums
        cols = table_columns(self.con, t)
        tc, vc, lc = pick(cols, "Type"), pick(cols, "Value"), pick(cols, "LocId")
        if not (tc and vc and lc):
            return enums
        for typ, val, lid in self.con.execute(f'SELECT "{tc}", "{vc}", "{lc}" FROM "{t}"'):
            name = self.loc.get(lid)
            if name:
                enums.setdefault(str(typ).lower(), {})[int(val)] = name
        return enums

    def _enum_list(self, raw, enum_name, fallback=None):
        if raw is None or raw == "":
            return []
        parts = [p for p in re.split(r"[,\s]+", str(raw)) if p.strip().lstrip("-").isdigit()]
        table = self.enums.get(enum_name.lower(), {})
        out = []
        for p in parts:
            v = int(p)
            out.append(table.get(v) or (fallback or {}).get(v) or str(v))
        return out

    def cards(self):
        t = next((t for t in self.tables if t.lower() == "cards"), None)
        if not t:
            raise RuntimeError(f"No 'Cards' table in Arena DB (tables: {self.tables})")
        cols = table_columns(self.con, t)
        c = {
            "grp": pick(cols, "GrpId", "GrpID", "Id"),
            "title": pick(cols, "TitleId", "TitleID"),
            "alt": pick(cols, "AltTitleId"),
            "inter": pick(cols, "InterchangeableTitleId"),
            "set": pick(cols, "ExpansionCode", "Set", "SetCode"),
            "dset": pick(cols, "DigitalReleaseSet"),
            "num": pick(cols, "CollectorNumber"),
            "rar": pick(cols, "Rarity"),
            "col": pick(cols, "Colors", "Color"),
            "super": pick(cols, "Supertypes"),
            "types": pick(cols, "Types"),
            "sub": pick(cols, "Subtypes"),
            "typetext": pick(cols, "TypeTextId"),
            "subtext": pick(cols, "SubtypeTextId"),
            "digital": pick(cols, "IsDigitalOnly"),
            "rebal": pick(cols, "IsRebalanced"),
            "token": pick(cols, "IsToken"),
            "primary": pick(cols, "IsPrimaryCard"),
            "draft": pick(cols, "DraftContent"),
            "mana": pick(cols, "OldSchoolManaText"),
        }
        if not c["grp"]:
            raise RuntimeError(f"Can't find GrpId column in Cards (columns: {cols})")
        sel = [k for k, v in c.items() if v]
        q = "SELECT " + ", ".join(f'"{c[k]}"' for k in sel) + f' FROM "{t}"'
        out = {}
        for row in self.con.execute(q):
            r = dict(zip(sel, row))
            grp = int(r["grp"])
            name = self.loc.get(r.get("title")) if "title" in r else None
            rarity = r.get("rar")
            rar_name = ""
            if rarity is not None and str(rarity).lstrip("-").isdigit():
                rar_name = (self.enums.get("rarity", {}).get(int(rarity))
                            or RARITY_FALLBACK.get(int(rarity), str(rarity)))
            color_str = colors_to_letters(r.get("col"))
            # Preferred: Arena's own pre-written type text ("Legendary Creature")
            main_t = self.loc.get(r.get("typetext")) if r.get("typetext") else None
            sub_t = self.loc.get(r.get("subtext")) if r.get("subtext") else None
            if main_t:
                type_line = main_t + (f" — {sub_t}" if sub_t else "")
            else:  # fallback: build it from enum codes
                type_line = " ".join(
                    self._enum_list(r.get("super"), "supertype")
                    + self._enum_list(r.get("types"), "cardtype"))
                subs = self._enum_list(r.get("sub"), "subtype")
                if subs:
                    type_line += " — " + " ".join(subs)
            # Some cards have a second name (Universes Beyond <-> Omenpaths/
            # Universes Within versions, crossover printings). Keep both.
            alt_name = ""
            for k in ("inter", "alt"):
                lid = r.get(k)
                if lid:
                    n2 = self.loc.get(lid)
                    if n2 and n2 != name:
                        alt_name = n2
                        break
            out[grp] = {
                "Name": name or "",
                "Alternate Name": alt_name,
                "Set": (r.get("set") or r.get("dset") or "").upper(),
                "Collector Number": r.get("num") or "",
                "Rarity": rar_name,
                "Colors": color_str or ("Colorless" if "col" in r else ""),
                "Type": type_line.strip(),
                "Digital Only": "Yes" if r.get("digital") else "",
                "Rebalanced (Alchemy)": "Yes" if r.get("rebal") else "",
                "_token": bool(r.get("token")),
                "_rebal": bool(r.get("rebal")),
                "_primary": bool(r.get("primary")),
                "_draft": bool(r.get("draft")),
                "_rar_n": int(rarity) if str(rarity).lstrip("-").isdigit() else 0,
                "_has_title": bool(name),
                # Arena's own mana cost; Scryfall's value replaces it when found
                "Mana Cost": parse_mana(r.get("mana"))[0],
                "Mana Value": parse_mana(r.get("mana"))[1] if r.get("mana") or "mana" in r else "",
            }
        return out



# --------------------------------------------------------------------------- #
# Scryfall enrichment (set names, format legality, rules text), cached for a week
# --------------------------------------------------------------------------- #
# Scryfall objects that aren't playable cards. Art-series cards are named like
# "Mountain // Mountain" and are "not legal" everywhere; before v1.6 they could
# claim a real card's name first and mark it Not legal (Mountain, Burst
# Lightning, The Infamous Cruelclaw...). They're skipped now.
SKIP_LAYOUTS = {"art_series", "token", "double_faced_token", "emblem", "planar",
                "scheme", "vanguard", "augment", "host"}
ORACLE_CACHE = "scryfall_oracle.json"   # v1.6+: legality + rules text per name
SCRYFALL_HEADERS = {"User-Agent": f"MTGACollectionExporter/{VERSION}",
                    "Accept": "application/json;q=0.9,*/*;q=0.8"}


def scryfall_json(url, timeout=60):
    req = urllib.request.Request(url, headers=SCRYFALL_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url, dest):
    req = urllib.request.Request(url, headers=SCRYFALL_HEADERS)
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                print(f"\r  downloading card data... {got >> 20}/{total >> 20} MB", end="")
    print()


def iter_cards(path):
    """Yield card dicts from a Scryfall bulk file: gzip or plain, JSON-lines or one JSON array."""
    with open(path, "rb") as f:
        gz = f.read(2) == b"\x1f\x8b"
    opener = (lambda: gzip.open(path, "rt", encoding="utf-8")) if gz else \
             (lambda: open(path, encoding="utf-8"))
    with opener() as f:
        first = ""
        while not first:
            ch = f.read(1)
            if not ch:
                return
            first = ch.strip()
    if first == "[":
        with opener() as f:
            yield from json.load(f)
        return
    with opener() as f:
        for line in f:
            line = line.strip().rstrip(",")
            if line.startswith("{"):
                yield json.loads(line)


def _faces_join(c, key, sep=" // "):
    """A field from the card, or from each face joined (split / DFC / adventure cards)."""
    if c.get(key):
        return c[key]
    vals = [fc.get(key, "") for fc in c.get("card_faces") or []]
    return sep.join(v for v in vals if v)


def oracle_entry(c, fmt_keys):
    """The bits of a Scryfall card we keep in the cache."""
    faces = c.get("card_faces") or []
    if faces and not c.get("oracle_text"):
        text = "\n//\n".join(
            (f"{fc.get('name', '')}: " if len(faces) > 1 else "") + (fc.get("oracle_text") or "")
            for fc in faces)
    else:
        text = c.get("oracle_text") or ""
    lg = c.get("legalities") or {}
    cmc = c.get("cmc")
    return {
        "legal": {k: lg[k] for k in fmt_keys if k in lg},
        "mana_cost": _faces_join(c, "mana_cost"),
        "cmc": int(cmc) if isinstance(cmc, (int, float)) and cmc == int(cmc) else cmc,
        "color_identity": "".join(x for x in COLOR_ORDER if x in (c.get("color_identity") or [])),
        "power": _faces_join(c, "power", " / "),
        "toughness": _faces_join(c, "toughness", " / "),
        "loyalty": _faces_join(c, "loyalty", " / "),
        "keywords": ", ".join(c.get("keywords") or []),
        "type_line": c.get("type_line") or _faces_join(c, "type_line"),
        "text": text,
    }


def build_oracle_index(bulk_path, fmt_keys):
    """{card name: oracle_entry}. A card's full name beats a face name
    ("Fire // Ice" vs "Fire"), and a playable card always beats a non-card
    object with the same name."""
    index, prio = {}, {}
    for c in iter_cards(bulk_path):
        if c.get("layout") in SKIP_LAYOUTS:
            continue
        entry = oracle_entry(c, fmt_keys)
        full = c.get("name", "")
        base = 2 if c.get("set_type") == "funny" else 0   # Un-sets / playtest cards lose ties
        names = [(full, base)]
        names += [(p.strip(), base + 1) for p in full.split("//") if "//" in full]
        names += [(fc.get("name", ""), base + 1) for fc in c.get("card_faces") or []]
        for n, p in names:
            if not n:
                continue
            if n not in index or p < prio[n]:
                index[n], prio[n] = entry, p
    return index


def load_scryfall(cache_dir, max_age_days=7, refresh=False):
    """Returns (sets, oracle): sets = {CODE: {name, released}},
    oracle = {card name: oracle_entry}. Uses a cache; on any network
    failure falls back to an old cache, or returns empty dicts."""
    os.makedirs(cache_dir, exist_ok=True)
    sets_f = os.path.join(cache_dir, "scryfall_sets.json")
    legal_f = os.path.join(cache_dir, ORACLE_CACHE)
    old_f = os.path.join(cache_dir, "scryfall_legality.json")
    if os.path.isfile(old_f):   # pre-1.6 cache had the art-series bug; drop it
        try:
            os.remove(old_f)
        except OSError:
            pass
    fresh = all(os.path.isfile(f) and
                time.time() - os.path.getmtime(f) < max_age_days * 86400
                for f in (sets_f, legal_f))
    if not fresh or refresh:
        print("Updating set names, legality + rules text from Scryfall (weekly)...")
        try:
            sets = {}
            for st in scryfall_json("https://api.scryfall.com/sets").get("data", []):
                info = {"name": st.get("name", ""), "released": st.get("released_at", "")}
                for code in (st.get("code"), st.get("arena_code")):
                    if code:
                        # an explicit arena_code mapping wins over a plain code match
                        if code == st.get("arena_code") or code.upper() not in sets:
                            sets[code.upper()] = info
            bulk = scryfall_json("https://api.scryfall.com/bulk-data").get("data", [])
            entry = next((b for b in bulk if b.get("type") == "oracle_cards"), None)
            if not entry:
                raise RuntimeError("no oracle_cards entry in Scryfall bulk-data")
            # Scryfall now serves gzipped JSON-lines (jsonl_download_uri);
            # older API versions served one big JSON file (download_uri).
            uri = entry.get("jsonl_download_uri") or entry.get("download_uri")
            if not uri:
                raise RuntimeError(f"no download link in bulk-data entry (keys: {sorted(entry)})")
            tmp = os.path.join(cache_dir, "oracle_cards.tmp")
            download(uri, tmp)
            legal = build_oracle_index(tmp, [k for k, _ in LEGAL_FORMATS])
            os.remove(tmp)
            with open(sets_f, "w", encoding="utf-8") as f:
                json.dump(sets, f)
            with open(legal_f, "w", encoding="utf-8") as f:
                json.dump(legal, f)
            print(f"  {len(sets)} sets, {len(legal)} card names cached.")
        except Exception as e:
            print(f"  Scryfall update failed ({e}).")
            if not (os.path.isfile(sets_f) and os.path.isfile(legal_f)):
                print("  Continuing without set names / legality.")
                return {}, {}
            print("  Using the older cached copy.")
    with open(sets_f, encoding="utf-8") as f:
        sets = json.load(f)
    with open(legal_f, encoding="utf-8") as f:
        legal = json.load(f)
    return sets, legal


# --------------------------------------------------------------------------- #
# Mechanics tags: a rough "what does this card do / care about" label set,
# so engines can be found by filtering (e.g. Token maker + Sacrifice + Death
# trigger). Pattern matching on rules text - helpful, not perfect.
# --------------------------------------------------------------------------- #
MECHANIC_RULES = [
    # (tag, regex on lower-case rules text)
    ("Lifegain", r"\byou gain \w+ life|\bgain \d+ life|\blifelink\b|gains? that much life"),
    ("Lifegain payoff", r"whenever you gain life|if you gained( \d+ or more)? life|life you gained"),
    ("Drain", r"(opponent|each player|target player)s? loses? (\d+|x|that much) life"),
    ("Opponent lost life", r"opponents? (has |have )?lost (\w+ )?life|an opponent loses life|life (your |an )?opponents? (have |has )?lost"),
    ("Direct damage", r"deals? (\d+|x|that much) damage to (any target|each opponent|target (player|opponent))"),
    ("Removal", r"destroy (target|each|all)|exile target (creature|nonland|permanent|artifact|enchantment)"
                r"|deals? (\d+|x) damage to target creature|\bfights?\b|target creature gets -\d"),
    ("Counterspell", r"\bcounter target\b"),
    ("Bounce", r"return target [^.]*? to (its|their) owner'?s'? hand"),
    ("Token maker", r"\bcreates? [^.]*?\btokens?\b"),
    ("Go-wide payoff", r"creatures you control get|for each (other )?creature you control|"
                       r"(three|four|five) or more creatures"),
    ("Sacrifice outlet", r"sacrifice (a|an|another|one or more|x|any number of) "),
    ("Death trigger", r"\bdies\b|is put into a graveyard from the battlefield"),
    ("ETB", r"when(ever)? (this \w+|this|[^.]{0,40}?) enters"),
    ("Enters payoff", r"whenever (a|an|another|one or more) [^.]*?\benters?\b"),
    ("Attack trigger", r"whenever [^.]{0,40}\battacks?\b"),
    ("+1/+1 counters", r"\+1/\+1 counter"),
    ("-1/-1 counters", r"-1/-1 counter"),
    ("Card draw", r"\bdraws? (a|an|one|two|three|four|x|that many|\d+) cards?\b"),
    ("Discard", r"\bdiscards?\b"),
    ("Mill / self-mill", r"\bmills?\b|put the top [^.]*? into (your|their) graveyard"),
    ("Graveyard", r"from (your|a|their) graveyard|in your graveyard|cards? in graveyards?"),
    ("Reanimation", r"return [^.]*? from (your|a) graveyard to the battlefield"),
    ("Landfall", r"whenever a land (you control )?enters|\blandfall\b"),
    ("Mana / ramp", r"\badd \{|search your library for [^.]*?\bland|play an additional land"),
    ("Spells matter", r"whenever you cast (a|an|your (first|second))? ?(instant|sorcery|noncreature|spell)"
                      r"|instant (and|or) sorcery spells"),
    ("Artifacts matter", r"artifacts? you control|whenever [^.]*?\bartifact\b"),
    ("Enchantments matter", r"enchantments? you control|whenever [^.]*?\benchantment\b"),
    ("Blink", r"exile [^.]*?, then return|return (it|that card|them) to the battlefield"),
    ("Copy", r"\bcopy\b|\bcopies\b"),
    ("Tap / untap", r"\buntap target\b|\btap target\b|\buntap (it|this)"),
    ("Equipment / auras", r"equipped creature|enchanted creature|\battach\b"),
    ("Vehicles / crew", r"\bcrew \d|\bvehicles?\b"),
    ("Planeswalkers", r"planeswalkers? you control|loyalty abilit"),
    ("Legendary matters", r"legendary (creature|spell|permanent)s? you control|historic"),
]
_MECH_RE = [(t, re.compile(p)) for t, p in MECHANIC_RULES]

# plural -> singular for creature types whose plural isn't just +s
IRREGULAR_PLURALS = {"Mouse": "mice", "Elf": "elves", "Dwarf": "dwarves", "Wolf": "wolves",
                     "Ox": "oxen", "Fungus": "fungi", "Werewolf": "werewolves",
                     "Thief": "thieves", "Leech": "leeches", "Fox": "foxes", "Sphinx": "sphinxes",
                     "Octopus": "octopuses", "Moonfolk": "moonfolk", "Kithkin": "kithkin",
                     "Merfolk": "merfolk", "Leonin": "leonin", "Vedalken": "vedalken",
                     "Djinn": "djinn", "Sheep": "sheep", "Fish": "fish"}
# creature types too common as plain English to tag on
TYPE_STOPWORDS = {"Human", "Spirit", "Construct", "Elemental", "Citizen", "Scout",
                  "Warrior", "Soldier", "Advisor", "Noble", "Peasant", "Hero", "Villain"}


def creature_types(type_line):
    if "—" not in type_line:
        return []
    left = type_line.split("—")[0]
    if not any(w in left for w in ("Creature", "Kindred", "Tribal")):
        return []
    return [t for t in type_line.split("—", 1)[1].split() if t[:1].isupper()]


def build_type_patterns(rows):
    """One regex per creature type seen in the collection."""
    seen = set()
    for r in rows:
        for part in (r.get("Type") or "").split(" // "):
            seen.update(creature_types(part))
    pats = {}
    for t in sorted(seen - TYPE_STOPWORDS):
        plural = IRREGULAR_PLURALS.get(t, t.lower() + ("es" if t.lower().endswith(("s", "x", "ch", "sh")) else "s"))
        pats[t] = re.compile(rf"\b({re.escape(t.lower())}|{re.escape(plural)})\b")
    return pats


def mechanic_tags(text, name, type_pats, own_types, is_land=False):
    t = (text or "").lower()
    if not t:
        return ""
    for n in {name, *name.split(" // "), name.split(",")[0]}:   # own name / short name -> "this"
        if n:
            t = re.sub(rf"\b{re.escape(n.lower())}\b", "this", t)
    tags = [tag for tag, rx in _MECH_RE if rx.search(t)]
    if is_land:   # every land "adds" mana; that isn't ramp
        tags = [x for x in tags if x != "Mana / ramp"]
    # "this Lizard" is the card talking about itself, not caring about Lizards
    for ty in own_types:
        t = re.sub(rf"\bthis {re.escape(ty.lower())}\b", "this", t)
    tags += [f"Cares about {ty}" for ty, rx in type_pats.items() if rx.search(t)]
    return "; ".join(tags)


def enrich(rows, sets, legal, quiet=False):
    """Adds Set Name / Set Released / legality / rules-text columns.
    Returns the column list."""
    present = set()
    for v in legal.values():
        present.update(v.get("legal", {}).keys())
    fmts = [(k, col) for k, col in LEGAL_FORMATS if k in present]
    type_pats = build_type_patterns(rows)
    unmatched = 0
    for r in rows:
        si = sets.get((r.get("Set") or "").upper())
        if si:
            r["Set Name"], r["Set Released"] = si["name"], si["released"]
        o = None
        for n in (r.get("Name"), r.get("Alternate Name")):
            # Arena prefixes rebalanced cards "A-"; Scryfall does too, but try both
            for cand in (n, (n or "")[2:] if (n or "").startswith("A-") else None):
                if cand and cand in legal:
                    o = legal[cand]
                    break
            if o:
                break
        if o is None and legal:
            unmatched += 1
        o = o or {}
        for k, col in fmts:
            r[col] = LEGAL_WORDS.get(o.get("legal", {}).get(k, ""), "")
        if o:
            # keep Arena's own value when Scryfall's is empty
            r["Mana Cost"] = o.get("mana_cost") or r.get("Mana Cost", "")
            r["Mana Value"] = o.get("cmc") if o.get("cmc") not in (None, "") else r.get("Mana Value", "")
            r["Color Identity"] = o.get("color_identity", "") or "Colorless"
            r["Power"], r["Toughness"] = o.get("power", ""), o.get("toughness", "")
            r["Loyalty"] = o.get("loyalty", "")
            r["Keywords"] = o.get("keywords", "")
            r["Oracle Text"] = o.get("text", "")
            own = set()
            for part in (r.get("Type") or o.get("type_line", "")).split(" // "):
                own.update(creature_types(part))
            tl = r.get("Type") or o.get("type_line", "")
            r["Mechanics"] = mechanic_tags(o.get("text", ""), r.get("Name", ""), type_pats, own,
                                           is_land="Land" in tl and "Creature" not in tl)
    if legal and unmatched and not quiet:
        print(f"  ({unmatched} cards not found on Scryfall - legality / rules text left blank)")
    i = CSV_COLUMNS.index("Owned") + 1
    return CSV_COLUMNS[:i] + [col for _, col in fmts] + CSV_COLUMNS[i:]


def set_members(details):
    """grpIds that make up each set's main card list (what set completion counts).
    From Arena's DB: primary, booster ('DraftContent') cards; not tokens, not
    Alchemy rebalanced copies, not basic lands. Sets with no booster flag at all
    (e.g. J25) fall back to all their primary cards."""
    by_set = {}
    for g, d in details.items():
        if d.get("_token") or d.get("_rebal") or not d.get("_has_title") or d.get("_rar_n", 0) <= 1:
            continue
        if d.get("_primary"):
            by_set.setdefault(d.get("Set") or "?", []).append(g)
    members = set()
    for gs in by_set.values():
        members.update([g for g in gs if details[g].get("_draft")] or gs)
    return members


def build_full_rows(rows, details, members):
    """Owned rows plus one row per set card not owned in that set. Adds
    'In Set' and 'Owned (any printing)' (copies of that name across all sets -
    Arena lets any printing fill a deck slot)."""
    by_name = {}
    for r in rows:
        by_name[r["Name"]] = by_name.get(r["Name"], 0) + int(r["Owned"] or 0)
    owned_ids = {r["Arena ID"] for r in rows}
    full = [{**r, "In Set": "Yes" if r["Arena ID"] in members else "",
             "Owned (any printing)": by_name.get(r["Name"], 0)} for r in rows]
    seen = {(r["Set"], r["Name"]) for r in rows if r["Arena ID"] in members}
    for g in sorted(members, key=lambda g: (details[g].get("Set", ""), str(details[g].get("Collector Number", "")))):
        d = details[g]
        key = (d.get("Set"), d.get("Name"))
        if g in owned_ids or key in seen:
            continue
        seen.add(key)
        full.append({**{k: "" for k in CSV_COLUMNS}, **d, "Owned": 0, "New": "", "Arena ID": g,
                     "In Set": "Yes", "Owned (any printing)": by_name.get(d.get("Name"), 0)})
    return full


# --------------------------------------------------------------------------- #
# Inventory: gold, gems, wildcards (v1.8)
# --------------------------------------------------------------------------- #
INVENTORY_COLUMNS = ["Date", "Gold", "Gems", "Common Wildcards", "Uncommon Wildcards",
                     "Rare Wildcards", "Mythic Wildcards", "Vault Progress",
                     # v2.0: collection totals, so this file doubles as your history (ArcVault History tab)
                     "Printings", "Copies", "Usable Copies", "Full Playsets"]


def collection_totals(rows):
    """Printings owned, copies, usable copies (max 4 per card name, any printing), full playsets."""
    per_name = {}
    for r in rows:
        per_name[r["Name"]] = per_name.get(r["Name"], 0) + int(r["Owned"] or 0)
    return {"Printings": len(rows), "Copies": sum(per_name.values()),
            "Usable Copies": sum(min(n, 4) for n in per_name.values()),
            "Full Playsets": sum(1 for n in per_name.values() if n >= 4)}


def pick_wildcards(fields):
    """Find wildcard counts among the inventory object's fields by name, so a
    renamed field ('wcRare', 'wildCardRares', ...) still matches."""
    out = {}
    low = {k.lower(): v for k, v in (fields or {}).items()}
    for rarity in ("mythic", "rare", "uncommon", "common"):
        for k, v in low.items():
            if ("wc" in k or "wild" in k) and rarity in k:
                if rarity == "common" and "uncommon" in k:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out[rarity] = int(v)
                    break
    for k, v in low.items():
        if "vault" in k and isinstance(v, (int, float)) and not isinstance(v, bool):
            # a garbled read shows up as a denormal like 6.5e-320 - leave blank rather than show 0%
            if 0 <= float(v) <= 100 and not (0 < abs(float(v)) < 1e-6):
                out["vault"] = round(float(v), 1)
            break
    return out


def read_inventory(daemon):
    """Returns a row for the inventory file (mtga_inventory.csv), or None. Never fails the export."""
    try:
        inv = daemon.get("/inventory", timeout=60)
    except Exception as e:
        print(f"  (couldn't read gold/gems/wildcards: {e})")
        return None
    fields = inv.get("fields")
    try:   # raw copy for troubleshooting if Arena renames things
        os.makedirs(P.cache_dir, exist_ok=True)
        with open(P.cache("inventory_fields.json"), "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=1, sort_keys=True)
    except OSError:
        pass
    wc = pick_wildcards(fields)
    row = {"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Gold": inv.get("gold", ""),
           "Gems": inv.get("gems", ""),
           "Common Wildcards": wc.get("common", ""), "Uncommon Wildcards": wc.get("uncommon", ""),
           "Rare Wildcards": wc.get("rare", ""), "Mythic Wildcards": wc.get("mythic", ""),
           "Vault Progress": wc.get("vault", "")}
    if fields is None:
        print("  Gold/gems read. For wildcards, rebuild the daemon with the patched source "
              "(see README: 'Wildcards').")
    elif not wc:
        print("  Gold/gems read, but no wildcard fields recognised - see cache\\inventory_fields.json.")
    return row


def inventory_changed(path, row):
    """True if this row differs from the last one recorded (ignoring the date)."""
    if not os.path.isfile(path):
        return True
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return True
    if not rows:
        return True
    last = rows[-1]
    return any(str(last.get(k, "")) != str(row.get(k, "")) for k in INVENTORY_COLUMNS if k != "Date")


def append_inventory(path, row):
    new = not os.path.isfile(path)
    if not new:
        # an older file without the newer columns: rewrite it once with the full header
        with open(path, newline="", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            header, old = r.fieldnames or [], list(r)
        if header != INVENTORY_COLUMNS:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=INVENTORY_COLUMNS, extrasaction="ignore")
                w.writeheader()
                w.writerows(old)
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INVENTORY_COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def write_txt(path, rows):
    """Plain list: '4 Lightning Strike', one line per card name, printings
    combined, A-Z. Same layout Arena, Moxfield, Archidekt etc. import."""
    totals = {}
    for r in rows:
        name = r.get("Name") or ""
        if name and not name.startswith("Unknown ("):
            totals[name] = totals.get(name, 0) + int(r.get("Owned") or 0)
    lines = [f"{n} {name}" for name, n in sorted(totals.items(), key=lambda kv: kv[0].lower())]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    return len(lines)


# --------------------------------------------------------------------------- #
# CSV + history
# --------------------------------------------------------------------------- #
def read_previous(path):
    prev = {}
    if not os.path.isfile(path):
        return prev
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                prev[int(row["Arena ID"])] = row
            except (KeyError, ValueError):
                pass
    return prev


def write_csv(path, rows, columns):
    tmp = path + ".tmp"
    # utf-8-sig so Excel shows accented names (e.g. "Lim-Dûl") correctly
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def inspect(args):
    """Dump what we can see so a broken mapping can be fixed quickly."""
    lines = [f"ArcVault v{VERSION} inspect report", ""]
    d = Daemon(args.port)
    db_path = args.db
    for p in ["/status", "/allCardsConnectionString"]:
        try:
            r = d.get(p, timeout=10)
            lines.append(f"{p}: {json.dumps(r)}")
            if p == "/allCardsConnectionString" and not db_path:
                db_path = path_from_connection_string(r.get("connectionString"))
        except Exception as e:
            lines.append(f"{p}: FAILED {e}")
    try:
        cards = d.get("/cards", timeout=120).get("cards", [])
        lines.append(f"/cards: {len(cards)} entries, first 3: {json.dumps(cards[:3])}")
    except Exception as e:
        lines.append(f"/cards: FAILED {e}")
    if not db_path or not os.path.isfile(db_path):
        g = guess_db_paths()
        db_path = g[0] if g else db_path
    lines.append(f"\nDB path: {db_path}")
    if db_path and os.path.isfile(db_path):
        db = CardDB(db_path)
        for t in db.tables:
            n = db.con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            lines.append(f"  table {t} ({n} rows): {table_columns(db.con, t)}")
        lines.append(f"\nEnum groups found: { {k: len(v) for k, v in db.enums.items()} }")
        t = next((t for t in db.tables if t.lower() == "enums"), None)
        if t:
            lines.append("Enum Type values: " + str([r[0] for r in db.con.execute(
                f'SELECT DISTINCT "{table_columns(db.con, t)[0]}" FROM "{t}"')]))
        sample = list(db.cards().items())[:8]
        lines.append("\nSample decoded cards:")
        for g, c in sample:
            lines.append(f"  {g}: {c}")
        lines.append("\nRaw Cards rows:")
        ct = next((t for t in db.tables if t.lower() == "cards"), None)
        if ct:
            cols = table_columns(db.con, ct)
            for row in db.con.execute(f'SELECT * FROM "{ct}" LIMIT 3'):
                lines.append("  " + str(dict(zip(cols, row))))
        db.close()
    out = os.path.join(args.out, "inspect_report.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:12]))
    print(f"\nFull report written to {out}")


def main():
    ap = argparse.ArgumentParser(description="Export your MTG Arena collection to CSV.")
    ap.add_argument("--port", type=int, default=6842, help="daemon port (default 6842, the daemon's own default)")
    ap.add_argument("--daemon", help="path to mtga-tracker-daemon.exe (auto-start if not running)")
    ap.add_argument("--db", help="path to Raw_CardDatabase_*.mtga (normally auto-detected)")
    ap.add_argument("--out", default=P.data_dir,
                    help="folder for your files (default: next to this script, or Documents\\ArcVault when installed)")
    ap.add_argument("--where", action="store_true", help="print where ArcVault keeps its files, then stop")
    ap.add_argument("--force", action="store_true", help="write even if safety checks fail")
    ap.add_argument("--baseline", help="measure the 'New' column against this earlier CSV "
                    "(the auto-export watcher uses the collection from the start of the Arena session)")
    ap.add_argument("--no-scryfall", action="store_true", help="skip set names / legality lookup")
    ap.add_argument("--no-site-exports", action="store_true",
                    help="don't write the exports/ folder (Moxfield, ManaBox, Archidekt, ...)")
    ap.add_argument("--refresh-scryfall", action="store_true", help="re-download Scryfall data now")
    ap.add_argument("--inspect", action="store_true",
                    help="print Arena DB layout + daemon info to inspect_report.txt (for debugging)")
    args = ap.parse_args()

    if args.where:
        print(P.describe())
        return
    print(f"ArcVault v{VERSION} - collection export")
    if args.inspect:
        return inspect(args)
    daemon = Daemon(args.port)
    proc = None

    # 1. daemon up?
    print(f"Looking for mtga-tracker-daemon on port {args.port}...")
    if not daemon.reachable():
        # maybe it was started by hand on another common port
        for alt in (6842, 9000):
            if alt != args.port and Daemon(alt).reachable():
                print(f"  Found it on port {alt} instead.")
                daemon, args.port = Daemon(alt), alt
                break
    if not daemon.reachable():
        print("  Not running - trying to start it.")
        exe = args.daemon or os.environ.get("MTGA_DAEMON_EXE")
        if not exe:
            exe = P.daemon_exe()          # prefers the published build, newest first
        proc = start_daemon(exe, args.port)
        if proc:
            for _ in range(20):
                time.sleep(1)
                if daemon.reachable():
                    break
        if not daemon.reachable():
            where = P.program_dir
            if not exe:
                sys.exit("mtga-tracker-daemon isn't running, and no mtga-tracker-daemon.exe was found in\n"
                         f"  {where}\n"
                         "Put the daemon (exe + its DLLs) in a 'daemon' subfolder there - or run \"Build Daemon.bat\" - see README step 2.")
            sys.exit(f"Started {exe} but it didn't answer on port {args.port}.\n"
                     "Check its console window for errors (try running the .bat as administrator).")

    # 2. Arena up?
    st = wait_for_arena(daemon)
    if not st:
        sys.exit("Daemon is running but can't see MTG Arena. Launch Arena, log in, "
                 "wait at the Home screen, then run this again.")
    print(f"Daemon {st.get('daemonVersion', '?')} sees Arena (pid {st.get('processId')}).")

    # 3. owned cards
    try:
        owned_raw = daemon.get("/cards", timeout=120).get("cards", [])
    except RuntimeError as e:
        # the daemon can't read the collection while Arena is still loading / logging in
        sys.exit("Arena isn't ready yet - the daemon couldn't read your collection "
                 f"({str(e)[:80]}...). Wait at the Home screen and try again.")
    owned = {}
    for c in owned_raw:
        try:
            g, n = int(c["grpId"]), int(c["owned"])
        except (KeyError, TypeError, ValueError):
            continue
        if n > 0:
            owned[g] = owned.get(g, 0) + n
    print(f"Owned: {len(owned)} distinct cards, {sum(owned.values())} copies.")

    inventory = read_inventory(daemon)
    if inventory:
        wc = [inventory[k] for k in ("Mythic Wildcards", "Rare Wildcards", "Uncommon Wildcards", "Common Wildcards")]
        print(f"Gold {inventory['Gold']}, gems {inventory['Gems']}" +
              (f", wildcards M/R/U/C {'/'.join(str(x) for x in wc)}" if any(x != "" for x in wc) else ""))

    # 4. card details
    details, source = {}, ""
    db_path = args.db
    if not db_path:
        try:
            db_path = path_from_connection_string(
                daemon.get("/allCardsConnectionString").get("connectionString"))
        except Exception as e:
            print(f"  (daemon didn't give DB path: {e})")
    if not db_path or not os.path.isfile(db_path):
        guesses = guess_db_paths()
        db_path = guesses[0] if guesses else db_path
    if db_path and os.path.isfile(db_path):
        try:
            db = CardDB(db_path)
            details = db.cards()
            db.close()
            source = f"Arena DB ({os.path.basename(db_path)})"
        except Exception as e:
            print(f"  Couldn't read Arena DB ({e}); falling back to daemon /allCards.")
    # names from daemon fill any gaps (or everything, if DB failed)
    missing = [g for g in owned if not details.get(g, {}).get("Name")]
    if missing:
        try:
            for c in daemon.get("/allCards", timeout=120).get("cards", []):
                g = int(c.get("grpId", -1))
                if g in owned:
                    d = details.setdefault(g, {})
                    if not d.get("Name"):
                        d["Name"] = c.get("title", "")
                    if not d.get("Set"):
                        d["Set"] = (c.get("expansionCode") or "").upper()
            source = source or "daemon /allCards (name + set only)"
        except Exception as e:
            print(f"  /allCards failed too: {e}")
    print(f"Card details from: {source or 'nothing - IDs only'}")

    rows, unknown = [], 0
    for g, n in owned.items():
        d = details.get(g, {})
        if not d.get("Name"):
            unknown += 1
        rows.append({**{k: "" for k in CSV_COLUMNS}, **d, "Owned": n, "Arena ID": g,
                     "Name": d.get("Name") or f"Unknown ({g})"})
    rows.sort(key=lambda r: (r["Set"], r["Name"].lower(), str(r["Collector Number"])))

    columns = CSV_COLUMNS
    if not args.no_scryfall:
        sets, legal = load_scryfall(P.cache_dir,
                                    refresh=args.refresh_scryfall)
        columns = enrich(rows, sets, legal)

    # 5. safety checks
    os.makedirs(args.out, exist_ok=True)
    latest = P.file("collection", args.out)
    latest_name = os.path.basename(latest)
    prev = read_previous(latest)
    base = read_previous(args.baseline) if args.baseline and os.path.isfile(args.baseline) else prev
    for r in rows:
        before = int(base.get(r["Arena ID"], {}).get("Owned") or 0) if base else 0
        r["New"] = (r["Owned"] - before) if base and r["Owned"] > before else ""
    # v1.9: did anything change since the last export? (frequent auto-exports shouldn't pile up snapshots)
    changed = not prev or any(int(prev.get(r["Arena ID"], {}).get("Owned") or 0) != r["Owned"] for r in rows) \
        or len(prev) != len(rows)
    if not args.force:
        if not rows:
            sys.exit("Got an EMPTY collection - not overwriting your CSV. "
                     "(Is Arena fully loaded? Try again from the Home screen, or use --force.)")
        if prev and len(rows) < 0.8 * len(prev):
            sys.exit(f"Collection dropped from {len(prev)} to {len(rows)} distinct cards - "
                     "that looks wrong (Arena update/half-loaded?). Not overwriting. Use --force if it's real.")
        if unknown > 0.2 * len(rows):
            print(f"WARNING: {unknown} cards have no name - the card DB lookup may be broken.")

    # 6. write latest + snapshot + changes
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    try:
        write_csv(latest, rows, columns)
    except PermissionError:
        alt = os.path.join(args.out, f"{os.path.splitext(latest_name)[0]}_{stamp}.csv")
        write_csv(alt, rows, columns)
        try:
            os.remove(latest + ".tmp")
        except OSError:
            pass
        print(f"\nNOTE: {latest_name} is open in another program (Excel?), so it can't be replaced.\n"
              f"      Saved this export as {os.path.basename(alt)} instead.\n"
              f"      Close the file and run the export again to update {latest_name}.")
        latest = alt
    if changed:
        snap_dir = P.snapshots_dir(args.out)
        os.makedirs(snap_dir, exist_ok=True)
        write_csv(os.path.join(snap_dir, f"collection_{stamp}.csv"), rows, columns)
    txt = P.file("collection_txt", args.out)
    try:
        n_txt = write_txt(txt, rows)
        print(f"Wrote {n_txt} card names to {os.path.basename(txt)}")
    except PermissionError:
        print(f"NOTE: {os.path.basename(txt)} is open in another program - text list not updated.")

    inv_path = P.file("inventory", args.out)
    if inventory is None:     # old daemon / read failed: still record collection history
        inventory = {"Date": datetime.now().strftime("%Y-%m-%d %H:%M")}
    inventory.update(collection_totals(rows))
    if inventory_changed(inv_path, inventory):
        try:
            append_inventory(inv_path, inventory)
        except PermissionError:
            print(f"NOTE: {os.path.basename(inv_path)} is open in another program - inventory not recorded.")

    # v1.7: every Arena set card, owned or not - set completion + missing cards in ArcVault
    if details:
        members = set_members(details)
        full = build_full_rows(rows, details, members)
        if not args.no_scryfall and legal:
            enrich(full, sets, legal, quiet=True)
        full_path = P.file("collection_full", args.out)
        try:
            write_csv(full_path, full, columns + FULL_EXTRA)
            missing = len({r["Name"] for r in full if not r["Owned (any printing)"]})
            print(f"Wrote {os.path.basename(full_path)} ({len(full)} rows; {missing} set cards you own no copy of)")
        except PermissionError:
            print(f"NOTE: {os.path.basename(full_path)} is open in another program - not updated.")

    # v2.0: the same collection in the import formats of popular sites (exports/ folder)
    if not args.no_scryfall and not args.no_site_exports:
        try:
            import mtga_site_exports as site
            owned = [r for r in rows if int(r.get("Owned") or 0) > 0]
            prints = site.load_prints(P.cache_dir, [r["Arena ID"] for r in owned],
                                      scryfall_json, download, iter_cards, refresh=args.refresh_scryfall,
                                      owned_names={r["Name"] for r in owned})
            site.write_site_exports(P.exports_dir(args.out), rows, prints)
        except ImportError:
            print("NOTE: mtga_site_exports.py is missing - site exports skipped.")
        except Exception as e:
            print(f"NOTE: site exports failed ({e}) - your main files were still written.")

    if prev:
        changes = []
        for r in rows:
            before = int(prev.get(r["Arena ID"], {}).get("Owned") or 0)
            if r["Owned"] != before:
                changes.append({**r, "Before": before, "After": r["Owned"],
                                "Change": r["Owned"] - before})
        now_ids = {r["Arena ID"] for r in rows}
        for g, p in prev.items():
            if g not in now_ids:
                before = int(p.get("Owned") or 0)
                changes.append({**p, "Before": before, "After": 0, "Change": -before})
        if changes:
            ch_dir = P.changes_dir(args.out)
            os.makedirs(ch_dir, exist_ok=True)
            cols = ["Change", "Before", "After"] + columns
            changes.sort(key=lambda r: (-int(r["Change"]), r["Name"]))
            write_csv(os.path.join(ch_dir, f"changes_{stamp}.csv"), changes, cols)
            gained = sum(c["Change"] for c in changes if c["Change"] > 0)
            print(f"Changes since last run: {len(changes)} cards (+{gained} copies) "
                  f"-> changes/changes_{stamp}.csv")
        else:
            print("No changes since last run (no new snapshot saved).")

    print(f"\nWrote {len(rows)} cards to {latest}")
    if unknown:
        print(f"({unknown} cards couldn't be named - they're listed as 'Unknown (id)')")
    if proc:
        try:
            urllib.request.urlopen(urllib.request.Request(daemon.base + "/shutdown", method="POST"), timeout=5)
        except Exception:
            proc.terminate()


def cli():
    """Run one export from the command line (also ArcVault.exe --export)."""
    code = 0
    try:
        main()
    except SystemExit as e:
        # print the message BEFORE pausing (otherwise it's hidden behind the pause)
        if isinstance(e.code, str):
            print("\nERROR: " + e.code)
            code = 1
        else:
            code = e.code or 0
    except urllib.error.URLError as e:
        print(f"\nERROR: Network error talking to the daemon: {e}")
        code = 1
    except KeyboardInterrupt:
        code = 1
    except Exception:
        import traceback
        print("\nUNEXPECTED ERROR - copy this so it can be fixed:")
        traceback.print_exc()
        code = 1
    if os.environ.get("MTGA_PAUSE") == "1":
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    sys.exit(code)


if __name__ == "__main__":
    cli()
