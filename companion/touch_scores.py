"""Touch-friendly scoring presentation with shared scoring transactions."""
import tkinter as tk
from tkinter import ttk
from . import dialogs
from .match import GARRISON
from .artwork import objective_art, timeline_portrait
from .theme import PANEL, families
from .touch_service import ChoiceRow, choice_style, TouchUnitDialog


class TouchLineup(ttk.Frame):
    """Wrapping portrait buttons, including duplicate slots and deployed RWS."""
    def __init__(self, parent, app):
        super().__init__(parent, style='PanelFill.TFrame')
        self.app, self.options, self.index = app, [], -1
        self.value = tk.IntVar(self, -1)
        self.tiles = ttk.Frame(self, style='PanelFill.TFrame')
        self.tiles.pack(fill='x')
        self.detail = ttk.Label(self, style='TouchScore.PanelMuted.TLabel', wraplength=850)
        self.detail.pack(fill='x', pady=(6, 0))
        self.buttons, self.photos = [], []
        self.bind('<Configure>', self.arrange)
        self.bind('<Left>', lambda e: self.choose(max(0, self.index - 1)))
        self.bind('<Right>', lambda e: self.choose(min(len(self.options)-1, self.index + 1)))

    def set_options(self, options):
        self.options = list(options)
        for child in self.tiles.winfo_children():
            child.destroy()
        self.buttons, self.photos = [], []
        for index, (unit, system) in enumerate(self.options):
            if unit is GARRISON:
                photo, caption = None, 'Enemy Garrison\n1 HP · 2 VP'
            else:
                photo = self.app.photos.get(timeline_portrait, system.image if system else unit.card.image, (76, 88), 0)
                name = system.name if system else unit.card.name
                caption = f'  {unit.slot:02d} · {name}\n  P{unit.player+1}' + (' · RWS' if system else '')
            self.photos.append(photo)
            button = ttk.Radiobutton(self.tiles, image=photo or '', compound='left',
                text=caption,
                variable=self.value, value=index, style='TouchScoreUnit.TRadiobutton',
                command=lambda i=index: self.choose(i))
            button.bind('<Left>', lambda e: self.choose(max(0, self.index-1)))
            button.bind('<Right>', lambda e: self.choose(min(len(self.options)-1, self.index+1)))
            self.buttons.append(button)
        self.current(-1)
        self.arrange()

    def arrange(self, _event=None):
        columns = 3 if self.winfo_width() >= 800 else 2 if self.winfo_width() >= 500 else 1
        for col in range(3):
            self.tiles.columnconfigure(col, weight=1 if col < columns else 0, uniform='targets' if col < columns else '')
        for i, button in enumerate(self.buttons):
            button.grid(row=i//columns, column=i%columns, sticky='nsew', padx=4, pady=4)
        self.detail.configure(wraplength=max(250, self.winfo_width()-8))

    def current(self, index=None):
        if index is None:
            return self.index
        self.index = index if 0 <= index < len(self.options) else -1
        self.value.set(self.index)
        if self.index >= 0:
            unit, system = self.options[self.index]
            if unit is GARRISON:
                self.detail.configure(text='Choose the enemy Garrison on the tabletop.')
                return
            hp = unit.remote_weapon_hp[system.number] if system else unit.hp
            self.detail.configure(text=f'{unit.label} · {system.name if system else unit.card.number} · HP {hp}'
                                  + ('' if system else f' · Shields {unit.shield_active}'))
        else:
            self.detail.configure(text='Tap a unit to select it.' if self.options else 'No eligible deployed units.')

    def choose(self, index):
        if 0 <= index < len(self.options):
            self.current(index)
            self.event_generate('<<UnitSelected>>')
        return 'break'

    def focus_set(self):
        if self.buttons:
            self.buttons[max(0, self.index)].focus_set()


class TouchScoreDialog(dialogs.ScoreDialog):
    def __init__(self, app, player, *, reason=dialogs.UNIT_DEFEAT):
        dialogs.Dialog.__init__(self, app.root, 'Record Victory Points')
        self.app, self.player = app, player
        self.inputs, self.read_only = [], app.match.winner is not None
        self.deployed_units = [[u for u in app.match.units if u.deployed and u.player == side] for side in range(2)]
        self.target_options, self.remote_choices = [], []
        self.phase = tk.StringVar(self.window, str(app.match.phase))
        self.points, self.note = tk.StringVar(self.window), tk.StringVar(self.window)
        self.reason = tk.StringVar(self.window, reason)
        self.objective_photo = app.photos.get(objective_art, player)
        heading, mono = families(app.root)
        style = ttk.Style(app.root)
        choice = choice_style(app.root)
        for name, size in [('TouchScoreReason.TRadiobutton', 15), ('TouchScoreUnit.TRadiobutton', 16)]:
            style.layout(name, style.layout(choice))
            style.configure(name, font=(heading, -size, 'bold'), foreground='#F2EDE0', padding=8,
                            anchor='center', width=0, wraplength=170 if 'Reason' in name else 180)
            style.map(name, foreground=[('selected', '#FFB762')])
        style.configure('TouchScore.PanelMuted.TLabel', font=(heading, -15))
        style.configure('TouchScore.Panel.FieldLabel.TLabel', font=(mono, -13))
        style.configure('TouchScore.TEntry', font=(mono, -22), padding=(10, 10))
        style.configure('TouchScore.Panel.TCheckbutton', font=(heading, -16), padding=(12, 14))
        style.configure('TouchBayStep.TButton', font=(mono, -26, 'bold'), padding=0)
        for kind in ('Primary', 'Quiet'):
            style.configure(f'TouchBay.{kind}.TButton', font=(heading, -16, 'bold'), padding=(12, 6))

        self.title = self.workspace.caption(self.body, 'Record Victory Points')
        self.title.pack(anchor='w', pady=(0, 10))
        shell = ttk.Frame(self.body, style='Panel.TFrame', padding=10)
        shell.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(shell, background=PANEL, highlightthickness=0, width=910, height=650)
        scroll = ttk.Scrollbar(shell, command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        panel = ttk.Frame(self.canvas, style='PanelFill.TFrame', padding=6)
        mount = self.canvas.create_window(0, 0, anchor='nw', window=panel)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(mount, width=e.width))
        panel.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.window.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta/120), 'units'))
        self.window.bind('<FocusIn>', self.reveal_focus, add='+')
        identity = ttk.Frame(panel, style=f'Hangar{player}.TFrame', padding=12)
        identity.pack(fill='x', pady=(0, 12))
        ttk.Label(identity, text=app.match.players[player], style=f'Side{player}.TLabel').pack(side='left')
        ttk.Label(identity, text=f'PLAYER {player+1}', style=f'SideMeta{player}.TLabel').pack(side='right')
        self.reason_label = ttk.Label(panel, text='SCORING ACTION', compound='left', style='TouchScore.Panel.FieldLabel.TLabel')
        self.reason_label.pack(anchor='w', pady=(0, 4))
        reasons = ttk.Frame(panel, style='PanelFill.TFrame')
        reasons.pack(fill='x', pady=(0, 12))
        reasons.columnconfigure(tuple(range(5)), weight=1, uniform='reason')
        for col, (key, label) in enumerate(self.REASON_LABELS.items()):
            box = ttk.Frame(reasons, style='PanelFill.TFrame', height=56, width=1)
            box.grid(row=0, column=col, sticky='ew', padx=3)
            box.pack_propagate(False)
            ttk.Radiobutton(box, text='Adjust VP' if key == self.ADJUST_VP else label,
                variable=self.reason, value=key, style='TouchScoreReason.TRadiobutton', command=self.update_reason).pack(fill='both', expand=True)
        phase_row = ttk.Frame(panel, style='PanelFill.TFrame')
        phase_row.pack(fill='x', pady=(0, 12))
        ttk.Label(phase_row, text='PHASE', style='TouchScore.Panel.FieldLabel.TLabel').pack(side='left', padx=(0, 16))
        ChoiceRow(phase_row, self, self.phase, range(1, app.match.phases+1)).pack(side='left', fill='x', expand=True)
        fields = ttk.Frame(panel, style='PanelFill.TFrame')
        fields.pack(fill='x')
        fields.columnconfigure(0, weight=1)
        self.target_label = ttk.Label(fields, style='TouchScore.Panel.FieldLabel.TLabel')
        self.target_label.grid(row=0, column=0, sticky='w')
        self.targets = TouchLineup(fields, app)
        self.targets.grid(row=1, column=0, sticky='ew', pady=(4, 12))
        self.unpaid_tl = tk.StringVar(self.window, '0')
        self.cost_row = ttk.Frame(fields, style='PanelFill.TFrame')
        self.cost_row.grid(row=3, column=0, sticky='w')
        ttk.Label(self.cost_row, text='Unpaid TL (0 if already paid)', style='TouchScore.PanelMuted.TLabel').pack(side='left')
        from .touch_actions import Stepper
        Stepper(self.cost_row, self.unpaid_tl, 0, 99).pack(side='left', padx=8)
        self.remote_defeat = ttk.Frame(fields, style='PanelFill.TFrame')
        self.remote_defeat.grid(row=2, column=0, sticky='ew')
        self.points_label = ttk.Label(panel, text='VP ADJUSTMENT', style='TouchScore.Panel.FieldLabel.TLabel')
        self.points_label.pack(anchor='w', pady=(8, 6))
        amount = ttk.Frame(panel, style='PanelFill.TFrame')
        amount.pack(fill='x', pady=(0, 12))
        self.adjusters = []
        for column, delta in ((0, -5), (1, -1), (3, 1), (4, 5)):
            box = ttk.Frame(amount, style='PanelFill.TFrame', width=64, height=52)
            box.grid(row=0, column=column, padx=4)
            box.pack_propagate(False)
            button = ttk.Button(box, text=f'{delta:+d}', style='TouchBayStep.TButton', command=lambda d=delta: self.adjust_points(d))
            button.pack(fill='both', expand=True)
            self.adjusters.append(button)
        self.points_field = ttk.Entry(amount, textvariable=self.points, width=6, justify='center', style='TouchScore.TEntry', font=(mono, -24, 'bold'))
        self.points_field.grid(row=0, column=2, sticky='ns', padx=8)
        dialogs.touch_keyboard(self.points_field, 'Victory Points', numeric=True)
        ttk.Label(panel, text='NOTE (OPTIONAL)', style='TouchScore.Panel.FieldLabel.TLabel').pack(anchor='w', pady=(0, 6))
        notes = ttk.Entry(panel, textvariable=self.note, style='TouchScore.TEntry', font=(heading, -18))
        notes.pack(fill='x')
        dialogs.touch_keyboard(notes, 'Scoring Note')
        self.hint = ttk.Label(panel, style='TouchScore.PanelMuted.TLabel', wraplength=850)
        self.hint.pack(fill='x', pady=(12, 4))
        self.targets.bind('<<UnitSelected>>', self.set_target_points)
        self.record_button = self.buttons('Record VP', self.record)
        self.update_reason()
        self.show((980, 840))

    buttons = TouchUnitDialog.buttons

    def selected_reason(self):
        return self.reason.get()

    def update_reason(self, _event=None):
        super().update_reason()
        reason = self.selected_reason()
        if reason == dialogs.GARRISON_DEFEAT:
            self.cost_row.grid()
        else:
            self.cost_row.grid_remove()
        editable = reason not in self.UNIT_ACTIONS
        for button in self.adjusters:
            button.state(['!disabled'] if editable else ['disabled'])
        if editable:
            self.points.set('0')
        title = 'Record Victory Points' if reason == self.ADJUST_VP else self.REASON_LABELS[reason]
        for item in self.title.find_all():
            if self.title.type(item) == 'text':
                self.title.itemconfigure(item, text=title)
        self.window.title(title)

    def adjust_points(self, delta):
        if self.selected_reason() in self.UNIT_ACTIONS:
            return
        try:
            value = int(self.points.get().strip() or '0')
        except ValueError:
            self.error('Enter a whole number of Victory Points.')
            return
        self.points.set(str(value + delta))

    def set_target_points(self, _event=None):
        # Original calculation includes selected deployed Remote Weapon Systems.
        super().set_target_points(_event)
        for child in self.remote_defeat.winfo_children():
            child.configure(style='TouchScore.Panel.TCheckbutton')
        # Keep additions within the scrollable body instead of growing the window.
        if self.window.winfo_viewable():
            from .window_placement import monitor_bounds
            bounds = monitor_bounds(self.app.root) or (0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight())
            self.window.geometry(f'{min(980, bounds[2]-bounds[0]-20)}x{min(840, bounds[3]-bounds[1]-80)}')

    def reveal_focus(self, event):
        widget = event.widget
        # Ancestor FocusIn events must not scroll the entire content panel.
        if widget is not self.window.focus_get() or widget is self.window or not str(widget).startswith(str(self.canvas)+'.'):
            return
        self.window.update_idletasks()
        top = widget.winfo_rooty() - self.canvas.winfo_rooty() + self.canvas.canvasy(0)
        bottom = top + widget.winfo_height()
        region = self.canvas.bbox('all')
        if not region:
            return
        visible = self.canvas.canvasy(0)
        if top < visible:
            self.canvas.yview_moveto(max(0, top-8)/max(1, region[3]))
        elif bottom > visible + self.canvas.winfo_height():
            self.canvas.yview_moveto(max(0, bottom-self.canvas.winfo_height()+8)/max(1, region[3]))
