import argparse
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from companion.artwork import APP_ICON
from companion.catalog import load_catalog
from companion.storage import MatchStore, default_save_path
from companion.theme import PRODUCT
from companion.ui import Companion
from companion.window_placement import enter_fullscreen, monitor_bounds


def main(argv=None):
    parser = argparse.ArgumentParser(description=PRODUCT)
    parser.add_argument("--save-path", type=Path, default=default_save_path(), help="Use an alternate match database.")
    parser.add_argument("--fullscreen", action="store_true", help="Open directly in fullscreen; Esc or a header screw restores window mode.")
    options = parser.parse_args(argv)

    root = tk.Tk()
    root.withdraw()
    if sys.platform == "win32" and APP_ICON.is_file():
        root.iconbitmap(default=str(APP_ICON))
        root.iconbitmap(str(APP_ICON))
    store = None
    try:
        catalog = load_catalog()
        store = MatchStore(options.save_path)
        Companion(root, catalog, store)
        if options.fullscreen:
            # Establish the normal window's placement before Tk recreates its frame.
            # Enter while withdrawn so the first visible window is already fullscreen.
            root.update_idletasks()
            enter_fullscreen(root, monitor_bounds(root))
    except (OSError, ValueError, sqlite3.Error) as error:
        messagebox.showerror(f"{PRODUCT} Could Not Start", str(error), parent=root)
        if store is not None:
            store.close()
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
