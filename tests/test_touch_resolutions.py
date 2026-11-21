"""Regression checks for the compact desktop and full-HD touch layouts."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.catalog import load_catalog
from companion.match import Match
from companion.storage import MatchStore
from companion.touch_actions import TouchDicePrompt
from companion.ui import Companion


class TouchResolutionTests(unittest.TestCase):
    def test_card_targets_and_attack_scroll_at_supported_resolutions(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Native Tk display unavailable: {error}')
        root.withdraw()
        def settle():
            root.update()
            root.after(120, root.quit)
            root.mainloop()
            root.update_idletasks()
        with tempfile.TemporaryDirectory() as folder:
            store = MatchStore(Path(folder) / 'layout.sqlite3')
            catalog = load_catalog()
            match = Match.new(['Blue', 'Red'], '', 4,
                [['PA01-U01','PA01-U02','PA01-U03','ST01-U01','EX01-U01'],
                 ['ST01-U04','ST01-U05','ST01-U02','ST01-U06','EX02-U01']], catalog)
            for unit in match.units:
                unit.deployed = True
            store.save(match, 0)
            app = Companion(root, catalog, store)
            preview = app.preview

            def bounds(widget):
                return (widget.winfo_rootx(), widget.winfo_rooty(),
                        widget.winfo_width(), widget.winfo_height())

            def console_layout():
                return (preview.card_box,) + tuple(bounds(widget) for widget in (
                    root, app.track, *app.player_hangars, preview.canvas,
                    preview.controls, preview.meters, preview.open_button))

            def check_selection_layout():
                original = console_layout()
                for selected in (10, 8, 1):  # Aerial, Wing Zero, Gundam
                    app.select_unit(selected)
                    settle()
                    self.assertEqual(console_layout(), original)
                    self.assertEqual(any(row.winfo_ismapped() for row in preview.remote_readouts),
                                     selected == 10)

            try:
                for width, height in ((1366,688), (1366,768), (1920,1080)):
                    with self.subTest(viewport=(width,height)):
                        root.geometry(f'{width}x{height}+0+0')
                        root.deiconify()
                        settle()
                        check_selection_layout()
                        for button in (*preview.upgrade_buttons.values(), *preview.status_buttons.values()):
                            self.assertGreaterEqual(button.winfo_height(), 36)
                            self.assertGreaterEqual(button.winfo_width(), 36)
                            for ancestor in (preview.left if button in preview.upgrade_buttons.values() else preview.right, preview):
                                self.assertGreaterEqual(button.winfo_rooty(), ancestor.winfo_rooty())
                                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), ancestor.winfo_rooty()+ancestor.winfo_height())
                        for button in (*preview.header_buttons.values(), preview.open_button):
                            self.assertGreaterEqual(button.winfo_rootx(), preview.header.winfo_rootx())
                            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(), preview.header.winfo_rootx()+preview.header.winfo_width())
                        with patch('companion.dialogs.monitor_bounds', return_value=(0,0,width,768 if width==1366 else 1080)):
                            dialog = TouchDicePrompt(root, unit=app.match.unit(1), profiles=app.attacks['PA01-U01'], app=app)
                            settle()
                            self.assertEqual(len(dialog.targets), 6)
                            self.assertLess(dialog.canvas.yview()[0], .02, 'Attack must open at the weapon controls')
                            self.assertGreaterEqual(dialog.roll_button.winfo_height(), 48)
                            self.assertLessEqual(dialog.roll_button.winfo_rooty()+dialog.roll_button.winfo_height(), dialog.window.winfo_rooty()+dialog.window.winfo_height())
                            dialog.canvas.yview_moveto(1)
                            settle()
                            self.assertAlmostEqual(dialog.canvas.yview()[1], 1, places=2)
                            dialog.window.destroy()
                root.geometry('1020x595+0+0')
                settle()
                check_selection_layout()
                self.assertEqual(app.preview.well.grid_rowconfigure(0, 'minsize'), 0)
            finally:
                app.close()

