"""Pack the approved Sonic Wake sheet; retain generated originals unchanged.

The generated first three rows place their bowl baseline at y253 rather than
y236; the last row uses y240. Register those rows before packing. Binary alpha
coverage matches the Windows color-key overlay and the Reactor Surge workflow.
"""

import argparse
from pathlib import Path

from PIL import Image


def prepare(source, output):
    frames = []
    with Image.open(source) as sheet:
        if sheet.mode != "RGBA" or sheet.size != (1536, 1024):
            raise ValueError("Expected the approved 1536x1024 RGBA, 6x4 sheet")
        for row, offset in enumerate((17, 17, 17, 4)):
            for column in range(6):
                tile = sheet.crop((column*256, row*256, (column+1)*256, (row+1)*256))
                tile.putalpha(tile.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
                original = tile.getbbox()
                if original is None or original[1] < offset:
                    raise ValueError("Registration would crop visible artwork")
                frame = Image.new("RGBA", (256, 256))
                frame.paste(tile, (0, -offset))
                bounds = frame.getbbox()
                if min(bounds[:2]) < 8 or max(bounds[2:]) > 248:
                    raise ValueError(f"Frame {len(frames)+1} lacks edge clearance: {bounds}")
                frames.append(frame)
    frames.append(Image.new("RGBA", (256, 256)))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, format="WEBP", save_all=True, append_images=frames[1:],
                   duration=60, loop=0, lossless=True, method=6)
    with Image.open(output) as packed:
        if packed.n_frames != len(frames):
            raise ValueError("Unexpected frame count")
        for index, original in enumerate(frames):
            packed.seek(index)
            packed.load()
            if packed.info["duration"] != 60:
                raise ValueError(f"Unexpected frame duration at {index}")
            decoded = packed.convert("RGBA")
            if decoded.getchannel("A").tobytes() != original.getchannel("A").tobytes():
                raise ValueError(f"Changed alpha coverage at {index}")
            # Transparent RGB is not meaningful; compare composited visible RGB.
            for background in ("black", "white"):
                def visible(image):
                    base = Image.new("RGBA", image.size, background)
                    return Image.alpha_composite(base, image).tobytes()
                if visible(decoded) != visible(original):
                    raise ValueError(f"Changed artwork at {index}")
    print(f"Verified {len(frames)} frames / 1.50 seconds / {output.stat().st_size:,} bytes: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("Video/SONIC-WAKE.webp"))
    args = parser.parse_args()
    prepare(args.source, args.output)
