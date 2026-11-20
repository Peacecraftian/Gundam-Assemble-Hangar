import math
import sqlite3
import tkinter as tk
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk
from uuid import uuid4

from PIL import Image, ImageDraw

from .artwork import map_token_art, objective_art, published_token_art, scenario_token_art, token_puff_art
from .battlefield_stars import draw_ground_stars
from .dialogs import overflow_scrollbar
from .scenarios import (
    DEFAULT_PALETTE, HEX_COLUMN_LENGTHS, HEX_KEYS, MISSION_FIELDS, NEW_SCENARIO, NUMBERED_TOKENS, PALETTES, SPECIAL_TERRAIN,
    SPECIAL_TERRAIN_RULES, TERRAIN, TOKENS, read_scenario_file, scenario_choices, set_scenario_token, write_scenario_file,
)
from .storage import LOCAL_SCENARIO_PREFIX, UNDO_LIMIT, SaveConflict
from .theme import FooterButton, AMBER, BORDER, CELL, DISPLAY_FAMILY, FOCUS, INK, PANEL, SIDES, app_cursor, panel_heading


SCENARIO_FILE_TYPES = (("Scenario JSON", "*.json"),)
HEX_DIVIDER = "#030710"
HEX_SELECTION = "#FFFFE4"
PLACEMENT_SCALES = (.84, .67, .85, 1.17, 1.07, .97, 1)


def terrain_swatch(color):
    swatch = Image.new("RGBA", (24, 24))
    ImageDraw.Draw(swatch).polygon(((1, 12), (6, 2), (18, 2), (23, 12), (18, 22), (6, 22)),
                                   fill=color, outline=HEX_DIVIDER)
    return swatch


@dataclass
class TerrainStroke:
    clear: bool
    change: tuple[str, str | None]
    point: tuple[int, int]
    before: dict


class BattlefieldScreen:
    def __init__(self, parent, app):
        self.app = app
        self.draft_cells = None
        self.brush = None
        self.brushes = {}
        self.terrain_stroke = None
        self.placement_job = None
        self.placement_photos = ()
        self.undo_cells = deque(maxlen=UNDO_LIMIT)
        self.redo_cells = deque(maxlen=UNDO_LIMIT)
        self.frame = app.workspace.layer(parent)
        self.frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.frame.columnconfigure((0, 2), weight=1, uniform="battlefield_menus", minsize=215)
        self.frame.columnconfigure(1, weight=4, minsize=340)
        self.frame.rowconfigure(0, weight=1)
        left = ttk.Frame(self.frame, style="Panel.TFrame", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel_heading(left, "01", "Mission briefing").pack(fill="x")
        self.choice = ttk.Combobox(left, state="readonly", width=20)
        self.choice.pack(fill="x", pady=10)
        self.choice.bind("<<ComboboxSelected>>", self.select)
        self.link_notice = ttk.Label(left, text="The match’s scenario is unavailable.",
                                     style="PanelMuted.TLabel", wraplength=200)
        self.edit_button = ttk.Button(left, text="Edit Mode", style="Quiet.TButton", command=self.start_edit)
        self.edit_button.pack(anchor="w", padx=3)
        self.briefing_frame = ttk.Frame(left, style="PanelFill.TFrame")
        self.briefing_frame.pack(fill="both", expand=True)
        self.briefing = tk.Text(self.briefing_frame, width=20, height=10, wrap="word", background=PANEL,
                               foreground=INK, borderwidth=0, highlightthickness=0,
                               font=("Segoe UI", 10), padx=8, pady=4)
        self.briefing.tag_configure("heading", foreground=AMBER, font=(DISPLAY_FAMILY, 11, "bold"),
                                    spacing1=4, spacing3=1)
        self.briefing.tag_configure("title", font=(DISPLAY_FAMILY, 12, "bold"))
        self.briefing.tag_configure("paragraph_gap", font=("Segoe UI", -4), spacing3=14)
        scrollbar = ttk.Scrollbar(self.briefing_frame, orient="vertical", command=self.briefing.yview)
        scrollbar.pack(side="right", fill="y")
        self.briefing.configure(yscrollcommand=scrollbar.set)
        self.briefing.pack(side="left", fill="both", expand=True)
        self.editor = self.build_editor(left)
        self.canvas = app.workspace.layer(self.frame)
        self.canvas.configure(takefocus=True)
        self.canvas.grid(row=0, column=1, sticky="nsew")
        style = ttk.Style(self.frame)
        self.map_font = font.Font(root=self.canvas, font=style.lookup("TLabel", "font"))
        self.objective_font = font.Font(root=self.canvas, font=style.lookup("PanelCode.TLabel", "font"))
        self.objective_font.configure(weight="bold")
        self.side_name_font = font.Font(root=self.canvas, font=style.lookup("Name0.TEntry", "font"))
        self.side_meta_font = font.Font(root=self.canvas, font=style.lookup("SideMeta0.TLabel", "font"))
        self.side_badges = [app.photos.get(objective_art, side) for side in range(2)]
        right = ttk.Frame(self.frame, style="Panel.TFrame", padding=(10, 8))
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        legend_panel = ttk.Frame(right, style="PanelFill.TFrame")
        legend_panel.grid(row=0, column=0, sticky="nsew")
        palette = self.build_palette(legend_panel)
        self.build_terrain_hud(right, style)
        for role in ("Quiet", "Primary"):
            style.configure(f"Brush.{role}.TButton", anchor="w", padding=(5, 1))
        panel_heading(palette, "02", "Terrain").pack(fill="x")
        ttk.Label(palette, text="PALETTE", style="Panel.FieldLabel.TLabel").pack(anchor="w", pady=(6, 2))
        self.palette_choice = ttk.Combobox(palette, state="readonly", width=16,
                                          values=[name.title() for name in PALETTES])
        self.palette_choice.pack(fill="x", pady=(0, 6))
        self.palette_choice.bind("<<ComboboxSelected>>", self.choose_palette)
        for key, label in TERRAIN.items():
            self.legend(palette, "terrain", key, label, None)
        panel_heading(palette, "03", "Special Terrain").pack(fill="x", pady=(8, 0))
        for key, (label, artwork) in SPECIAL_TERRAIN.items():
            self.legend(palette, "special_terrain", key, label, app.photos.get(published_token_art, artwork, 27))
        panel_heading(palette, "04", "Tokens").pack(fill="x", pady=(8, 0))
        for key, (label, artwork) in TOKENS.items():
            self.legend(palette, "token", key, label, app.photos.get(scenario_token_art, artwork, 27))
        self.footer = ttk.Frame(self.frame, style="Rail.TFrame", padding=(8, 4))
        self.footer.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        for label, command in (("Import", self.import_scenario), ("Export", self.export_scenario)):
            FooterButton(self.footer, text=label, style="Quiet.TButton", command=command).pack(
                side="left", padx=(0, 6),
            )
        self.undo_button = FooterButton(self.footer, text="Undo", style="Quiet.TButton",
                                      command=lambda: self.apply_history(self.undo_cells, self.redo_cells))
        self.redo_button = FooterButton(self.footer, text="Redo", style="Quiet.TButton",
                                      command=lambda: self.apply_history(self.redo_cells, self.undo_cells))
        self.update_history_buttons()
        self.save_button = FooterButton(self.footer, text="Save", style="Primary.TButton", command=self.save_edit)
        self.cancel_button = FooterButton(self.footer, text="Cancel", style="Quiet.TButton", command=self.cancel_edit)
        self.delete_button = FooterButton(self.footer, text="Delete", style="Danger.TButton", command=self.delete_edit)
        self.hint = ttk.Label(self.footer, text="")
        self.hint.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.footer.bind("<Configure>", self.layout_footer)
        self.selected = HEX_KEYS[0]
        self.canvas.bind("<Configure>", self.draw, add="+")
        self.canvas.bind("<FocusIn>", self.draw)
        self.canvas.bind("<FocusOut>", self.draw)
        self.canvas.bind("<Destroy>", self.stop_token_placement, add="+")
        for button, clear in ((1, False), (3, True)):
            self.canvas.bind(f"<Button-{button}>", lambda event, clear=clear: self.inspect(event, clear=clear))
            self.canvas.bind(f"<B{button}-Motion>", lambda event, clear=clear: self.drag_terrain(event, clear=clear))
            self.canvas.bind(f"<ButtonRelease-{button}>",
                             lambda event, clear=clear: self.end_terrain_stroke(event, clear=clear))
        self.canvas.bind("<space>", lambda _event: self.paint_selected())
        self.canvas.bind("<Delete>", lambda _event: self.paint_selected(clear=True))
        for key in ("Left", "Right", "Up", "Down"):
            self.canvas.bind(f"<{key}>", self.move)
        self.refresh_scenarios(app.battlefield_scenario)

    @property
    def editing(self):
        return self.draft_cells is not None

    def layout_footer(self, _event=None):
        # Preserve brush guidance without squeezing the seven editing actions.
        stacked = self.editing and self.footer.winfo_width() < 1100
        side = "top" if stacked else "left"
        if str(self.hint.pack_info().get("side")) == side:
            return
        self.hint.pack_forget()
        actions = self.footer.pack_slaves()
        placement = {"before": actions[0]} if stacked else {}
        self.hint.pack(side=side, fill="x", expand=not stacked, padx=(4, 6),
                       pady=(0, 3) if stacked else 0, **placement)

    @property
    def cells(self):
        return self.draft_cells if self.editing else self.scenario["cells"]

    @property
    def palette_id(self):
        return self.palette_choice.get().lower()

    @property
    def view_palette(self):
        return self.app.battlefield_palettes.get(self.scenario["id"], self.scenario["palette"])

    def build_terrain_hud(self, parent, style):
        self.hud_terrain = None
        self.terrain_hud = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 6))
        self.terrain_hud.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.terrain_hud.grid_remove()
        ttk.Label(self.terrain_hud, text="SPECIAL TERRAIN RULES", style="Panel.FieldLabel.TLabel").pack(anchor="w")
        self.terrain_rule_title = ttk.Label(self.terrain_hud, style="Panel.TLabel",
                                            font=style.lookup("Rail.TLabel", "font"))
        self.terrain_rule_title.pack(anchor="w", pady=(3, 2))
        self.terrain_rule_text = ttk.Label(self.terrain_hud, style="Panel.TLabel", justify="left", width=1)
        self.terrain_rule_text.pack(fill="x")
        self.terrain_rule_text.bind("<Configure>", lambda event: self.terrain_rule_text.configure(wraplength=event.width))
        ttk.Label(self.terrain_hud, text="Core Rules v1.2 · p. 39", style="PanelMuted.TLabel").pack(
            anchor="w", pady=(4, 0),
        )

    def show_terrain_rules(self, terrain):
        if terrain == self.hud_terrain:
            return
        self.hud_terrain = terrain
        if terrain is None:
            self.terrain_hud.grid_remove()
            return
        self.terrain_rule_title.configure(text=SPECIAL_TERRAIN[terrain][0])
        self.terrain_rule_text.configure(text=SPECIAL_TERRAIN_RULES[terrain])
        self.terrain_hud.grid()

    def build_editor(self, parent):
        editor = ttk.Frame(parent, style="PanelFill.TFrame")
        editor.columnconfigure(0, weight=1)
        self.fields = {}
        for index, (label, key) in enumerate(MISSION_FIELDS):
            row = 2 * index
            ttk.Label(editor, text=label, style="Panel.FieldLabel.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(4, 2),
            )
            if key in ("name", "location"):
                field = ttk.Entry(editor, width=20)
                field.grid(row=row + 1, column=0, columnspan=2, sticky="ew")
            else:
                field = tk.Text(editor, width=20, height=3, wrap="word", undo=True, background=CELL,
                                foreground=INK, insertbackground=AMBER, borderwidth=0, highlightthickness=1,
                                highlightbackground=BORDER, highlightcolor=FOCUS,
                                font=("Segoe UI", 10), padx=6, pady=4)
                field.configure(cursor=app_cursor(field, "ibeam"))
                field.grid(row=row + 1, column=0, sticky="nsew")
                scrollbar = ttk.Scrollbar(editor, orient="vertical", command=field.yview)
                scrollbar.grid(row=row + 1, column=1, sticky="ns")
                field.configure(yscrollcommand=scrollbar.set)
                editor.rowconfigure(row + 1, weight=1)
            from .dialogs import touch_keyboard
            touch_keyboard(field, label, multiline=isinstance(field, tk.Text))
            self.fields[key] = field
        return editor

    def build_palette(self, parent):
        self.palette = tk.Canvas(parent, width=140, height=1, background=PANEL, highlightthickness=0)
        self.palette.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.palette.yview)
        self.palette.configure(yscrollcommand=lambda first, last: overflow_scrollbar(scrollbar, first, last))
        content = ttk.Frame(self.palette, style="PanelFill.TFrame")
        mount = self.palette.create_window(0, 0, window=content, anchor="nw")

        def resize(event):
            self.palette.itemconfigure(mount, width=event.width)
            # Use tighter spacing when the footer leaves less room for the brushes.
            row_gap = 1 if event.height < 475 else 4
            for display, _ in self.brushes.values():
                display.master.pack_configure(pady=(0, row_gap))

        self.palette.bind("<Configure>", resize)
        content.bind("<Configure>", lambda _event: self.palette.configure(
            width=content.winfo_reqwidth(), scrollregion=self.palette.bbox(mount),
        ))
        self.palette.bind("<MouseWheel>", self.scroll_palette)
        content.bind("<MouseWheel>", self.scroll_palette)
        return content

    def scroll_palette(self, event):
        self.palette.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def show_focused_brush(self, event):
        button = event.widget
        top = button.winfo_y() + button.master.winfo_y()
        height = self.palette.winfo_height()
        view_top = self.palette.canvasy(0)
        target = min(top, max(view_top, top + button.winfo_height() - height))
        self.palette.yview_moveto(target / button.master.master.winfo_height())

    def legend(self, parent, layer, key, label, photo):
        row = ttk.Frame(parent, style="PanelFill.TFrame")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        display = ttk.Label(row, text=label, image=photo, compound="left", style="Panel.TLabel")
        display.photo = photo
        display.grid(sticky="ew")
        brush = (layer, key)
        button = ttk.Button(row, text=label, image=photo, compound="left", style="Brush.Quiet.TButton",
                            command=lambda: self.choose_brush(brush))
        button.grid(row=0, column=0, sticky="ew")
        button.grid_remove()
        button.bind("<FocusIn>", self.show_focused_brush)
        for widget in (row, display, button):
            widget.bind("<MouseWheel>", self.scroll_palette)
        self.brushes[brush] = (display, button)

    def show_palette(self, palette_id):
        self.palette_choice.set(palette_id.title())
        for key, color in PALETTES[palette_id].items():
            display, button = self.brushes["terrain", key]
            display.photo = self.app.photos.get(terrain_swatch, color)
            display.configure(image=display.photo)
            button.configure(image=display.photo)

    def choose_palette(self, _event):
        self.finish_terrain_stroke()
        if not self.editing:
            self.app.battlefield_palettes[self.scenario["id"]] = self.palette_id
        self.show_palette(self.palette_id)
        self.draw()

    def refresh_scenarios(self, selected_id):
        self.scenarios, labels = scenario_choices(self.app.store)
        positions = {scenario["id"]: index for index, (scenario, _) in enumerate(self.scenarios)}
        linked_id = self.app.match.scenario_id if self.app.match is not None else None
        if linked_id and linked_id not in positions:
            self.link_notice.pack(before=self.edit_button, anchor="w", padx=3, pady=(0, 5))
        else:
            self.link_notice.pack_forget()
        self.choice.configure(values=[*labels, NEW_SCENARIO])
        self.choice.current(positions.get(selected_id, positions.get(linked_id, 0)))
        self.select()

    def select(self, _event=None):
        index = self.choice.current()
        if index == len(self.scenarios):
            blank_fields = {field: "" for _, field in MISSION_FIELDS}
            self.scenario = dict(id=None, palette=DEFAULT_PALETTE,
                                 cells={key: {"terrain": "ground"} for key in HEX_KEYS}, **blank_fields)
            self.revision = 0
            self.selected = HEX_KEYS[0]
            self.show_palette(self.view_palette)
            self.start_edit()
            self.fields["name"].focus_set()
            return
        self.scenario, self.revision = self.scenarios[index]
        self.app.battlefield_scenario = self.scenario["id"]
        self.show_palette(self.view_palette)
        self.briefing.configure(state="normal")
        self.briefing.delete("1.0", "end")
        for heading, field in MISSION_FIELDS:
            self.briefing.insert("end", heading.upper() + "\n", "heading")
            text_style = "title" if field == "name" else ()
            for line in self.scenario[field].split("\n"):
                self.briefing.insert("end", line + "\n", text_style if line.strip() else "paragraph_gap")
        self.briefing.configure(state="disabled")
        self.briefing.yview_moveto(0)
        self.hint.configure(text="Share scenarios as JSON files.")
        self.draw()

    def start_edit(self):
        self.draft_cells = deepcopy(self.scenario["cells"])
        for key, widget in self.fields.items():
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", self.scenario[key])
                widget.edit_reset()
            else:
                widget.delete(0, "end")
                widget.insert(0, self.scenario[key])
                widget.xview_moveto(0)
        self.choice.state(["disabled"])
        self.edit_button.pack_forget()
        self.briefing_frame.pack_forget()
        self.editor.pack(fill="both", expand=True)
        for display, button in self.brushes.values():
            display.grid_remove()
            button.grid()
        self.palette.yview_moveto(0)
        for button in (self.undo_button, self.redo_button):
            button.pack(side="left", before=self.hint, padx=(0, 6))
        self.save_button.pack(side="right", before=self.hint)
        self.cancel_button.pack(side="right", before=self.hint, padx=(0, 6))
        if self.can_delete():
            self.delete_button.pack(side="right", before=self.hint, padx=(0, 6))
        self.layout_footer()
        self.choose_brush(None)
        self.canvas.focus_set()
        self.draw()

    def choose_brush(self, brush):
        self.finish_terrain_stroke()
        if self.brush is not None:
            self.brushes[self.brush][1].configure(style="Brush.Quiet.TButton")
        self.brush = brush
        hint = "Choose a brush. Right-drag to reset terrain."
        if brush is not None:
            button = self.brushes[brush][1]
            button.configure(style="Brush.Primary.TButton")
            label = button.cget("text")
            if brush[0] == "terrain":
                hint = f"{label} brush  ·  Left-drag to paint  ·  Right-drag to reset"
            elif brush[0] == "special_terrain":
                hint = f"{label} brush  ·  Left-drag to paint  ·  Right-drag to erase"
            else:
                hint = f"{label} brush  ·  Left-click to place  ·  Right-click to remove token"
        self.hint.configure(text=hint)

    def mission_fields(self):
        return {key: widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get().strip()
                for key, widget in self.fields.items()}

    def can_leave(self):
        if not self.editing:
            return True
        changed = self.draft_cells != self.scenario["cells"] or self.palette_id != self.view_palette or any(
            self.scenario[key] != value for key, value in self.mission_fields().items()
        )
        return not changed or messagebox.askokcancel(
            "Discard scenario edits?", "Leave Edit Mode and discard the unsaved changes?",
            parent=self.frame, icon="warning", default="cancel",
        )

    def cancel_edit(self):
        if self.can_leave():
            self.end_edit(self.app.battlefield_scenario)

    def end_edit(self, selected_id):
        self.choose_brush(None)
        self.stop_token_placement()
        self.draft_cells = None
        self.undo_cells.clear()
        self.redo_cells.clear()
        self.update_history_buttons()
        self.choice.state(["!disabled"])
        self.editor.pack_forget()
        self.edit_button.pack(anchor="w", padx=3)
        self.briefing_frame.pack(fill="both", expand=True)
        for display, button in self.brushes.values():
            button.grid_remove()
            display.grid()
        self.palette.yview_moveto(0)
        for button in (self.undo_button, self.redo_button, self.save_button, self.cancel_button, self.delete_button):
            button.pack_forget()
        self.layout_footer()
        self.refresh_scenarios(selected_id)
        self.edit_button.focus_set()

    def draft_scenario(self):
        fields = self.mission_fields()
        for label, key in MISSION_FIELDS:
            if not fields[key].strip():
                messagebox.showerror("Scenario needs more information", f"Enter the {label.lower()}.", parent=self.frame)
                self.fields[key].focus_set()
                return None
        scenario_id = self.scenario["id"] if self.revision else f"{LOCAL_SCENARIO_PREFIX}{uuid4().hex}"
        return dict(id=scenario_id, palette=self.palette_id, cells=self.draft_cells, **fields)

    def save_edit(self):
        scenario = self.draft_scenario()
        if scenario is None:
            return
        try:
            self.app.store.save_scenario(scenario, self.revision)
        except (sqlite3.Error, SaveConflict) as error:
            messagebox.showerror("Could not save scenario", str(error), parent=self.frame)
            return
        self.app.battlefield_palettes.pop(scenario["id"], None)
        self.end_edit(scenario["id"])

    def import_scenario(self):
        filename = filedialog.askopenfilename(title="Import scenario", parent=self.frame, filetypes=SCENARIO_FILE_TYPES)
        if not filename:
            return
        try:
            scenario = read_scenario_file(Path(filename))
        except (OSError, ValueError, RecursionError) as error:
            messagebox.showerror("Could not import scenario", str(error), parent=self.frame)
            return
        if not self.can_leave():
            return
        scenario_id = f"{LOCAL_SCENARIO_PREFIX}{uuid4().hex}"
        scenario["id"] = scenario_id
        try:
            self.app.store.save_scenario(scenario, 0)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Could not import scenario", str(error), parent=self.frame)
            return
        if self.editing:
            self.end_edit(scenario_id)
        else:
            self.refresh_scenarios(scenario_id)
        self.hint.configure(text=f'Imported {scenario["name"]}.')

    def export_scenario(self):
        scenario = self.draft_scenario() if self.editing else dict(self.scenario, palette=self.palette_id)
        if scenario is None:
            return
        filename = filedialog.asksaveasfilename(
            title="Export scenario", parent=self.frame, defaultextension=".json",
            initialfile="scenario.json", filetypes=SCENARIO_FILE_TYPES,
        )
        if not filename:
            return
        try:
            write_scenario_file(Path(filename), scenario)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not export scenario", str(error), parent=self.frame)
            return
        self.hint.configure(text=f"Exported {Path(filename).name}.")

    def can_delete(self):
        return self.editing and self.revision > 0 and self.scenario["id"].startswith(LOCAL_SCENARIO_PREFIX)

    def delete_edit(self):
        if not self.can_delete():
            return
        if not messagebox.askyesno(
            "Delete local scenario?", f'Delete “{self.scenario["name"]}” permanently?',
            parent=self.frame, icon="warning", default="no",
        ):
            return
        try:
            self.app.store.delete_scenario(self.scenario["id"], self.revision)
        except (sqlite3.Error, ValueError) as error:
            messagebox.showerror("Could not delete scenario", str(error), parent=self.frame)
            return
        self.app.battlefield_palettes.pop(self.scenario["id"], None)
        self.end_edit(None)

    def move(self, event):
        step = -1 if event.keysym in ("Left", "Up") else 1
        row, column = map(int, self.selected.split("-"))
        if event.keysym in ("Up", "Down"):
            row += step
        else:
            column = max(1, min(len(HEX_COLUMN_LENGTHS), column + step))
        row = max(1, min(HEX_COLUMN_LENGTHS[column - 1], row))
        self.selected = f"{row:02}-{column:02}"
        self.draw()
        return "break"

    def hex_at(self, x, y):
        items = self.canvas.find_overlapping(x, y, x, y)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            if "hex" in tags:
                return tags[0]
        return None

    def brush_change(self, clear):
        if not clear:
            return self.brush
        layer = self.brush[0] if self.brush else "terrain"
        return layer, "ground" if layer == "terrain" else None

    def paint_cell(self, key, change):
        layer, value = change
        if layer == "token":
            return set_scenario_token(self.draft_cells, key, value)
        cell = self.draft_cells[key]
        if cell.get(layer) == value:
            return False
        if value is None:
            del cell[layer]
        else:
            cell[layer] = value
        return True

    def inspect(self, event, *, clear=False):
        if clear and not self.editing:
            return
        self.canvas.focus_set()
        self.finish_terrain_stroke()
        change = self.brush_change(clear)
        if self.editing and change is not None and change[0] != "token":
            self.terrain_stroke = TerrainStroke(clear, change, (event.x, event.y), deepcopy(self.draft_cells))
        key = self.hex_at(event.x, event.y)
        if key is not None:
            self.selected = key
            self.paint_selected(clear=clear, part_of_stroke=self.terrain_stroke is not None)

    def drag_terrain(self, event, *, clear):
        stroke = self.terrain_stroke
        if stroke is None or stroke.clear != clear:
            return
        start_x, start_y = stroke.point
        stroke.point = event.x, event.y
        dx, dy = event.x - start_x, event.y - start_y
        # Sample between events so a quick swipe paints the intervening hexes.
        steps = max(1, math.ceil(math.hypot(dx, dy) / 4))
        previous_selection = self.selected
        changed = False
        for step in range(1, steps + 1):
            fraction = step / steps
            key = self.hex_at(start_x + dx * fraction, start_y + dy * fraction)
            if key is None:
                continue
            self.selected = key
            if self.paint_cell(key, stroke.change):
                changed = True
        if changed or self.selected != previous_selection:
            self.draw()

    def end_terrain_stroke(self, event, *, clear):
        if self.terrain_stroke is not None and self.terrain_stroke.clear == clear:
            self.drag_terrain(event, clear=clear)
            self.finish_terrain_stroke()

    def finish_terrain_stroke(self):
        if self.terrain_stroke is not None:
            before = self.terrain_stroke.before
            self.terrain_stroke = None
            self.record_edit(before)

    def update_history_buttons(self):
        self.undo_button.state(["!disabled" if self.undo_cells else "disabled"])
        self.redo_button.state(["!disabled" if self.redo_cells else "disabled"])

    def record_edit(self, before):
        if before != self.draft_cells:
            self.undo_cells.append(before)
            self.redo_cells.clear()
            self.update_history_buttons()

    def apply_history(self, source, target):
        self.finish_terrain_stroke()
        if source:
            self.stop_token_placement()
            target.append(self.draft_cells)
            self.draft_cells = source.pop()
            self.update_history_buttons()
            self.draw()

    def paint_selected(self, *, clear=False, part_of_stroke=False):
        change = self.brush_change(clear)
        placed_token = None
        if self.editing and change is not None:
            if not part_of_stroke:
                self.finish_terrain_stroke()
                before = deepcopy(self.draft_cells)
            try:
                changed = self.paint_cell(self.selected, change)
            except ValueError as error:
                self.hint.configure(text=str(error))
            else:
                if not part_of_stroke:
                    self.record_edit(before)
                if changed and change[0] == "token":
                    self.choose_brush(self.brush)
                    self.stop_token_placement()
                    placed_token = change[1]
        self.draw()
        if placed_token is not None:
            self.placement_job = self.canvas.after_idle(self.animate_token_placement, self.selected, placed_token)
        return "break"

    def stop_token_placement(self, _event=None):
        if self.placement_job is not None:
            self.canvas.after_cancel(self.placement_job)
            self.placement_job = None
        self.placement_photos = ()

    def animate_token_placement(self, key, token, frame=0):
        self.placement_job = None
        canvas = self.canvas
        canvas.delete("token-puff")
        if not self.editing or self.cells[key].get("token") != token:
            self.placement_photos = ()
            return
        item = next((item for item in canvas.find_withtag(key) if "hex-token" in canvas.gettags(item)), None)
        if item is None:
            self.placement_photos = ()
            return
        if frame == len(PLACEMENT_SCALES) - 1:
            canvas.itemconfigure(item, image=self.map_photos[token])
            self.placement_photos = ()
            return

        size = self.map_token_size
        scaled = round(size * PLACEMENT_SCALES[frame])
        image = self.app.photos.get(map_token_art, TOKENS[token][1], scaled)
        puff = self.app.photos.get(token_puff_art, size, frame / (len(PLACEMENT_SCALES) - 1))
        self.placement_photos = (image, puff)
        canvas.itemconfigure(item, image=image)
        x, y = canvas.coords(item)
        dust = canvas.create_image(x, y + size * .10, image=puff, tags=("token-puff", "battlefield"))
        canvas.tag_lower(dust, item)
        self.placement_job = canvas.after(30, self.animate_token_placement, key, token, frame + 1)

    def draw_objective_number(self, key, number, x, y, icon_size):
        label = str(number)
        x += icon_size * .27
        y += icon_size * .18
        half_width = (self.objective_font.measure(label) + 4) / 2
        half_height = (self.objective_font.metrics("linespace") + 1) / 2
        tags = (key, "hex-objective-number", "battlefield")
        self.canvas.create_rectangle(x - half_width, y - half_height, x + half_width, y + half_height,
                                     fill=CELL, outline=BORDER, tags=tags)
        self.canvas.create_text(x, y, text=label, fill=AMBER, font=self.objective_font, tags=tags)

    def draw(self, event=None):
        if event is not None and event.type == tk.EventType.Configure:
            self.finish_terrain_stroke()
        canvas = self.canvas
        canvas.delete("battlefield")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        line_height = self.map_font.metrics("linespace")
        caption_height = max(26, self.side_name_font.metrics("linespace") + 4,
                             self.side_meta_font.metrics("linespace") + 4)
        detail_height = max(44, 2 * line_height + 4)
        top, bottom = caption_height + 2, height - caption_height - detail_height - 6
        map_height = bottom - top
        if width < 60 or map_height < 60:
            return
        for side, y, direction in ((1, caption_height / 2, "NORTH"),
                                   (0, bottom + caption_height / 2 + 4, "SOUTH")):
            name = f"Player {side + 1}"
            meta = f"/  {direction}"
            badge = self.side_badges[side]
            name_width = self.side_name_font.measure(name)
            meta_width = self.side_meta_font.measure(meta)
            x = (width - badge.width() - name_width - meta_width - 18) / 2
            canvas.create_image(x, y, image=badge, anchor="w", tags="battlefield")
            x += badge.width() + 6
            canvas.create_text(x, y, text=name, fill=SIDES[side], font=self.side_name_font,
                               anchor="w", tags="battlefield")
            canvas.create_text(x + name_width + 12, y, text=meta, fill=SIDES[side], font=self.side_meta_font,
                               anchor="w", tags="battlefield")
        corner = min(30, width * .05, map_height * .05)
        edge = FOCUS if canvas.focus_get() is canvas else "#657370"
        left, right = 3, width - 4
        canvas.create_polygon(
            left+corner, top, right-corner, top, right, top, right, top+corner,
            right, bottom-corner, right, bottom, right-corner, bottom,
            left+corner, bottom, left, bottom, left, bottom-corner, left, top+corner, left, top,
            smooth=True, splinesteps=24, fill="", outline=edge, width=1.5, tags="battlefield",
        )
        width_in_radii = 2 + 1.5 * (len(HEX_COLUMN_LENGTHS) - 1)
        height_in_radii = max(HEX_COLUMN_LENGTHS) * math.sqrt(3)
        radius = max(1, .92 * min((width - 40) / width_in_radii, (map_height - 40) / height_in_radii))
        # The reference uses a 4px stroke on a hex with a 40px radius.
        divider_width = max(2, round(radius / 10))
        step = math.sqrt(3) * radius
        ox = (width - width_in_radii * radius) / 2 + radius
        oy = (top + bottom - height_in_radii * radius) / 2 + step / 2
        vertices = ((radius, 0), (radius / 2, step / 2), (-radius / 2, step / 2),
                    (-radius, 0), (-radius / 2, -step / 2), (radius / 2, -step / 2))
        icon_size = max(12, round(radius * 1.12 / 2) * 2)
        self.map_token_size = icon_size
        objective_size = -max(8, round(icon_size * .46))
        if self.objective_font.cget("size") != objective_size:
            self.objective_font.configure(size=objective_size)
        self.map_photos = {key: self.app.photos.get(map_token_art, artwork, icon_size)
                           for key, (_, artwork) in TOKENS.items()}
        decals = {cell["special_terrain"] for cell in self.cells.values() if cell.get("special_terrain")}
        decal_size = max(1, round(radius * 2))
        self.decal_photos = {key: self.app.photos.get(published_token_art, SPECIAL_TERRAIN[key][1], decal_size)
                             for key in decals}
        colors = PALETTES[self.palette_id]
        for key, cell in self.cells.items():
            row, col = (int(part) for part in key.split("-"))
            x = ox + (col - 1) * 1.5 * radius
            y = oy + (row - 1 + (.5 if col % 2 == 0 else 0)) * step
            points = [value for dx, dy in vertices for value in (x + dx, y + dy)]
            canvas.create_polygon(points, fill=colors[cell["terrain"]], tags=(key, "hex", "battlefield"))
            draw_ground_stars(canvas, self.palette_id, cell["terrain"], key, x, y, radius)
            decal = self.decal_photos.get(cell.get("special_terrain"))
            if decal is not None:
                canvas.create_image(x, y, image=decal, tags=(key, "hex-decal", "battlefield"))
            selected = key == self.selected
            canvas.create_polygon(
                points, fill="", outline=HEX_SELECTION if selected else HEX_DIVIDER, joinstyle="round",
                width=divider_width + 1 if selected else divider_width,
                tags=("battlefield", "hex-selection" if selected else "hex-divider"),
            )
            if cell.get("token"):
                canvas.create_image(x, y, image=self.map_photos[cell["token"]],
                                    tags=(key, "hex-token", "battlefield"))
                if cell["token"] in NUMBERED_TOKENS:
                    self.draw_objective_number(key, cell["objective_number"], x, y, icon_size)
        # Decals cover elevation fills. Grid lines, selection and gameplay tokens sit above them.
        for layer in ("hex-decal", "hex-divider", "hex-selection", "hex-token", "hex-objective-number"):
            canvas.tag_raise(layer)
        cell = self.cells[self.selected]
        self.show_terrain_rules(cell.get("special_terrain"))
        token = TOKENS[cell["token"]][0] if cell.get("token") else "No token"
        if cell.get("token") in NUMBERED_TOKENS:
            token += f" {cell['objective_number']}"
        self.detail_photo = (self.app.photos.get(scenario_token_art, TOKENS[cell["token"]][1], 42)
                             if cell.get("token") else None)
        details = [f"Hex {self.selected}", TERRAIN[cell["terrain"]]]
        if cell.get("special_terrain"):
            details.append(SPECIAL_TERRAIN[cell["special_terrain"]][0])
        details.append(token)
        readout = "  ·  ".join(details)
        icon_width = self.detail_photo.width() + 6 if self.detail_photo else 0
        text_width = min(self.map_font.measure(readout), width - icon_width - 16)
        start = (width - text_width - icon_width) / 2
        readout_y = height - detail_height / 2
        if self.detail_photo:
            canvas.create_image(start, readout_y, image=self.detail_photo, anchor="w", tags="battlefield")
        canvas.create_text(start + icon_width, readout_y, text=readout, fill=INK, font=self.map_font,
                           width=text_width + 2, anchor="w", tags="battlefield")
