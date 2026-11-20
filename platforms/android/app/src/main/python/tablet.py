import json
from pathlib import Path
from uuid import uuid4

from companion.battlefield_stars import SPACE_STARS
from companion.scenarios import (HEX_COLUMN_LENGTHS, HEX_KEYS, MISSION_FIELDS, PALETTES, SPECIAL_TERRAIN,
                                 TERRAIN, TOKENS, SPECIAL_TERRAIN_RULES, parse_scenario_export)
from companion.attacks import critical_threshold, die_result, load_attacks, rifle_bonus
from companion.catalog import Card, RemoteWeapon
from companion.match import GARRISON_DEFEAT, GARRISON_RESCUE, Match, combat_damage, cycle_upgrade, toggle_condition
from companion.storage import MatchStore


class Session:
    def __init__(self, directory):
        directory = Path(directory)
        self.store = MatchStore(directory / "prototype.sqlite3")
        self.match, self.revision = self.store.load()
        records = json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
        self.catalog = {number: Card(number, **fields) for number, fields in records.items()}
        self.profiles = load_attacks(self.catalog, directory)
        records = json.loads((directory / "remote_weapons.json").read_text(encoding="utf-8"))
        self.weapons = {number: RemoteWeapon(number, **fields) for number, fields in records.items()}
        official = json.loads((directory / "scenarios.json").read_text(encoding="utf-8"))
        self.official = {s["id"]: s for s in official}
        self._refresh_boards()

    def _refresh_boards(self):
        custom = self.store.load_scenarios()
        self.boards = self.official.copy()
        self.boards.update({s["id"]: s for s, _ in custom})
        self.board_revisions = {s["id"]: rev for s, rev in custom}
        self.scenarios = {}
        used = {"New Scenario", "No scenario"}
        for key, s in self.boards.items():
            label, suffix = s["name"], 2
            while label in used:
                label = f"{s['name']} ({suffix})"
                suffix += 1
            self.scenarios[key] = label
            used.add(label)

    def battlefield(self, identifier=None):
        if identifier is None:
            identifier = self.match.scenario_id if self.match else next(iter(self.official), None)
        scenario = self.boards.get(identifier)
        if identifier == "new":
            scenario = {key: "" for _, key in MISSION_FIELDS}
            scenario.update(palette="desert", cells={k: {"terrain": "ground"} for k in HEX_KEYS})
        if scenario is None:
            return json.dumps({"message": "The selected scenario is unavailable." if identifier else
                               "This match was started without a scenario."})
        return json.dumps(dict(scenario=scenario, players=self.match.players if self.match else ["Blue","Red"],
                               fields=MISSION_FIELDS, columns=HEX_COLUMN_LENGTHS,
                               colors=PALETTES[scenario["palette"]], palettes=PALETTES, terrain=TERRAIN,
                               special=SPECIAL_TERRAIN, tokens=TOKENS, stars=dict(SPACE_STARS),
                               rules=SPECIAL_TERRAIN_RULES, revision=self.board_revisions.get(identifier, 0)))

    def save_board(self, text, identifier="", revision=0):
        scenario = parse_scenario_export(text.encode("utf-8"))
        if not identifier or identifier in self.official or identifier == "new":
            identifier = "local-" + uuid4().hex
            revision = 0
        scenario["id"] = identifier
        self.store.save_scenario(scenario, revision)
        self._refresh_boards()
        return identifier

    def delete_board(self, identifier, revision):
        self.store.delete_scenario(identifier, revision)
        self._refresh_boards()

    def start(self, blue, red, phases, scenario_id, squads_json):
        name = self.boards[scenario_id]["name"] if scenario_id else ""
        match = Match.new([blue, red], name, phases, json.loads(squads_json),
                          self.catalog, scenario_id=scenario_id or None)
        self.revision = self.store.save(match, self.revision, replace=True)
        self.match = match

    def change(self, unit_id, counter, delta):
        self._save_action(Match.adjust_unit_counter, unit_id, counter, delta)

    def move(self, unit_id, round_number):
        unit = self.match.unit(unit_id)
        self._save_action(Match.move_token, unit_id, unit.phase, round_number)

    def deploy(self, unit_id):
        self._save_action(Match.deploy_unit, unit_id)

    def blocked_deployment(self, unit_id):
        self._save_action(Match.blocked_deployment, unit_id)

    def energize(self, unit_id):
        self._save_action(Match.energize_unit, unit_id)

    def dash(self, unit_id):
        self._save_action(Match.dash_unit, unit_id)

    def garrison_defeat(self, unit_id, unpaid_tl=0):
        self._save_action(Match.record_garrison, unit_id, self.match.phase, GARRISON_DEFEAT, unpaid_tl=unpaid_tl)

    def garrison_rescue(self, unit_id):
        self._save_action(Match.record_garrison, unit_id, self.match.phase, GARRISON_RESCUE)

    def systems(self, unit_id):
        return [w for w in self.weapons.values() if w.parent == self.unit(unit_id).card.number]

    def deploy_system(self, unit_id, number):
        self._save_action(Match.deploy_remote_weapon, unit_id, self.weapons[number])

    def system_hp(self, unit_id, number, delta):
        self._save_action(Match.adjust_remote_weapon_hp, unit_id, self.weapons[number], delta)

    def defeat_system(self, unit_id, number):
        self._save_action(Match.defeat_remote_weapon, unit_id, self.weapons[number], self.match.phase)

    def unit_defeat(self, unit_id, systems_json="[]"):
        weapons = [self.weapons[number] for number in json.loads(systems_json)]
        self._save_action(Match.defeat_unit, unit_id, self.match.phase, defeated_weapons=weapons)

    def attacks(self, unit_id):
        return self.profiles.get(self.unit(unit_id).card.number, ())

    def disarm(self, unit_id):
        self._save_action(Match.consume_disarm, unit_id)

    @staticmethod
    def attack_hits(values_json, accuracy, card_number=None):
        values = json.loads(values_json)
        if not isinstance(values, list) or len(values) > 60:
            raise ValueError("Invalid dice pool.")
        return sum(die_result(n, accuracy, card_number) != "miss" for n in values)

    def damage_preview(self, target, hits, modifier, bonus=0):
        unit = self.match.attack_target(target)
        damage = combat_damage(hits, modifier, unit.shield_active, "Fracture" in unit.statuses, bonus)
        return json.dumps(dict(fracture=damage.fracture_bonus, shields=damage.blocked,
                               hp_loss=damage.damage, remaining=max(0, unit.hp - damage.damage),
                               defeat=damage.damage > 0 and damage.damage >= unit.hp))

    def pending(self):
        p = self.match.pending_attack
        if not p:
            return ""
        card = self.unit(p["attacker"]).card.number
        return json.dumps(dict(p, threshold=critical_threshold(card)))

    def declare(self, attacker, target, name, count, accuracy):
        self._save_action(Match.declare_attack, attacker, target, self.weapon(attacker, name), count, accuracy)

    def settle_roll(self, values_json, accuracy, mandatory):
        self._save_action(Match.save_attack_roll, json.loads(values_json), accuracy, resolve_disarm=mandatory)

    def roll_bonus(self, attacker, name, values_json):
        p = self.match.pending_attack
        return rifle_bonus(self.unit(attacker).card.number, name, json.loads(values_json),
                           p["disarmed"] if p else "Disarm" in self.unit(attacker).statuses)

    def weapon(self, attacker, name):
        weapon = next((w for w in self.attacks(attacker) if w.name == name), None)
        if weapon is None:
            raise ValueError("Choose a weapon on the attacking unit's card.")
        return weapon

    def finish_attack(self, attacker, target, values_json, accuracy, modifier, name):
        p = self.match.pending_attack
        if not p or (p["attacker"], p["target"], p["weapon"], p["values"]) != (
                attacker, target, name, json.loads(values_json)):
            raise ValueError("Reopen the declared attack to apply its saved roll.")
        if p["finalized"] and accuracy != p["accuracy"]:
            raise ValueError("Accuracy is locked after Disarm.")
        self.attack(attacker, target, values_json, accuracy, modifier, name)

    def attack(self, attacker, target, values_json, accuracy, modifier, name):
        weapon = self.weapon(attacker, name)
        hits = self.attack_hits(values_json, accuracy, self.unit(attacker).card.number)
        self._save_action(Match.resolve_attack, attacker, target, hits, timeline_cost=weapon.timeline,
                          modifier=modifier, note=name, weapon_bonus=self.roll_bonus(attacker, name, values_json))

    def score(self, player, phase, points, reason):
        self._save_action(Match.record_score, player, phase, points, reason)

    def cursor(self, phase, round_number):
        self._save_action(Match.set_cursor, phase, round_number)

    def finish(self, last_to_act):
        self._save_action(Match.finish, last_to_act)

    def upgrade(self, unit_id, key):
        self._save_action(cycle_upgrade, unit_id, key)

    def condition(self, unit_id, key):
        self._save_action(toggle_condition, unit_id, key)

    def service(self, unit_id, fields_json):
        fields = json.loads(fields_json)
        timeline = fields.pop("timeline", None)
        systems = [self.weapons[number] for number in fields.pop("launch_systems", [])]

        def apply(match):
            match.edit_unit(unit_id, **fields)
            for system in systems:
                match.deploy_remote_weapon(unit_id, system)
            if timeline is not None:
                phase, round_number, position = timeline
                unit = match.unit(unit_id)
                current = match.tokens(unit.player, unit.phase, unit.round).index(unit) + 1
                if (phase, round_number, position) != (unit.phase, unit.round, current):
                    match.move_token(unit_id, phase, round_number, position)

        self._save_action(apply)

    def schedule(self, unit_id, phase, round_number, position):
        self._save_action(Match.move_token, unit_id, phase, round_number, position)

    def _save_action(self, action, *args, **kwargs):
        if self.match.winner is not None:
            raise ValueError("This match is complete.")
        before = self.match.to_json()
        candidate = Match.from_json(before)
        action(candidate, *args, **kwargs)
        if candidate.to_json() == before:
            return
        self.revision = self.store.save(candidate, self.revision)
        self.match = candidate

    def undo(self):
        self.match, self.revision = self.store.undo(self.revision)

    def unit(self, unit_id):
        return self.match.unit(unit_id)

    def close(self):
        self.store.close()
