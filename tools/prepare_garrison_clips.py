"""Bake the desktop Garrison art as transparent, offline tablet animations."""
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw

from Video.garrison_effect import (
    EXPLOSION_FPS, EXPLOSION_SECONDS, explosion_frame, particles,
    rescue_confetti, rescue_pickups, rescue_sprite,
)


def write_clip(path, frames, fps):
    times = [round(i * 1000 / fps) for i in range(len(frames) + 1)]
    frames[0].save(path, save_all=True, append_images=frames[1:], lossless=True,
                   duration=[b - a for a, b in zip(times, times[1:])], loop=1)


def main():
    video = Path(__file__).resolve().parents[1] / "Video"
    write_clip(video / "GARRISON-DEFEAT.webp",
               [explosion_frame(i) for i in range(round(EXPLOSION_FPS * EXPLOSION_SECONDS))],
               EXPLOSION_FPS)
    sparks = particles(Random(41))
    frames = []
    for i in range(56):
        width, height = 240, 180
        frame = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(frame)
        for polygon, fill in rescue_confetti(width, height, i / 25, sparks, "#82d6c3"):
            draw.polygon(polygon, fill=fill)
        for x, y, kind, angle, size in rescue_pickups(width, height, i / 25, sparks):
            sprite = rescue_sprite(kind, angle).resize((size, size), Image.Resampling.NEAREST)
            frame.alpha_composite(sprite, (round(x - size / 2), round(y - size / 2)))
        frames.append(frame)
    write_clip(video / "GARRISON-RESCUE.webp", frames, 25)


if __name__ == "__main__":
    main()

