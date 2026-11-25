"""
ArcVault - the single entry point that gets compiled into ArcVault.exe.

One exe holds every part; the first argument picks which part runs:

    ArcVault.exe                     the window (arcvault_app.py)
    ArcVault.exe --tray              the window, starting in the tray (Start with Windows)
    ArcVault.exe --shortcut          make Desktop / folder shortcuts
    ArcVault.exe --watcher [...]     auto-export in the background (mtga_auto_export.py)
    ArcVault.exe --export [...]      one collection export (mtga_collection_export.py)
    ArcVault.exe --migrate [...]     bring in your history (arcvault_migrate.py)
    ArcVault.exe --where             print where ArcVault keeps its files

Run as plain Python scripts, nothing goes through here: each script still runs on its own.
"""

import os
import sys


def main():
    first = sys.argv[1] if len(sys.argv) > 1 else ""
    rest = sys.argv[2:]
    if first == "--where":
        import arcvault_paths
        print(arcvault_paths.L.describe())
        return 0
    if first == "--watcher":
        sys.argv = [sys.argv[0]] + rest
        import mtga_auto_export
        return mtga_auto_export.main()
    if first == "--export":
        sys.argv = [sys.argv[0]] + rest
        import mtga_collection_export
        return mtga_collection_export.cli()
    if first == "--migrate":
        sys.argv = [sys.argv[0]] + rest
        import arcvault_migrate
        return arcvault_migrate.main()
    import arcvault_app                     # the window: reads --tray / --shortcut itself
    return arcvault_app.cli()


if __name__ == "__main__":
    # A compiled windowless exe has no console. If nobody gave it one (no pipe, no terminal),
    # send print() nowhere instead of crashing. When the watcher captures an export's output,
    # the pipe it passes in is used as normal.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    sys.exit(main())
