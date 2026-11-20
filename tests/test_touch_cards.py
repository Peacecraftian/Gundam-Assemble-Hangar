import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion.catalog import load_catalog
from companion.match import Match
from companion.storage import MatchStore
from companion.touch_cards import cycle_upgrade, toggle_condition

class TouchControlsTests(unittest.TestCase):
    def setUp(self):
        self.match = Match.new(['P1','P2'], '', 2, [['PA01-U01'],['PA01-U02']], load_catalog())

    def test_each_upgrade_wraps_after_eight(self):
        for key in ('speed', 'strength', 'shields'):
            for expected in (*range(1, 9), 0, 1):
                cycle_upgrade(self.match, 1, key)
                unit = self.match.unit(1)
                value = unit.shield_active + unit.shield_spent if key == 'shields' else getattr(unit, key)
                self.assertEqual(value, expected)
                self.assertEqual(Match.from_json(self.match.to_json()).unit(1), unit)

    def test_new_shield_keeps_spent_shields_and_slot_order(self):
        unit = self.match.unit(1)
        unit.shield_active, unit.shield_spent = 1, 2
        unit.shield_slots = ['spent','empty','active','spent','empty']
        cycle_upgrade(self.match, 1, 'shields')
        self.assertEqual((unit.shield_active, unit.shield_spent), (2,2))
        self.assertEqual(unit.shields, ('spent','active','active','spent','empty'))

    def test_extra_shields_survive_existing_service_bay_save(self):
        unit = self.match.unit(1)
        for _ in range(7):
            cycle_upgrade(self.match,1,'shields')
        self.assertEqual(unit.extra_shields,(2,0))
        # Service Bay uses this existing model path; no new save schema is needed.
        values = dict(hp=unit.hp, energy=unit.energy, deployed=unit.deployed, statuses=unit.statuses,
                      upgrades={'speed':unit.speed,'strength':unit.strength}, note=unit.note,
                      shield_slots=list(unit.shields))
        self.match.edit_unit(1, **values)
        self.assertEqual(unit.shield_active, 7)

    def test_status_toggles_without_duplicate_entries(self):
        self.match.deploy_unit(1)
        for status in ('Disarm','Slow','Fracture'):
            toggle_condition(self.match,1,status)
            self.assertEqual(self.match.unit(1).statuses.count(status),1)
            toggle_condition(self.match,1,status)
            self.assertNotIn(status,self.match.unit(1).statuses)

    def test_finished_match_blocks_draft_edits(self):
        self.match.finish(0)
        original=self.match.to_json()
        for key in ('speed','strength','shields'):
            cycle_upgrade(self.match,1,key)
        toggle_condition(self.match,1,'Slow')
        self.assertEqual(self.match.to_json(),original)

    def test_wrap_is_one_undoable_edit_after_reopening(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.sqlite3'
            store=MatchStore(path)
            for _ in range(8): cycle_upgrade(self.match,1,'shields')
            revision=store.save(self.match,0)
            cycle_upgrade(self.match,1,'shields')
            revision=store.save(self.match,revision)
            store.close()
            reopened=MatchStore(path)
            restored,_=reopened.undo(revision)
            self.assertEqual(restored.unit(1).shield_active,8)
            reopened.close()

if __name__=='__main__': unittest.main(verbosity=2)
