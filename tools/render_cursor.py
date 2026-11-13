"""Regenerate the Hangar cursors with `python -m tools.render_cursor`."""

from struct import pack

from PIL import Image, ImageDraw, ImageFilter

from companion.artwork import APP_CURSORS
from companion.theme import AMBER, AMBER_INK, SERVICE_ORANGE


ARROW = ((5, 4), (18.8, 15.5), (13.5, 16.1), (16.2, 21.2), (13.2, 22.7), (10.2, 17.5), (5, 21.6))
HAND = (
    (12, 5.3), (13.2, 4.4), (14.3, 4.4), (15.2, 5.4), (15.2, 12.3),
    (16.3, 11.3), (17.5, 11.3), (18.4, 12.3), (19.5, 12.1), (20.6, 12.7), (21.1, 13.7),
    (22.2, 13.5), (23.3, 14.4), (23.7, 16), (23.3, 18.5), (21.8, 20.6), (21.5, 22.8),
    (13, 22.8), (12.7, 21), (7.9, 17.8), (7.6, 16.5), (8.2, 15.6), (9.5, 15.4), (12, 17.3),
)
DRAG_ARM = ((14.6, 14.6), (14.6, 10), (12.4, 10), (16, 6.3), (19.6, 10), (17.4, 10))
IBEAM = (
    (11.6, 6.2), (20.4, 6.2), (20.4, 7.8), (16.9, 7.8), (16.9, 24.2), (20.4, 24.2),
    (20.4, 25.8), (11.6, 25.8), (11.6, 24.2), (15.1, 24.2), (15.1, 7.8), (11.6, 7.8),
)
RESIZE = (
    (5.8, 16), (11.4, 11.5), (11.4, 14.6), (20.6, 14.6), (20.6, 11.5),
    (26.2, 16), (20.6, 20.5), (20.6, 17.4), (11.4, 17.4), (11.4, 20.5),
)
SIZES = (32, 40, 48, 64)


def drag_points():
    points = []
    arm = DRAG_ARM
    for _ in range(4):
        points.extend(arm)
        arm = tuple((32 - y, x) for x, y in arm)
    return points


def render_pointer(size, shape, details=()):
    scale = size / 8
    points = [(round(x * scale), round(y * scale)) for x, y in shape]
    fill = Image.new("L", (size * 4, size * 4))
    ImageDraw.Draw(fill).polygon(points, fill=255)
    outline = fill.copy()
    draw = ImageDraw.Draw(outline)
    radius = round(scale)
    draw.line([*points, points[0]], fill=255, width=2 * radius, joint="curve")
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    halo = outline.filter(ImageFilter.MaxFilter(2 * round(.65 * scale) + 1))
    halo = halo.filter(ImageFilter.GaussianBlur(.9 * scale)).point(lambda alpha: round(alpha * .35))

    pointer = Image.new("RGBA", fill.size)
    for color, alpha in ((AMBER, halo), (AMBER_INK, outline), (SERVICE_ORANGE, fill)):
        layer = Image.new("RGBA", fill.size, color)
        layer.putalpha(alpha)
        pointer.alpha_composite(layer)
    if details:
        marks = Image.new("RGBA", fill.size)
        draw = ImageDraw.Draw(marks)
        for line in details:
            points = [(round(x * scale), round(y * scale)) for x, y in line]
            draw.line(points, fill=AMBER_INK + "aa", width=round(.55 * scale))
        pointer.alpha_composite(marks)
    return pointer.resize((size, size), Image.Resampling.LANCZOS)


def cursor_bitmap(pointer):
    # A CUR DIB contains bottom-up color pixels followed by a DWORD-aligned AND mask.
    size = pointer.width
    bitmap = pointer.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    color = bitmap.tobytes("raw", "BGRA")
    stride = ((size + 31) // 32) * 4
    mask = bytearray(stride * size)
    for index, alpha in enumerate(bitmap.getchannel("A").tobytes()):
        if alpha == 0:
            y, x = divmod(index, size)
            mask[y * stride + x // 8] |= 1 << (7 - x % 8)
    header = pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(color), 0, 0, 0, 0)
    return header + color + mask


def write_cursor(path, shape, hotspot, details=()):
    directory = bytearray(pack("<HHH", 0, 2, len(SIZES)))
    offset = len(directory) + 16 * len(SIZES)
    bitmaps = []
    for size in SIZES:
        bitmap = cursor_bitmap(render_pointer(size, shape, details))
        x, y = (round(coord * size / 32) for coord in hotspot)
        directory.extend(pack("<BBBBHHII", size, size, 0, 0, x, y, len(bitmap), offset))
        bitmaps.append(bitmap)
        offset += len(bitmap)
    path.write_bytes(directory + b"".join(bitmaps))


def main():
    write_cursor(APP_CURSORS["arrow"], ARROW, ARROW[0])
    write_cursor(APP_CURSORS["hand2"], HAND, (13.5, 4.7), (
        ((15.2, 12.8), (15.2, 15.1)), ((18.4, 12.8), (18.4, 15.3)), ((21.0, 14.2), (21.0, 16.0)),
    ))
    write_cursor(APP_CURSORS["fleur"], drag_points(), (16, 16))
    write_cursor(APP_CURSORS["ibeam"], IBEAM, (16, 16))
    write_cursor(APP_CURSORS["hresize"], RESIZE, (16, 16))


if __name__ == "__main__":
    main()
