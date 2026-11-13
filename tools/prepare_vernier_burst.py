"""Pack the Vernier Burst art study and a compact, standalone motion preview.

The generated source is retained unchanged in .local-authoring. As with Reactor
Surge, binary coverage adapts alpha to the Windows color-key overlay. This tool
does not register the study with the app or portable asset allowlist.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def prepare(source, output, preview):
    with Image.open(source) as sheet:
        if sheet.mode != "RGBA" or sheet.size != (1536, 1024):
            raise ValueError("Expected the approved 1536x1024 RGBA, 6x4 sheet")
        frames = []
        for row in range(4):
            for column in range(6):
                frame = sheet.crop((column*256, row*256, (column+1)*256, (row+1)*256))
                # Discard low-coverage generated haze; retain opaque pixel bands.
                frame.putalpha(frame.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
                bounds = frame.getbbox()
                if not bounds or min(bounds[:2]) < 4 or max(bounds[2:]) > 252:
                    raise ValueError(f"Frame {len(frames)+1} touches its cell edge: {bounds}")
                frames.append(frame)
    frames.append(Image.new("RGBA", (256, 256)))
    durations = [70]*24 + [80]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, format="WEBP", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, lossless=True, method=6)
    with Image.open(output) as packed:
        if packed.n_frames != len(frames):
            raise ValueError("Unexpected packed frame count")
        for i, expected in enumerate(frames):
            packed.seek(i)
            packed.load()
            if packed.info["duration"] != durations[i]:
                raise ValueError(f"Wrong frame timing at {i}")
            decoded = packed.convert("RGBA")
            if decoded.getchannel("A").tobytes() != expected.getchannel("A").tobytes():
                raise ValueError(f"Coverage changed at {i}")

    # A small neutral stage demonstrates the proposed 224px footprint. The
    # notification is preview-only and is never baked into reusable sprite art.
    font = ImageFont.load_default(size=15)
    small = ImageFont.load_default(size=11)
    preview_frames = []
    for tick in range(63):
        seconds = tick*.05
        stage = Image.new("RGB", (480, 320), "#151e22")
        draw = ImageDraw.Draw(stage)
        draw.text((240, 14), "VERNIER BURST / COMPACT MOTION STUDY", font=small,
                  fill="#8d9da4", anchor="mt")
        frame_index = int(seconds/.07)
        if frame_index < 24:
            sprite = frames[frame_index].resize((224, 224), Image.Resampling.NEAREST)
            stage.paste(sprite, (128, 30), sprite)
        if .20 <= seconds < 3.05:
            enter = min(1., max(0., (seconds-.20)/.35))
            leave = min(1., max(0., (seconds-2.30)/.75))
            y = round(250 + 90*(1-enter)**3 + 90*leave**2)
            draw.rectangle((135, y, 345, y+54), fill="#11191e", outline="#6e9caa", width=1)
            draw.line((136, y, 344, y), fill="#81dfff", width=2)
            draw.text((240, y+10), "DASH", font=font, fill="#81dfff", anchor="mt")
            draw.text((240, y+31), "TIMELINE +2", font=small, fill="#eeeee6", anchor="mt")
        preview_frames.append(stage)
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview_frames[0].save(preview, save_all=True, append_images=preview_frames[1:],
                           duration=[50]*62+[700], loop=0, disposal=2)
    print(f"Verified {len(frames)} frames / {sum(durations)}ms / {output.stat().st_size:,} bytes: {output}")
    print(f"Compact preview: {preview}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("Video/VERNIER-BURST.webp"))
    parser.add_argument("--preview", type=Path, default=Path("Images/Dash/dash-vernier-burst-preview.gif"))
    args = parser.parse_args()
    prepare(args.source, args.output, args.preview)
