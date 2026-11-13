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


def main():
    parser = argparse.ArgumentParser(description=PRODUCT)
    parser.add_argument("--save-path", type=Path, default=default_save_path(), help="Use an alternate match database.")
    options = parser.parse_args()

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
