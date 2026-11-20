"""Touch controls for the Service Bay workflow."""
import math
import tkinter as tk
from tkinter import ttk

from . import dialogs
from .artwork import upgrade_art
from .catalog import ROUNDS
from .match import whole_number
from .theme import (AMBER, BORDER, CELL, DISABLED, DISABLED_WELL, FOCUS, INK,
                             KEY_FACE, PANEL, button_surface_layout, families,
                             panel_heading, surface_element)


def destination_positions(match, unit, phase, round_number):
    """Only occupied allied slots plus the destination's new last slot are valid."""
    tokens = match.tokens(unit.player, phase, round_number)
    others = [token for token in tokens if token.id != unit.id]
    last = len(others) + 1
    current = next((index + 1 for index, token in enumerate(tokens) if token.id == unit.id), last)
    display_count = max(5, sum(token.player == unit.player for token in match.units))
    return tuple(range(1, display_count + 1)), tuple(range(1, last + 1)), current


def choice_style(root):
    style = ttk.Style(root)
    name = 'TouchChoice.TRadiobutton'
    element = name + '.face'
    if element not in style.element_names():
        surface_element(root, style, element, KEY_FACE, '#788681', radius=4, depth=1,
                        backdrop=PANEL, states=(
                            (('disabled',), DISABLED_WELL, BORDER, 0),
                            (('selected', 'focus'), '#60452E', FOCUS, 0),
                            (('selected',), '#60452E', AMBER, 0),
                            (('focus',), KEY_FACE, FOCUS, 1),
                            (('active',), '#475557', '#A5B2AD', 1),
                        ))
        button_surface_layout(style, name, element)
    _, mono = families(root)
    style.configure(name, font=(mono, -18, 'bold'), foreground=INK, background=PANEL,
                    padding=2, width=0, anchor='center')
    style.map(name, foreground=[('disabled', DISABLED), ('selected', AMBER)])
    return name


class ChoiceRow(ttk.Frame):
    def __init__(self, parent, dialog, variable, values, *, enabled=None, extend=None):
        super().__init__(parent, style='PanelFill.TFrame', width=1, height=44)
        self.dialog, self.variable, self.extend = dialog, variable, extend
        self.options = ()
        self.buttons, self.boxes = [], []
        self.allowed = set()
        self.columns = None
        self.grid_propagate(False)
        self.bind('<Configure>', self.arrange)
        self.set_values(values, enabled=enabled)

    def set_values(self, values, *, enabled=None):
        values = tuple(str(value) for value in values)
        self.allowed = set(str(value) for value in (enabled if enabled is not None else values))
        if values != self.options:
            for button in self.buttons:
                if button in self.dialog.inputs:
                    self.dialog.inputs.remove(button)
            for box in self.boxes:
                box.destroy()
            self.buttons, self.boxes, self.options = [], [], values
            for value in values:
                box = ttk.Frame(self, style='PanelFill.TFrame', width=44, height=44)
                box.pack_propagate(False)
                button = ttk.Radiobutton(box, text=value, value=value, variable=self.variable,
                                         style=choice_style(self.dialog.app.root))
                button.pack(fill='both', expand=True)
                self.boxes.append(box)
                self.buttons.append(button)
                self.dialog.inputs.append(button)
            if self.extend is not None:
                box = ttk.Frame(self, style='PanelFill.TFrame', width=44, height=44)
                box.pack_propagate(False)
                button = ttk.Button(box, text='+', style='TouchBayStep.TButton', command=self.extend)
                button.pack(fill='both', expand=True)
                self.boxes.append(box)
                self.buttons.append(button)
                self.dialog.inputs.append(button)
            self.columns = None
        self.refresh_enabled()
        self.arrange()

    def refresh_enabled(self):
        for index, button in enumerate(self.buttons):
            available = index >= len(self.options) or self.options[index] in self.allowed
            button.state(['!disabled'] if available and not self.dialog.read_only else ['disabled'])

    def state(self, statespec=None):
        result = super().state(statespec)
        if statespec and 'disabled' in statespec:
            for button in self.buttons:
                button.state(['disabled'])
        elif statespec and '!disabled' in statespec:
            self.refresh_enabled()
        return result

    def focus_set(self):
        for value, button in zip(self.options, self.buttons):
            if value == self.variable.get():
                button.focus_set()
                return
        super().focus_set()

    def arrange(self, _event=None):
        width = self.winfo_width()
        columns = min(len(self.boxes), max(1, (width + 4) // 48)) if width > 1 else min(10, len(self.boxes))
        if columns == self.columns:
            return
        self.columns = columns
        for index, box in enumerate(self.boxes):
            box.grid(row=index // columns, column=index % columns, padx=(0, 4), pady=(0, 4))
        self.configure(height=math.ceil(len(self.boxes) / columns) * 48 - 4)


class TouchUnitDialog(dialogs.UnitDialog):
    def __init__(self, app, unit):
        heading, mono = families(app.root)
        style = ttk.Style(app.root)
        style.configure('TouchBayStep.TButton', font=(mono, -26, 'bold'), padding=0)
        style.configure('TouchBayToken.Token.TButton', font=(mono, -18, 'bold'), padding=3)
        for kind in ('Primary', 'Quiet'):
            style.configure(f'TouchBay.{kind}.TButton', font=(heading, -16, 'bold'), padding=(12, 6))
        choice_style(app.root)
        super().__init__(app, unit)

    def number(self, parent, row, label, variable, minimum, maximum):
        if label not in ('Scheduled Phase', 'Scheduled Round'):
            return super().number(parent, row, label, variable, minimum, maximum)
        if label == 'Scheduled Phase':
            self.phase_limit = maximum
            def extend():
                if not self.read_only:
                    self.phase_limit += 1
                    self.phase_choices.set_values(range(1, self.phase_limit + 1))
                    self.phase.set(str(self.phase_limit))
            choices = ChoiceRow(parent, self, variable, range(minimum, maximum + 1), extend=extend)
            self.phase_choices = choices
        else:
            choices = ChoiceRow(parent, self, variable, range(1, ROUNDS + 1))
        ttk.Label(parent, text=label, style='PanelMuted.TLabel').grid(row=row, column=0, sticky='nw', padx=(0, 10), pady=(14, 4))
        choices.grid(row=row, column=1, sticky='ew', pady=4)
        self.fields[label] = choices
        self.inputs.append(choices)

    def update_ranks(self, *_args):
        if not isinstance(self.ranks, ChoiceRow):
            old = self.ranks
            parent = old.master
            old.grid_forget()
            if old in self.inputs:
                self.inputs.remove(old)
            old.destroy()
            self.ranks = ChoiceRow(parent, self, self.rank, range(1, 6))
            self.ranks.grid(row=2, column=1, sticky='ew', pady=4)
            self.inputs.append(self.ranks)
        phase = whole_number(self.phase.get(), 'Scheduled Phase', 1)
        round_number = whole_number(self.round.get(), 'Scheduled Round', 1, ROUNDS)
        values, enabled, selected = destination_positions(self.app.match, self.unit, phase, round_number)
        self.ranks.set_values(values, enabled=enabled)
        self.rank.set(str(selected))

    def upgrade_fields(self, parent):
        panel_heading(parent, '03', 'Upgrades').pack(fill='x')
        self.shield_fields(parent)
        row = ttk.Frame(parent, style='PanelFill.TFrame')
        row.pack(fill='both', expand=True, pady=(14, 6))
        row.columnconfigure((0, 1), weight=1, uniform='upgrades')
        self.upgrade_buttons = {}
        for column, key in enumerate(('strength', 'speed')):
            group = ttk.Frame(row, style='PanelFill.TFrame')
            group.grid(row=0, column=column, padx=6)
            ttk.Label(group, text=key.upper(), style='Panel.FieldLabel.TLabel').pack(pady=(0, 5))
            controls = ttk.Frame(group, style='PanelFill.TFrame')
            controls.pack()
            self.upgrade_buttons[key] = self.token_counter(controls, self.upgrades[key], key)

    def token_counter(self, parent, value, key):
        def button_box(width, height):
            box = ttk.Frame(parent, style='PanelFill.TFrame', width=width, height=height)
            box.pack(side='left', padx=3)
            box.pack_propagate(False)
            return box
        minus = ttk.Button(button_box(44, 44), text='−', style='TouchBayStep.TButton',
                           command=lambda: self.adjust_count(value, -1))
        minus.pack(fill='both', expand=True)
        photo = self.app.photos.get(upgrade_art, key, 44)
        self.counter_photos.append(photo)
        icon = ttk.Button(button_box(78, 78), image=photo, textvariable=value, compound='top',
                          style='TouchBayToken.Token.TButton', command=lambda: self.adjust_count(value, 1))
        icon.pack(fill='both', expand=True)
        icon.bind('<Button-3>', lambda _event: self.adjust_count(value, -1))
        icon.bind('<minus>', lambda _event: self.adjust_count(value, -1))
        plus = ttk.Button(button_box(44, 44), text='+', style='TouchBayStep.TButton',
                          command=lambda: self.adjust_count(value, 1))
        plus.pack(fill='both', expand=True)
        self.inputs.extend((minus, icon, plus))
        def update(*_args):
            minus.state(['!disabled'] if self.counter_amount(value) and not self.read_only else ['disabled'])
        value.trace_add('write', update)
        update()
        return icon

    def buttons(self, text, command):
        buttons = []
        for title, action, kind in ((text, command, 'Primary'), ('Cancel', self.cancel, 'Quiet')):
            box = ttk.Frame(self.footer, style='RailFill.TFrame', width=152, height=48)
            box.pack(side='right', padx=(8, 0))
            box.pack_propagate(False)
            button = ttk.Button(box, text=title, style=f'TouchBay.{kind}.TButton', command=action)
            button.pack(fill='both', expand=True)
            buttons.append(button)
        return buttons[0]
