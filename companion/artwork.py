from collections import OrderedDict
from functools import lru_cache
from math import ceil

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageSequence, ImageTk

from .card_display import DISPLAY_SIZES, display_revision, load_display_image, published_bundle
from .catalog import ASSETS, TACTICS_CARDS, UNIT_CARDS, load_card_image, published_number


HANGAR_ART = ASSETS / "Video" / "Freight Lift.webp"
HANGAR_TINT = .18
HANGAR_OPACITY = .5
LOGO_ART = ASSETS / "Images" / "gundam-assemble-hangar.png"
SPEAKER_ART = ASSETS / "Images" / "speaker-grille.png"
APP_ICON = LOGO_ART.with_suffix(".ico")
APP_CURSORS = {
    "arrow": LOGO_ART.with_name("hangar-pointer.cur"),
    "hand2": LOGO_ART.with_name("hangar-hand.cur"),
    "fleur": LOGO_ART.with_name("hangar-drag.cur"),
    "ibeam": LOGO_ART.with_name("hangar-text.cur"),
    "hresize": LOGO_ART.with_name("hangar-resize.cur"),
}
CARD_EDGE_WIDTH = 3
CARD_EDGE_COLOR = "#f8f6ef"


class PhotoCache:
    """Share rendered Tk images across views in one interpreter."""

    MAX_IMAGES = 256
    MAX_BYTES = 24 * 1024 * 1024

    def __init__(self, master):
        self.master = master
        self.images = OrderedDict()
        self.bytes = 0

    def get(self, render, *args, load=True):
        revisions = tuple(display_revision(arg, UNIT_CARDS if "-U" in published_number(arg) else TACTICS_CARDS)
                          for arg in args if isinstance(arg, str) and published_number(arg))
        key = (render, args, revisions)
        if key in self.images:
            self.images.move_to_end(key)
            return self.images[key][0]
        if not load:
            return None

        image = render(*args)
        photo = ImageTk.PhotoImage(image, master=self.master) if image is not None else None
        size = image.width * image.height * 4 if image is not None else 0
        if size <= self.MAX_BYTES:
            while self.bytes + size > self.MAX_BYTES or len(self.images) >= self.MAX_IMAGES:
                _, (_, removed) = self.images.popitem(last=False)
                self.bytes -= removed
            self.images[key] = (photo, size)
            self.bytes += size
        return photo


@lru_cache(maxsize=1)
def logo_art():
    # Tk 8.6 uses the PNG export of Images/gundam-assemble-hangar.svg.
    try:
        with Image.open(LOGO_ART) as source:
            return ImageOps.contain(source.convert("RGBA"), (206, 54), Image.Resampling.LANCZOS)
    except OSError:
        return None


@lru_cache(maxsize=1)
def speaker_art():
    try:
        with Image.open(SPEAKER_ART) as source:
            return source.convert("RGBA")
    except OSError:
        return None


@lru_cache(maxsize=32)
def decal_art(name, color=None, size=None, transpose=None):
    try:
        with Image.open(ASSETS / "Images" / f"{name}.png") as source:
            image = source.convert("RGBA")
    except OSError:
        return None
    if transpose is not None:
        image = image.transpose(transpose)
    if size is not None:
        image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    if color is not None:
        tint = Image.new("RGBA", image.size, color)
        tint.putalpha(image.getchannel("A"))
        return tint
    return image


def navigation_icon(name, color):
    try:
        with Image.open(ASSETS / "Images" / "Navigation" / f"{name}.png") as source:
            mask = source.convert("RGBA").getchannel("A").resize((17, 17), Image.Resampling.LANCZOS)
    except OSError:
        return None
    icon = Image.new("RGBA", mask.size, color)
    icon.putalpha(mask)
    return icon


@lru_cache(maxsize=1)
def hangar_art():
    try:
        with Image.open(HANGAR_ART) as image:
            return tuple(frame.convert("RGB") for frame in ImageSequence.Iterator(image))
    except OSError:
        return ()


@lru_cache(maxsize=4)
def hangar_background(size, tint, frame=0):
    frames = hangar_art()
    if not frames:
        return None
    art = frames[frame]
    width, height = size
    scale = max(width / art.width, height / art.height)
    crop_width = min(art.width, width / scale)
    crop_height = min(art.height, height / scale)
    left = (art.width - crop_width) / 2
    top = (art.height - crop_height) * .40
    cropped = art.resize(size, Image.Resampling.LANCZOS, box=(left, top, left + crop_width, top + crop_height),
                         reducing_gap=3.0)
    # Composite the tinted artwork at half opacity over the Hangar's solid player color.
    return Image.blend(Image.new("RGB", size, tint), cropped, (1 - HANGAR_TINT) * HANGAR_OPACITY)


def hangar_header(size, tint, height):
    art = hangar_background(size, tint, 0)
    if art is None:
        return None
    header = art.crop((0, 0, size[0], height))
    return Image.blend(header, Image.new("RGB", header.size, tint), .52)


def card_art(filename, folder=UNIT_CARDS):
    return _card_art(filename, folder, display_revision(filename, folder))


@lru_cache(maxsize=12)
def _card_art(filename, folder, _revision):
    # Keep a screen-sized copy rather than retaining every full-resolution decode.
    return load_card_image(filename, ASSETS, folder=folder, size=(1600, 1900), mode="RGBA")


def card_edge(card):
    edge = CARD_EDGE_WIDTH
    outlined = Image.new("RGBA", card.size, CARD_EDGE_COLOR)
    interior = edge, edge, card.width - edge, card.height - edge
    if interior[0] < interior[2] and interior[1] < interior[3]:
        outlined.paste(card.crop(interior), interior[:2])
    outlined.putalpha(card.getchannel("A"))
    return outlined


def unit_preview_art(filename):
    return _unit_preview_art(filename, display_revision(filename, UNIT_CARDS))


@lru_cache(maxsize=16)
def _unit_preview_art(filename, _revision):
    return load_display_image(filename, "preview", folder=UNIT_CARDS)


def fitted_card(filename, size):
    if all(requested > cached for requested, cached in zip(size, DISPLAY_SIZES[UNIT_CARDS]["preview"])):
        art = card_art(filename)
    else:
        art = unit_preview_art(filename)
    return card_edge(ImageOps.contain(art, size, Image.Resampling.LANCZOS)) if art is not None else None


def hangar_card(filename, width, height, displayed, reserve=False):
    art = unit_preview_art(filename)
    if art is None:
        return None
    # Six pixels on the 800-pixel template clear the outline and rounded corners.
    bleed = min(ceil(art.width * 6 / 800), (art.width - 1) // 2, (art.height - 1) // 2)
    crop_width = art.width - 2 * bleed
    crop_height = round(art.height * (crop_width / art.width) * (displayed / height))
    bottom = min(art.height, bleed + max(1, crop_height))
    crop = art.crop((bleed, bleed, art.width - bleed, bottom))
    card = crop.convert("RGB").resize((width, displayed), Image.Resampling.LANCZOS)
    if reserve:
        muted = Image.blend(card, ImageOps.grayscale(card).convert("RGB"), .88)
        card = Image.blend(muted, Image.new("RGB", card.size, "#111517"), .46)
    return card


def unit_portrait(filename, size):
    return _unit_portrait(filename, size, display_revision(filename, UNIT_CARDS))


@lru_cache(maxsize=128)
def _unit_portrait(filename, size, _revision):
    art = load_display_image(filename, "portrait", folder=UNIT_CARDS)
    return ImageOps.fit(art, size, Image.Resampling.LANCZOS, centering=(.5, .42)) if art is not None else None


def timeline_portrait(filename, size, angle):
    art = unit_portrait(filename, size)
    if art is not None and angle:
        return art.convert("RGBA").rotate(angle, Image.Resampling.BICUBIC, expand=True)
    return art


@lru_cache(maxsize=32)
def upgrade_art(key, width=28):
    name = "shields" if key.startswith("shield_") else key
    image = token_art(f"{name}-upgrade", width)
    tint = {
        "shield_spent": ("#362124", "#B47B73"),
        "shield_empty": ("#171B1C", "#58605F"),
    }.get(key)
    return tint_token(image, tint) if tint is not None else image


@lru_cache(maxsize=32)
def status_art(status, active, width=28):
    name = {"Disarm": "disarmed", "Fracture": "fractured", "Slow": "slow"}[status]
    image = token_art(f"{name}-status", width)
    return image if active else tint_token(image, ("#171B1C", "#58605F"))


def objective_art(side, width=18):
    return token_art(("blue-objective", "red-objective")[side], width)


@lru_cache(maxsize=64)
def token_art(name, width, directory=ASSETS):
    with Image.open(directory / "Tokens" / "rendered" / f"{name}.png") as source:
        return ImageOps.contain(source.convert("RGBA"), (width, width), Image.Resampling.LANCZOS)


def published_token_art(name, width):
    directory = ASSETS if published_bundle(ASSETS) else ASSETS / ".build" / "published"
    try:
        return token_art(name, width, directory)
    except OSError:
        return None


def scenario_token_art(name, width):
    if name == "objective":
        # Keep the marker visible in a source checkout before asset preparation.
        return published_token_art(name, width) or token_art("blue-objective", width)
    return token_art(name, width)


def map_token_art(name, width):
    token = scenario_token_art(name, width)
    offset = 1 if width < 26 else 2
    padding = 4
    size = token.width + 2 * padding, token.height + 2 * padding
    mask = Image.new("L", size)
    mask.paste(token.getchannel("A"), (padding, padding + offset))
    shadow = Image.new("RGBA", size)
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(.8)).point(lambda alpha: round(alpha * .55)))
    shadow.alpha_composite(token, (padding, padding))
    return shadow


def token_puff_art(width, progress):
    size = round(width * 1.8)
    center = (size - 1) / 2
    spread = width * (.27 + .38 * progress)
    radius = width * (.14 + .04 * progress)
    opacity = round(170 * (1 - progress) ** 1.5)
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    for dx, dy, scale in ((-1, .22, 1), (-.72, -.52, .8), (-.38, .75, .72),
                          (.38, -.62, .65), (.95, -.13, .9), (.68, .61, .86)):
        x, y = center + dx * spread, center + dy * spread
        r = radius * scale
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(242, 237, 224, opacity))
    return image.filter(ImageFilter.GaussianBlur(.5))


def tint_token(image, tint):
    result = ImageOps.colorize(ImageOps.grayscale(image), *tint)
    result.putalpha(image.getchannel("A"))
    return result


def launch_mark(width=26):
    image = Image.new("RGB", (26, 21), "#3F2B1C")
    draw = ImageDraw.Draw(image)
    draw.polygon(((13, 3), (22, 13), (16, 13), (16, 18), (10, 18), (10, 13), (4, 13)), fill="#FFE08A")
    draw.line((5, 16, 5, 19), fill="#F3A14D", width=2)
    draw.line((21, 16, 21, 19), fill="#F3A14D", width=2)
    return ImageOps.contain(image, (width, width), Image.Resampling.LANCZOS) if width != 26 else image

def hazard_mark():
    image = Image.new("RGB", (24, 15), "#3F2B1C")
    draw = ImageDraw.Draw(image)
    for x in range(-8, 25, 8):
        draw.polygon(((x, 15), (x + 4, 15), (x + 14, 0), (x + 10, 0)), fill="#FFE08A")
    return image
