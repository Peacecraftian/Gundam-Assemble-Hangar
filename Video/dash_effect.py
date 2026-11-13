"""Compact Sonic Wake animation for a successfully saved Dash action."""

import logging
from bisect import bisect_right
from functools import cache

from PIL import Image, ImageTk

from companion.catalog import ASSETS
from .garrison_effect import draw_placard


DASH_SECONDS = 3.1
DASH_ART = ASSETS / "Video" / "SONIC-WAKE.webp"
DASH_BLUE = "#71dfff"


@cache
def dash_frames():
    """Load only on first Dash so startup does not pay for animation decoding."""
    frames, deadlines = [], []
    elapsed = 0
    try:
        with Image.open(DASH_ART) as animation:
            for index in range(animation.n_frames):
                animation.seek(index)
                frames.append(animation.convert("RGBA"))
                elapsed += max(1, animation.info.get("duration", 60))
                deadlines.append(elapsed / 1000)
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("Could not load Sonic Wake artwork", exc_info=True)
        return (), ()
    return tuple(frames), tuple(deadlines)


def draw_dash(canvas, width, height, t, side):
    canvas.delete("all")
    seconds = t * DASH_SECONDS
    frames, deadlines = dash_frames()
    index = bisect_right(deadlines, seconds)
    if index < len(frames):
        # Keep the bowl above the shared placard throughout its readable hold.
        bottom = max(1, height * .70 - 47)
        edge = max(1, round(min(224, width - 24, bottom - 8)))
        key = (index, edge)
        if getattr(canvas, "_dash_key", None) != key:
            canvas._dash_photo = ImageTk.PhotoImage(
                frames[index].resize((edge, edge), Image.Resampling.NEAREST), master=canvas)
            canvas._dash_key = key
        canvas.create_image(width/2, bottom, image=canvas._dash_photo,
                            anchor="s", tags="dash-jet")
    draw_placard(canvas, width, height, seconds, "DASH",
                 f"PLAYER {side+1}  ·  TIMELINE +2", DASH_BLUE)
