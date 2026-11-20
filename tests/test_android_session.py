import json
import shutil
import tempfile
import unittest
from pathlib import Path

from companion.storage import SaveConflict
from platforms.android.app.src.main.python.tablet import Session


class TabletSessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        repo = Path(__file__).resolve().parents[1]
        for name in ("catalog.json", "scenarios.json", "attacks.json", "remote_weapons.json"):
            shutil.copyfile(repo / name, self.root / name)
        self.s = Session(self.root)
        self.addCleanup(lambda: self.s.close())

    def start(self, scenario=""):
        self.s.start("Blue", "Red", 2, scenario, json.dumps([["EX01-U03"], ["EX02-U03"]]))

    def reopen(self):
        self.s.close()
        self.s = Session(self.root)

    def test_declared_zero_system_rifle_resumes_and_undo_restores_everything(self):
        self.s.start("Blue", "Red", 2, "", json.dumps([["ST01-U02"], ["EX02-U03"]]))
        s = self.s
        s.deploy(1)
        s.deploy(2)
        before = s.match.to_json()
        rifle = "Twin Buster Rifle"
        s.declare(1, 2, rifle, 6, -9)
        self.assertEqual(s.unit(1).round, 7)
        rolled = "[7,8,9,10,7,1]"
        s.settle_roll(rolled, -9, False)
        self.reopen()
        s = self.s
        self.assertEqual(json.loads(s.pending())["values"], json.loads(rolled))
        self.assertEqual(s.roll_bonus(1, rifle, rolled), 4)
        s.finish_attack(1, 2, rolled, -9, 0, rifle)
        self.assertEqual(s.unit(2).hp, s.unit(2).card.hp-9)
        self.assertEqual(s.unit(1).round, 7)
        with self.assertRaises(ValueError):
            s.finish_attack(1, 2, rolled, -9, 0, rifle)
        s.undo()
        self.assertEqual(s.match.to_json(), before)
        s.condition(1, "Disarm")
        disarmed = s.match.to_json()
        s.declare(1, 0, rifle, 1, -9)
        s.settle_roll("[7]", -9, False)
        s.settle_roll("[8]", -9, True)
        self.assertEqual(s.roll_bonus(1, rifle, "[8]"), 0)
        s.finish_attack(1, 0, "[8]", -9, 0, rifle)
        self.assertEqual(s.match.total(0), 2)
        s.undo()
        self.assertEqual(s.match.to_json(), disarmed)

    def test_reserve_and_tabletop_garrison_paths(self):
        self.start()
        s = self.s
        before = s.match.to_json()
        with self.assertRaisesRegex(ValueError, "Reserve"):
            s.condition(1, "Slow")
        with self.assertRaisesRegex(ValueError, "Reserve"):
            s.service(1, json.dumps(dict(hp=1, energy=0, deployed=False, statuses=["Fracture"],
                      note="", upgrades=dict(speed=0,strength=0,shield_active=0,shield_spent=0))))
        s.blocked_deployment(1)
        self.assertEqual((s.unit(1).deployed,s.unit(1).round,s.unit(1).energy),(False,4,1))
        s.undo()
        self.assertEqual(s.match.to_json(), before)
        s.deploy(1)
        with self.assertRaises(ValueError):
            s.blocked_deployment(1)
        w = s.attacks(1)[0]
        s.declare(1, 0, w.name, 1, 0)
        s.settle_roll("[1]", 0, False)
        s.finish_attack(1, 0, "[1]", 0, 0, w.name)
        self.assertEqual((s.unit(1).round,s.match.total(0)),(2+w.timeline,0))
        s.garrison_defeat(1)
        self.assertEqual((s.unit(1).round,s.match.total(0)),(2+w.timeline,2))
        s.garrison_defeat(1, 3)
        self.assertEqual((s.unit(1).round,s.match.total(0)),(5+w.timeline,4))

    def test_official_copy_and_import_get_distinct_ids_and_resume_the_selected_map(self):
        s = self.s
        official = next(iter(s.official))
        record = json.loads(s.battlefield(official))["scenario"]
        record["palette"] = "space"
        record["cells"]["01-01"] = {"terrain": "height2", "special_terrain": "water", "token": "energy"}
        contents = json.dumps(record)
        custom = s.save_board(contents, official)
        imported = s.save_board(contents)
        self.assertEqual(len({custom, imported, official}), 3)
        self.assertEqual(len(set(s.scenarios.values())), len(s.boards))
        self.assertNotEqual(s.boards[official], s.boards[custom])
        self.start(custom)
        self.reopen()
        board = json.loads(self.s.battlefield())
        self.assertEqual(board["scenario"]["cells"], record["cells"])
        self.assertEqual(board["scenario"]["palette"], "space")
        self.s.save_board(contents, custom, board["revision"])
        with self.assertRaises(SaveConflict):
            self.s.save_board(contents, custom, board["revision"])
        with self.assertRaises(ValueError):
            self.s.delete_board(official, 0)

    def test_disarm_and_damage_are_separately_undoable_and_noop_edits_preserve_history(self):
        self.start()
        s = self.s
        s.deploy(1)
        s.deploy(2)
        s.condition(1, "Disarm")
        s.condition(2, "Fracture")
        s.upgrade(2, "shields")
        before = s.match.to_json()
        s.disarm(1)
        prepared = s.match.to_json()
        rev = s.revision
        s.cursor(1, 1)
        self.assertEqual(s.revision, rev)
        faces = "[4, 5, 9, 1]"
        hits = s.attack_hits(faces, 0)
        preview = json.loads(s.damage_preview(2, hits, 0))
        s.attack(1, 2, faces, 0, 0, "Beam Rifle")
        self.assertEqual(s.unit(1).round, s.unit(1).card.timeline + 4)
        self.assertEqual(preview["hp_loss"], 5)
        self.assertEqual(preview["remaining"], s.unit(2).hp)
        self.assertEqual(s.unit(2).shield_spent, 1)
        self.reopen()
        self.s.undo()
        self.assertEqual(self.s.match.to_json(), prepared)
        self.s.undo()
        self.assertEqual(self.s.match.to_json(), before)

    def test_missed_weapon_attack_pays_selected_cost_after_preview_only(self):
        self.start()
        s = self.s
        s.deploy(1)
        s.deploy(2)
        s.schedule(1, 1, 10, 1)
        before = s.match.to_json()
        for faces in ("[3,2,1]", "[1,1,2]"):
            s.damage_preview(2, s.attack_hits(faces, 0), 0)
            self.assertEqual(s.match.to_json(), before)
        s.attack(1, 2, faces, 0, 0, "Twin-Barreled Grenade Launcher")
        self.reopen()
        self.assertEqual((self.s.unit(1).phase, self.s.unit(1).round), (2, 2))
        self.assertEqual(self.s.unit(2).hp, self.s.unit(2).card.hp)
        self.s.undo()
        self.assertEqual(self.s.match.to_json(), before)

    def test_service_timeline_and_unit_state_save_and_undo_together(self):
        self.start()
        before = self.s.match.to_json()
        fields = dict(hp=4, energy=2, deployed=True, statuses=["Slow"], note="Objective",
                      upgrades=dict(strength=1, speed=0), shield_slots=["empty"] * 5)
        with self.assertRaises(ValueError):
            self.s.service(1, json.dumps(dict(fields, timeline=[2, 7, 2])))
        self.assertEqual(self.s.match.to_json(), before)
        self.s.service(1, json.dumps(dict(fields, timeline=[2, 7, 1])))
        self.reopen()
        unit = self.s.unit(1)
        self.assertEqual((unit.phase, unit.round, unit.hp, unit.energy), (2, 7, 4, 2))
        self.s.undo()
        self.assertEqual(self.s.match.to_json(), before)

    def test_service_remote_launch_and_legacy_shields_are_one_edit(self):
        self.start()
        s = self.s
        # Older saves can contain Shields in excess of the five displayed slots.
        s.service(2, json.dumps(dict(hp=13, energy=0, deployed=False, statuses=[], note="",
                                     upgrades=dict(strength=0, speed=0, shield_active=7, shield_spent=0))))
        before = s.match.to_json()
        fields = dict(hp=0, energy=3, deployed=True, note="", statuses=[],
                      upgrades=dict(strength=1, speed=0), shield_slots=["active"] * 5,
                      keep_extra_shields=False, launch_systems=["EX02-U03A"])
        with self.assertRaises(ValueError):
            s.service(2, json.dumps(fields))
        self.assertEqual(s.match.to_json(), before)
        s.service(2, json.dumps(dict(fields, hp=10)))
        self.reopen()
        self.assertEqual(self.s.unit(2).remote_weapon_hp, {"EX02-U03A": 1})
        self.assertEqual(self.s.unit(2).shield_active, 5)
        self.s.undo()
        self.assertEqual(self.s.match.to_json(), before)
        self.assertEqual(self.s.unit(2).shield_active, 7)

    def test_remote_defeat_award_and_finished_match_guard(self):
        self.start()
        s = self.s
        s.deploy(2)
        s.deploy_system(2, "EX02-U03A")
        before = s.match.to_json()
        s.unit_defeat(2, '["EX02-U03A"]')
        self.assertEqual(s.match.total(0), s.unit(2).card.vp + 2)
        s.undo()
        self.assertEqual(s.match.to_json(), before)
        s.defeat_system(2, "EX02-U03A")
        self.assertTrue(s.unit(2).deployed)
        self.assertEqual(s.match.total(0), 2)
        s.score(1, 1, 2, "Scenario goal")
        s.finish(1)
        self.reopen()
        self.assertEqual(self.s.match.winner, 1)
        with self.assertRaises(ValueError):
            self.s.schedule(2, 1, 6, 1)
        self.s.undo()
        self.assertIsNone(self.s.match.winner)
