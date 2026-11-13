"""Pack the approved Reactor Surge sheet for the Windows color-key overlay.

Authoring PNGs stay in ignored .local-authoring; only the lossless animated WebP
is a runtime asset. The row cuts and baseline anchors describe this approved
sheet, whose generated rows are not perfectly aligned to the requested grid.
"""
import argparse
from pathlib import Path

from PIL import Image


def prepare(source, destination):
    with Image.open(source) as original:
        if original.size != (1536, 1024) or original.mode != 'RGBA':
            raise ValueError('Expected the approved 1536×1024 RGBA, six-column sheet.')
        sheet = original.copy()
    frames = []
    for top, bottom, baseline in ((0, 266, 259), (270, 510, 501),
                                  (518, 768, 757), (780, 1024, 1009)):
        for column in range(6):
            tile = sheet.crop((column*256, top, (column+1)*256, bottom))
            # Tk's color-key window cannot blend per-pixel alpha against the app.
            # Binary coverage retains the sprite's colored pixel bands and removes
            # antialias fringe; the original full-alpha source remains untouched.
            tile.putalpha(tile.getchannel('A').point(lambda value: 255 if value >= 128 else 0))
            frame = Image.new('RGBA', (256, 256))
            frame.paste(tile, (0, 236-(baseline-top)))
            bounds = frame.getbbox()
            if not bounds or bounds[0] < 2 or bounds[1] < 2 or bounds[2] > 254 or bounds[3] > 246:
                raise ValueError(f'Frame {len(frames)+1} is empty or touches its cell edge: {bounds}')
            frames.append(frame)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(destination, format='WEBP', save_all=True, append_images=frames[1:],
                   duration=80, loop=0, lossless=True, method=6, minimize_size=True)
    with Image.open(destination) as packed:
        assert packed.n_frames == 24 and packed.size == (256, 256)
        for i, frame in enumerate(frames):
            packed.seek(i)
            packed.load()
            assert packed.info['duration'] == 80
            # Hidden RGB under transparent pixels may be discarded by WebP.
            decoded = packed.convert('RGBA')
            assert decoded.getchannel('A').tobytes() == frame.getchannel('A').tobytes()
    print(f'Packed 24 anchored frames / 1.92 seconds / {destination.stat().st_size:,} bytes: {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('Video/REACTOR-SURGE.webp'))
    args = parser.parse_args()
    prepare(args.source, args.output)
