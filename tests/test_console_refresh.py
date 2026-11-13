import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

from companion.catalog import load_catalog
from companion.match import GARRISON_DEFEAT, Match
from companion.storage import MatchStore
from companion.theme import MATCH_CONSOLE, TACTICS
from companion.ui import Companion


class ConsoleRefreshTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        app = self.app = Companion.__new__(Companion)
        app.store = MatchStore(Path(folder.name)/"match.sqlite3")
        self.addCleanup(app.store.close)
        app.match = Match.new(["Aki", "Ren"], "", 2,
                              [["PA01-U01"], ["ST01-U06"]], load_catalog())
        for unit in app.match.units:
            app.match.deploy_unit(unit.id)
        app.revision = app.store.save(app.match, 0, replace=True)
        app.active_workspace = MATCH_CONSOLE
        app.selected_id = app.match.units[0].id
        app.root = Mock()
        app.track = Mock()
        app.track.winfo_exists.return_value = True
        app.player_hangars = [Mock(), Mock()]
        app.score_readouts = [Mock(), Mock()]
        app.preview = Mock()
        app.undo_button = Mock()
        app.other_phases_button = Mock()
        app.timeline_hint = Mock()
        app.round_label = Mock()
        app.previous_round = Mock()
        app.next_round = Mock()
        app.deployment = Mock()
        app.draw_phase_lights = Mock()
        app.announce = Mock()
        app.render = Mock()

    def test_dash_and_undo_keep_card_art_and_console_alive(self):
        app = self.app
        before = app.match.to_json()
        self.assertTrue(app.edit(lambda match: match.dash_unit(1), app.root))
        app.render.assert_not_called()
        app.track.draw.assert_called_once()
        app.preview.draw.assert_not_called()
        for hangar in app.player_hangars:
            hangar.draw.assert_not_called()
        app.undo()
        self.assertEqual(app.match.to_json(), before)
        app.render.assert_not_called()
        self.assertEqual(app.track.draw.call_count, 2)
        app.undo_button.state.assert_called_with(["disabled"])

    def test_score_only_updates_total_without_redrawing_board(self):
        app = self.app
        app.edit(lambda match: match.record_score(0, 1, 2, "Scenario goal"), app.root)
        app.score_readouts[0].configure.assert_called_once_with(text="02")
        app.score_readouts[1].configure.assert_not_called()
        app.track.draw.assert_not_called()
        app.preview.draw.assert_not_called()
        app.render.assert_not_called()

    def test_energize_refreshes_only_affected_side_and_selected_card(self):
        app = self.app
        app.edit(lambda match: match.energize_unit(1), app.root)
        app.player_hangars[0].draw.assert_called_once()
        app.player_hangars[1].draw.assert_not_called()
        app.preview.draw.assert_called_once()
        app.track.draw.assert_called_once()
        app.render.assert_not_called()

    def test_garrison_and_defeat_update_totals_timeline_and_unit_state(self):
        app = self.app
        app.edit(lambda match: match.record_garrison(1, 1, GARRISON_DEFEAT), app.root)
        app.score_readouts[0].configure.assert_called_with(text="02")
        app.preview.draw.assert_not_called()
        app.edit(lambda match: match.defeat_unit(1, 1), app.root)
        self.assertFalse(app.match.unit(1).deployed)
        app.player_hangars[0].draw.assert_called_once()
        app.preview.draw.assert_called_once()
        app.score_readouts[1].configure.assert_called_with(text=f"{app.match.unit(1).card.vp:02d}")
        app.render.assert_not_called()

    def test_cursor_updates_round_phase_arrows_and_future_count(self):
        app = self.app
        app.edit(lambda match: match.set_cursor(2, 10), app.root)
        app.round_label.configure.assert_called_with(text="Round 10")
        app.draw_phase_lights.assert_called_once()
        app.next_round.state.assert_called_with(["disabled"])
        app.previous_round.state.assert_called_with(["!disabled"])
        app.other_phases_button.configure.assert_called_with(text="Other Phases (2)")
        app.render.assert_not_called()

    def test_full_render_for_finish_replacement_and_other_workspace(self):
        app = self.app
        app.edit(lambda match: match.finish(0), app.root)
        app.render.assert_called_once()
        app.render.reset_mock()
        app.undo()
        app.render.assert_called_once()
        app.render.reset_mock()
        app.save(deepcopy(app.match), app.root, replace=True)
        app.render.assert_called_once()
        app.render.reset_mock()
        app.active_workspace = TACTICS
        app.edit(lambda match: match.record_score(1, 1, 1, "Score"), app.root)
        app.render.assert_called_once()

    def test_noop_save_does_not_redraw_or_add_undo(self):
        app = self.app
        revision = app.revision
        app.edit(lambda match: None, app.root)
        self.assertEqual(app.revision, revision)
        self.assertFalse(app.store.can_undo())
        app.render.assert_not_called()
        app.track.draw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
