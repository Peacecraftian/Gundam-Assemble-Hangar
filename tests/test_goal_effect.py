import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Video import ANIMATION_FILES, goal_effect
from companion.catalog import load_catalog
from companion.dialogs import ScoreDialog
from companion.match import Match


class GoalEffectTests(unittest.TestCase):
    def tearDown(self):
        goal_effect.goal_frames.cache_clear()

    def test_clip_is_published_cached_and_ends_clear(self):
        goal_effect.goal_frames.cache_clear()
        self.assertIn(goal_effect.GOAL_ART.name, ANIMATION_FILES)
        frames, deadlines = goal_effect.goal_frames()
        self.assertEqual(len(frames), 25)
        self.assertEqual(deadlines[-1], 2.0)
        self.assertTrue(all(a < b for a, b in zip(deadlines, deadlines[1:])))
        self.assertIsNone(frames[-1].getbbox())
        self.assertIs(goal_effect.goal_frames()[0], frames)
        for frame in frames:
            self.assertEqual(frame.size, (256, 256))
            self.assertFalse(any(frame.getchannel('A').histogram()[1:255]))

    def test_bad_art_still_shows_actual_player_and_award(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.webp'
            for corrupt in (False, True):
                if corrupt:
                    path.write_bytes(b'not an image')
                goal_effect.goal_frames.cache_clear()
                with patch.object(goal_effect, 'GOAL_ART', path), \
                        patch.object(goal_effect, 'draw_placard') as placard, \
                        self.assertLogs(goal_effect.__name__, level='WARNING'):
                    goal_effect.draw_goal(Mock(), 790, 370, .2, 1, 8)
                self.assertEqual(placard.call_args.args[4:6], ('SCENARIO GOAL', 'PLAYER 2  ·  +8 VP'))

    def make_dialog(self, points, *, player=0, saved=True, goal=True):
        dialog = ScoreDialog.__new__(ScoreDialog)
        dialog.player = player
        dialog.selected_reason = Mock(return_value=ScoreDialog.SCENARIO_GOAL if goal else ScoreDialog.ADJUST_VP)
        dialog.selected_target = Mock(return_value=(None, None))
        dialog.selected_remote_weapons = Mock(return_value=())
        dialog.note = Mock(get=Mock(return_value='Supply crates'))
        dialog.phase = Mock(get=Mock(return_value='1'))
        dialog.points = Mock(get=Mock(return_value=str(points)))
        dialog.window = Mock()
        dialog.app = SimpleNamespace(
            match=Match.new(['Aki', 'Ren'], '', 2, [['PA01-U01'], ['ST01-U06']], load_catalog()),
            announce=Mock(), deployment=Mock())
        def edit(action, parent):
            if saved:
                try:
                    action(dialog.app.match)
                except ValueError:
                    return False
            return saved
        dialog.app.edit = edit
        return dialog

    def test_positive_goal_celebrates_after_save_and_dialog_closes(self):
        for side, points in ((0, 5), (1, 8)):
            with self.subTest(side=side):
                dialog = self.make_dialog(points, player=side)
                def celebrate(**kwargs):
                    dialog.window.destroy.assert_called_once()
                    self.assertEqual(dialog.app.match.total(side), points)
                    self.assertEqual(kwargs, {'side': side, 'points': points})
                dialog.app.deployment.play_goal.side_effect = celebrate
                dialog.record()
                dialog.app.deployment.play_goal.assert_called_once_with(side=side, points=points)
                self.assertEqual(len(dialog.app.match.scores), 1)

    def test_no_celebration_for_adjustments_or_unsaved_goal(self):
        for points, saved, goal in ((0, True, True), (-2, True, True), (5, False, True), (5, True, False)):
            with self.subTest(points=points, saved=saved, goal=goal):
                dialog = self.make_dialog(points, saved=saved, goal=goal)
                dialog.record()
                dialog.app.deployment.play_goal.assert_not_called()
                if not saved:
                    dialog.window.destroy.assert_not_called()
                    self.assertFalse(dialog.app.match.scores)


if __name__ == '__main__':
    unittest.main()
