# ArcVault

*From collection to strategy.*

ArcVault is a free Windows app for MTG Arena players. It shows your whole Arena collection on your PC and keeps it up to date while you play: sets, wildcards, decks, engine ideas and your history over time.

**[Download the latest release](https://github.com/ikkitco/ArcVault/releases/latest)** · Windows 10 or 11 (64-bit) · Free

> **Before you install:** ArcVault reads your collection from MTG Arena's memory while the game runs. Wizards of the Coast's terms don't allow third-party software that reads game data. Please read [Is this allowed by Wizards?](#is-this-allowed-by-wizards) before you decide.

## What it does

- **Cards and Sets:** every card you own, with search and filters, set completion, missing cards, and the cards that are new since your last export.
- **Decks:** check a deck against your collection and see the wildcards it would cost. Build decks from your own cards, import and export with Arena, and try sample opening hands with exact draw odds.
- **Engines:** find cards in your collection that work together (enablers and payoffs), read them side by side, and start a deck from them.
- **History:** gold, gems, wildcards, vault progress and collection totals over time.
- **Exports** for Moxfield, ManaBox, Archidekt, deckstats, MTGGoldfish (beta) and a plain text list.
- **Automatic updates while you play.** ArcVault can export by itself while Arena is running, and can start with Windows.

## Requirements

- Windows 10 or 11, 64-bit. A Linux version is planned; there is no Mac version.
- MTG Arena installed on the same PC.
- Microsoft Edge WebView2. Most PCs already have it, and the installer adds it if yours doesn't.
- An internet connection, used only to download public card data and card pictures from Scryfall.
- No administrator rights are needed.

## Install

1. Download `ArcVault-Setup-<version>.exe` from the [Releases page](https://github.com/ikkitco/ArcVault/releases).
2. Optional: check the download is genuine. Open PowerShell in the folder you downloaded it to and run:
   ```
   Get-FileHash .\ArcVault-Setup-<version>.exe -Algorithm SHA256
   ```
   The code it prints should match the SHA-256 in that release's notes.
3. Run the installer. Windows may show **"Windows protected your PC"** because ArcVault isn't code-signed yet. Click **More info**, then **Run anyway**.
4. Follow the steps in Setup. The first page repeats the notice above.
5. Start MTG Arena, log in and wait at the Home screen, then open ArcVault. Click the ArcVault logo at the top left to export your collection.

To update, run the newer installer. Your files are kept.

## Where your files are

| What | Where |
|---|---|
| The program | Your user folder (`%LOCALAPPDATA%\Programs\ArcVault`), unless you choose another folder in Setup |
| Your collection, history, exports and saved decks | `Documents\ArcVault` |
| Settings, logs and the card picture cache | `%LOCALAPPDATA%\ArcVault` |

Uninstalling (Windows Settings → Apps → Installed apps → ArcVault → Uninstall) removes the program but **never deletes `Documents\ArcVault`**.

## What ArcVault reads and sends

**Reads, on your PC only:**
- From Arena's memory, while the game runs: the cards you own, gold, gems, wildcards and vault progress.
- Arena's own card database file: card names and details.

It never reads matches, opponents or your login, and it never changes anything in the game.

**Sends:** nothing about you. The only network use is downloading public card data and card pictures from [Scryfall](https://scryfall.com). Pictures are saved in ArcVault's cache so each one is downloaded once. There's no account and no tracking, and nothing is uploaded.

## Is this allowed by Wizards?

Not officially. Wizards of the Coast's General Terms (section 2.2) prohibit software that reads data from their games, and third-party tools they haven't authorised. The stated penalty can include suspending your account. ArcVault reads Arena's memory, so it falls under that wording.

ArcVault is read-only: it doesn't change the game, doesn't automate play, doesn't look at your opponent's hand or deck, and gives no advantage in a match. Tools that work the same way have been used openly by the community for years without any action against them that we know of, but the risk is yours to weigh. If you'd rather not take it, please don't install ArcVault.

## Troubleshooting

- **The window is blank:** WebView2 is missing or damaged. ArcVault offers to repair it; if it doesn't, run the installer again.
- **"Arena busy" or "Arena loading":** Arena is mid-game, loading or updating. ArcVault tries again by itself and exports once the collection can be read.
- **Exports stop working after an Arena update:** an Arena update can break the memory reader until it's updated. Your existing files aren't touched in the meantime; watch the Releases page for a fix.
- **Card pictures don't show:** something on your connection may be blocking `cards.scryfall.io`, for example a broadband content filter. Allow that address in your provider's or router's filter settings. Until then, ArcVault shows its own plain card faces.

## Credits

- **Collection reader:** [mtga-tracker-daemon](https://github.com/frcaton/mtga-tracker-daemon) by frcaton, licensed under GPL-3.0. ArcVault uses a patched copy from [ikkitco/mtga-tracker-daemon](https://github.com/ikkitco/mtga-tracker-daemon) (branch `arcvault`), and the licence text is included with the installer.
- **Card data and pictures:** [Scryfall](https://scryfall.com). ArcVault isn't affiliated with or endorsed by Scryfall.
- **Building from source,** or running ArcVault as a plain folder with Python: see [docs/folder-setup.md](docs/folder-setup.md).

## Licence

ArcVault is free software, licensed under the [GNU General Public License v3](LICENSE). You can use, study, share and change it; if you share a changed version, it must stay under the GPL v3 with its source available. ArcVault comes with no warranty.

The parts bundled with ArcVault keep their own licences: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Card names, card pictures and other Magic: The Gathering material belong to Wizards of the Coast, and card data and pictures come from Scryfall; none of that is covered by ArcVault's licence.

Made by [ikkitco](https://ikkit.co). Copyright © 2026 ikkitco.

---

ArcVault is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
