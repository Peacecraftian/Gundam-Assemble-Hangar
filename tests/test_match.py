import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from companion.catalog import ASSETS, card_source_directory, load_catalog, load_remote_weapons
from companion.match import GARRISON_DEFEAT, GARRISON_RESCUE, UPGRADES, Match
from companion.storage import UNDO_LIMIT, MatchStore, SaveConflict


class MatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(verify_images=True)
        cls.weapons = load_remote_weapons(cls.catalog)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "match.sqlite3"
        self.store = MatchStore(self.path)
        self.addCleanup(self.store.close)
        self.match = Match.new(
            ["Kai", "Char"], "Test scenario", 2,
            [["EX01-U02", "EX01-U02", "ST01-U01"], ["ST01-U04", "PA01-U02", "PA01-U03"]], self.catalog,
        )

    def test_scenario_saves_upgrade_existing_database_without_changing_match_history(self):
        revision = self.store.save(self.match, 0)
        self.match.round = 2
        revision = self.store.save(self.match, revision)
        with self.store.db:
            self.store.db.execute("DROP TABLE scenarios")

        first = MatchStore(self.path)
        self.addCleanup(first.close)
        scenario = {"id": "local-example", "name": "Test field", "overview": "First line\n\nSecond line",
                    "cells": {"01-01": {"terrain": "water", "token": "energy"}}}
        first.save_scenario(scenario, 0)
        second = MatchStore(self.path)
        self.addCleanup(second.close)
        self.assertEqual(second.load_scenarios(), [(scenario, 1)])
        updated = dict(scenario, name="Coastal assault")
        second.save_scenario(updated, 1)
        with self.assertRaises(SaveConflict):
            first.save_scenario(scenario, 1)
        self.assertEqual(first.load_scenarios(), [(updated, 2)])
        match, _ = first.undo(revision)
        self.assertEqual(match.round, 1)
        self.assertEqual(first.load_scenarios(), [(updated, 2)])

    def test_scenario_deletion_requires_a_local_id_and_current_revision(self):
        official = {"id": "official-example", "name": "Official scenario"}
        local = {"id": "local-example", "name": "Custom scenario"}
        self.store.save_scenario(official, 0)
        self.store.save_scenario(local, 0)
        self.store.save_scenario(dict(local, name="Updated custom scenario"), 1)

        with self.assertRaisesRegex(ValueError, "Only saved local scenarios"):
            self.store.delete_scenario(official["id"], 1)
        with self.assertRaises(SaveConflict):
            self.store.delete_scenario(local["id"], 1)
        self.store.delete_scenario(local["id"], 2)
        self.assertEqual(self.store.load_scenarios(), [(official, 1)])

    def test_match_keeps_linked_scenario_through_resume_and_undo(self):
        legacy_payload = self.match.to_json()
        self.assertNotIn("scenario_id", json.loads(legacy_payload))
        self.assertIsNone(Match.from_json(legacy_payload).scenario_id)
        match = Match.new(["Kai", "Char"], "Coastal assault", 2, [["EX01-U01"], ["ST01-U04"]],
                          self.catalog, scenario_id="local-coastal-assault")
        revision = self.store.save(match, 0)
        match.set_cursor(1, 2)
        revision = self.store.save(match, revision)
        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        resumed, _ = reopened.load()
        self.assertEqual(resumed.scenario_id, "local-coastal-assault")
        previous, _ = reopened.undo(revision)
        self.assertEqual((previous.round, previous.scenario, previous.scenario_id),
                         (1, "Coastal assault", "local-coastal-assault"))

    def test_supplied_cards_have_printed_stats(self):
        expected = {
            "EX01-U01": (14, 10, 3), "EX01-U02": (8, 5, 1), "EX01-U03": (11, 7, 2),
            "EX02-U01": (16, 10, 1), "EX02-U02": (12, 7, 2), "EX02-U03": (13, 8, 3),
            "PA01-U01": (17, 10, 1), "PA01-U02": (12, 7, 2), "PA01-U03": (13, 7, 2),
            "ST01-U01": (15, 8, 2), "ST01-U02": (12, 9, 3), "ST01-U03": (17, 10, 2),
            "ST01-U04": (12, 7, 2), "ST01-U05": (15, 9, 3), "ST01-U06": (13, 7, 1),
        }
        for number, stats in expected.items():
            card = self.catalog[number]
            self.assertEqual((card.hp, card.vp, card.timeline), stats, number)
        self.assertEqual([card.number for card in self.catalog.values() if card.mass_produced], ["EX01-U02"])

    def test_new_squad_allows_only_mass_produced_duplicates_by_card_number(self):
        with self.assertRaisesRegex(ValueError, "can only appear once"):
            Match.new(["A", "B"], "", 2, [["ST01-U01"], ["ST01-U01", "ST01-U01"]], self.catalog)

        match = Match.new(
            ["A", "B"], "", 2,
            [["ST01-U01", "PA01-U01", "EX01-U02", "EX01-U02"], ["ST01-U01"]], self.catalog,
        )
        self.assertNotEqual(match.unit(3).label, match.unit(4).label)
        self.assertEqual(match.unit(1).card.number, match.unit(5).card.number)

    def test_legacy_match_resumes_with_existing_duplicates(self):
        payload = json.loads(self.match.to_json())
        for unit in payload["units"]:
            unit["card"].pop("mass_produced", None)
        payload["units"][1]["card"] = payload["units"][2]["card"]
        legacy = Match.from_json(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(legacy.unit(2).card.number, legacy.unit(3).card.number)
        self.assertEqual(json.loads(legacy.to_json()), payload)

    def test_cursor_arrows_cross_phase_boundaries_without_wrapping_the_match(self):
        self.assertIsNone(self.match.adjacent_cursor(-1))
        self.assertEqual(self.match.adjacent_cursor(1), (1, 2))
        self.match.set_cursor(1, 10)
        self.assertEqual(self.match.adjacent_cursor(1), (2, 1))
        self.assertEqual((self.match.phase, self.match.round), (1, 10))
        self.match.set_cursor(2, 1)
        self.assertEqual(self.match.adjacent_cursor(-1), (1, 10))
        self.match.set_cursor(2, 10)
        self.assertIsNone(self.match.adjacent_cursor(1))

    def test_shield_slots_round_trip_and_preserve_legacy_extras(self):
        payload = json.loads(self.match.to_json())
        unit = payload["units"][0]
        self.assertNotIn("shield_slots", unit)
        unit.update(shield_active=3, shield_spent=4)
        self.match = Match.from_json(json.dumps(payload))
        self.assertEqual(self.match.unit(1).shields, ("active", "active", "active", "spent", "spent"))
        self.assertEqual(self.match.unit(1).extra_shields, (0, 2))
        revision = self.store.save(self.match, 0)

        states = ["spent", "empty", "active", "spent", "active"]
        fields = dict(hp=8, energy=0, deployed=False, statuses=[], note="", upgrades={"speed": 1, "strength": 0})
        self.match.edit_unit(1, **fields, shield_slots=states)
        revision = self.store.save(self.match, revision)
        loaded, _ = self.store.load()
        unit = loaded.unit(1)
        self.assertEqual(unit.shields, tuple(states))
        self.assertEqual((unit.shield_active, unit.shield_spent), (2, 4))

        loaded.edit_unit(1, **fields, shield_slots=states, keep_extra_shields=False)
        revision = self.store.save(loaded, revision)
        self.assertEqual(loaded.unit(1).extra_shields, (0, 0))
        previous, revision = self.store.undo(revision)
        self.assertEqual(previous.unit(1).shields, tuple(states))
        self.assertEqual(previous.unit(1).extra_shields, (0, 2))
        legacy, _ = self.store.undo(revision)
        self.assertEqual((legacy.unit(1).shield_active, legacy.unit(1).shield_spent), (3, 4))

    def test_clearing_a_hangar_status_is_undoable_and_keeps_other_state(self):
        self.match.edit_unit(
            1, hp=7, energy=2, deployed=True, statuses=["Disarm", "Slow"], note="Unit 1",
            upgrades={"speed": 2, "strength": 1}, shield_slots=["empty", "active", "empty", "empty", "spent"],
        )
        revision = self.store.save(self.match, 0)
        self.match.clear_unit_status(1, "Disarm")
        self.match.clear_unit_status(1, "Disarm")
        revision = self.store.save(self.match, revision)
        saved, _ = self.store.load()
        unit = saved.unit(1)
        self.assertEqual(unit.statuses, ["Slow"])
        self.assertEqual((unit.hp, unit.energy, unit.deployed), (7, 2, True))
        self.assertEqual((unit.shield_active, unit.shield_spent, unit.speed), (1, 1, 2))
        self.assertEqual(self.store.undo(revision)[0].unit(1).statuses, ["Disarm", "Slow"])

        saved.finish(0)
        saved.clear_unit_status(1, "Slow")
        self.assertEqual(saved.unit(1).statuses, ["Slow"])

    def test_hangar_deploy_changes_only_deployment_and_can_be_undone(self):
        unit = self.match.unit(2)
        unit.hp, unit.energy, unit.note = 6, 2, "Carry objective"
        revision = self.store.save(self.match, 0)
        before = replace(unit)

        self.match.deploy_unit(unit.id)
        self.assertEqual(unit, replace(before, deployed=True))
        self.assertFalse(self.match.unit(1).deployed)
        revision = self.store.save(self.match, revision)
        self.assertTrue(self.store.load()[0].unit(unit.id).deployed)
        self.assertEqual(self.store.undo(revision)[0].unit(unit.id), before)

        self.match.finish(0)
        self.match.deploy_unit(1)
        self.assertFalse(self.match.unit(1).deployed)

    def test_quick_status_counters_apply_clear_and_undo_without_stacking(self):
        self.match.deploy_unit(1)
        unit = self.match.unit(1)
        unit.statuses = ["Slow"]
        revision = self.store.save(self.match, 0)

        self.match.adjust_unit_counter(1, "Fracture", 1)
        self.match.adjust_unit_counter(1, "Fracture", 1)
        self.assertEqual(unit.statuses, ["Fracture", "Slow"])
        revision = self.store.save(self.match, revision)

        self.match.adjust_unit_counter(1, "Fracture", -1)
        self.match.adjust_unit_counter(1, "Fracture", -1)
        self.assertEqual(unit.statuses, ["Slow"])
        revision = self.store.save(self.match, revision)
        self.assertEqual(self.store.undo(revision)[0].unit(1).statuses, ["Fracture", "Slow"])

        self.match.finish(0)
        self.match.adjust_unit_counter(1, "Disarm", 1)
        self.match.adjust_unit_counter(1, "Slow", -1)
        self.assertEqual(unit.statuses, ["Slow"])

    def test_quick_unit_counters_keep_limits_and_restore_inactive_shields_in_place(self):
        unit = self.match.unit(1)
        unit.shield_slots = ["spent", "empty", "active", "spent", "active"]
        unit.shield_active, unit.shield_spent = 2, 4
        revision = self.store.save(self.match, 0)

        self.match.adjust_unit_counter(1, "hp", 1)
        self.assertEqual(unit.hp, unit.card.hp)
        self.match.adjust_unit_counter(1, "hp", -1)
        for counter in ("energy", "speed", "strength"):
            self.match.adjust_unit_counter(1, counter, -1)
            self.assertEqual(getattr(unit, counter), 0)
            self.match.adjust_unit_counter(1, counter, 1)
        self.match.adjust_unit_counter(1, "shields", 1)
        self.assertEqual(unit.shields, ("active", "empty", "active", "active", "active"))
        self.assertEqual((unit.shield_active, unit.shield_spent, unit.extra_shields), (6, 0, (2, 0)))
        self.match.adjust_unit_counter(1, "shields", -1)
        self.assertEqual((unit.shields[-1], unit.shield_active, unit.shield_spent), ("spent", 5, 1))

        revision = self.store.save(self.match, revision)
        saved, _ = self.store.load()
        self.assertEqual((saved.unit(1).hp, saved.unit(1).energy, saved.unit(1).speed, saved.unit(1).strength), (7, 1, 1, 1))
        self.assertEqual(saved.unit(1).shields, unit.shields)
        self.assertEqual(self.store.undo(revision)[0].unit(1).shield_spent, 4)

        for _ in range(6):
            self.match.adjust_unit_counter(2, "shields", 1)
        self.assertEqual(self.match.unit(2).shield_active, 5)
        self.match.finish(0)
        self.match.adjust_unit_counter(1, "hp", -1)
        self.assertEqual(unit.hp, 7)

    def test_new_match_and_catalog_update(self):
        self.assertEqual(len({unit.id for unit in self.match.units}), 6)
        self.assertNotEqual(self.match.unit(1).label, self.match.unit(2).label)
        self.assertTrue(all(not unit.deployed and unit.hp == unit.card.hp for unit in self.match.units))
        self.assertEqual([unit.id for unit in self.match.tokens(0, 1, 1)], [1, 2])
        self.store.save(self.match, 0)

        published = self.catalog["EX01-U02"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Unit Cards").mkdir()
            shutil.copy(card_source_directory(ASSETS, "Unit Cards") / published.image, root / "Unit Cards" / published.image)
            (root / "catalog.json").write_text(json.dumps({
                "TEST-U01": {
                    "name": published.name, "title": published.title, "hp": 13, "vp": published.vp,
                    "timeline": 4, "image": published.image,
                }
            }), encoding="utf-8")
            update = load_catalog(root, verify_images=True)
        update[published.number] = replace(published, hp=99)
        match = Match.new(["A", "B"], "", 2, [["TEST-U01"], [published.number]], update)
        self.assertEqual((match.unit(1).card.number, match.unit(1).round), ("TEST-U01", 4))
        self.assertEqual(self.store.load()[0].unit(1).card.hp, 8)
        with self.assertRaisesRegex(ValueError, "published catalog"):
            Match.new(["A", "B"], "", 2, [["UNKNOWN"], [published.number]], update)

    def test_timeline_persists_stack_and_undo(self):
        revision = self.store.save(self.match, 0)
        self.match.set_cursor(1, 8)
        self.match.move_token(1, 1, 8)
        self.match.move_token(2, 2, 2)
        revision = self.store.save(self.match, revision)
        self.match.move_token(1, 2, 2)
        self.assertEqual([unit.id for unit in self.match.tokens(0, 2, 2)], [2, 1])
        self.match.move_token(1, 2, 2, 1)
        self.store.save(self.match, revision)

        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        saved, revision = reopened.load()
        self.assertEqual([unit.id for unit in saved.tokens(0, 2, 2)], [1, 2])
        self.assertEqual((saved.phase, saved.round), (1, 8))
        previous, _ = reopened.undo(revision)
        self.assertEqual((previous.unit(1).phase, previous.unit(1).round), (1, 8))

    def test_unit_defeat_updates_score_and_unit_in_one_undoable_edit(self):
        self.match.edit_unit(
            1, hp=1, energy=2, deployed=True, statuses=["Fracture", "Slow"], note="Table note",
            upgrades={"speed": 2, "strength": 1}, shield_slots=["active", "spent", "empty", "empty", "empty"],
        )
        self.match.move_token(1, 1, 10)
        self.match.move_token(2, 2, 2)
        before = self.match.to_json()
        revision = self.store.save(self.match, 0)

        with self.assertRaisesRegex(ValueError, "Scoring Phase"):
            self.match.defeat_unit(1, 3)
        self.assertEqual(self.match.to_json(), before)
        self.match.defeat_unit(1, 1, note="Beam Rifle")
        unit = self.match.unit(1)
        self.assertEqual((unit.deployed, unit.hp, unit.statuses), (False, unit.card.hp, []))
        self.assertEqual((unit.energy, unit.speed, unit.strength, unit.note), (2, 2, 1, "Table note"))
        self.assertEqual(unit.shields, ("active", "spent", "empty", "empty", "empty"))
        self.assertEqual([token.id for token in self.match.tokens(0, 2, 2)], [2, 1])
        self.assertEqual((self.match.total(0), self.match.total(1)), (0, unit.card.vp))
        self.assertEqual((self.match.scores[-1].phase, self.match.scores[-1].reason),
                         (1, f"Unit defeat · {unit.label} · Beam Rifle"))
        after = self.match.to_json()
        with self.assertRaisesRegex(ValueError, "Reserve"):
            self.match.defeat_unit(1, 1)
        self.assertEqual(self.match.to_json(), after)
        self.store.save(self.match, revision)

        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        saved, revision = reopened.load()
        self.assertEqual(saved.to_json(), after)
        previous, _ = reopened.undo(revision)
        self.assertEqual(previous.to_json(), before)
        self.assertFalse(reopened.can_undo())

    def test_zero_vp_unit_defeat_still_records_the_unit_state(self):
        unit = self.match.unit(1)
        unit.card = replace(unit.card, vp=0)
        self.match.deploy_unit(1)
        self.match.defeat_unit(1, 1)
        self.assertEqual((unit.deployed, unit.phase, unit.round), (False, 1, 3))
        self.assertEqual(self.match.scores[-1].points, 0)

    def test_remote_weapon_hp_persists_per_parent_instance(self):
        weapon = replace(self.weapons["EX02-U01A"], hp=3)
        match = Match.new(["A", "B"], "", 2, [[weapon.parent], [weapon.parent]], self.catalog)
        match = Match.from_json(match.to_json())
        self.assertEqual(match.unit(1).remote_weapon_hp, {})
        with self.assertRaisesRegex(ValueError, "Reserve"):
            match.deploy_remote_weapon(1, weapon)
        match.deploy_unit(1)
        match.deploy_unit(2)
        with self.assertRaisesRegex(ValueError, "parent unit"):
            match.deploy_remote_weapon(1, self.weapons["EX02-U02A"])
        match.deploy_remote_weapon(1, weapon)
        match.deploy_remote_weapon(2, weapon)
        match.adjust_remote_weapon_hp(1, weapon, -1)
        match.deploy_remote_weapon(1, weapon)
        revision = self.store.save(match, 0)

        saved, saved_revision = self.store.load()
        self.assertEqual(saved_revision, revision)
        self.assertEqual(saved.unit(1).remote_weapon_hp, {weapon.number: 2})
        self.assertEqual(saved.unit(2).remote_weapon_hp, {weapon.number: 3})
        saved.adjust_remote_weapon_hp(1, weapon, 10)
        self.assertEqual(saved.unit(1).remote_weapon_hp, {weapon.number: 3})

    def test_remote_weapon_defeat_returns_to_supply_scores_once_and_undoes_together(self):
        weapon = self.weapons["EX02-U02A"]
        match = Match.new(["A", "B"], "", 2, [[weapon.parent], ["ST01-U01"]], self.catalog)
        match.deploy_unit(1)
        match.deploy_remote_weapon(1, weapon)
        match.set_cursor(2, 1)
        unit = match.unit(1)
        position = unit.phase, unit.round, unit.stack
        before = match.to_json()
        revision = self.store.save(match, 0)

        match.adjust_remote_weapon_hp(1, weapon, -1)
        match.adjust_remote_weapon_hp(1, weapon, -1)
        self.assertEqual(unit.remote_weapon_hp, {})
        self.assertTrue(unit.deployed)
        self.assertEqual((unit.phase, unit.round, unit.stack), position)
        self.assertEqual([(entry.player, entry.phase, entry.points) for entry in match.scores], [(1, 2, 2)])
        revision = self.store.save(match, revision)
        previous, _ = self.store.undo(revision)
        self.assertEqual(previous.to_json(), before)
        match.deploy_remote_weapon(1, weapon)
        self.assertEqual(unit.remote_weapon_hp, {weapon.number: weapon.hp})

    def test_record_remote_weapon_defeat_uses_selected_phase_and_undoes_only_the_system(self):
        weapon = self.weapons["EX02-U01A"]
        match = Match.new(["A", "B"], "", 2, [[weapon.parent], [weapon.parent]], self.catalog)
        for unit_id in (1, 2):
            match.deploy_unit(unit_id)
            match.deploy_remote_weapon(unit_id, weapon)
        parent = match.unit(2)
        parent.hp -= 3
        parent.statuses.append("Slow")
        before = match.to_json()
        revision = self.store.save(match, 0)
        with self.assertRaisesRegex(ValueError, "Scoring Phase"):
            match.defeat_remote_weapon(parent.id, weapon, 3)
        self.assertEqual(match.to_json(), before)

        match.defeat_remote_weapon(parent.id, weapon, "2", note="Area attack")
        self.assertEqual(parent, replace(Match.from_json(before).unit(parent.id), remote_weapon_hp={}))
        self.assertEqual(match.unit(1).remote_weapon_hp, {weapon.number: weapon.hp})
        score, = match.scores
        self.assertEqual((score.player, score.phase, score.points), (0, 2, weapon.vp))
        self.assertEqual(score.reason, f"RWS defeat · {weapon.name} · {parent.label} · Area attack")
        after = match.to_json()
        with self.assertRaisesRegex(ValueError, "in supply"):
            match.defeat_remote_weapon(parent.id, weapon, 2)
        self.assertEqual(match.to_json(), after)
        revision = self.store.save(match, revision)
        self.assertEqual(self.store.load()[0].to_json(), after)
        previous, _ = self.store.undo(revision)
        self.assertEqual(previous.to_json(), before)
        self.assertFalse(self.store.can_undo())

    def test_parent_defeat_returns_only_its_system_to_supply(self):
        weapon = self.weapons["EX02-U03A"]
        match = Match.new(["A", "B"], "", 2, [[weapon.parent], [weapon.parent]], self.catalog)
        for unit_id in (1, 2):
            match.deploy_unit(unit_id)
            match.deploy_remote_weapon(unit_id, weapon)
        before = match.to_json()
        revision = self.store.save(match, 0)

        match.defeat_unit(1, 1)
        self.assertEqual(match.unit(1).remote_weapon_hp, {})
        self.assertEqual(match.unit(2).remote_weapon_hp, {weapon.number: weapon.hp})
        self.assertEqual([entry.points for entry in match.scores], [match.unit(1).card.vp])
        revision = self.store.save(match, revision)
        previous, _ = self.store.undo(revision)
        self.assertEqual(previous.to_json(), before)

    def test_simultaneous_unit_and_remote_weapon_defeat_scores_and_undoes_together(self):
        weapon = self.weapons["EX02-U01A"]
        match = Match.new(["A", "B"], "", 2, [[weapon.parent], [weapon.parent]], self.catalog)
        match.deploy_unit(1)
        match.deploy_unit(2)
        match.deploy_remote_weapon(2, weapon)
        before = match.to_json()
        with self.assertRaisesRegex(ValueError, "deployed Remote Weapon System"):
            match.defeat_unit(1, 2, defeated_weapons=(weapon,))
        self.assertEqual(match.to_json(), before)

        match.deploy_remote_weapon(1, weapon)
        before = match.to_json()
        revision = self.store.save(match, 0)
        with self.assertRaisesRegex(ValueError, "only be recorded once"):
            match.defeat_unit(1, 2, defeated_weapons=(weapon, weapon))
        self.assertEqual(match.to_json(), before)

        match.defeat_unit(1, 2, note="Same attack", defeated_weapons=(weapon,))
        parent = match.unit(1)
        self.assertFalse(parent.deployed)
        self.assertEqual(parent.remote_weapon_hp, {})
        self.assertEqual(parent.round, parent.card.timeline + 2)
        self.assertEqual(match.unit(2).remote_weapon_hp, {weapon.number: weapon.hp})
        self.assertEqual([(entry.player, entry.phase, entry.points) for entry in match.scores],
                         [(1, 2, parent.card.vp), (1, 2, weapon.vp)])
        self.assertEqual(match.scores[0].reason, f"Unit defeat · {parent.label} · Same attack")
        self.assertEqual(match.scores[1].reason, f"RWS defeat · {weapon.name} · {parent.label}")
        revision = self.store.save(match, revision)
        self.assertEqual(self.store.load()[0].to_json(), match.to_json())
        previous, _ = self.store.undo(revision)
        self.assertEqual(previous.to_json(), before)
        self.assertFalse(self.store.can_undo())

    def test_garrison_actions_score_for_the_actor_and_move_only_its_token(self):
        self.match.set_cursor(1, 9)
        self.match.move_token(1, 1, 9)
        self.match.move_token(2, 2, 1)
        self.match.move_token(4, 1, 4)
        self.match.edit_unit(
            1, hp=3, energy=2, deployed=True, statuses=["Slow"], note="Table note",
            upgrades={"speed": 1, "strength": 2}, shield_slots=["spent", "active", "empty", "empty", "empty"],
        )
        self.match.deploy_unit(4)
        before = self.match.to_json()
        rescuer = replace(self.match.unit(1))
        attacker = replace(self.match.unit(4))
        revision = self.store.save(self.match, 0)

        self.match.record_garrison(1, 1, GARRISON_RESCUE, note="North objective")
        self.assertEqual(self.match.unit(1), replace(rescuer, phase=2, round=1, stack=1))
        self.assertEqual([token.id for token in self.match.tokens(0, 2, 1)], [2, 1])
        self.assertEqual(self.match.scores[-1].reason, f"{GARRISON_RESCUE} · {rescuer.label} · North objective")
        after_rescue = self.match.to_json()
        revision = self.store.save(self.match, revision)

        self.match.record_garrison(4, 1, GARRISON_DEFEAT, unpaid_tl=2)
        self.assertEqual(self.match.unit(4), replace(attacker, round=6))
        self.assertEqual(self.match.scores[-1].reason, f"{GARRISON_DEFEAT} · {attacker.label}")
        self.assertEqual((self.match.total(0), self.match.total(1)), (2, 2))
        self.assertEqual((self.match.phase, self.match.round), (1, 9))
        revision = self.store.save(self.match, revision)

        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.load()[0].to_json(), self.match.to_json())
        previous, revision = reopened.undo(revision)
        self.assertEqual(previous.to_json(), after_rescue)
        previous, _ = reopened.undo(revision)
        self.assertEqual(previous.to_json(), before)

    def test_garrison_action_validates_before_scoring_or_moving(self):
        self.match.deploy_unit(1)
        before = self.match.to_json()
        for unit_id, phase, reason, error in (
            (2, 1, GARRISON_RESCUE, "Reserve"),
            (1, 3, GARRISON_DEFEAT, "Scoring Phase"),
            (1, 1, "Other adjustment", "Choose Garrison"),
        ):
            with self.subTest(unit_id=unit_id, phase=phase, reason=reason):
                with self.assertRaisesRegex(ValueError, error):
                    self.match.record_garrison(unit_id, phase, reason)
                self.assertEqual(self.match.to_json(), before)

    def test_energize_adds_energy_and_advances_token_in_one_undoable_edit(self):
        self.match.set_cursor(1, 10)
        self.match.move_token(1, 1, 10)
        self.match.move_token(2, 2, 2)
        self.match.edit_unit(
            1, hp=4, energy=2, deployed=True, statuses=["Slow"], note="Table note",
            upgrades={"speed": 1, "strength": 2}, shield_slots=["spent", "active", "empty", "empty", "empty"],
        )
        before = self.match.to_json()
        unit = replace(self.match.unit(1))
        revision = self.store.save(self.match, 0)

        self.match.energize_unit(1)
        self.assertEqual(self.match.unit(1), replace(unit, energy=3, phase=2, round=2, stack=1))
        self.assertEqual([token.id for token in self.match.tokens(0, 2, 2)], [2, 1])
        self.assertEqual((self.match.phase, self.match.round, self.match.scores), (1, 10, []))
        revision = self.store.save(self.match, revision)

        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.load()[0].to_json(), self.match.to_json())
        previous, _ = reopened.undo(revision)
        self.assertEqual(previous.to_json(), before)
        self.assertFalse(reopened.can_undo())

    def test_dash_moves_only_the_token_and_can_be_undone(self):
        self.match.set_cursor(1, 9)
        self.match.move_token(1, 1, 9)
        self.match.move_token(2, 2, 1)
        self.match.edit_unit(
            1, hp=4, energy=2, deployed=True, statuses=["Slow"], note="Table note",
            upgrades={"speed": 1, "strength": 2}, shield_slots=["spent", "active", "empty", "empty", "empty"],
        )
        before = self.match.to_json()
        unit = replace(self.match.unit(1))
        revision = self.store.save(self.match, 0)

        self.match.dash_unit(1)
        self.assertEqual(self.match.unit(1), replace(unit, phase=2, round=1, stack=1))
        self.assertEqual([token.id for token in self.match.tokens(0, 2, 1)], [2, 1])
        self.assertEqual((self.match.phase, self.match.round, self.match.scores), (1, 9, []))
        revision = self.store.save(self.match, revision)

        reopened = MatchStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.load()[0].to_json(), self.match.to_json())
        previous, _ = reopened.undo(revision)
        self.assertEqual(previous.to_json(), before)
        self.assertFalse(reopened.can_undo())

    def test_timeline_actions_require_a_deployed_unit_in_an_active_match(self):
        before = self.match.to_json()
        actions = (self.match.dash_unit, self.match.energize_unit)
        for action in actions:
            with self.assertRaisesRegex(ValueError, "Reserve"):
                action(1)
            self.assertEqual(self.match.to_json(), before)
        self.match.deploy_unit(1)
        self.match.finish(0)
        before = self.match.to_json()
        for action in actions:
            with self.assertRaisesRegex(ValueError, "already complete"):
                action(1)
            self.assertEqual(self.match.to_json(), before)

    def test_manual_vp_adjustments_and_redeployment_remain_independent(self):
        revision = self.store.save(self.match, 0)
        upgrades = dict(zip(UPGRADES, (0, 1, 1, 0)))
        self.match.edit_unit(
            1, hp=8, energy=2, deployed=True, statuses=["Slow"], note="Objective", upgrades=upgrades,
        )
        revision = self.store.save(self.match, revision)
        self.match.edit_unit(1, hp=8, energy=2, deployed=False, statuses=[], note="", upgrades=upgrades)
        self.match.move_token(1, 1, 3)
        revision = self.store.save(self.match, revision)
        self.match.record_score(1, 1, 5, "Unit defeat")
        revision = self.store.save(self.match, revision)
        self.match.edit_unit(1, hp=8, energy=2, deployed=True, statuses=[], note="", upgrades=upgrades)
        revision = self.store.save(self.match, revision)
        self.match.record_score(0, 1, 2, "Garrison rescue")
        self.match.record_score(0, 1, 4, "Phase-end goal")
        self.match.record_score(0, 1, -1, "Score correction")
        revision = self.store.save(self.match, revision)

        self.assertTrue(self.match.unit(1).deployed)
        self.assertEqual((self.match.total(0), self.match.total(1)), (5, 5))
        with self.assertRaisesRegex(ValueError, "acted last"):
            self.match.finish()
        self.match.finish(1)
        revision = self.store.save(self.match, revision)
        self.assertEqual(self.store.load()[0].winner, 1)
        previous, revision = self.store.undo(revision)
        self.assertIsNone(previous.winner)
        previous, _ = self.store.undo(revision)
        self.assertEqual(previous.total(0), 0)
        self.assertTrue(previous.unit(1).deployed)
        self.assertEqual(previous.unit(1).shield_spent, 1)

    def test_undo_is_bounded_and_detects_concurrent_windows(self):
        revision = self.store.save(self.match, 0)
        for edit in range(25):
            self.match.record_score(0, 1, 1, f"Score {edit}")
            revision = self.store.save(self.match, revision)
        with self.assertRaises(SaveConflict):
            self.store.save(self.match, 1, replace=True)
        for _ in range(UNDO_LIMIT):
            previous, revision = self.store.undo(revision)
        self.assertFalse(self.store.can_undo())
        self.assertEqual(previous.total(0), 5)
        self.store.save(self.match, revision, replace=True)
        self.assertFalse(self.store.can_undo())

    def test_invalid_catalog_entries_are_rejected(self):
        directory = self.path.parent
        catalog = directory / "catalog.json"
        catalog.write_text('{"ST01-U01": {}, "ST01-U01": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_catalog(directory)
        card = {"name": "Gundam", "title": "Legendary Hero", "hp": 0, "vp": 8, "timeline": 2, "image": "card.webp"}
        catalog.write_text(json.dumps({"ST01-U01": card}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid hp"):
            load_catalog(directory)
        card["hp"] = 15
        card["mass_produced"] = "true"
        catalog.write_text(json.dumps({"ST01-U01": card}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid Mass Produced flag"):
            load_catalog(directory)
        del card["mass_produced"]
        catalog.write_text(json.dumps({"ST01-U01": card}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing its Unit Card image"):
            load_catalog(directory)


if __name__ == "__main__":
    unittest.main()
