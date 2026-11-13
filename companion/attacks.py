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


def die_result(face, accuracy):
    if not 1 <= face <= 10:
        raise ValueError("Attack dice have faces 1 through 10.")
    if face >= 9:
        return "critical"
    if face != 1 and face + accuracy >= 4:
        return "hit"
    return "miss"
