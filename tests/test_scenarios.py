import json
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageColor

from companion.asset_pipeline import BATTLEFIELD_ART, BATTLEFIELD_RENDER_DIR, publish_assets
from companion.card_display import display_cache_path
from companion.catalog import TACTICS_CARDS, UNIT_CARDS
from companion.scenarios import (
    HEX_KEYS, PALETTES, SPECIAL_TERRAIN, TERRAIN, load_scenarios, read_scenario_file, scenario_choices, set_scenario_token,
    write_scenario_file,
)
from companion.storage import MatchStore
from tools.bundle_scenario import bundle_scenario


class ScenarioFileTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "scenario.json"
        self.scenario = {
            "id": "local-test",
            "name": "Prise du port",
            "location": "São Tomé",
            "overview": "Approach from the south.\n\nSecure the pier.",
            "objectives": "• Hold the pier.",
            "palette": "urban",
            "cells": {key: {"terrain": "ground"} for key in HEX_KEYS},
        }
        for number, special in enumerate(SPECIAL_TERRAIN, 1):
            self.scenario["cells"][f"02-{8-number:02}"] = {
                "terrain": "height1", "special_terrain": special, "token": "objective", "objective_number": number,
            }

    def test_json_round_trip_preserves_briefing_palette_terrain_and_tokens(self):
        write_scenario_file(self.path, self.scenario)
        exported = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(exported, self.scenario)
        del exported["id"]
        self.assertEqual(read_scenario_file(self.path), exported)

    def test_rejects_incomplete_and_invalid_hex_data(self):
        for cells in (
            {},
            self.scenario["cells"] | {"01-01": {"terrain": []}},
            self.scenario["cells"] | {"01-01": {"terrain": "ground", "special_terrain": []}},
            self.scenario["cells"] | {"01-01": {"terrain": "ground", "special_terrain": "unknown"}},
            self.scenario["cells"] | {"01-01": {"terrain": "ground", "token": "unknown"}},
            self.scenario["cells"] | {"01-01": {"terrain": "ground", "objective_number": 1}},
            self.scenario["cells"] | {"02-04": {"terrain": "ground", "token": "objective", "objective_number": 1}},
            self.scenario["cells"] | {"02-04": {"terrain": "ground", "token": "objective"}},
        ):
            with self.subTest(cell_count=len(cells), first_cell=cells.get("01-01")):
                scenario = deepcopy(self.scenario)
                scenario["cells"] = cells
                self.path.write_text(json.dumps(scenario), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_scenario_file(self.path)

    def test_objective_order_closes_gaps_when_tokens_are_removed_or_replaced(self):
        keys = ("03-09", "01-01", "06-04", "04-07", "08-03")
        cells = {key: {"terrain": "height1"} for key in keys}
        for key in keys[:4]:
            self.assertTrue(set_scenario_token(cells, key, "objective"))
        self.assertEqual([cells[key]["objective_number"] for key in keys[:4]], [1, 2, 3, 4])
        self.assertFalse(set_scenario_token(cells, keys[0], "objective"))
        before = deepcopy(cells)
        with self.assertRaisesRegex(ValueError, "Up to 4 objectives"):
            set_scenario_token(cells, keys[4], "objective")
        self.assertEqual(cells, before)
        set_scenario_token(cells, keys[1], None)
        set_scenario_token(cells, keys[2], "energy")
        set_scenario_token(cells, keys[4], "objective")
        self.assertEqual(cells[keys[1]], {"terrain": "height1"})
        self.assertEqual(cells[keys[2]], {"terrain": "height1", "token": "energy"})
        self.assertEqual([cells[key]["objective_number"] for key in (keys[0], keys[3], keys[4])], [1, 2, 3])

    def test_special_objectives_round_trip_without_using_regular_objective_slots(self):
        cells = self.scenario["cells"]
        self.assertTrue(set_scenario_token(cells, "01-01", "special_objective"))
        self.assertEqual(cells["01-01"]["objective_number"], 1)
        write_scenario_file(self.path, self.scenario)
        self.assertEqual(read_scenario_file(self.path)["cells"], cells)
        self.assertTrue(set_scenario_token(cells, "02-04", "special_objective"))
        self.assertEqual(cells["02-04"]["objective_number"], 2)
        self.assertEqual([cells[key]["objective_number"] for key in ("02-07", "02-06", "02-05")], [1, 2, 3])
        write_scenario_file(self.path, self.scenario)
        self.assertEqual(read_scenario_file(self.path)["cells"], cells)

    def test_special_numbering_closes_gaps_on_removal_and_replacement_then_restarts(self):
        cells = self.scenario["cells"]
        keys = ("03-09", "01-01", "06-04", "04-07", "08-03")
        regular = {key: deepcopy(cell) for key, cell in cells.items() if cell.get("token") == "objective"}
        for key in keys:
            self.assertTrue(set_scenario_token(cells, key, "special_objective"))
        self.assertEqual([cells[key]["objective_number"] for key in keys], [1, 2, 3, 4, 5])
        self.assertFalse(set_scenario_token(cells, keys[0], "special_objective"))
        set_scenario_token(cells, keys[1], None)
        set_scenario_token(cells, keys[2], "energy")
        self.assertEqual([cells[key]["objective_number"] for key in (keys[0], keys[3], keys[4])], [1, 2, 3])
        self.assertNotIn("objective_number", cells[keys[1]])
        self.assertNotIn("objective_number", cells[keys[2]])
        set_scenario_token(cells, keys[1], "special_objective")
        self.assertEqual(cells[keys[1]]["objective_number"], 4)
        self.assertEqual({key: cells[key] for key in regular}, regular)
        for key in (keys[0], keys[1], keys[3], keys[4]):
            set_scenario_token(cells, key, None)
        set_scenario_token(cells, keys[2], "special_objective")
        self.assertEqual(cells[keys[2]]["objective_number"], 1)

    def test_switching_objective_types_updates_both_sequences_and_failed_placement_is_atomic(self):
        cells = self.scenario["cells"]
        set_scenario_token(cells, "01-01", "special_objective")
        set_scenario_token(cells, "01-02", "special_objective")
        before = deepcopy(cells)
        with self.assertRaisesRegex(ValueError, "Up to 4 objectives"):
            set_scenario_token(cells, "01-01", "objective")
        self.assertEqual(cells, before)
        set_scenario_token(cells, "02-04", "special_objective")
        self.assertEqual(cells["02-04"]["objective_number"], 3)
        self.assertEqual([cells[key]["objective_number"] for key in ("02-07", "02-06", "02-05")], [1, 2, 3])
        set_scenario_token(cells, "01-01", "objective")
        self.assertEqual(cells["01-01"]["objective_number"], 4)
        self.assertEqual([cells[key]["objective_number"] for key in ("01-02", "02-04")], [1, 2])
        write_scenario_file(self.path, self.scenario)
        self.assertEqual(read_scenario_file(self.path)["cells"], cells)

    def test_legacy_special_objectives_get_numbers_without_rewriting_saved_payloads(self):
        cells = self.scenario["cells"]
        for key in ("05-09", "01-02", "03-05"):
            cells[key]["token"] = "special_objective"
        self.path.write_text(json.dumps(self.scenario), encoding="utf-8")
        original = self.path.read_bytes()
        imported = read_scenario_file(self.path)
        self.assertEqual([imported["cells"][key]["objective_number"] for key in ("01-02", "03-05", "05-09")], [1, 2, 3])
        self.assertEqual(self.path.read_bytes(), original)
        store = MatchStore(self.path.with_suffix(".sqlite3"))
        self.addCleanup(store.close)
        store.save_scenario(self.scenario, 0)
        choices, _ = scenario_choices(store)
        self.assertEqual(choices[-1][0]["cells"], imported["cells"])
        self.assertEqual(store.load_scenarios(), [(self.scenario, 1)])

    def test_rejects_invalid_or_partial_special_objective_numbers(self):
        for number in (0, -1, True, "1", 1.5, 2, 3, None):
            with self.subTest(number=number):
                scenario = deepcopy(self.scenario)
                scenario["cells"]["01-01"].update(token="special_objective", objective_number=1)
                scenario["cells"]["01-02"].update(token="special_objective", objective_number=2)
                if number is None:
                    del scenario["cells"]["01-01"]["objective_number"]
                else:
                    scenario["cells"]["01-01"]["objective_number"] = number
                self.path.write_text(json.dumps(scenario), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_scenario_file(self.path)

    def test_legacy_maps_keep_all_unnumbered_objectives_in_board_order(self):
        cells = self.scenario["cells"]
        for cell in cells.values():
            cell.pop("objective_number", None)
        cells["01-01"]["token"] = "objective"
        self.path.write_text(json.dumps(self.scenario), encoding="utf-8")
        numbered = read_scenario_file(self.path)["cells"]
        keys = ("01-01", "02-04", "02-05", "02-06", "02-07")
        self.assertEqual([numbered[key]["objective_number"] for key in keys], [1, 2, 3, 4, 5])

    def test_rejects_invalid_palette_metadata(self):
        for palette in ("arctic", [], None):
            with self.subTest(palette=palette):
                self.path.write_text(json.dumps(dict(self.scenario, palette=palette)), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Battlefield palette"):
                    read_scenario_file(self.path)

    def test_elevation_palettes_use_pineapple_swatches_with_distinct_elevations(self):
        source = Path(__file__).resolve().parents[1] / "Images" / "palette_pineapple-32-32x.png"
        with Image.open(source) as image:
            swatches = {color for _, color in image.convert("RGB").getcolors()}
        for palette, colors in PALETTES.items():
            with self.subTest(palette=palette):
                self.assertEqual(colors.keys(), TERRAIN.keys())
                self.assertTrue({ImageColor.getrgb(color) for color in colors.values()} <= swatches)
                ground, height1, height2 = (ImageColor.getcolor(colors[key], "L") for key in TERRAIN)
                if palette in ("space", "underwater"):
                    self.assertLess(ground, height1)
                    self.assertLess(height1, height2)
                else:
                    self.assertGreater(ground, height1)
                    self.assertGreater(height1, height2)

    def test_portrait_grids_rotate_on_import_and_load_without_rewriting_local_saves(self):
        cells = {f"{row:02}-{col:02}": {"terrain": "ground"}
                 for row in range(1, 16) for col in range(1, 15 if row % 2 else 14)}
        cells["01-01"] = {"terrain": "forest", "token": "red_base"}
        cells["02-04"] = {"terrain": "water", "token": "objective"}
        cells["15-14"] = {"terrain": "height2", "token": "blue_base"}
        extra = {f"{row:02}-14": {"terrain": "height1", "token": "energy"} for row in range(2, 15, 2)}
        expected = {key: {"terrain": "ground"} for key in HEX_KEYS}
        expected["01-15"] = {"terrain": "height1", "token": "red_base"}
        expected["04-14"] = {
            "terrain": "ground", "special_terrain": "water", "token": "objective", "objective_number": 1,
        }
        expected["14-01"] = cells["15-14"]
        store = MatchStore(self.path.with_suffix(".sqlite3"))
        self.addCleanup(store.close)
        originals = []
        for portrait in (cells, cells | extra):
            with self.subTest(cell_count=len(portrait)):
                scenario = dict(self.scenario, id=f"local-{len(portrait)}", cells=portrait)
                del scenario["palette"]
                self.path.write_text(json.dumps(scenario), encoding="utf-8")
                imported = read_scenario_file(self.path)
                self.assertEqual(imported["palette"], "jungle")
                self.assertEqual(imported["cells"], expected)
                store.save_scenario(scenario, 0)
                originals.append((scenario, 1))
                choices, _ = scenario_choices(store)
                self.assertEqual(choices[-1], (dict(scenario, palette="jungle", cells=expected), 1))
                self.assertEqual(store.load_scenarios(), originals)

    def test_bundled_board_rotates_archived_leviathan_layout(self):
        scenario = next(entry for entry in load_scenarios() if entry["id"] == "concept-sleeping-leviathan")
        cells = scenario["cells"]
        lengths = Counter(key[3:] for key in cells)
        self.assertEqual([lengths[f"{col:02}"] for col in range(1, 16)], [14, 13] * 7 + [14])
        self.assertEqual(cells["01-08"]["token"], "red_base")
        self.assertEqual(cells["13-08"]["token"], "blue_base")
        source = Path(__file__).resolve().parents[1] / scenario["source"]
        archived = read_scenario_file(source)
        for number, key in enumerate(("09-09", "06-07", "07-02", "07-14"), 1):
            archived["cells"][key]["objective_number"] = number
        self.assertEqual(cells, archived["cells"])
        self.assertEqual(scenario["palette"], "desert")
        self.assertEqual(archived["palette"], "desert")

    def test_promotes_export_with_provenance_and_publishes_only_the_catalog(self):
        root = self.path.parent
        catalog = root / "scenarios.json"
        catalog.write_text("[]", encoding="utf-8")
        write_scenario_file(self.path, self.scenario)
        bundled = bundle_scenario(root, self.path, "GA-001", "1.0")
        self.assertEqual(load_scenarios(root), [bundled])
        self.assertEqual(bundled["id"], "GA-001")
        self.assertEqual(bundled["revision"], "1.0")
        self.assertEqual(bundled["palette"], "urban")
        self.assertEqual(bundled["cells"], self.scenario["cells"])
        self.assertEqual((root / bundled["source"]).read_bytes(), self.path.read_bytes())
        with self.assertRaisesRegex(ValueError, "already bundled"):
            bundle_scenario(root, self.path, "ga-001", "1.1")
        with self.assertRaisesRegex(ValueError, "reserved"):
            bundle_scenario(root, self.path, "local-new", "1.0")
        self.assertEqual(load_scenarios(root), [bundled])

        for name in ("catalog.json", "remote_weapons.json", "tactics.json"):
            (root / name).write_text("{}", encoding="utf-8")
        for folder in (UNIT_CARDS, TACTICS_CARDS):
            cache = display_cache_path(root, folder)
            cache.mkdir(parents=True)
            (cache / "sources.json").write_text("{}", encoding="utf-8")
        render_cache = root / BATTLEFIELD_RENDER_DIR
        render_cache.mkdir(parents=True)
        (root / "Tokens").mkdir()
        for name, size in BATTLEFIELD_ART.items():
            (root / "Tokens" / f"{name}.svg").write_text("<svg/>", encoding="utf-8")
            Image.new("RGBA", size).save(render_cache / f"{name}.png")
        with (patch("companion.asset_pipeline.STATIC_FILES", ("scenarios.json",)),
              patch("companion.asset_pipeline.DICE_FILES", {})):
            published = publish_assets(root, [], battlefield_art=True)
        self.assertEqual(load_scenarios(published), [bundled])
        self.assertFalse((published / bundled["source"]).exists())
        self.assertEqual(
            {path.name for path in (published / "Tokens").rglob("*") if path.is_file()},
            {f"{name}.png" for name in BATTLEFIELD_ART},
        )
