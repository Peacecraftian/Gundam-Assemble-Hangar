import sys
import tkinter as tk
from functools import cache
from math import cos, radians, sin
from tkinter import font, ttk

from PIL import Image, ImageDraw, ImageTk

from .artwork import APP_CURSORS, logo_art, navigation_icon, speaker_art
from .catalog import ASSETS
from .window_placement import enter_fullscreen, exit_fullscreen, monitor_bounds


BACKGROUND = "#151A1C"
PANEL = "#242B2D"
RAIL = "#2D3537"
CELL = "#191F21"
INK = "#F2EDE0"
MUTED = "#B4BCB5"
BORDER = "#4D5656"
PANEL_EDGE = "#535F5D"
RAISED = "#626B68"
KEY_FACE = "#364143"
KEY_EDGE = "#6A7672"
ENAMEL = "#E2DACA"
ENAMEL_INK = "#242A29"
AMBER = "#FFB762"
SERVICE_ORANGE = "#F3A14D"
ENERGY_YELLOW = "#F1D36A"
ENERGY_SEGMENTS = 10
AMBER_INK = "#261A10"
AMBER_WELL = "#392F25"
SIDES = ("#82D6C3", "#FFA18D")
HANGARS = ("#293D3A", "#41332F")
SIDE_EDGES = ("#4D8074", "#88594F")
READY = "#B2D98A"
DANGER = "#FFD6D1"
DANGER_WELL = "#462F2D"
FOCUS = "#D1EDFF"
DISABLED = "#929C97"
DISABLED_WELL = "#293031"
NAV_ACTIVE_INK = "#FFE0B6"

PRODUCT = "Gundam Assemble Hangar"
MISSION_SORTIE = "Mission Sortie"
BATTLEFIELD = "Battlefield"
MATCH_CONSOLE = "Match Console"
TACTICS = "Tactics"
WORKSPACES = (MISSION_SORTIE, BATTLEFIELD, MATCH_CONSOLE, TACTICS)
NAVIGATION_ICONS = {MISSION_SORTIE: "layers", BATTLEFIELD: "map", MATCH_CONSOLE: "sliders-vertical",
                    TACTICS: "gallery-vertical-end"}
DISPLAY_FONT = ASSETS / "Fonts" / "ChakraPetch-Bold.ttf"
DISPLAY_FAMILY = "Chakra Petch"
SCORE_FONT = ASSETS / "Fonts" / "SairaStencilOne-Regular.ttf"
SCORE_FAMILY = "Saira Stencil One"


@cache
def register_private_font(path):
    if sys.platform != "win32":
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False

    from ctypes import POINTER, WinDLL, byref, c_void_p, create_string_buffer
    from ctypes.wintypes import DWORD, HANDLE

    add_font = WinDLL("gdi32").AddFontMemResourceEx
    add_font.argtypes = c_void_p, DWORD, c_void_p, POINTER(DWORD)
    add_font.restype = HANDLE
    count = DWORD()
    return bool(add_font(create_string_buffer(data), len(data), None, byref(count)))


def families(root):
    registered = register_private_font(DISPLAY_FONT)
    installed = {name.casefold() for name in font.families(root)}
    return (
        DISPLAY_FAMILY if registered or DISPLAY_FAMILY.casefold() in installed else "Segoe UI",
        "Consolas" if "consolas" in installed else "Courier New",
    )


def widen_face(image, width, left, right):
    """Expand a face's center while retaining its fixed border pixels."""
    height = image.height
    right_start = image.width - right
    result = Image.new("RGBA", (width, height))
    result.paste(image.crop((0, 0, left, height)), (0, 0))
    center = image.crop((left, 0, right_start, height))
    result.paste(center.resize((width - left - right, height), Image.Resampling.NEAREST), (left, 0))
    result.paste(image.crop((right_start, 0, image.width, height)), (width - right, 0))
    return result


def surface_face(root, fill, edge, *, tile, radius, depth, lip, highlight=None, backdrop=None, bevel=None,
                 accent=None, inset=None, stroke_width=1):
    key = fill, edge, tile, radius, depth, lip, highlight, backdrop, bevel, accent, inset, stroke_width
    if key in root.surface_images:
        return root.surface_images[key]

    size, scale = 18, 4
    image = Image.new("RGBA", (size * scale, (size + depth) * scale))
    draw = ImageDraw.Draw(image)

    def face(y, color, outline=None):
        box = (scale, y * scale, (size - 1) * scale - 1, (size + y) * scale - 1)
        stroke = max(stroke_width, 2 if outline == FOCUS else 1)
        draw.rounded_rectangle(box, radius=radius * scale, fill=color, outline=outline, width=stroke * scale)

    if lip:
        face(lip, (5, 9, 11, 75))
        if lip > 1:
            face(lip - 1, (8, 12, 14, 155))
        if bevel is not None and lip > 2:
            face(lip - 2, bevel)
    face(0, fill, edge)
    if highlight:
        draw.line(((radius + 1) * scale, scale, (size - radius - 1) * scale - 1, scale),
                  fill=highlight, width=scale)
    if inset:
        draw.line((2 * scale, (size - 4) * scale, 2 * scale, 2 * scale,
                   (size - 2) * scale - 1, 2 * scale, (size - 2) * scale - 1, (size - 4) * scale),
                  fill=inset, width=scale)
        draw.line((3 * scale, 3 * scale, (size - 3) * scale - 1, 3 * scale), fill=inset, width=scale)
    if accent:
        draw.line((3 * scale, (size - 2) * scale, (size - 3) * scale - 1, (size - 2) * scale),
                  fill=accent, width=2 * scale)
    image = image.resize((size, size + depth), Image.Resampling.LANCZOS)
    if backdrop is not None:
        image = Image.alpha_composite(Image.new("RGBA", image.size, backdrop), image)
    width, height = tile
    corner = radius + 2
    image = widen_face(image, width, corner, corner).transpose(Image.Transpose.TRANSPOSE)
    image = widen_face(image, height + depth, corner, corner + depth).transpose(Image.Transpose.TRANSPOSE)
    photo = ImageTk.PhotoImage(image, master=root)
    root.surface_images[key] = photo
    return photo


def surface_element(root, style, name, fill, edge, *, tile=(128, 32), radius=4, depth=3,
                    highlight=None, backdrop=None, bevel=None, accent=None, inset=None, states=(), stroke_width=1):
    photo = surface_face(root, fill, edge, tile=tile, radius=radius, depth=depth, lip=depth,
                         highlight=highlight, backdrop=backdrop, bevel=bevel, accent=accent, inset=inset,
                         stroke_width=stroke_width)
    variants = []
    for flags, color, line, lip in states:
        variant = surface_face(root, color, line, tile=tile, radius=radius, depth=depth, lip=lip,
                               highlight=highlight if lip else None, backdrop=backdrop, bevel=bevel,
                               accent=accent, inset=inset, stroke_width=stroke_width)
        variants.append((*flags, variant))
    corner = radius + 2
    # Ttk tiles image slices rather than scaling them. Wide centers avoid hundreds
    # of tiny blits per repaint, while the explicit minimum preserves widget sizing.
    style.element_create(name, "image", photo, *variants,
                         border=(corner, corner, corner, corner + depth),
                         padding=(2, 1, 2, 1 + depth), width=18, height=18 + depth, sticky="nswe")


def frame_surface(root, style, name, fill, edge=PANEL_EDGE, *, tile=(192, 128), **finish):
    element = f"{name}.bezel"
    surface_element(root, style, element, fill, edge, tile=tile, **finish)
    style.layout(f"{name}.TFrame", [(element, {"sticky": "nswe"})])
    style.configure(f"{name}.TFrame", background=fill)


def button_surface_layout(style, kind, element):
    style.layout(kind, [(element, {"sticky": "nswe", "children": [
        ("Button.padding", {"sticky": "nswe", "children": [
            ("Button.label", {"sticky": "nswe"}),
        ]}),
    ]})])


def navigation_styles(root, style, heading):
    frame_surface(root, style, "Navigation", PANEL, "#111718", tile=(256, 40), radius=4, depth=0,
                  highlight="#151A1C", backdrop=ENAMEL)
    for kind, fill, edge, ink, hover, hover_edge, pressed, accent, inset in (
        ("Workspace.TButton", PANEL, PANEL, INK, "#30393A", "#424D4D", CELL, None, None),
        ("Active.Workspace.TButton", "#4E3926", "#A86E37", NAV_ACTIVE_INK, "#57402A", "#B67D46",
         "#473222", AMBER, "#322519"),
    ):
        element = f"{kind}.face"
        surface_element(root, style, element, fill, edge, radius=2, depth=0, backdrop=PANEL, accent=accent,
                        inset=inset, states=(
            (("disabled",), PANEL, PANEL, 0),
            (("pressed", "focus"), pressed, FOCUS, 0),
            (("pressed",), pressed, edge, 0),
            (("active", "focus"), hover, FOCUS, 0),
            (("focus",), fill, FOCUS, 0),
            (("active",), hover, hover_edge, 0),
        ))
        button_surface_layout(style, kind, element)
        style.configure(kind, background=PANEL, foreground=ink)
        style.map(kind, foreground=[("disabled", DISABLED)])
    style.configure("Workspace.TButton", padding=(10, 5), font=(heading, 10, "bold"))
    style.configure("Active.Workspace.TButton", padding=(10, 6, 10, 4))


def field_surfaces(root, style):
    surface_element(root, style, "Input.bezel", CELL, PANEL_EDGE, radius=3, depth=0, highlight="#111719", states=(
        (("disabled",), DISABLED_WELL, BORDER, 0),
        (("invalid",), CELL, AMBER, 0),
        (("focus",), CELL, FOCUS, 0),
    ))
    for kind in ("TEntry", "TSpinbox", "TCombobox"):
        layout = style.layout(kind)
        field = layout[-1][1]
        if kind == "TCombobox":
            # Keep the native arrow and text area inside the same rounded field.
            field["children"].insert(0, layout[0])
        style.layout(kind, [("Input.bezel", {**field, "sticky": "nswe"})])


def setup_cursors(root):
    root.app_cursors = {}
    if root.tk.call("tk", "windowingsystem") != "win32":
        return
    probe = tk.Frame(root)
    for name, path in APP_CURSORS.items():
        cursor = (f"@{path.as_posix()}",)
        try:
            probe.configure(cursor=cursor)
        except tk.TclError:
            continue
        root.app_cursors[name] = cursor
    if "arrow" in root.app_cursors:
        arrow = root.app_cursors["arrow"]
        root.configure(cursor=arrow)
        # Tk cursor inheritance starts afresh at each top-level window.
        root.option_add("*Toplevel.cursor", arrow, "widgetDefault")
    probe.destroy()
    if "ibeam" in root.app_cursors:
        text = root.app_cursors["ibeam"]
        root.option_add("*TEntry.cursor", text, "widgetDefault")

        def field_cursor(event):
            field = event.widget
            in_text = field.identify(event.x, event.y) == "textarea" and field.instate(("!readonly", "!disabled"))
            cursor = text if in_text else ()
            if field.tk.splitlist(field.cget("cursor")) != cursor:
                field.configure(cursor=cursor)

        # These widgets normally change the pointer over their editable area on motion.
        for widget_class in ("TSpinbox", "TCombobox"):
            root.bind_class(widget_class, "<Motion>", field_cursor)
    if "hresize" in root.app_cursors:
        resize = root.app_cursors["hresize"]

        def table_cursor(event):
            tree = event.widget
            region = tree.identify_region(event.x, event.y)
            cursor = resize if region == "separator" else ()
            if tree.tk.splitlist(tree.cget("cursor")) != cursor:
                tree.configure(cursor=cursor)
            heading = tree.identify_column(event.x) if region == "heading" else ""
            tree.tk.call("ttk::treeview::ActivateHeading", str(tree), heading)

        root.bind_class("Treeview", "<Motion>", table_cursor)


def app_cursor(widget, name):
    return getattr(widget._root(), "app_cursors", {}).get(name, name)


FOOTER_BUTTON_STYLES = ("TButton", "Compact.TButton", "Primary.TButton", "Quiet.TButton",
                        "Danger.TButton", "Service.TButton")


class FooterButton(ttk.Button):
    """Use one responsive footprint for footer actions without changing their colors."""

    def __init__(self, parent, *, style="TButton", **options):
        super().__init__(parent, style=f"Footer.{style}", **options)


def setup_theme(root):
    score_registered = register_private_font(SCORE_FONT)
    heading, mono = families(root)
    score_family = SCORE_FAMILY if score_registered else heading
    chakra = heading == DISPLAY_FAMILY
    root.configure(background=BACKGROUND)
    setup_cursors(root)
    style = ttk.Style(root)
    style.theme_use("clam")
    root.surface_images = {}
    root.navigation_icons = {}
    style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=INK, bordercolor=BORDER)
    style.configure("Heading.TLabel", font=(heading, 29, "bold"))
    style.configure("Section.TLabel", font=(heading, 12, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    frame_surface(root, style, "Panel", PANEL, highlight="#394443")
    style.configure("PanelFill.TFrame", background=PANEL)
    style.configure("Panel.TLabel", background=PANEL)
    style.configure("Panel.TCheckbutton", background=PANEL)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Result.TLabel", background=PANEL, font=(heading, 15, "bold"))
    style.configure("Preview.TLabel", background=PANEL, font=(heading, 13, "bold"))
    if chakra:
        style.configure("Preview.TLabel", padding=(0, -4))
    style.configure("Readout.TLabel", background=CELL, foreground=INK, font=(mono, 14, "bold"), padding=(7, 1))
    frame_surface(root, style, "Rail", RAIL, tile=(256, 36), radius=3, depth=2, highlight="#414C4D")
    style.configure("RailFill.TFrame", background=RAIL)
    frame_surface(root, style, "Housing", RAIL, tile=(256, 36), radius=3, depth=1, highlight="#414C4D")
    style.configure("Rail.TLabel", background=RAIL, foreground=INK, font=(heading, 11, "bold"))
    if chakra:
        style.configure("Rail.TLabel", padding=(0, -3))
    style.configure("RailMeta.TLabel", background=RAIL, foreground=MUTED, font=(mono, 9))
    style.configure("PanelCode.TLabel", background=PANEL, foreground=AMBER, font=(mono, -11),
                    padding=(5, 2), relief="solid", borderwidth=1)
    style.configure("PanelTag.TLabel", background=CELL, foreground=MUTED, font=(mono, -11),
                    padding=(6, 2), relief="solid", borderwidth=1)
    style.configure("FieldLabel.TLabel", foreground=MUTED, font=(mono, -11))
    style.configure("Panel.FieldLabel.TLabel", background=PANEL)
    style.configure("Well.TFrame", background=CELL)
    style.configure("Well.TLabel", background=CELL)
    style.configure("WellMeta.TLabel", background=CELL, foreground=MUTED, font=(mono, -11))
    frame_surface(root, style, "Recess", CELL, radius=3, depth=0, highlight="#111719")
    frame_surface(root, style, "Stat", CELL, tile=(128, 48), radius=3, depth=1, highlight="#111719")
    style.configure("Stat.TLabel", background=CELL, font=(heading, -19, "bold"))
    style.configure("RosterRow.TLabel", background=CELL, font=("Segoe UI", -13, "bold"))
    style.configure("Saved.TLabel", background=RAIL, foreground=READY, font=(mono, 9, "bold"))
    style.configure("Attention.TLabel", background=RAIL, foreground=AMBER, font=(mono, 9, "bold"))
    style.configure("Error.TLabel", background=RAIL, foreground=DANGER, font=("Segoe UI", 9, "bold"))
    # The plate face carries the enamel. Its rounded exterior and shadow sit on graphite.
    frame_surface(root, style, "Enamel", ENAMEL, "#A9A597", tile=(256, 56), radius=5, depth=5,
                  highlight="#F0E8D8", backdrop=BACKGROUND, bevel="#ABA290")
    style.configure("Enamel.TFrame", background=BACKGROUND)
    style.configure("EnamelFill.TFrame", background=ENAMEL)
    style.configure("Enamel.TLabel", background=ENAMEL, foreground=ENAMEL_INK, font=(heading, 13, "bold"))

    def key(kind, fill, ink=INK, hover=RAIL, edge=KEY_EDGE, highlight=RAISED, pressed=BORDER, backdrop=PANEL,
            *, radius=3, stroke_width=1):
        element = f"{kind}.face"
        surface_element(root, style, element, fill, edge, radius=radius, depth=2, highlight=highlight,
                        backdrop=backdrop, stroke_width=stroke_width, states=(
            (("disabled",), DISABLED_WELL, BORDER, 0),
            (("pressed", "focus"), pressed, FOCUS, 0),
            (("pressed",), pressed, edge, 0),
            (("active", "focus"), hover, FOCUS, 2),
            (("focus",), fill, FOCUS, 2),
            (("active",), hover, "#879591", 2),
        ))
        button_surface_layout(style, kind, element)
        style.configure(kind, background=backdrop, foreground=ink)
        style.map(kind, foreground=[("disabled", DISABLED)])

    key("TButton", KEY_FACE, hover="#475557")
    style.configure("TButton", width=0, padding=(8, 4), font=(heading, 10, "bold"))
    style.configure("Compact.TButton", padding=(4, -2 if chakra else 2), font=(heading, 10, "bold"))
    style.configure("Scoring.Compact.TButton", padding=(0, -1) if chakra else (1, 2))
    key("Primary.TButton", AMBER, AMBER_INK, "#FFCA89", "#D88D46", "#FFD69E", "#E19A4D")
    key("Quiet.TButton", PANEL, hover=KEY_FACE, edge=BORDER, highlight=BORDER)
    key("Danger.TButton", DANGER_WELL, DANGER, "#60403C")
    if chakra:
        style.configure("Danger.TButton", padding=(8, 1))
    key("Service.TButton", SERVICE_ORANGE, AMBER_INK, "#FFC17A", "#D58A46", "#FFD28D", "#E89142")
    style.configure("Service.TButton", padding=(9, 0 if chakra else 4))
    for kind in FOOTER_BUTTON_STYLES:
        style.configure(f"Footer.{kind}", width=13, padding=(7, 0 if chakra else 3),
                        font=(heading, 10, "bold"))
    key("Token.TButton", CELL, hover=RAIL)
    style.configure("Token.TButton", padding=(3, 3))
    navigation_styles(root, style, heading)
    style.configure("Arrow.TButton", padding=(4, -4 if chakra else 1), font=(heading, -16, "bold"))
    style.configure("Cursor.TLabel", background=CELL, foreground=INK, font=(mono, -13, "bold"), padding=(4, 1))
    style.configure("Icon.TButton", padding=(6, 2), font=(heading, -15, "bold"), width=0)

    native_entry = style.layout("TEntry")
    score_font, score_padding = score_typography(score_family)
    for side, color in enumerate(SIDES):
        tint, edge = HANGARS[side], SIDE_EDGES[side]
        frame_surface(root, style, f"Hangar{side}", tint, edge, highlight=edge)
        frame_surface(root, style, f"SquadDrop{side}", tint, AMBER, highlight=AMBER)
        style.configure(f"HangarFill{side}.TFrame", background=tint)
        style.configure(f"Side{side}.TLabel", background=tint, foreground=color, font=(heading, 11, "bold"))
        style.configure(f"PlayerName{side}.TLabel", background=tint, foreground=color, font=(heading, 19, "bold"))
        style.configure(f"SideMeta{side}.TLabel", background=tint, foreground=color, font=(mono, 8))
        style.configure(f"SideMark{side}.TFrame", background=color)
        style.configure(f"Slot{side}.TLabel", background=tint, foreground=color, font=(mono, -11),
                        anchor="center", padding=(3, 1), bordercolor=edge, relief="solid", borderwidth=1)
        key(f"Side{side}.TButton", tint, color, ("#35524E", "#593D37")[side], edge=edge, highlight=edge, pressed=tint)
        style.configure(f"Side{side}.TButton", padding=(5, 5), font=(heading, -14, "bold"))
        score_button, score_label = f"Score.Side{side}.TButton", f"Score{side}.TLabel"
        key(score_button, tint, color, ("#35524E", "#593D37")[side], edge=edge, highlight=None, backdrop=tint,
            radius=5, stroke_width=2)
        style.layout(score_label, [(f"{score_button}.face", {
            "sticky": "nswe", "children": style.layout("TLabel")[0][1]["children"],
        })])
        style.configure(score_button, padding=score_padding, font=score_font)
        style.configure(score_label, padding=score_padding, font=score_font,
                        background=tint, foreground=color, anchor="center")
        key(f"Edit{side}.Icon.TButton", CELL, color, tint, edge=edge, highlight=edge, backdrop=tint)
        style.layout(f"Name{side}.TEntry", native_entry)
        style.configure(f"Name{side}.TEntry", fieldbackground=tint, foreground=color,
                        bordercolor=tint, lightcolor=tint, padding=(4, 2), font=(heading, -16, "bold"))
        style.map(f"Name{side}.TEntry", fieldbackground=[("focus", CELL)], bordercolor=[("focus", FOCUS)],
                  lightcolor=[("focus", CELL)])

    style.configure("Treeview", background=CELL, fieldbackground=CELL, foreground=INK, rowheight=24,
                    borderwidth=1, bordercolor=CELL, lightcolor=CELL, darkcolor=CELL)
    style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, font=(mono, -11),
                    padding=(7, 5), borderwidth=1, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
    style.configure("Catalog.Treeview", rowheight=32, font=("Segoe UI", -13))
    style.layout("Catalog.Treeview.Item", [
        ("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.text", {"side": "left", "sticky": ""}),
        ]}),
    ])
    style.map("Treeview.Heading", background=[("active", PANEL)])
    style.map("Treeview", background=[("selected", AMBER_WELL)], foreground=[("selected", AMBER)],
              bordercolor=[("focus", FOCUS)])
    style.layout("Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"sticky": "nswe"}),
        ]}),
    ])
    style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=CELL, arrowsize=10, gripcount=0,
                    bordercolor=CELL, lightcolor=BORDER, darkcolor=BORDER)
    style.map("Vertical.TScrollbar", background=[("active", KEY_EDGE)], lightcolor=[("active", KEY_EDGE)])
    field_surfaces(root, style)
    for kind in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(kind, fieldbackground=CELL, foreground=INK, insertcolor=SERVICE_ORANGE, insertwidth=1,
                        background=KEY_FACE, arrowcolor=MUTED, bordercolor=BORDER,
                        lightcolor=CELL, darkcolor=CELL, padding=(7, 3))
        style.map(kind, fieldbackground=[("disabled", DISABLED_WELL), ("readonly", CELL)],
                  foreground=[("disabled", DISABLED)],
                  bordercolor=[("invalid", AMBER), ("focus", FOCUS)],
                  lightcolor=[("disabled", DISABLED_WELL)],
                  background=[("disabled", DISABLED_WELL), ("active", "#475557")])
    style.configure("Sortie.TEntry", padding=(8, 6), font=("Segoe UI", -14))
    style.configure("Step.TEntry", padding=(3, 5), font=(mono, -15, "bold"))
    root.option_add("*TCombobox*Listbox.background", CELL)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", AMBER_WELL)
    root.option_add("*TCombobox*Listbox.selectForeground", AMBER)
    watch_density(root, style, heading, mono, score_family)


def score_typography(family, compact=False):
    # Trim the font's leading to keep the digits centered within the bezel.
    size = -38 if compact else 40
    if family == SCORE_FAMILY:
        padding = (4, -13, 4, -11) if compact else (4, -15, 4, -7)
        return (family, size, "normal"), padding
    elif family == DISPLAY_FAMILY:
        padding = (4, -17 if compact else -19)
    else:
        padding = (4, -4)
    return (family, size, "bold"), padding


def watch_density(root, style, heading, mono, score_family):
    compact = None

    def resize(event):
        nonlocal compact
        if event.widget is not root:
            return
        scale = float(root.tk.call("tk", "scaling")) / (4 / 3)
        next_density = event.width < 1150 * scale or event.height < 650 * scale
        if compact == next_density:
            return
        compact = next_density
        for kind in FOOTER_BUTTON_STYLES:
            style.configure(f"Footer.{kind}", font=(heading, -11 if compact else 10, "bold"))
        for kind, family, points, pixels, weight in (
            ("Heading.TLabel", heading, 29, 25, "bold"),
            ("Preview.TLabel", heading, 13, 16, "bold"),
            ("Readout.TLabel", mono, 14, 16, "bold"),
            ("Rail.TLabel", heading, 11, 13, "bold"),
            ("RailMeta.TLabel", mono, 9, 11, "normal"),
            ("Saved.TLabel", mono, 9, 11, "bold"),
            ("Attention.TLabel", mono, 9, 11, "bold"),
            ("Compact.TButton", heading, 10, 12, "bold"),
            ("Service.TButton", heading, 11, 13, "bold"),
            ("Token.TButton", heading, 9, 11, "bold"),
            ("Workspace.TButton", heading, 10, 12, "bold"),
            ("Danger.TButton", heading, 10, 13, "bold"),
        ):
            style.configure(kind, font=(family, -pixels if compact else points, weight))
        if heading == DISPLAY_FAMILY:
            style.configure("Scoring.Compact.TButton", font=(heading, -11 if compact else 10, "bold"))
        score_font, score_padding = score_typography(score_family, compact)
        for side in range(2):
            style.configure(f"Score{side}.TLabel", font=score_font, padding=score_padding)
            style.configure(f"Score.Side{side}.TButton", font=score_font, padding=score_padding)
            style.configure(f"PlayerName{side}.TLabel", font=(heading, -20 if compact else 19, "bold"))

    root.bind("<Configure>", resize, add="+")


def shell_windows(window):
    while window is not None:
        yield window
        window = window.master.winfo_toplevel() if window.master is not None else None


def leave_fullscreen(window):
    restored = False
    for shell in shell_windows(window):
        if shell.attributes("-fullscreen"):
            exit_fullscreen(shell)
            restored = True
    return restored


def drag_pose(elapsed, direction):
    wiggle = 2 * sin(elapsed * 19)
    angle = direction * round(3 + 3 * max(0, 1 - 5 * elapsed) + wiggle)
    return angle, round(5 + wiggle)


def plate_bolt(parent, *, angle):
    bolt = tk.Canvas(parent, width=20, height=20, background=ENAMEL,
                     cursor=app_cursor(parent, "hand2"), takefocus=True,
                     highlightthickness=1, highlightbackground=ENAMEL, highlightcolor=ENAMEL_INK)
    bolt.create_oval(2, 3, 18, 19, fill="#F2EBDD", outline="")
    bolt.create_oval(2, 1, 18, 17, fill="#C9C1AF", outline="#9A9181")
    bolt.create_arc(3, 2, 17, 16, start=53, extent=125, style="arc", outline="#EAE2D2")
    turn = radians(angle)
    dx, dy = 7 * cos(turn), 7 * sin(turn)
    edge_x, edge_y = -sin(turn), cos(turn)
    left, top, right, bottom = 10 - dx, 9 - dy, 10 + dx, 9 + dy
    bolt.create_line(left + edge_x, top + edge_y, right + edge_x, bottom + edge_y, fill="#DBD2C0")
    bolt.create_line(left, top, right, bottom, fill="#867E70")
    def toggle_fullscreen(_event):
        window = bolt.winfo_toplevel()
        if not leave_fullscreen(window):
            shells = tuple(reversed(tuple(shell_windows(window))))
            placements = [(shell, monitor_bounds(shell)) for shell in shells]
            try:
                for shell, bounds in placements:
                    enter_fullscreen(shell, bounds)
            except OSError:
                leave_fullscreen(window)
                raise
        return "break"

    bolt.bind("<ButtonRelease-1>", toggle_fullscreen)
    bolt.bind("<Return>", toggle_fullscreen)
    bolt.bind("<space>", toggle_fullscreen)
    return bolt


def console_hardware(parent):
    face = tk.Canvas(parent, width=134, height=36, background=ENAMEL, highlightthickness=0, takefocus=False)
    face.create_oval(0, 6, 24, 30, fill="#D8D9B8", outline="")
    face.create_oval(3, 9, 21, 27, fill="#BECBA5", outline="")
    face.create_oval(5, 11, 19, 25, fill="#738A5C", outline="#A7AE86")
    face.create_oval(7, 13, 17, 23, fill="#8FBD58", outline="")
    face.create_oval(9, 14, 13, 17, fill="#CDE794", outline="")

    grille = speaker_art()
    if grille is not None:
        grille = grille.resize((104, 36), Image.Resampling.LANCZOS)
        face.grille_photo = ImageTk.PhotoImage(grille, master=face)
        face.create_image(29, 0, image=face.grille_photo, anchor="nw")
    return face


def draw_phase_led(canvas, x, y, active, *, red=False):
    if red:
        bezel, ring, lens = ("#58302E", "#A54F48", "#FF7468") if active else ("#2C2020", "#65413E", "#492B29")
        glint = "#FFD5CF"
    else:
        bezel, ring, lens = ("#374B36", "#667D49", "#A9D66C") if active else ("#1D2622", "#35483A", "#24352B")
        glint = "#D9EFAC"
    canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=bezel, outline="")
    canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=ring, outline="")
    canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=lens, outline="")
    if active:
        canvas.create_oval(x - 2, y - 3, x + 1, y - 1, fill=glint, outline="")


def nameplate(parent, active, actions):
    plate = ttk.Frame(parent, style="Enamel.TFrame", padding=(12, 3, 12, 8))
    plate.columnconfigure((0, 2), weight=1, uniform="plate")
    identity = ttk.Frame(plate, style="EnamelFill.TFrame")
    identity.grid(row=0, column=0, sticky="w")
    plate_bolt(identity, angle=-48).pack(side="left", padx=(0, 9))
    brand = ttk.Label(identity, text=PRODUCT, style="Enamel.TLabel")
    artwork = logo_art()
    if artwork is not None:
        if BATTLEFIELD in actions:
            artwork = artwork.copy()
            artwork.thumbnail((150, 44), Image.Resampling.LANCZOS)
        brand.photo = ImageTk.PhotoImage(artwork, master=brand)
        brand.configure(image=brand.photo)
    brand.pack(side="left")
    console = ttk.Frame(plate, style="EnamelFill.TFrame")
    console.grid(row=0, column=2, sticky="e")
    console_hardware(console).pack(side="left")
    plate_bolt(console, angle=27).pack(side="left", padx=(13, 0))
    navigation = ttk.Frame(plate, style="Navigation.TFrame", padding=(5, 4))
    navigation.grid(row=0, column=1, padx=9)
    tabs = (name for name in WORKSPACES if name in actions or name in (MISSION_SORTIE, MATCH_CONSOLE))
    root = parent._root()
    for column, name in enumerate(tabs):
        action = actions.get(name)
        selected = name == active
        disabled = action is None and not selected
        style = "Active.Workspace.TButton" if selected else "Workspace.TButton"
        button = ttk.Button(navigation, text=name, style=style, command=action)
        color = NAV_ACTIVE_INK if selected else DISABLED if disabled else INK
        icon_key = NAVIGATION_ICONS[name], color
        if icon_key not in root.navigation_icons:
            icon = navigation_icon(*icon_key)
            root.navigation_icons[icon_key] = ImageTk.PhotoImage(icon, master=root) if icon is not None else ""
        button.configure(image=root.navigation_icons[icon_key], compound="left")
        button.grid(row=0, column=column, padx=1, sticky="ew")
        navigation.columnconfigure(column, weight=1, uniform="tabs")
        if disabled:
            button.state(["disabled"])
        elif selected:
            button.state(["selected"])
    return plate


def panel_heading(parent, code, title, *, tag=None, spacious=False, decal=None):
    header = ttk.Frame(parent, style="Housing.TFrame", padding=(7, 3))
    if spacious:
        header.configure(padding=(9, 7))
    ttk.Label(header, text=code, style="PanelCode.TLabel").pack(side="left", padx=(0, 8))
    ttk.Label(header, text=title, style="Rail.TLabel").pack(side="left", fill="x")
    if tag:
        ttk.Label(header, text=tag, style="PanelTag.TLabel").pack(side="right")
    if decal is not None:
        ornament = ttk.Label(header, image=decal, style="Rail.TLabel", takefocus=False)
        ornament.photo = decal
        ornament.pack(side="right", padx=(6, 6))
    return header


def registration(canvas, left, top, right, bottom):
    length = min(22, max(4, (right - left) // 10))
    canvas.create_line(left, top + length, left, top, left + length, top, fill=AMBER)
    canvas.create_line(right - length, bottom, right, bottom, right, bottom - length, fill=AMBER)


def draw_well(canvas, left, top, right, bottom):
    def face(offset, fill, edge):
        y, end = top + offset, bottom + offset
        r = 4
        canvas.create_polygon(
            left + r, y, right - r, y, right, y, right, y + r, right, end - r, right, end,
            right - r, end, left + r, end, left, end, left, end - r, left, y + r, left, y,
            fill=fill, outline=edge, smooth=True, splinesteps=8,
        )

    face(2, "#101618", "")
    face(0, PANEL, PANEL_EDGE)


def draw_segments(canvas, x, y, width, height, segments, filled, color, *, tag):
    for index in range(segments):
        left = x + width * index // segments
        right = max(left, x + width * (index + 1) // segments - 2)
        canvas.create_rectangle(left, y, right, y + height, fill=color if index < filled else BORDER,
                                width=0, tags=(tag,))
