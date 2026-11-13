"""Victory Standard celebration for a successfully saved Scenario Goal award."""

import logging
from bisect import bisect_right
from functools import cache
from PIL import Image, ImageTk

from companion.catalog import ASSETS
from .garrison_effect import draw_placard


GOAL_SECONDS = 3.1
GOAL_ART = ASSETS / "Video" / "VICTORY-STANDARD.webp"
VICTORY_GOLD = "#f6d56c"


@cache
def goal_frames():
    """Defer decoding until the first award, keeping startup fast."""
    frames, deadlines = [], []
    elapsed = 0
    try:
        with Image.open(GOAL_ART) as animation:
            for index in range(animation.n_frames):
                animation.seek(index)
                frames.append(animation.convert("RGBA"))
                elapsed += max(1, animation.info.get("duration", 80))
                deadlines.append(elapsed / 1000)
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("Could not load Victory Standard artwork", exc_info=True)
        return (), ()
    return tuple(frames), tuple(deadlines)


def draw_goal(canvas, width, height, t, side, points):
    canvas.delete("all")
    seconds = t * GOAL_SECONDS
    frames, deadlines = goal_frames()
    index = bisect_right(deadlines, seconds)
    if index < len(frames):
        # Keep the entire standard visible above the existing action placard.
        bottom = max(1, height * .70 - 47)
        edge = max(1, round(min(224, width - 24, bottom - 8)))
        key = (index, edge)
        if getattr(canvas, "_goal_key", None) != key:
            canvas._goal_photo = ImageTk.PhotoImage(
                frames[index].resize((edge, edge), Image.Resampling.NEAREST), master=canvas)
            canvas._goal_key = key
        canvas.create_image(width/2, bottom, image=canvas._goal_photo,
                            anchor="s", tags="goal-standard")
    draw_placard(canvas, width, height, seconds, "SCENARIO GOAL",
                 f"PLAYER {side+1}  ·  +{points} VP", VICTORY_GOLD)
