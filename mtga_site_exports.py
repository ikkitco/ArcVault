"""
Site exports (v2.4): your MTGA collection in the import formats of popular
collection / deckbuilding sites, written to the exports/ folder.

Every printing is matched to Scryfall by its Arena ID - or, where Scryfall has no
Arena ID yet, by name + set + collector number - so the files carry the
paper set code, collector number and Scryfall ID - the most reliable way for
sites to pick the exact printing.

  moxfield.csv      Moxfield  > Collection > Import (CSV)
  manabox.csv       ManaBox   > Collection > Import > CSV
  manabox.txt       ManaBox   > Collection > Import > text / file (phone file picker wants .txt)
  (Archidekt: import moxfield.csv with its "Moxfield" option, or manabox.csv with "ManaBox - Single folder")
  mtggoldfish.csv   MTGGoldfish collection CSV (best known layout)
  deckstats.csv     deckstats.net CSV layout (best known; Moxfield also accepts it as "deckstats.net")
  collection_list.txt   "4 Lightning Strike (DMU) 137" - text import on most sites

Files are UTF-8 *without* a byte-order mark: some importers fail to recognise
the first column ("Count") when one is present.
"""

import csv
import json
import os
import time

PRINTS_CACHE = "scryfall_prints.json"
CACHE_VERSION = 2
SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "vanguard", "scheme", "planar"}


def _key(name):
    """Name key for matching: lower case, straight apostrophes, no Alchemy 'A-' prefix."""
    n = (name or "").strip().replace("\u2019", "'").lower()
    return n[2:] if n.startswith("a-") else n


def load_prints(cache_dir, owned_ids, scryfall_json, download, iter_cards, refresh=False,
                max_age_days=7, owned_names=None):
    """Printings index built from Scryfall's 'default_cards' bulk file (~80 MB compressed):
         {"v": 2, "arena": {arena_id: entry}, "names": {name_key: [entry, ...]}}
       entry = [scryfall_id, set_code, collector_number, set_name, digital, name, released]
    Refreshed weekly; after a day if you own a card whose *name* Scryfall didn't know yet
    (a brand-new set). Missing Arena IDs alone don't trigger it - Scryfall is often slow to
    add them, and the name index covers those printings."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, PRINTS_CACHE)
    idx = None
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                idx = json.load(f)
            if idx.get("v") != CACHE_VERSION:
                idx = None                              # older cache layout: rebuild
            else:
                idx["arena"] = {int(k): v for k, v in idx["arena"].items()}
        except (OSError, ValueError, AttributeError, KeyError):
            idx = None
    age = time.time() - os.path.getmtime(path) if os.path.isfile(path) else 1e12
    unknown = [n for n in (owned_names or []) if idx and _key(n) not in idx["names"]]
    if idx and not refresh and age < max_age_days * 86400 and not (unknown and age > 86400):
        return idx
    print("Updating printings from Scryfall (for site exports)...")
    try:
        bulk = scryfall_json("https://api.scryfall.com/bulk-data").get("data", [])
        entry = next((b for b in bulk if b.get("type") == "default_cards"), None)
        if not entry:
            raise RuntimeError("no default_cards entry in Scryfall bulk-data")
        uri = entry.get("jsonl_download_uri") or entry.get("download_uri")
        tmp = os.path.join(cache_dir, "default_cards.tmp")
        download(uri, tmp)
        new = build_index(iter_cards(tmp))
        os.remove(tmp)
        if new["arena"]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(new, f, separators=(",", ":"))
            idx = new
            print(f"  {len(new['arena'])} Arena IDs and {len(new['names'])} card names indexed.")
    except Exception as e:
        print(f"  Scryfall printings update failed ({e}).")
        if idx:
            print("  Using the older cached copy.")
    return idx or {"v": CACHE_VERSION, "arena": {}, "names": {}}


def build_index(cards):
    arena, names = {}, {}
    for c in cards:
        if c.get("layout") in SKIP_LAYOUTS or c.get("lang", "en") != "en":
            continue
        e = [c.get("id", ""), c.get("set", ""), c.get("collector_number", ""), c.get("set_name", ""),
             bool(c.get("digital")), c.get("name", ""), c.get("released_at", "")]
        if c.get("arena_id") is not None:
            arena[int(c["arena_id"])] = e
        full = c.get("name", "")
        keys = {_key(full)}
        if " // " in full:                       # Arena often names a two-faced card by its front
            keys.add(_key(full.split(" // ")[0]))
        for k in keys:
            names.setdefault(k, []).append(e)
    return {"v": CACHE_VERSION, "arena": arena, "names": names}


def _cn_sort(cn):
    digits = "".join(ch for ch in cn if ch.isdigit())
    return (not cn.isdigit(), int(digits) if digits else 10**9, cn)


def match_printing(idx, arena_id, name, set_code, cn):
    """Best Scryfall printing for one Arena printing. Returns (entry, how) or (None, None).
    how: 'id' (Arena ID), 'exact' (same set + number), 'set' (same set), 'alchemy'
    (Arena's yearly Y-set -> Scryfall's per-set Alchemy code), 'name' (another printing)."""
    e = idx["arena"].get(int(arena_id))
    if e:
        return e, "id"
    cands = idx["names"].get(_key(name), [])
    if not cands:
        return None, None
    s, n = (set_code or "").lower(), str(cn or "")
    same = [c for c in cands if c[1] == s]
    for c in same:
        if c[2] == n:
            return c, "exact"
    if same:
        return min(same, key=lambda c: _cn_sort(c[2])), "set"
    newest = lambda pool: max(pool, key=lambda c: (c[6], -_cn_sort(c[2])[1]))
    if len(s) == 3 and s[0] == "y" and s[1:].isdigit():
        alch = [c for c in cands if c[4] and c[1].startswith("y")]
        if alch:
            same_cn = [c for c in alch if c[2] == n]
            return newest(same_cn or alch), "alchemy"
    paper = [c for c in cands if not c[4]]
    return newest(paper or cands), "name"


def _items(rows, idx):
    """One entry per owned printing, in paper-site terms."""
    out, stats = [], {"id": 0, "exact": 0, "set": 0, "alchemy": 0, "name": 0, None: 0}
    digital = 0
    for r in rows:
        n = int(r.get("Owned") or 0)
        if n <= 0:
            continue
        e, how = match_printing(idx, r["Arena ID"], r.get("Name", ""), r.get("Set", ""),
                                r.get("Collector Number", ""))
        stats[how] += 1
        if e:
            sf_id, set_code, cn, set_name, dig, sf_name = e[:6]
            digital += bool(dig)
        else:
            sf_id, set_code, cn, set_name, sf_name = "", (r.get("Set") or "").lower(), r.get("Collector Number", ""), r.get("Set Name", ""), ""
        out.append({
            "qty": n,
            # Scryfall's name is the paper name ("Fable of the Mirror-Breaker // Reflection of Kiki-Jiki");
            # Alchemy rebalanced cards ("A-...") export as the original card, which is what sites list
            "name": sf_name or r.get("Name", ""),
            "set": (set_code or "").lower(),
            "cn": str(cn or ""),
            "set_name": set_name or r.get("Set Name", ""),
            "sf_id": sf_id,
            "digital": bool(e and e[4]),
            "key": _key(r.get("Name", "")),
            "rarity": (r.get("Rarity") or "").lower().replace("basic land", "common"),
        })
    # Rebalanced + original of the same printing now share a line: merge them
    merged = {}
    for i in out:
        k = (i["name"], i["set"], i["cn"])
        if k in merged:
            merged[k]["qty"] += i["qty"]
        else:
            merged[k] = i
    out = sorted(merged.values(), key=lambda x: (x["name"].lower(), x["set"], x["cn"]))
    return out, stats, digital


def _write(path, header, rows, quote_all=False, lf=False):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:       # no BOM on purpose
        w = csv.writer(f, quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL,
                       lineterminator="\n" if lf else "\r\n")
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)


def _paper_lines(items, idx):
    """{(name, set, cn): qty} with digital-only printings moved to a paper printing where one exists."""
    out = {}
    for i in items:
        k = (i["name"], i["set"], i["cn"])
        if i.get("digital"):
            paper = [c for c in idx["names"].get(i.get("key") or _key(i["name"]), []) if not c[4]]
            if paper:
                # prefer a normal printing: plain number, 3-letter set code, not The List (plst)
                # or promo sets, whose numbers ("M20-344", "75p") deckstats can't read
                p = max(paper, key=lambda c: (c[2].isdigit(), c[1] != "plst", len(c[1]) == 3,
                                              c[6], -_cn_sort(c[2])[1]))
                k = (p[5], p[1], p[2])
            else:
                k = (i["name"], "", "")
        out[k] = out.get(k, 0) + i["qty"]
    return dict(sorted(out.items(), key=lambda kv: (kv[0][0].lower(), kv[0][1], kv[0][2])))


def write_site_exports(folder, rows, prints):
    """Writes every site format into `folder` (the exports folder, from arcvault_paths)."""
    os.makedirs(folder, exist_ok=True)
    items, stats, digital = _items(rows, prints)
    written = []

    def save(name, header, data, **kw):
        try:
            _write(os.path.join(folder, name), header, data, **kw)
            written.append(name)
        except PermissionError:
            print(f"NOTE: exports\\{name} is open in another program - not updated.")

    # Moxfield: columns are matched by name; this is its documented header.
    save("moxfield.csv",
         ["Count", "Tradelist Count", "Name", "Edition", "Condition", "Language", "Foil", "Tags",
          "Last Modified", "Collector Number", "Alter", "Proxy", "Purchase Price"],
         [[i["qty"], 0, i["name"], i["set"], "Near Mint", "English", "", "", "", i["cn"], "False", "False", ""]
          for i in items])
    # ManaBox: needs name + set code (or a Scryfall ID); uses Scryfall's set codes.
    # Columns in ManaBox's current "single folder" export order (18 columns; ManaBox added
    # Signed, Proxy and Added in 2026). Archidekt's "ManaBox - Single folder" preset reads the
    # file by column position, so the count and order must match exactly. ManaBox itself
    # splits lines on LF only, so this file uses LF line endings.
    save("manabox.csv",
         ["Name", "Set code", "Set name", "Collector number", "Foil", "Rarity", "Quantity",
          "ManaBox ID", "Scryfall ID", "Purchase price", "Misprint", "Altered", "Signed",
          "Condition", "Language", "Proxy", "Purchase price currency", "Added"],
         [[i["name"], i["set"], i["set_name"], i["cn"], "normal", i["rarity"], i["qty"],
           "", i["sf_id"], "", "false", "false", "false", "near_mint", "en", "false", "", ""]
          for i in items], lf=True)
    # Archidekt has no format of its own: its importer reads other sites' files (moxfield.csv
    # with its Moxfield preset, manabox.csv with "ManaBox - Single folder"). Remove the old archidekt.csv from earlier versions.
    try:
        os.remove(os.path.join(folder, "archidekt.csv"))
    except OSError:
        pass
    # MTGGoldfish: the layout of its own collection CSV.
    save("mtggoldfish.csv",
         ["Card", "Set ID", "Set Name", "Quantity", "Foil"],
         [[i["name"], i["set"].upper(), i["set_name"], i["qty"], ""] for i in items])
    # deckstats.net: all fields quoted; is_foil empty for non-foil. deckstats doesn't carry
    # Arena-only sets (Alchemy: HBG, YMID...), so digital printings use the newest paper
    # printing of the same card, or the name alone when the card never had a paper printing.
    save("deckstats.csv",
         ["amount", "card_name", "is_foil", "set_code", "collector_number"],
         [[q, n, "", st, cn] for (n, st, cn), q in _paper_lines(items, prints).items()], quote_all=True)
    # ManaBox text import (the phone app's file picker only takes .txt): "4 Name (set) number",
    # set codes in lower case as in ManaBox's own examples.
    try:
        with open(os.path.join(folder, "manabox.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(f'{i["qty"]} {i["name"]} ({i["set"]}) {i["cn"]}'.rstrip() for i in items) + "\n")
        written.append("manabox.txt")
    except PermissionError:
        print("NOTE: exports\\manabox.txt is open in another program - not updated.")
    # Text list in Arena/MTGO style, one line per printing.
    try:
        with open(os.path.join(folder, "collection_list.txt"), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(f'{i["qty"]} {i["name"]} ({i["set"].upper()}) {i["cn"]}'.rstrip() for i in items) + "\n")
        written.append("collection_list.txt")
    except PermissionError:
        print("NOTE: exports\\collection_list.txt is open in another program - not updated.")

    note = f"Site exports: {len(items)} printings -> exports\\ ({', '.join(written)})"
    by_name = stats["exact"] + stats["set"] + stats["alchemy"] + stats["name"]
    if by_name:
        note += f"; {by_name} matched by name (Scryfall has no Arena ID for them yet)"
    if stats[None]:
        note += f"; {stats[None]} not found on Scryfall (Arena set codes used)"
    if digital:
        note += f"; {digital} are digital-only printings (Alchemy etc.) that paper-focused sites may skip"
    print(note)
    return written
