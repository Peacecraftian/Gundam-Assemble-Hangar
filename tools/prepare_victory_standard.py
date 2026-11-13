"""Pack the approved Victory Standard sheet without modifying the source.

Register each generated pole foot to (96, 236). Binary alpha coverage follows
the existing Windows color-key overlay pipeline; source art remains archived.
"""

import argparse
from pathlib import Path
from PIL import Image


# Measured foot centers on the approved 1536x1024 six-column source sheet.
FOOT_X = (120, 124, 127, 98, 91, 85, 93, 91, 89, 88, 87, 85,
          91, 91, 89, 88, 87, 85, 91, 91, 89, 90, 89, 85)


def prepare(source, output):
    frames = []
    with Image.open(source) as sheet:
        if sheet.mode != "RGBA" or sheet.size != (1536, 1024):
            raise ValueError("Expected the approved 1536x1024 RGBA, 6x4 sheet")
        for index, foot in enumerate(FOOT_X):
            row, column = divmod(index, 6)
            tile = sheet.crop((column*256, row*256, (column+1)*256, (row+1)*256))
            tile.putalpha(tile.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
            dx, dy = 96-foot, -(11, 10, 10, 9)[row]
            bounds = tile.getbbox()
            if bounds is None or min(bounds[0]+dx, bounds[1]+dy) < 8 or max(bounds[2]+dx, bounds[3]+dy) > 248:
                raise ValueError(f"Frame {index+1} lacks registered edge clearance")
            frame = Image.new("RGBA", (256, 256))
            frame.paste(tile, (dx, dy))
            frames.append(frame)
    frames.append(Image.new("RGBA", (256, 256)))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, format="WEBP", save_all=True, append_images=frames[1:],
                   duration=80, loop=0, lossless=True, method=6)
    with Image.open(output) as packed:
        if packed.n_frames != len(frames):
            raise ValueError("Unexpected frame count")
        for index, expected in enumerate(frames):
            packed.seek(index)
            packed.load()
            if packed.info["duration"] != 80:
                raise ValueError(f"Unexpected duration at {index}")
            decoded = packed.convert("RGBA")
            if decoded.getchannel("A").tobytes() != expected.getchannel("A").tobytes():
                raise ValueError(f"Changed coverage at {index}")
            for color in ("black", "white"):
                base = Image.new("RGBA", (256, 256), color)
                if Image.alpha_composite(base, decoded).tobytes() != Image.alpha_composite(base, expected).tobytes():
                    raise ValueError(f"Changed visible colors at {index}")
    print(f"Verified {len(frames)} frames / 2.00 seconds / {output.stat().st_size:,} bytes: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("Video/VICTORY-STANDARD.webp"))
    args = parser.parse_args()
    prepare(args.source, args.output)
