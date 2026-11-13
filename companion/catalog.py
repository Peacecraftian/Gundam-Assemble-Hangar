import json
import re
from dataclasses import dataclass
from pathlib import Path

from .file_hash import current_digest


ASSETS = Path(__file__).resolve().parent.parent
ROUNDS = 10
UNIT_CARDS = "Unit Cards"
TACTICS_CARDS = "Tactics Cards"
PUBLISHED_IMAGE = re.compile(r"img_card_(?:front_)?([A-Z0-9]+-(?:U[0-9]+[A-Z]*|T[0-9]+))_en\.webp", re.IGNORECASE)
TACTIC_NUMBER = re.compile(r"[A-Z0-9]+-T[0-9]+")


@dataclass(frozen=True)
class Card:
    number: str
    name: str
    title: str
    hp: int
    vp: int
    timeline: int
    image: str
    mass_produced: bool = False

    @property
    def label(self):
        return f"{self.name} · {self.title} [{self.number}]"

    def can_add_to(self, roster):
        return self.mass_produced or self.number not in roster


@dataclass(frozen=True)
class TacticCard:
    number: str
    name: str
    image: str


@dataclass(frozen=True)
class RemoteWeapon:
    number: str
    name: str
    image: str
    parent: str
    icon_bounds: tuple[float, float, float, float]
    hp: int
    vp: int


def published_number(filename):
    match = PUBLISHED_IMAGE.fullmatch(filename)
    return match[1].upper() if match else None


def card_image_paths(filename, directory=ASSETS, folder=UNIT_CARDS):
    if any(separator in filename for separator in ("/", "\\", ":")):
        return ()
    base = card_source_directory(directory, folder)
    number = published_number(filename)
    original = base / filename
    if not number:
        return (original,)
    display = directory / folder / "Display"
    preview = display / f"{number}-preview.webp"
    try:
        entry = json.loads((display / 'sources.json').read_text(encoding='utf-8'))[number]['variants']['preview']
        if re.fullmatch(r'[A-Z0-9]+-[UT][0-9]+[A-Z]*-preview-[a-f0-9]{16}\.webp', entry['file']):
            candidate = display / entry['file']
            if current_digest(candidate) == entry['sha256']:
                preview = candidate
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return (preview,
            directory / ".build" / "card-renders" / folder / "PNG" / f"{number}.png",
            base / "PNG" / f"{number}.png", original)


def card_source_directory(directory, folder):
    source = directory / "authoring" / "cards" / folder
    return source if source.is_dir() else directory / folder


def load_card_image(filename, directory=ASSETS, *, folder=UNIT_CARDS, size, mode="RGB"):
    from PIL import Image

    for path in card_image_paths(filename, directory, folder):
        try:
            with Image.open(path) as image:
                image.thumbnail(size, Image.Resampling.LANCZOS, reducing_gap=2.0)
                return image.convert(mode)
        except (OSError, Image.DecompressionBombError):
            continue
    return None


def load_tactics(directory=ASSETS):
    folder = card_source_directory(directory, TACTICS_CARDS)
    originals = {}
    for path in sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == '.webp'):
        number = published_number(path.name)
        if number and TACTIC_NUMBER.fullmatch(number):
            if number in originals:
                raise ValueError(f"Duplicate published image for {number}.")
            originals[number] = path.name
    numbers = set(originals)
    numbers.update(path.stem.upper() for path in (folder / "PNG").glob("*.png")
                   if TACTIC_NUMBER.fullmatch(path.stem.upper()))
    labels = directory / "tactics.json"
    names = json.loads(labels.read_text(encoding="utf-8"), object_pairs_hook=unique_keys) if labels.is_file() else {}
    return {number: TacticCard(number, names.get(number, number),
                               originals.get(number, f"img_card_{number.lower()}_en.webp"))
            for number in sorted(numbers)}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate catalog key {key!r}.")
        result[key] = value
    return result


def load_catalog(directory=ASSETS, *, verify_images=False):
    path = directory / "catalog.json"
    records = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(records, dict) or not records:
        raise ValueError("The Unit Card catalog must contain at least one card.")

    catalog = {}
    for number, fields in records.items():
        if not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", number):
            raise ValueError(f"Invalid published card number {number!r}.")
        if not isinstance(fields, dict) or fields.keys() - {"mass_produced"} != {
            "name", "title", "hp", "vp", "timeline", "image"
        }:
            raise ValueError(f"{number} has an incomplete or unexpected set of fields.")
        if type(fields.get("mass_produced", False)) is not bool:
            raise ValueError(f"{number} has an invalid Mass Produced flag.")
        for field in ("name", "title", "image"):
            if not isinstance(fields[field], str) or not fields[field].strip():
                raise ValueError(f"{number} has an invalid {field}.")
        for field, minimum in (("hp", 1), ("vp", 0), ("timeline", 1)):
            if type(fields[field]) is not int or fields[field] < minimum:
                raise ValueError(f"{number} has an invalid {field}.")
        if fields["timeline"] > ROUNDS:
            raise ValueError(f"{number} has an invalid starting Timeline round.")
        filename = fields["image"]
        if not any(path.is_file() for path in card_image_paths(filename, directory)):
            raise ValueError(f"{number} is missing its Unit Card image: {filename}.")
        if verify_images and load_card_image(filename, directory, size=(1, 1)) is None:
            raise ValueError(f"{number} has an unreadable Unit Card image: {filename}.")
        catalog[number] = Card(number, **fields)
    return catalog


def load_remote_weapons(catalog, directory=ASSETS, *, verify_images=False):
    path = directory / "remote_weapons.json"
    records = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(records, dict):
        raise ValueError("The Remote Weapon System catalog must be keyed by card number.")

    weapons = {}
    for number, fields in records.items():
        if not isinstance(fields, dict) or fields.keys() != {"name", "image", "parent", "icon_bounds", "hp", "vp"}:
            raise ValueError(f"{number} has an incomplete or unexpected set of Remote Weapon System fields.")
        for field in ("name", "image", "parent"):
            if not isinstance(fields[field], str) or not fields[field].strip():
                raise ValueError(f"{number} has an invalid {field}.")
        for field, minimum in (("hp", 1), ("vp", 0)):
            if type(fields[field]) is not int or fields[field] < minimum:
                raise ValueError(f"{number} has an invalid {field}.")
        filename, parent = fields["image"], fields["parent"]
        if not re.fullmatch(r"[A-Z0-9]+-U[0-9]+[A-Z]+", number) or published_number(filename) != number:
            raise ValueError(f"{number} does not match its published Remote Weapon System image: {filename}.")
        if parent not in catalog or number in catalog:
            raise ValueError(f"{number} must link to a playable parent ({parent}) and have its own card number.")
        bounds = fields["icon_bounds"]
        if not isinstance(bounds, list) or len(bounds) != 4 or any(type(value) not in (int, float) for value in bounds):
            raise ValueError(f"{number} has invalid companion icon bounds.")
        left, top, right, bottom = bounds
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError(f"{number} has invalid companion icon bounds.")
        if verify_images and load_card_image(filename, directory, size=(1, 1)) is None:
            raise ValueError(f"{number} has an unreadable Remote Weapon System image: {filename}.")
        weapons[number] = RemoteWeapon(number, **{**fields, "icon_bounds": tuple(bounds)})
    return weapons
