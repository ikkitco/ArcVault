# ArcVault: handover

**For:** GitHub Copilot, or any developer picking up this folder.
**Written:** 19 Nov 2026.
**Owner:** ikkitco (ikkit.co).

Read this first, then `ROADMAP.md` (decisions and status) and `README.md` (user instructions).

**Where the code lives:**
- ikkitco works in a plain project folder (folder mode), with git managed in GitHub Desktop.
- Private GitHub repo `ArcVault`, managed with GitHub Desktop.
  - **Work on `dev`.** `main` only gets batches ikkitco has confirmed.
  - Personal data, `cache\`, logs and `daemon\` are git-ignored. Never commit a collection CSV.
- The reader is its own repo: public fork `ikkitco/mtga-tracker-daemon`, cloned into `ArcVault\daemon`.
  - `master` mirrors upstream; **our patch lives on `arcvault`**. Change the reader there, never in ArcVault's repo.

---

## 1. What ArcVault is

ArcVault is a free, standalone Windows desktop app for **MTG Arena collection intelligence**. It was formerly called "MTGA Collection Exporter". The tagline is *"From collection to strategy."*

It does three things:
- reads the player's own collection, wildcards, gold and gems from Arena while it runs;
- writes them to CSV and text files;
- shows them in its own window, with tabs for:
  - browsing the collection;
  - set completion;
  - checking a deck against the collection;
  - "engines" (synergy pointers);
  - history;
  - a roadmap.

It also writes import files for Moxfield, Archidekt, deckstats, ManaBox and MTGGoldfish.

### Principles (non-negotiable unless ikkitco changes them)

- **Standalone, player-centric.** No accounts, no logins, no servers of ours. Everything stays on the player's PC.
- **Nothing runs unless the player chose it.** Auto-export is an explicit switch.
- **Read-only, own account only, never during a match.**
  - The match check is yes/no only.
  - We never read opponent or live-match data.
  - We don't build match tracking, win rates or draft ratings; Untapped and 17Lands own that space.
- **Free core.** It may earn *around* the app later, never by paywalling basics.
- **Honest about the risk.**
  - Wizards' General Terms 2.2 don't allow third-party tools that read game data.
  - ikkitco decided (18 Nov) to keep reading memory and label it clearly. This is "warning option B":
    - one calm line on the welcome screen;
    - an FAQ in `README.md`;
    - the Fan Content Policy line.
  - There is no "I understand" gate.

### How ikkitco works (please follow)

- **Iterate in small steps and discuss trade-offs.** Don't present one big finished solution.
- **Keep two lists in `ROADMAP.md`.** "In development (testing)" is for things built but not signed off. "Confirmed (prod)" is for things ikkitco has tested on their own PC.
  - **Only ikkitco moves items to Confirmed.**
- **Step-by-step instructions must match the real current UI exactly.** Cover every option and toggle they'll meet; no generic steps.
- **Be precise.** ikkitco corrects mechanical inaccuracies and expects the correction to stick.
- **Back up a file before changing it** (`name_vX.Y.Z_backup.py` pattern), and never overwrite their exports.

---

## 2. How it works

```
MTG Arena (running)
   │  memory read (read-only)
   ▼
daemon\  mtga-tracker-daemon (patched fork, C#/.NET, HTTP on :6842)
   │  JSON
   ▼
mtga_collection_export.py  (v2.1.0)  ──► mtga_collection.csv / _full.csv / .txt, mtga_inventory.csv
   │                                     snapshots\, changes\
   └─► mtga_site_exports.py (v2.4)   ──► exports\ moxfield.csv, manabox.csv, manabox.txt,
                                          deckstats.csv, mtggoldfish.csv, collection_list.txt
mtga_auto_export.py  (watcher, v2.1) runs the exporter on a timer while Arena is open
arcvault_app.py      (window, v0.4)  pywebview window + tray, shows ArcVault.html
ArcVault.html        the whole UI (one self-contained HTML/CSS/JS file)
```

### The reader (`daemon\`)

- It is **frcaton/mtga-tracker-daemon** (GPL-3.0), version 1.0.12, **patched by us** to read wildcards, gold, gems and the vault.
  - Arena hasn't written the collection to its log since 2021, so reading memory is the only route.
- Source: our fork `ikkitco/mtga-tracker-daemon`, branch `arcvault`, cloned into `daemon\`.
- Build it with `Build Daemon.bat`. This needs the .NET SDK and runs `dotnet publish -c Release -r win-x64 --self-contained`.
- Endpoints we use:
  - `/status`, `/cards`, `/playerId`, `/events`
  - `/inventory`: the patched `fields` are gold, gems, `wcCommon`, `wcUncommon`, `wcRare`, `wcMythic`, `wcTrackPosition` and `vaultProgress`.
  - `/matchState`: used as yes/no only.
  - `/allCards`, `/allCardsConnectionString`, `/shutdown`, `/checkForUpdates`.
- **Known bug:** `vaultProgress` reads as garbage, a denormal like `6.5e-320`.
  - The exporter leaves it blank, and the UI shows "—" for 0 or blank.
  - Decoding it properly is on the reader list (section 6).

### Paths (`arcvault_paths.py`)

- **Every file location comes from here.** Never build a path to a data file, cache, log or setting by hand; use `from arcvault_paths import L as P` and `P.file("collection")`, `P.cache(...)`, `P.log(...)`, `P.exports_dir()`, `P.program(...)`.
- **Folder mode** (default, ikkitco's dev folder): today's names and places, next to the scripts.
- **Installed mode** (an `arcvault.installed` marker next to the program): `Documents\ArcVault` with `arc_` names, plus `%LOCALAPPDATA%\ArcVault` for cache, window, logs and settings. Linux uses the XDG folders.
- `python mtga_collection_export.py --where` prints the current layout; `python arcvault_paths.py --installed` prints where an installed copy would keep files.
- `arcvault_paths.sandbox(dir)` gives an installed layout inside a test folder. Use it for any test that would otherwise touch the real Documents or LocalAppData.

### Building (`build.bat`, `arcvault.py`)

- **`arcvault.py`** is the only entry point compiled into `ArcVault.exe`; the first argument picks the part (`--watcher`, `--export`, `--migrate`, `--where`; none = the window).
- **Never start a part with a hand-built `python script.py` command line.** Use `arcvault_paths.launch("watcher" | "export" | "app", ...)`, which works both as scripts and compiled.
- **`build.bat`** produces `dist\ArcVault` (git-ignored, as is `build\`): Nuitka standalone + the reader published from `daemon\` + `arcvault.installed`. That folder is what the installer packs.
- **`installer\ArcVault.iss`** (Inno Setup 6) turns it into `dist\ArcVault-Setup-<version>.exe`. The version comes from `VER` in `build.bat`. Keep the `AppId` GUID unchanged forever, so upgrades replace the existing install. The uninstaller must never delete `Documents\ArcVault`.

### History import (`arcvault_migrate.py`)

- Copies an old folder-mode ArcVault into the installed places. **Copy only**: never move, change or delete the old folder, and never replace newer data. History is merged; every copy is verified.
- `python arcvault_migrate.py --find | --from <old> --dry-run | --sandbox <test> | --real`.
- The first-run screen of an installed copy uses it through the window's API (`where`, `pick_folder`, `set_data_dir`, `import_plan`, `import_start`, `import_status`).
- **`ARCVAULT_SANDBOX=<folder>`** makes any script behave as an installed copy inside that folder. Use it to test installed-mode screens without touching real folders.

### Exporter (`mtga_collection_export.py`, v2.2.0)

- **Card data:**
  - Names, rarity and type lines come from Arena's own card database (`Raw_CardDatabase_*.mtga`, auto-detected).
  - Set names, legality and rules text come from Scryfall bulk data, cached in `cache\`.
- **Safety checks:** it refuses to overwrite if the collection comes back empty or drops by more than 20%. Use `--force` to skip them.
- **Other options:** `--inspect` writes a diagnostic report; `--refresh-scryfall` and `--no-scryfall` control the card-data lookup.
- **`mtga_inventory.csv`** gets one row whenever something changes: date, gold, gems, wildcards and vault, plus collection totals. This file is the History tab's data.

### Site exports (`mtga_site_exports.py`, v2.4)

- Printings are matched in this order: Arena id → exact → set → Alchemy → name.
- **deckstats:** prefer a numeric collector number and a normal 3-letter paper set. Never The List (`plst`) or promo sets.
- **ManaBox:** `manabox.csv` uses ManaBox's full 18-column order with LF line endings. Archidekt's presets read files by column position.
- **Archidekt** has no format of its own. Users upload `manabox.csv` with the "ManaBox – Single folder" preset, or `moxfield.csv`.

### Watcher (`mtga_auto_export.py`, v2.1)

- Control port **6851**, with text commands `status` (JSON state), `now`, `stop` and `ping`.
- Export timing:
  - The first export runs a few minutes after Arena starts. `--soon` runs it straight away.
  - After that it exports every 15 minutes, never mid-match or while Arena is loading.
- Helpers: `set_startup()` and `start_watcher()`.
- `run_export()` returns `(ok, result)`.

### Window (`arcvault_app.py`, v0.4)

- Built on pywebview (WebView2).
- The `js_api` methods are:
  - `latest`, which returns the newest export files;
  - `stamp`;
  - `auto_status`, `auto_set` and `auto_now` (a one-off export even when the watcher is off);
  - `startup_set`.
- **Tray icon** (pystray + pillow):
  - With auto-export on, closing the window hides it to the tray. With auto-export off, closing quits.
  - The tray icon shows a status dot.
- **Single instance** on port **6852**.
- **Start with Windows** uses the shortcut `ArcVault.lnk --tray`.
- **Where things are kept:**
  - window profile: `cache\window`;
  - settings: `arcvault_settings.json`;
  - log: `arcvault_app.log`.
- `ArcVault setup.bat` installs pywebview, pystray and pillow, and creates the shortcuts.

### Page (`ArcVault.html`)

- The whole UI is a single self-contained file: plain HTML, CSS and JS, no framework or build step.
- **Edit `ArcVault.html` directly.**
  - It was generated from a template with `const EMBEDDED = null`. Any copy you keep must keep that line, so the window loads files from the folder.
  - `MTGA Collection Viewer.html` is the old browser-only page. Don't develop it further.
- **App mode** is detected by `#app` in the URL or the user agent `ArcVaultApp/`. In app mode `<html>` gets class `in-app`.
  - CSS for app-only pieces is written as `.in-app .x`.
  - In light mode it's `:root[data-theme="light"].in-app .x`, with **no space**, because `in-app` is on `<html>` itself.
- **Browser storage keys** start with `mtgaview:`. Renaming them waits for the installer migration.
- **Tabs:** Cards · Sets · Deck check · Engines · History · Coming next.
- **Layout:**
  - The header and stats bar are fixed.
  - The left filter panel scrolls with a hidden scrollbar.
  - Each tab's table scrolls inside `.tablewrap`, with sticky column headings.

---

## 3. Brand and UI rules

**Dark palette (default):**

| Use | Value |
|---|---|
| Background | `#0F1218` |
| Panel | `#171C24` |
| Text | `#E7EAF0` |
| Arc Blue (accent) | `#5A8DFF` |
| Vault Gold (brand) | `#D5AE58` |
| Warning | `#E8A33D` |

**Light mode** is warm parchment and never pure white: background `#ECE6DA`, panel `#F6F2EA`. Light mode is chosen with the ◐ button.

**Fonts:**
- Display: Barlow Condensed (uppercase labels, numbers).
- Body: IBM Plex Sans.
- Mono: IBM Plex Mono (file names).

**Colour rules:**
- Vault Gold is for brand elements: the logo, the wordmark and the gold line under the header.
- ikkitco has also approved gold for:
  - the "last checked" time in the Inventory slot;
  - the auto-export switch when it's on;
  - the "exporting" status text.
- Interactive elements use Arc Blue.
- Card data uses only rarity, legality and colour-identity colours. Rare is gold by Arena convention, which is why brand gold stays off data.

**Wording:**
- Say "desktop app", never "platform". The word "viewer" is retired.
- Use UK English, plain words, short sentences.

**Logo:** the master files are in `brand\`: SVGs, `arcvault.ico`, and `make_logo.py` / `build.py`.

---

## 4. Where it is now (19 Nov 2026)

### Confirmed by ikkitco (see the full list in ROADMAP)

- Collection export, Scryfall data, the txt list, mechanics tags, set completion, missing cards, mana value.
- Wildcards, gold and gems: all correct against Arena.
- The auto-export watcher.
- The ArcVault window, the auto-export switch, the tray icon and the first-run screen.
- The Owned column showing "this printing / all printings".
- The warm light theme and the rebrand.
- Site imports for Moxfield, Archidekt (via the ManaBox preset), deckstats and ManaBox (phone .txt). All tested with real imports.

### In testing (built, not yet signed off)

**UI changes from 18 Nov:**
- **Header**
  - The ArcVault logo is the **Export now** button.
  - While exporting, the logo glows: yellow-white in dark mode, blue in light mode.
  - When the export finishes, the logo flashes white (dark mode) or green (light mode).
  - The gold header line runs a slow left-to-right sweep while exporting.
- **Auto-export controls**
  - The switch sits at the top of the filter panel and turns gold when it's on.
  - The export status sits at the left end of the stats row, on one line. Long messages slide along it.
  - "Start ArcVault with Windows" sits under "New cards since last export".
- **Filters**
  - Rarity and colour chips fill with their own colour when selected.
  - The theme button sits left of the Collection/Inventory slots.
- **Sets tab:** you can pick several sets, and a selection bar offers "Show their cards" and "Clear".
- **Engines tab:**
  - The theme tiles form a 3-row strip that scrolls sideways.
  - It has ‹ › buttons and moves on by itself every 7 seconds.
  - An arc-logo button pauses it; ArcVault remembers the setting.
  - The strip stays fixed at the top while the cards beneath it scroll.
- **Deck check:** wildcards you have, the deck list, "missing from this build" and "wildcards left after crafting" are all shown as rarity-coloured tiles. The tiles are read-only.
- **History:** sections are ordered Currency, Collection, Wildcards.
- **Coming next tab** with the roadmap written for players.
- **Warning option B** is in place: the welcome screen line, the README FAQ and the Fan Content Policy line.

**Also still in testing:**
- the MTGGoldfish export (needs Premium to test; ship it labelled beta);
- the History tab (needs real days of data);
- the Engines rules (parked for now);
- the "Arena isn't ready yet" handling.

### Known issues

- Vault % isn't decoded (see section 2).
- The `__pycache__`, `New folder` and `*_backup.py` files in the folder are leftovers.

---

## 5. Decided, waiting to start

**Git repo and daemon fork:** both done 20 Nov (see the top of this file). **Next:** the installer.

**Installer, part 1** (decided 18 Nov; full table in ROADMAP):
- **Where things go:**
  - The program installs per-user in `%LOCALAPPDATA%\Programs\ArcVault`, with no admin prompt.
  - The player's files go in `Documents\ArcVault`, changeable with a "Save files to…" setting.
  - Working files go in `%LOCALAPPDATA%\ArcVault`: the Scryfall cache, the window profile, settings and logs.
- **Renames:** `mtga_` becomes `arc_` (`arc_collection.csv`, `arc_collection_full.csv`, `arc_collection.txt`, `arc_inventory.csv`). The browser storage keys and the Startup shortcut are renamed once, with a migration.
- **Paths module:** one small module gives every file location.
  - **Folder mode:** a `portable.txt` marker keeps ikkitco's dev folder working unchanged, with today's names.
- **"Bring in your history":** this *copies* the old folder and checks row counts afterwards. It never moves or deletes anything.
- **Uninstall** removes the program and `%LOCALAPPDATA%\ArcVault`. It never touches `Documents\ArcVault`.
- **Build:** `build.bat` builds the daemon (self-contained), compiles the Python with Nuitka and packs everything with Inno Setup into `ArcVault-Setup-x.y.z.exe`.
- **Signing:** builds are unsigned for now (decided 17 Nov), with clear SmartScreen notes. Code signing waits for funding.

---

## 6. Where it's heading (in order)

1. **Installer and app** (section 5).
   - Then automatic updates, the "Save files to" setting, and an optional Steam launch option.
2. **More from the reader.** Own account only, read-only, between matches.
   1. **Player ID:** separate collection and history per Arena account (`/playerId`), plus current events (`/events`).
   2. **Saved Arena decks and unopened packs.** This needs a reader patch, like the wildcard one.
      - Deck check on your real decks, with the wildcard cost of any you can't build yet.
      - A pack planner: which set to open next, allowing for duplicate protection.
   3. **Wildcard track** (`wcTrackPosition`): "X packs to your next rare/mythic wildcard". Also decode the vault.
3. **Planned features:**
   1. **Meta tab:** tournament decklists from magic.gg and melee.gg, with "Check this deck" and "Copy list" buttons. Be upfront that there's no Arena ladder data.
   2. **Engines v2:** "often played with", worked out from decklists and filtered to owned cards.
   3. **Optional AI "Ask":** the player brings their own API key (any provider). No payment to ArcVault: without a key the area simply doesn't work (decided 20 Nov).
   4. **Later:** offline "cards that do similar things" (embeddings).
4. **Pre-launch checks:**
   - Read Arena's terms in full.
   - Consider emailing Wizards.
   - Fan Content Policy checked 20 Nov: free access required; ads, sponsors and donations are fine.
   - Run antivirus false-positive checks on a clean PC.
   - Name checks: UK IPO search, domains, GitHub org.
   - Offer the wildcard patch upstream to the daemon's maintainer.
   - Publish our daemon fork's source; the GPL requires this when we distribute.

---

## 7. Gotchas

- **Arena updates can break the reader.** When it fails, the CSVs are left untouched. Use `--inspect` for card-database layout changes.
- **Scryfall:** be gentle, about 700 ms between search calls. They return HTTP 429 if you go faster.
- **Don't rename the data files or storage keys** outside the installer migration. Doing so breaks history and the watcher.
- **Test with the real flow** before asking ikkitco to confirm anything: Arena open, auto-export on, one export, then the window reloads by itself. He confirms on his own PC.
