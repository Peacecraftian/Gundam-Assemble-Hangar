import tkinter as tk
from math import cos, radians, sin
from time import monotonic
from tkinter import font, ttk

from PIL import Image

from .artwork import (
    decal_art, fitted_card, hangar_background, hangar_card, hangar_header, hazard_mark, launch_mark, status_art,
    timeline_portrait, token_art, upgrade_art,
)
from .attack_overlay import AttackOverlay
from .catalog import ROUNDS
from .match import SHIELD_SLOTS, STATUS_EFFECTS
from .remote_overlay import RemoteWeaponOverlay, contains
from .theme import (
    AMBER, AMBER_INK, AMBER_WELL, BORDER, CELL, ENERGY_SEGMENTS, ENERGY_YELLOW, FOCUS, HANGARS, INK, MUTED,
    PANEL, RAIL, SCORE_FAMILY, SERVICE_ORANGE, SIDE_EDGES, SIDES, app_cursor, drag_pose, draw_segments, draw_well,
    families,
)


def fit_text(text, width, face):
    if face.measure(text) <= width:
        return text
    while text and face.measure(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def hit(boxes, x, y):
    return next((key for key, box in boxes.items() if contains(box, x, y)), None)


class Hangar(ttk.Frame):
    HEADER_HEIGHT = 31
    CARD_RATIO = 567 / 800
    IDENTITY_CROP = .275
    WEAPON_NAME_CROP = .322

    def __init__(self, parent, app, side):
        super().__init__(parent, style=f"Hangar{side}.TFrame", padding=(4, 4))
        self.app = app
        self.side = side
        self.last_pick = None
        self.photos = []
        self.vital_photos = {key: app.photos.get(token_art, key, 15) for key in ("hp", "energy")}
        self.status_photos = {}
        self.background_photo = None
        self.header_photo = None
        decal_color = SIDES[0] if side == 0 else None
        self.header_decals = (
            app.photos.get(decal_art, "hangar-chevrons", decal_color, None, Image.Transpose.FLIP_LEFT_RIGHT),
            app.photos.get(decal_art, "hangar-chevrons", decal_color),
        )
        self.background_size = None
        self.door_frame = 0
        self.pinned_top = 0
        self.content_height = 1
        self.face = font.Font(root=self, family="Segoe UI", size=9)
        heading, _mono = families(self)
        self.heading_face = font.Font(root=self, family=heading, size=-16, weight="bold")
        self.deploy_face = font.Font(root=self, family=heading, size=-12, weight="bold")
        self.deploy_photo = app.photos.get(launch_mark, 16)
        self.deploy_width = self.deploy_photo.width() + self.deploy_face.measure("Deploy") + 17
        self.canvas = tk.Canvas(self, background=HANGARS[side], highlightthickness=1, width=1, height=1,
                                highlightbackground=HANGARS[side], highlightcolor=FOCUS, takefocus=True)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrolled)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.draw)
        self.canvas.bind("<Button-1>", self.pick)
        self.canvas.bind("<Double-Button-1>", self.open_card)
        self.canvas.bind("<Motion>", self.hover)
        self.canvas.bind("<Leave>", lambda _event: self.canvas.configure(cursor=""))
        self.canvas.bind("<MouseWheel>", self.scroll)
        self.canvas.bind("<Up>", lambda _event: self.step(-1))
        self.canvas.bind("<Down>", lambda _event: self.step(1))
        self.canvas.bind("<Return>", lambda _event: app.open_unit())
        self.canvas.bind("<space>", self.deploy_selected)
        self.canvas.bind("<FocusIn>", self.on_focus)

    @property
    def units(self):
        return [unit for unit in self.app.match.units if unit.player == self.side]

    def on_focus(self, _event):
        if self.units and all(unit.id != self.app.selected_id for unit in self.units):
            self.app.select_unit(self.units[0].id)

    def scroll(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def scrolled(self, first, last):
        self.scrollbar.set(first, last)
        top = self.canvas.canvasy(1)
        self.canvas.move("pinned", 0, top - self.pinned_top)
        self.pinned_top = top

    def step(self, direction):
        if not self.units:
            return "break"
        current = next((i for i, unit in enumerate(self.units) if unit.id == self.app.selected_id), 0)
        unit = self.units[max(0, min(len(self.units) - 1, current + direction))]
        self.app.select_unit(unit.id)
        self.reveal(unit.id)
        return "break"

    def deploy_selected(self, _event):
        unit_id = self.app.selected_id
        if any(unit.id == unit_id for unit in self.units):
            self.app.deploy_unit(unit_id)
        return "break"

    def reveal(self, unit_id):
        canvas = self.canvas
        bounds = canvas.bbox(f"unit{unit_id}")
        if bounds:
            _, top, _, bottom = bounds
            offset = canvas.canvasy(1)
            if top < offset + self.HEADER_HEIGHT or bottom > offset + canvas.winfo_height() - 2:
                canvas.yview_moveto(max(0, top - self.HEADER_HEIGHT) / self.content_height)

    def draw_background(self, width, height):
        size = width, height
        if size != self.background_size:
            self.background_size = size
            tint = HANGARS[self.side]
            self.background_photo = self.app.photos.get(hangar_background, size, tint, self.door_frame)
            self.header_photo = self.app.photos.get(hangar_header, size, tint, self.HEADER_HEIGHT)
        if self.background_photo is not None:
            self.canvas.create_image(0, self.pinned_top, image=self.background_photo, anchor="nw",
                                     tags=("hangar_background", "pinned"))

    def set_door_frame(self, frame):
        if frame == self.door_frame:
            return
        self.door_frame = frame
        if self.background_size is not None:
            self.background_photo = self.app.photos.get(
                hangar_background, self.background_size, HANGARS[self.side], frame,
            )
            self.canvas.itemconfigure("hangar_background", image=self.background_photo)

    def draw_header(self, width):
        canvas = self.canvas
        top = self.pinned_top
        if self.header_photo is not None:
            canvas.create_image(0, top, image=self.header_photo, anchor="nw", tags=("pinned",))
        else:
            canvas.create_rectangle(0, top, width, top + self.HEADER_HEIGHT, fill=HANGARS[self.side],
                                    width=0, tags=("pinned",))
        canvas.create_line(0, top + self.HEADER_HEIGHT - 1, width, top + self.HEADER_HEIGHT - 1,
                           fill=SIDE_EDGES[self.side], tags=("pinned",))
        player = self.app.match.players[self.side]
        title = f"{player} · Hangar"
        inset = 8
        left, right = self.header_decals
        if left is not None and right is not None:
            clearance = left.width() + 16
            if self.heading_face.measure(title) <= width - 2 * clearance:
                y = top + self.HEADER_HEIGHT / 2
                canvas.create_image(inset, y, image=left, anchor="w", tags=("hangar_decal", "pinned"))
                canvas.create_image(width - inset, y, image=right, anchor="e", tags=("hangar_decal", "pinned"))
                inset = clearance
        title = fit_text(title, width - 2 * inset, self.heading_face)
        canvas.create_text(width / 2, top + self.HEADER_HEIGHT / 2, text=title, font=self.heading_face,
                           fill=SIDES[self.side], tags=("pinned",))

    def draw(self, _event=None):
        canvas = self.canvas
        available, height = canvas.winfo_width() - 2, canvas.winfo_height() - 2
        viewport = height - self.HEADER_HEIGHT
        if available < 60 or viewport < 15:
            return
        previous_scroll = canvas.yview()[0]
        canvas.delete("all")
        self.pinned_top = canvas.canvasy(1)
        self.photos.clear()
        width = min(375, available - 2 * (self.scrollbar.winfo_reqwidth() + 4))
        self.draw_background(available, height)
        units = self.units
        editable = self.app.match.winner is None
        match_count = len(self.app.match.units)
        rows = max(1, len(units), match_count - len(units))
        art_inset = 2
        footer_height = 23
        gap = 5
        roster_inset = 7
        tile_chrome = 2 * art_inset + footer_height + gap
        row_budget = (viewport - 2 * roster_inset + gap) // rows - tile_chrome
        # Leave the complete identification strip intact and scroll crowded squads.
        fitting_width = int(row_budget / (self.CARD_RATIO * self.IDENTITY_CROP))
        width = min(width, max(round(width * .67), fitting_width))
        left = (available - width) // 2
        height = round(width * self.CARD_RATIO)
        identity_height = round(height * self.IDENTITY_CROP)
        weapon_name_height = round(height * self.WEAPON_NAME_CROP)
        displayed = weapon_name_height if weapon_name_height <= row_budget else identity_height
        shield_width = min(24, max(13, width // 10), max(10, identity_height - 4))
        self.shield_photo = None
        if any(unit.shield_active for unit in units):
            self.shield_photo = self.app.photos.get(upgrade_art, "shield_active", shield_width)
        stack_height = len(units) * (displayed + tile_chrome) - gap
        y = self.HEADER_HEIGHT + max(roster_inset, (viewport - stack_height) // 2)
        for unit in units:
            tag = f"unit{unit.id}"
            art_top = y + art_inset
            footer_top = art_top + displayed + art_inset
            bottom = footer_top + footer_height
            selected = unit.id == self.app.selected_id
            canvas.create_rectangle(
                left - art_inset, y, left + width + art_inset, bottom,
                fill=HANGARS[self.side] if selected else CELL,
                outline=AMBER if selected else SIDE_EDGES[self.side], width=2 if selected else 1, tags=(tag,),
            )
            canvas.create_line(left - art_inset + 1, footer_top, left + width + art_inset - 1, footer_top,
                               fill=BORDER, tags=(tag,))
            reserve = not unit.deployed
            photo = self.app.photos.get(hangar_card, unit.card.image, width, height, displayed, reserve)
            if photo is not None:
                self.photos.append(photo)
                canvas.create_image(left, art_top, image=photo, anchor="nw", tags=(tag,))
            else:
                canvas.create_text(left + 6, art_top + displayed / 2,
                                   text=fit_text(unit.card.name, width - 12, self.face),
                                   fill=INK, font=self.face, anchor="w", tags=(tag,))
            shield_right = left + width - 3
            if reserve and editable:
                shield_right = self.draw_deploy(left + width - 5, art_top + 1, height, tag) - 4
            if unit.shield_active:
                self.draw_shields(unit, shield_right, art_top + 2, tag, minimum=left + round(width * .42))
            status_width = self.draw_statuses(unit, left + width, bottom, tag)
            self.draw_summary(
                unit, left + 5, left + width - status_width - 4, bottom - footer_height / 2, selected, tag,
            )
            y = bottom + gap
        self.draw_header(available)
        content_end = y - gap + roster_inset
        self.content_height = max(content_end, viewport + self.HEADER_HEIGHT)
        canvas.configure(scrollregion=(0, 0, available, self.content_height))
        canvas.yview_moveto(previous_scroll)
        if content_end > viewport + self.HEADER_HEIGHT:
            self.scrollbar.place(relx=1, x=-1, y=self.HEADER_HEIGHT + 1, anchor="ne",
                                 relheight=1, height=-self.HEADER_HEIGHT - 2)
        else:
            self.scrollbar.place_forget()

    def draw_deploy(self, right, top, card_height, tag):
        left = right - self.deploy_width
        height = min(24, max(14, round(card_height * .145) - 2))
        bottom = top + height
        center = (top + bottom) / 2
        canvas = self.canvas
        tags = (tag, "deploy")
        canvas.create_rectangle(left, top + 1, right, bottom + 1,
                                fill="#181411", width=0, tags=tags)
        canvas.create_rectangle(left, top, right, bottom,
                                fill=SERVICE_ORANGE, outline="#FFCB87", tags=tags)
        canvas.create_image(left + 6, center, anchor="w", image=self.deploy_photo, tags=tags)
        canvas.create_text(left + self.deploy_photo.width() + 10, center, anchor="w",
                           text="Deploy", fill=AMBER_INK, font=self.deploy_face, tags=tags)
        return left

    def draw_summary(self, unit, left, right, y, selected, tag):
        slot = f"{'◆ ' if selected else ''}{unit.slot:02d}"
        hp, energy = f"{unit.hp}/{unit.card.hp}", str(unit.energy)
        hp_label, energy_label = f"HP {hp}", f"EN {energy}"
        icon_width = sum(photo.width() + 2 for photo in self.vital_photos.values())
        if self.face.measure(f"{slot}{hp_label}{energy_label}") + icon_width + 8 > right - left:
            hp_label, energy_label = hp, energy
        parts = (
            (None, slot),
            ("hp", hp_label),
            ("energy", energy_label),
            (None, "Deployed" if unit.deployed else "Reserve"),
        )
        for key, label in parts:
            photo = self.vital_photos.get(key)
            if photo is not None and left + photo.width() + self.face.measure("…") + 2 <= right:
                self.canvas.create_image(left, y, image=photo, anchor="w", tags=(tag, key))
                left += photo.width() + 2
            if right - left < self.face.measure("…"):
                break
            label = fit_text(label, right - left, self.face)
            self.canvas.create_text(left, y, text=label, font=self.face, fill=INK if selected else MUTED,
                                    anchor="w", tags=(tag,))
            left += self.face.measure(label) + 4

    def draw_shields(self, unit, right, top, tag, *, minimum):
        canvas = self.canvas
        photo = self.shield_photo
        shown = min(unit.shield_active, SHIELD_SLOTS)
        extra = unit.shield_active - shown
        caption = f"+{extra}" if extra else ""
        label_width = self.face.measure(caption) + 4 if extra else 0
        pitch = photo.width() + 1
        left = right - shown * pitch - label_width - 4
        if left < minimum:
            shown, extra = 1, unit.shield_active - 1
            caption = f"+{extra}" if extra else ""
            label_width = self.face.measure(caption) + 4 if extra else 0
            left = right - pitch - label_width - 4
        canvas.create_rectangle(left, top, right, top + photo.height() + 4, fill=CELL, outline=BORDER, tags=(tag,))
        for index in range(shown):
            canvas.create_image(left + 2 + index * pitch, top + 2, image=photo, anchor="nw", tags=(tag, "shield"))
        if extra:
            canvas.create_text(right - 2, top + 2 + photo.height() / 2, text=caption, font=self.face,
                               fill=INK, anchor="e", tags=(tag,))

    def draw_statuses(self, unit, right, bottom, tag):
        statuses = [status for status in STATUS_EFFECTS if status in unit.statuses]
        pitch = 23
        left = right - len(statuses) * pitch
        for index, status in enumerate(statuses):
            if status not in self.status_photos:
                self.status_photos[status] = self.app.photos.get(status_art, status, True, 20)
            x = left + index * pitch
            tags = (tag, "status_badge", f"status:{status}")
            self.canvas.create_rectangle(x, bottom - 21, x + 21, bottom - 2, fill=CELL, outline=BORDER, tags=tags)
            self.canvas.create_image(x + 11, bottom - 11, image=self.status_photos[status], tags=tags)
        return len(statuses) * pitch

    def hover(self, _event):
        tags = self.canvas.gettags("current")
        clickable = self.app.match.winner is None and ("status_badge" in tags or "deploy" in tags)
        self.canvas.configure(cursor=app_cursor(self, "hand2") if clickable else "")

    def card_hit(self):
        tags = self.canvas.gettags("current")
        unit_tag = next((tag for tag in tags if tag.startswith("unit")), None)
        status_tag = next((tag for tag in tags if tag.startswith("status:")), None)
        return (int(unit_tag[4:]) if unit_tag else None, status_tag, "deploy" in tags)

    def pick(self, _event):
        unit_id, status_tag, deploy = self.card_hit()
        self.last_pick = None
        if unit_id is None:
            return
        if deploy:
            self.canvas.configure(cursor="")
            self.app.deploy_unit(unit_id)
        elif status_tag is not None and self.app.match.winner is None:
            self.app.clear_unit_status(unit_id, status_tag.removeprefix("status:"))
        else:
            self.last_pick = unit_id
            self.app.select_unit(unit_id)
            self.canvas.focus_set()

    def open_card(self, event):
        unit_id, status_tag, deploy = self.card_hit()
        if unit_id is not None and unit_id == self.last_pick and status_tag is None and not deploy:
            self.last_pick = None
            self.app.open_unit(unit_id)
        else:
            self.pick(event)


class RemoteWeaponReadout(ttk.Frame):
    def __init__(self, parent, app, weapon):
        super().__init__(parent, style="Rail.TFrame", padding=(5, 3))
        self.weapon = weapon
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=weapon.name, style="RailMeta.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.status = ttk.Label(self, style="RailMeta.TLabel", width=1)
        self.status.grid(row=0, column=1, sticky="ew")
        self.deploy = ttk.Button(self, text="Deploy RWS", style="Service.TButton",
                                 command=lambda: app.deploy_remote_weapon(weapon))
        self.deploy.grid(row=0, column=2, columnspan=2, sticky="e")
        self.damage = ttk.Button(self, text="− HP", width=5, style="Compact.TButton",
                                 command=lambda: app.adjust_remote_weapon_hp(weapon, -1))
        self.damage.grid(row=0, column=2, padx=(0, 2))
        self.repair = ttk.Button(self, text="+ HP", width=5, style="Compact.TButton",
                                 command=lambda: app.adjust_remote_weapon_hp(weapon, 1))
        self.repair.grid(row=0, column=3)

    def update_state(self, unit, live):
        hp = unit.remote_weapon_hp.get(self.weapon.number)
        if hp is None:
            self.status.configure(text="In Supply")
            self.damage.grid_remove()
            self.repair.grid_remove()
            self.deploy.grid()
            self.deploy.state(["!disabled"] if live and unit.deployed and unit.hp > 0 else ["disabled"])
        else:
            self.status.configure(text=f"Deployed · HP {hp}/{self.weapon.hp}")
            self.deploy.grid_remove()
            self.damage.grid()
            self.repair.grid()
            self.damage.state(["!disabled"] if live else ["disabled"])
            self.repair.state(["!disabled"] if live and hp < self.weapon.hp else ["disabled"])


class CardPreview(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="Panel.TFrame", padding=(12, 6))
        self.app = app
        toolbar = ttk.Frame(self, style="PanelFill.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))
        self.hazard = app.photos.get(hazard_mark)
        self.open_button = ttk.Button(
            toolbar, text="Service Bay", style="Service.TButton", image=self.hazard,
            compound="left", command=app.open_unit,
        )
        self.open_button.pack(side="right")
        self.title = ttk.Label(toolbar, style="Preview.TLabel")
        self.title.pack(side="left", fill="x", expand=True)
        footer = ttk.Frame(self, style="Rail.TFrame", padding=(5, 3))
        footer.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(footer, text="View Card", style="Compact.TButton", command=app.view_card).pack(side="right")
        self.attack_button = ttk.Button(footer, text="Attack", style="Compact.TButton", command=app.open_attack)
        readout = ttk.Frame(footer, style="RailFill.TFrame")
        readout.pack(side="left", fill="x", expand=True)
        readout.columnconfigure(0, weight=1)
        self.summary = ttk.Frame(readout, style="RailFill.TFrame")
        self.summary.grid(row=0, column=0, sticky="ew")
        self.hint = ttk.Label(readout, style="RailMeta.TLabel", width=1)
        self.hint.grid(row=0, column=0, sticky="ew")
        self.identity = ttk.Label(self.summary, style="RailMeta.TLabel")
        self.identity.pack(side="left", padx=(0, 4))
        self.vital_readouts = {}
        for key in ("hp", "energy"):
            label = ttk.Label(self.summary, style="RailMeta.TLabel", compound="left")
            label.token_photo = app.photos.get(token_art, key, 17)
            label.configure(image=label.token_photo)
            label.pack(side="left", padx=(0, 5))
            self.vital_readouts[key] = label
        self.status_readouts = {}
        for status in STATUS_EFFECTS:
            label = ttk.Label(self.summary, style="RailMeta.TLabel")
            label.token_photo = app.photos.get(status_art, status, True, 17)
            label.configure(image=label.token_photo)
            self.status_readouts[status] = label
        self.detail = ttk.Label(self.summary, style="RailMeta.TLabel", width=1)
        self.detail.pack(side="left", fill="x", expand=True)
        self.well = ttk.Frame(self, style="Recess.TFrame", padding=2)
        self.well.pack(fill="both", expand=True)
        self.remote_readouts = [RemoteWeaponReadout(self, app, weapon) for weapon in app.remote_weapons.values()]
        self.canvas = tk.Canvas(self.well, background=CELL, highlightthickness=0, width=1, height=1)
        self.canvas.pack(fill="both", expand=True)
        self.remote = RemoteWeaponOverlay(self.canvas, app)
        self.attack = AttackOverlay()
        self.clicked_remote = False
        self.canvas.bind("<Configure>", self.draw)
        self.canvas.bind("<Button-1>", self.adjust)
        self.canvas.bind("<Button-3>", lambda event: self.adjust(event, -1))
        self.canvas.bind("<Double-Button-1>", self.open_card)
        self.canvas.bind("<Motion>", self.hover)
        self.canvas.bind("<Leave>", self.clear_hover)
        heading, mono = families(self)
        self.face = font.Font(root=self, family=heading, size=13, weight="bold")
        self.gauge_label = font.Font(root=self, family=heading, size=-12, weight="bold")
        self.compact_label = font.Font(root=self, family=heading, size=-10, weight="bold")
        self.gauge_value = font.Font(root=self, family=mono, size=-14, weight="bold")
        self.readout_icons = {}
        self.counter_boxes = {}
        self.card_box = None
        self.photo = None
        self.draw()

    def draw(self, _event=None):
        unit = self.app.selected_unit()
        canvas = self.canvas
        canvas.delete("all")
        self.counter_boxes.clear()
        self.card_box = None
        self.photo = None
        profiles = self.app.attack_profiles(unit)
        if profiles and not self.attack_button.winfo_manager():
            self.attack_button.pack(side="right", padx=(0, 4))
        elif not profiles:
            self.attack_button.pack_forget()
        width, height = canvas.winfo_width(), canvas.winfo_height()
        self.title.configure(text=fit_text(unit.label, max(35, width - self.open_button.winfo_reqwidth() - 6), self.face))
        self.draw_summary(unit)
        for readout in self.remote_readouts:
            if readout.weapon.parent == unit.card.number:
                readout.update_state(unit, self.app.match.winner is None)
                if not readout.winfo_manager():
                    readout.pack(side="bottom", fill="x", before=self.well, pady=(3, 0))
            else:
                readout.pack_forget()
        if width < 40 or height < 30:
            self.remote.place(unit.card.number, None, selection=unit.id)
            self.attack.place((), None)
            return
        rail_width = min(128, max(74, width // 5))
        stacked = height >= 136
        if not stacked:
            rail_width = min(rail_width, (width - 76) // 3)
        show_readouts = rail_width >= 56 and width >= rail_width * 2 + 95 and height >= 45
        control_gap = 8
        mount_left, mount_right = 12, width - 12
        if show_readouts:
            mount_left = 7 + rail_width + control_gap
            mount_right = width - mount_left
            if not stacked:
                mount_left += rail_width + 6
        mount_width = mount_right - mount_left
        self.photo = self.app.photos.get(fitted_card, unit.card.image, (mount_width, height - 16))
        if self.photo is not None:
            art_width, art_height = self.photo.width(), self.photo.height()
            left = mount_left + (mount_width - art_width) // 2
            top = (height - art_height) // 2
            canvas.create_image(left, top, image=self.photo, anchor="nw")
            self.card_box = left, top, left + art_width, top + art_height
        else:
            self.card_box = mount_left, 8, mount_right, height - 8
            canvas.create_text((mount_left + mount_right) / 2, height / 2,
                               text=f"{unit.card.number}\nCard image unavailable",
                               fill=MUTED, font=self.gauge_label, width=mount_width, justify="center")
        if show_readouts:
            left = self.card_box[0] - control_gap - rail_width
            if stacked:
                gap = 6
                section = min(115, (height - gap) // 2)
                top = (height - 2 * section - gap) // 2
                self.draw_upgrades(unit, left, top, section, rail_width)
                self.draw_statuses(unit, left, top + section + gap, section, rail_width)
            else:
                left -= rail_width + 6
                self.draw_upgrades(unit, left, 0, height, rail_width)
                self.draw_statuses(unit, left + rail_width + 6, 0, height, rail_width)
            self.draw_vitals(unit, self.card_box[2] + control_gap, height, rail_width)
        self.remote.place(unit.card.number, self.card_box if self.photo else None, selection=unit.id)
        self.attack.place(profiles, self.card_box if self.photo is not None and self.remote.active is None else None)

    def draw_summary(self, unit):
        self.identity.configure(text=f"P{unit.player + 1}")
        self.vital_readouts["hp"].configure(text=f"HP {unit.hp}/{unit.card.hp}")
        self.vital_readouts["energy"].configure(text=f"Energy {unit.energy}")
        for status, label in self.status_readouts.items():
            if status in unit.statuses:
                label.pack(side="left", padx=(0, 2), before=self.detail)
            else:
                label.pack_forget()
        state = "Deployed" if unit.deployed else "Reserve"
        self.detail.configure(text=" · ".join(filter(None, (state, " / ".join(unit.statuses)))))
        self.summary.tkraise()

    def draw_upgrades(self, unit, x, top, height, width):
        total = unit.shield_active + unit.shield_spent
        shields = f"{unit.shield_active}/{total}" if unit.shield_spent else str(total)
        rows = (
            ("shields", "Shields", shields, ("shield_active",)),
            ("speed", "Speed", str(unit.speed), ("speed",)),
            ("strength", "Strength", str(unit.strength), ("strength",)),
        )
        self.draw_counter_panel("UPGRADES", rows, upgrade_art, x, top, height, width)

    def draw_statuses(self, unit, x, top, height, width):
        rows = []
        for status in STATUS_EFFECTS:
            active = status in unit.statuses
            rows.append((status, status, "1" if active else "0", (status, active)))
        self.draw_counter_panel("STATUS CONDITIONS", rows, status_art, x, top, height, width)

    def draw_counter_panel(self, title, rows, artwork, x, top, height, width):
        canvas = self.canvas
        header = 18 if height >= 68 else 0
        label_font = self.gauge_label if header else self.compact_label
        row = min(31, (height - header - 4) // len(rows))
        panel_height = len(rows) * row + header
        top += (height - panel_height) // 2
        draw_well(canvas, x, top, x + width, top + panel_height)
        if header:
            title = title if self.gauge_label.measure(title) <= width - 12 else title.split()[0]
            canvas.create_text(x + 6, top + 9, text=title, fill=MUTED, font=self.gauge_label, anchor="w")
        for index, (counter, label, count, args) in enumerate(rows):
            y = top + header + index * row
            self.counter_boxes[counter] = x, y, x + width, y + row - 1
            if header or index:
                canvas.create_line(x + 1, y, x + width - 1, y, fill=BORDER)
            size = min(22, row - 2)
            icon = (artwork, args, size)
            if icon not in self.readout_icons:
                self.readout_icons[icon] = self.app.photos.get(artwork, *args, size)
            photo = self.readout_icons[icon]
            canvas.create_image(x + 4, y + row / 2, image=photo, anchor="w")
            count_width = self.gauge_value.measure(count)
            label_width = width - photo.width() - count_width - 14
            if label_width >= label_font.measure("…"):
                canvas.create_text(x + photo.width() + 7, y + row / 2,
                                   text=fit_text(label, label_width, label_font), fill=MUTED,
                                   font=label_font, anchor="w")
            canvas.create_text(x + width - 5, y + row / 2, text=count, fill=INK, font=self.gauge_value,
                               anchor="e", tags=(f"{counter}_value",))

    def draw_vitals(self, unit, x, height, width):
        canvas = self.canvas
        row = min(43, (height - 6) // 2)
        top = (height - 2 * row) // 2
        compact = row < 32
        text_y, meter_y, meter_height = (7, row - 5, 3) if compact else (11, row - 10, 5)
        size = 15 if compact else 20
        draw_well(canvas, x, top, x + width, top + 2 * row)
        canvas.create_line(x + 1, top + row, x + width - 1, top + row, fill=BORDER)
        meter_width = width - 12
        hp_slots = min(unit.card.hp, 12, meter_width // 5)
        energy_slots = min(ENERGY_SEGMENTS, meter_width // 6)
        values = (
            ("HP", f"{unit.hp}/{unit.card.hp}", hp_slots, round(unit.hp * hp_slots / unit.card.hp), SIDES[unit.player]),
            ("Energy", str(unit.energy), energy_slots, min(unit.energy, energy_slots), ENERGY_YELLOW),
        )
        for index, (label, value, slots, filled, color) in enumerate(values):
            y = top + index * row
            key = label.lower()
            self.counter_boxes[key] = x, y, x + width, y + row - 1
            if (key, size) not in self.readout_icons:
                self.readout_icons[key, size] = self.app.photos.get(token_art, key, size)
            photo = self.readout_icons[key, size]
            canvas.create_image(x + 5, y + text_y, image=photo, anchor="w", tags=(f"{key}_icon",))
            label_width = width - photo.width() - self.gauge_value.measure(value) - 16
            if key == "energy" and label_width < self.gauge_label.measure(label):
                label = "EN"
            if label_width >= self.gauge_label.measure("…"):
                canvas.create_text(x + photo.width() + 7, y + text_y,
                                   text=fit_text(label, label_width, self.gauge_label),
                                   fill=MUTED, font=self.gauge_label, anchor="w")
            canvas.create_text(x + width - 6, y + text_y, text=value, fill=color, font=self.gauge_value,
                               anchor="e", tags=(f"{key}_value",))
            draw_segments(canvas, x + 6, y + meter_y, meter_width, meter_height, slots, filled, color,
                          tag=f"{key}_meter")

    def hover(self, event):
        self.canvas.delete("counter_hover")
        remote_hint = self.remote.hover(event)
        if remote_hint is not None:
            self.canvas.configure(cursor=app_cursor(self, "hand2"))
            self.hint.configure(text=remote_hint)
            self.hint.tkraise()
            return
        profile = self.attack.target(event)
        if profile is not None:
            self.canvas.configure(cursor=app_cursor(self, "hand2"))
            self.hint.configure(text=f"Roll {profile.name}")
            self.hint.tkraise()
            return
        counter = hit(self.counter_boxes, event.x, event.y)
        if counter is not None and self.app.match.winner is None:
            self.canvas.configure(cursor=app_cursor(self, "hand2"))
            self.canvas.create_rectangle(*self.counter_boxes[counter], outline=AMBER, tags="counter_hover")
            if counter in STATUS_EFFECTS:
                hint = f"{counter} · Left apply · Right clear"
            elif counter == "shields":
                hint = "Shields · Left restore/add · Right spend"
            else:
                hint = "Left +1 · Right −1"
            self.hint.configure(text=hint)
            self.hint.tkraise()
        else:
            self.clear_hover()

    def clear_hover(self, _event=None):
        self.canvas.configure(cursor="")
        self.canvas.delete("counter_hover")
        self.remote.clear_hover()
        self.summary.tkraise()

    def adjust(self, event, delta=1):
        if delta == 1:
            self.clicked_remote = self.remote.click(event)
            if self.clicked_remote:
                self.draw()
                self.hover(event)
                return "break"
            profile = self.attack.target(event)
            if profile is not None:
                self.app.open_attack(profile)
                return "break"
        counter = hit(self.counter_boxes, event.x, event.y)
        if counter is not None and self.app.match.winner is None:
            self.app.adjust_unit_counter(counter, delta)
            if self.canvas.winfo_exists():
                self.hover(event)

    def open_card(self, event):
        if self.remote.click(event):
            self.clicked_remote = True
            self.draw()
            self.hover(event)
            return "break"
        if self.clicked_remote:
            return "break"
        if self.attack.target(event) is not None:
            return "break"
        if self.card_box is not None and contains(self.card_box, event.x, event.y):
            self.app.view_card()
        else:
            self.adjust(event)


class Timeline(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, background=CELL, highlightthickness=0, width=1, height=126)
        self.app = app
        heading, mono = families(self)
        self.face = font.Font(root=self, family=heading, size=10, weight="bold")
        self.dense_face = font.Font(root=self, family=heading, size=8, weight="bold")
        self.meta = font.Font(root=self, family=mono, size=8)
        self.badge = font.Font(root=self, family=mono, size=7, weight="bold")
        self.number_faces = {}
        self.portraits = {}
        self.cell_decals = {}
        self.cells = {}
        self.slots = {}
        self.overflow = {}
        self.offsets = {}
        self.scroll_limits = {}
        self.press = None
        self.stack_press = None
        self.dragging = False
        self.last_tap = None
        self.drag_frame = None
        self.drag_pointer = None
        self.pickup_time = 0
        self.settle_frame = None
        self.settling = None
        self.bind("<Configure>", self.draw)
        self.bind("<ButtonPress-1>", self.start)
        self.bind("<B1-Motion>", self.motion)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<Double-ButtonRelease-1>", self.release_double)
        self.bind("<MouseWheel>", self.scroll)
        self.bind("<Escape>", self.cancel)
        self.bind("<Destroy>", self.stop_animations)

    def draw(self, _event=None):
        self.finish_settle()
        self.delete("all")
        self.portraits.clear()
        self.cell_decals.clear()
        self.cells.clear()
        self.slots.clear()
        self.overflow.clear()
        self.scroll_limits.clear()
        width, height = self.winfo_width(), self.winfo_height()
        if width < 300 or height < 75:
            return
        match = self.app.match
        gutter, header = min(130, max(68, width // 13)), 23
        lane_height = (height - header) // 2
        self.create_text(8, 11, text="ROUND", fill=MUTED, font=self.meta, anchor="w")
        for side in range(2):
            y = header + lane_height * side
            self.create_rectangle(0, y, gutter - 1, y + lane_height - 1,
                                  fill=HANGARS[side], outline=SIDE_EDGES[side])
            center = y + lane_height / 2
            self.create_text(8, center - 9, text=f"PLAYER {side + 1}", fill=SIDES[side], font=self.meta, anchor="w")
            name = fit_text(match.players[side], gutter - 16, self.face)
            self.create_text(8, center + 9, text=name, fill=SIDES[side], font=self.face, anchor="w")
        for round_number in range(1, ROUNDS + 1):
            active = round_number == match.round
            x = gutter + (width - gutter) * (round_number - 1) // ROUNDS
            right = gutter + (width - gutter) * round_number // ROUNDS - 1
            self.create_rectangle(x, 0, right, header - 1,
                                  fill=AMBER_WELL if active else RAIL, outline=AMBER if active else BORDER)
            self.create_text(x + 7, 11, text=f"{round_number:02d}", font=self.meta, anchor="w",
                             fill=AMBER if active else INK)
            if active:
                self.create_text(right - 5, 11, text="CURRENT" if right - x > 74 else "NOW",
                                 font=self.badge, fill=AMBER, anchor="e")
            for side in range(2):
                top = header + side * lane_height
                bounds = (x, top, right, top + lane_height - 1)
                key = side, round_number
                self.cells[key] = bounds
                self.create_rectangle(*bounds, fill=AMBER_WELL if active else PANEL if round_number % 2 else CELL,
                                      outline=AMBER if active else BORDER)
                if round_number % 2 == 0:
                    self.draw_cell_decal(side, bounds)
                self.draw_stack(key, match.tokens(side, match.phase, round_number))
        if self.dragging and self.drag_pointer is not None:
            self.draw_drop_guides(match.unit(self.press[0]), *self.drag_pointer)

    def draw_cell_decal(self, side, bounds):
        left, top, right, bottom = bounds
        size = min(74, right - left - 6), min(50, bottom - top - 6)
        key = side, size
        if key not in self.cell_decals:
            transpose = Image.Transpose.FLIP_TOP_BOTTOM if side else None
            self.cell_decals[key] = self.app.photos.get(decal_art, "pixel-decal", None, size, transpose)
        photo = self.cell_decals[key]
        if photo is not None:
            self.create_image((left + right) / 2, (top + bottom) / 2, image=photo, tags=("timeline_decal",))

    def draw_stack(self, key, units):
        left, top, right, bottom = self.cells[key]
        dense = len(units) >= 4
        columns = 2 if dense else 1
        capacity = 6 if dense else 3
        shown = min(capacity, len(units))
        has_overflow = shown < len(units)
        self.scroll_limits[key] = len(units) - shown
        offset = min(self.offsets.get(key, 0), self.scroll_limits[key])
        height = bottom - top - (14 if has_overflow else 0)
        pitch = min(28 if dense else 43, max(7, (height - 4) // 3))
        width = (right - left - 5) // columns
        for index, unit in enumerate(units[offset:offset + shown]):
            row, col = divmod(index, columns)
            x, y = left + 3 + col * width, top + 2 + row * pitch
            box = (x, y, x + width - 2, y + pitch - 2)
            self.slots[unit.id] = box
            self.draw_token(unit, box, dense)
        if has_overflow:
            box = left + 3, bottom - 13, right - 2, bottom - 1
            self.overflow[key] = box
            side = key[0]
            self.create_rectangle(*box, fill=HANGARS[side], outline=SIDE_EDGES[side])
            self.create_text((left + right) / 2, bottom - 7, text=f"{offset + 1}–{offset + shown}/{len(units)}  ↕",
                             fill=SIDES[side], font=self.meta)

    def draw_token(self, unit, box, dense, *, ghost=False, angle=0):
        """Draw the Number Rail frame and labels around the Unit's source portrait."""
        x, y, right, bottom = box
        color = SIDES[unit.player]
        selected = unit.id == self.app.selected_id or ghost
        tags = ("drag_ghost",) if ghost else (f"token{unit.id}",)
        edge = AMBER if selected else BORDER
        center_x, center_y = (x + right) / 2, (y + bottom) / 2
        sine, cosine = sin(radians(angle)), cos(radians(angle))

        def point(px, py):
            dx, dy = px - center_x, py - center_y
            return center_x + dx * cosine + dy * sine, center_y + dy * cosine - dx * sine

        def rectangle(left, top, right, bottom, **options):
            if angle:
                corners = (point(left, top), point(right, top), point(right, bottom), point(left, bottom))
                self.create_polygon(*corners, tags=tags, **options)
            else:
                self.create_rectangle(left, top, right, bottom, tags=tags, **options)

        rectangle(x + 1, y + 2, right + 1, bottom + (4 if ghost else 1), fill=CELL, width=0)
        rectangle(*box, fill=PANEL, width=0)
        height = max(0, round(bottom - y - 2))
        slot = f"{unit.slot:02d}"
        number_size = min(15, max(8, round(height * .46)), max(5, int(height)),
                          max(8, round((right - x) * .2)))
        if number_size not in self.number_faces:
            self.number_faces[number_size] = font.Font(root=self, family=SCORE_FAMILY, size=-number_size)
        number_face = self.number_faces[number_size]
        number_width = min(max(number_face.measure(slot) + 6, round(height * .82)),
                           (right - x) * (.34 if dense else .45))
        number_right = x + 1 + number_width
        rectangle(x + 1, y + 1, number_right, bottom - 1, fill=color, width=0)
        self.create_text(*point(x + 1 + number_width / 2, center_y),
                         text=slot, fill=CELL, font=number_face, angle=angle, tags=tags)

        face = self.dense_face if dense or height < 19 else self.face
        name_padding = 2 if dense else 4
        portrait_width = max(0, min(int(height * 1.45), int((right - x) * .34),
                                    int(right - number_right - face.measure("…") - 2 * name_padding)))
        filename = unit.card.image
        key = (filename, portrait_width, height, angle)
        photo = None
        if portrait_width >= 8 and height >= 8:
            if key not in self.portraits:
                self.portraits[key] = self.app.photos.get(timeline_portrait, filename, (portrait_width, height), angle)
            photo = self.portraits[key]
        label = unit.card.name
        if photo is not None:
            if angle:
                self.create_image(*point(number_right + portrait_width / 2, y + 1 + height / 2),
                                  image=photo, tags=tags)
            else:
                self.create_image(number_right, y + 1, anchor="nw", image=photo, tags=tags)
        else:
            portrait_width = 0
        name_left = number_right + portrait_width + name_padding
        available = max(1, right - name_left - name_padding)
        if face.measure(label) > available:
            label = label.removesuffix(" (EW)").replace("Gundam ", "", 1)
        self.create_text(*point(name_left, center_y), anchor="w",
                         text=fit_text(label, available, face), fill=INK, font=face, angle=angle, tags=tags)
        rectangle(*box, fill="", outline=edge, width=2 if selected else 1)

    def start(self, event):
        self.finish_settle()
        unit_id = hit(self.slots, event.x, event.y)
        self.stack_press = hit(self.overflow, event.x, event.y)
        if unit_id is not None:
            self.press = (unit_id, event.x, event.y)
            self.focus_set()

    def scroll(self, event):
        cell = hit(self.cells, event.x, event.y)
        if cell is not None and self.press is None and self.scroll_limits[cell]:
            direction = -1 if event.delta > 0 else 1
            self.offsets[cell] = max(0, min(self.scroll_limits[cell], self.offsets.get(cell, 0) + direction))
            self.draw()
        return "break"

    def drop_target(self, unit, x, y):
        cell = hit(self.cells, x, y)
        if cell is None or cell[0] != unit.player:
            return None
        match = self.app.match
        units = match.tokens(unit.player, match.phase, cell[1])
        if cell[1] != unit.round:
            return cell, len(units) + 1
        if hit(self.overflow, x, y) == cell:
            return cell, len(units)
        visible = [(index, self.slots[other.id])
                   for index, other in enumerate((other for other in units if other.id != unit.id), 1)
                   if other.id in self.slots]
        if not visible:
            return cell, units.index(unit) + 1
        for index, (left, top, right, bottom) in visible:
            before = y < (top + bottom) / 2
            if len(units) >= 4 and top - 1 <= y <= bottom + 1:
                before = x < (left + right) / 2
            if before:
                return cell, index
        return cell, visible[-1][0] + 1

    def motion(self, event):
        if self.press is None or self.app.match.winner is not None:
            return
        unit_id, x, y = self.press
        if not self.dragging and max(abs(event.x - x), abs(event.y - y)) < 5:
            return
        self.drag_pointer = event.x, event.y
        if not self.dragging:
            self.dragging = True
            self.last_tap = None
            self.pickup_time = monotonic()
            self.configure(cursor=app_cursor(self, "fleur"))
        unit = self.app.match.unit(unit_id)
        self.draw_drop_guides(unit, event.x, event.y)
        self.draw_drag_ghost()
        if self.drag_frame is None:
            self.drag_frame = self.after(30, self.animate_drag)

    def draw_drop_guides(self, unit, x, y):
        self.delete("drag")
        origin = self.cells.get((unit.player, unit.round))
        if origin is None:
            return
        self.create_rectangle(*origin, outline=FOCUS, dash=(4, 3), width=2, tags="drag")
        if unit.id in self.slots:
            self.create_rectangle(*self.slots[unit.id], fill=CELL, outline=FOCUS, dash=(3, 2), tags="drag")
            left, top, right, bottom = self.slots[unit.id]
            self.create_text((left + right) / 2, (top + bottom) / 2, text="FROM", fill=FOCUS,
                             font=self.badge, tags="drag")
        source = f"Dragging {unit.slot:02d} · Round {unit.round:02d}"
        target = self.drop_target(unit, x, y)
        if target is not None:
            cell, position = target
            self.create_rectangle(*self.cells[cell], outline=AMBER, width=2, tags="drag")
            if cell[1] == unit.round:
                self.mark_insertion(unit, position)
            left, top, right, bottom = self.cells[cell]
            self.create_rectangle(left + 1, bottom - 14, right - 1, bottom - 1, fill=AMBER, width=0, tags="drag")
            self.create_text((left + right) / 2, bottom - 7, text=f"TO {cell[1]:02d} / #{position:02d}",
                             fill=AMBER_INK, font=self.badge, tags="drag")
            self.app.announce(f"{source} → Round {cell[1]:02d}, position {position:02d}", "Attention.TLabel")
        else:
            self.app.announce(f"{source} · Drop within Player {unit.player + 1}'s lane", "Attention.TLabel")

    def draw_drag_ghost(self):
        self.delete("drag_ghost")
        x, y = self.drag_pointer
        unit_id, start_x, _ = self.press
        elapsed = monotonic() - self.pickup_time
        side = 1 if x >= start_x else -1
        angle, lift = drag_pose(elapsed, side)
        width = min(148, self.winfo_width() - 18)
        left = max(9, min(x + 12, self.winfo_width() - width - 9))
        top = max(9, min(y + 10 - lift, self.winfo_height() - 41))
        self.draw_token(self.app.match.unit(unit_id), (left, top, left + width, top + 28),
                        False, ghost=True, angle=angle)

    def animate_drag(self):
        self.draw_drag_ghost()
        self.drag_frame = self.after(30, self.animate_drag)

    def animate_drop(self, unit_id):
        self.finish_settle()
        tag = f"token{unit_id}"
        if unit_id not in self.slots:
            match = self.app.match
            unit = match.unit(unit_id)
            key = unit.player, unit.round
            if self.scroll_limits.get(key, 0):
                stack = match.tokens(unit.player, match.phase, unit.round)
                visible = len(stack) - self.scroll_limits[key]
                self.offsets[key] = max(0, stack.index(unit) - visible + 1)
                self.draw()
        if not self.find_withtag(tag):
            return
        self.tag_raise(tag)
        self.settling = (tag, 0, 0)
        self.settle(((-2, -7), (1, 2), (-1, -2), (0, 0)))

    def settle(self, frames):
        tag, old_x, old_y = self.settling
        (x, y), *remaining = frames
        self.move(tag, x - old_x, y - old_y)
        self.settling = (tag, x, y)
        if remaining:
            self.settle_frame = self.after(35, self.settle, remaining)
        else:
            self.settle_frame = self.settling = None

    def finish_settle(self):
        if self.settle_frame is not None:
            self.after_cancel(self.settle_frame)
            self.settle_frame = None
        if self.settling is not None:
            tag, x, y = self.settling
            self.move(tag, -x, -y)
            self.settling = None

    def stop_animations(self, _event):
        for frame in (self.drag_frame, self.settle_frame):
            if frame is not None:
                self.after_cancel(frame)

    def mark_insertion(self, unit, position):
        stack = self.app.match.tokens(unit.player, unit.phase, unit.round)
        others = [token for token in stack if token.id != unit.id]
        if not others:
            return
        before = position <= len(others)
        adjacent = others[position - 1] if before else others[-1]
        bounds = self.slots.get(adjacent.id)
        if bounds is None:
            return
        left, top, right, bottom = bounds
        if len(stack) >= 4:
            x = left if before else right
            self.create_line(x, top, x, bottom, fill=AMBER, width=3, tags="drag")
        else:
            y = top if before else bottom
            self.create_line(left, y, right, y, fill=AMBER, width=3, tags="drag")

    def clear_drag(self):
        if self.drag_frame is not None:
            self.after_cancel(self.drag_frame)
            self.drag_frame = None
        self.press = None
        self.stack_press = None
        self.dragging = False
        self.drag_pointer = None
        self.configure(cursor="")
        self.delete("drag", "drag_ghost")

    def cancel(self, _event=None):
        if self.dragging:
            self.app.announce("●  Drag canceled · Timeline unchanged")
            self.animate_drop(self.press[0])
        self.last_tap = None
        self.clear_drag()

    def release_double(self, event):
        unit_id = hit(self.slots, event.x, event.y)
        if self.press is not None and not self.dragging and unit_id == self.last_tap == self.press[0]:
            self.last_tap = None
            self.clear_drag()
            self.app.open_unit(unit_id)
        else:
            self.release(event)

    def release(self, event):
        press, stack_press, dragging = self.press, self.stack_press, self.dragging
        self.last_tap = None
        self.clear_drag()
        if press is None:
            if stack_press is not None and hit(self.overflow, event.x, event.y) == stack_press:
                self.app.show_stack(self.app.match.tokens(stack_press[0], self.app.match.phase, stack_press[1]))
            return
        unit_id = press[0]
        if not dragging:
            if hit(self.slots, event.x, event.y) == unit_id:
                self.last_tap = unit_id
                self.app.select_unit(unit_id)
            return
        unit = self.app.match.unit(unit_id)
        target = self.drop_target(unit, event.x, event.y)
        if target is None or self.app.match.winner is not None:
            self.app.announce("●  Drop canceled · Timeline unchanged")
            self.animate_drop(unit_id)
            return
        cell, position = target
        phase, round_number = self.app.match.phase, cell[1]
        if round_number == unit.round and position == self.app.match.tokens(unit.player, phase, round_number).index(unit) + 1:
            self.app.announce("●  Timeline unchanged")
            self.animate_drop(unit_id)
            return
        self.app.select_unit(unit_id)
        if self.app.edit(lambda match: match.move_token(unit_id, phase, round_number, position),
                         self.app.root, refresh=self.draw):
            self.animate_drop(unit_id)
            self.app.announce(f"●  Saved · Unit {unit.slot:02d} → Round {round_number:02d} / position {position:02d}")
