import unittest

from companion.attacks import die_result, load_attacks
from companion.catalog import load_catalog


class AttackRulesTests(unittest.TestCase):
    def test_natural_faces_ignore_accuracy(self):
        self.assertEqual(die_result(1, 99), "miss")
        self.assertEqual(die_result(9, -99), "critical")
        self.assertEqual(die_result(10, -99), "critical")
        self.assertEqual(die_result(8, 2), "hit")

    def test_middle_faces_use_modified_threshold(self):
        self.assertEqual(die_result(3, 1), "hit")
        self.assertEqual(die_result(4, -1), "miss")
        self.assertEqual(die_result(4, 0), "hit")
        self.assertEqual(die_result(8, -5), "miss")

    def test_current_cards_have_published_attack_profiles(self):
        catalog = load_catalog()
        attacks = load_attacks(catalog)
        self.assertEqual(attacks.keys(), catalog.keys())
        self.assertEqual([profile.strength for profile in attacks["EX02-U01"]], [3, 6])
        self.assertEqual(attacks["PA01-U02"][0].range, "SP")
        self.assertEqual(len(attacks["EX01-U02"]), 1)
