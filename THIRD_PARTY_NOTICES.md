# Third-party notices

ArcVault is licensed under the GNU General Public License v3 (see `LICENSE`). It includes, or is built with, the parts below, and each keeps its own licence. In an installed copy, the full licence texts of the bundled Python parts are in the `licenses` folder; `licenses\README.txt` lists each one with its version.

## Inside the program (ArcVault.exe and its folder)

| Part | Licence | Source |
|---|---|---|
| Python runtime | Python Software Foundation License | https://www.python.org |
| pywebview (the app window) and the packages it needs on Windows | BSD-3-Clause; dependencies under their own permissive licences | https://github.com/r0x0r/pywebview |
| pystray (tray icon) | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| Pillow (images for the tray icon) | MIT-CMU | https://github.com/python-pillow/Pillow |
| Nuitka (compiler runtime parts) | AGPL-3.0 with a runtime exception for compiled programs | https://nuitka.net |

pystray is under the LGPL-3.0. ArcVault as a whole is GPL-3.0 and its full source and build script (`build.bat`) are public, so you can rebuild ArcVault with a changed copy of pystray.

## The reader (daemon folder)

| Part | Licence | Source |
|---|---|---|
| mtga-tracker-daemon, with ArcVault's patch | GPL-3.0 | https://github.com/frcaton/mtga-tracker-daemon, patched copy at https://github.com/ikkitco/mtga-tracker-daemon (branch `arcvault`) |
| .NET runtime (bundled self-contained) | MIT | https://github.com/dotnet/runtime |
| Newtonsoft.Json | MIT | https://github.com/JamesNK/Newtonsoft.Json |
| Microsoft.Data.Sqlite, Microsoft.CSharp | MIT | https://github.com/dotnet/efcore, https://github.com/dotnet/runtime |
| SQLitePCLRaw (used by Microsoft.Data.Sqlite) | Apache-2.0 | https://github.com/ericsink/SQLitePCL.raw |
| SQLite | Public domain | https://sqlite.org |
| PeNet | Apache-2.0 | https://github.com/secana/PeNet |
| SharpZipLib | MIT | https://github.com/icsharpcode/SharpZipLib |
| JetBrains.Annotations | MIT | https://github.com/JetBrains/JetBrains.Annotations |
| HackF5.UnitySpy (memory reading, included in the reader's source) | See the reader's repository | https://github.com/frcaton/mtga-tracker-daemon |

## Shipped alongside

| Part | Terms | Source |
|---|---|---|
| Microsoft Edge WebView2 bootstrapper (`redist\MicrosoftEdgeWebview2Setup.exe`) | Microsoft's redistribution terms for WebView2 | https://developer.microsoft.com/microsoft-edge/webview2 |

## Data, not code

- **Card data and card pictures** come from [Scryfall](https://scryfall.com) and are downloaded on your PC. ArcVault isn't affiliated with or endorsed by Scryfall.
- **Magic: The Gathering** names, card text, pictures and symbols are property of Wizards of the Coast. ArcVault is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
