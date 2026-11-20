"""Static Space ground decoration, in board coordinates (one hex radius = 1)."""
import math
from types import MappingProxyType

from .scenarios import HEX_COLUMN_LENGTHS


def _make_star_field():
    # Explicit LCG and seed keep this identical across processes and Python versions.
    # Generate across the whole board, never by repeating a per-tile texture.
    seed = 73517

    def random():
        nonlocal seed
        seed = (1664525 * seed + 1013904223) & 0xffffffff
        return seed / 4294967296

    step = math.sqrt(3)
    centers = [(f"{row + 1:02}-{col + 1:02}", col * 1.5,
                (row + (0.5 if col % 2 else 0)) * step)
               for col, length in enumerate(HEX_COLUMN_LENGTHS) for row in range(length)]
    result = {key: [] for key, _, _ in centers}
    candidates = []
    width = 2 + (len(HEX_COLUMN_LENGTHS) - 1) * 1.5
    height = max(HEX_COLUMN_LENGTHS) * step
    for _ in range(10000):
        if len(candidates) == 140:
            break
        x, y = -1 + random() * width, -step / 2 + random() * height
        if any(math.hypot(x - px, y - py) < .3 for px, py in candidates):
            continue
        candidates.append((x, y))
        brightness = random()
        size, color = ((.0383, "#BFC3C6") if brightness > .96 else
                       (.0267, "#6D8A8D") if brightness > .68 else (.0183, "#293B49"))
        for key, cx, cy in centers:
            dx, dy = x - cx, y - cy
            # Inset clipping keeps even the brightest point off the thick grid edges.
            if abs(dy) < step / 2 - .12 and step * abs(dx) + abs(dy) < step - .24:
                result[key].append((dx, dy, size, color))
                break
    return MappingProxyType({key: tuple(stars) for key, stars in result.items()})


SPACE_STARS = _make_star_field()


def draw_ground_stars(canvas, palette, terrain, key, x, y, radius):
    """Draw cached points below decals; no timers, raster assets, or scenario mutations."""
    if palette != "space" or terrain != "ground":
        return
    for dx, dy, size, color in SPACE_STARS.get(key, ()):
        cx, cy = x + dx * radius, y + dy * radius
        dot = max(.4, size * radius)
        canvas.create_oval(cx - dot, cy - dot, cx + dot, cy + dot,
                           fill=color, outline="", tags=(key, "hex-star", "battlefield"))
