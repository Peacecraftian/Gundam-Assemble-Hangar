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
from companion.match import Match, GARRISON_RESCUE, GARRISON_DEFEAT, UNIT_DEFEAT
from companion.theme import setup_theme
from companion.touch_scores import TouchScoreDialog


class TouchScoreTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk display unavailable: {error}")
        self.root.withdraw()
        setup_theme(self.root)
        match = Match.new(['Blue', 'Red'], '', 3, [['PA01-U01', 'PA01-U02'], ['ST01-U04']], load_catalog())
        match.unit(2).deployed = match.unit(3).deployed = True
        self.app = SimpleNamespace(root=self.root, match=match, selected_id=2,
            photos=PhotoCache(self.root), remote_weapons={}, deployment=Mock(), announce=Mock())
        self.actions = []
        def edit(action, parent):
            draft = Match.from_json(self.app.match.to_json())
            action(draft)
            self.actions.append(self.app.match.to_json())
            self.app.match = draft
            return True
        self.app.edit = edit
        self.show = patch.object(TouchScoreDialog, 'show')
        self.show.start()

    def tearDown(self):
        self.show.stop()
        self.root.destroy()

    def open(self, reason):
        return TouchScoreDialog(self.app, 0, reason=reason)

    def test_adjustment_and_cancel_do_not_modify_until_record(self):
        d = self.open(TouchScoreDialog.ADJUST_VP)
        d.adjust_points(-5)
        d.adjust_points(1)
        self.assertEqual(d.points.get(), '-4')
        d.cancel()
        self.assertEqual(self.app.match.total(0), 0)
        self.assertEqual(self.actions, [])
        d = self.open(TouchScoreDialog.ADJUST_VP)
        d.adjust_points(-5)
        d.record()
        self.assertEqual(self.app.match.total(0), -5)
        self.assertEqual(len(self.actions), 1)

    def test_goal_phase_note_and_animation(self):
        d = self.open(TouchScoreDialog.SCENARIO_GOAL)
        d.phase.set('3')
        d.note.set('Objective 2')
        d.adjust_points(5)
        d.record()
        self.assertEqual(self.app.match.scores[-1].phase, 3)
        self.assertIn('Objective 2', self.app.match.scores[-1].reason)
        self.assertEqual(self.app.match.total(0), 5)
        self.app.deployment.play_goal.assert_called_once_with(side=0, points=5)

    def test_garrison_targets_second_deployed_slot_and_preserves_fixed_award(self):
        for reason in (GARRISON_RESCUE, GARRISON_DEFEAT):
            d = self.open(reason)
            self.assertEqual(d.selected_target()[0].id, 2)
            self.assertEqual(d.points.get(), '2')
            d.adjust_points(5)
            self.assertEqual(d.points.get(), '2')
            before = self.app.match.unit(2).round
            d.record()
            self.assertEqual(self.app.match.unit(2).round, before + (2 if reason == GARRISON_RESCUE else 0))
        self.assertEqual(self.app.match.total(0), 4)
        self.assertEqual(len(self.actions), 2)

    def test_reason_switch_to_defeat_clears_allied_selection(self):
        d = self.open(GARRISON_RESCUE)
        d.reason.set(UNIT_DEFEAT)
        d.update_reason()
        self.assertEqual([u.player for u, _ in d.target_options], [1])
        self.assertIsNone(d.selected_target()[0])
        self.assertTrue(d.record_button.instate(['disabled']))
        d.targets.current(0)
        d.set_target_points()
        vp = self.app.match.unit(3).card.vp
        d.record()
        self.assertEqual(self.app.match.total(0), vp)
        self.assertFalse(self.app.match.unit(3).deployed)
        self.assertEqual(self.app.match.unit(3).hp, self.app.match.unit(3).card.hp)
        self.assertEqual(len(self.actions), 1)

if __name__ == '__main__':
    unittest.main()
