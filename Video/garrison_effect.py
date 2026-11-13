from functools import lru_cache
from math import cos, pi, sin
from random import Random

from PIL import Image, ImageDraw, ImageTk

from companion.theme import AMBER, BORDER, CELL, INK, SIDES


GARRISON_EFFECT_SECONDS = 3.1
EXPLOSION_FPS = 30
EXPLOSION_SECONDS = 1.8
PLACARD_ENTER = .20
PLACARD_SETTLE = .55
PLACARD_EXIT = 2.30
PLACARD_END = 3.05


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


@lru_cache(maxsize=55)
def explosion_frame(frame):
    """Original low-resolution arcade fire/smoke, enlarged without smoothing.

    Generate only frames that are shown. Small cached sprites avoid video decoding
    and keep the same stepped outlines at every window size.
    """
    t = frame / EXPLOSION_FPS
    image = Image.new("RGBA", (192, 160))
    if not 0 < t < EXPLOSION_SECONDS:
        return image
    draw = ImageDraw.Draw(image)
    rise = 1 - (1 - min(1, t / .75)) ** 3
    growth = ease(t / .25)
    cooling = ease((t - .35) / .65)
    breakup = ease((t - 1.02) / .78)
    # Hard color bands, warm undersides and irregular lobes suggest sprite art.
    palettes = (
        ("#512b30", "#ad402b", "#ed692d", "#ffb64b", "#fff1b5"),
        ("#463039", "#7c4140", "#c6633e", "#ee9550", "#ffd67a"),
        ("#382c29", "#604336", "#916140", "#bd8951", "#e0b571"),
        ("#302d28", "#494337", "#68604b", "#89806a", "#b5a78b"),
    )
    palette = palettes[min(3, int(cooling * 3.99))]

    def puff(cx, cy, rx, ry, seed, heat=1.0, outlined=True):
        if rx < 1 or ry < 1:
            return
        # Uneven faceted contour. Every vertex lands on the sprite pixel grid.
        rng = Random(seed)
        contour = [(cos(i * pi / 8), sin(i * pi / 8), rng.uniform(.87, 1.12))
                   for i in range(16)]
        for layer, shrink in enumerate((1, .84, .66, .44, .22)):
            if layer > 2 and heat < .3:
                continue
            ox, oy = -rx * layer * .08, -ry * layer * .11
            points = [(round(cx + ox + dx * rx * shrink * bump),
                       round(cy + oy + dy * ry * shrink * bump)) for dx, dy, bump in contour]
            draw.polygon(points, fill=palette[max(layer, 0 if outlined else 1)])

    # A ragged ground ring spreads ahead of the fire, then fragments into dust.
    if t < 1.15:
        radius = 10 + 79 * ease(t / .75)
        rng = Random(511)
        ring = [(round(96 + cos(i*pi/24) * radius * rng.uniform(.94, 1.06)),
                 round(147 + sin(i*pi/24) * radius * .13)) for i in range(49)]
        for i in range(48):
            if t < .45 or (i % 5) / 5 > ease((t - .45) / .7):
                draw.line((ring[i], ring[i+1]), fill="#fff1b5" if t < .18 else palette[1],
                          width=2 if t < .45 else 1)

    # Ground flash opens into a low dust skirt, separate from the upright stem.
    if t < .18:
        flash = sin(pi * t / .18)
        draw.polygon([(96, 149 - 85 * flash), (104, 134), (126, 115),
                      (114, 141), (158, 151), (96, 155), (34, 151),
                      (77, 141), (67, 119), (88, 134)], fill="#fff1b5")
    if t < 1.25:
        for i in range(9):
            dx = i - 4
            puff(96 + dx * (5 + 8 * rise), 149 - (4 - abs(dx)) * 1.5,
                 (11 + 6 * rise) * (1 - ease((t - .6) / .65)),
                 7 * (1 - ease((t - .7) / .55)), 60 + i, .2)

    # A narrow, turbulent column remains visibly attached to the broad cap.
    cap_y = 134 - 91 * rise - 17 * breakup
    for i in range(7):
        u = i / 6
        cx = 96 + sin(i * 2.3 + t * 8) * (2 + u * 2)
        cy = 145 - u * (145 - cap_y)
        fade = 1 - ease((t - .65 - u * .12) / .65)
        puff(cx, cy, (13 + 8 * u) * growth * fade,
             (17 + 6 * u) * growth * fade, 100 + i, outlined=i == 0)

    # Rolling lobes curl outward around a high crown, with an uneven underside.
    lobes = ((-39, 11, 20, 17), (39, 9, 21, 17), (-28, -4, 23, 21),
             (26, -6, 24, 22), (-8, -12, 25, 24), (12, -11, 24, 23),
             (-19, 10, 22, 17), (20, 12, 21, 16), (0, 3, 25, 22))
    spread = .25 + .75 * rise + breakup * .22
    for i, (dx, dy, rx, ry) in enumerate(lobes):
        erosion = 1 - ease((t - 1.03 - (i % 3) * .07) / .60)
        puff(96 + dx * spread, cap_y + dy * spread - breakup * (i % 3) * 5,
             rx * growth * erosion, ry * growth * erosion, 200 + i,
             1 - cooling, outlined=i < 6)
    # Smaller rolls travel up and out across the crown, breaking the large masses
    # into the boiling, scalloped surface characteristic of arcade explosions.
    rng = Random(816)
    for i in range(34):
        angle, radius = rng.uniform(0, 2*pi), rng.uniform(.1, 1) ** .5
        dx, dy = cos(angle) * radius * 46, sin(angle) * radius * 23
        size = rng.uniform(5, 9)
        erosion = 1 - ease((t - 1.02 - rng.uniform(0, .16)) / .60)
        drift = sin(t * 9 + angle) * 2
        puff(96 + dx * spread + drift, cap_y + dy * spread - breakup * 7,
             size * growth * erosion, size * .8 * growth * erosion, 320 + i,
             1 - cooling, outlined=dy > 9)
        # Hanging, torn edges shorten as the cooling smoke rises and evaporates.
        if dy > 8 and .4 < t < 1.65:
            cx = round(96 + dx * spread + drift)
            cy = round(cap_y + (dy + size*.6) * spread)
            tail = (4 + size) * erosion * sin(pi * min(1, (t - .4) / 1.25))
            draw.polygon(((cx-2, cy), (cx+2, cy), (cx-1, round(cy+tail))), fill=palette[0])
    # Bright embers give way to separated, dark smoke chips at the tail.
    rng = Random(419)
    for i in range(22):
        dx, speed, size = rng.uniform(-1, 1), rng.uniform(.6, 1.3), rng.randint(1, 3)
        age = t - (i % 5) * .025
        if 0 < age < 1.35:
            cx = round(96 + dx * (8 + 72 * age))
            cy = round(147 - speed * 150 * age + 66 * age * age)
            draw.rectangle((cx, cy, cx + size, cy + size * 2),
                           fill=palette[3 if age < .6 else 1])
    return image


def particles():
    rng = Random()
    return [(rng.uniform(-1, 1), rng.uniform(.55, 1.2), rng.uniform(.45, 1),
             rng.uniform(0, 2 * pi), rng.uniform(2, 6)) for _ in range(68)]


@lru_cache(maxsize=48)
def rescue_sprite(kind, frame):
    """Tiny original arcade pickups; a bounded atlas, generated only on use."""
    image = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(image)
    outline = "#382c29"
    if kind == "ring":
        # Squashing the ring around its vertical axis gives a coin-like spin.
        half = max(2, round(11 * abs(cos(frame * pi / 8))))
        box = (16-half, 4, 16+half, 27)
        draw.ellipse(box, fill=outline)
        draw.ellipse((17-half, 5, 15+half, 26), fill="#b77425")
        draw.ellipse((17-half, 5, 15+half, 23), fill="#ffe16a")
        if half > 4:
            draw.ellipse((20-half, 9, 12+half, 22), fill=outline)
            draw.ellipse((21-half, 10, 11+half, 21), fill=(0, 0, 0, 0))
        draw.arc(box, 195, 285, fill="#fff6cc", width=2)
        draw.rectangle((15, 5, 17, 6), fill="#fff6cc")
        return image
    if kind == "sidearm":
        # Short silver slide, angled brown grip, and an open trigger guard.
        draw.polygon(((3, 8), (27, 8), (29, 10), (29, 15), (18, 15),
                      (17, 20), (13, 20), (12, 26), (5, 26), (8, 15),
                      (3, 15)), fill=outline)
        draw.rectangle((4, 9, 27, 12), fill="#bfc3c6")
        draw.line((5, 9, 25, 9), fill="#f2ede0")
        draw.rectangle((5, 13, 26, 14), fill="#637782")
        draw.polygon(((10, 15), (15, 15), (11, 24), (7, 24)), fill="#ad7044")
        draw.line((10, 17, 12, 17), fill="#e4b078")
        draw.line((9, 20, 11, 20), fill="#704934")
        draw.rectangle((16, 16, 16, 18), fill=(0, 0, 0, 0))
        draw.rectangle((7, 7, 9, 8), fill=outline)
        draw.rectangle((25, 7, 26, 8), fill=outline)
    else:
        # Paired cartridges with copper tips and bright brass casings.
        for x, y in ((7, 5), (18, 9)):
            draw.polygon(((x+3, y), (x+6, y+4), (x+6, y+18),
                          (x, y+18), (x, y+4)), fill=outline)
            draw.polygon(((x+3, y+2), (x+5, y+5), (x+1, y+5)), fill="#dc9561")
            draw.rectangle((x+1, y+6, x+5, y+16), fill="#dfac42")
            draw.line((x+1, y+6, x+1, y+16), fill="#fff1b5")
            draw.line((x+1, y+17, x+5, y+17), fill="#9b632f")
    return image.rotate(frame * 22.5, resample=Image.Resampling.NEAREST)


def draw_rescue_pickups(canvas, width, height, seconds, sparks):
    # A few guaranteed pickups stay distinct from the larger confetti burst.
    pickups = (("ring", -.90, 1.05), ("sidearm", -.48, 1.18),
               ("ammo", -.70, .88), ("ring", -.08, 1.26),
               ("ammo", .23, .98), ("sidearm", .48, 1.15),
               ("ring", .80, 1.08), ("ammo", .96, .87))
    scale = min(1.2, height / 330)
    span = min(width * .43, 315 * scale)
    photos = getattr(canvas, "_rescue_photos", None)
    if photos is None:
        canvas._rescue_photos = photos = {}
    for i, (kind, direction, speed) in enumerate(pickups):
        age = seconds - .06 - (i % 3) * .09
        if not 0 < age < 1.95:
            continue
        # Slow rotation keeps silhouettes readable while they follow a falling arc.
        phase = sparks[i][3] if i < len(sparks) else i
        frame = int(phase + age * (13 if kind == "ring" else 7)) % 16
        size = max(1, round((40 if kind == "sidearm" else 34) * scale))
        key = (kind, frame, size)
        if key not in photos:
            photos[key] = ImageTk.PhotoImage(
                rescue_sprite(kind, frame).resize((size, size), Image.Resampling.NEAREST), master=canvas)
        x = width / 2 + direction * span * min(1, age / 1.65)
        y = height - 13 - scale * (speed * 370 * age - 225 * age * age)
        canvas.create_image(x, y, image=photos[key], tags=("rescue-pickup", kind))


def draw_garrison(canvas, width, height, t, rescue, side, points, sparks):
    canvas.delete("all")
    seconds = t * GARRISON_EFFECT_SECONDS
    # Keep particle motion brisk when extending the notification's lifetime.
    t = seconds / 1.6
    x = width / 2
    ground = height - 13
    scale = min(1.2, height / 330)
    color = SIDES[side] if rescue else AMBER
    if not rescue and seconds < EXPLOSION_SECONDS:
        frame = min(54, int(seconds * EXPLOSION_FPS))
        size = (max(1, round(384 * scale)), max(1, round(320 * scale)))
        key = (frame, size)
        if getattr(canvas, "_garrison_sprite_key", None) != key:
            canvas._garrison_sprite = ImageTk.PhotoImage(
                explosion_frame(frame).resize(size, Image.Resampling.NEAREST), master=canvas)
            canvas._garrison_sprite_key = key
        canvas.create_image(x, ground + 8, image=canvas._garrison_sprite, anchor="s")

    colors = (color, "#ffcb7a", "#f4eccc", "#8be0c7")
    for i, (dx, speed, life, angle, size) in enumerate(sparks if rescue else ()):
        age = t - (i % 11) * .023
        if not 0 < age < life:
            continue
        cx = x + dx * (30 + age * 315) * scale
        y = ground - scale * (speed * 470 * age - 260 * age * age)
        cx += sin(angle + 10 * age) * 11 * scale
        r = size * scale * (1 - .6 * age / life)
        spin = angle + age * 9
        points_xy = [coord for j in range(4) for coord in
                     (cx + cos(spin + j*pi/2)*r, y + sin(spin + j*pi/2)*r)]
        canvas.create_polygon(points_xy, fill=colors[i % len(colors)])

    if rescue:
        draw_rescue_pickups(canvas, width, height, seconds, sparks)

    draw_placard(canvas, width, height, seconds,
                 "GARRISON RESCUED" if rescue else "GARRISON DEFEATED",
                 f"PLAYER {side + 1}  ·  +{points} VP", color)


def draw_placard(canvas, width, height, seconds, title, detail, color):
    """Shared entrance, readable hold, and gentle downward exit for action notices."""
    x, ground = width / 2, height - 13
    if PLACARD_ENTER < seconds < PLACARD_END:
        rise = min(1, (seconds - PLACARD_ENTER) / (PLACARD_SETTLE - PLACARD_ENTER))
        retreat = ease((seconds - PLACARD_EXIT) / (PLACARD_END - PLACARD_EXIT))
        rest_y = ground - height * .30
        y = ground + 50 - (1 - (1 - rise) ** 3) * (height * .30 + 50)
        y += (height + 30 - rest_y) * retreat
        canvas.create_rectangle(x-125, y-28, x+125, y+28, outline=BORDER, fill=CELL, width=2)
        canvas.create_line(x-125, y-28, x+125, y-28, fill=color, width=2)
        canvas.create_text(x, y-11, text=title,
                           fill=color, font=("TkDefaultFont", -14, "bold"))
        canvas.create_text(x, y+10, text=detail, fill=INK,
                           font=("TkFixedFont", -13, "bold"))
