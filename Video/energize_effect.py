"""Reactor Surge sprite animation for a successfully saved Energize action."""

import logging
from bisect import bisect_right
from functools import cache

from PIL import Image, ImageTk

from companion.catalog import ASSETS
from .garrison_effect import draw_placard


ENERGIZE_SECONDS = 3.1
SURGE_ART = ASSETS / "Video" / "REACTOR-SURGE.webp"
AURA_PINK = "#ff94d4"


@cache
def reactor_frames():
    """Decode the small sprite sequence on first use, never during app startup."""
    frames, deadlines = [], []
    elapsed = 0
    try:
        with Image.open(SURGE_ART) as animation:
            for index in range(animation.n_frames):
                animation.seek(index)
                frame = animation.convert("RGBA")
                elapsed += max(1, animation.info.get("duration", 80))
                frames.append(frame)
                deadlines.append(elapsed / 1000)
    except (OSError, ValueError):
        # A cosmetic asset failure must not obscure the successful saved action.
        logging.getLogger(__name__).warning("Could not load Reactor Surge artwork", exc_info=True)
        return (), ()
    return tuple(frames), tuple(deadlines)


def draw_energize(canvas, width, height, t, side):
    canvas.delete("all")
    seconds = t * ENERGIZE_SECONDS
    frames, deadlines = reactor_frames()
    index = bisect_right(deadlines, seconds)
    if index < len(frames):
        edge = max(1, round(min(320 * 1.2, height * 320 / 330)))
        size = (edge, edge)
        key = (index, size)
        if getattr(canvas, "_surge_key", None) != key:
            canvas._surge_photo = ImageTk.PhotoImage(
                frames[index].resize(size, Image.Resampling.NEAREST), master=canvas)
            canvas._surge_key = key
        canvas.create_image(width/2, height-5, image=canvas._surge_photo,
                            anchor="s", tags="energize-aura")
    draw_placard(canvas, width, height, seconds, "ENERGIZED", f"PLAYER {side+1}  ·  +1 ENERGY", AURA_PINK)
