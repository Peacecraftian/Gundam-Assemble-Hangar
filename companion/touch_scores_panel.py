"""Mirrored, touch-sized Victory Point panels."""
import tkinter as tk
from tkinter import font, ttk

from .board import fit_text
from .touch_scores import TouchScoreDialog as ScoreDialog
from .touch_actions import TouchTimelineAction as TimelineActionDialog
from .match import GARRISON_DEFEAT, GARRISON_RESCUE, UNIT_DEFEAT
from .theme import (BORDER, DISABLED, DISABLED_WELL, FOCUS, HANGARS, INK,
                             KEY_EDGE, KEY_FACE, PANEL, SCORE_FAMILY, SIDES,
                             app_cursor, button_surface_layout, families, panel_heading,
                             score_typography, surface_element)


class ScoreReadout(ttk.Button):
    """Retain the normal configure(text=...) refresh contract, including large totals."""
    def __init__(self, parent, app, side):
        self.face = font.Font(root=parent, family=SCORE_FAMILY, size=-52)
        style = ttk.Style(parent)
        name = f'Touch.Score.Side{side}.TButton'
        _, padding = score_typography(SCORE_FAMILY)
        style.configure(name, font=self.face, padding=padding)
        style.map(name, foreground=[('disabled', SIDES[side])])
        self.fit_job = None
        super().__init__(parent, text=f"{app.match.total(side):02d}", style=name,
                         cursor=app_cursor(parent, 'hand2'),
                         command=lambda: ScoreDialog(app, side, reason=ScoreDialog.ADJUST_VP))
        self.bind('<Configure>', self.fit)
        self.bind('<Destroy>', self.cancel_fit)
        if app.match.winner is not None:
            self.state(['disabled'])

    def configure(self, cnf=None, **options):
        result = super().configure(cnf, **options)
        if 'text' in options and self.fit_job is None:
            self.fit_job = self.after_idle(self.fit)
        return result

    config = configure

    def cancel_fit(self, _event=None):
        if self.fit_job is not None:
            self.after_cancel(self.fit_job)
            self.fit_job = None

    def fit(self, _event=None):
        self.cancel_fit()
        available = max(12, self.winfo_width() - 10)
        for size in range(52, 11, -1):
            self.face.configure(size=-size)
            if self.face.measure(str(self.cget('text'))) <= available:
                break


def action_style(root, side):
    style = ttk.Style(root)
    name = f'TouchAction{side}.TButton'
    element = name + '.face'
    fill, hover, pressed, edge = (
        ('#315653', '#3E6B66', '#253F3D', '#77B7AD') if side == 0 else
        ('#63423E', '#7B514A', '#48312E', '#D29283')
    )
    if element not in style.element_names():
        surface_element(root, style, element, fill, edge, radius=6, depth=1,
                        highlight=None, backdrop=HANGARS[side], tile=(128, 48), states=(
                            (('disabled',), DISABLED_WELL, BORDER, 0),
                            (('pressed', 'focus'), pressed, FOCUS, 0),
                            (('pressed',), pressed, edge, 0),
                            (('active', 'focus'), hover, FOCUS, 1),
                            (('focus',), fill, FOCUS, 1),
                            (('active',), hover, SIDES[side], 1),
                        ))
        button_surface_layout(style, name, element)
    _, mono = families(root)
    style.configure(name, font=(mono, -13, 'bold'), foreground=INK,
                    background=HANGARS[side], padding=2, anchor='center', justify='center', width=0)
    style.map(name, foreground=[('disabled', DISABLED)])
    return name


class PlayerScorePanel(ttk.Frame):
    def __init__(self, parent, app, side):
        super().__init__(parent, style=f'Hangar{side}.TFrame', padding=(10, 6))
        self.app, self.side = app, side
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, minsize=94)
        self.score_slot = ttk.Frame(self, style=f'HangarFill{side}.TFrame', width=80, height=72)
        self.score_slot.grid(row=0, column=0 if side == 0 else 2,
                             padx=(0, 8) if side == 0 else (8, 0))
        self.score_slot.pack_propagate(False)
        self.score = ScoreReadout(self.score_slot, app, side)
        self.score.pack(fill='both', expand=True)
        self.identity = tk.Canvas(self, background=HANGARS[side], highlightthickness=0,
                                  width=1, height=78)
        self.identity.grid(row=0, column=1, sticky='nsew', padx=(0, 12) if side == 0 else (12, 0))
        heading, mono = families(self)
        self.name_face = font.Font(root=self, family=heading, size=-30, weight='bold')
        self.meta_face = font.Font(root=self, family=mono, size=-11)
        self.identity.bind('<Configure>', self.draw_identity)
        self.action_grid = ttk.Frame(self, style=f'HangarFill{side}.TFrame', width=342, height=94)
        self.action_grid.grid(row=0, column=2 if side == 0 else 0, sticky='ns')
        self.action_grid.grid_propagate(False)
        for column in (0, 2, 4):
            self.action_grid.columnconfigure(column, weight=1, uniform='actions')
        for column in (1, 3):
            self.action_grid.columnconfigure(column, minsize=6)
        for row in (0, 2):
            self.action_grid.rowconfigure(row, weight=1, uniform='actions')
        self.action_grid.rowconfigure(1, minsize=6)
        commands = (
            ('DASH', lambda: TimelineActionDialog(app, side, 'Dash'), 0, 0),
            ('ENERGIZE', lambda: TimelineActionDialog(app, side, 'Energize'), 1, 0),
            ('GARRISON\nDEFEAT', lambda: ScoreDialog(app, side, reason=GARRISON_DEFEAT), 0, 1),
            ('GARRISON\nRESCUE', lambda: ScoreDialog(app, side, reason=GARRISON_RESCUE), 1, 1),
            ('UNIT DEFEAT', lambda: ScoreDialog(app, side, reason=UNIT_DEFEAT), 0, 2),
            ('SCENARIO GOAL', lambda: ScoreDialog(app, side, reason=ScoreDialog.SCENARIO_GOAL), 1, 2),
        )
        self.buttons = []
        self.style_name = action_style(app.root, side)
        for text, command, row, column in commands:
            column = column if side == 0 else 2 - column
            button = ttk.Button(self.action_grid, text=text, style=self.style_name, command=command)
            button.grid(row=row * 2, column=column * 2, sticky='nsew')
            if app.match.winner is not None:
                button.state(['disabled'])
            self.buttons.append(button)
        self.bind('<Configure>', self.arrange)

    def arrange(self, _event=None):
        width = max(1, self.winfo_width() - 20)
        action_width = min(354, max(184, int(width * .54)))
        score_width = 80 if width >= 580 else 70 if width >= 440 else 58
        self.action_grid.configure(width=action_width)
        self.score_slot.configure(width=score_width, height=72 if width >= 440 else 62)
        _, mono = families(self)
        small = action_width < 250
        ttk.Style(self).configure(self.style_name, font=(mono, -10 if small else -13, 'bold'))
        face = font.Font(root=self, family=mono, size=-10 if small else -13, weight='bold')
        label_width = (action_width - 12) / 3 - 10
        for index, label in ((4, 'UNIT DEFEAT'), (5, 'SCENARIO GOAL')):
            self.buttons[index].configure(text=label.replace(' ', '\n') if face.measure(label) > label_width else label)
        self.draw_identity()

    def draw_identity(self, _event=None):
        canvas = self.identity
        canvas.delete('all')
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 8:
            return
        name_size = 30 if width >= 210 else 25 if width >= 150 else 20 if width >= 100 else 15
        self.name_face.configure(size=-name_size)
        color = 'BLUE' if self.side == 0 else 'RED'
        meta = f'PLAYER {self.side + 1} // {color}' if width >= 145 else f'P{self.side + 1} / {color}'
        self.meta_face.configure(size=-11 if width >= 100 else -9)
        anchor = 'w' if self.side == 0 else 'e'
        x = 0 if self.side == 0 else width
        top = height / 2 - 17
        canvas.create_text(x, top, text=fit_text(meta, width, self.meta_face), anchor=anchor,
                           font=self.meta_face, fill=SIDES[self.side])
        canvas.create_text(x, top + 25, text=fit_text(self.app.match.players[self.side], width, self.name_face),
                           anchor=anchor, font=self.name_face, fill=SIDES[self.side])

