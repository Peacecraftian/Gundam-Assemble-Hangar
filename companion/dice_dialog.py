import tkinter as tk
from math import ceil, sqrt
from time import monotonic
from tkinter import ttk

from .attacks import MAX_DICE, die_result
from .dialogs import Dialog, field, spinner
from .dice import DiceWorld
from .match import attack_damage, whole_number
from .unit_picker import UnitPicker
from .theme import FooterButton, AMBER, AMBER_WELL, BORDER, CELL, DANGER, INK, READY, SIDES, app_cursor, families, panel_heading


TRAY = "#151e22"
GRID = "#202c30"
AMBER_DICE = "#dc9447"


def blend(color, target, amount):
    channels = [round(int(color[i:i+2], 16) * (1 - amount) + int(target[i:i+2], 16) * amount)
                for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(channels)


def rotated(vertex, rotation):
    x, y, z = vertex
    qx, qy, qz, qw = rotation
    tx, ty, tz = 2 * (qy*z - qz*y), 2 * (qz*x - qx*z), 2 * (qx*y - qy*x)
    return (x + qw*tx + qy*tz - qz*ty, y + qw*ty + qz*tx - qx*tz, z + qw*tz + qx*ty - qy*tx)


class DicePrompt(Dialog):
    def __init__(self, parent, *, unit=None, profiles=(), selected=None, app=None):
        super().__init__(parent, "Attack Roll" if unit else "Roll D10s")
        self.unit, self.profiles = unit, profiles
        self.app = app
        self.revision = app.revision if app is not None else None
        self.targets = []
        self.strength = tk.StringVar(master=self.window, value="0" if unit else "1")
        self.accuracy = tk.StringVar(master=self.window, value="0")
        self.pool = tk.StringVar(master=self.window)
        panel = ttk.Frame(self.body, style="Panel.TFrame", padding=(14, 11))
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(1, weight=1)
        header = panel_heading(panel, "D10", unit.label if unit else "Dice Tray")
        header.grid(row=0, columnspan=2, sticky="ew", pady=(0, 7))
        if unit:
            self.weapon = ttk.Combobox(panel, state="readonly", values=[profile.name for profile in profiles], width=29)
            self.weapon.current(profiles.index(selected) if selected else 0)
            self.weapon.bind("<<ComboboxSelected>>", self.update_pool)
            field(panel, 1, "WEAPON", self.weapon)
            self.printed = ttk.Label(panel, style="PanelMuted.TLabel")
            self.printed.grid(row=2, columnspan=2, sticky="w", pady=(2, 6))
            self.initial_focus = self.weapon
            self.upgrades = tk.StringVar(master=self.window, value=str(unit.strength))
            field(panel, 3, "STRENGTH UPGRADES", spinner(panel, self.upgrades, 0, max(MAX_DICE, unit.strength)))
            field(panel, 5, "ACCURACY MODIFIER", spinner(panel, self.accuracy, -99, 99))
            self.upgrades.trace_add("write", self.update_pool)
        strength = spinner(panel, self.strength, -MAX_DICE if unit else 1, MAX_DICE)
        field(panel, 4, "OTHER STRENGTH MODIFIER" if unit else "NUMBER OF DICE", strength)
        ttk.Label(panel, textvariable=self.pool, style="PanelMuted.TLabel").grid(
            row=6, columnspan=2, sticky="w", pady=(6, 0),
        )
        if unit:
            ttk.Label(panel, text="Check range and line of sight at the table before declaring.",
                      style="PanelMuted.TLabel").grid(row=7, columnspan=2, sticky="w", pady=(4, 0))
        if unit and app is not None:
            self.targets = [target for target in app.match.units if target.deployed and target.player != unit.player]
            ttk.Label(panel, text="TARGET", style="Panel.FieldLabel.TLabel").grid(
                row=8, columnspan=2, sticky="w", pady=(8, 3))
            self.target_choice = UnitPicker(panel, app, [(target, None) for target in self.targets])
            self.target_choice.grid(row=9, columnspan=2, sticky="ew")
            if len(self.targets) == 1:
                self.target_choice.current(0)
            self.initial_focus = self.target_choice
            ttk.Label(panel, text="Finalize rerolls, then apply damage to this target." if self.targets
                      else "No deployed enemy units. Deploy a target before attacking.",
                      style="PanelMuted.TLabel").grid(row=10, columnspan=2, sticky="w", pady=(2, 0))
        self.initial_focus = self.initial_focus or strength
        self.roll_button = self.buttons("Roll Dice", self.roll)
        if unit and app is not None and not self.targets:
            self.roll_button.state(["disabled"])
        self.window.bind("<Return>", lambda _event: self.roll())
        self.strength.trace_add("write", self.update_pool)
        self.update_pool()
        self.show()

    def create_tray(self, *args, **kwargs):
        from .status_rules import StatusDiceTray
        return StatusDiceTray(*args, **kwargs)

    def attack(self):
        return self.profiles[self.weapon.current()] if self.unit else None

    def dice_count(self):
        attack = self.attack()
        entered = whole_number(self.strength.get(), "Strength modifier" if attack else "Dice", -MAX_DICE, MAX_DICE)
        if attack:
            upgrades = whole_number(self.upgrades.get(), "Strength upgrades", 0)
            return whole_number(attack.strength + upgrades + entered, "Dice", 0, MAX_DICE)
        return whole_number(entered, "Dice", 1, MAX_DICE)

    def update_pool(self, *_args):
        attack = self.attack()
        if attack:
            self.printed.configure(text=f"TL {attack.timeline}  ·  Range {attack.range}  ·  Strength {attack.strength}")
        try:
            self.pool.set(f"Pool  ·  {self.dice_count()} D10")
        except ValueError:
            self.pool.set(f"Enter a modifier that leaves 0–{MAX_DICE} dice." if attack
                          else f"Choose 1–{MAX_DICE} dice.")

    def roll(self):
        target = None
        try:
            if self.unit and self.app is not None:
                if self.app.revision != self.revision:
                    raise ValueError("The match changed. Close this prompt and start the attack again.")
                if self.target_choice.current() < 0:
                    raise ValueError("Choose a deployed enemy target.")
                target = self.targets[self.target_choice.current()]
            count = self.dice_count()
            accuracy = whole_number(self.accuracy.get(), "Accuracy modifier", -99, 99)
        except ValueError as error:
            self.error(str(error))
            return
        attack = self.attack()
        if attack and target is not None:
            if not self.app.edit(lambda m: m.declare_attack(self.unit.id, target.id, attack, count, accuracy), self.window):
                return
            self.revision = self.app.revision
        title = f"{self.unit.label}  /  {attack.name}" if attack else "Free Roll"
        parent = self.window.master
        self.window.destroy()
        self.create_tray(parent, title, count, accuracy, self.unit.player if attack else None,
                 app=self.app, attacker=self.unit, target=target, weapon=attack, revision=self.revision)


class DiceTray(Dialog):
    def __init__(self, parent, title, count, accuracy, side, *, app=None, attacker=None,
                 target=None, weapon=None, revision=None):
        super().__init__(parent, "Dice Tray")
        self.count, self.side = count, side
        self.app, self.attacker, self.target, self.weapon = app, attacker, target, weapon
        self.revision = revision
        self.applied = self.applying = self.stale = False
        self.damage_modifier = tk.StringVar(master=self.window, value="0")
        self.color = AMBER_DICE if side is None else SIDES[side]
        self.job = None
        self.world = None
        self.poses = []
        self.values = None
        self.selected = set()
        self.reroll_indices = ()
        self.focused_die = 0
        self.result_columns = 1
        self.state = "starting"
        self.tray_size = None
        self.accuracy = tk.StringVar(master=self.window, value=str(accuracy))
        self.status = ttk.Label(self.footer, text="Initializing tray…", style="RailMeta.TLabel")
        self.status.pack(side="left")
        self.close_button = FooterButton(self.footer, text="Close", command=self.cancel, style="Quiet.TButton")
        self.close_button.pack(side="right")
        self.apply_button = None
        if target is not None:
            self.apply_button = FooterButton(self.footer, text="Apply Damage", style="Primary.TButton",
                                           command=self.apply_damage, state="disabled")
            self.apply_button.pack(side="right", padx=(6, 0))
        self.controls = ttk.Frame(self.footer, style="RailFill.TFrame")
        self.reroll_button = FooterButton(self.controls, text="Reroll Selected", style="Primary.TButton", command=self.reroll)
        self.reroll_button.pack(side="right")
        if side is not None:
            ttk.Label(self.controls, text="ACCURACY", style="RailMeta.TLabel").pack(side="left", padx=(0, 5))
            spinner(self.controls, self.accuracy, -99, 99, width=4).pack(side="left", padx=(0, 10))
        heading = panel_heading(self.body, "D10", title)
        heading.pack(fill="x", pady=(0, 8))
        if target is not None:
            resolution = ttk.Frame(self.body, style="Panel.TFrame", padding=(9, 6))
            resolution.pack(fill="x", pady=(0, 6))
            resolution.columnconfigure(0, weight=1)
            ttk.Label(resolution, text=f"TARGET  ·  {target.label}    |    Weapon TL {weapon.timeline}", style="Panel.TLabel", wraplength=420).grid(
                row=0, column=0, sticky="w")
            modifiers = ttk.Frame(resolution, style="PanelFill.TFrame")
            modifiers.grid(row=0, column=1, sticky="e")
            ttk.Label(modifiers, text="DAMAGE MODIFIER", style="Panel.FieldLabel.TLabel").pack(side="left", padx=6)
            spinner(modifiers, self.damage_modifier, -99, 99, width=4).pack(side="left")
            self.damage_summary = ttk.Label(resolution, text="Damage is applied after the final roll.",
                                            style="PanelMuted.TLabel", wraplength=780)
            self.damage_summary.grid(row=1, columnspan=2, sticky="w", pady=(3, 0))
            ttk.Label(resolution, text="Resolve critical effects, Fracture and other abilities at the table;"
                      " enter damage adjustments before Shields.", style="PanelMuted.TLabel", wraplength=750).grid(
                          row=2, columnspan=2, sticky="w", pady=(3, 0))
        self.canvas = tk.Canvas(self.body, background=TRAY, width=650, height=240 if target is not None else 330, highlightthickness=1,
                                highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<Button-1>", self.pick_die)
        self.canvas.bind("<Motion>", self.hover_die)
        self.canvas.bind("<KeyPress>", self.die_key)
        self.canvas.bind("<FocusIn>", self.update_results)
        self.canvas.bind("<FocusOut>", self.update_results)
        self.heading, self.mono = families(self.window)
        self.accuracy.trace_add("write", self.update_results)
        self.damage_modifier.trace_add("write", self.update_results)
        self.window.bind("<Destroy>", self.cleanup, add="+")
        self.initial_focus = self.close_button
        root = parent.winfo_toplevel()
        while isinstance(root.master, tk.Misc):
            root = root.master.winfo_toplevel()
        self.show((min(1150, root.winfo_width() - 80), min(670, root.winfo_height() - 72)))
        self.job = self.window.after_idle(self.start)

    def cleanup(self, event):
        if event.widget is self.window:
            if self.job is not None:
                self.window.after_cancel(self.job)
                self.job = None
            if self.world is not None:
                self.world.close()
                self.world = None

    def start(self):
        self.job = None
        if self.apply_button is not None:
            self.apply_button.state(["disabled"])
        count = len(self.reroll_indices) if self.reroll_indices else self.count
        if count == 0:
            self.reveal(())
            return
        try:
            if self.world is None:
                self.world = DiceWorld()
            self.world.start(count, self.canvas.winfo_width() / max(1, self.canvas.winfo_height()))
        except (ImportError, OSError, RuntimeError) as error:
            self.failed(error)
            return
        self.state = "rolling"
        self.canvas.delete("result")
        self.canvas.configure(cursor="", takefocus=False)
        self.controls.pack_forget()
        self.close_button.focus_set()
        self.status.configure(text=f"Rerolling {count} of {self.count} dice…" if self.reroll_indices
                              else f"Rolling {count} D10…")
        self.tick()

    def tick(self):
        self.job = None
        now = monotonic()
        try:
            self.poses, rolled = self.world.step(4)
        except RuntimeError as error:
            self.failed(error)
            return
        self.draw_dice()
        if rolled is None:
            delay = max(1, round(1000 / 30 - (monotonic() - now) * 1000))
            self.job = self.window.after(delay, self.tick)
        else:
            self.state = "settled"
            self.status.configure(text="Reading settled dice…")
            self.job = self.window.after(540, self.fade, monotonic() + .54, rolled)

    def failed(self, error):
        self.canvas.delete("dice")
        self.poses = []
        if self.reroll_indices:
            self.reroll_indices = ()
            self.show_results()
        else:
            self.state = "failed"
            self.status.configure(text="Dice tray unavailable", style="Error.TLabel")
        self.error(f"The offline dice engine could not complete the roll.\n\n{error}")

    def fade(self, started, rolled):
        self.job = None
        progress = min(1, max(0, (monotonic() - started) / .31))
        if progress < 1:
            self.draw_dice(progress)
            self.job = self.window.after(24, self.fade, started, rolled)
        else:
            self.reveal(rolled)

    def resize(self, _event=None):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if (width, height) == self.tray_size:
            return
        self.tray_size = width, height
        self.canvas.delete("grid")
        for x in range(width // 2 % 28, width, 28):
            self.canvas.create_line(x, 1, x, height - 2, fill=GRID, tags="grid")
        for y in range(height // 2 % 28, height, 28):
            self.canvas.create_line(1, y, width - 2, y, fill=GRID, tags="grid")
        self.canvas.tag_lower("grid")
        if self.state == "results":
            self.update_results()
        elif self.poses:
            self.draw_dice()

    def draw_dice(self, fade=0):
        canvas = self.canvas
        canvas.delete("dice")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        scale = min(width / self.world.width, height / self.world.height)
        xmid, ymid = width / 2, height / 2
        ordered = sorted(enumerate(self.poses), key=lambda item: item[1][2])
        shadow = blend("#0b1215", TRAY, fade)
        inks = (blend(INK, TRAY, fade), blend("#172628", TRAY, fade))
        edge = blend("#142328", TRAY, fade)
        light = (blend(self.color, "#151c20", .52), self.color, blend(self.color, "#fff2d7", .45))
        colors = tuple(blend(shade, TRAY, fade) for shade in light)
        for _, (x, y, z, *_) in ordered:
            sx, sy = xmid + (x + .23 * z) * scale, ymid - (y + .18 * z) * scale
            canvas.create_oval(sx - .81*scale, sy - .6*scale, sx + .81*scale, sy + .6*scale,
                               fill=shadow, outline="", tags="dice")
        for die, (x, y, z, *rotation) in ordered:
            vertices = [rotated(vertex, rotation) for vertex in self.world.vertices]
            for i, face in enumerate(self.world.faces):
                corners = [vertices[j] for j in face]
                a, b, c, _ = corners
                area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
                if area <= .02:
                    continue
                polygon = [(xmid + (x + vx) * scale, ymid - (y + vy) * scale) for vx, vy, _ in corners]
                shade = 2 if area > .86 else 1 if area > .42 else 0
                canvas.create_polygon(polygon, fill=colors[shade], outline=edge, width=1, tags="dice")
                if area > .28:
                    cx, cy = (sum(point[axis] for point in polygon) / 4 for axis in (0, 1))
                    size = max(7, round(scale * (.43 if area > .72 else .30)))
                    canvas.create_text(cx, cy, text=self.world.number(die, i), fill=inks[bool(shade)],
                                       font=(self.mono, -size, "bold"), tags="dice")

    def reveal(self, rolled):
        if self.reroll_indices:
            values = list(self.values)
            for index, face in zip(self.reroll_indices, rolled, strict=True):
                values[index] = face
            self.values = tuple(values)
        else:
            self.values = rolled
        self.reroll_indices = ()
        self.selected.clear()
        self.show_results()

    def show_results(self):
        self.canvas.delete("dice")
        self.poses = []
        self.state = "results"
        self.canvas.configure(takefocus=bool(self.values))
        if self.side is not None or self.values:
            self.controls.pack(side="right", padx=12)
        self.update_results()

    def die_at(self, event):
        for item in self.canvas.find_overlapping(event.x, event.y, event.x, event.y):
            for tag in self.canvas.gettags(item):
                if tag.startswith("die-"):
                    return int(tag[4:])
        return None

    def hover_die(self, event):
        self.canvas.configure(cursor=app_cursor(self.canvas, "hand2") if self.die_at(event) is not None else "")

    def pick_die(self, event):
        index = self.die_at(event)
        if index is not None:
            self.focused_die = index
            self.canvas.focus_set()
            self.toggle_die()

    def die_key(self, event):
        if self.state != "results" or not self.values:
            return
        if event.keysym == "space":
            self.toggle_die()
        else:
            steps = {"Left": -1, "Right": 1, "Up": -self.result_columns, "Down": self.result_columns}
            if event.keysym not in steps:
                return
            self.focused_die = max(0, min(len(self.values) - 1, self.focused_die + steps[event.keysym]))
            self.update_results()
        return "break"

    def toggle_die(self):
        self.selected.symmetric_difference_update({self.focused_die})
        self.update_results()

    def reroll(self):
        if self.state == "results" and self.selected and not self.reroll_button.instate(["disabled"]):
            self.reroll_indices = tuple(sorted(self.selected))
            self.start()

    def update_results(self, *_args):
        if self.state != "results":
            return
        canvas = self.canvas
        canvas.delete("result")
        if self.apply_button is not None:
            self.apply_button.state(["disabled"])
        self.reroll_button.state(["disabled"])
        if self.selected:
            self.status.configure(text=f"{len(self.selected)} selected")
        else:
            self.status.configure(text="Select dice to reroll." if self.values else "Roll complete")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        try:
            accuracy = whole_number(self.accuracy.get(), "Accuracy modifier", -99, 99)
        except ValueError:
            if self.target is not None:
                self.damage_summary.configure(text="Enter a valid Accuracy modifier before applying damage.")
            canvas.create_text(width / 2, height / 2, text="Enter a whole Accuracy modifier from −99 to +99.",
                               fill=INK, font=(self.heading, -16, "bold"), tags="result")
            return
        if self.selected:
            self.reroll_button.state(["!disabled"])
        attack = self.side is not None
        card_number = self.attacker.card.number if self.attacker else None
        results = [die_result(value, accuracy, card_number) for value in self.values] if attack else ["roll"] * len(self.values)
        criticals = results.count("critical")
        hits = results.count("hit") + criticals
        if self.target is not None:
            self.update_damage(hits)
        label = f"{hits} {'HIT' if hits == 1 else 'HITS'}" if attack else f"{len(results)} D10  /  TOTAL {sum(self.values)}"
        detail = (f"{criticals} critical  ·  {results.count('miss')} misses  ·  Accuracy {accuracy:+d}"
                  if attack else "DICE RESULTS")
        cols = max(1, min(len(results), width // 53 - 1))
        self.result_columns = cols
        rows = ceil(len(results) / cols)
        slot = min(58, (width - 32) // cols)
        row_height = min(56, max(30, (height - 119) // max(1, rows)))
        top = max(8, (height - 108 - rows * row_height) // 2)
        canvas.create_text(width / 2, top + 34, text=label, fill=AMBER,
                           font=(self.heading, -48, "bold"), tags="result")
        canvas.create_text(width / 2, top + 73, text=detail, fill=INK, font=(self.mono, -14), tags="result")
        colors = {"critical": AMBER, "hit": READY, "miss": DANGER, "roll": INK}
        for i, (value, result) in enumerate(zip(self.values, results)):
            row, column = divmod(i, cols)
            columns = min(cols, len(results) - row * cols)
            x = (width - columns * slot) / 2 + (column + .5) * slot
            y = top + 98 + (row + .5) * row_height
            color = colors[result]
            marked = i in self.selected
            tags = ("result", f"die-{i}")
            display = f"{value}→{value + accuracy}" if attack and accuracy and 1 < value < 9 else str(value)
            x1, y1 = x - slot / 2 + 3, y - row_height / 2 + 3
            x2, y2 = x + slot / 2 - 3, y + row_height / 2 - 3
            canvas.create_rectangle(x1, y1, x2, y2, fill=AMBER_WELL if marked else CELL,
                                    outline=AMBER if marked else color, width=2 if marked else 1, tags=tags)
            canvas.create_text(x, y - (5 if attack else 0), text=display, fill=INK,
                               font=(self.mono, -12 if len(display) > 3 else -16, "bold"), tags=tags)
            if attack:
                canvas.create_text(x, y + 10, text="CRIT" if result == "critical" else result.upper(),
                                   fill=color, font=(self.mono, -9, "bold"), tags=tags)
            if marked:
                canvas.create_text(x2 - 6, y1 + 6, text="✓", fill=AMBER, font=(self.mono, -9), tags=tags)
            if i == self.focused_die and canvas.focus_get() is canvas:
                canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, outline=INK, dash=(2, 2), tags=tags)

    def update_damage(self, hits):
        try:
            modifier = whole_number(self.damage_modifier.get(), "Damage modifier", -99, 99)
            blocked, damage = attack_damage(hits, modifier, self.target.shield_active)
        except ValueError as error:
            self.damage_summary.configure(text=str(error))
            return
        if self.app.revision != self.revision or self.stale:
            self.damage_summary.configure(text="The match changed. Close this roll and start a new attack.")
            return
        defeated = damage > 0 and damage >= self.target.hp
        outcome = (f"DEFEAT · +{self.target.card.vp} VP · Reserve / TL +2 / HP restored" if defeated
                   else f"HP {self.target.hp} → {max(0, self.target.hp-damage)}")
        shields = "Shield" if blocked == 1 else "Shields"
        self.damage_summary.configure(text=f"{hits} hits {modifier:+d} modifier − {blocked} {shields} = {damage} damage  ·  {outcome}")
        if not self.applying and not self.applied:
            self.apply_button.state(["!disabled"])

    def apply_damage(self):
        if self.state != "results" or self.applying or self.applied or self.target is None:
            return
        if self.app.revision != self.revision:
            self.stale = True
            self.update_results()
            return
        try:
            accuracy = whole_number(self.accuracy.get(), "Accuracy modifier", -99, 99)
            modifier = whole_number(self.damage_modifier.get(), "Damage modifier", -99, 99)
            hits = sum(die_result(value, accuracy) != "miss" for value in self.values)
            _, damage = attack_damage(hits, modifier, self.target.shield_active)
        except ValueError as error:
            self.error(str(error))
            return
        self.applying = True
        self.apply_button.state(["disabled"])
        outcome = []
        saved = self.app.edit(lambda match: outcome.append(match.resolve_attack(
            self.attacker.id, self.target.id, hits, timeline_cost=self.weapon.timeline, modifier=modifier,
            note=f"{self.attacker.label} / {self.weapon.name}")), self.window)
        if not saved:
            self.applying = False
            if self.window.winfo_exists():
                self.update_results()
            return
        self.applied = True
        self.cancel()
        if outcome[0]:
            self.app.announce(f"●  Saved · {self.target.label} defeated · +{self.target.card.vp} VP")
            self.app.deployment.play_defeat()
        else:
            self.app.announce(f"●  Saved · {self.target.label} · {damage} HP damage")
