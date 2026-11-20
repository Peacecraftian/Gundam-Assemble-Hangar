import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from companion.catalog import load_catalog, load_remote_weapons
from companion.match import Match
from companion.storage import MatchStore, SaveConflict


class AttackResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def setUp(self):
        self.match = Match.new(['Aki', 'Ren'], '', 2,
                               [['EX02-U01', 'PA01-U02'], ['ST01-U04', 'ST01-U05']], self.catalog)
        self.match.deploy_unit(1)
        self.match.deploy_unit(3)
        self.target = self.match.unit(3)

    def shields(self, active, spent=0):
        self.target.shield_active, self.target.shield_spent = active, spent
        self.target.shield_slots = ['active'] * active + ['spent'] * spent + ['empty'] * (5-active-spent)

    def test_nonlethal_hit_damage_consumes_shields_after_modifiers(self):
        self.shields(2, 1)
        hp = self.target.hp
        attacker = replace(self.match.unit(1))
        self.assertFalse(self.match.resolve_attack(1, 3, 3, modifier=2))
        self.assertEqual(self.target.hp, hp-3)
        self.assertEqual((self.target.shield_active, self.target.shield_spent), (0, 3))
        self.assertEqual(self.target.shields, ('spent', 'spent', 'spent', 'empty', 'empty'))
        self.assertTrue(self.target.deployed)
        self.assertEqual(self.match.unit(1), attacker)
        self.assertFalse(self.match.scores)

    def test_only_shields_that_absorb_damage_become_spent(self):
        self.shields(3, 1)
        hp = self.target.hp
        self.assertFalse(self.match.resolve_attack(1, 3, 1))
        self.assertEqual(self.target.hp, hp)
        self.assertEqual((self.target.shield_active, self.target.shield_spent), (2, 2))
        self.assertEqual(self.target.shields, ('active', 'active', 'spent', 'spent', 'empty'))

    def test_misses_and_pre_shield_reduction_do_not_spend_shields(self):
        self.shields(2)
        before = self.match.to_json()
        self.assertFalse(self.match.resolve_attack(1, 3, 0))
        self.assertFalse(self.match.resolve_attack(1, 3, 2, modifier=-5))
        self.assertEqual(self.match.to_json(), before)

    def test_paid_miss_wraps_phase_and_joins_allied_stack(self):
        self.match.move_token(1, 1, 9)
        self.match.move_token(2, 2, 3)
        target_before = replace(self.target)
        self.match.resolve_attack(1, 3, 0, timeline_cost=4)
        self.assertEqual([u.id for u in self.match.tokens(0, 2, 3)], [2, 1])
        self.assertEqual(self.target, target_before)
        self.assertEqual((self.match.phase, self.match.round), (1, 1))

    def test_legacy_extra_shields_are_spent_consistently(self):
        self.target.shield_active = 7
        self.target.shield_spent = 1
        self.assertFalse(self.match.resolve_attack(1, 3, 6))
        self.assertEqual((self.target.shield_active, self.target.shield_spent), (1, 7))
        self.assertEqual(self.target.shields, ('spent',)*5)
        self.assertEqual(self.target.extra_shields, (1, 2))

    def test_lethal_damage_defeats_and_persists_as_one_undoable_edit(self):
        self.shields(1, 1)
        self.target.hp, self.target.energy = 2, 4
        self.target.strength, self.target.speed = 2, 1
        self.target.statuses = ['Disarm', 'Fracture', 'Slow']
        self.target.note = 'Objective 2'
        self.match.move_token(3, 1, 10)
        self.match.move_token(4, 2, 2)
        before = self.match.to_json()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'attack.sqlite3'
            store = MatchStore(path)
            try:
                revision = store.save(self.match, 0)
                self.assertTrue(self.match.resolve_attack(1, 3, 3, timeline_cost=4, note='Beam Rifle'))
                self.assertEqual(self.match.unit(1).round, self.catalog['EX02-U01'].timeline + 4)
                self.assertEqual((self.target.hp, self.target.deployed, self.target.statuses),
                                 (self.target.card.hp, False, []))
                self.assertEqual((self.target.energy, self.target.strength, self.target.speed, self.target.note),
                                 (4, 2, 1, 'Objective 2'))
                self.assertEqual((self.target.shield_active, self.target.shield_spent), (0, 2))
                self.assertEqual([u.id for u in self.match.tokens(1, 2, 2)], [4, 3])
                self.assertEqual((self.match.total(0), self.match.total(1)), (self.target.card.vp, 0))
                self.assertEqual(self.match.scores[-1].phase, 1)
                self.assertIn('Beam Rifle', self.match.scores[-1].reason)
                store.save(self.match, revision)
            finally:
                store.close()
            reopened = MatchStore(path)
            try:
                loaded, revision = reopened.load()
                self.assertEqual(loaded.to_json(), self.match.to_json())
                previous, _ = reopened.undo(revision)
                self.assertEqual(previous.to_json(), before)
                self.assertFalse(reopened.can_undo())
            finally:
                reopened.close()

    def test_overkill_zero_vp_and_last_phase_defeat(self):
        self.target.hp = 1
        self.target.card = replace(self.target.card, vp=0)
        self.match.phase = 2
        self.match.move_token(3, 2, 10)
        self.assertTrue(self.match.resolve_attack(1, 3, 60))
        self.assertEqual((self.target.phase, self.target.round, self.target.hp), (3, 2, self.target.card.hp))
        self.assertEqual((self.match.scores[-1].phase, self.match.scores[-1].points), (2, 0))
        before = self.match.to_json()
        with self.assertRaisesRegex(ValueError, 'Reserve'):
            self.match.resolve_attack(1, 3, 1)
        self.assertEqual(self.match.to_json(), before)

    def test_parent_defeat_returns_remote_weapons_without_awarding_their_vp(self):
        weapon = load_remote_weapons(self.catalog)['EX02-U01A']
        match = Match.new(['A', 'B'], '', 2, [['ST01-U04'], [weapon.parent]], self.catalog)
        match.deploy_unit(1)
        match.deploy_unit(2)
        target = match.unit(2)
        target.remote_weapon_hp[weapon.number] = weapon.hp
        target.hp = 1
        self.assertTrue(match.resolve_attack(1, 2, 1))
        self.assertFalse(target.remote_weapon_hp)
        self.assertEqual(match.total(0), target.card.vp)

    def test_invalid_attacks_do_not_mutate_the_match(self):
        self.shields(2)
        for attacker, target, hits, modifier in ((1, 1, 4, 0), (1, 2, 4, 0), (2, 3, 4, 0),
                                                (1, 4, 4, 0), (99, 3, 4, 0), (1, 99, 4, 0),
                                                (1, 3, -1, 0), (1, 3, 61, 0), (1, 3, 2, 'bad')):
            with self.subTest(attacker=attacker, target=target, hits=hits, modifier=modifier):
                before = self.match.to_json()
                with self.assertRaises(ValueError):
                    self.match.resolve_attack(attacker, target, hits, modifier=modifier)
                self.assertEqual(self.match.to_json(), before)
        self.match.winner = 0
        before = self.match.to_json()
        with self.assertRaisesRegex(ValueError, 'complete'):
            self.match.resolve_attack(1, 3, 4)
        self.assertEqual(self.match.to_json(), before)

    def test_attack_save_rejects_a_stale_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MatchStore(Path(directory) / 'attack.sqlite3')
            try:
                revision = store.save(self.match, 0)
                stale = Match.from_json(self.match.to_json())
                self.match.unit(3).hp -= 1
                store.save(self.match, revision)
                stale.resolve_attack(1, 3, 3)
                with self.assertRaises(SaveConflict):
                    store.save(stale, revision)
                self.assertEqual(store.load()[0].to_json(), self.match.to_json())
            finally:
                store.close()
