import json

from .catalog import ASSETS, unique_keys
from .storage import LOCAL_SCENARIO_PREFIX


TERRAIN = {
    "ground": "Ground Level",
    "height1": "Height 1",
    "height2": "Height 2",
}
# Exact swatches from Images/palette_pineapple-32-32x.png.
PALETTES = {
    "desert": {"ground": "#EB9C6E", "height1": "#C76E46", "height2": "#73392E"},
    "jungle": {"ground": "#9CB93B", "height1": "#458239", "height2": "#273B2D"},
    "space": {"ground": "#041528", "height1": "#293B49", "height2": "#BFC3C6"},
    "urban": {"ground": "#BFC3C6", "height1": "#6D8A8D", "height2": "#033E5E"},
    "underwater": {"ground": "#033E5E", "height1": "#1C92A7", "height2": "#77D6C1"},
}
DEFAULT_PALETTE = "desert"
LEGACY_TERRAIN = {"forest": "height1", "water": "ground"}

SPECIAL_TERRAIN = {
    "water": ("Water", "water"),
    "impassable_terrain": ("Impassable Terrain", "impassable-terrain"),
    "debris_fields": ("Debris Fields", "debris-fields"),
    "minovsky_particles": ("Minovsky Particles", "minovsky-particles"),
}
SPECIAL_TERRAIN_RULES = {
    "water": "Move actions starting in water lose 1 hex.\n"
             "Attacks lose 1 Accuracy for the attacker in water and 1 for the target in water (-2 if both).",
    "impassable_terrain": "Only units with Hover can move through these hexes. "
                          "Every unit must end its movement elsewhere.",
    "debris_fields": "Move actions starting in a debris field lose 1 hex.\n"
                     "Attacks lose 1 Accuracy for the attacker in debris and 1 for the target in debris (-2 if both).",
    "minovsky_particles": "For non-adjacent attacks, apply -2 Accuracy if either the attacker or target is inside "
                          "Minovsky Particles. Apply the penalty once when both are inside.",
}
TOKENS = {
    "red_base": ("Red base", "red-deployment-base"),
    "blue_base": ("Blue base", "blue-deployment-base"),
    "red_garrison": ("Red garrison", "red-garrison"),
    "blue_garrison": ("Blue garrison", "blue-garrison"),
    "energy": ("Energy", "energy"),
    "objective": ("Objective", "objective"),
    "special_objective": ("Special Objective", "special-objective"),
    "upgrade": ("Upgrade", "generic-upgrade"),
}
NUMBERED_TOKENS = ("objective", "special_objective")
MISSION_FIELDS = (
    ("Mission Name", "name"), ("Location", "location"),
    ("Overview", "overview"), ("Objectives", "objectives"),
)
HEX_COLUMN_LENGTHS = (14, 13) * 7 + (14,)
HEX_KEYS = tuple(
    f"{row:02}-{col:02}"
    for row in range(1, max(HEX_COLUMN_LENGTHS) + 1)
    for col, length in enumerate(HEX_COLUMN_LENGTHS, 1)
    if row <= length
)
PORTRAIT_HEX_KEYS = frozenset(
    f"{row:02}-{col:02}"
    for row, length in enumerate(HEX_COLUMN_LENGTHS, 1)
    for col in range(1, length + 1)
)
LEGACY_HEX_KEYS = PORTRAIT_HEX_KEYS | {
    f"{row:02}-14" for row in range(2, len(HEX_COLUMN_LENGTHS), 2)
}
NEW_SCENARIO = "New Scenario"
NO_SCENARIO = "No scenario"
MAX_OBJECTIVES = 4


def validate_scenario(scenario):
    if not isinstance(scenario, dict):
        raise ValueError("The file must contain one scenario object.")
    for label, field in MISSION_FIELDS:
        value = scenario.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Enter the {label.lower()}.")
    palette = scenario.get("palette")
    if not isinstance(palette, str) or palette not in PALETTES:
        raise ValueError("Choose a known Battlefield palette.")
    cells = scenario.get("cells")
    if not isinstance(cells, dict) or cells.keys() != set(HEX_KEYS):
        raise ValueError("Scenarios require 15 columns alternating between 14 and 13 hexes.")
    objective_numbers = {token: [] for token in NUMBERED_TOKENS}
    for key, cell in cells.items():
        if not isinstance(cell, dict):
            raise ValueError(f"Invalid hex {key}.")
        terrain, token = cell.get("terrain"), cell.get("token")
        if not isinstance(terrain, str) or terrain not in TERRAIN:
            raise ValueError(f"Unknown terrain at hex {key}.")
        special = cell.get("special_terrain")
        if special is not None and (not isinstance(special, str) or special not in SPECIAL_TERRAIN):
            raise ValueError(f"Unknown Special Terrain at hex {key}.")
        if token is not None and (not isinstance(token, str) or token not in TOKENS):
            raise ValueError(f"Unknown token at hex {key}.")
        if "objective_number" in cell:
            number = cell["objective_number"]
            if token not in NUMBERED_TOKENS or type(number) is not int or number < 1:
                raise ValueError(f"Invalid objective number at hex {key}.")
            objective_numbers[token].append(number)
    for token, numbers in objective_numbers.items():
        if numbers:
            count = sum(cell.get("token") == token for cell in cells.values())
            if sorted(numbers) != list(range(1, count + 1)):
                raise ValueError(f"{TOKENS[token][0]} numbers must be consecutive starting at 1.")


def set_scenario_token(cells, key, token):
    cell = cells[key]
    previous = cell.get("token")
    if previous == token:
        return False
    if token in NUMBERED_TOKENS:
        count = sum(other.get("token") == token for other in cells.values())
        if token == "objective" and count >= MAX_OBJECTIVES:
            raise ValueError(f"Up to {MAX_OBJECTIVES} objectives fit on a map. Remove one to place another.")
    if previous in NUMBERED_TOKENS:
        removed = cell.pop("objective_number")
        for other in cells.values():
            if other.get("token") == previous and other.get("objective_number", 0) > removed:
                other["objective_number"] -= 1
    if token in NUMBERED_TOKENS:
        cell["objective_number"] = count + 1
    if token is None:
        del cell["token"]
    else:
        cell["token"] = token
    return True


def read_scenario_file(path):
    return parse_scenario_export(path.read_bytes())


def parse_scenario_export(contents):
    scenario = json.loads(contents.decode("utf-8-sig"), object_pairs_hook=unique_keys)
    scenario = normalize_scenario(scenario)
    validate_scenario(scenario)
    cells = {key: {field: cell[field] for field in ("terrain", "special_terrain", "token", "objective_number")
                   if field in cell}
             for key, cell in scenario["cells"].items()}
    return {field: scenario[field] for _, field in MISSION_FIELDS} | {
        "palette": scenario["palette"], "cells": cells,
    }


def normalize_scenario(scenario):
    scenario = rotate_portrait_board(scenario)
    if not isinstance(scenario, dict):
        return scenario
    scenario = dict(scenario)
    cells = scenario.get("cells")
    has_forest = False
    if isinstance(cells, dict):
        scenario["cells"] = dict(cells)
        for key, cell in cells.items():
            terrain = cell.get("terrain") if isinstance(cell, dict) else None
            if isinstance(terrain, str) and terrain in LEGACY_TERRAIN:
                migrated = dict(cell, terrain=LEGACY_TERRAIN[terrain])
                if terrain == "water":
                    migrated.setdefault("special_terrain", "water")
                scenario["cells"][key] = migrated
                has_forest = has_forest or terrain == "forest"
        for token in NUMBERED_TOKENS:
            objectives = [key for key in HEX_KEYS
                          if isinstance(cells.get(key), dict) and cells[key].get("token") == token]
            if all("objective_number" not in cells[key] for key in objectives):
                for number, key in enumerate(objectives, 1):
                    scenario["cells"][key] = dict(scenario["cells"][key], objective_number=number)
    scenario.setdefault("palette", "jungle" if has_forest else DEFAULT_PALETTE)
    return scenario


def rotate_portrait_board(scenario):
    cells = scenario.get("cells") if isinstance(scenario, dict) else None
    if not isinstance(cells, dict) or cells.keys() not in (PORTRAIT_HEX_KEYS, LEGACY_HEX_KEYS):
        return scenario
    # Clockwise rotation turns an old row into a column counted from the right.
    rotated = {}
    for key in HEX_KEYS:
        row, col = map(int, key.split("-"))
        old_row = len(HEX_COLUMN_LENGTHS) + 1 - col
        rotated[key] = cells[f"{old_row:02}-{row:02}"]
    return dict(scenario, cells=rotated)


def write_scenario_file(path, scenario):
    from .card_display import atomic_write

    validate_scenario(scenario)
    contents = json.dumps(normalize_scenario(scenario), ensure_ascii=False, indent=2) + "\n"
    atomic_write(path, contents.encode("utf-8"))


def load_scenarios(directory=ASSETS):
    path = directory / "scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(scenarios, list):
        raise ValueError("The bundled scenario catalog must contain a list.")
    identifiers = set()
    for scenario in scenarios:
        validate_scenario(scenario)
        identifier = scenario.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("A bundled scenario is missing its identifier.")
        if identifier.casefold().startswith(LOCAL_SCENARIO_PREFIX):
            raise ValueError(f"Bundled scenario {identifier!r} uses a reserved local ID.")
        if identifier in identifiers:
            raise ValueError(f"Duplicate scenario identifier {identifier!r}.")
        identifiers.add(identifier)
    return [normalize_scenario(scenario) for scenario in scenarios]


def scenario_choices(store):
    scenarios = [(scenario, 0) for scenario in load_scenarios()]
    scenarios.extend((normalize_scenario(scenario), revision) for scenario, revision in store.load_scenarios())
    labels = []
    used = {NEW_SCENARIO, NO_SCENARIO}
    for scenario, _ in scenarios:
        name = label = scenario["name"]
        suffix = 2
        while label in used:
            label = f"{name} ({suffix})"
            suffix += 1
        used.add(label)
        labels.append(label)
    return scenarios, labels
