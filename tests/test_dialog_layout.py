import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock

from companion.dialogs import CardMount, Dialog, show_card, table
from companion.theme import FOOTER_BUTTON_STYLES, FooterButton, setup_theme


class DialogLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk display unavailable: {error}")
        self.addCleanup(self.root.destroy)
        setup_theme(self.root)
        self.root.geometry("1020x595+20+20")
        self.root.update()

    def test_footer_styles_match_in_both_densities(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x")
        buttons = [FooterButton(bar, text="Reroll Selected", style=style) for style in FOOTER_BUTTON_STYLES]
        for button in buttons:
            button.pack(side="left", padx=3)
        for size in ("1366x768", "1020x595"):
            self.root.geometry(size)
            self.root.update()
            with self.subTest(size=size):
                self.assertEqual(len({(b.winfo_width(), b.winfo_height()) for b in buttons}), 1)
                for button in buttons:
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                    self.assertLessEqual(button.winfo_x() + button.winfo_width(), bar.winfo_width())

    def test_shared_footer_survives_short_window(self):
        dialog = Dialog(self.root, "Layout check")
        ttk.Frame(dialog.body, width=700, height=600).pack(fill="both", expand=True)
        button = dialog.buttons("Save", lambda: None)
        dialog.show()
        dialog.window.geometry("800x400")
        self.root.update()
        self.assertTrue(button.winfo_viewable())
        self.assertLessEqual(dialog.footer.winfo_y() + dialog.footer.winfo_height(), 400)
        self.assertLessEqual(dialog.body.winfo_y() + dialog.body.winfo_height(), dialog.footer.winfo_y())

    def test_card_actions_share_rail_and_status_stays_inside(self):
        card = SimpleNamespace(number="TEST-U01", name="Unit", title="Title", image="missing.webp")
        weapon = SimpleNamespace(number="TEST-U01A", name="BIT Stave", parent=card.number, hp=1)
        unit = SimpleNamespace(deployed=True, hp=10, remote_weapon_hp={})
        app = SimpleNamespace(root=self.root, photos=Mock(), remote_weapons={weapon.number: weapon},
                              match=SimpleNamespace(unit=lambda _: unit, winner=None))
        app.photos.get.return_value = None
        dialog = show_card(app, card, unit_id=7, attacks=(object(),), on_attack=lambda *_: None)
        dialog.window.geometry("800x400")
        self.root.update()
        actions = {str(child.cget("text")): child for child in dialog.footer.winfo_children()
                   if isinstance(child, ttk.Button)}
        self.assertEqual(set(actions), {"Deploy RWS", "Attack", "Close"})
        self.assertEqual(len({(button.winfo_width(), button.winfo_height()) for button in actions.values()}), 1)
        centers = [button.winfo_y() + button.winfo_height() / 2 for button in actions.values()]
        self.assertLessEqual(max(centers) - min(centers), 1)
        systems = next(child for child in dialog.footer.winfo_children() if isinstance(child, ttk.Frame))
        label = systems.winfo_children()[0]
        self.assertEqual(systems.cget("style"), "RailFill.TFrame")
        self.assertGreaterEqual(label.winfo_rootx() - dialog.footer.winfo_rootx(), 8)
        self.assertLessEqual(systems.winfo_x() + systems.winfo_width(), actions["Deploy RWS"].winfo_x())

    def test_card_and_table_keep_content_off_recess_border(self):
        app = SimpleNamespace(photos=Mock(), remote_weapons={})
        mount = CardMount(self.root, app, width=160, height=100)
        mount.pack()
        frame, tree = table(self.root, (("name", "Name", 120, True),), height=2)
        frame.pack()
        self.root.update()
        for parent, child in ((mount, mount.canvas), (frame, tree)):
            with self.subTest(widget=type(parent).__name__):
                self.assertGreaterEqual(child.winfo_x(), 2)
                self.assertGreaterEqual(child.winfo_y(), 2)
                self.assertLessEqual(child.winfo_x() + child.winfo_width(), parent.winfo_width() - 2)
                self.assertLessEqual(child.winfo_y() + child.winfo_height(), parent.winfo_height() - 2)
