"""Published weapon data and attack-roll adjudication."""

import json
from dataclasses import dataclass

from .catalog import ASSETS, unique_keys


MAX_DICE = 60


@dataclass(frozen=True)
class Attack:
    name: str
    timeline: int
    range: int | str
    strength: int
    bounds: tuple[float, float, float, float]


def load_attacks(catalog, directory=ASSETS):
    records = json.loads((directory / "attacks.json").read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(records, dict) or records.keys() - catalog.keys():
        raise ValueError("Attack profiles must be keyed by playable Unit Card number.")
    attacks = {}
    for number, entries in records.items():
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{number}: expected a list of printed attacks.")
        profiles = []
        for item in entries:
            try:
                name, timeline, attack_range, strength, bounds = (
                    item[key] for key in ("name", "timeline", "range", "strength", "bounds")
                )
                left, top, right, bottom = bounds
                if (not isinstance(name, str) or not name.strip()
                        or type(timeline) is not int or timeline < 0
                        or (attack_range != "SP" and (type(attack_range) is not int or attack_range < 1))
                        or type(strength) is not int or not 1 <= strength <= MAX_DICE
                        or not (0 <= left < right <= 1 and 0 <= top < bottom <= 1)):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"{number}: invalid attack profile.") from None
            profiles.append(Attack(name, timeline, attack_range, strength, tuple(bounds)))
        attacks[number] = tuple(profiles)
    return attacks


def critical_threshold(card_number):
    return 7 if card_number == "ST01-U02" else 9


def rifle_bonus(card_number, weapon_name, values, disarmed):
    if card_number == "ST01-U02" and weapon_name == "Twin Buster Rifle" and not disarmed:
        return min(4, sum(face >= critical_threshold(card_number) for face in values))
    return 0


def die_result(face, accuracy, card_number=None):
    if not 1 <= face <= 10:
        raise ValueError("Attack dice have faces 1 through 10.")
    if face >= critical_threshold(card_number):
        return "critical"
    if face != 1 and face + accuracy >= 4:
        return "hit"
    return "miss"
