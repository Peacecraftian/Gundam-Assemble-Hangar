import sqlite3
import tkinter as tk
from copy import deepcopy
from tkinter import font, messagebox, ttk

from .artwork import PhotoCache, decal_art, objective_art
from .attacks import load_attacks
from .board import CardPreview, Hangar, Timeline, fit_text
from .battlefield import BattlefieldScreen
from .catalog import ROUNDS, load_remote_weapons, load_tactics
from Video.playback import DeploymentOverlay
from .dialogs import (
    Dialog, ScoreDialog, SetupScreen, TimelineActionDialog, UnitDialog, show_card, show_finish, show_history, spinner,
    table,
)
from .dice_dialog import DicePrompt
from .match import GARRISON_DEFEAT, GARRISON_RESCUE, UNIT_DEFEAT
from .storage import SaveConflict
from .tactics import TacticsScreen
from .theme import (
    FooterButton,
    BATTLEFIELD, CELL, DANGER, HANGARS, MATCH_CONSOLE, MISSION_SORTIE, MUTED, PRODUCT, READY, TACTICS, app_cursor, draw_phase_led,
    leave_fullscreen, nameplate, panel_heading, setup_theme,
)
from .workspace import Workspace


MATCH_SECTION_GAP = 11
FULL_PHASE_BANK = 5


def shortened(text, limit):
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def score_text(points):
    return f"{points:02d}"


class Companion:
    def __init__(self, root, catalog, store):
        self.root = root
        self.deployment = DeploymentOverlay(root)
        self.photos = PhotoCache(root)
        self.catalog = catalog
        self.attacks = load_attacks(catalog)
        self.remote_weapons = load_remote_weapons(catalog)
        self.tactics = load_tactics()
        self.store = store
        self.match, self.revision = store.load()
        self.battlefield_scenario = self.match.scenario_id if self.match is not None else None
        self.battlefield_palettes = {}
        self.view = None
        self.active_workspace = MATCH_CONSOLE if self.match is not None else MISSION_SORTIE
        self.setup_return = None
        self.tactics_screen = None
        self.battlefield_screen = None
        self.selected_id = None
        self.feedback = tk.StringVar(master=root, value="●  Local autosave")
        self.feedback_style = "Saved.TLabel"
        self.feedback_label = None
        root.title(PRODUCT)
        setup_theme(root)
        self.workspace = Workspace(root)
        screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
        width = min(1700, screen_width - 54)
        height = min(930, screen_height - 90)
        x = (screen_width - width) // 2
        y = (screen_height - height - 76) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.minsize(min(1020, width), min(595, height))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", self.escape)
        self.render()

    def close(self):
        if self.battlefield_screen is not None and not self.battlefield_screen.can_leave():
            return
        self.deployment.stop()
        self.store.close()
        self.root.destroy()

    def render(self):
        self.tactics_screen = None
        self.battlefield_screen = None
        if self.view is None:
            self.view = self.workspace.layer(self.root)
            self.view.pack(fill="both", expand=True, padx=15, pady=(10, 8))
            self.view.columnconfigure(0, weight=1)
        else:
            for child in self.view.winfo_children():
                child.destroy()
        self.view.rowconfigure((1, 2, 3), weight=0, minsize=0)
        navigation = {MISSION_SORTIE: self.open_setup, TACTICS: lambda: self.switch_workspace(TACTICS)}
        navigation[BATTLEFIELD] = lambda: self.switch_workspace(BATTLEFIELD)
        if self.match is not None:
            navigation[MATCH_CONSOLE] = lambda: self.switch_workspace(MATCH_CONSOLE)
        active = self.active_workspace
        header_gap = MATCH_SECTION_GAP if active == MATCH_CONSOLE else 6
        nameplate(self.view, active or MISSION_SORTIE, navigation).grid(
            row=0, column=0, sticky="ew", pady=(0, header_gap),
        )
        if active != MATCH_CONSOLE:
            self.view.rowconfigure(1, weight=1)
        if active == TACTICS:
            self.tactics_screen = TacticsScreen(self.view, self)
            self.tactics_screen.show()
            return
        if active == BATTLEFIELD:
            self.battlefield_screen = BattlefieldScreen(self.view, self)
            return
        if active == MISSION_SORTIE:
            SetupScreen(self.view, self).show()
            return
        if active is None:
            self.welcome()
            return

        if all(unit.id != self.selected_id for unit in self.match.units):
            self.selected_id = self.match.units[0].id
        self.view.rowconfigure(2, weight=3, minsize=167)
        self.view.rowconfigure(3, weight=10, minsize=115)
        self.scoreboard()
        self.timeline()
        self.hangars()
        self.action_bar()

    def open_setup(self):
        self.switch_workspace(MISSION_SORTIE)

    def cancel_setup(self):
        self.switch_workspace(self.setup_return)

    def switch_workspace(self, workspace):
        if self.active_workspace == workspace:
            return
        if self.battlefield_screen is not None and not self.battlefield_screen.can_leave():
            return
        if workspace == MISSION_SORTIE:
            self.setup_return = self.active_workspace
        self.active_workspace = workspace
        self.deployment.stop()
        self.render()

    def escape(self, _event):
        if self.tactics_screen is not None and self.tactics_screen.escape():
            return "break"
        if leave_fullscreen(self.root):
            return "break"
        if self.battlefield_screen is not None and self.battlefield_screen.editing:
            self.battlefield_screen.cancel_edit()
            return "break"
        if self.active_workspace == MISSION_SORTIE:
            self.cancel_setup()
            return "break"

    def welcome(self):
        panel = ttk.Frame(self.view, style="Panel.TFrame", padding=24)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        content = ttk.Frame(panel, style="PanelFill.TFrame")
        content.grid(row=0, column=0)
        ttk.Label(content, text=MISSION_SORTIE, style="Result.TLabel").pack(anchor="w")
        ttk.Label(
            content, text="Start a match to unlock Match Console and Service Bay.",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(5, 15))
        ttk.Button(
            content, text=f"Open {MISSION_SORTIE}", style="Primary.TButton", command=self.open_setup,
        ).pack(anchor="w")

    def announce(self, message, style="Saved.TLabel"):
        self.feedback.set(message)
        if self.feedback_style != style:
            self.feedback_style = style
            if self.feedback_label is not None and self.feedback_label.winfo_exists():
                self.feedback_label.configure(style=style)

    def action_bar(self):
        bar = ttk.Frame(self.view, style="Rail.TFrame", padding=(7, 3))
        bar.grid(row=4, column=0, sticky="ew", pady=(MATCH_SECTION_GAP, 0))
        actions = [("New Match", self.open_setup, "Compact.TButton"),
                   ("VP History", lambda: show_history(self), "Compact.TButton"),
                   ("Undo", self.undo, "Compact.TButton"),
                   ("Roll D10s", lambda: DicePrompt(self.root), "Compact.TButton")]
        if self.match.winner is None:
            actions.insert(0, ("Finish Match", lambda: show_finish(self), "Danger.TButton"))
        for text, action, style in actions:
            button = FooterButton(bar, text=text, style=style, command=action)
            button.pack(side="right", padx=(4, 0))
            if text == "Undo":
                self.undo_button = button
                button.state(["!disabled"] if self.store.can_undo() else ["disabled"])
        self.feedback_label = ttk.Label(bar, textvariable=self.feedback, style=self.feedback_style)
        self.feedback_label.pack(side="left", fill="x", expand=True)

    def scoreboard(self):
        match = self.match
        board = self.workspace.layer(self.view)
        board.grid(row=1, column=0, sticky="ew", pady=(0, MATCH_SECTION_GAP))
        board.columnconfigure((0, 2), weight=1, uniform="scores")
        self.score_readouts = []
        for side, column in enumerate((0, 2)):
            outer = "w" if side == 0 else "e"
            mark_pad = (7, 0) if side == 0 else (0, 7)
            score_pad = (0, 8) if side == 0 else (8, 0)
            tile = ttk.Frame(board, style=f"Hangar{side}.TFrame", padding=(10, 4))
            tile.grid(row=0, column=column, sticky="nsew")
            heading = ttk.Frame(tile, style=f"HangarFill{side}.TFrame")
            heading.pack(fill="x")
            heading.columnconfigure(1, weight=1)
            ttk.Frame(heading, style=f"SideMark{side}.TFrame", width=3).grid(
                row=0, column=2 - column, sticky="ns", padx=mark_pad,
            )
            total = score_text(match.total(side))
            if match.winner is None:
                score = ttk.Button(
                    heading, text=total, style=f"Score.Side{side}.TButton", cursor=app_cursor(heading, "hand2"),
                    command=lambda side=side: ScoreDialog(self, side, reason=ScoreDialog.ADJUST_VP),
                )
            else:
                score = ttk.Label(heading, text=total, style=f"Score{side}.TLabel")
            self.score_readouts.append(score)
            score.grid(row=0, column=column, sticky=outer, padx=score_pad, pady=4)
            self.score_identity(heading, side)
            if match.winner is None:
                self.scoring_buttons(tile, side)

        center = ttk.Frame(board, style="Panel.TFrame", padding=(8, 5))
        center.grid(row=0, column=1, sticky="nsew", padx=8)
        if match.winner is None:
            self.controls_header(center)
            self.cursor_controls(center)
        else:
            winner = shortened(match.players[match.winner], 25)
            panel_heading(center, "FINAL", f"{winner} wins").pack(fill="x")
            ttk.Label(center, text=f"Phase {match.phase:02d}  ·  Round {match.round:02d}  ·  Match complete",
                      style="PanelMuted.TLabel").pack(expand=True, pady=4)

    def score_identity(self, heading, side):
        identity = tk.Canvas(heading, width=1, height=1, background=HANGARS[side], highlightthickness=0,
                             borderwidth=0, takefocus=False)
        identity.grid(row=0, column=1, sticky="nsew")
        identity.warning_photo = self.photos.get(decal_art, "score-warning")
        warning = identity.create_image(0, 0, image=identity.warning_photo, state="hidden", tags=("score_decal",))
        meta = ttk.Label(identity, text=f"PLAYER {side + 1}  /  VP", style=f"SideMeta{side}.TLabel")
        inner, outer = ("e", "w") if side == 0 else ("w", "e")
        name_style = f"PlayerName{side}.TLabel"
        label = ttk.Label(identity, style=name_style, compound="left", anchor=inner)
        label.objective_photo = self.photos.get(objective_art, side)
        label.configure(image=label.objective_photo)
        name = shortened(self.match.players[side], 48)

        def arrange(_event):
            width, height = identity.winfo_width(), identity.winfo_height()
            face = font.Font(root=label, font=ttk.Style(label).lookup(name_style, "font"))
            available = width - label.objective_photo.width() - 6
            text = fit_text(name, available, face) if available >= face.measure("…") else ""
            if text != label.cget("text"):
                label.configure(text=text)
            label_height, meta_height = label.winfo_reqheight(), meta.winfo_reqheight()
            content_height = label_height + meta_height
            if int(identity.cget("height")) != content_height:
                identity.configure(height=content_height)
            center = (height + meta_height - label_height) // 2
            relx = 1 - side
            meta.place(relx=relx, y=center, anchor=f"s{inner}")
            label.place(relx=relx, y=center, anchor=f"n{inner}")
            photo = identity.warning_photo
            padding = 16
            fits = (photo is not None and width - max(meta.winfo_reqwidth(), label.winfo_reqwidth()) >=
                    photo.width() + 2 * padding and height >= photo.height() + 8)
            identity.coords(warning, padding if side == 0 else width - padding, height / 2)
            identity.itemconfigure(warning, anchor=outer, state="normal" if fits else "hidden")

        identity.bind("<Configure>", arrange)
        label.bind("<<ThemeChanged>>", arrange)

    def scoring_buttons(self, parent, side):
        row = ttk.Frame(parent, style=f"HangarFill{side}.TFrame")
        row.pack(fill="x", pady=(2, 0))
        labels = ScoreDialog.REASON_LABELS
        goal_reason = ScoreDialog.SCENARIO_GOAL
        timeline_actions = ("Dash", "Energize")
        full = (*timeline_actions, "Garrison Defeat", labels[GARRISON_RESCUE], labels[UNIT_DEFEAT], labels[goal_reason])
        short = (*timeline_actions, "Garr. Defeat", "Rescue", labels[UNIT_DEFEAT], "Goal")
        tight = (*timeline_actions, "Garr. KO", "Rescue", "Unit KO", "Goal")
        actions = [lambda action=action: TimelineActionDialog(self, side, action) for action in timeline_actions]
        actions.extend(lambda reason=reason: ScoreDialog(self, side, reason=reason)
                       for reason in (GARRISON_DEFEAT, GARRISON_RESCUE, UNIT_DEFEAT, goal_reason))
        buttons = []
        for label, action in zip(full, actions):
            button = ttk.Button(row, text=label, style="Scoring.Compact.TButton", command=action)
            button.pack(side="left", fill="x", expand=True, padx=(0, 1))
            buttons.append(button)

        def resize(event):
            face = font.Font(root=row, font=ttk.Style(row).lookup("Scoring.Compact.TButton", "font"))
            labels = next((labels for labels in (full, short)
                           if sum(face.measure(label) + 8 for label in labels) <= event.width), tight)
            for button, label in zip(buttons, labels):
                if button.cget("text") != label:
                    button.configure(text=label)

        row.bind("<Configure>", resize)

    def controls_header(self, parent):
        header = ttk.Frame(parent, style="Housing.TFrame", padding=(7, 3))
        header.pack(fill="x")
        live = ttk.Label(header, text="LIVE", style="PanelCode.TLabel")
        live.grid(row=0, column=0, sticky="w", padx=(0, 4))
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, minsize=live.winfo_reqwidth() + 4)
        name = (self.match.scenario or "").strip() or "Game Controls"
        title = ttk.Label(header, text=name, style="Rail.TLabel", anchor="center", width=1)
        title.grid(row=0, column=1, sticky="ew")

        def fit_title(_event):
            face = font.Font(root=title, font=ttk.Style(title).lookup("Rail.TLabel", "font"))
            width = title.winfo_width() - 4
            text = fit_text(name, width, face) if width >= face.measure("…") else ""
            if text != title.cget("text"):
                title.configure(text=text)

        title.bind("<Configure>", fit_title)
        title.bind("<<ThemeChanged>>", fit_title)

    def phase_lights(self, parent):
        bank = ttk.Frame(parent, style="Well.TFrame")
        ttk.Label(bank, text="Phase", style="Cursor.TLabel").pack(side="left")
        canvas = tk.Canvas(bank, background=CELL, height=24, highlightthickness=0, takefocus=False)
        canvas.pack(side="left")
        face = font.Font(root=canvas, font=ttk.Style(canvas).lookup("Cursor.TLabel", "font"))
        canvas.number_font = face
        self.phase_canvas = canvas
        self.draw_phase_lights()
        return bank

    def draw_phase_lights(self):
        current, total = self.match.phase, self.match.phases
        canvas = self.phase_canvas
        face = canvas.number_font
        canvas.delete("all")
        total_text = str(total)
        label_width = face.measure("0" * min(len(total_text), 3))
        if total <= FULL_PHASE_BANK:
            first, last = 1, total
        else:
            first = max(1, min(current - 1, total - 2))
            last = first + 2
        x = 0
        for phase in range(first, last + 1):
            active = phase == current
            red = phase == total
            active_ink = DANGER if red else READY
            canvas.create_text(x + label_width, 12, text=shortened(str(phase), 3), anchor="e",
                               fill=active_ink if active else MUTED, font=face)
            draw_phase_led(canvas, x + label_width + 9, 12, active, red=red)
            x += label_width + 21
        if total > FULL_PHASE_BANK:
            count = f"/{shortened(total_text, 4)}"
            canvas.create_text(x + 1, 12, text=count, anchor="w", fill=MUTED, font=face)
            x += face.measure(count) + 3
        canvas.configure(width=x)

    def cursor_controls(self, parent):
        match = self.match
        controls = ttk.Frame(parent, style="PanelFill.TFrame")
        controls.pack(expand=True, pady=4)
        self.phase_lights(controls).pack(side="left")
        selector = ttk.Frame(controls, style="Well.TFrame")
        selector.pack(side="left", padx=(7, 0))
        self.previous_round = self.round_arrow(selector, "‹", -1)
        self.previous_round.pack(side="left")
        self.round_label = ttk.Label(selector, text=f"Round {match.round:02d}", style="Cursor.TLabel")
        self.round_label.pack(side="left")
        self.next_round = self.round_arrow(selector, "›", 1)
        self.next_round.pack(side="left")
        ttk.Button(controls, text="Jump", style="Compact.TButton", command=self.jump_cursor).pack(
            side="left", padx=(6, 0),
        )

    def round_arrow(self, parent, text, direction):
        target = self.match.adjacent_cursor(direction)
        button = ttk.Button(parent, text=text, width=1, style="Arrow.TButton",
                            command=lambda: self.step_cursor(direction))
        if target is None:
            button.state(["disabled"])
        return button

    def step_cursor(self, direction):
        target = self.match.adjacent_cursor(direction)
        if target is not None and self.edit(lambda draft: draft.set_cursor(*target), self.root):
            phase, round_number = target
            self.announce(f"●  Saved · Phase {phase:02d} / Round {round_number:02d}")
            arrow = self.previous_round if direction < 0 else self.next_round
            if arrow.instate(["disabled"]):
                arrow = self.next_round if direction < 0 else self.previous_round
            arrow.focus_set()

    def jump_cursor(self):
        dialog = Dialog(self.root, "Jump To Phase And Round")
        dialog.workspace.caption(dialog.body, "Set Current Timeline Position").grid(
            row=0, columnspan=2, sticky="w",
        )
        phase = tk.StringVar(value=str(self.match.phase))
        round_number = tk.StringVar(value=str(self.match.round))
        for row, label, value, limit in (
            (1, "Phase", phase, self.match.phases), (2, "Round", round_number, ROUNDS),
        ):
            dialog.workspace.caption(dialog.body, label, "FieldLabel.TLabel").grid(
                row=row, column=0, sticky="w", pady=4, padx=(0, 12),
            )
            spinner(dialog.body, value, 1, limit).grid(row=row, column=1, sticky="ew", pady=4)

        def jump():
            if self.edit(lambda draft: draft.set_cursor(phase.get(), round_number.get()), dialog.window):
                dialog.window.destroy()

        dialog.buttons("Set Current", jump)
        dialog.show()

    def timeline(self):
        panel = ttk.Frame(self.view, style="Panel.TFrame", padding=(12, 7))
        panel.grid(row=2, column=0, sticky="nsew", pady=(0, MATCH_SECTION_GAP))
        header = panel_heading(panel, "04", "Timeline")
        header.pack(fill="x", pady=(0, 6))
        self.other_phases_button = ttk.Button(
            header, style="Compact.TButton",
            command=lambda: self.show_other_phases(
                [unit for unit in self.match.units if unit.phase != self.match.phase]),
        )
        self.other_phases_button.pack(side="right")
        self.timeline_hint = ttk.Label(header, style="RailMeta.TLabel")
        self.timeline_hint.pack(side="left", padx=9)
        self.refresh_timeline_header()
        self.track = Timeline(panel, self)
        self.track.pack(fill="both", expand=True)

    def refresh_timeline_header(self):
        match = self.match
        hint = f"Phase {match.phase} of {match.phases} · Round {match.round}"
        if match.winner is None:
            hint += "  /  Drag within a lane  ·  Scroll crowded stacks"
        self.timeline_hint.configure(text=hint)
        other = sum(unit.phase != match.phase for unit in match.units)
        self.other_phases_button.configure(text=f"Other Phases ({other})")

    def can_refresh_console(self, previous):
        """Only reuse widgets when the screen's structure and roster are unchanged."""
        match = self.match
        if (self.active_workspace != MATCH_CONSOLE or previous is None or match is None
                or not hasattr(self, "track") or not self.track.winfo_exists()):
            return False
        for field in ("players", "scenario", "scenario_id", "phases", "winner"):
            if getattr(previous, field) != getattr(match, field):
                return False
        return ([(u.id, u.player, u.slot, u.card) for u in previous.units]
                == [(u.id, u.player, u.slot, u.card) for u in match.units])

    def refresh_console(self, previous):
        """Refresh changed match data without tearing down the console or its art."""
        if not self.can_refresh_console(previous):
            self.render()
            return
        match = self.match
        for side, score in enumerate(self.score_readouts):
            if previous.total(side) != match.total(side):
                score.configure(text=score_text(match.total(side)))
        cursor_changed = (previous.phase, previous.round) != (match.phase, match.round)
        if cursor_changed and match.winner is None:
            self.draw_phase_lights()
            self.round_label.configure(text=f"Round {match.round:02d}")
            for direction, button in ((-1, self.previous_round), (1, self.next_round)):
                button.state(["disabled"] if match.adjacent_cursor(direction) is None else ["!disabled"])
        position = lambda unit: (unit.phase, unit.round, unit.stack)
        if cursor_changed or any(position(a) != position(b) for a, b in zip(previous.units, match.units)):
            self.track.draw()
        self.refresh_timeline_header()
        # A Timeline-only move does not alter Hangar art or the featured card.
        visible = lambda unit: {key: value for key, value in vars(unit).items()
                                if key not in ("phase", "round", "stack")}
        changed = [after for before, after in zip(previous.units, match.units)
                   if visible(before) != visible(after)]
        for side in {unit.player for unit in changed}:
            self.player_hangars[side].draw()
        if any(unit.id == self.selected_id for unit in changed):
            self.preview.draw()
        self.undo_button.state(["!disabled"] if self.store.can_undo() else ["disabled"])

    def show_stack(self, units):
        self.show_unit_list("Timeline Stack", ("rank", "Position", 75, False),
                            [(unit, index) for index, unit in enumerate(units, 1)])

    def show_other_phases(self, units):
        units = sorted(units, key=lambda unit: (unit.phase, unit.round, unit.player, unit.stack))
        self.show_unit_list("Other Phases", ("when", "Phase / Round", 110, False),
                            [(unit, f"P{unit.phase} / R{unit.round}") for unit in units])

    def show_unit_list(self, title, column, rows):
        dialog = Dialog(self.root, title)
        dialog.workspace.caption(dialog.body, title).pack(anchor="w")
        frame, tree = table(dialog.body, (column, ("name", "Unit", 320, True)), height=8)
        frame.pack(fill="both", expand=True, pady=(6, 0))
        for unit, value in rows:
            player = self.match.players[unit.player]
            tree.insert("", "end", iid=str(unit.id), values=(value, f"{player} · {unit.label}"))
        if not rows:
            dialog.workspace.caption(dialog.body, "No tokens outside this Phase.", "Muted.TLabel").pack(anchor="w")

        def open_unit():
            selected = tree.selection()
            if selected:
                dialog.window.destroy()
                self.select_unit(int(selected[0]))
                self.open_unit()

        dialog.buttons("Open Unit", open_unit)
        dialog.initial_focus = tree
        tree.bind("<Double-1>", lambda _event: open_unit())
        tree.bind("<Return>", lambda _event: open_unit())
        dialog.show()

    def hangars(self):
        row = self.workspace.layer(self.view)
        row.grid(row=3, column=0, sticky="nsew")
        row.columnconfigure((0, 2), weight=7, uniform="hangars")
        row.columnconfigure(1, weight=10, uniform="hangars")
        row.rowconfigure(0, weight=1)
        self.player_hangars = [Hangar(row, self, side) for side in range(2)]
        for column, hangar in zip((0, 2), self.player_hangars):
            hangar.grid(row=0, column=column, sticky="nsew")
        self.deployment.restore_hangar(self.player_hangars)
        self.preview = CardPreview(row, self)
        self.preview.grid(row=0, column=1, sticky="nsew", padx=12)

    def selected_unit(self):
        return self.match.unit(self.selected_id)

    def select_unit(self, unit_id):
        if unit_id == self.selected_id:
            return
        self.selected_id = unit_id
        self.preview.draw()
        for hangar in self.player_hangars:
            hangar.draw()
        self.track.draw()

    def open_unit(self, unit_id=None):
        if unit_id is not None:
            self.select_unit(unit_id)
        UnitDialog(self, self.selected_unit())

    def deploy_unit(self, unit_id):
        if self.match.winner is not None or self.match.unit(unit_id).deployed:
            return

        def refresh():
            if unit_id == self.selected_id:
                self.refresh_unit_display()
            else:
                self.select_unit(unit_id)

        if self.edit(lambda draft: draft.deploy_unit(unit_id), self.root, refresh=refresh):
            self.play_hangar_transition(unit_id, with_clip=True)

    def play_hangar_transition(self, unit_id, *, with_clip):
        hangar = self.player_hangars[self.match.unit(unit_id).player]
        self.deployment.play(hangar, with_clip=with_clip)

    def adjust_unit_counter(self, counter, delta):
        unit_id = self.selected_id
        self.edit(
            lambda draft: draft.adjust_unit_counter(unit_id, counter, delta), self.root,
            refresh=self.refresh_unit_display,
        )

    def deploy_remote_weapon(self, weapon, *, unit_id=None, parent=None):
        unit_id = self.selected_id if unit_id is None else unit_id
        return self.edit(lambda draft: draft.deploy_remote_weapon(unit_id, weapon),
                         parent or self.root, refresh=self.preview.draw)

    def adjust_remote_weapon_hp(self, weapon, delta):
        unit_id = self.selected_id

        def refresh():
            self.preview.draw()
            for side, score in enumerate(self.score_readouts):
                score.configure(text=score_text(self.match.total(side)))

        self.edit(lambda draft: draft.adjust_remote_weapon_hp(unit_id, weapon, delta), self.root, refresh=refresh)

    def refresh_unit_display(self):
        self.preview.draw()
        for hangar in self.player_hangars:
            hangar.draw()

    def clear_unit_status(self, unit_id, status):
        unit = self.match.unit(unit_id)
        if self.match.winner is not None or status not in unit.statuses:
            return
        if self.edit(lambda draft: draft.clear_unit_status(unit_id, status), self.root, refresh=self.refresh_unit_display):
            self.announce(f"●  Saved · {shortened(unit.label, 24)} cleared {status}")

    def view_card(self):
        unit = self.selected_unit()
        show_card(self, unit.card, unit_id=unit.id, attacks=self.attack_profiles(unit),
                  on_attack=lambda parent, profile: self.open_attack(profile, parent=parent))

    def attack_profiles(self, unit):
        if self.match.winner is None and unit.deployed:
            return self.attacks.get(unit.card.number, ())
        return ()

    def open_attack(self, profile=None, *, parent=None):
        unit = self.selected_unit()
        profiles = self.attack_profiles(unit)
        if profiles and (profile is None or profile in profiles):
            DicePrompt(parent or self.root, unit=unit, profiles=profiles, selected=profile, app=self)

    def conflict(self, error, parent):
        messagebox.showwarning("Save Changed", str(error), parent=parent)
        if parent is not self.root:
            parent.destroy()
        self.match, self.revision = self.store.load()
        self.battlefield_scenario = self.match.scenario_id if self.match is not None else None
        if self.active_workspace == MISSION_SORTIE and self.match is not None:
            self.active_workspace = self.setup_return or MATCH_CONSOLE
        self.deployment.stop()
        self.render()
        self.announce("●  Reloaded the latest saved match", "Attention.TLabel")

    def save(self, match, parent, *, replace=False, refresh=None):
        try:
            revision = self.store.save(match, self.revision, replace=replace)
        except SaveConflict as error:
            self.conflict(error, parent)
            return False
        except sqlite3.Error as error:
            self.announce("●  Save failed · Check the match file", "Error.TLabel")
            messagebox.showerror("Match Could Not Be Saved", str(error), parent=parent)
            return False
        if not replace and revision == self.revision:
            return True
        previous = self.match
        self.match, self.revision = match, revision
        if replace:
            self.battlefield_scenario = match.scenario_id
            self.deployment.stop()
            self.selected_id = None
            self.active_workspace = MATCH_CONSOLE
        if replace:
            self.render()
        elif refresh is None:
            self.refresh_console(previous)
        else:
            refresh()
            self.undo_button.state(["!disabled"] if self.store.can_undo() else ["disabled"])
            if self.active_workspace == MATCH_CONSOLE:
                self.refresh_timeline_header()
        self.announce("●  Match saved")
        return True

    def edit(self, action, parent, *, refresh=None):
        draft = deepcopy(self.match)
        try:
            action(draft)
        except ValueError as error:
            messagebox.showerror("Check The Entry", str(error), parent=parent)
            return False
        return self.save(draft, parent, refresh=refresh)

    def undo(self):
        previous = self.match
        try:
            self.match, self.revision = self.store.undo(self.revision)
        except SaveConflict as error:
            self.conflict(error, self.root)
            return
        except sqlite3.Error as error:
            self.announce("●  Undo failed · Check the match file", "Error.TLabel")
            messagebox.showerror("Edit Could Not Be Undone", str(error), parent=self.root)
            return
        self.deployment.stop()
        self.refresh_console(previous)
        self.announce("●  Last edit undone")
