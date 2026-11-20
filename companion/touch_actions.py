"""Touch layouts for unit actions and dice, preserving shared game workflows."""
import tkinter as tk
from tkinter import ttk
from . import dialogs, dice_dialog
from .attacks import MAX_DICE
from .match import GARRISON
from .theme import PANEL, families, panel_heading
from .touch_service import choice_style, TouchUnitDialog
from .touch_scores import TouchLineup, TouchScoreDialog


def touch_styles(root):
    heading, mono = families(root)
    style = ttk.Style(root)
    choice = choice_style(root)
    for name in ('TouchActionChoice.TRadiobutton', 'TouchScoreUnit.TRadiobutton'):
        style.layout(name, style.layout(choice))
        style.configure(name, font=(heading, -16, 'bold'), foreground='#F2EDE0', padding=8,
                        anchor='center', width=0, wraplength=180)
        style.map(name, foreground=[('selected', '#FFB762')])
    style.configure('TouchScore.PanelMuted.TLabel', font=(heading, -15))
    style.configure('TouchAction.Panel.FieldLabel.TLabel', font=(mono, -13))
    style.configure('TouchAction.TEntry', font=(mono, -22), padding=(8, 8))
    style.configure('TouchBayStep.TButton', font=(mono, -24, 'bold'), padding=0)
    for kind in ('Primary', 'Quiet'):
        style.configure(f'TouchBay.{kind}.TButton', font=(heading, -16, 'bold'), padding=(12, 6))
        style.configure(f'TouchTray.{kind}.TButton', font=(heading, -16, 'bold'), padding=(14, 12), width=14)


class Stepper(ttk.Frame):
    """48px tap controls retain direct text entry and existing range validation."""
    def __init__(self, parent, variable, minimum, maximum, *, quick=False):
        super().__init__(parent, style='PanelFill.TFrame')
        self.variable, self.minimum, self.maximum = variable, minimum, maximum
        self.buttons = []
        for delta in ((-5, -1) if quick else (-1,)):
            self.add_button(delta)
        self.entry = ttk.Entry(self, textvariable=variable, width=5, justify='center',
                               font=(families(parent)[1], -22, 'bold'), style='TouchAction.TEntry')
        self.entry.pack(side='left', fill='y', padx=6)
        dialogs.touch_keyboard(self.entry, 'Enter Number', numeric=True)
        for delta in ((1, 5) if quick else (1,)):
            self.add_button(delta)
        self.trace = variable.trace_add('write', self.refresh)
        self.bind('<Destroy>', self.cleanup)
        self.refresh()

    def add_button(self, delta):
        box = ttk.Frame(self, style='PanelFill.TFrame', width=54, height=48)
        box.pack(side='left', padx=3)
        box.pack_propagate(False)
        button = ttk.Button(box, text=f'{delta:+d}', style='TouchBayStep.TButton', command=lambda: self.adjust(delta))
        button.pack(fill='both', expand=True)
        self.buttons.append((delta, button))

    def adjust(self, delta):
        try:
            value = int(self.variable.get().strip() or '0')
        except ValueError:
            self.entry.focus_set()
            self.entry.selection_range(0, 'end')
            return
        self.variable.set(str(max(self.minimum, min(self.maximum, value+delta))))

    def refresh(self, *_args):
        try:
            value = int(self.variable.get())
        except ValueError:
            value = None
        for delta, button in self.buttons:
            available = value is None or (value > self.minimum if delta < 0 else value < self.maximum)
            button.state(['!disabled'] if available else ['disabled'])

    def cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove('write', self.trace)


class TouchBody:
    buttons = TouchUnitDialog.buttons
    reveal_focus = TouchScoreDialog.reveal_focus

    def touch_body(self, title, *, height=560, width=900):
        self.workspace.caption(self.body, title).pack(anchor='w', pady=(0, 10))
        shell = ttk.Frame(self.body, style='Panel.TFrame', padding=10)
        shell.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(shell, background=PANEL, highlightthickness=0, width=width, height=height)
        scroll = ttk.Scrollbar(shell, command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        panel = ttk.Frame(self.canvas, style='PanelFill.TFrame', padding=8)
        mount = self.canvas.create_window(0, 0, anchor='nw', window=panel)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(mount, width=e.width))
        panel.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.window.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta/120), 'units'))
        self.window.bind('<FocusIn>', self.reveal_focus, add='+')
        return panel


class TouchTimelineAction(TouchBody, dialogs.TimelineActionDialog):
    def __init__(self, app, player, action):
        dialogs.Dialog.__init__(self, app.root, action)
        touch_styles(app.root)
        self.app = app
        hint, apply, result = self.ACTIONS[action]
        units = [unit for unit in app.match.units if unit.player == player and unit.deployed]
        panel = self.touch_body(action, height=330)
        panel_heading(panel, f'P{player+1}', f'{app.match.players[player]} · Acting Unit').pack(fill='x', pady=(0, 10))
        self.choice = TouchLineup(panel, app)
        self.choice.set_options([(unit, None) for unit in units])
        self.choice.pack(fill='x', pady=(0, 14))
        dialogs.preselect_unit(self.choice, units, app.selected_id)
        ttk.Label(panel, text=hint if units else 'This player has no deployed units.',
                  style='TouchScore.PanelMuted.TLabel', wraplength=850).pack(fill='x')

        def record():
            index = self.choice.current()
            if index >= 0:
                unit = units[index]
                if app.edit(lambda draft: apply(draft, unit.id), self.window):
                    app.announce(f'●  Saved · {unit.label} {result}')
                    self.window.destroy()
                    if action == 'Energize':
                        app.deployment.play_energize(side=unit.player)
                    elif action == 'Dash':
                        app.deployment.play_dash(side=unit.player)
        self.confirm = self.buttons(action, record)
        if self.choice.current() < 0:
            self.confirm.state(['disabled'])
        self.choice.bind('<<UnitSelected>>', lambda e: self.confirm.state(['!disabled']))
        self.initial_focus = self.choice if units else None
        self.show((980, 500))


class TouchDicePrompt(TouchBody, dice_dialog.DicePrompt):
    def __init__(self, parent, *, unit=None, profiles=(), selected=None, app=None):
        dialogs.Dialog.__init__(self, parent, 'Attack Roll' if unit else 'Roll D10s')
        touch_styles(parent._root())
        self.unit, self.profiles, self.app = unit, profiles, app
        self.revision = app.revision if app is not None else None
        self.targets = []
        self.strength = tk.StringVar(self.window, '0' if unit else '1')
        self.accuracy = tk.StringVar(self.window, '0')
        self.pool = tk.StringVar(self.window)
        self.weapon_index = tk.IntVar(self.window, profiles.index(selected) if selected else 0)
        panel = self.touch_body('Attack Roll' if unit else 'Roll D10s', height=650 if unit else 220, width=900 if unit else 560)
        panel_heading(panel, 'D10', unit.label if unit else 'Dice Tray').pack(fill='x', pady=(0, 12))
        if unit:
            ttk.Label(panel, text='WEAPON', style='TouchAction.Panel.FieldLabel.TLabel').pack(anchor='w')
            weapons = ttk.Frame(panel, style='PanelFill.TFrame')
            weapons.pack(fill='x', pady=(6, 10))
            weapons.columnconfigure((0, 1), weight=1, uniform='weapons')
            for index, profile in enumerate(profiles):
                box = ttk.Frame(weapons, style='PanelFill.TFrame', height=56, width=1)
                box.grid(row=index//2, column=index%2, sticky='ew', padx=4, pady=3)
                box.pack_propagate(False)
                weapon_button = ttk.Radiobutton(box, text=profile.name, variable=self.weapon_index, value=index,
                    style='TouchActionChoice.TRadiobutton', command=self.update_pool)
                weapon_button.pack(fill='both', expand=True)
                if index == 0:
                    self.initial_focus = weapon_button
            self.printed = ttk.Label(panel, style='TouchScore.PanelMuted.TLabel')
            self.printed.pack(anchor='w', pady=(0, 12))
            self.upgrades = tk.StringVar(self.window, str(unit.strength))
        fields = ttk.Frame(panel, style='PanelFill.TFrame')
        fields.pack(fill='x', pady=(0, 12))
        fields.columnconfigure(0, weight=1)
        self.steppers = {}
        rows = [('STRENGTH UPGRADES', self.upgrades, 0, max(MAX_DICE, unit.strength)),
                ('OTHER STRENGTH MODIFIER', self.strength, -MAX_DICE, MAX_DICE),
                ('ACCURACY MODIFIER', self.accuracy, -99, 99)] if unit else [('NUMBER OF DICE', self.strength, 1, MAX_DICE)]
        for row, (label, variable, minimum, maximum) in enumerate(rows):
            ttk.Label(fields, text=label, style='TouchAction.Panel.FieldLabel.TLabel').grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)
            stepper = Stepper(fields, variable, minimum, maximum, quick=not unit)
            stepper.grid(row=row, column=1, sticky='e', pady=6)
            self.steppers[label] = stepper
        ttk.Label(panel, textvariable=self.pool, style='TouchScore.PanelMuted.TLabel').pack(anchor='w', pady=(0, 10))
        if unit:
            self.upgrades.trace_add('write', self.update_pool)
            ttk.Label(panel, text='Check range and line of sight at the table before declaring.',
                      style='TouchScore.PanelMuted.TLabel', wraplength=850).pack(fill='x', pady=(0, 12))
        if unit and app is not None:
            self.targets = [target for target in app.match.units if target.deployed and target.player != unit.player]
            ttk.Label(panel, text='TARGET', style='TouchAction.Panel.FieldLabel.TLabel').pack(anchor='w')
            self.targets.append(GARRISON)
            self.target_choice = TouchLineup(panel, app)
            self.target_choice.set_options([(target, None) for target in self.targets])
            self.target_choice.pack(fill='x', pady=(6, 10))
            if len(self.targets) <= 2:
                self.target_choice.current(0)
            ttk.Label(panel, text='Declaring pays the weapon TL before rolling. Undo takes back the whole attack.',
                      style='TouchScore.PanelMuted.TLabel', wraplength=850).pack(fill='x')
        self.initial_focus = self.initial_focus or next(iter(self.steppers.values())).entry
        self.roll_button = self.buttons('Declare & Roll' if unit else 'Roll Dice', self.roll)
        if unit and app is not None and not self.targets:
            self.roll_button.state(['disabled'])
        self.window.bind('<Return>', lambda e: self.roll())
        self.strength.trace_add('write', self.update_pool)
        self.update_pool()
        self.show((980, 940 if len(self.targets) > 3 else 840) if unit else (650, 400))

    def create_tray(self, *args, **kwargs):
        from .status_rules import StatusDiceTray
        return StatusDiceTray(*args, **kwargs)

    def attack(self):
        return self.profiles[self.weapon_index.get()] if self.unit else None


class TouchDiceTray(dice_dialog.DiceTray):
    def __init__(self, parent, *args, **kwargs):
        touch_styles(parent._root())
        super().__init__(parent, *args, **kwargs)
        for button, kind in ((self.close_button, 'Quiet'), (self.reroll_button, 'Primary'), (self.apply_button, 'Primary')):
            if button is not None:
                button.configure(style=f'TouchTray.{kind}.TButton')
        def replace_spinners(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Spinbox):
                    variable = self.accuracy if str(child.cget('textvariable')) == str(self.accuracy) else self.damage_modifier
                    info = child.pack_info()
                    child.destroy()
                    Stepper(widget, variable, -99, 99).pack(**info)
                else:
                    replace_spinners(child)
        replace_spinners(self.body)
        replace_spinners(self.controls)
