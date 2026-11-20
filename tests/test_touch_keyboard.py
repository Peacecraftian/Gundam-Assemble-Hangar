import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.dialogs import Dialog
from companion.theme import setup_theme
from companion.touch_keyboard import TextKeyboard, bind_keyboard


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        setup_theme(self.root)
        self.root.geometry('1366x688+0+0')
        self.bounds=patch('companion.dialogs.monitor_bounds',return_value=(0,0,1366,768))
        self.bounds.start()

    def tearDown(self):
        self.root.destroy()
        self.bounds.stop()

    def settle(self):
        self.root.update()
        self.root.after(50,self.root.quit);self.root.mainloop()

    def open(self, widget):
        widget.pack();self.settle()
        widget.event_generate('<ButtonRelease-1>',x=10,y=10);self.settle()
        return getattr(self.root,'touch_keyboard',None)

    def test_live_search_updates_and_cancel_restores_original(self):
        value=tk.StringVar(self.root,'Gundam')
        changes=[]
        value.trace_add('write',lambda *_:changes.append(value.get()))
        widget=bind_keyboard(ttk.Entry(self.root,textvariable=value),'Search',live=True)
        keyboard=self.open(widget)
        keyboard.insert('z')
        self.assertEqual(value.get(),'z')
        keyboard.clear()
        self.assertEqual(value.get(),'')
        keyboard.cancel()
        self.assertEqual(value.get(),'Gundam')
        self.assertIn('z',changes)
        keyboard=self.open(widget)
        keyboard.clear();keyboard.accept()
        self.assertEqual(value.get(),'')

    def test_multiline_preserves_paragraphs_cancel_and_one_text_undo(self):
        text=tk.Text(self.root,undo=True)
        original='First paragraph.\n\nSecond paragraph.'
        text.insert('1.0',original);text.edit_reset()
        bind_keyboard(text,'Overview',multiline=True)
        keyboard=self.open(text)
        keyboard.insert('\nNew objective.')
        self.assertEqual(text.get('1.0','end-1c'),original)
        keyboard.accept()
        self.assertEqual(text.get('1.0','end-1c'),original+'\nNew objective.')
        text.edit_undo()
        self.assertEqual(text.get('1.0','end-1c'),original)
        keyboard=self.open(text);keyboard.clear();keyboard.cancel()
        self.assertEqual(text.get('1.0','end-1c'),original)

    def test_nested_number_pad_changes_only_dialog_draft_and_restores_grab(self):
        dialog=Dialog(self.root,'Parent')
        draft=tk.StringVar(dialog.window,'3')
        entry=bind_keyboard(ttk.Entry(dialog.body,textvariable=draft),'Damage Modifier',numeric=True)
        entry.pack();dialog.show((600,400));self.settle()
        keyboard=self.open(entry)
        keyboard.insert('-');keyboard.insert('2')
        self.assertEqual(draft.get(),'3')
        keyboard.accept();self.settle()
        self.assertEqual(draft.get(),'-2')
        self.assertEqual(self.root.grab_current(),dialog.window)
        dialog.cancel()

    def test_disabled_fields_and_spin_arrows_do_not_open_keyboard(self):
        entry=bind_keyboard(ttk.Entry(self.root,state='disabled'),'Disabled')
        self.open(entry)
        self.assertIsNone(getattr(self.root,'touch_keyboard',None))
        entry.state(['!disabled','readonly'])
        self.open(entry)
        self.assertIsNone(getattr(self.root,'touch_keyboard',None))
        spin=bind_keyboard(ttk.Spinbox(self.root,from_=0,to=10),'Number',numeric=True)
        spin.pack();self.settle()
        with patch.object(spin,'identify',return_value='uparrow'):
            spin.event_generate('<ButtonRelease-1>',x=10,y=10);self.settle()
        self.assertIsNone(getattr(self.root,'touch_keyboard',None))

    def test_modes_fit_compact_and_symbols_insert_without_recursive_popup(self):
        for options in ({},{'multiline':True},{'numeric':True}):
            with self.subTest(options=options):
                keyboard=TextKeyboard(self.root,tk.StringVar(self.root,''),'Input',**options)
                self.settle()
                for button in (*keyboard.buttons_by_key.values(),keyboard.done):
                    self.assertGreaterEqual(button.winfo_height(),44)
                    self.assertGreaterEqual(button.winfo_rootx(),keyboard.window.winfo_rootx())
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),keyboard.window.winfo_rootx()+keyboard.window.winfo_width())
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),keyboard.window.winfo_rooty()+keyboard.window.winfo_height())
                keyboard.entry.event_generate('<ButtonRelease-1>',x=5,y=5);self.settle()
                self.assertIs(self.root.touch_keyboard,keyboard)
                if not options.get('numeric'):
                    keyboard.toggle_symbols();keyboard.buttons_by_key['?'].invoke()
                    self.assertIn('?',keyboard.value.get())
                keyboard.cancel()

    def test_destroying_source_closes_keyboard_without_stale_writes(self):
        entry=bind_keyboard(ttk.Entry(self.root),'Search',live=True)
        keyboard=self.open(entry)
        entry.destroy();self.settle()
        self.assertFalse(keyboard.window.winfo_exists())
        self.assertIsNone(self.root.touch_keyboard)

class KeyboardCoverageTests(unittest.TestCase):
    def test_all_four_tabs_and_match_dialogs_have_keyboard_bindings(self):
        from companion.catalog import load_catalog
        from companion.match import Match
        from companion.storage import MatchStore
        from companion.ui import Companion
        from companion.theme import MISSION_SORTIE, TACTICS, BATTLEFIELD, MATCH_CONSOLE
        from companion.touch_service import TouchUnitDialog
        from companion.touch_scores import TouchScoreDialog
        from companion.touch_actions import TouchDicePrompt
        try:
            root=tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            catalog=load_catalog()
            store=MatchStore(Path(folder)/'coverage.sqlite3')
            match=Match.new(['Blue','Red'],'',2,[['PA01-U01'],['ST01-U04']],catalog)
            for unit in match.units:unit.deployed=True
            store.save(match,0)
            app=Companion(root,catalog,store)
            def fields(parent):
                found=[]
                for widget in parent.winfo_children():
                    if isinstance(widget,(ttk.Entry,ttk.Spinbox)) and not isinstance(widget,ttk.Combobox):
                        found.append(widget)
                    found.extend(fields(widget))
                return found
            try:
                for workspace, expected in ((MISSION_SORTIE,'Search Unit Catalog'),(TACTICS,'Search Tactics Cards'),(BATTLEFIELD,'Mission Name')):
                    app.switch_workspace(workspace)
                    root.update_idletasks()
                    entries=fields(app.view)
                    titles=[getattr(w,'touch_keyboard_options',{}).get('title') for w in entries]
                    self.assertIn(expected,titles)
                    for entry in entries:
                        self.assertTrue(hasattr(entry,'touch_keyboard_options') or 'Name' in str(entry.cget('style')))
                    if workspace==BATTLEFIELD:
                        for key in ('overview','objectives'):
                            self.assertTrue(app.battlefield_screen.fields[key].touch_keyboard_options['multiline'])
                        self.assertFalse(hasattr(app.battlefield_screen.briefing,'touch_keyboard_options'))
                app.switch_workspace(MATCH_CONSOLE)
                for factory in (lambda:TouchUnitDialog(app,app.match.unit(1)),
                                lambda:TouchScoreDialog(app,0,reason=TouchScoreDialog.ADJUST_VP),
                                lambda:TouchDicePrompt(root,unit=app.match.unit(1),profiles=app.attacks['PA01-U01'],app=app)):
                    dialog=factory()
                    for entry in fields(dialog.window):
                        self.assertTrue(hasattr(entry,'touch_keyboard_options'),str(entry))
                    dialog.cancel()
            finally:
                app.close()
