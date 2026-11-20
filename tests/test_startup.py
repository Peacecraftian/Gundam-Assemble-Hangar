"""Native startup coverage for the launcher's fullscreen handoff and escape path."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import run_companion
from companion.ui import Companion
from companion.window_placement import monitor_bounds


class StartupTests(unittest.TestCase):
    def exercise_startup(self, fullscreen):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Native Tk display unavailable: {error}')
        def destroy():
            try:
                root.destroy()
            except tk.TclError:
                pass
        self.addCleanup(destroy)
        actual_loop = root.mainloop
        apps = []

        def create_app(*args):
            app = Companion(*args)
            apps.append(app)
            return app

        def settle():
            root.after(150, root.quit)
            actual_loop()
            root.update_idletasks()

        def inspect_startup():
            # Inspect the real mapped window, not just a requested Tk attribute.
            settle()
            self.assertEqual(bool(root.attributes('-fullscreen')), fullscreen)
            self.assertTrue(root.winfo_ismapped())
            if fullscreen:
                bounds = monitor_bounds(root)
                if bounds is not None:
                    left, top, right, bottom = bounds
                    self.assertEqual((root.winfo_rootx(), root.winfo_rooty(),
                                      root.winfo_width(), root.winfo_height()),
                                     (left, top, right - left, bottom - top))
                # Exercise the existing Escape handler without injecting desktop input.
                self.assertEqual(apps[0].escape(None), 'break')
                settle()
                self.assertFalse(root.attributes('-fullscreen'))
                self.assertLess(root.winfo_width(), root.winfo_screenwidth())

        with tempfile.TemporaryDirectory(dir=Path('.build')) as folder:
            database = Path(folder) / 'startup.sqlite3'
            args = ['--save-path', str(database)]
            if fullscreen:
                args.append('--fullscreen')
            try:
                with patch.object(run_companion.tk, 'Tk', return_value=root), \
                     patch.object(run_companion, 'Companion', side_effect=create_app), \
                     patch.object(root, 'mainloop', side_effect=inspect_startup):
                    self.assertEqual(run_companion.main(args), 0)
                self.assertTrue(database.is_file())
                self.assertIsNone(apps[0].store.load()[0])
            finally:
                for app in apps:
                    app.close()

    def test_fullscreen_startup_and_escape_restore_window(self):
        self.exercise_startup(True)

    def test_direct_launch_remains_windowed_by_default(self):
        self.exercise_startup(False)
