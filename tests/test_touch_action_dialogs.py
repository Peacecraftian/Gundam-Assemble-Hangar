import sys
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion.artwork import PhotoCache
from companion.catalog import load_catalog
from companion.attacks import load_attacks, MAX_DICE
from companion.match import Match
from companion.theme import setup_theme
from companion.touch_actions import TouchTimelineAction, TouchDicePrompt, TouchDiceTray, Stepper

class TouchActionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk display unavailable: {error}")
        self.root.withdraw()
        setup_theme(self.root)
        self.catalog=load_catalog()
        match=Match.new(['Blue','Red'], '', 2, [['PA01-U01','PA01-U02'],['ST01-U04']],self.catalog)
        match.unit(2).deployed=match.unit(3).deployed=True
        self.app=SimpleNamespace(root=self.root,match=match,selected_id=2,revision=1,
            photos=PhotoCache(self.root),deployment=Mock(),announce=Mock())
        self.actions=[]
        def edit(action,parent):
            draft=Match.from_json(self.app.match.to_json())
            action(draft)
            self.actions.append(self.app.match.to_json())
            self.app.match=draft
            return True
        self.app.edit=edit
        self.show=patch('companion.dialogs.Dialog.show')
        self.show.start()

    def tearDown(self):
        self.show.stop()
        self.root.destroy()

    def attack_prompt(self):
        unit=self.app.match.unit(2)
        profiles=load_attacks(self.catalog)[unit.card.number]
        return TouchDicePrompt(self.root,unit=unit,profiles=profiles,app=self.app)

    def test_dash_and_energize_preserve_transaction_and_preselection(self):
        for action in ('Dash','Energize'):
            d=TouchTimelineAction(self.app,0,action)
            self.assertEqual(d.choice.options[d.choice.current()][0].id,2)
            before=self.app.match.unit(2).round
            d.confirm.invoke()
            self.assertEqual(self.app.match.unit(2).round,before+2)
        self.assertEqual(self.app.match.unit(2).energy,1)
        self.assertEqual(len(self.actions),2)
        self.app.deployment.play_dash.assert_called_once_with(side=0)
        self.app.deployment.play_energize.assert_called_once_with(side=0)

    def test_empty_lineup_cannot_confirm_and_cancel_does_not_edit(self):
        self.app.match.unit(2).deployed=False
        d=TouchTimelineAction(self.app,0,'Dash')
        self.assertTrue(d.confirm.instate(['disabled']))
        d.cancel()
        self.assertEqual(self.actions,[])

    def test_attack_uses_upgrades_modifiers_and_target_in_existing_roll(self):
        self.app.match.unit(2).strength=2
        d=self.attack_prompt()
        printed=d.attack().strength
        self.assertEqual(d.upgrades.get(),'2')
        d.steppers['OTHER STRENGTH MODIFIER'].adjust(-1)
        d.steppers['ACCURACY MODIFIER'].adjust(1)
        self.assertEqual(d.dice_count(),printed+1)
        with patch('companion.touch_actions.TouchDicePrompt.create_tray') as tray:
            d.roll()
        self.assertEqual(tray.call_args.args[2:4],(printed+1,1))
        self.assertEqual(tray.call_args.kwargs['target'].id,3)
        self.assertEqual(tray.call_args.kwargs['revision'],1)

    def test_stale_revision_blocks_attack_and_garrison_remains_available_without_units(self):
        d=self.attack_prompt()
        d.error=Mock()
        self.app.revision=2
        with patch('companion.touch_actions.TouchDicePrompt.create_tray') as tray:
            d.roll()
            tray.assert_not_called()
        d.error.assert_called_once()
        d.cancel()
        self.app.match.unit(3).deployed=False
        d=self.attack_prompt()
        self.assertEqual(d.targets[d.target_choice.current()].label, 'Enemy Garrison')
        self.assertFalse(d.roll_button.instate(['disabled']))

    def test_free_roll_stepper_limits_and_invalid_text_still_validated(self):
        d=TouchDicePrompt(self.root)
        step=d.steppers['NUMBER OF DICE']
        step.adjust(-5)
        self.assertEqual(d.dice_count(),1)
        d.strength.set(str(MAX_DICE))
        step.adjust(5)
        self.assertEqual(d.dice_count(),MAX_DICE)
        d.strength.set('not a number')
        d.error=Mock()
        with patch('companion.touch_actions.TouchDicePrompt.create_tray') as tray:
            d.roll()
            tray.assert_not_called()
        d.error.assert_called_once()

    def test_result_tray_keeps_reroll_selection_and_touch_modifiers(self):
        unit=self.app.match.unit(2)
        with patch.object(TouchDiceTray,'start'):
            tray=TouchDiceTray(self.root,'Attack',3,0,0,app=self.app,attacker=unit,
                               target=self.app.match.unit(3),weapon=load_attacks(self.catalog)[unit.card.number][0],revision=1)
            self.root.update_idletasks()
            tray.reveal((1,5,9))
            tray.selected={0}
            tray.update_results()
            before=tray.values
            tray.reroll()
            self.assertEqual(tray.reroll_indices,(0,))
            self.assertEqual(tray.values,before)
            self.assertIn('TouchTray',tray.apply_button.cget('style'))
            self.assertEqual(tray.damage_modifier.get(),'0')
            tray.cancel()

if __name__=='__main__':
    unittest.main()
