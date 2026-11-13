"""Versioned, content-checked display derivatives; authoring inputs are never published here."""
import json
import re
import sys
from functools import lru_cache
from hashlib import sha256
from uuid import uuid4

from PIL import Image, __version__ as PILLOW_VERSION

from .file_hash import current_digest, source_digest
from .catalog import ASSETS, TACTICS_CARDS, UNIT_CARDS, card_image_paths, load_card_image, published_number


DISPLAY_SIZES = {
    UNIT_CARDS: {"portrait": (272, 119), "preview": (1280, 908)},
    TACTICS_CARDS: {"fan": (232, 320), "preview": (1000, 1400)},
}
# Bump for changes to cropping, scaling, color handling or other rendering behavior.
RENDER_VERSION = 4
# Horizontal face positions in the full published Unit Card. Keep these tied to
# card IDs (not names): different printings can use different artwork/poses.
# Most portraits retain the banner's full height; narrow trackers crop its sides.
PORTRAIT_CENTERS = {
    "EX01-U01": .654, "EX01-U02": .666, "EX01-U03": .693,
    "EX02-U01": .683, "EX02-U02": .655, "EX02-U03": .672,
    "PA01-U01": .750, "PA01-U02": .650, "PA01-U03": .719,
    "ST01-U01": .690, "ST01-U02": .702, "ST01-U03": .750,
    "ST01-U04": .744, "ST01-U05": .774, "ST01-U06": .690,
}
# Width/height fractions of the full card: exclude printed titles that overlap
# the usual banner crop. Apply these before fitting to any tracker aspect ratio.
PORTRAIT_WINDOWS = {
    "EX01-U01": (.26, .135),  # Unicorn: the name crosses the lower torso.
    "ST01-U02": (.24, .21),  # Wing Zero: exclude the (EW) suffix on the left.
    "ST01-U03": (.16, .21),  # Barbatos: keep the Lupus Rex title outside the crop.
}
GENERATED_IMAGE = re.compile(r"[A-Z0-9]+-[UT][0-9]+[A-Z]*-(?:portrait|preview|fan)(?:-[a-f0-9]{16})?\.(?:png|webp)")


def published_bundle(directory):
    return getattr(sys, "frozen", False) or (directory / "assets.json").is_file()


def display_cache_path(directory, folder):
    if published_bundle(directory):
        return directory / folder / "Display"
    return directory / ".build" / ("unit-display" if folder == UNIT_CARDS else "tactics-display")


def read_manifest(cache):
    try:
        entries = json.loads((cache / "sources.json").read_text(encoding="utf-8"))
        return entries if isinstance(entries, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_write(path, contents):
    if path.is_file() and path.read_bytes() == contents:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(contents)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_manifest(path, entries):
    atomic_write(path, (json.dumps(entries, sort_keys=True, indent=2) + "\n").encode())



@lru_cache(maxsize=256)
def _readable(path, digest):
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError, Image.DecompressionBombError):
        return False


def preferred_source(filename, directory, folder):
    for path in card_image_paths(filename, directory, folder):
        digest = current_digest(path)
        if digest and _readable(path, digest):
            return path
    return None


def recipe(folder):
    return {"version": RENDER_VERSION, "sizes": {key: list(size) for key, size in DISPLAY_SIZES[folder].items()},
            "format": "WEBP", "lossless": True, "method": 4, "pillow": PILLOW_VERSION}


def display_revision(filename, folder, directory=ASSETS):
    """Key in-memory images by the same inputs as the persistent cache."""
    source = preferred_source(filename, directory, folder)
    return (current_digest(display_cache_path(directory, folder) / 'sources.json'),
            current_digest(source) if source is not None else None,
            json.dumps(recipe(folder), sort_keys=True))


def unit_portrait_crop(image, number=None):
    width, height = image.size
    center = PORTRAIT_CENTERS.get(number, .77)
    span, depth = PORTRAIT_WINDOWS.get(number, (.34, .21))
    left = int(width * max(0, min(1 - span, center - span / 2)))
    return image.crop((left, 0, max(left + 1, left + int(width * span)), max(1, int(height * depth))))


def valid_variant(cache, item, *, fresh=False):
    if not isinstance(item, dict) or not isinstance(item.get("file"), str):
        return False
    if not GENERATED_IMAGE.fullmatch(item["file"]):
        return False
    path = cache / item["file"]
    digest = source_digest(path) if fresh else current_digest(path)
    return bool(digest and digest == item.get("sha256"))


def load_display_image(filename, variant, directory=ASSETS, *, folder, cache=None):
    cache = cache if cache is not None else display_cache_path(directory, folder)
    size = DISPLAY_SIZES[folder][variant]
    mode = "RGB" if variant == "portrait" else "RGBA"
    number = published_number(filename)
    record = read_manifest(cache).get(number, {})
    if isinstance(record, dict) and record.get("recipe") == recipe(folder):
        source = None if published_bundle(directory) else preferred_source(filename, directory, folder)
        matches = published_bundle(directory) or (source is not None and
                  record.get("source") == {"path": source.relative_to(directory).as_posix(),
                                            "sha256": current_digest(source)})
        variants = record.get("variants", {})
        item = variants.get(variant) if isinstance(variants, dict) else None
        if matches and valid_variant(cache, item):
            try:
                with Image.open(cache / item["file"]) as image:
                    return image.convert(mode)
            except (OSError, Image.DecompressionBombError):
                pass
    if variant == "portrait":
        image = load_card_image(filename, directory, folder=folder, size=DISPLAY_SIZES[folder]["preview"], mode=mode)
        if image is None:
            return None
        portrait = unit_portrait_crop(image, number)
        portrait.thumbnail(size, Image.Resampling.LANCZOS)
        return portrait
    return load_card_image(filename, directory, folder=folder, size=size, mode=mode)


def build_display_cache(cards, directory=ASSETS, *, folder, cache=None, preview_only=()):
    cache = cache if cache is not None else display_cache_path(directory, folder)
    cache.mkdir(parents=True, exist_ok=True)
    previous = read_manifest(cache)
    entries = {}
    configuration = recipe(folder)
    for card in cards:
        number = published_number(card.image)
        if not number or number in entries:
            continue
        source = preferred_source(card.image, directory, folder)
        if source is None:
            raise ValueError(f"{number}: no readable source image")
        # Builds always hash bytes afresh, even when timestamps were preserved by extraction.
        identity = {"path": source.relative_to(directory).as_posix(), "sha256": source_digest(source)}
        variants = [key for key in DISPLAY_SIZES[folder] if number not in preview_only or key == "preview"]
        old = previous.get(number, {})
        if (isinstance(old, dict) and old.get("source") == identity and old.get("recipe") == configuration
                and isinstance(old.get("variants"), dict)
                and set(old.get("variants", {})) == set(variants)
                and all(valid_variant(cache, item, fresh=True) for item in old["variants"].values())):
            entries[number] = old
            continue
        signature = sha256(json.dumps([identity, configuration, variants], sort_keys=True).encode()).hexdigest()[:16]
        with Image.open(source) as image:
            art = image.convert("RGBA")
        outputs = {}
        for variant in variants:
            scaled = unit_portrait_crop(art, number) if variant == "portrait" else art.copy()
            scaled.thumbnail(DISPLAY_SIZES[folder][variant], Image.Resampling.LANCZOS, reducing_gap=2.0)
            if variant == "portrait":
                scaled = scaled.convert("RGB")
            path = cache / f"{number}-{variant}-{signature}.webp"
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                scaled.save(temporary, format="WEBP", lossless=True, method=4, exact=True)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            outputs[variant] = {"file": path.name, "sha256": source_digest(path), "size": list(scaled.size)}
        entries[number] = {"source": identity, "recipe": configuration, "variants": outputs}
    write_manifest(cache / "sources.json", entries)
    keep = {item["file"] for entry in entries.values() for item in entry["variants"].values()}
    for path in cache.iterdir():
        if GENERATED_IMAGE.fullmatch(path.name) and path.name not in keep:
            path.unlink()
    return len(entries)
