from functools import lru_cache

from PIL import Image, ImageOps

from .artwork import card_art, card_edge
from .card_display import DISPLAY_SIZES, display_revision, load_display_image
from .catalog import TACTICS_CARDS


def fan_art(filename):
    return _fan_art(filename, display_revision(filename, TACTICS_CARDS))


@lru_cache(maxsize=64)
def _fan_art(filename, _revision):
    return load_display_image(filename, "fan", folder=TACTICS_CARDS)


def preview_art(filename):
    return _preview_art(filename, display_revision(filename, TACTICS_CARDS))


@lru_cache(maxsize=6)
def _preview_art(filename, _revision):
    return load_display_image(filename, "preview", folder=TACTICS_CARDS)


def tactics_fan_card(filename, size, angle):
    art = fan_art(filename)
    if art is None:
        return None
    card = ImageOps.contain(art, size, Image.Resampling.LANCZOS)
    # Paint the edge at display size so it remains three pixels wide in the fan.
    return card_edge(card).rotate(angle, Image.Resampling.BICUBIC, expand=True)


def tactics_preview_card(filename, size):
    if all(requested > cached for requested, cached in zip(size, DISPLAY_SIZES[TACTICS_CARDS]["preview"])):
        art = card_art(filename, TACTICS_CARDS)
    else:
        art = preview_art(filename)
    return card_edge(ImageOps.contain(art, size, Image.Resampling.LANCZOS)) if art is not None else None
