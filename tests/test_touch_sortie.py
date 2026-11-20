"""Touch setup keeps player edits transactional and squad drops ordered."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from companion.artwork import PhotoCache
from companion.catalog import load_catalog
from companion.dialogs import SetupScreen, SquadDragPress
from companion.storage import MatchStore
from companion.theme import setup_theme
from companion.touch_sortie import PlayerNameKeyboard
from companion.workspace import Workspace


class SortieTouchTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Native Tk display unavailable: {error}')
        self.root.withdraw()
        setup_theme(self.root)
        self.temp = tempfile.TemporaryDirectory()
        self.store = MatchStore(Path(self.temp.name)/'test.sqlite3')
        self.app = SimpleNamespace(root=self.root, workspace=Workspace(self.root), photos=PhotoCache(self.root),
            catalog=load_catalog(), store=self.store, remote_weapons={}, cancel_setup=Mock(), match=None, save=Mock())
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        # Reserve the real app header and outer spacing in this isolated screen.
        tk.Frame(self.root, height=86).grid(row=0,column=0,sticky="ew")
        self.screen = SetupScreen(self.root,self.app)
        self.screen.show()

    def tearDown(self):
        self.root.destroy()
        self.store.close()
        self.temp.cleanup()

    def settle(self):
        self.root.update()
        self.root.after(100,self.root.quit)
        self.root.mainloop()
        self.root.update_idletasks()

    def test_keyboard_selection_backspace_shift_cancel_and_commit(self):
        player = self.screen.players[0]
        with patch('companion.dialogs.monitor_bounds', return_value=(0,0,1366,768)):
            keyboard = PlayerNameKeyboard(self.root,player,0)
            self.settle()
            keyboard.buttons_by_key['r'].invoke()
            self.assertEqual(keyboard.value.get(),'r')
            keyboard.toggle_shift()
            keyboard.buttons_by_key['x'].invoke()
            self.assertEqual(keyboard.value.get(),'rX')
            keyboard.backspace()
            self.assertEqual(keyboard.value.get(),'r')
            keyboard.entry.delete(0,'end')
            keyboard.backspace()
            self.assertTrue(keyboard.done.instate(['disabled']))
            keyboard.cancel()
            self.assertEqual(player.get(),'Player 1')
            keyboard = PlayerNameKeyboard(self.root,player,0)
            keyboard.value.set('  Amuro Ray  ')
            keyboard.accept()
            self.assertEqual(player.get(),'Amuro Ray')

    def test_layout_and_keyboard_fit_compact_and_full_hd(self):
        for side in range(2):
            for number in ('PA01-U01','PA01-U02','PA01-U03','ST01-U01','EX01-U01'):
                self.screen.add_card(side,number)
        for width,height in ((1366,688),(1920,1080)):
            with self.subTest(viewport=(width,height)):
                self.root.geometry(f'{width}x{height}+0+0')
                self.root.deiconify()
                self.settle()
                self.assertEqual(self.screen.cards.bbox(self.screen.cards.get_children()[0])[3],64)
                self.assertGreaterEqual(self.screen.cards.column("number", "width"),100)
                for button in [self.screen.start_button,*self.screen.add_buttons]:
                    self.assertGreaterEqual(button.winfo_height(),44)
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),self.root.winfo_rootx()+width)
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),self.root.winfo_rooty()+height)
                for roster in self.screen.roster_views:
                    self.assertGreaterEqual(roster.name.winfo_height(),44)
                    self.assertGreaterEqual(roster.canvas.winfo_height(),64, "A complete squad row must remain visible")
                    self.assertTrue(all(key.winfo_height()>=48 for key in roster.remove_keys))
                    roster.canvas.yview_moveto(1)
                    self.settle()
                    self.assertAlmostEqual(roster.canvas.yview()[1],1,places=2)
                with patch('companion.dialogs.monitor_bounds',return_value=(0,0,width,768 if width==1366 else 1080)):
                    self.screen.roster_views[0].name.event_generate('<ButtonRelease-1>',x=10,y=10)
                    self.settle()
                    keyboard = self.screen.name_keyboard
                    self.assertIsNotNone(keyboard)
                    for button in [*keyboard.buttons_by_key.values(),keyboard.done]:
                        self.assertGreaterEqual(button.winfo_height(),44)
                        self.assertGreaterEqual(button.winfo_rootx(),keyboard.window.winfo_rootx())
                        self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),keyboard.window.winfo_rootx()+keyboard.window.winfo_width())
                        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),keyboard.window.winfo_rooty()+keyboard.window.winfo_height())
                    keyboard.cancel()

    def test_catalog_insertion_reorder_duplicate_validation_and_slot_order(self):
        self.root.geometry('1366x688+0+0');self.root.deiconify()
        screen=self.screen
        screen.add_card(0,'PA01-U01')
        screen.add_card(0,'PA01-U02')
        screen.add_card(1,'ST01-U04')
        self.settle()
        # Catalog drop inserts at the indicated gap using the existing workflow.
        screen.drag_press=SquadDragPress('PA01-U03',screen.cards,0,0)
        screen.drag_pointer=(10,10)
        with patch.object(screen,'clear_drag'),patch.object(screen,'drop_side',return_value=0),patch.object(screen.roster_views[0],'insertion_index',return_value=1):
            screen.drop_unit(SimpleNamespace(widget=screen.cards,x_root=10,y_root=10))
        screen.drag_press=screen.drag_pointer=None
        self.assertEqual(screen.rosters[0],['PA01-U01','PA01-U03','PA01-U02'])
        screen.add_card(0,'PA01-U01')
        self.assertEqual(len(screen.rosters[0]),3)
        self.settle()
        row=screen.roster_views[0].unit_rows[0]
        screen.drag_press=SquadDragPress('PA01-U01',row,0,0,(0,0))
        screen.drag_pointer=(10,10)
        with patch.object(screen,'clear_drag'),patch.object(screen.roster_views[0],'insertion_index',return_value=3):
            screen.drop_unit(SimpleNamespace(widget=row,x_root=10,y_root=10))
        screen.drag_press=screen.drag_pointer=None
        self.assertEqual(screen.rosters[0],['PA01-U03','PA01-U02','PA01-U01'])
        screen.start()
        match=self.app.save.call_args.args[0]
        self.assertEqual([u.card.number for u in match.units if u.player==0],screen.rosters[0])
        self.assertEqual([u.slot for u in match.units if u.player==0],[1,2,3])
