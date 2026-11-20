import tkinter as tk
from dataclasses import dataclass
from math import ceil, cos, radians, sin
from time import monotonic
from tkinter import font, messagebox, ttk

from .artwork import (
    decal_art, fitted_card, launch_mark, objective_art, status_art, sortie_art, sortie_card, sortie_portrait, token_art,
    upgrade_art,
)
from .attack_overlay import AttackOverlay
from .board import fit_text
from .catalog import ROUNDS
from .match import (
    COUNTED_UPGRADES, GARRISON_DEFEAT, GARRISON_POINTS, GARRISON_RESCUE, SHIELD_STATES, STATUS_EFFECTS,
    UNIT_DEFEAT, Match, whole_number,
)
from .remote_overlay import RemoteWeaponOverlay, contains
from .scenarios import NO_SCENARIO, scenario_choices
from .theme import (
    FooterButton,
    AMBER, BACKGROUND, BORDER, CELL, ENERGY_SEGMENTS, ENERGY_YELLOW, INK, MATCH_CONSOLE, MISSION_SORTIE, MUTED,
    PANEL, SIDES, app_cursor, drag_pose, draw_segments, families, leave_fullscreen, nameplate, panel_heading,
    registration,
)
from .workspace import Workspace
from .unit_picker import UnitPicker
from .window_placement import monitor_bounds


SORTIE_DECAL_COLORS = ("#66D6C3", "#F6A179")


def touch_keyboard(widget, title, **options):
    from .touch_keyboard import bind_keyboard
    return bind_keyboard(widget, title, **options)


def spinner(parent, variable, first, last, width=5):
    return touch_keyboard(ttk.Spinbox(parent, from_=first, to=last, textvariable=variable, width=width),
                          "Enter Number", numeric=True)


def field(parent, row, label, widget):
    ttk.Label(parent, text=label, style="Panel.FieldLabel.TLabel").grid(
        row=row, column=0, sticky="w", pady=4, padx=(0, 12),
    )
    widget.grid(row=row, column=1, sticky="ew", pady=4)


def table(parent, columns, height, *, style="Treeview", portraits=False, on_scroll=None):
    frame = ttk.Frame(parent, style="Recess.TFrame", padding=2)
    keys = [key for key, _, _, _ in columns]
    tree = ttk.Treeview(frame, columns=keys, show="tree headings" if portraits else "headings",
                        height=height, selectmode="browse", style=style)
    if portraits:
        tree.column("#0", width=42, minwidth=42, stretch=False)
    for key, title, width, stretch in columns:
        tree.heading(key, text=title, anchor="w")
        tree.column(key, width=width, minwidth=width, stretch=stretch)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.pack(side="left", fill="both", expand=True)
    def scrolled(first, last):
        overflow_scrollbar(scrollbar, first, last)
        if on_scroll is not None:
            on_scroll()

    tree.configure(yscrollcommand=scrolled)
    return frame, tree


def overflow_scrollbar(scrollbar, first, last):
    scrollbar.set(first, last)
    if float(first) > 0 or float(last) < 1:
        if not scrollbar.winfo_manager():
            scrollbar.pack(side="right", fill="y", before=scrollbar.master.winfo_children()[0])
    elif scrollbar.winfo_manager():
        scrollbar.pack_forget()


class Dialog:
    def __init__(self, parent, title):
        self.launcher = parent.focus_get()
        self.previous_grab = parent.grab_current()
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(title)
        self.window.transient(parent)
        self.window.configure(background=BACKGROUND)
        self.workspace = Workspace(self.window)
        self.window.bind("<Escape>", self.escape)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Destroy>", self.restore_focus)
        self.body = self.workspace.layer(self.window)
        self.body.pack(fill="both", expand=True, padx=18, pady=(14, 8))
        self.footer = ttk.Frame(self.window, style="Rail.TFrame", padding=(8, 5))
        # Allocate the action rail before the expanding body, even in short windows.
        self.footer.pack(side="bottom", fill="x", padx=12, pady=(0, 8), before=self.body)
        self.initial_focus = None

    def add_nameplate(self, active, actions):
        nameplate(self.window, active, actions).pack(fill="x", padx=12, pady=(8, 0), before=self.body)

    def buttons(self, text, command):
        button = FooterButton(self.footer, text=text, command=command, style="Primary.TButton")
        button.pack(side="right")
        FooterButton(self.footer, text="Cancel", style="Quiet.TButton", command=self.cancel).pack(side="right", padx=(0, 8))
        return button

    def cancel(self):
        self.window.destroy()

    def escape(self, _event):
        if not leave_fullscreen(self.window):
            self.cancel()
        return "break"

    def restore_focus(self, event):
        if event.widget is not self.window:
            return
        if self.previous_grab is not None and self.previous_grab.winfo_exists():
            self.previous_grab.grab_set()
        if self.launcher is not None and self.launcher.winfo_exists():
            self.launcher.focus_set()

    def show(self, preferred=None):
        window = self.window
        parent = window.master
        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        if preferred:
            width, height = max(width, preferred[0]), max(height, preferred[1])
        left, top, right, bottom = monitor_bounds(parent) or (
            0, 0, window.winfo_screenwidth(), window.winfo_screenheight(),
        )
        width = min(width, right - left - 20)
        height = min(height, bottom - top - 80)
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        x = max(left, min(x, right - width))
        y = max(top, min(y, bottom - height - 70))
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.deiconify()
        window.grab_set()
        (self.initial_focus or window).focus_set()

    def error(self, message):
        messagebox.showerror("Check The Entry", message, parent=self.window)


class CardMount(ttk.Frame):
    def __init__(self, parent, app, *, on_open=None, attacks=(), on_attack=None, sortie=False, **size):
        super().__init__(parent, style="Recess.TFrame", padding=2)
        self.canvas = tk.Canvas(self, background=CELL, highlightthickness=0, **size)
        self.canvas.pack(fill="both", expand=True)
        self.photos = app.photos
        self.sortie = sortie
        self.system_links = ttk.Frame(self) if sortie else None
        self.remote = RemoteWeaponOverlay(self.canvas, app)
        self.attack = AttackOverlay()
        self.attacks, self.on_attack = attacks, on_attack
        self.on_open = on_open
        self.clicked_remote = False
        self.card = None
        self.rendered = None
        self.photo = None
        self.canvas.bind("<Configure>", self.draw)
        self.canvas.bind("<Button-1>", self.click)
        if on_open is not None:
            self.canvas.bind("<Double-Button-1>", self.open_card)
        self.canvas.bind("<Motion>", self.hover)
        self.canvas.bind("<Leave>", self.clear_hover)

    def select(self, card):
        if self.sortie and self.card != card:
            self.system_links.pack_forget()
            for link in self.system_links.winfo_children():
                link.destroy()
            if card and sortie_art(card.image) is not None:
                for weapon in self.remote.weapons:
                    if weapon.parent == card.number:
                        # Full-art fronts have no printed system hotspot.
                        ttk.Button(self.system_links, text=weapon.name, style="Compact.TButton",
                                   command=lambda w=weapon: self.show_system(w)).pack(side="left")
                if self.system_links.winfo_children():
                    self.system_links.pack(side="bottom", before=self.canvas)
        self.card = card
        self.draw()

    def show_system(self, weapon):
        self.remote.active = None if self.remote.active == weapon else weapon
        self.remote.draw()

    def click(self, event):
        self.clicked_remote = self.remote.click(event)
        if self.clicked_remote:
            self.rendered = None
            self.draw()
            self.hover(event)
        elif (profile := self.attack.target(event)) is not None:
            self.on_attack(profile)
            return "break"

    def open_card(self, event):
        was_remote = self.clicked_remote
        self.click(event)
        box = self.remote.card_box
        if not (was_remote or self.clicked_remote) and box is not None and contains(box, event.x, event.y):
            self.on_open(self.card)
        return "break"

    def hover(self, event):
        action = self.remote.hover(event) or self.attack.target(event)
        self.canvas.configure(cursor=app_cursor(self, "hand2") if action else "")

    def clear_hover(self, _event):
        self.canvas.configure(cursor="")
        self.remote.clear_hover()

    def draw(self, _event=None):
        canvas = self.canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 30 or height < 30:
            return
        key = self.card, width, height
        if key == self.rendered:
            return
        self.rendered = key
        canvas.delete("all")
        canvas.configure(cursor="")
        number = self.card.number if self.card else None
        renderer = sortie_card if self.sortie else fitted_card
        self.photo = self.photos.get(renderer, self.card.image, (width - 24, height - 20)) if self.card else None
        if self.photo is None:
            self.remote.place(number, None)
            self.attack.place((), None)
            message = "Unit Card image unavailable." if self.card else "Select a Unit Card to inspect it."
            canvas.create_text(width / 2, height / 2, text=message, fill=MUTED, width=width - 20)
            return
        art_width, art_height = self.photo.width(), self.photo.height()
        left, top = (width - art_width) // 2, (height - art_height) // 2
        canvas.create_image(left, top, image=self.photo, anchor="nw")
        registration(canvas, left - 4, top - 4, left + art_width + 4, top + art_height + 4)
        box = left, top, left + art_width, top + art_height
        full_art = self.sortie and sortie_art(self.card.image) is not None
        self.remote.place(None if full_art else number, box, selection=number)
        self.attack.place(self.attacks, box if self.remote.active is None else None)


class SquadRoster(ttk.Frame):
    def __init__(self, parent, side, player, remove, bind_drag, *, decal=None, photos=None, on_name=None):
        super().__init__(parent, style=f"Hangar{side}.TFrame", padding=(3, 3, 3, 4))
        self.side, self.remove = side, remove
        self.bind_drag = bind_drag
        self.photos, self.row_photos = photos, []
        header = ttk.Frame(self, style=f"HangarFill{side}.TFrame", padding=(7, 4))
        header.pack(fill="x")
        ttk.Frame(header, width=3, style=f"SideMark{side}.TFrame").pack(side="left", fill="y", padx=(0, 4))
        self.count = ttk.Label(header, style=f"SideMeta{side}.TLabel")
        self.count.pack(side="right")
        heading, _ = families(self)
        self.name = ttk.Entry(header, textvariable=player, style=f"TouchSortie.Name{side}.TEntry", width=9,
                              font=(heading, -19, "bold"))

        def edit_name():
            if on_name is not None:
                on_name()
            else:
                self.name.focus_set()
                self.name.selection_range(0, "end")

        edit_box = ttk.Frame(header, style=f"HangarFill{side}.TFrame", width=44, height=44)
        edit_box.pack(side="right", padx=4)
        edit_box.pack_propagate(False)
        ttk.Button(edit_box, text="✎", style=f"TouchSortie.Edit{side}.Icon.TButton", command=edit_name).pack(fill="both", expand=True)
        ttk.Label(header, text=f"PLAYER {side + 1}", style=f"SideMeta{side}.TLabel").pack(side="right", padx=(3, 0))
        self.name.pack(side="left", fill="x", expand=True)
        if on_name is not None:
            self.name.bind("<ButtonRelease-1>", lambda _event: edit_name())
        viewport = ttk.Frame(self, style="Well.TFrame")
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, background=CELL, highlightthickness=0, width=1, height=96,
                                yscrollincrement=1)
        scroll = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview, style="TouchSortie.Vertical.TScrollbar")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=lambda first, last: overflow_scrollbar(scroll, first, last))
        self.rows = ttk.Frame(self.canvas, style="Well.TFrame")
        self.rows_mount = self.canvas.create_window(0, 0, anchor="nw", window=self.rows)
        self.decal_photo = decal
        if decal is not None:
            self.decal = self.canvas.create_image(0, 0, image=decal, anchor="sw", state="hidden")
        self.insertion_marker = tk.Frame(self.canvas, background=AMBER, height=3)
        self.canvas.bind("<Configure>", self.resize_viewport)
        self.rows.bind("<Configure>", self.update_scroll)
        window = self.winfo_toplevel()
        wheel_binding = window.bind("<MouseWheel>", self.scroll_rows, add="+")
        self.bind("<Destroy>", lambda _event: window.unbind("<MouseWheel>", wheel_binding))
        self.remove_keys = []
        self.unit_rows = []

    def viewport_y(self, x, y):
        canvas = self.canvas
        x, y = x - canvas.winfo_rootx(), y - canvas.winfo_rooty()
        if 0 <= x < canvas.winfo_width() and 0 <= y < canvas.winfo_height():
            return y
        return None

    def scroll_rows(self, event):
        if self.viewport_y(event.x_root, event.y_root) is not None:
            self.canvas.yview_scroll(-round(event.delta / 120 * 36), "units")
            return "break"

    def scroll_drag(self, x, y):
        y = self.viewport_y(x, y)
        if y is None:
            return
        height = self.canvas.winfo_height()
        edge = min(16, height // 4)
        if y < edge:
            self.canvas.yview_scroll(-6, "units")
        elif y >= height - edge:
            self.canvas.yview_scroll(6, "units")

    def insertion_index(self, x, y):
        y = self.viewport_y(x, y)
        if y is None:
            return None
        position = self.canvas.canvasy(y)
        return next((index for index, row in enumerate(self.unit_rows)
                     if position < row.winfo_y() + row.winfo_height() / 2), len(self.unit_rows))

    def mark_insertion(self, index):
        marker = self.insertion_marker
        if index is None:
            marker.place_forget()
            return
        if not self.unit_rows:
            row_y = 0
        elif index == len(self.unit_rows):
            row_y = self.rows.winfo_height()
        else:
            row_y = self.unit_rows[index].winfo_y()
        y = round(row_y - self.canvas.canvasy(0))
        y = max(1, min(y, self.canvas.winfo_height() - 2))
        marker.place(x=4, y=y, relwidth=1, width=-8, anchor="w")
        marker.lift()

    def update_scroll(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox(self.rows_mount))
        self.position_decal()

    def resize_viewport(self, event):
        self.canvas.itemconfigure(self.rows_mount, width=event.width)
        self.update_scroll()

    def position_decal(self):
        photo = self.decal_photo
        if photo is None:
            return
        bottom = self.canvas.winfo_height() - 4
        fits = (self.rows.winfo_reqheight() + photo.height() + 4 <= bottom
                and self.canvas.winfo_width() >= photo.width() + 12)
        self.canvas.coords(self.decal, 6, bottom)
        self.canvas.itemconfigure(self.decal, state="normal" if fits else "hidden")

    def reveal(self, row):
        top = row.winfo_y()
        offset = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        if top < offset or top + row.winfo_height() > offset + height:
            target = min(top, max(0, top + row.winfo_height() - height))
            self.canvas.yview_moveto(target / max(1, self.rows.winfo_height()))

    def populate(self, cards):
        for row in self.rows.winfo_children():
            row.destroy()
        count = len(cards)
        self.count.configure(text=f"{count} {'UNIT' if count == 1 else 'UNITS'}")
        self.remove_keys.clear()
        self.row_photos.clear()
        self.unit_rows.clear()
        if not cards:
            empty = ttk.Label(self.rows, text="No Unit Cards added", style="WellMeta.TLabel", padding=(8, 10))
            empty.pack(anchor="w")
        for index, card in enumerate(cards):
            tk.Frame(self.rows, background=BORDER, height=1).pack(fill="x")
            row = ttk.Frame(self.rows, style="Well.TFrame", padding=(8, 7))
            row.pack(fill="x")
            self.unit_rows.append(row)
            badge = ttk.Label(row, text=f"{index + 1:02d}", style=f"Slot{self.side}.TLabel")
            badge.pack(side="left", padx=(0, 6))
            key_box = ttk.Frame(row, style="Well.TFrame", width=44, height=48)
            key_box.pack(side="right", padx=(6, 0))
            key_box.pack_propagate(False)
            key = ttk.Button(key_box, text="−", style="TouchSortie.Icon.TButton", command=lambda index=index: self.remove(index))
            key.pack(fill="both", expand=True)
            key.bind("<FocusIn>", lambda _event, row=row: self.reveal(row))
            self.remove_keys.append(key)
            portrait = ttk.Label(row, style="Well.TLabel")
            if self.photos is not None:
                photo = self.photos.get(sortie_portrait, card.image, (54, 38))
                self.row_photos.append(photo)
                if photo is not None:
                    portrait.configure(image=photo)
            portrait.pack(side="left", padx=(0, 8))
            details = ttk.Frame(row, style="Well.TFrame")
            details.pack(side="left", fill="x", expand=True)
            name = ttk.Label(details, text=card.name, width=1, style="TouchSortie.RosterRow.TLabel")
            name.pack(fill="x")
            number = ttk.Label(details, text=card.number, style="TouchSortie.WellMeta.TLabel")
            number.pack(anchor="w", pady=(3, 0))
            for widget in (row, badge, portrait, details, number, name):
                self.bind_drag(widget, index)
        self.rows.update_idletasks()
        self.update_scroll()


@dataclass(frozen=True)
class SquadDragPress:
    number: str
    widget: tk.Widget
    x: int
    y: int
    source: tuple[int, int] | None = None


class SetupScreen:
    PORTRAIT_SIZE = (60, 42)
    DRAG_PORTRAIT_SIZE = (34, 23)
    GHOST_SIZE = (206, 58)

    def __init__(self, parent, app):
        from .touch_sortie import setup_sortie_styles
        setup_sortie_styles(app.root)
        self.name_keyboard = None
        self.app = app
        self.body = app.workspace.layer(parent)
        self.footer = ttk.Frame(parent, style="Rail.TFrame", padding=(8, 5))
        self.players = [tk.StringVar(master=self.body, value=f"Player {side + 1}") for side in range(2)]
        self.phases = tk.StringVar(master=self.body, value="02")
        self.rosters = [[], []]
        self.roster_views = []
        self.add_buttons = []
        self.catalog_photos = {}
        self.catalog_rows = ()
        self.roster_preview = None
        self.portrait_job = None
        self.drag_press = None
        self.drag_pointer = None
        self.drag_target = None
        self.drag_job = None
        self.drag_ghost = None

        self.heading = app.workspace.caption(self.body, MISSION_SORTIE)
        self.heading.pack(anchor="w")
        self.hint = app.workspace.caption(self.body, "Drag catalog cards to add. Reorder squad cards or drop them outside their list to remove.", "Muted.TLabel")
        self.hint.pack(anchor="w", pady=(2, 8))
        self.body.bind("<Configure>", self.layout_height, add="+")
        chooser = app.workspace.layer(self.body)
        chooser.pack(fill="both", expand=True)
        for column, weight in enumerate((29, 34, 37)):
            chooser.columnconfigure(column, weight=weight, uniform="assembly")
        chooser.rowconfigure(0, weight=1)

        catalog = ttk.Frame(chooser, style="Panel.TFrame", padding=8)
        catalog.grid(row=0, column=0, sticky="nsew")
        catalog_decal = app.photos.get(decal_art, "sortie-chevrons", SORTIE_DECAL_COLORS[0])
        panel_heading(catalog, "01", "Unit Catalog", spacious=True, decal=catalog_decal).pack(fill="x")
        self.search = tk.StringVar(master=self.body)
        ttk.Label(catalog, text="SEARCH UNIT CARDS", style="Panel.FieldLabel.TLabel").pack(anchor="w", pady=(9, 3))
        self.initial_focus = ttk.Entry(catalog, textvariable=self.search, width=12, style="TouchSortie.Sortie.TEntry", font=(families(parent)[0], -18))
        self.initial_focus.pack(fill="x", pady=(0, 7))
        touch_keyboard(self.initial_focus, "Search Unit Catalog", live=True)
        catalog_table, self.cards = table(catalog, (
            ("name", "UNIT", 67, True), ("number", "CARD ID", 73, False),
            ("hp", "HP", 43, False), ("vp", "VP", 29, False),
        ), height=8, style="TouchSortie.Catalog.Treeview", portraits=True, on_scroll=self.queue_portraits)
        self.cards.column("#0", width=72, minwidth=72)
        self.cards.column("number", width=100, minwidth=100)
        self.cards.bind("<Configure>", self.layout_catalog, add="+")
        for child in catalog_table.winfo_children():
            if isinstance(child, ttk.Scrollbar):
                child.configure(style="TouchSortie.Vertical.TScrollbar")
        self.hp_photo = app.photos.get(token_art, "hp", 14)
        self.cards.heading("hp", image=self.hp_photo)
        for stat in ("hp", "vp"):
            self.cards.column(stat, anchor="center")
        self.cards.bind("<Map>", self.queue_portraits)
        self.cards.bind("<Configure>", self.queue_portraits, add="+")
        self.cards.bind("<ButtonPress-1>", self.press_catalog)
        self.bind_drag_source(self.cards)
        self.body.bind("<Destroy>", self.dispose, add="+")
        self.cards.tag_configure("alternate", background=PANEL)
        self.result_count = ttk.Label(catalog, style="PanelMuted.TLabel")
        self.result_count.pack(side="bottom", anchor="w", pady=(4, 0))
        catalog_table.pack(fill="both", expand=True)

        inspection = ttk.Frame(chooser, style="Panel.TFrame", padding=8)
        inspection.grid(row=0, column=1, sticky="nsew", padx=8)
        inspection_decal = app.photos.get(decal_art, "sortie-chevrons")
        panel_heading(inspection, "02", "Card Inspection", spacious=True, decal=inspection_decal).pack(fill="x")
        self.card_title = ttk.Label(inspection, style="Preview.TLabel", wraplength=210)
        self.card_title.pack(anchor="w", pady=(8, 1))
        self.card_meta = ttk.Label(inspection, style="PanelMuted.TLabel", wraplength=210)
        self.card_meta.pack(anchor="w")
        stats = ttk.Frame(inspection, style="PanelFill.TFrame")
        stats.pack(side="bottom", fill="x", pady=(8, 0))
        stats.columnconfigure((0, 1, 2), weight=1, uniform="printed")
        self.card_stats = []
        for column, label in enumerate(("PRINTED HP", "VP VALUE", "START ROUND")):
            tile = ttk.Frame(stats, style="Stat.TFrame", padding=(6, 4))
            tile.grid(row=0, column=column, sticky="nsew", padx=(0, 4 if column < 2 else 0))
            ttk.Label(tile, text=label, style="WellMeta.TLabel", compound="left",
                      image=self.hp_photo if column == 0 else "").pack(anchor="w")
            reading = ttk.Label(tile, style="Stat.TLabel")
            reading.pack(anchor="w")
            self.card_stats.append(reading)
        self.mount = CardMount(inspection, app, sortie=True, on_open=lambda card: show_card(app, card, sortie=True),
                               width=145, height=100)
        self.mount.pack(fill="both", expand=True, pady=(5, 0))
        def wrap_inspection(event):
            for label in (self.card_title, self.card_meta):
                label.configure(wraplength=max(120, event.width - 20))

        inspection.bind("<Configure>", wrap_inspection)

        squads = ttk.Frame(chooser, style="Panel.TFrame", padding=8)
        squads.grid(row=0, column=2, sticky="nsew")
        self.place_squad_warning(chooser, squads)
        squads.columnconfigure(0, weight=1)
        squads.rowconfigure((2, 3), weight=1, uniform="squads")
        panel_heading(squads, "03", "Squad Assembly", tag="2 PLAYERS", spacious=True).grid(row=0, sticky="ew")
        options = ttk.Frame(squads, style="PanelFill.TFrame")
        options.grid(row=1, sticky="ew", pady=(9, 8))
        options.columnconfigure(0, weight=1)
        ttk.Label(options, text="SCENARIO (OPTIONAL)", style="Panel.FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="PHASES", style="Panel.FieldLabel.TLabel").grid(row=0, column=1, sticky="w")
        self.scenarios, scenario_labels = scenario_choices(app.store)
        self.scenario = ttk.Combobox(options, state="readonly", values=[NO_SCENARIO, *scenario_labels], width=8,
                                     style="TouchSortie.TCombobox", font=(families(parent)[0], -16))
        self.scenario.current(0)
        self.scenario.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(3, 0))
        stepper = ttk.Frame(options, style="Well.TFrame")
        stepper.grid(row=1, column=1, sticky="nsew", pady=(3, 0))
        self.phase_down = ttk.Button(stepper, text="−", style="TouchSortie.Icon.TButton", width=2, command=lambda: self.step_phases(-1))
        self.phase_down.pack(side="left", fill="y")
        self.phase_entry = ttk.Entry(stepper, textvariable=self.phases, width=4, justify="center", style="TouchSortie.Step.TEntry", font=(families(parent)[1], -18))
        self.phase_entry.pack(side="left", fill="y")
        touch_keyboard(self.phase_entry, "Match Phases", numeric=True)
        self.phase_entry.bind("<Up>", lambda _event: self.step_phases(1))
        self.phase_entry.bind("<Down>", lambda _event: self.step_phases(-1))
        ttk.Button(stepper, text="+", style="TouchSortie.Icon.TButton", width=2, command=lambda: self.step_phases(1)).pack(
            side="left", fill="y",
        )
        actions = ttk.Frame(squads, style="PanelFill.TFrame")
        actions.grid(row=4, sticky="ew", pady=(2, 0))
        actions.columnconfigure((0, 1), weight=1, uniform="add")
        for side in range(2):
            roster = SquadRoster(
                squads, side, self.players[side], lambda index, side=side: self.remove_card(side, index),
                lambda widget, index, side=side: self.bind_roster_drag(widget, side, index),
                decal=app.photos.get(decal_art, "sortie-arrow", SORTIE_DECAL_COLORS[side]),
                photos=app.photos, on_name=lambda side=side: self.edit_player_name(side),
            )
            roster.grid(row=side + 2, sticky="nsew", pady=(0, 7))
            self.roster_views.append(roster)
            add = ttk.Button(actions, text=f"+  Add To Player {side + 1}", style=f"TouchSortie.Side{side}.TButton",
                             command=lambda side=side: self.add_card(side))
            add.grid(row=0, column=side, sticky="ew", padx=(0, 6 if side == 0 else 0))
            self.add_buttons.append(add)

        self.readiness = ttk.Label(self.footer, style="Attention.TLabel", width=1)
        self.readiness.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.start_button = ttk.Button(self.footer, text="Start Match", style="TouchSortie.Primary.TButton", command=self.start)
        self.start_button.pack(side="right")
        ttk.Button(self.footer, text="Cancel", style="TouchSortie.Quiet.TButton", command=app.cancel_setup).pack(
            side="right", padx=(0, 8),
        )
        self.traces = [(variable, variable.trace_add("write", self.update_ready))
                       for variable in (*self.players, self.phases)]
        self.cards.bind("<<TreeviewSelect>>", self.inspect)
        self.traces.append((self.search, self.search.trace_add("write", self.filter_cards)))
        self.filter_cards()
        for side in range(2):
            self.show_roster(side)

    def layout_height(self, _event=None):
        # Keep a complete touch-sized squad row visible on a 768px desktop.
        # Navigation already names this page, so its oversized caption can yield.
        if self.app.root.winfo_height() < 800:
            self.heading.pack_forget()
        elif not self.heading.winfo_manager():
            self.heading.pack(anchor="w", before=self.hint)

    def layout_catalog(self, event):
        columns = ("name", "number") if event.width < 480 else ("name", "number", "hp", "vp")
        if tuple(self.cards.cget("displaycolumns")) != columns:
            self.cards.configure(displaycolumns=columns)

    def edit_player_name(self, side):
        from .touch_sortie import PlayerNameKeyboard
        if self.name_keyboard is not None and self.name_keyboard.window.winfo_exists():
            self.name_keyboard.window.lift()
            return
        self.name_keyboard = PlayerNameKeyboard(self.app.root, self.players[side], side)

    def place_squad_warning(self, chooser, squads):
        self.warning_photo = self.app.photos.get(decal_art, "sortie-warning")
        photo = self.warning_photo
        if photo is None:
            return
        warning = self.body.create_image(0, 0, image=photo, state="hidden")

        def position(_event):
            height = chooser.winfo_y()
            width = squads.winfo_width()
            x = chooser.winfo_x() + squads.winfo_x() + width / 2
            self.body.coords(warning, x, height / 2)
            fits = width >= photo.width() + 16 and height >= photo.height() + 12
            self.body.itemconfigure(warning, state="normal" if fits else "hidden")

        for widget in (chooser, squads):
            widget.bind("<Configure>", position, add="+")

    def show(self):
        self.body.grid(row=1, column=0, sticky="nsew")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.initial_focus.focus_set()

    def filter_cards(self, *_args):
        self.clear_drag()
        query = self.search.get().strip().casefold()
        selection = self.cards.selection()
        self.cards.delete(*self.cards.get_children())
        cards = sorted((card for card in self.app.catalog.values() if query in card.label.casefold()),
                       key=lambda card: (card.name.casefold(), card.number))
        for index, card in enumerate(cards):
            if card.number not in self.catalog_photos:
                photo = self.app.photos.get(sortie_portrait, card.image, self.PORTRAIT_SIZE, load=False)
                if photo is not None:
                    self.catalog_photos[card.number] = photo
            self.cards.insert("", "end", iid=card.number, image=self.catalog_photos.get(card.number, ""),
                              values=(card.name, card.number, card.hp, card.vp),
                              tags=("alternate",) if index % 2 else ())
        matches = self.cards.get_children()
        self.catalog_rows = matches
        self.result_count.configure(text=f"{len(matches)} of {len(self.app.catalog)} cards" if matches else "No cards match the search.")
        if selection and selection[0] in matches:
            self.cards.selection_set(selection[0])
        self.inspect()
        self.queue_portraits()

    def queue_portraits(self, _event=None):
        if self.portrait_job is None and self.catalog_rows and self.cards.winfo_ismapped():
            self.portrait_job = self.body.after(12, self.load_portraits)

    def load_portraits(self):
        self.portrait_job = None
        first, last = self.cards.yview()
        count = len(self.catalog_rows)
        visible = self.catalog_rows[round(first * count):ceil(last * count) + 2]
        missing = [number for number in visible if number not in self.catalog_photos]
        # Leave room for painting and input between batches of card image decodes.
        for number in missing[:2]:
            filename = self.app.catalog[number].image
            photo = self.app.photos.get(sortie_portrait, filename, self.PORTRAIT_SIZE)
            self.catalog_photos[number] = photo if photo is not None else ""
            self.cards.item(number, image=self.catalog_photos[number])
        if len(missing) > 2:
            self.queue_portraits()

    def dispose(self, _event):
        if _event.widget is not self.body:
            return
        if self.name_keyboard is not None and self.name_keyboard.window.winfo_exists():
            self.name_keyboard.cancel()
        if self.drag_job is not None:
            self.body.after_cancel(self.drag_job)
        if self.portrait_job is not None:
            self.body.after_cancel(self.portrait_job)
            self.portrait_job = None
        for variable, trace in self.traces:
            variable.trace_remove("write", trace)

    def inspect(self, _event=None):
        selection = self.cards.selection()
        if selection:
            self.roster_preview = None
        number = selection[0] if selection else self.roster_preview
        card = self.app.catalog.get(number)
        self.mount.select(card)
        self.card_title.configure(text=card.name if card else "No card selected")
        meta = f"{card.title} · {card.number}" if card else ""
        if card and card.mass_produced:
            meta += " · Mass Produced"
        self.card_meta.configure(text=meta)
        values = (card.hp, card.vp, f"{card.timeline:02d}") if card else ("—", "—", "—")
        for reading, value in zip(self.card_stats, values):
            reading.configure(text=value)
        for side, button in enumerate(self.add_buttons):
            can_add = card is not None and card.can_add_to(self.rosters[side])
            button.configure(text=(f"In Player {side + 1} Squad" if card and not can_add
                                   else f"+  Add To Player {side + 1}"))
            button.state(["!disabled"] if can_add else ["disabled"])

    def inspect_roster_card(self, number):
        if self.cards.exists(number):
            self.cards.selection_set(number)
            self.cards.focus(number)
            self.cards.see(number)
        else:
            self.roster_preview = number
            self.cards.selection_remove(*self.cards.selection())
        self.inspect()

    def press_catalog(self, event):
        self.clear_drag()
        if self.cards.identify_region(event.x, event.y) not in ("tree", "cell"):
            return
        number = self.cards.identify_row(event.y)
        if number:
            self.drag_press = SquadDragPress(number, self.cards, event.x_root, event.y_root)
            self.cards.focus_set()
            self.cards.focus(number)
            self.cards.selection_set(number)
            return "break"

    def bind_drag_source(self, widget):
        widget.bind("<B1-Motion>", self.drag_unit)
        widget.bind("<ButtonRelease-1>", self.drop_unit)
        widget.bind("<Escape>", lambda _event: "break" if self.clear_drag() else None)
        widget.bind("<FocusOut>", self.cancel_source)
        widget.bind("<Unmap>", self.cancel_source)

    def bind_roster_drag(self, widget, side, index):
        widget.configure(cursor=app_cursor(widget, "hand2"))
        widget.bind("<ButtonPress-1>", lambda event: self.press_roster(event, side, index))
        self.bind_drag_source(widget)

    def press_roster(self, event, side, index):
        self.clear_drag()
        self.drag_press = SquadDragPress(
            self.rosters[side][index], event.widget, event.x_root, event.y_root, (side, index),
        )
        event.widget.focus_set()
        return "break"

    def cancel_source(self, event):
        if self.drag_press is not None and self.drag_press.widget == event.widget:
            self.clear_drag()

    def drop_side(self, x, y):
        for side, roster in enumerate(self.roster_views):
            left, top = roster.winfo_rootx(), roster.winfo_rooty()
            if contains((left, top, left + roster.winfo_width() - 1, top + roster.winfo_height() - 1), x, y):
                return side
        return None

    def drag_unit(self, event):
        press = self.drag_press
        if press is None or press.widget != event.widget:
            return
        x, y = event.x_root, event.y_root
        picking_up = self.drag_pointer is None
        if picking_up and max(abs(x - press.x), abs(y - press.y)) < 5:
            return
        self.drag_pointer = x, y
        if picking_up:
            self.drag_started = monotonic()
            press.widget.configure(cursor=app_cursor(press.widget, "fleur"))
            if self.drag_ghost is None:
                width, height = self.GHOST_SIZE
                self.drag_ghost = tk.Canvas(self.body, width=width, height=height, background=CELL,
                                            highlightthickness=0, takefocus=False)
                self.drag_face = font.Font(root=self.body, family="Segoe UI", size=-13, weight="bold")
            name = self.app.catalog[press.number].name
            if press.source is not None:
                name = f"{press.source[1] + 1:02d}  {name}"
            self.drag_title = fit_text(name, 142, self.drag_face)
        self.guide_drop()
        width, height = self.GHOST_SIZE
        left, top = x - self.body.winfo_rootx(), y - self.body.winfo_rooty()
        max_left = self.body.winfo_width() - width
        left = left + 14 if left + 14 <= max_left else left - width - 14
        self.drag_ghost.place(x=max(0, min(left, max_left)),
                              y=max(0, min(top + 10, self.body.winfo_height() - height)))
        if picking_up:
            self.animate_drag()
        return "break"

    def guide_drop(self, *, scroll=False):
        press = self.drag_press
        x, y = self.drag_pointer
        if press.source is None:
            side = self.drop_side(x, y)
            allowed = side is not None and self.app.catalog[press.number].can_add_to(self.rosters[side])
        else:
            side, source_index = press.source
            allowed = True
        roster = self.roster_views[side] if allowed else None
        if scroll and roster is not None:
            roster.scroll_drag(x, y)
        gap = roster.insertion_index(x, y) if roster is not None else None
        target = side, gap, roster.canvas.canvasy(0) if gap is not None else None
        if target == self.drag_target:
            return
        if press.source is None and (self.drag_target is None or side != self.drag_target[0]):
            for index, view in enumerate(self.roster_views):
                style = "SquadDrop" if allowed and index == side else "Hangar"
                view.configure(style=f"{style}{index}.TFrame")
        self.drag_target = target
        for index, view in enumerate(self.roster_views):
            view.mark_insertion(gap if index == side else None)

        if side is None:
            hint = "Drop on either squad to add this Unit Card."
        elif not allowed:
            hint = f"Already in Player {side + 1}'s squad."
        elif press.source is None:
            slot = gap + 1 if gap is not None else len(self.rosters[side]) + 1
            hint = f"Release to add to Player {side + 1}, slot {slot:02d}."
        elif gap is None:
            hint = f"Release to remove this Unit Card from Player {side + 1}'s squad."
        else:
            slot = gap - (gap > source_index) + 1
            hint = f"Release to place in slot {slot:02d}."
        self.readiness.configure(text=hint, style="Attention.TLabel")

    def animate_drag(self):
        ghost = self.drag_ghost
        press = self.drag_press
        self.guide_drop(scroll=True)
        card = self.app.catalog[press.number]
        direction = 1 if self.drag_pointer[0] >= press.x else -1
        angle, lift = drag_pose(monotonic() - self.drag_started, direction)
        width, height = self.GHOST_SIZE
        sine, cosine = sin(radians(angle)), cos(radians(angle))

        def point(x, y):
            return width / 2 + x * cosine + y * sine, (height + 5 - lift) / 2 + y * cosine - x * sine

        ghost.delete("all")
        ghost.create_polygon(point(-94, -15), point(94, -15), point(94, 15), point(-94, 15),
                             fill=PANEL, outline=AMBER)
        ghost.photo = self.app.photos.get(sortie_portrait, card.image, self.DRAG_PORTRAIT_SIZE, angle)
        if ghost.photo is not None:
            ghost.create_image(*point(-73, 0), image=ghost.photo)
        ghost.create_text(*point(-52, 0), text=self.drag_title, fill=INK,
                          font=self.drag_face, anchor="w", angle=angle)
        self.drag_job = self.body.after(30, self.animate_drag)

    def clear_drag(self):
        press = self.drag_press
        self.drag_press = None
        if self.drag_pointer is None:
            return False
        self.body.after_cancel(self.drag_job)
        self.drag_job = self.drag_pointer = self.drag_target = None
        self.drag_ghost.place_forget()
        if press.source is None:
            self.cards.configure(cursor="")
            for side, roster in enumerate(self.roster_views):
                roster.configure(style=f"Hangar{side}.TFrame")
        else:
            press.widget.configure(cursor=app_cursor(press.widget, "hand2"))
        for roster in self.roster_views:
            roster.mark_insertion(None)
        self.update_ready()
        return True

    def drop_unit(self, event):
        press = self.drag_press
        if press is None or press.widget != event.widget:
            return
        if self.drag_pointer is None:
            self.drag_press = None
            if press.source is not None:
                self.inspect_roster_card(press.number)
                return "break"
            return
        self.clear_drag()
        if press.source is None:
            side = self.drop_side(event.x_root, event.y_root)
            if side is not None:
                gap = self.roster_views[side].insertion_index(event.x_root, event.y_root)
                self.add_card(side, press.number, index=gap)
        else:
            side, index = press.source
            roster = self.roster_views[side]
            gap = roster.insertion_index(event.x_root, event.y_root)
            if gap is None:
                self.remove_card(side, index)
            else:
                destination = gap - (gap > index)
                if destination != index:
                    cards = self.rosters[side]
                    cards.insert(destination, cards.pop(index))
                    self.show_roster(side)
                    row = roster.unit_rows[destination]
                    roster.reveal(row)
                    row.focus_set()
        return "break"

    def add_card(self, side, number=None, *, index=None):
        if number is None:
            selection = self.cards.selection()
            number = selection[0] if selection else self.roster_preview
        cards = self.rosters[side]
        if number is not None and self.app.catalog[number].can_add_to(cards):
            index = len(cards) if index is None else index
            cards.insert(index, number)
            self.show_roster(side)
            roster = self.roster_views[side]
            roster.reveal(roster.unit_rows[index])

    def remove_card(self, side, index):
        del self.rosters[side][index]
        self.show_roster(side)
        keys = self.roster_views[side].remove_keys
        (keys[min(index, len(keys) - 1)] if keys else self.add_buttons[side]).focus_set()

    def show_roster(self, side):
        self.clear_drag()
        self.roster_views[side].populate([self.app.catalog[number] for number in self.rosters[side]])
        self.inspect()
        self.update_ready()

    def step_phases(self, delta):
        try:
            count = whole_number(self.phases.get(), "Phase count", 1)
        except ValueError:
            self.phase_entry.focus_set()
        else:
            self.phases.set(f"{max(1, count + delta):02d}")
        return "break"

    def update_ready(self, *_args):
        message = ""
        phase_count = None
        try:
            phase_count = whole_number(self.phases.get(), "Phase count", 1)
        except ValueError as error:
            message = str(error)
        if not all(name.get().strip() for name in self.players):
            message = "Enter both player names."
        elif not message and not all(self.rosters):
            message = "Add at least one published card to each squad."
        self.readiness.configure(text=message or "●  Ready to start", style="Attention.TLabel" if message else "Saved.TLabel")
        self.start_button.state(["disabled"] if message else ["!disabled"])
        self.phase_down.state(["disabled"] if phase_count == 1 else ["!disabled"])
        self.phase_entry.state(["invalid"] if phase_count is None else ["!invalid"])

    def start(self):
        parent = self.app.root
        index = self.scenario.current()
        scenario = self.scenarios[index - 1][0] if index > 0 else None
        try:
            match = Match.new(
                [name.get() for name in self.players], scenario["name"] if scenario else "",
                self.phases.get(), self.rosters, self.app.catalog,
                scenario_id=scenario["id"] if scenario else None,
            )
        except ValueError as error:
            messagebox.showerror("Check The Entry", str(error), parent=parent)
            return
        if self.app.match is not None and not messagebox.askyesno(
            "Replace Saved Match?", "Starting this match will replace the saved match and its undo history.",
            parent=parent,
        ):
            return
        self.app.save(match, parent, replace=True)


class UnitDialog(Dialog):
    def __init__(self, app, unit):
        super().__init__(app.root, "Service Bay")
        self.add_nameplate("Service Bay", {MATCH_CONSOLE: self.cancel})
        self.app, self.unit = app, unit
        match = app.match
        self.read_only = match.winner is not None
        self.hp = tk.StringVar(value=str(unit.hp))
        self.energy = tk.StringVar(value=str(unit.energy))
        self.counter_photos = []
        self.deployment = tk.StringVar(value="Deployed" if unit.deployed else "Reserve")
        self.statuses = {status: tk.BooleanVar(value=status in unit.statuses) for status in STATUS_EFFECTS}
        self.upgrades = {key: tk.IntVar(value=getattr(unit, key)) for key in COUNTED_UPGRADES}
        self.shields = [tk.StringVar(value=state) for state in unit.shields]
        self.keep_extra_shields = tk.BooleanVar(value=True)
        self.note = tk.StringVar(value=unit.note)
        self.phase = tk.StringVar(value=str(unit.phase))
        self.round = tk.StringVar(value=str(unit.round))
        self.rank = tk.StringVar()
        self.fields = {}
        self.inputs = []

        heading = self.workspace.layer(self.body)
        heading.pack(fill="x", pady=(0, 6))
        self.workspace.caption(heading, "Service Bay").pack(side="left")
        self.launch_photo = app.photos.get(launch_mark)
        self.deploy_button = ttk.Button(
            heading, text="Deploy", image=self.launch_photo, compound="left", width=11,
            style="Service.TButton", command=lambda: self.deployment.set("Deployed"),
        )
        self.deploy_button.pack(side="right")
        self.inputs.append(self.deploy_button)
        tray = self.workspace.layer(self.body)
        tray.pack(fill="both", expand=True)
        tray.columnconfigure(0, weight=4)
        tray.columnconfigure(1, weight=7)
        tray.rowconfigure(0, weight=1)

        card_panel = ttk.Frame(tray, style="Panel.TFrame", padding=7)
        card_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel_heading(card_panel, "01", "Unit Inspection").pack(fill="x")
        ttk.Label(card_panel, text=unit.card.name, style="Preview.TLabel", wraplength=230).pack(
            anchor="w", pady=(5, 1),
        )
        ttk.Label(card_panel, text=f"{match.players[unit.player]} · Player {unit.player + 1} / Slot {unit.slot:02d}",
                  style="PanelMuted.TLabel", wraplength=230).pack(anchor="w")
        ttk.Label(card_panel, text=f"{unit.card.title} · {unit.card.number}", style="PanelMuted.TLabel",
                  wraplength=230).pack(anchor="w", pady=(0, 5))
        def view_card(card=unit.card):
            show_card(app, card, parent=self.window, unit_id=unit.id)

        mount = CardMount(card_panel, app, on_open=view_card, width=190, height=150)
        mount.select(unit.card)
        mount.pack(fill="both", expand=True)
        ttk.Button(card_panel, text="View Card", style="Compact.TButton", command=view_card).pack(anchor="e", pady=(4, 0))

        housing = self.workspace.layer(tray)
        housing.grid(row=0, column=1, sticky="nsew")
        form = self.workspace.layer(housing, width=410, height=395)
        scroll = ttk.Scrollbar(housing, orient="vertical", command=form.yview)
        scroll.pack(side="right", fill="y")
        form.pack(side="left", fill="both", expand=True)
        details = self.workspace.layer(form)
        form_window = form.create_window(0, 0, anchor="nw", window=details)
        form.bind("<Configure>", lambda event: form.itemconfigure(form_window, width=event.width), add="+")
        details.bind("<Configure>", lambda _event: form.configure(scrollregion=form.bbox(form_window)), add="+")

        def form_scrolled(first, last):
            scroll.set(first, last)
            self.workspace.align(form)

        form.configure(yscrollcommand=form_scrolled)

        wide = app.root.winfo_screenwidth() / float(app.root.tk.call("tk", "scaling")) >= 960
        details.columnconfigure(0, weight=1)
        if wide:
            details.columnconfigure(1, weight=1)
        state = ttk.Frame(details, style="Panel.TFrame", padding=6)
        state.grid(row=0, column=0, sticky="nsew", padx=(0, 5 if wide else 0), pady=(0, 5))
        self.state_fields(state)
        tokens = ttk.Frame(details, style="Panel.TFrame", padding=6)
        tokens.grid(row=0 if wide else 1, column=1 if wide else 0, sticky="nsew", pady=(0, 5))
        self.upgrade_fields(tokens)
        timeline = ttk.Frame(details, style="Panel.TFrame", padding=6)
        timeline.grid(row=1 if wide else 2, column=0, columnspan=2 if wide else 1, sticky="ew")
        panel_heading(timeline, "04", "Timeline Token").pack(fill="x")
        fields = ttk.Frame(timeline, style="PanelFill.TFrame")
        fields.pack(fill="x", pady=(3, 0))
        fields.columnconfigure(1, weight=1)
        self.number(fields, 0, "Scheduled Phase", self.phase, 1, max(match.phases + 1, unit.phase + 1))
        self.number(fields, 1, "Scheduled Round", self.round, 1, ROUNDS)
        self.ranks = ttk.Combobox(fields, textvariable=self.rank, width=11, state="readonly")
        field(fields, 2, "Stack Position", self.ranks)
        notes = ttk.Entry(fields, textvariable=self.note, width=15)
        field(fields, 3, "Token Notes", notes)
        touch_keyboard(notes, "Unit Token Notes")
        self.inputs.extend((self.ranks, notes))
        self.phase.trace_add("write", self.update_ranks)
        self.round.trace_add("write", self.update_ranks)
        self.update_ranks()

        self.status = ttk.Label(self.footer, text="Read-only · Match complete" if self.read_only else "●  Unit state loaded",
                                style="RailMeta.TLabel", wraplength=345)
        self.status.pack(side="left", fill="x", expand=True)
        self.variables = [self.hp, self.energy, self.deployment, self.phase, self.round, self.rank, self.note,
                          *self.statuses.values(), *self.upgrades.values(), *self.shields, self.keep_extra_shields]
        self.original = self.snapshot()
        for variable in self.variables:
            variable.trace_add("write", self.update_draft)
        if self.read_only:
            for widget in self.inputs:
                widget.state(["disabled"])
            FooterButton(self.footer, text="Close", style="Quiet.TButton", command=self.window.destroy).pack(side="right")
        else:
            self.buttons("Save Unit", self.save)
            self.initial_focus = self.fields["HP"]

        def follow_focus(event):
            widget = event.widget
            if widget in self.inputs and form.bbox(form_window):
                offset = form.canvasy(0)
                top = widget.winfo_rooty() - form.winfo_rooty() + offset
                if top < offset or top + widget.winfo_height() > offset + form.winfo_height():
                    form.yview_moveto(max(0, top - 7) / max(1, details.winfo_height()))

        self.window.bind("<FocusIn>", follow_focus, add="+")
        def scroll_form(event):
            x, y = event.x_root - form.winfo_rootx(), event.y_root - form.winfo_rooty()
            if 0 <= x < form.winfo_width() and 0 <= y < form.winfo_height():
                form.yview_scroll(-int(event.delta / 120), "units")
                return "break"

        self.window.bind("<MouseWheel>", scroll_form, add="+")
        width, height = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
        self.show((min(1390, width - 55), min(720, height - 118)))

    def number(self, parent, row, label, variable, minimum, maximum):
        entry = spinner(parent, variable, minimum, maximum)
        field(parent, row, label, entry)
        self.fields[label] = entry
        self.inputs.append(entry)

    def state_fields(self, state):
        panel_heading(state, "02", "Unit State").pack(fill="x")
        fields = ttk.Frame(state, style="PanelFill.TFrame")
        fields.pack(fill="x", pady=(3, 0))
        fields.columnconfigure(1, weight=1)
        self.vital_counter(fields, 0, "HP", self.hp, SIDES[self.unit.player], maximum=self.unit.card.hp)
        self.vital_counter(fields, 2, "Energy", self.energy, ENERGY_YELLOW)
        ttk.Label(fields, text="STATUS EFFECTS", style="Panel.FieldLabel.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 3),
        )
        statuses = ttk.Frame(fields, style="PanelFill.TFrame")
        statuses.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.status_buttons = {}
        self.status_photos = {
            (status, active): self.app.photos.get(status_art, status, active, 39)
            for status in STATUS_EFFECTS for active in (False, True)
        }
        for index, (status, variable) in enumerate(self.statuses.items()):
            button = ttk.Button(
                statuses, text=status, compound="top", width=9, style="Token.TButton",
                command=lambda variable=variable: variable.set(not variable.get()),
            )
            statuses.columnconfigure(index, weight=1, uniform="statuses")
            button.grid(row=0, column=index, sticky="ew", padx=(0, 3))
            self.status_buttons[status] = button
            self.inputs.append(button)

            def update(*_args, status=status, variable=variable, button=button):
                active = variable.get()
                button.configure(image=self.status_photos[status, active])
                button.state(["selected"] if active else ["!selected"])
                button.state(['disabled'] if self.read_only or (self.deployment.get() == 'Reserve' and not active) else ['!disabled'])

            variable.trace_add("write", update)
            self.deployment.trace_add("write", update)
            update()
        if not self.read_only:
            self.reserve_button = ttk.Button(
                fields, text="Return To Reserve", style="Quiet.TButton", command=lambda: self.deployment.set("Reserve"),
            )
            self.reserve_button.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 1))
            self.inputs.append(self.reserve_button)
        self.deployment.trace_add("write", self.update_deployment)
        self.update_deployment()

    def update_deployment(self, *_args):
        deployed = self.deployment.get() == "Deployed"
        text = "Deployed" if deployed else "Reserve" if self.read_only else "Deploy"
        self.deploy_button.configure(text=text)
        self.deploy_button.state(["disabled"] if self.read_only or deployed else ["!disabled"])
        if not self.read_only:
            self.reserve_button.state(["!disabled"] if deployed else ["disabled"])

    def vital_counter(self, parent, row, label, value, color, *, maximum=None):
        heading = ttk.Frame(parent, style="PanelFill.TFrame")
        heading.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5, 2))
        photo = self.app.photos.get(token_art, label.lower(), 21)
        self.counter_photos.append(photo)
        caption = label.upper() if maximum is None else f"{label} / {maximum}"
        ttk.Label(heading, text=caption, style="Panel.FieldLabel.TLabel", compound="left",
                  image=photo).pack(side="left")
        entry = ttk.Entry(heading, textvariable=value, width=5, justify="center")
        entry.pack(side="right")
        touch_keyboard(entry, label, numeric=True)
        self.fields[label] = entry
        self.inputs.append(entry)
        for key, delta in (("<Up>", 1), ("<Down>", -1)):
            entry.bind(key, lambda _event, delta=delta: self.adjust_count(value, delta, maximum))

        bar = ttk.Frame(parent, style="Well.TFrame")
        bar.grid(row=row + 1, column=0, columnspan=2, sticky="ew")
        minus = ttk.Button(bar, text="−", width=2, style="Compact.TButton",
                           command=lambda: self.adjust_count(value, -1, maximum))
        plus = ttk.Button(bar, text="+", width=2, style="Compact.TButton",
                          command=lambda: self.adjust_count(value, 1, maximum))
        minus.pack(side="left")
        plus.pack(side="right")
        meter = tk.Canvas(bar, background=CELL, highlightthickness=0, height=10, width=70)
        meter.pack(side="left", expand=True, fill="x", padx=6)
        self.inputs.extend((minus, plus))

        def update(*_args):
            amount = self.counter_amount(value)
            can_change = not self.read_only and amount is not None
            minus.state(["!disabled"] if can_change and amount > 0 else ["disabled"])
            plus.state(["!disabled"] if can_change and (maximum is None or amount < maximum) else ["disabled"])
            segments = ENERGY_SEGMENTS if maximum is None else min(24, maximum)
            filled = min(amount or 0, segments) if maximum is None else round(min(amount or 0, maximum) * segments / maximum)
            meter.delete("all")
            draw_segments(meter, 0, 1, meter.winfo_width(), 8, segments, filled, color, tag="vitals")

        meter.bind("<Configure>", update)
        value.trace_add("write", update)
        update()

    def upgrade_fields(self, parent):
        panel_heading(parent, "03", "Upgrades").pack(fill="x")
        self.shield_fields(parent)
        self.upgrade_buttons = {}
        for key in COUNTED_UPGRADES:
            counter = ttk.Frame(parent, style="Well.TFrame", padding=(4, 2))
            counter.pack(fill="x", pady=(3, 0))
            ttk.Label(counter, text=key.title(), style="Well.TLabel").pack(side="left", padx=3)
            self.upgrade_buttons[key] = self.token_counter(counter, self.upgrades[key], key)

    def token_counter(self, parent, value, key):
        photo = self.app.photos.get(upgrade_art, key)
        self.counter_photos.append(photo)
        plus = ttk.Button(parent, text="+", width=2, style="Compact.TButton",
                          command=lambda: self.adjust_count(value, 1))
        plus.pack(side="right")
        icon = ttk.Button(parent, image=photo, textvariable=value, compound="left", width=-3,
                          style="Compact.TButton", command=lambda: self.adjust_count(value, 1))
        icon.pack(side="right", padx=2)
        icon.bind("<Button-3>", lambda _event: self.adjust_count(value, -1))
        icon.bind("<minus>", lambda _event: self.adjust_count(value, -1))
        minus = ttk.Button(parent, text="−", width=2, style="Compact.TButton",
                           command=lambda: self.adjust_count(value, -1))
        minus.pack(side="right")
        self.inputs.extend((minus, icon, plus))

        def update(*_args):
            minus.state(["!disabled"] if self.counter_amount(value) and not self.read_only else ["disabled"])

        value.trace_add("write", update)
        update()
        return icon

    def shield_fields(self, parent):
        ttk.Label(parent, text="Shields", style="Panel.TLabel").pack(anchor="w", pady=(5, 1))
        row = ttk.Frame(parent, style="PanelFill.TFrame")
        row.pack(fill="x")
        self.shield_photos = {
            state: self.app.photos.get(upgrade_art, f"shield_{state}", 39)
            for state in SHIELD_STATES
        }
        self.shield_buttons = []
        for index, shield in enumerate(self.shields):
            button = ttk.Button(row, compound="top", width=10, style="Token.TButton",
                                command=lambda index=index: self.cycle_shield(index))
            row.columnconfigure(index, weight=1, uniform="shields")
            button.grid(row=0, column=index, sticky="ew", padx=(0, 3))
            self.shield_buttons.append(button)
            self.inputs.append(button)

            def update(*_args, index=index, shield=shield, button=button):
                state = shield.get()
                label = {"empty": "Empty", "active": "Active", "spent": "Inactive"}[state]
                button.configure(image=self.shield_photos[state], text=f"{index + 1} {label}")

            shield.trace_add("write", update)
            update()
        if not self.read_only:
            ttk.Label(parent, text="Click to cycle · Empty → Active → Inactive", style="PanelMuted.TLabel").pack(
                anchor="w", pady=(2, 2),
            )
        active, spent = self.unit.extra_shields
        if active or spent:
            keep = ttk.Checkbutton(
                parent, text=f"Keep Older Shields (+{active} Active, +{spent} Inactive)",
                variable=self.keep_extra_shields,
            )
            keep.pack(anchor="w", pady=(1, 3))
            self.inputs.append(keep)

    def cycle_shield(self, index):
        if not self.read_only:
            shield = self.shields[index]
            shield.set(SHIELD_STATES[(SHIELD_STATES.index(shield.get()) + 1) % len(SHIELD_STATES)])

    def adjust_count(self, value, delta, maximum=None):
        if not self.read_only:
            amount = self.counter_amount(value)
            if amount is not None:
                next_amount = max(0, amount + delta)
                value.set(min(next_amount, maximum) if maximum is not None else next_amount)
        return "break"

    @staticmethod
    def counter_amount(value):
        try:
            return whole_number(value.get(), "Amount", 0)
        except ValueError:
            return None

    def update_ranks(self, *_args):
        try:
            phase = whole_number(self.phase.get(), "Scheduled Phase", 1)
            round_number = whole_number(self.round.get(), "Scheduled Round", 1, ROUNDS)
        except ValueError:
            self.ranks.configure(values=("Bottom",))
            self.rank.set("Bottom")
            return
        unit = self.unit
        tokens = self.app.match.tokens(unit.player, phase, round_number)
        if unit in tokens:
            self.ranks.configure(values=[str(rank) for rank in range(1, len(tokens) + 1)])
            self.rank.set(str(tokens.index(unit) + 1))
        else:
            self.ranks.configure(values=["Bottom", *(str(rank) for rank in range(1, len(tokens) + 1))])
            self.rank.set("Bottom")

    def snapshot(self):
        return tuple(variable.get() for variable in self.variables)

    def update_draft(self, *_args):
        dirty = self.snapshot() != self.original
        self.status.configure(text="●  Unsaved unit changes" if dirty else "●  Unit state loaded",
                              style="Attention.TLabel" if dirty else "RailMeta.TLabel")
        for widget in self.fields.values():
            widget.state(["!invalid"])

    def cancel(self):
        if not self.read_only and self.snapshot() != self.original:
            decision = messagebox.askyesnocancel("Unsaved Unit Changes",
                                                "Save the draft before leaving?\nYes: save · No: discard · Cancel: stay.",
                                                parent=self.window)
            if decision is None:
                return
            if decision:
                self.save()
                return
        self.window.destroy()

    def save(self):
        for label, variable, low, high in (
            ("HP", self.hp, 0, self.unit.card.hp), ("Energy", self.energy, 0, None),
            ("Scheduled Phase", self.phase, 1, None), ("Scheduled Round", self.round, 1, ROUNDS),
        ):
            try:
                whole_number(variable.get(), label, low, high)
            except ValueError as error:
                self.status.configure(text=str(error), style="Error.TLabel")
                self.fields[label].state(["invalid"])
                self.fields[label].focus_set()
                return

        deployed = self.deployment.get() == "Deployed"
        changed_deployment = deployed != self.app.match.unit(self.unit.id).deployed

        def edit(match):
            match.edit_unit(
                self.unit.id, hp=self.hp.get(), energy=self.energy.get(),
                deployed=deployed, note=self.note.get(),
                statuses=[status for status, var in self.statuses.items() if var.get()],
                upgrades={key: var.get() for key, var in self.upgrades.items()},
                shield_slots=[shield.get() for shield in self.shields],
                keep_extra_shields=self.keep_extra_shields.get(),
            )
            position = None if self.rank.get() == "Bottom" else self.rank.get()
            match.move_token(self.unit.id, self.phase.get(), self.round.get(), position)

        if self.app.edit(edit, self.window):
            self.window.destroy()
            if changed_deployment:
                self.app.play_hangar_transition(self.unit.id, with_clip=deployed)
        elif self.window.winfo_exists():
            self.status.configure(text="Draft retained · Check the save or entry.", style="Error.TLabel")


def show_card(app, card, *, parent=None, unit_id=None, attacks=(), on_attack=None, sortie=False):
    dialog = Dialog(parent or app.root, "Unit Card")
    dialog.workspace.caption(dialog.body, card.name).pack(anchor="w")
    dialog.workspace.caption(dialog.body, f"{card.title} · {card.number}", "Muted.TLabel").pack(anchor="w")
    screen_width, screen_height = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
    launch = (lambda profile=None: on_attack(dialog.window, profile)) if on_attack is not None else None
    mount = CardMount(dialog.body, app, attacks=attacks, on_attack=launch, sortie=sortie,
                      width=min(840, screen_width - 100), height=min(600, screen_height - 230))
    mount.select(card)
    mount.pack(fill="both", expand=True, pady=(5, 0))
    actions = [FooterButton(dialog.footer, text="Close", style="Quiet.TButton", command=dialog.cancel)]
    if attacks:
        actions.append(FooterButton(dialog.footer, text="Attack", style="Compact.TButton", command=launch))
    weapons = [weapon for weapon in app.remote_weapons.values()
               if unit_id is not None and weapon.parent == card.number]
    if weapons:
        systems = ttk.Frame(dialog.footer, style="RailFill.TFrame")
        controls = []

        def refresh_systems(_event=None):
            unit = app.match.unit(unit_id)
            for weapon, label, button in controls:
                hp = unit.remote_weapon_hp.get(weapon.number)
                label.configure(text=f"{weapon.name} · " + (
                    "In Supply" if hp is None else f"Deployed · HP {hp}/{weapon.hp}"))
                available = (hp is None and unit.deployed and unit.hp > 0
                             and app.match.winner is None)
                button.state(["!disabled"] if available else ["disabled"])

        def deploy(weapon):
            app.deploy_remote_weapon(weapon, unit_id=unit_id, parent=dialog.window)
            refresh_systems()

        for weapon in weapons:
            label = ttk.Label(systems, style="RailMeta.TLabel", width=1)
            label.pack(fill="x")
            button = FooterButton(dialog.footer, text="Deploy RWS", style="Service.TButton",
                                command=lambda weapon=weapon: deploy(weapon))
            actions.append(button)
            controls.append((weapon, label, button))
        systems.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        refresh_systems()
        dialog.window.bind("<FocusIn>", refresh_systems, add="+")
    dialog.footer.columnconfigure(0, weight=1)
    for column, button in enumerate(reversed(actions), 1):
        dialog.footer.columnconfigure(column, uniform="card_actions")
        button.grid(row=0, column=column, sticky="nsew", padx=(6, 0))
    from .card_gestures import CardDismissGesture
    dialog.dismiss_gesture = CardDismissGesture(dialog, mount)
    dialog.show()
    return dialog


def preselect_unit(choice, units, unit_id):
    for index, unit in enumerate(units):
        if unit.id == unit_id:
            choice.current(index)
            break


class TimelineActionDialog(Dialog):
    ACTIONS = {
        "Energize": ("Gain 1 Energy and advance two Timeline spaces.", Match.energize_unit, "+1 Energy"),
        "Dash": ("Advance two Timeline spaces. Move the miniature on the tabletop.", Match.dash_unit, "dashed"),
    }

    def __init__(self, app, player, action):
        super().__init__(app.root, action)
        hint, apply, result = self.ACTIONS[action]
        units = [unit for unit in app.match.units if unit.player == player and unit.deployed]
        self.workspace.caption(self.body, action).pack(anchor="w", pady=(0, 8))
        panel = ttk.Frame(self.body, style="Panel.TFrame", padding=8)
        panel.pack(fill="both", expand=True)
        panel_heading(panel, f"P{player + 1}", "Acting Unit").pack(fill="x")
        choice = UnitPicker(panel, app, [(unit, None) for unit in units])
        choice.pack(fill="x", pady=(8, 5))
        preselect_unit(choice, units, app.selected_id)
        ttk.Label(panel, text=hint if units else "This player has no deployed units.",
                  style="PanelMuted.TLabel").pack(anchor="w")

        def record():
            index = choice.current()
            if index >= 0:
                unit = units[index]
                if app.edit(lambda draft: apply(draft, unit.id), self.window):
                    app.announce(f"●  Saved · {unit.label} {result}")
                    self.window.destroy()
                    if action == "Energize":
                        app.deployment.play_energize(side=unit.player)
                    elif action == "Dash":
                        app.deployment.play_dash(side=unit.player)

        button = self.buttons(action, record)
        if choice.current() < 0:
            button.state(["disabled"])
        choice.bind("<<UnitSelected>>", lambda _event: button.state(["!disabled"]))
        self.initial_focus = choice if units else None
        self.show()


class ScoreDialog(Dialog):
    UNIT_ACTIONS = {
        UNIT_DEFEAT: ("DEFEATED TARGET", "VP AWARD", "Record Defeat"),
        GARRISON_DEFEAT: ("ATTACKING UNIT", "VP AWARD", "Record Defeat"),
        GARRISON_RESCUE: ("RESCUING UNIT", "VP AWARD", "Record Rescue"),
    }
    SCENARIO_GOAL = "Scenario goal"
    ADJUST_VP = "Other adjustment"
    REASON_LABELS = {
        UNIT_DEFEAT: "Unit Defeat",
        GARRISON_DEFEAT: "Garrison Defeated",
        GARRISON_RESCUE: "Garrison Rescue",
        SCENARIO_GOAL: "Scenario Goal",
        ADJUST_VP: "Other Adjustment",
    }

    def __init__(self, app, player, *, reason=UNIT_DEFEAT):
        super().__init__(app.root, "Record Victory Points")
        self.app, self.player = app, player
        self.deployed_units = [[], []]
        for unit in app.match.units:
            if unit.deployed:
                self.deployed_units[unit.player].append(unit)
        self.target_options = []
        self.phase = tk.StringVar(value=str(app.match.phase))
        self.points = tk.StringVar()
        self.note = tk.StringVar()
        self.objective_photo = app.photos.get(objective_art, player)

        self.workspace.caption(self.body, "Record Victory Points").pack(anchor="w", pady=(0, 8))
        panel = ttk.Frame(self.body, style="Panel.TFrame", padding=8)
        panel.pack(fill="both", expand=True)
        identity = ttk.Frame(panel, style=f"Hangar{player}.TFrame", padding=(7, 5))
        identity.pack(fill="x")
        ttk.Frame(identity, width=3, style=f"SideMark{player}.TFrame").pack(side="left", fill="y", padx=(0, 7))
        ttk.Label(identity, text=app.match.players[player], style=f"Side{player}.TLabel", wraplength=380).pack(side="left")
        ttk.Label(identity, text=f"PLAYER {player + 1}", style=f"SideMeta{player}.TLabel").pack(side="right")

        fields = ttk.Frame(panel, style="PanelFill.TFrame")
        fields.pack(fill="x", pady=(8, 0))
        fields.columnconfigure(0, weight=3)
        fields.columnconfigure(1, weight=2)
        self.targets = UnitPicker(fields, app)
        self.points_field = touch_keyboard(ttk.Entry(fields, textvariable=self.points, width=8), "Victory Points", numeric=True)
        self.reason_picker = ttk.Combobox(fields, values=tuple(self.REASON_LABELS.values()), state="readonly", width=19)
        self.reason_picker.set(self.REASON_LABELS[reason])
        self.remote_defeat = ttk.Frame(fields, style="PanelFill.TFrame")
        self.remote_defeat.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.remote_choices = []
        for row, column, span, label, control in (
            (0, 0, 1, "REASON", self.reason_picker),
            (0, 1, 1, "PHASE", spinner(fields, self.phase, 1, app.match.phases)),
            (2, 0, 2, "UNIT", self.targets),
            (5, 0, 1, "NOTE (OPTIONAL)", touch_keyboard(ttk.Entry(fields, textvariable=self.note, width=18), "Scoring Note")),
            (5, 1, 1, "VP ADJUSTMENT", self.points_field),
        ):
            padx = (0, 8) if column == 0 and span == 1 else 0
            caption = ttk.Label(fields, text=label, style="Panel.FieldLabel.TLabel", compound="left")
            caption.grid(
                row=row, column=column, columnspan=span, sticky="w", padx=padx, pady=(3, 2),
            )
            if control is self.reason_picker:
                self.reason_label = caption
            if control is self.targets:
                self.target_label = caption
            if control is self.points_field:
                self.points_label = caption
            control.grid(row=row + 1, column=column, columnspan=span, sticky="ew", padx=padx, pady=(0, 6))
        self.hint = ttk.Label(panel, style="PanelMuted.TLabel")
        self.hint.pack(anchor="w", pady=(1, 0))
        self.reason_picker.bind("<<ComboboxSelected>>", self.update_reason)
        self.targets.bind("<<UnitSelected>>", self.set_target_points)
        self.initial_focus = self.reason_picker
        self.record_button = self.buttons("Record VP", self.record)
        self.update_reason()
        self.show()

    def selected_reason(self):
        return tuple(self.REASON_LABELS)[self.reason_picker.current()]

    def update_reason(self, _event=None):
        reason = self.selected_reason()
        unit_action = reason in self.UNIT_ACTIONS
        unit_defeat = reason == UNIT_DEFEAT
        side = 1 - self.player if unit_defeat else self.player
        units = self.deployed_units[side] if unit_action else []
        systems = [(unit, weapon) for unit in units for weapon in self.deployed_systems(unit)] if unit_defeat else []
        options = [(unit, None) for unit in units] + systems
        if options != self.target_options:
            self.target_options = options
            self.targets.set_options(options)
        unit_label, points_label, action_label = self.UNIT_ACTIONS.get(reason, ("UNIT", "VP ADJUSTMENT", "Record VP"))
        self.reason_label.configure(image=self.objective_photo if reason == self.SCENARIO_GOAL else "")
        self.target_label.configure(text=unit_label)
        if unit_action:
            self.targets.grid()
            self.target_label.grid()
        else:
            self.targets.grid_remove()
            self.target_label.grid_remove()
        self.points_field.configure(state="readonly" if unit_action else "normal")
        self.points_label.configure(text=points_label)
        self.record_button.configure(text=action_label)
        if unit_action and not unit_defeat:
            if self.targets.current() < 0:
                preselect_unit(self.targets, units, self.app.selected_id)
            hint = ('Award 2 VP for a defeat resolved at the table. Enter only unpaid TL.' if reason == GARRISON_DEFEAT
                    else 'Award 2 VP and advance the rescuing unit two Timeline spaces.')
            self.hint.configure(text=hint
                                if units else "This player has no deployed units.")
        elif not unit_action:
            self.hint.configure(text="Use a negative adjustment to correct a score.")
        self.set_target_points()

    def deployed_systems(self, unit):
        for number in unit.remote_weapon_hp:
            weapon = self.app.remote_weapons.get(number)
            if weapon is not None and weapon.parent == unit.card.number:
                yield weapon

    def selected_target(self):
        index = self.targets.current()
        return self.target_options[index] if index >= 0 else (None, None)

    def set_target_points(self, _event=None):
        unit, system = self.selected_target()
        reason = self.selected_reason()
        self.remote_choices.clear()
        for child in self.remote_defeat.winfo_children():
            child.destroy()
        if reason == UNIT_DEFEAT and unit is not None and system is None:
            for weapon in self.deployed_systems(unit):
                checked = tk.BooleanVar(master=self.window)
                self.remote_choices.append((weapon, checked))
                ttk.Checkbutton(
                    self.remote_defeat, text=f"Also Defeated {weapon.name} (+{weapon.vp} VP)",
                    variable=checked, command=self.update_defeat_points, style="Panel.TCheckbutton",
                ).pack(anchor="w")
        if self.remote_choices:
            self.remote_defeat.grid()
            self.window.update_idletasks()
            width = max(self.window.winfo_width(), self.window.winfo_reqwidth())
            height = max(self.window.winfo_height(), self.window.winfo_reqheight())
            if (width, height) != (self.window.winfo_width(), self.window.winfo_height()):
                self.window.geometry(f"{width}x{height}")
        else:
            self.remote_defeat.grid_remove()
        if reason == UNIT_DEFEAT:
            self.update_defeat_points()
            if system is not None:
                hint = "Awards printed VP and returns the system to supply."
            elif unit is not None:
                hint = "Awards printed VP and returns the unit to Reserve."
            else:
                hint = "Choose an opposing unit or system." if self.target_options else "No opposing units are deployed."
            self.hint.configure(text=hint)
        elif reason in self.UNIT_ACTIONS:
            self.points.set(str(GARRISON_POINTS))
        else:
            self.points.set("")
        can_record = unit is not None or reason not in self.UNIT_ACTIONS
        self.record_button.state(["!disabled"] if can_record else ["disabled"])

    def selected_remote_weapons(self):
        return tuple(weapon for weapon, checked in self.remote_choices if checked.get())

    def update_defeat_points(self):
        unit, system = self.selected_target()
        if system is not None:
            self.points.set(str(system.vp))
        else:
            self.points.set(str(unit.card.vp + sum(weapon.vp for weapon in self.selected_remote_weapons())) if unit else "")

    def record(self):
        reason = self.selected_reason()
        unit, system = self.selected_target()
        if reason in self.UNIT_ACTIONS and unit is None:
            self.error("Choose a deployed target." if reason == UNIT_DEFEAT else "Choose a deployed unit.")
            return
        note = self.note.get().strip()
        phase = self.phase.get()
        defeated_weapons = self.selected_remote_weapons()
        score_count = len(self.app.match.scores)

        def apply(match):
            if system is not None:
                match.defeat_remote_weapon(unit.id, system, phase, note=note)
            elif reason == UNIT_DEFEAT:
                match.defeat_unit(unit.id, phase, note=note, defeated_weapons=defeated_weapons)
            elif reason in self.UNIT_ACTIONS:
                match.record_garrison(unit.id, phase, reason, note=note,
                                      unpaid_tl=self.unpaid_tl.get() if hasattr(self, 'unpaid_tl') else 0)
            else:
                match.record_score(self.player, phase, self.points.get(), f"{reason} · {note}" if note else reason)

        if self.app.edit(apply, self.window):
            points = sum(entry.points for entry in self.app.match.scores[score_count:])
            self.app.announce(f"●  Saved · Player {self.player + 1} {points:+d} VP")
            self.window.destroy()
            if reason == UNIT_DEFEAT and points > 0:
                self.app.deployment.play_defeat()
            elif reason in (GARRISON_DEFEAT, GARRISON_RESCUE) and points > 0:
                self.app.deployment.play_garrison(rescue=reason == GARRISON_RESCUE, side=self.player, points=points)
            elif reason == self.SCENARIO_GOAL and points > 0:
                self.app.deployment.play_goal(side=self.player, points=points)


def show_history(app):
    dialog = Dialog(app.root, "Victory Point History")
    match = app.match
    dialog.workspace.caption(dialog.body, "Victory Point History").pack(anchor="w", pady=(0, 8))
    goals = [entry.reason.partition(" · ")[0] == ScoreDialog.SCENARIO_GOAL for entry in match.scores]
    has_goals = any(goals)
    frame, entries = table(dialog.body, (
        ("phase", "Phase", 55, False), ("player", "Player", 115, True), ("points", "VP", 48, False),
        ("reason", "Reason", 350, True),
    ), height=11, portraits=has_goals)
    frame.pack(fill="both", expand=True)
    if has_goals:
        entries.column("#0", width=26, minwidth=26)
        entries.objective_photos = [app.photos.get(objective_art, side) for side in range(2)]
    history_labels = {**ScoreDialog.REASON_LABELS, "RWS defeat": "RWS Defeat"}
    for entry, goal in zip(reversed(match.scores), reversed(goals)):
        photo = entries.objective_photos[entry.player] if goal else ""
        reason, separator, details = entry.reason.partition(" · ")
        label = history_labels.get(reason, reason) + separator + details
        entries.insert("", "end", image=photo, values=(
            entry.phase, match.players[entry.player], f"{entry.points:+d}", label,
        ))
    if not match.scores:
        dialog.workspace.caption(dialog.body, "No VP adjustments recorded yet.", "Muted.TLabel").pack(anchor="w", pady=6)
    FooterButton(dialog.footer, text="Close", command=dialog.window.destroy).pack(side="right")
    dialog.show()


def show_finish(app):
    match = app.match
    dialog = Dialog(app.root, "Finish Match")
    dialog.workspace.caption(dialog.body, "Final Score").pack(anchor="w")
    for side in range(2):
        dialog.workspace.caption(dialog.body, f"{match.players[side]} · {match.total(side)} VP", "TLabel").pack(
            anchor="w", pady=(4, 0),
        )
    choice = None
    if match.total(0) == match.total(1):
        dialog.workspace.caption(dialog.body, "Tied score. Which player acted last?", "TLabel").pack(
            anchor="w", pady=(12, 4),
        )
        choice = ttk.Combobox(dialog.body, values=[
            f"Player {side + 1} · {name}" for side, name in enumerate(match.players)
        ], state="readonly", width=34)
        choice.pack(fill="x")

    def finish():
        last = choice.current() if choice is not None else None
        if app.edit(lambda draft: draft.finish(last), dialog.window):
            dialog.window.destroy()

    dialog.buttons("Finish Match", finish)
    dialog.show()
