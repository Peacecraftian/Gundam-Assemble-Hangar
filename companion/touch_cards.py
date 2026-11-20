"""Touch-friendly card detail and Hangar readouts."""
import tkinter as tk
from tkinter import font, ttk

from .artwork import fitted_card, hazard_mark, status_art, token_art, upgrade_art
from .attack_overlay import AttackOverlay
from .board import CardPreview, Hangar, RemoteWeaponReadout, fit_text
from .match import cycle_upgrade, toggle_condition
from .remote_overlay import RemoteWeaponOverlay, contains
from .theme import (AMBER, BORDER, CELL, ENERGY_YELLOW, INK, MUTED,
                             RAIL, app_cursor, families)

UPGRADES = ('strength', 'speed', 'shields')
CONDITIONS = ('Disarm', 'Slow', 'Fracture')
HP_PINK = '#FF6494'
ENERGY_PIPS = 5
PIP_WIDTH = 18
PIP_GAP = 2


def draw_meter_pips(canvas, x, y, pitch, count, proportion, color, background, tags):
    """Shared pip geometry; HP and Energy shrink together when space is tight."""
    gap = min(PIP_GAP, pitch / 4)
    for index in range(count):
        left = x + index * pitch
        right = left + pitch - gap
        canvas.create_rectangle(left, y - 4, right, y + 4, fill=background, width=0, tags=tags)
        filled = min(1, max(0, proportion * count - index))
        if filled:
            canvas.create_rectangle(left, y - 4, left + (right - left) * filled, y + 4,
                                    fill=color, width=0, tags=tags)



class TouchCardPreview(CardPreview):
    def __init__(self, parent, app):
        ttk.Frame.__init__(self, parent, style='Panel.TFrame', padding=(12, 6))
        self.app = app
        heading, mono = families(self)
        self.face = font.Font(root=self, family=heading, size=13, weight='bold')
        self.meta = font.Font(root=self, family=mono, size=-11)
        self.count_face = font.Font(root=self, family=mono, size=-16)
        self.header_mode = None
        self.icon_size = None
        self.card_box = None
        self.photo = None
        self.clicked_remote = False
        self.hint_text = ''
        self.header = ttk.Frame(self, style='PanelFill.TFrame')
        self.header.pack(fill='x', pady=(0, 5))
        self.header.columnconfigure(1, weight=1)
        self.title = ttk.Label(self.header, style='Preview.TLabel', width=-1)
        self.title.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.controls = ttk.Frame(self.header, style='PanelFill.TFrame')
        self.header_buttons = {}
        self.header_icons = {}
        self.photos = {}
        style = ttk.Style(self)
        style.configure('TouchStep.TButton', font=(mono, -21), padding=0)
        for index, key in enumerate(('hp', 'energy')):
            group = ttk.Frame(self.controls, style='PanelFill.TFrame')
            group.pack(side='left', padx=(0 if index == 0 else 10, 0))
            for sign, delta in (('−', -1), ('+', 1)):
                if delta == 1:
                    icon = app.photos.get(token_art, key, 27)
                    self.photos[key] = icon
                    label = ttk.Label(group, image=icon, style='Panel.TLabel')
                    label.pack(side='left', padx=3)
                    self.header_icons[key] = label
                box = ttk.Frame(group, width=30, height=30, style='PanelFill.TFrame')
                box.pack(side='left')
                box.pack_propagate(False)
                button = ttk.Button(box, text=sign, style='TouchStep.TButton',
                                    command=lambda key=key, delta=delta: app.adjust_unit_counter(key, delta))
                button.pack(fill='both', expand=True)
                self.header_buttons[key, delta] = button
                self.bind_hint(button, f'{"HP" if key == "hp" else "Energy"} {sign}1')
        self.hazard = app.photos.get(hazard_mark)
        self.open_button = ttk.Button(self.header, text='Service Bay', style='Service.TButton',
                                      image=self.hazard, compound='left', command=app.open_unit)
        self.open_button.grid(row=0, column=2, sticky='e', padx=(8, 0))
        self.header.bind('<Configure>', self.layout_header)

        footer = ttk.Frame(self, style='Rail.TFrame', padding=(5, 3))
        footer.pack(side='bottom', fill='x', pady=(4, 0))
        ttk.Button(footer, text='View Card', style='Compact.TButton', command=app.view_card).pack(side='right')
        self.attack_button = ttk.Button(footer, text='Attack', style='Compact.TButton', command=app.open_attack)
        self.meters = tk.Canvas(footer, background=RAIL, width=1, height=22, highlightthickness=0)
        self.meters.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.meters.bind('<Configure>', self.draw_meters)
        self.remote_readouts = [RemoteWeaponReadout(self, app, weapon) for weapon in app.remote_weapons.values()]
        self.well = ttk.Frame(self, style='Recess.TFrame', padding=2)
        self.well.pack(fill='both', expand=True)
        self.well.columnconfigure(1, weight=1)
        self.well.rowconfigure(0, weight=1)
        self.left = tk.Frame(self.well, background=CELL, width=62)
        self.left.grid(row=0, column=0, sticky='ns')
        self.left.grid_propagate(False)
        self.right = tk.Frame(self.well, background=CELL, width=62)
        self.right.grid(row=0, column=2, sticky='ns')
        self.right.grid_propagate(False)
        self.upgrade_buttons, self.counts, self.status_buttons = {}, {}, {}
        for rail in (self.left, self.right):
            rail.columnconfigure(0, weight=1)
            for row in range(3):
                rail.rowconfigure(row, weight=1, uniform='icons')
        for row, key in enumerate(UPGRADES):
            group = tk.Frame(self.left, background=CELL)
            group.grid(row=row, column=0)
            button = self.icon_button(group, lambda key=key: self.acquire(key))
            button.pack()
            self.upgrade_buttons[key] = button
            count = tk.Label(group, text='0', font=self.count_face, foreground=INK, background='#414F52',
                             width=3, borderwidth=1, relief='solid', pady=0)
            count.pack(pady=(1, 0))
            self.counts[key] = count
            self.bind_hint(button, f'{key.title()} · tap to add · 8 → 0')
        for row, status in enumerate(CONDITIONS):
            button = self.icon_button(self.right, lambda status=status: self.toggle(status))
            button.grid(row=row, column=0)
            self.status_buttons[status] = button
            self.bind_hint(button, f'{status} · tap to toggle')
        self.canvas = tk.Canvas(self.well, background=CELL, highlightthickness=0, width=1, height=1)
        self.canvas.grid(row=0, column=1, sticky='nsew')
        self.remote = RemoteWeaponOverlay(self.canvas, app)
        self.attack = AttackOverlay()
        self.canvas.bind('<Configure>', self.draw)
        self.canvas.bind('<Button-1>', self.adjust)
        self.canvas.bind('<Double-Button-1>', self.open_card)
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Leave>', self.clear_hover)
        self.bind('<Configure>', self.layout_space)
        self.layout_space()
        self.draw()

    def layout_space(self, _event=None):
        # Reserve usable icon targets on a 768px desktop, with a compact
        # fallback for the legacy minimum window size.
        minimum = 160 if self.app.root.winfo_height() >= 680 else 0
        if self.well.grid_rowconfigure(0, 'minsize') != minimum:
            self.well.rowconfigure(0, minsize=minimum)
            self.app.view.rowconfigure(3, minsize=250 if minimum else 115)

    def icon_button(self, parent, command):
        return tk.Button(parent, command=command, background=CELL, activebackground=CELL,
                         foreground=INK, borderwidth=0, relief='flat', padx=2, pady=2,
                         highlightthickness=1, highlightbackground=CELL, highlightcolor=AMBER,
                         cursor=app_cursor(self, 'hand2'), takefocus=True)

    def bind_hint(self, widget, text):
        widget.bind('<Enter>', lambda _event: self.set_hint(text), add='+')
        widget.bind('<FocusIn>', lambda _event: self.set_hint(text), add='+')
        widget.bind('<Leave>', self.clear_hover, add='+')
        widget.bind('<FocusOut>', self.clear_hover, add='+')

    def set_hint(self, text):
        self.hint_text = text
        self.draw_meters()

    def layout_header(self, _event=None):
        width = self.header.winfo_width()
        mode = 'full' if width >= 600 else 'compact'
        if mode != self.header_mode:
            self.header_mode = mode
            self.controls.grid(row=0, column=1)
            self.open_button.configure(image=self.hazard if mode == 'full' else '')
            for key, label in self.header_icons.items():
                icon = self.app.photos.get(token_art, key, 27 if mode == 'full' else 20)
                self.photos[key] = icon
                label.configure(image=icon)
        occupied = self.open_button.winfo_reqwidth() + self.controls.winfo_reqwidth() + 20
        self.title.configure(text=fit_text(self.app.selected_unit().label, max(20, min(220, width - occupied)), self.face))

    def acquire(self, key):
        unit_id = self.app.selected_id
        self.app.edit(lambda draft: cycle_upgrade(draft, unit_id, key), self.app.root,
                      refresh=self.app.refresh_unit_display)

    def toggle(self, status):
        unit_id = self.app.selected_id
        self.app.edit(lambda draft: toggle_condition(draft, unit_id, status), self.app.root,
                      refresh=self.app.refresh_unit_display)

    def draw(self, _event=None):
        unit = self.app.selected_unit()
        live = self.app.match.winner is None
        self.layout_header()
        for (key, delta), button in self.header_buttons.items():
            value = getattr(unit, key)
            allowed = live and (value > 0 if delta < 0 else key != 'hp' or value < unit.card.hp)
            button.state(['!disabled'] if allowed else ['disabled'])
        height = self.canvas.winfo_height()
        compact = height < 200
        self.count_face.configure(size=-10 if compact else -16)
        count_height = 14 if compact else 22
        size = min(48, max(42 if self.app.root.winfo_height() >= 680 else 10,
                           (height - 6) // 3 - count_height - 7))
        rail_width = size + 16
        self.left.configure(width=rail_width)
        self.right.configure(width=rail_width)
        for key, button in self.upgrade_buttons.items():
            art_key = 'shield_active' if key == 'shields' else key
            photo = self.app.photos.get(upgrade_art, art_key, size)
            self.photos[key] = photo
            button.configure(image=photo, state='normal' if live else 'disabled')
            value = unit.shield_active + unit.shield_spent if key == 'shields' else getattr(unit, key)
            self.counts[key].configure(text=str(value))
        for status, button in self.status_buttons.items():
            active = status in unit.statuses
            photo = self.app.photos.get(status_art, status, active, size)
            self.photos[status] = photo
            button.configure(image=photo, state='normal' if live and (unit.deployed or active) else 'disabled', relief='sunken' if active else 'flat')
        profiles = self.app.attack_profiles(unit)
        if profiles and not self.attack_button.winfo_manager():
            self.attack_button.pack(side='right', padx=(0, 4), before=self.meters)
        elif not profiles:
            self.attack_button.pack_forget()
        for readout in self.remote_readouts:
            if readout.weapon.parent == unit.card.number:
                readout.update_state(unit, live)
                if not readout.winfo_manager():
                    readout.pack(side='bottom', fill='x', before=self.well, pady=(3, 0))
            else:
                readout.pack_forget()
        self.draw_meters()
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.delete('all')
        self.card_box = None
        self.photo = None
        if width > 24 and height > 24:
            self.photo = self.app.photos.get(fitted_card, unit.card.image, (width - 12, height - 16))
            if self.photo is not None:
                left, top = (width - self.photo.width()) // 2, (height - self.photo.height()) // 2
                self.canvas.create_image(left, top, image=self.photo, anchor='nw')
                self.card_box = left, top, left + self.photo.width(), top + self.photo.height()
            else:
                self.canvas.create_text(width / 2, height / 2, text='Card image unavailable', fill=MUTED)
        self.remote.place(unit.card.number, self.card_box, selection=unit.id)
        self.attack.place(profiles, self.card_box if self.remote.active is None else None)

    def draw_meters(self, _event=None):
        unit = self.app.selected_unit()
        canvas = self.meters
        canvas.delete('all')
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if self.hint_text:
            canvas.create_text(3, height / 2, text=fit_text(self.hint_text, max(10, width - 6), self.meta),
                               anchor='w', fill=INK, font=self.meta)
            return
        state_width = 76 if width >= 310 else 0
        texts = (f'{unit.hp}/{unit.card.hp}', str(unit.energy))
        number_widths = tuple(self.meta.measure(text) + 6 for text in texts)
        overhead = 2 * (23 + 8) + sum(number_widths)
        pitch = min(PIP_WIDTH + PIP_GAP, max(1, (width - state_width - overhead) / (10 + ENERGY_PIPS)))
        x = 0
        for index, (key, value, maximum, slots, color) in enumerate((
                ('hp', unit.hp, unit.card.hp, 10, HP_PINK),
                ('energy', unit.energy, ENERGY_PIPS, ENERGY_PIPS, ENERGY_YELLOW))):
            footer_icon = self.app.photos.get(token_art, key, 17)
            self.photos[key + '_footer'] = footer_icon
            canvas.create_image(x + 10, height / 2, image=footer_icon)
            bar_width = slots * pitch
            draw_meter_pips(canvas, x + 23, height / 2, pitch, slots,
                            min(1, value / maximum), color, BORDER, ('vitals', key))
            canvas.create_text(x + 23 + bar_width + 4, height / 2, text=texts[index],
                               anchor='w', fill=INK, font=self.meta)
            x += 23 + bar_width + number_widths[index] + 8
        if state_width:
            canvas.create_text(width - state_width + 5, height / 2, text='DEPLOYED' if unit.deployed else 'RESERVE',
                               fill=MUTED, font=self.meta, anchor='w')

    def hover(self, event):
        hint = self.remote.hover(event)
        profile = self.attack.target(event)
        if hint is not None or profile is not None:
            self.canvas.configure(cursor=app_cursor(self, 'hand2'))
            self.set_hint(hint if hint is not None else f'Roll {profile.name}')
        else:
            self.clear_hover()

    def clear_hover(self, _event=None):
        self.hint_text = ''
        if hasattr(self, 'canvas'):
            self.canvas.configure(cursor='')
            self.remote.clear_hover()
        if hasattr(self, 'meters'):
            self.draw_meters()

    def adjust(self, event):
        self.clicked_remote = self.remote.click(event)
        if self.clicked_remote:
            self.draw()
            return 'break'
        profile = self.attack.target(event)
        if profile is not None:
            self.app.open_attack(profile)
            return 'break'

    def open_card(self, event):
        if self.clicked_remote or self.attack.target(event) is not None:
            return 'break'
        if self.card_box is not None and contains(self.card_box, event.x, event.y):
            self.app.view_card()


# Keep the normal Hangar card layout, selection, deployment, and status badges.
# Preserve Hangar interactions while replacing its compact vital readout.
def hangar_vital_icon(key, deployed, size=16):
    from PIL import ImageEnhance
    image = token_art(key, size)
    return image if deployed else ImageEnhance.Brightness(image).enhance(.45)


class TouchHangar(Hangar):
    def __init__(self, parent, app, side):
        super().__init__(parent, app, side)
        _, mono = families(self)
        self.meter_face = font.Font(root=self, family=mono, size=-10)
        self.meter_icons = {(key, deployed, size): app.photos.get(hangar_vital_icon, key, deployed, size)
                            for key in ('hp', 'energy') for deployed in (False, True) for size in (12, 16)}

    def draw_summary(self, unit, left, right, y, selected, tag):
        canvas = self.canvas
        available = right - left
        # Preserve copy numbers so duplicate Mass Produced cards remain identifiable.
        slot = f'{unit.slot:02d}'
        canvas.create_text(left, y, text=slot, anchor='w', font=self.meter_face,
                           fill=INK if selected else MUTED, tags=(tag,))
        left += self.meter_face.measure(slot) + 5
        state = ('DEPLOYED' if unit.deployed else 'RESERVE') if available >= 210 else ('DEP' if unit.deployed else 'RSV')
        if available < 130:
            state = 'D' if unit.deployed else 'R'
        state_width = self.meter_face.measure(state) + 8
        canvas.create_text(right, y, text=state, anchor='e', font=self.meter_face,
                           fill=INK if unit.deployed else MUTED, tags=(tag,))
        content_width = max(2, right - left - state_width)
        icon_size = 16 if content_width >= 190 else 12
        overflow = f'+{unit.energy - ENERGY_PIPS}' if unit.energy > ENERGY_PIPS else ''
        if overflow and content_width < 160:
            overflow = '+'
        overflow_width = self.meter_face.measure(overflow) + 2 if overflow else 0
        overhead = 2 * (icon_size + 8) + overflow_width
        pitch = min(PIP_WIDTH + PIP_GAP, max(1, (content_width - overhead) / (8 + ENERGY_PIPS)))
        x = left
        for key, amount, maximum, segments, color in (
                ('hp', unit.hp, unit.card.hp, 8, HP_PINK if unit.deployed else '#773549'),
                ('energy', unit.energy, ENERGY_PIPS, ENERGY_PIPS, ENERGY_YELLOW if unit.deployed else '#80643F')):
            icon = self.meter_icons[key, unit.deployed, icon_size]
            canvas.create_image(x + icon_size / 2, y, image=icon, tags=(tag, key))
            bar_left = x + icon_size + 4
            draw_meter_pips(canvas, bar_left, y, pitch, segments,
                            min(1, max(0, amount / maximum)), color,
                            '#374043' if unit.deployed else '#292F30', (tag, key))
            x += icon_size + 8 + segments * pitch
            if key == 'energy' and overflow:
                canvas.create_text(x - 4, y, text=overflow, anchor='w', font=self.meter_face,
                                   fill=color, tags=(tag, key))
