import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageOps

from companion.artwork import fitted_card, hangar_card
from companion.card_display import build_display_cache, load_display_image, read_manifest
from companion.catalog import TACTICS_CARDS, UNIT_CARDS, load_card_image, load_catalog, load_remote_weapons, load_tactics
from companion.tactics_art import tactics_fan_card


class CardArtworkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for folder in (UNIT_CARDS, TACTICS_CARDS):
            (self.root / folder / "PNG").mkdir(parents=True)

    def test_both_card_sets_prefer_png_and_fall_back_to_readable_webp(self):
        for folder, number, filename in (
            (UNIT_CARDS, "ST01-U01", "img_card_front_st01-u01_en.webp"),
            (TACTICS_CARDS, "ST01-T01", "img_card_st01-t01_en.webp"),
        ):
            with self.subTest(folder=folder):
                primary = self.root / folder / "PNG" / f"{number}.png"
                original = self.root / folder / filename
                Image.new("RGB", (8, 8), "red").save(primary)
                Image.new("RGB", (8, 8), "blue").save(original, lossless=True)

                def pixel():
                    image = load_card_image(filename, self.root, folder=folder, size=(4, 4))
                    return image.getpixel((0, 0))

                self.assertEqual(pixel(), (255, 0, 0))
                primary.write_bytes(b"corrupt PNG")
                self.assertEqual(pixel(), (0, 0, 255))
                primary.unlink()
                self.assertEqual(pixel(), (0, 0, 255))

    def test_tactics_catalog_includes_png_only_and_webp_only_cards(self):
        directory = self.root / TACTICS_CARDS
        Image.new("RGB", (4, 6)).save(directory / "PNG" / "ST01-T02.png")
        Image.new("RGB", (4, 6)).save(directory / "img_card_st01-t03_en.webp")
        (self.root / "tactics.json").write_text(json.dumps({"ST01-T02": "Sacrificial Overload"}), encoding="utf-8")
        tactics = load_tactics(self.root)
        self.assertEqual(list(tactics), ["ST01-T02", "ST01-T03"])
        self.assertEqual(tactics["ST01-T02"].name, "Sacrificial Overload")
        self.assertEqual(tactics["ST01-T03"].image, "img_card_st01-t03_en.webp")

    def test_tactics_display_copy_is_used_only_for_matching_png(self):
        folder = self.root / TACTICS_CARDS
        cache = self.root / "display"
        filename = "img_card_st01-t01_en.webp"
        png = folder / "PNG" / "ST01-T01.png"
        Image.new("RGB", (746, 1044), "red").save(png)
        Image.new("RGB", (8, 8), "blue").save(folder / filename, lossless=True)
        self.assertEqual(build_display_cache(load_tactics(self.root).values(), self.root,
                                             folder=TACTICS_CARDS, cache=cache), 1)

        with patch("companion.card_display.load_card_image", side_effect=AssertionError("unexpected source decode")):
            fan = load_display_image(filename, "fan", self.root, folder=TACTICS_CARDS, cache=cache)
            self.assertEqual(fan.height, 320)
            self.assertEqual(fan.getpixel((0, 0)), (255, 0, 0, 255))

        Image.new("RGB", (8, 8), "green").save(png)
        self.assertEqual(load_display_image(filename, "preview", self.root, folder=TACTICS_CARDS, cache=cache)
                         .getpixel((0, 0)), (0, 128, 0, 255))
        png.write_bytes(b"unreadable PNG")
        self.assertEqual(load_display_image(filename, "fan", self.root, folder=TACTICS_CARDS, cache=cache)
                         .getpixel((0, 0)), (0, 0, 255, 255))

    def test_unit_display_caches_portrait_and_preview_and_preserves_webp_fallback(self):
        folder = self.root / UNIT_CARDS
        filename = "img_card_front_st01-u01_en.webp"
        png = folder / "PNG" / "ST01-U01.png"
        image = Image.new("RGB", (800, 567), "red")
        image.paste("green", (400, 0, 752, 119))
        image.save(png)
        Image.new("RGB", (800, 567), "blue").save(folder / filename, lossless=True)
        (self.root / "catalog.json").write_text(json.dumps({
            "ST01-U01": {"name": "Gundam", "title": "Legendary Hero", "hp": 15,
                         "vp": 8, "timeline": 2, "image": filename},
        }), encoding="utf-8")
        self.assertEqual(build_display_cache(load_catalog(self.root).values(), self.root, folder=UNIT_CARDS), 1)

        with patch("companion.card_display.load_card_image", side_effect=AssertionError("unexpected source decode")):
            portrait = load_display_image(filename, "portrait", self.root, folder=UNIT_CARDS)
            preview = load_display_image(filename, "preview", self.root, folder=UNIT_CARDS)
            self.assertEqual((portrait.size, portrait.getpixel((0, 0))), ((272, 119), (0, 128, 0)))
            self.assertEqual((preview.size, preview.getpixel((0, 0))), ((800, 567), (255, 0, 0, 255)))

        png.write_bytes(b"unreadable PNG")
        self.assertEqual(load_display_image(filename, "portrait", self.root, folder=UNIT_CARDS).getpixel((0, 0)),
                         (0, 0, 255))
        self.assertEqual(load_display_image(filename, "preview", self.root, folder=UNIT_CARDS).getpixel((0, 0)),
                         (0, 0, 255, 255))

    def test_unit_catalog_accepts_png_only_without_changing_the_saved_filename(self):
        filename = "img_card_front_st01-u01_en.webp"
        Image.new("RGB", (8, 6)).save(self.root / UNIT_CARDS / "PNG" / "ST01-U01.png")
        (self.root / "catalog.json").write_text(json.dumps({
            "ST01-U01": {"name": "Gundam", "title": "Legendary Hero", "hp": 15,
                         "vp": 8, "timeline": 2, "image": filename},
        }), encoding="utf-8")
        self.assertEqual(load_catalog(self.root, verify_images=True)["ST01-U01"].image, filename)

    def test_guncannon_face_stays_centered_in_cached_and_fallback_trackers(self):
        filename = "img_card_front_pa01-u02_en.webp"
        image = Image.new("RGB", (1000, 709), "black")
        image.paste("white", (625, 35, 675, 110))  # Face is left of the old generic crop center.
        image.save(self.root / UNIT_CARDS / filename, lossless=True)
        (self.root / "catalog.json").write_text(json.dumps({
            "PA01-U02": {"name": "Guncannon", "title": "In Position", "hp": 12,
                         "vp": 7, "timeline": 2, "image": filename},
        }), encoding="utf-8")
        cache = self.root / "display-test"
        for cached in (False, True):
            if cached:
                build_display_cache(load_catalog(self.root).values(), self.root, folder=UNIT_CARDS, cache=cache)
            portrait = load_display_image(filename, "portrait", self.root, folder=UNIT_CARDS, cache=cache)
            for size in ((58, 68), (92, 64), (70, 36)):
                with self.subTest(cached=cached, size=size):
                    tracker = ImageOps.fit(portrait, size, centering=(.5, .42))
                    self.assertEqual(tracker.getpixel((size[0]//2, size[1]//2)), (255, 255, 255))

    def test_remote_weapon_uses_a_suffix_keyed_preview_with_webp_fallback(self):
        folder = self.root / UNIT_CARDS
        filename = "img_card_ex02-u01a_en.webp"
        png = folder / "PNG" / "EX02-U01A.png"
        Image.new("RGBA", (793, 567), "red").save(png)
        Image.new("RGB", (793, 567), "blue").save(folder / filename, lossless=True)
        (self.root / "remote_weapons.json").write_text(json.dumps({
            "EX02-U01A": {"name": "BIT Stave", "image": filename, "parent": "EX02-U01",
                          "icon_bounds": [0.825, 0.231, 0.924, 0.312], "hp": 1, "vp": 2},
        }), encoding="utf-8")
        weapons = load_remote_weapons({"EX02-U01": object()}, self.root, verify_images=True)
        self.assertEqual(weapons["EX02-U01A"].parent, "EX02-U01")
        self.assertEqual(build_display_cache(weapons.values(), self.root, folder=UNIT_CARDS, preview_only=weapons), 1)
        self.assertEqual([*read_manifest(self.root / ".build/unit-display")["EX02-U01A"]["variants"]],
                         ["preview"])
        with patch("companion.card_display.load_card_image", side_effect=AssertionError("unexpected source decode")):
            preview = load_display_image(filename, "preview", self.root, folder=UNIT_CARDS)
            self.assertEqual((preview.size, preview.getpixel((0, 0))), ((793, 567), (255, 0, 0, 255)))

        png.write_bytes(b"unreadable PNG")
        preview = load_display_image(filename, "preview", self.root, folder=UNIT_CARDS)
        self.assertEqual(preview.getpixel((0, 0)), (0, 0, 255, 255))

    def test_tactics_fan_stroke_is_three_display_pixels_with_transparent_corners(self):
        art = Image.new("RGBA", (48, 72), "navy")
        art.putpixel((0, 0), (0, 0, 0, 0))
        with patch("companion.tactics_art.fan_art", return_value=art):
            for size in ((48, 72), (24, 36)):
                with self.subTest(size=size):
                    card = tactics_fan_card("card.webp", size, 0)
                    self.assertEqual(card.size, size)
                    for x in range(3):
                        self.assertEqual(card.getpixel((x, size[1] // 2)), (248, 246, 239, 255))
                    self.assertEqual(card.getpixel((3, size[1] // 2)), (0, 0, 128, 255))
                    if size == art.size:
                        self.assertEqual(card.getpixel((0, 0))[3], 0)

    def test_only_full_unit_preview_keeps_the_edge(self):
        stock = (248, 246, 239, 255)
        art = Image.new("RGBA", (800, 567))
        ImageDraw.Draw(art).rounded_rectangle((0, 0, 799, 566), radius=13, fill="navy", outline=stock)
        with patch("companion.artwork.unit_preview_art", return_value=art):
            preview = fitted_card("card.webp", art.size)
            self.assertEqual(preview.getpixel((0, 0))[3], 0)
            self.assertEqual(preview.getpixel((400, 564)), stock)
            self.assertEqual(preview.getpixel((400, 563)), (0, 0, 128, 255))
            for reserve in (False, True):
                with self.subTest(reserve=reserve):
                    hangar = hangar_card("card.webp", 375, 266, 83, reserve=reserve)
                    self.assertEqual(hangar.size, (375, 83))
                    self.assertEqual(hangar.mode, "RGB")
                    self.assertEqual(hangar.getcolors(maxcolors=2), [(375 * 83, hangar.getpixel((187, 41)))])
