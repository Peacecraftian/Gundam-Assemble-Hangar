import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from companion import card_display
from companion.artwork import sortie_art
from companion.asset_pipeline import (DICE_FILES, discover_cards, needed_renders, prepare_assets, publish_assets,
                                     render_fingerprint)
from companion.card_display import build_display_cache, load_display_image, read_manifest, source_digest, write_manifest
from companion.catalog import TACTICS_CARDS, UNIT_CARDS, TacticCard, load_catalog, load_tactics


class AssetPipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for folder in (UNIT_CARDS, TACTICS_CARDS):
            (self.root / 'authoring/cards' / folder / 'SVG').mkdir(parents=True)
        for name in ('catalog.json', 'remote_weapons.json', 'tactics.json'):
            (self.root / name).write_text('{}')
        for filename in DICE_FILES.values():
            path = self.root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test dice dependency')
        self.original = self.root / 'authoring/cards/Tactics Cards/img_card_st01-t01_en.webp'
        Image.new('RGB', (746, 1044), 'red').save(self.original, lossless=True)
        self.master = self.original.parent / 'SVG/ST01-T01.svg'
        self.master.write_text('<svg/>')
        (self.root / 'tactics.json').write_text('{"ST01-T01":"Test tactic"}')
        self.card = TacticCard('ST01-T01', 'Test tactic', self.original.name)
        self.cache = self.root / '.build/tactics-display'

    def build(self, cards=None):
        return build_display_cache(cards if cards is not None else [self.card], self.root, folder=TACTICS_CARDS)

    def derivative(self, variant='fan'):
        record = read_manifest(self.cache)['ST01-T01']['variants'][variant]
        return self.cache / record['file']

    def pixel(self):
        return load_display_image(self.card.image, 'fan', self.root, folder=TACTICS_CARDS).getpixel((5, 5))

    def test_webp_only_cards_cache_and_repeat_without_rewriting(self):
        self.assertEqual(self.build(), 1)
        path = self.derivative()
        before = path.stat().st_mtime_ns
        manifest_before = (self.cache / 'sources.json').stat().st_mtime_ns
        self.assertEqual(self.pixel(), (255, 0, 0, 255))
        self.build()
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual((self.cache / 'sources.json').stat().st_mtime_ns, manifest_before)

    def test_size_and_recipe_changes_regenerate_and_prune_old_derivatives(self):
        self.build()
        old = self.derivative()
        with patch.dict(card_display.DISPLAY_SIZES[TACTICS_CARDS], fan=(116, 160)):
            self.build()
            with Image.open(self.derivative()) as image:
                self.assertEqual(image.height, 160)
            self.assertFalse(old.exists())
        old = self.derivative()
        with patch.object(card_display, 'RENDER_VERSION', 999):
            self.build()
            self.assertNotEqual(self.derivative(), old)
            self.assertFalse(old.exists())

    def test_changed_source_and_manifest_are_detected_in_same_process(self):
        self.build()
        self.assertEqual(self.pixel(), (255, 0, 0, 255))
        Image.new('RGB', (746, 1044), 'blue').save(self.original, lossless=True)
        self.assertEqual(self.pixel(), (0, 0, 255, 255))
        self.build()
        self.assertEqual(self.pixel(), (0, 0, 255, 255))

    def test_corrupt_derivative_is_rejected_and_rebuilt(self):
        self.build()
        path = self.derivative()
        path.write_bytes(b'corrupt')
        self.assertEqual(self.pixel(), (255, 0, 0, 255))
        self.build()
        with Image.open(self.derivative()) as image:
            self.assertEqual(image.getpixel((5, 5))[:3], (255, 0, 0))

    def test_corrupt_preferred_png_caches_readable_fallback(self):
        png = self.root / '.build/card-renders/Tactics Cards/PNG/ST01-T01.png'
        png.parent.mkdir(parents=True)
        png.write_bytes(b'corrupt')
        self.build()
        self.assertEqual(self.pixel(), (255, 0, 0, 255))
        self.assertEqual(read_manifest(self.cache)['ST01-T01']['source']['path'],
                         self.original.relative_to(self.root).as_posix())
        Image.new('RGB', (746, 1044), 'blue').save(png)
        self.build()
        self.assertEqual(self.pixel(), (0, 0, 255, 255))

    def test_removed_card_cleans_only_owned_outputs(self):
        self.build()
        image = self.derivative()
        unrelated = self.cache / 'user-notes.txt'
        unrelated.write_text('keep')
        self.build([])
        self.assertFalse(image.exists())
        self.assertEqual(read_manifest(self.cache), {})
        self.assertTrue(unrelated.exists())

    def test_new_unit_and_tactic_report_missing_onboarding_without_publication(self):
        unit = self.root / 'authoring/cards/Unit Cards/img_card_front_ex03-u01_en.webp'
        Image.new('RGB', (8, 8)).save(unit, lossless=True)
        self.master.unlink()
        records = discover_cards(self.root)
        unit_record = next(card for card in records if card['number'] == 'EX03-U01')
        self.assertIn('printed metadata', unit_record['missing'])
        self.assertTrue(any('SVG' in reason for reason in unit_record['missing']))
        with self.assertRaisesRegex(ValueError, '2 cards need onboarding'):
            prepare_assets(self.root)
        self.assertFalse((self.root / '.build/published').exists())
        self.assertEqual(len(json.loads((self.root / '.build/onboarding.json').read_text())['pending']), 2)

    def test_sortie_front_is_independent_of_printed_front_in_source_and_bundle(self):
        folder = self.root / 'authoring/cards/Unit Cards'
        printed = 'img_card_front_st01-u01_en.webp'
        variant = 'img_card_st01-u01_en.webp'
        (self.root / 'catalog.json').write_text(json.dumps({'ST01-U01': {
            'name': 'Gundam', 'title': 'Hero', 'hp': 15, 'vp': 8, 'timeline': 2, 'image': printed}}))
        (folder / 'SVG/ST01-U01.svg').write_text('<svg/>')
        Image.new('RGB', (64, 48), 'red').save(folder / variant, lossless=True)
        record = next(c for c in discover_cards(self.root) if c['number'] == 'ST01-U01')
        self.assertIn('original WEBP', record['missing'])
        Image.new('RGB', (64, 48), 'blue').save(folder / printed, lossless=True)
        self.build()
        build_display_cache(load_catalog(self.root).values(), self.root, folder=UNIT_CARDS)
        with patch('companion.asset_pipeline.STATIC_FILES', ()):
            bundle = publish_assets(self.root, discover_cards(self.root))
        for root in (self.root, bundle):
            with self.subTest(root=root):
                self.assertEqual(load_catalog(root)['ST01-U01'].image, printed)
                self.assertEqual(sortie_art(printed, root).getpixel((5, 5))[:3], (255, 0, 0))
                image = load_display_image(printed, 'preview', root, folder=UNIT_CARDS)
                self.assertEqual(image.getpixel((5, 5))[:3], (0, 0, 255))

    def test_duplicate_originals_are_rejected_deterministically(self):
        duplicate = self.original.with_name('img_card_front_st01-t01_en.webp')
        duplicate.write_bytes(self.original.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Duplicate published image'):
            discover_cards(self.root)
        with self.assertRaisesRegex(ValueError, 'Duplicate published image'):
            load_tactics(self.root)

    def test_master_and_renderer_changes_invalidate_render_stamp(self):
        renderer = self.root / 'tools/render_cards.cjs'
        renderer.write_text('renderer v1')
        cards = discover_cards(self.root)
        self.assertEqual(len(needed_renders(self.root, cards)), 1)
        output = self.root / '.build/card-renders/Tactics Cards'
        (output / 'PNG').mkdir(parents=True)
        png = output / 'PNG/ST01-T01.png'
        Image.new('RGB', (8, 8)).save(png)
        def stamp():
            write_manifest(output / 'sources.json', {'ST01-T01': {
                'fingerprint': render_fingerprint(self.root, cards[0]), 'sha256': source_digest(png)}})
        stamp()
        self.assertEqual(needed_renders(self.root, cards), [])
        self.master.write_text('<svg>revised rules</svg>')
        self.assertEqual(len(needed_renders(self.root, cards)), 1)
        stamp()
        renderer.write_text('renderer v2')
        self.assertEqual(len(needed_renders(self.root, cards)), 1)

    def test_publish_excludes_authoring_and_private_files_and_loads_without_sources(self):
        self.build()
        build_display_cache([], self.root, folder=UNIT_CARDS)
        unit_folder = self.root / 'authoring/cards/Unit Cards'
        filename = 'img_card_front_st01-u01_en.webp'
        Image.new('RGB', (800, 567), 'green').save(unit_folder / filename, lossless=True)
        (unit_folder / 'SVG/ST01-U01.svg').write_text('<svg/>')
        (self.root / 'catalog.json').write_text(json.dumps({'ST01-U01': {
            'name': 'Gundam', 'title': 'Hero', 'hp': 15, 'vp': 8, 'timeline': 2, 'image': filename}}))
        units = load_catalog(self.root)
        build_display_cache(units.values(), self.root, folder=UNIT_CARDS)
        (self.root / '.env').write_text('PRIVATE=do-not-publish')
        (self.root / 'unreferenced.png').write_bytes(b'ignore')
        with patch('companion.asset_pipeline.STATIC_FILES', ()):
            output = publish_assets(self.root, discover_cards(self.root))
            manifest = json.loads((output / 'assets.json').read_text())['files']
            self.assertNotIn('.env', manifest)
            self.assertTrue(DICE_FILES.keys() <= manifest.keys())
            self.assertFalse(any('authoring' in name or name.endswith(('.svg', '.png')) for name in manifest))
            self.assertEqual(len(load_catalog(output, verify_images=True)), 1)
            self.assertEqual(len(load_tactics(output)), 1)
            image = load_display_image(self.card.image, 'fan', output, folder=TACTICS_CARDS)
            self.assertEqual(image.getpixel((5, 5)), (255, 0, 0, 255))
            before = (output / 'assets.json').stat().st_mtime_ns
            publish_assets(self.root, discover_cards(self.root))
            self.assertEqual((output / 'assets.json').stat().st_mtime_ns, before)
            (output / 'stale-private-file').write_text('remove')
            publish_assets(self.root, discover_cards(self.root))
            self.assertFalse((output / 'stale-private-file').exists())

    def test_in_memory_preview_refreshes_after_source_update(self):
        from companion import tactics_art
        from companion.card_display import display_revision
        def revision(filename, folder):
            return display_revision(filename, folder, self.root)
        def load(filename, variant, *, folder):
            return load_display_image(filename, variant, self.root, folder=folder)
        self.build()
        with patch.object(tactics_art, 'display_revision', side_effect=revision), \
                patch.object(tactics_art, 'load_display_image', side_effect=load):
            self.assertEqual(tactics_art.fan_art(self.card.image).getpixel((5, 5)), (255, 0, 0, 255))
            Image.new('RGB', (746, 1044), 'blue').save(self.original, lossless=True)
            self.build()
            self.assertEqual(tactics_art.fan_art(self.card.image).getpixel((5, 5)), (0, 0, 255, 255))

    def test_published_preview_with_invalid_checksum_falls_back_to_original(self):
        self.build()
        build_display_cache([], self.root, folder=UNIT_CARDS)
        with patch('companion.asset_pipeline.STATIC_FILES', ()):
            output = publish_assets(self.root, discover_cards(self.root))
        manifest = read_manifest(output / TACTICS_CARDS / 'Display')
        preview = output / TACTICS_CARDS / 'Display' / manifest['ST01-T01']['variants']['preview']['file']
        Image.new('RGB', (746, 1044), 'blue').save(preview, lossless=True)
        # Both the display loader and its full-image fallback must reject a valid but altered derivative.
        image = load_display_image(self.card.image, 'preview', output, folder=TACTICS_CARDS)
        self.assertEqual(image.getpixel((5, 5)), (255, 0, 0, 255))
