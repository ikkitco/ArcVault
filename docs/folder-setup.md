> This is the guide for running ArcVault as a plain folder with Python, or building it from source. Most people should use the installer instead: see the [main page](../README.md).

# ArcVault

Collection intelligence for MTG Arena, on your PC. (Formerly *MTGA Collection Exporter*.)

Exports every card you own in MTG Arena to `mtga_collection.csv`.

> **Before you use it:** ArcVault reads your collection from Arena's memory while the game runs. Wizards' terms of use (General Terms, section 2.2) don't allow third-party software that reads game data, and the stated penalty can include suspending your account. ArcVault only reads: it never changes the game, never sends anything anywhere, and gives no advantage in a match. Wizards hasn't acted against read-only collection tools like this as far as we know, but that's their call, not ours. See the FAQ at the end.

## One-time setup

1. **Python 3.8 or newer.** Install it from python.org and tick **"Add python.exe to PATH"**. You don't need to pip install anything.
2. **mtga-tracker-daemon, ArcVault's patched version:** https://github.com/ikkitco/mtga-tracker-daemon, branch **`arcvault`** (a fork of https://github.com/frcaton/mtga-tracker-daemon with the inventory patch below). Clone that branch into a `daemon` folder next to this script, then build it:
   - Install the **.NET 8 SDK** (x64) from https://dotnet.microsoft.com/download/dotnet/8.0. Get the **SDK**, not the Runtime. To check what you have, open a terminal and run `dotnet --list-sdks`. You need a line starting with `8.` or higher.
   - Double-click **Build Daemon.bat**. It runs `dotnet publish src\mtga-tracker-daemon -c Release -r win-x64 --self-contained` inside `daemon`, which is the same command the daemon's own release build uses.
   - The exe ends up in `daemon\src\mtga-tracker-daemon\bin\Release\net8.0\win-x64\publish\`. The exporter finds it there and starts it for you.
   - Don't use the original repo's ready-made `mtga-tracker-daemon-Windows.zip`: it doesn't have the patch, so wildcards won't be read.

Your folder should end up like this:
```
MTGA Export\
  mtga_collection_export.py
  Export MTGA Collection.bat
  Build Daemon.bat
  daemon\  (daemon source; the built exe lands in ...\publish\)
```

## Each time you want an update

1. Start MTG Arena, log in and wait at the **Home screen**.
2. Double-click **Export MTGA Collection.bat**.

## Output

| File | What it is |
|---|---|
| `mtga_collection.csv` | Your full collection. It's overwritten on every run, so link your spreadsheet to this file. |
| `snapshots\collection_<date>.csv` | A copy saved on every run, so you have a history |
| `mtga_collection.txt` | Plain list, one line per card with printings combined, e.g. `4 Lightning Strike`. Moxfield, Archidekt and most collection sites can import it. |
| `mtga_collection_full.csv` | Every card in every Arena set: the cards you own plus one row (Owned 0) for each set card you don't. It adds **In Set** and **Owned (any printing)** columns. Load this one into ArcVault for set completion and missing cards. |
| `mtga_inventory.csv` | Your history: one row whenever something changes. Date, gold, gems, wildcards by rarity, vault %, plus collection totals (v2.0). Wildcards need the rebuilt daemon (v1.8). |
| `auto_export.log` | What the automatic watcher did and when (v1.9). |
| `exports\` | The collection in Moxfield, ManaBox, Archidekt, MTGGoldfish and deckstats formats, plus a text list (v2.0). |
| `changes\changes_<date>.csv` | Only the cards whose count changed since the last run (new pack pulls, crafts) |

Columns: Name, Set, Collector Number, Rarity, Colors, Type, Owned, Arena ID, Digital Only, Rebalanced (Alchemy), then the Scryfall columns described below.

**Keeping a spreadsheet live:**
- In Excel, use Data → From Text/CSV → `mtga_collection.csv` → Load. After each export, press Data → Refresh All.
- In Google Sheets, re-import the file with File → Import → Replace current sheet.

## Engines tab (engine-builder v1)

ArcVault's **Engines** tab finds engines in *your* collection. It's rules-based and offline. It defaults to **Standard-legal** cards; change the Format dropdown for other formats.

- **Start from a theme:** every engine your collection supports (Sacrifice, Tokens & go-wide, +1/+1 counters, Spells, Graveyard, Lifegain, creature types, ...), with how many **enablers** (provide the resource) and **payoffs** (reward it) you own, and a strength bar. Click a theme to see both lists.
- **Start from a card:** type a card you own. **Feeds it** lists the cards that enable it; **It pays off** lists the cards it enables. Each group is labelled with its pairing, e.g. *Fodder makers → Sacrifice outlets (this card)*. By default only cards that share a colour with it are shown. Click any card name to jump to it.
- The left-hand filters (rarity, colour, type, mana value, search) narrow the lists too.

Pairings come from the mechanics tags (v1.6), card types and rules text. They're pointers to explore, not a power ranking, so expect the odd miss or stretch.

## Site exports and history (v2.0)

**Archidekt** has no format of its own. Its importer reads other sites' files. To import:
1. **Collection → Import**. You land on *Collection Import*, on the **CSV (recommended)** tab.
2. Open **Use formatting from…** and choose a preset that matches the file you'll upload:
   - **ManaBox – Single folder**, for `exports\manabox.csv` (best). This file carries each card's Scryfall ID, which pins the exact printing. Tested 17 Nov: every line imported, none ambiguous.
   - **Moxfield**, for `exports\moxfield.csv`. Also works (tested: 0 not found), but a handful of printings can come back "Ambiguous" because the file has no Scryfall ID.

   Don't use *ManaBox – Whole collection*: that preset expects the extra binder columns from a full ManaBox export.
3. Click **Set columns**.
4. Set the **Extra Options**:
   - **Skip first line:** **Yes**. Our files start with a header row.
   - **Default language:** **English (EN)**.
   - **Default condition:** **Near Mint (NM)**. Arena cards have no condition, so any value is fine.
   - **Default collection type:** **Arena**. This keeps them apart from any paper cards you track there.
   - **When a printing is ambiguous…:** leave it on **Import with "Unsure" tag**, then review those few afterwards.
5. Drop the file onto the box (max 5 MB; ours are well under) and click **Upload**.

Every export also writes an **`exports\`** folder with your collection in the import formats of popular sites (Moxfield, ManaBox, Archidekt via the ManaBox file, MTGGoldfish, deckstats). Each printing is matched to Scryfall by its Arena ID, so the files carry the paper set code, collector number and Scryfall ID: the most reliable way for a site to pick the exact printing. Scryfall is often slow to add Arena IDs (brand-new sets, Alchemy cards, some promos), so those printings are matched by name, set and collector number instead (v2.1).

| File | Import it at |
|---|---|
| `moxfield.csv` | Moxfield → Collection → Import (CSV). **Confirmed working.** |
| `manabox.csv` | ManaBox app → Collection → Import → CSV. Columns match ManaBox's current single-folder export (18 columns, v2.2), which is also what Archidekt's *ManaBox – Single folder* preset expects. |
| `manabox.txt` | ManaBox (phone app) text import. The app's file picker only accepts `.txt`, and phones often turn a `.csv` into `.xlsx` when you save it, so use this file. Lines look like `2 Surgical Extraction (2x2) 94`. |
| `mtggoldfish.csv` | MTGGoldfish collection import (**Premium members only**; beta: not yet tested). Free MTGGoldfish accounts can't import a collection, but deck creation accepts a pasted text list: use ArcVault's **Copy as text list** or Deck check. |
| `deckstats.csv` | deckstats.net: in your collection's **Import Cards** window, on the **Paste or file** tab, click **Load from file…**. Tip: pick a binder (e.g. one called "Arena") in **Into binder** to keep Arena cards apart from paper ones. Arena-only printings are listed under a paper printing of the same card. |
| `collection_list.txt` | Any site's **text** import: `4 Lightning Strike (DMU) 137`, one line per printing |

Notes:
- The files are UTF-8 without a byte-order mark, because some importers misread the first column when one is present.
- Digital-only printings (Alchemy and so on) are included. Paper-focused sites may skip them, and the export says how many there are.
- Alchemy rebalanced cards (`A-Ancestral Katana`) export as the original card at the same set and number, because sites don't list the rebalanced versions. If you own both, the counts are added together on one line.
- Arena's yearly Alchemy sets (Y23, Y24…) export under Scryfall's per-set Alchemy codes (YBRO, YONE, YLCI…).
- Printings data comes from Scryfall's per-printing file, about 80 MB, downloaded weekly (or after a day if you own a card whose name it doesn't know yet). `--no-site-exports` turns this off.

**History:** `mtga_inventory.csv` now also records your collection totals (printings, copies, usable copies, full playsets). A row is added whenever the collection *or* your gold, gems or wildcards change. Load it into ArcVault (slot 2) and open the **History** tab for charts over time.

## Automatic exports (v1.9)

Double-click **Auto-export ON.bat** once. From then on:
- A small background watcher starts with Windows. It has no window and uses almost no CPU.
- When MTG Arena opens, it exports about 3 minutes later (time to log in), then **every 15 minutes** while Arena stays open.
- It never exports mid-match. It waits 2 minutes and tries again.
- When Arena closes, it stops the daemon and goes back to waiting.

The exporter reads Arena's memory, so it can only run while Arena is open. Your files are at most 15 minutes old when you close the game.

Other details:
- **New** counts cards gained since the start of the current Arena session. Manual runs still count from the previous export.
- Snapshots, changes files and inventory rows are only saved when something actually changed, so frequent exports don't pile up files.
- Everything the watcher does is written to **`auto_export.log`** in this folder.
- **Auto-export OFF.bat** stops it and removes it from Windows startup.
- Manual exports still work at any time, even while the watcher runs.
- To get your files on other devices, put this folder (or `--out`) inside a cloud-synced folder such as OneDrive. The app doesn't need to know.

## New in v1.8: wildcards and deck check

**Wildcards need the patched daemon.** The official daemon only reports gold and gems. Our fork's `arcvault` branch has a small change (marked `[MTGA exporter patch]` in `HttpServer.cs` and `Models\InventoryResponseData.cs`) that also returns every number on Arena's inventory: wildcards, vault progress and so on.
1. Double-click **Build Daemon.bat**. It stops any running daemon first, because Windows won't replace a running .exe.
2. Run **Export MTGA Collection.bat** as usual.

Each export then adds a row to **`mtga_inventory.csv`** with the date, gold, gems, wildcards by rarity and vault %, so you can chart them over time. A raw copy of everything the daemon returned is kept in `cache\inventory_fields.json`. If Wizards renames the wildcard fields, the new names will show there.

To see exactly what the patch changes, compare the fork's `arcvault` branch with `master` on GitHub (29 lines added in `HttpServer.cs`, 5 in `InventoryResponseData.cs`, nothing removed).

**Deck check (ArcVault):**
1. Drop `mtga_collection_full.csv` and `mtga_inventory.csv` onto ArcVault together.
2. Open the **Deck check** tab.
3. Paste a deck. In Arena: Decks → select the deck → Export (it copies to the clipboard).

It shows:
- each card's owned, missing and craft rarity
- wildcards needed against wildcards you have
- a verdict: can build now, or short N rares, and so on

How it counts:
- Copies from any printing count, the same as Arena's deck builder.
- Missing cards are priced at their cheapest printing's rarity on Arena.
- Basic lands are free.
- Omenpaths and Universes Beyond names both match.
- You can edit the wildcard boxes to try "what if".

## New in v1.7

- **Set completion:** load `mtga_collection_full.csv` into ArcVault, then open the **Sets** tab. Each set shows three measures:
  - **Collected (this set):** only that set's own printings count.
  - **Usable (any printing):** copies from older or other sets count too, because Arena lets any printing fill a deck slot.
  - **Usable playsets (4):** up to 4 copies per card; extras don't count.

  Each set also has usable / total per rarity. The set lists come from Arena's own card database: booster cards only, so no basic lands, tokens, alternate-art copies or Alchemy rebalanced versions.
- **Missing cards:** ArcVault's **Show: Missing** button lists set cards you own no copy of, from any set.
- **New column:** the copies gained since the previous export. In ArcVault, use **Only cards new since the last export**.
- **Mana value:** Arena's own mana cost fills Mana Cost / Mana Value when Scryfall has nothing (Arena-only cards). ArcVault has a Mana value filter and a Cost column.

## ArcVault window (v0.1, in testing)

ArcVault can open in its own window instead of a browser tab.

1. **One-time setup:** double-click **ArcVault setup.bat**. It installs the window components (pywebview, pystray, pillow) and puts an **ArcVault** shortcut on your Desktop and in this folder, then opens ArcVault.
2. **After that:** open ArcVault from either shortcut.

The window loads your newest export from this folder by itself (`mtga_collection_full.csv` and `mtga_inventory.csv`), so there's nothing to load by hand. While it's open it checks every 20 seconds for a newer export, for example from the auto-export watcher, and updates itself. If something goes wrong, the details go to `arcvault_app.log`.

**First run:** with no export in the folder yet, ArcVault shows a welcome screen instead of an empty table: open MTG Arena, then **Turn on auto-export** or **Export once**. It ticks off when Arena is open, shows progress during the export (the first one also downloads card data from Scryfall, about a minute), and says in plain words if something stops it (Arena still loading, in a match, the reader blocked by antivirus). Your collection appears as soon as the export finishes.

**The Auto-export switch** (top of the window) is the on/off for automatic exports:
- **On:** while Arena is open, ArcVault exports your collection every 15 minutes, never mid-match. If Arena is already open when you switch on, it exports straight away; if not, it waits for Arena and does the first export a few minutes after Arena starts.
- **Off:** nothing runs. Switching off doesn't export.
- The switch's colour says what's happening: grey off, amber waiting for Arena (or retrying after a match), pulsing blue exporting soon / now, green exported (with how long ago and how many new cards).
- **Export now** does a one-off export straight away (Arena must be open). It works with auto-export off too: ArcVault starts its reader, exports once and stops it again.
- **Start with Windows** turns auto-export on when Windows starts. It's the same setting as *Auto-export ON.bat*, which still works.
**Tray icon** (by the clock, v0.3):
- With auto-export **on**, closing the window keeps ArcVault running in the tray (a one-time notice tells you the first time). With it **off**, closing the window quits.
- The icon's dot shows the auto-export state, in the same colours as the switch. Hover for the details ("Exported 3 min ago · +2 new").
- Click the icon to open ArcVault. Right-click for **Open ArcVault**, **Export now**, **Auto-export** (tick = on) and **Quit ArcVault**. Quit turns auto-export off.
- **Start with Windows** now starts ArcVault in the tray with auto-export on. (An older *Auto-export ON.bat* Startup shortcut is switched over to this automatically.)
- Opening ArcVault while it's already in the tray brings the existing window back instead of opening a second one.

## Browsing your collection

Open **ArcVault.html** (it's in this folder) and drop `mtga_collection.csv` onto it. You can then sort and filter by set, rarity, colour, card type, copies owned and format legality. The Sets tab summarises each set.

The page used to be called **MTGA Collection Viewer.html**; that file is no longer updated and can be deleted. ArcVault opens in its dark theme; the ◐ button top right switches to light.

ArcVault remembers the last file you loaded. Drop the new CSV on it after each export.

## Set names, legality and rules text

Each export adds these columns from Scryfall:

- **Set Name**, **Set Released**
- a legality column per format (Standard, Alchemy, Explorer, Historic, Timeless, Pioneer, Standard Brawl, Brawl): Legal / Not legal / Banned
- **Mana Cost**, **Mana Value**, **Color Identity**, **Power**, **Toughness**, **Loyalty**, **Keywords**
- **Oracle Text**: the card's current rules text. Split, adventure and double-faced cards show each face as `Face name: text`, separated by `//`.
- **Mechanics**: tags for what the card does or cares about, worked out from its rules text. Examples: `Lifegain`, `Lifegain payoff`, `Token maker`, `Sacrifice outlet`, `Death trigger`, `ETB`, `+1/+1 counters`, `Opponent lost life`, `Spells matter`, `Landfall`, and `Cares about <creature type>` (only for creature types you own). Filter on two tags at once (for example `Token maker` and `Sacrifice outlet`) to find engines. The tags come from pattern matching, so a few will be missing or wrong. Check the Oracle Text before building around one.

The data is saved in `cache\` and refreshed weekly. The first export of each week downloads about 160 MB.

v1.6 fixes a legality bug: Scryfall's "art series" cards (named like `Mountain // Mountain`, not legal anywhere) could take a real card's name first, so cards like Mountain, Burst Lightning and The Infamous Cruelclaw showed as **Not legal**. The first v1.6 export deletes the old `scryfall_legality.json` cache and downloads fresh data automatically.

- `--refresh-scryfall` downloads it again straight away (for example after a ban announcement).
- `--no-scryfall` skips the lookup.

## Safety checks

The script won't overwrite your CSV in two cases:
- the collection comes back **empty**
- it drops by **more than 20%** compared with last time

Both usually mean Arena was half-loaded or had just updated. Wait at the Home screen and run it again. If the drop is genuine, add `--force`.

## When Arena updates and something breaks

- **The daemon fails or returns 0 cards.** The Arena update broke the memory reader. Check frcaton's repo for a fix. If there is one, use **Sync fork** on our fork's `master`, merge `master` into `arcvault`, pull it into the `daemon` folder and run **Build Daemon.bat** again. Your CSV isn't touched in the meantime.
- **Names show as `Unknown (id)` or types are wrong.** Arena changed its card database layout. Run:
  ```
  python mtga_collection_export.py --inspect
  ```
  Then send me `inspect_report.txt` so the mapping can be updated.

## Options

```
--port 6842          daemon port (default 6842, the daemon's own default)
--daemon <path>      path to mtga-tracker-daemon.exe if it isn't in this folder
--db <path>          path to Arena's Raw_CardDatabase_*.mtga (normally auto-detected)
--out <folder>       where the CSVs go (default: this folder)
--force              skip the safety checks
--inspect            write a diagnostic report
```

## FAQ

**Is this allowed by Wizards?**
Not officially. Wizards of the Coast's General Terms (section 2.2) prohibit software that reads data from their games and third-party tools they haven't authorised. ArcVault does read Arena's memory, so it falls under that wording. It's read-only: it doesn't change anything in the game, doesn't automate play, doesn't look at your opponent's hand or deck, and sends nothing off your PC. Tools that work the same way have been used openly by the community for years without action that we know of, but the risk is yours to weigh. If you'd rather not take it, don't run the exporter.

**Does it send my data anywhere?**
No. Everything stays in your ArcVault folder. The only network call is to Scryfall, to download public card data (names, sets, legality).

**Fan Content**
ArcVault is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
