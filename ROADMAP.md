# ArcVault: roadmap and decisions

*(Formerly MTGA Collection Exporter.)*

The agreed plan, so it survives between sessions. Update it when a decision changes.

## Brand (ArcVault)
- **Name:** ArcVault. Tagline: *From collection to strategy.* Positioning: collection intelligence for MTG Arena, on your PC.
- **Words:** public copy says "desktop app", never "platform" (platform implies accounts and a cloud service, which we don't have and don't want). "Viewer" is retired: the window is ArcVault.
- **Palette:** background `#0F1218`, panels `#171C24`, text `#E7EAF0`, Vault Gold `#D5AE58`, Arc Blue `#5A8DFF`.
- **Colour rules:**
  - Vault Gold is brand only: logo, wordmark, the one gold line under the header. Never on buttons, links or data. Agreed exception: the "last checked" time in the Inventory slot (with "updated" in Arc Blue beside it).
  - Interactive = Arc Blue (dark text on it; white on Arc Blue is only 3.1:1).
  - Card data only uses the rarity / legality / colour-identity colours. Rare is gold by Arena convention; that's why brand gold stays off data.
  - Gold and Arc Blue never sit side by side as a pair (1.5:1).
- **Theme:** dark by default; light is a choice (◐ button), remembered per browser. Light mode is warm parchment, never pure white.
- **Logo files** (`brand\` folder, vector masters made by `make_logo.py`):
  - Master mark (32 px and up): open hexagon frame, A, arc cut through it.
  - Small mark (16–24 px): solid gold hexagon with the A knocked out. The thin arc and frame vanish at 16 px.
  - Wordmark: geometric caps, ARC gold / VAULT text colour; the A's have crossbars (an open A reads "ΛRCVΛULT").
  - Light, mono and app-icon versions, `arcvault.ico` (16–256, small mark at 16/24), `favicon.svg`.
  - Refine from here; the original concept art (raster) is the north star, not a production file.
- **Avoid:** mana symbols, wizard hats, spellbooks, dragons, fantasy creatures, anything Wizards-branded. Check the mark side by side with MTG Arena's logo before launch.
- **Name check before launch:** done 25 Nov (see Pre-launch checks): name kept.
- **Renames that wait for the app build** (they'd break history or the watcher now): data files (`mtga_*.csv`), script names, folder names, the Startup shortcut name, `.bat` names, the browser storage keys (`mtgaview:`). Do them with a migration, once.
- **Navigation for growth:** Collection (Cards + Sets) · Decks (Deck check) · Engines · History, with room for Wildcards and Analytics. Tabs stay as they are until the app build.

## Principles
- **Player-centric and standalone.** Download it, use it, nothing else required. No accounts, no logins, no servers of ours.
- **Your data, your files.** Everything stays on the player's PC. For files on other devices, the player points the export folder at their own OneDrive or Google Drive. The app never integrates with those services.
- **Nothing runs unless the player chose it.**
- **Free core.** Earn *around* the app, e.g. support on the download page, maybe an optional paid tier later. Never paywall what other tools paywall just because they do.
- **Not tied to ikkit.co.** The project is only written about in ikkitco's dev logs.
- **Don't chase the trackers.** No match tracking, draft ratings or win rates; Untapped and 17Lands own that. Compete on exports, collection insight and building your own decks.

## How this list works
- **Confirmed (prod):** ikkitco has used it on their own setup and signed it off. Only ikkitco moves things here.
- **In development (testing):** built and delivered, but not yet confirmed by ikkitco. Bugs found here get fixed before anything moves up.
- **Planned:** agreed, not started. Order = priority.

When the desktop app starts, this split becomes real in the code too: a `main` branch (prod, what users get) and a `dev` branch (work in progress) in the project's GitHub repo, with releases only cut from `main`.

## Confirmed (prod)
- Collection export to CSV via mtga-tracker-daemon; names, rarity, type lines from Arena's own card database; alternate names (v1.0-1.3)
- Set names and format legality from Scryfall (v1.4)
- `.txt` list of card names and counts (v1.5)
- Rules text / keywords / mechanics tags (v1.6, built in another session)
- Set completion (Collected / Usable any printing / Usable playsets of 4), Missing cards, New column, mana value (v1.7)
- Wildcard counts via the patched daemon (v1.8); wildcards confirmed correct against Arena
- Auto-export watcher, ON/OFF (v1.9); confirmed exporting on ikkitco's PC
- ArcVault window (formerly the viewer): Cards / Sets / Deck check tabs, two labelled file slots (names go green), the same stats strip on every tab
- **Moxfield** site export (`exports\moxfield.csv`): confirmed importing into Moxfield
- **ArcVault window** (v0.1.1, option A: Python + pywebview / WebView2): confirmed 17 Nov on ikkitco's PC. Own window and taskbar icon (ArcVault logo), no browser. `ArcVault setup.bat` installs pywebview and adds Desktop + folder shortcuts. Loads the newest export from the folder by itself and refreshes every 20 s. Inventory slot reads "updated …" (Arc Blue) · "last checked …" (Vault Gold). Still to come: tray icon, big auto-export switch, installer, signing.
- **Big auto-export switch** (window v0.2, watcher v2.1): confirmed 17 Nov on ikkitco's PC. switch in the header controls the background watcher. On + Arena open = export straight away (`--soon`); on + Arena closed = wait, first export a few minutes after Arena starts; off = stop, no export. States: grey off / amber waiting or retrying / pulsing blue exporting soon or now / green "Exported 3 min ago · +2 new". Export now button; Start with Windows checkbox (same Startup shortcut as the .bat). Watcher control port gained `status` (JSON) and `now`. A finished export reloads the window straight away. Closing the window leaves the watcher running (tray icon next).
- **Tray icon** (window v0.3, pystray + pillow): auto-export on → closing the window hides to the tray (one-time notice); off → closing quits. Icon = small ArcVault mark + status dot (grey/amber/blue/green), tooltip with the state. Menu: Open (default click), Export now, Auto-export ✓, Quit (= auto-export off). Start with Windows now launches `arcvault_app.py --tray` (auto-export on); the old watcher-only Startup shortcut is migrated automatically. Single instance: a second start shows the first window. Confirmed 17 Nov on ikkitco's PC.
- **Owned column shows this printing / all printings** (e.g. `2/5`, total in grey; hover for detail). The "Combine printings of the same card" option is removed. Confirmed 17 Nov.
- **Gold / gems** reading: confirmed correct against Arena (17 Nov).
- **Warm light theme**: light mode uses parchment tones (background `#ECE6DA`, panels `#F6F2EA`) instead of white; light-mode rarity colours darkened slightly for contrast on beige. Confirmed 17 Nov.
- **First run** (window v0.4): no export in the folder → welcome screen (no table, no filters): 1) open Arena (live tick), 2) Turn on auto-export / Export once, 3) collection appears when done. Progress text during the export (incl. "first export: downloading Scryfall card data"); plain-word errors (Arena not open / still loading / in a match / reader missing / reader blocked by antivirus / export failed → log). The window never falls back to files loaded by hand. Export now works with auto-export off (one-off: start reader, export, stop reader); the switch shows "Off · exported 2 min ago". Test: move `mtga_collection_full.csv`, `mtga_collection.csv`, `mtga_inventory.csv` into a subfolder, keep auto-export off / Arena closed to see the screen; put `mtga_inventory.csv` back afterwards. Confirmed 17 Nov on ikkitco's PC (welcome screen, Export once with Arena closed and open, table appears after export).
- **ArcVault rebrand** (17 Nov): name and wording, dark palette, logo + wordmark in the header (42 px mark), header + stats strip fixed with one scrollbar for the rest, preview date in the Collection slot, Printings tile explains hidden basic lands
- **Archidekt** via `exports\manabox.csv` + *ManaBox – Single folder* preset (v2.2, 18-column ManaBox format with Scryfall IDs): confirmed 17 Nov, all 4,009 lines imported, 0 not found, 0 ambiguous
- **deckstats** via `exports\deckstats.csv` (v2.3.1): confirmed 17 Nov, 3,973 entries / 7,525 cards imported, 0 unmatched. Arena-only printings (HBG, YMID…) go to a normal paper printing, never The List or promo sets.
- **ManaBox** (phone app) via `exports\manabox.txt` text import (v2.4): confirmed 17 Nov, imported with no errors. The phone saved `manabox.csv` as .xlsx and the app's file picker only takes .txt, hence the .txt file.
- **Site export matching by name** (v2.1): printings Scryfall has no Arena ID for yet (new sets, Alchemy Y-sets, rebalanced A- cards, cn-0 promos, odd basics) matched by name + set + number; confirmed by the Archidekt import above
- **UI tweaks (18 Nov, window page only):** confirmed 20 Nov by ikkitco. logo = Export now button (glows while exporting, white/green flash when done; gold header line sweeps); auto-export switch at the top of the filters, gold when on; one-line export status in the stats row (slides if long); Start ArcVault with Windows under "New cards since last export"; theme button left of the file slots; rarity and colour chips fill with their own colour; Sets tab multi-pick with a selection bar (Show their cards / Clear); headings stay put (tables scroll inside); Engines 3-row theme strip with ‹ › buttons, 7 s timer and arc-logo pause; Deck check wildcard tiles (have / missing / left after crafting); History order Currency, Collection, Wildcards; Vault shows — until decoded; Coming next tab; warning option B (welcome line, README FAQ, Fan Content line). Handover for other tools: `HANDOVER.md`.
- **Text list** (`exports\collection_list.txt`) and **MTGGoldfish** (`exports\mtggoldfish.csv`): signed off 20 Nov. MTGGoldfish is **shipped as beta**: its collection import is Premium-only, so it has never been tested; label it "beta – report failed imports" in the app and fix from user reports. (Archidekt has no format of its own: users upload `moxfield.csv` or `manabox.csv` with the matching preset.)
- **Installer step 1: paths module** confirmed 20 Nov by ikkitco (built 20 Nov, exporter v2.2.0). New `arcvault_paths.py` decides where every file lives; the exporter, auto-export, site exports and window all ask it instead of building paths themselves. **Folder mode** (any plain folder, like ikkitco's) = exactly today's names and places. **Installed mode** (only when an `arcvault.installed` marker sits next to the program) = `Documents\ArcVault` with `arc_` names + `%LOCALAPPDATA%\ArcVault` (cache, window, logs, settings); on Linux the XDG folders. `ARCVAULT_DATA_DIR` or a `data_dir` setting moves your files (for the later "Save files to…" setting). `python mtga_collection_export.py --where` prints the layout. Tested here end-to-end against a fake reader in folder mode and Linux installed mode; Windows installed mode (real Documents folder lookup) still needs a test on Windows in step 2. ikkitco to check: one export, stats row and History unchanged.
- **Installer step 2a: bring in your history** confirmed 20 Nov by ikkitco (built 20 Nov). New `arcvault_migrate.py` copies a folder-mode ArcVault into the installed places: the four files (renamed `arc_`), `snapshots\`, `changes\`, `exports\`, the Scryfall cache, the window profile (theme etc.) and settings. Copy only, never moves or deletes; never replaces newer data (newer collection kept, history merged row by row, dated snapshots/changes never replaced); every CSV checked by row count, other files by size; writes `import_report.txt`. Command line for now (`--find`, `--dry-run`, `--sandbox <test folder>`; `--real` required for the real places). `python arcvault_paths.py --installed` shows where an installed copy would keep files on this PC (checks the real Documents folder). Tested here in a sandbox, including a second run and a history merge. Tested on ikkitco's PC 20 Nov (Documents found under OneDrive; 60-step sandbox import, all verified).
- **Installer step 2b: first-run screen of an installed copy** confirmed 20 Nov by ikkitco (built 20 Nov, window v0.5). Shows **where your files are kept**, says so plainly when OneDrive (or Dropbox etc.) syncs that folder, with a **Change…** button (decided 20 Nov: option 2, keep Documents but tell people). **Bring in your history**: suggests the old folder it found (Desktop/Startup shortcuts), previews the counts, copies with a progress bar, shows the report. The window profile (theme) is staged and swapped in at the next start, because the open window is using it. Header slots show the `arc_` names. Testable without installing: set `ARCVAULT_SANDBOX=<test folder>` and start `arcvault_app.py` (an installed copy inside that folder). Tested here with a mocked window and in a sandbox.
- **Installer step 3: `build.bat` and ArcVault.exe** confirmed 20 Nov by ikkitco (built 20 Nov). New `arcvault.py` is the single entry point: one exe holds every part (`ArcVault.exe` window, `--tray`, `--watcher`, `--export`, `--migrate`, `--where`). All part-to-part launches (auto-export, exports, Startup/Desktop shortcuts) now go through `arcvault_paths.launch()`, which gives `pythonw script.py` as scripts and `ArcVault.exe --part` when compiled, so the dev folder keeps working exactly as before. `build.bat`: installs Nuitka, builds the reader from the fork (`dotnet publish -o build\daemon`), compiles with Nuitka (standalone, pywebview plugin, console only when run from one), and assembles `dist\ArcVault` with the reader, the page, the icon, the `arcvault.installed` marker, README and the reader's GPL licence. Compiled and run here on Linux (installed layout, `--export` with captured output); **Built and tested on ikkitco's PC 20 Nov:** the compiled ArcVault.exe opens the window, brings in history (sandbox) and auto-exports with Arena through the bundled reader. One fix needed: in a Nuitka build `sys.executable` names a python.exe that doesn't exist, so the exe's own path now comes from Nuitka's `__compiled__.process_exe`. Next: step 4, the installer (Inno Setup).
- **Installer step 4: the installer** confirmed 20 Nov by ikkitco (built 20 Nov). `installer\ArcVault.iss` (Inno Setup 6), run by `build.bat` as step 5/5 → `dist\ArcVault-Setup-<version>.exe`. Per-user, no admin prompt, default `%LOCALAPPDATA%\Programs\ArcVault`. **Players can choose the folder** (decided 20 Nov); if it isn't the recommended one, a **red note under the folder box** says another folder may need the installer run as administrator, and Setup checks it can actually write there before going on (clear message if not). A "Before you install" page carries warning option B (memory reading, Wizards' terms, nothing uploaded, Fan Content line). Start menu shortcut, optional Desktop shortcut, "Start ArcVault now" at the end. Closes a running ArcVault and its reader before installing or uninstalling. Uninstall removes the program, `%LOCALAPPDATA%\ArcVault` and its Startup shortcut, **never `Documents\ArcVault`**, and says so. Upgrades install over the top (same AppId) and keep everything. **Tested end to end on ikkitco's PC 20 Nov:** build.bat → installer → install (folder note and write check) → first run (OneDrive Documents shown, history brought in) → auto-export with Arena → uninstall (Documents\ArcVault kept). Note for ikkitco's own PC: the dev setup and an installed copy both use a Startup shortcut called ArcVault.lnk.

- **Vault %**: confirmed 20 Nov by ikkitco, matches Arena. The reader's memory library (HackF5.UnitySpy) read floats and doubles as 2 bytes instead of 4 and 8, so the vault (a double) came out as a tiny garbage number. Fixed in the reader fork (`arcvault` branch, `ProcessFacade.cs`, marked `[MTGA exporter patch]`). Worth offering upstream.
- **"Arena isn't ready yet" handling** (v2.0.1): confirmed 20 Nov by ikkitco. Retries every 2 min and exports as soon as the collection can be read; mid-session stretches show "Arena busy · trying again in 2 min".
- **First outside test** (reported 25 Nov): a friend installed the 20 Nov test build (0.5.0, with WebView2 handling) on his own PC with the standard install steps, and exported his collection into ArcVault successfully. No issues reported along the way. **Clean-PC test** on ikkitco's old PC: installed and ran with no issues, window drawn correctly.
- **History** (v2.0): confirmed 25 Nov by ikkitco. Collection totals in `mtga_inventory.csv` + History tab; tracked correctly over 17-24 Nov (28 entries, snapshots from 15 Nov). A new entry is only added when an export runs.
## In development (testing)
- **0.5.1 pre-release** (25 Nov): first built 18:40, then rebuilt 20:05 from `a37a528` with the GPL-3.0 licence, third-party notices, the `licenses` folder and each copy's own file names; the release and tag `v0.5.1` were deleted and created again (private until the repo goes public). Installer SHA-256 `17a8239eaffb038c27da41bbd9109866b09eb19626269f285c5ce702c930c12d`. Card pictures: on ikkitco's Plusnet line `cards.scryfall.io` failed the secure handshake while Scryfall's other hosts worked; it started working after `cards.scryfall.io` was added to SafeGuard's Allow Websites (SafeGuard itself is off). Release notes tell users a broadband filter may block that host.
- **WebView2 on clean PCs** (20 Nov). Found in the Windows Sandbox test: ArcVault installed fine but the window stayed empty, because the Microsoft Edge WebView2 Runtime (which draws the window) isn't on every PC. The installer now checks for it (Microsoft's documented registry check) and, only if missing, runs Microsoft's small WebView2 installer (`installer\MicrosoftEdgeWebview2Setup.exe`, downloaded by `build.bat`, not in git). ArcVault itself now shows a clear message with the download link instead of an empty window. To confirm: rebuild, install in a fresh Sandbox, window shows.
- **Engines tab** (engine-builder v1): theme / card views, ~30 rules + creature types, Standard by default. **Parked:** ikkitco isn't focusing on it for now; tune rules later from their review. **Decided 20 Nov:** ships in the first release as is, with an "Early" badge on the tab (hover explains).
- **Decks tab, stage 1 of the Engines/Decks redesign** (25 Nov). "Deck check" tab renamed **Decks**. The left side (wildcards, deck list, missing / left after crafting) stays the same whichever tool is open; the right side has tool tabs: **Deck check** (works now), **Deck builder** (marked Next) and **Arena decks** (marked Later). New on the left: deck name, **Save** / **Delete** and a saved-decks list (Arena-format `.txt` files in `Documents\ArcVault\decks`; in a plain browser they're kept in the browser), **Import** (reads a deck exported from Arena off the clipboard, deck name included) and **Export** (copies the deck in Arena's import format, with its name). Anything that would throw away unsaved edits offers Undo; Delete and saving over a different deck ask with a second click.

## Engines / Decks redesign (agreed 25 Nov)
Engines stays informational: it shows what your collection could do and never re-sorts or hides cards based on suggestions.
1. **Decks tab split** - done, testing (above).
2. **Deck builder** tool on the right of Decks - done, testing (25 Nov). Uses the search and filters on the left; one row per card name with cost, type, rarity, copies owned and copies in the deck; + / - edit the deck list on the left (Deck or Sideboard switch), up to 4 per card (basic lands and "any number" cards unlimited); a basic lands row; cards in the deck stay at the top; "N short" when the deck has more copies than you own. Shows the first 250 matches.
   - **Opening hands** tool (added 25 Nov at ikkitco's request): New hand (7 from the main deck, sideboard left out), Mulligan (London: draw 7, pick cards to put on the bottom, Keep), Draw a card, On the play / On the draw. Exact odds (no simulation): lands in the opening 7, and the chance to have at least one copy of each card in the opening hand, by turn 2 and by turn 4.
   - **Decks polish** (25 Nov, agreed with ikkitco, testing): deck summary above the deck list (main deck count against 60, or 100 for Brawl; sideboard count; mana curve of spells; colour split); **format picker** that marks cards not legal in that format (summary, Deck check, Deck builder; uses the legality columns already in the collection file); search box in the Deck builder (typing shows your collection); the far-left filters fold away on History / Coming next and are dimmed with a note on Deck check / Opening hands, where they do nothing. Also: card pictures from Scryfall (by Arena ID) in the Deck builder preview, Opening hands, and a hover preview on card names on every tab; requests go one at a time ~0.1 s apart; text fallback when offline.
   - **Decks extras** (25 Nov, testing): shift-click + makes a card 4 copies (basic lands +4), shift-click - removes them all; **Tidy list** (creatures, other spells, lands, by mana value; repeated lines merged; Arena still imports it; Undo); start screen when the deck is empty (Import from Arena / Start building / Open a saved deck); "?" wildcard tiles open the inventory file picker; card previews also show when a card name gets keyboard focus; when Scryfall has no picture, ArcVault draws a plain card with the faded ArcVault mark.
   - **Pictures rule** (25 Nov, ikkitco): on the plain Cards tab the hover shows ArcVault's own card (no download); everywhere else, including Cards after Sets → Show their cards, the real picture comes first (Arena ID, then set + number), ArcVault's card if there's none.
   - **Engines card view** (25 Nov, testing; brings forward part of stage 5): the picked card shows its picture beside its text; **Add** on any card in Feeds it / It pays off puts it beside the picked card (up to 3), each with its picture, how the two connect, and the words the rules matched highlighted (only for rules that read rules text; mechanic-tag rules have nothing to highlight).
   - **Rules words** (25 Nov, testing): keywords in rules text (about 75: evergreen keywords, keyword actions like scry and surveil, token types, recent set mechanics, Arena-only words) get a dotted gold underline; hovering shows a short explanation in ArcVault's own words and points to Wizards' Comprehensive Rules for the exact wording. Shown on the Engines card text and on ArcVault's own card faces. Not on real card pictures (they're images).
3. **Engines colour chips** - done, testing (25 Nov). W U B R G C chips in the Engines bar keep cards whose colour identity fits inside the picked colours (C keeps colourless cards); themes are recounted within them; "All colours" clears. Each theme tile has a colour strip showing where its cards sit (hover for percentages). The card-view "Colours" dropdown is now called "Match" (shares a colour with the picked card / any colour).
4. **Pick cards and "Build deck with engine"** - done, testing (25 Nov). Tick boxes on every Engines card; a tray at the bottom lists the picks; "Build deck with engine" starts a new deck named "<theme> engine" (or "<card> engine", with the picked card included) at as many copies as you own up to 4, tidied, and opens Decks -> Deck builder. Unsaved work in the old list can be brought back with Undo.
5. **Pair reader and signals** - done, testing (25 Nov). Side-by-side reader is the Add button (above). ★ star you set yourself on any Engines card (remembered); deck icon on cards that are in any of your saved decks (hover for which). Tournament cards with a coloured name (teal suggested) still wait for the Meta tab's decklists.

## Planned
1. **Meta tab.** Tournament decklists fetched by the app itself when online: magic.gg (premier events), melee.gg (wider tournaments). Buttons: "Check this deck" (into Deck check) and "Copy list". There is no Arena ladder data; be upfront about that.
2. **Engine-builder v2.** "Often played with", from decklist co-occurrence, filtered to owned cards. After the parked v1 is reviewed.
3. **Optional AI "Ask".** Bring your own key, any provider (Claude, OpenAI, Google). A Claude.ai subscription is not an API key; keys come from the provider's developer console. **Decided 20 Nov: no payment to ArcVault.** The Ask area simply doesn't work without the player's own AI key, because ArcVault doesn't provide AI access; it's for AI enthusiasts. This fits the Fan Content Policy (ArcVault stays free).
4. Later: an offline "meaning fingerprint" (embeddings) for "cards that do similar things".
5. **Later: Linux version** (noted 20 Nov, for planning; platforms decided 20 Nov: **Windows and Linux only, no Mac**). Arena runs on Linux through Steam/Proton, and the reader's memory library (HackF5.UnitySpy) already has Linux code. The Python parts are mostly portable; Windows-only pieces are shortcuts, tray quirks and file locations. Package as an AppImage (Flatpak's sandbox would block memory reading). **Rule from now on:** Windows-specific code lives in one platform module, and the paths module is written to support Linux locations (XDG folders) from day one, so a port later is mostly packaging and testing.

## Desktop app (when we build it)
- **Installer comes with the app, not before** (decided: an installer for today's scripts would be thrown away). Daemon prebuilt as a self-contained exe, Python bundled (PyInstaller), Inno Setup installer; no Python or .NET for users. **Code signing: deferred (decided 17 Nov).** Early public builds ship unsigned, with clear "Windows may warn you" install notes and false-positive reports to Microsoft/AV vendors per release. Signing is a target for iKkitco's first funding, and gets its own dev log.
- A real app window with ArcVault's page inside it, and automatic updates. Has to be a download: only a program on the player's PC can read Arena's memory.
- **The big auto-export switch is the centrepiece and the routine** ("have you turned auto-export on?"):
  - **On:** the collector is watching. Closing the window keeps it running in the system tray (a one-time notice the first time).
  - **Off:** nothing runs; closing the window quits.
  - **States shown on the switch:** Off (grey) → Waiting for Arena (amber) → Arena detected, exporting soon (pulsing) → Exported (green, "3 min ago · +4 new cards"). The same green-means-good language as the file slots.
  - **First launch:** one screen inviting you to turn it on. If it's off and Arena starts while the app is open: one gentle prompt with "Don't ask again". No other nagging.
- **Where things live after install:** program in Program Files (read-only); exports, history and cache in a user folder (default `Documents\ArcVault`, changeable), so nothing needs admin rights.
- **Opt-in settings:** start with Windows; for Steam players, launch our app with Arena through Steam's launch options.
- **"Save exports to: [folder]"** setting. Pick a cloud-synced folder yourself if you want your files on other devices.
- Until then, the ON/OFF watcher (`mtga_auto_export.py`) stays as it is while we build.

## More from the reader (agreed order, 17 Nov; after the installer decisions)
Own account only, read-only, never during a match; never opponent or live-match data (the match check stays yes/no only).
1. **Player ID / account:** separate collection + history per Arena account (reader already has `/playerId`). Also: your current events (`/events`), shown between matches.
2. **Saved Arena decks + unopened booster packs** (needs a reader addition, like the wildcard patch): deck check on your real decks, "saved but not buildable yet" with wildcard cost; pack planner (which set to open next, completion per pack with duplicate protection). Later in this group: draft/sealed tokens, mastery/quests/weekly gold, own rank, cosmetics.
3. **Wildcard track position** (already read: `wcTrackPosition`): "X packs to your next rare/mythic wildcard"; decode vault progress.

## Pre-launch checks (added 17 Nov)
- **Distribution (decided 20 Nov):** GitHub releases first (public repo at launch), a torrent later. Publish SHA-256 checksums with each release so torrent copies can be checked.
- **Decided 18 Nov (ikkitco):** keep reading Arena's memory and ship it, clearly labelled as an unofficial community tool, with an honest warning. Wizards' General Terms 2.2 (i) unauthorized software that reads data, (ii) reverse engineering, (iii)(d) tools not expressly authorized, and (v) cheating apply; the risk for players is account suspension. So, option B (decided 18 Nov, after checking how others do it): one calm line on the welcome screen ("ArcVault reads your collection from Arena's memory. It's unofficial and not approved by Wizards; use at your own risk. Learn more") linking to an honest FAQ answer (what it reads, why, what it never does, not approved by Wizards); the Fan Content Policy line ("Unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards.") in the app's About/footer and on the download page. No "I understand" gate: nobody else in the scene uses one. ArcVault stays read-only, own account only, never during a match.
- **Wizards' terms: done 20 Nov.** ikkitco read the terms (as a non-lawyer) and keeps the decision above. Original note: read the MTG Arena terms in full, especially the software licence section (reverse engineering) and the "Cheating" clause (advantage over other players). Decision so far: keep reading Arena's memory, read-only, own account only, never during a match, and say so openly in the app and on the download page.
- **Email Wizards: decided 20 Nov, no email.** ArcVault will comply promptly with any takedown request from Wizards.
- **Fan Content Policy (checked 20 Nov):** Fan Content must be free to access: no payments, subscriptions or email sign-up to get it, and it can't be sold. Ads, sponsorships and donations (e.g. Patreon) are allowed as long as they don't get in the way of access. No Wizards logos or trademarks. **So:** ArcVault stays free; donations are fine. The AI "Ask" area needs the player's own AI key and charges nothing (decided 20 Nov), so it fits. The disclaimer line is already in the app, installer and README.
- **Antivirus:** Defender scan of the installer and program: no threats (20 Nov). Still to do: the clean-PC test on the old PC (planned 21 Nov; Windows Sandbox can't run WebView2), and false-positive reports per release if any appear.
- **Name check: done 25 Nov, decided by ikkitco.** TMview search for "arcvault" found 9 marks, all Overland Storage, Inc., class 9, for data-backup hardware (2005-2006); 8 expired or ended, and the EU mark 004946448 is still listed as registered but its expiry date (06/03/2026) has passed. Nothing for software, apps or games; the "ArcVault Password Management" product isn't a registered mark. Decision: keep the name; if anyone raises a concern, deal with it then. Not legal advice.

## Installer plan, part 1: where files live (decided 18 Nov, except git)

**Why:** today everything sits next to the scripts. An installed program's own folder isn't a safe place for data (read-only under Program Files, replaced on update), so data moves to the user's folders. This is also where the held-back renames happen, once.

**Three places:**

| What | Where (proposed) | Why there |
|---|---|---|
| The program (window, exporter, watcher, reader/daemon, page, icons) | `%LOCALAPPDATA%\Programs\ArcVault` (per-user install) | No admin prompt to install or update; updates can replace files freely |
| Your files: collection, history, site exports, snapshots, changes | `Documents\ArcVault` (changeable: "Save files to…") | Easy to find, open in Excel, upload to sites; backed up with Documents |
| ArcVault's own working files: Scryfall cache (~37 MB), window profile, settings, logs, session baseline | `%LOCALAPPDATA%\ArcVault` | Hidden, not synced by OneDrive, safe to delete (rebuilt automatically) |

Trade-off noted: many PCs sync Documents to OneDrive. That's good for your files (small, worth backing up) and why the big cache stays out of Documents.

**New names (the held-back renames):**

| Today | Installed |
|---|---|
| `mtga_collection.csv` | `Documents\ArcVault\arc_collection.csv` |
| `mtga_collection_full.csv` | `arc_collection_full.csv` |
| `mtga_collection.txt` | `arc_collection.txt` |
| `mtga_inventory.csv` | `arc_inventory.csv` |
| `exports\`, `snapshots\`, `changes\` | same names, inside `Documents\ArcVault` |
| `cache\*` | `%LOCALAPPDATA%\ArcVault\cache\` |
| `cache\window\` (window profile, settings) | `%LOCALAPPDATA%\ArcVault\window\` |
| `arcvault_app.log`, `auto_export.log` | `%LOCALAPPDATA%\ArcVault\logs\` |

**How the code changes:** one small paths module used by the exporter, watcher, site exports and window, so every file location comes from one place.
- **Installed mode** (prod / `main`): the folders above.
- **Folder mode** (dev): when ArcVault runs from a folder with a `portable.txt` marker (your current folder), everything stays in that folder with today's names. Your dev setup keeps working unchanged while the installed version is tested side by side.

**Moving your existing data (copy, never move):**
1. The installed ArcVault's welcome screen gets a small link: "Used an earlier version? Bring in your history" → pick the old folder.
2. It **copies** with the new names, then checks the copy (row counts for history, collection and snapshots match). The old folder is left untouched, so nothing can be lost; delete it yourself once happy.
3. Old Startup shortcut (if any) is replaced by the installed ArcVault's own "Start with Windows".
For a brand-new player there's nothing to move; the link just isn't needed.

**Installer and uninstaller:**
- Installs per-user, adds Start menu + optional Desktop shortcut, optional Start with Windows (unticked by default), opens ArcVault at the end.
- Reader (daemon) ships ready-built from your patched source (wildcards included), self-contained (no .NET needed).
- Uninstall removes the program and `%LOCALAPPDATA%\ArcVault`; it **never** deletes `Documents\ArcVault` (your files).
- Unsigned for now: install notes explain Windows' "unknown publisher" / SmartScreen screen ("More info → Run anyway").

**Build:** a `build.bat` you run on your PC: builds the reader, compiles the Python parts (Nuitka), packs everything with Inno Setup into one `ArcVault-Setup-x.y.z.exe`. Next up.

**Decisions (18 Nov):**
1. Your files in `Documents\ArcVault`, working files hidden in `%LOCALAPPDATA%\ArcVault`: **OK**.
2. Per-user install (no admin prompt): **OK**.
3. File names: **`mtga_` becomes `arc_`** (`arc_collection.csv`, `arc_collection_full.csv`, `arc_collection.txt`, `arc_inventory.csv`).
4. Git repo (main/dev): **done 20 Nov; public from 25 Nov.** The public repo `ikkitco/ArcVault` starts from a clean first commit; the earlier history is kept in the private repo `ArcVault-private`. Earlier note: private GitHub repo `ArcVault` (ikkitco's account), managed with GitHub Desktop. `main` = prod (only confirmed work, releases cut from here), `dev` = testing (all new work goes here; merged into `main` when ikkitco confirms a batch). `.gitignore` keeps out personal data (`mtga_*` CSV/txt, `exports\`, `snapshots\`, `changes\`), `cache\`, logs, backups and `daemon\`. The reader has its own public fork (done 20 Nov): `ikkitco/mtga-tracker-daemon`. `master` mirrors frcaton's upstream (update with GitHub's **Sync fork**), and our inventory patch is one commit on the `arcvault` branch (29 lines in `HttpServer.cs`, 5 in `Models/InventoryResponseData.cs`, additions only). The fork is cloned into `ArcVault\daemon` (git-ignored by ArcVault, so it's its own repo) and built with `Build Daemon.bat`; rebuilt from the fork and export checked 20 Nov. This also covers the GPL source requirement for distribution. Dev folder moved 20 Nov to `D:\iKkitco\apps\ArcVault`.

## Daemon and licence
- We use frcaton/mtga-tracker-daemon (GPL-3.0; 1.0.12, last changed 9 Sep 2026; one maintainer). The collection isn't in Arena's log since 2021, so memory reading is the only route.
- Ours is a fork (the wildcard patch): `ikkitco/mtga-tracker-daemon`, patch on branch `arcvault` (done 20 Nov). Pull in upstream fixes via Sync fork on `master`, then merge into `arcvault`; fix it ourselves if upstream stops.
- After a week or two of testing, offer the wildcard patch upstream as a pull request. ikkitco may also reach out to the maintainer.
- GPL: no obligations for private use. When distributing, publish the daemon's source including our changes (the GitHub fork covers it). ArcVault's exporter and page talk to it as a separate program, so they can be licensed separately; consider open-sourcing them too for credibility. Not legal advice; check it if anything is ever sold.
