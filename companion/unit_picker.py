"""Compact, keyboard-accessible lineups using the Timeline's portrait artwork."""
import tkinter as tk
from tkinter import font, ttk

from .artwork import timeline_portrait
from .theme import AMBER, CELL, HANGARS, INK, MUTED, SIDES, SIDE_EDGES, app_cursor, families


class UnitPicker(ttk.Frame):
    TILE = 160
    HEIGHT = 80

    def __init__(self, parent, app, options=()):
        super().__init__(parent, style="PanelFill.TFrame")
        self.app = app
        self.options = []
        self.index = -1
        self.hover = -1
        self.photos = []
        self.display, self.mono = families(self)
        self.name_font = font.Font(self, family=self.display, size=9, weight="bold")
        self.canvas = tk.Canvas(self, height=self.HEIGHT, background=CELL,
                                highlightthickness=0, takefocus=True, cursor=app_cursor(self, "hand2"))
        self.canvas.pack(fill="x", expand=True)
        self.scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scrolled)
        self.detail = ttk.Label(self, style="PanelMuted.TLabel", wraplength=760)
        self.detail.pack(fill="x", pady=(5, 0))
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<Motion>", self.motion)
        self.canvas.bind("<Leave>", lambda _e: self.set_hover(-1))
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<Left>", lambda _e: self.step(-1))
        self.canvas.bind("<Right>", lambda _e: self.step(1))
        self.canvas.bind("<Home>", lambda _e: self.choose(0))
        self.canvas.bind("<End>", lambda _e: self.choose(len(self.options)-1))
        self.canvas.bind("<FocusIn>", lambda _e: self.draw())
        self.canvas.bind("<FocusOut>", lambda _e: self.draw())
        self.set_options(options)

    def focus_set(self):
        self.canvas.focus_set()

    def scrolled(self, first, last):
        self.scroll.set(first, last)
        if float(first) > 0 or float(last) < 1:
            if not self.scroll.winfo_manager():
                self.scroll.pack(fill="x", before=self.detail)
        else:
            self.scroll.pack_forget()

    def set_options(self, options):
        self.options = list(options)
        self.index = self.hover = -1
        self.canvas.configure(width=min(800, max(480, len(self.options)*self.TILE)),
                              scrollregion=(0, 0, len(self.options)*self.TILE, self.HEIGHT))
        self.canvas.xview_moveto(0)
        self.current(-1)

    def current(self, index=None):
        if index is None:
            return self.index
        self.index = index if 0 <= index < len(self.options) else -1
        if self.index >= 0:
            unit, system = self.options[self.index]
            name = f"RWS · {system.name} · {unit.label}" if system else unit.label
            hp = unit.remote_weapon_hp[system.number] if system else unit.hp
            self.detail.configure(text=f"{name} [{system.number if system else unit.card.number}] · HP {hp}"
                                  + (f" · Shields {unit.shield_active}" if not system else ""))
            left = self.canvas.canvasx(0)
            right = left + self.canvas.winfo_width()
            start = self.index*self.TILE
            total = max(1, len(self.options)*self.TILE)
            if start < left:
                self.canvas.xview_moveto(start/total)
            elif start+self.TILE > right:
                self.canvas.xview_moveto((start+self.TILE-self.canvas.winfo_width())/total)
        else:
            self.detail.configure(text="Click a unit to select it." if self.options else "No eligible deployed units.")
        self.draw()

    def choose(self, index):
        if 0 <= index < len(self.options):
            self.current(index)
            self.event_generate("<<UnitSelected>>")
        return "break"

    def step(self, amount):
        return self.choose(max(0, min(len(self.options)-1, self.index+amount)))

    def hit(self, event):
        index = int(self.canvas.canvasx(event.x)//self.TILE)
        return index if 0 <= index < len(self.options) else -1

    def click(self, event):
        self.canvas.focus_set()
        return self.choose(self.hit(event))

    def motion(self, event):
        self.set_hover(self.hit(event))

    def set_hover(self, index):
        if index != self.hover:
            self.hover = index
            self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.photos.clear()
        display, mono = self.display, self.mono
        for index, (unit, system) in enumerate(self.options):
            x = index*self.TILE+3
            selected = index == self.index
            edge = AMBER if selected else SIDES[unit.player] if index == self.hover else SIDE_EDGES[unit.player]
            self.canvas.create_rectangle(x+1, 5, x+self.TILE-6, 77, fill=CELL, outline="")
            self.canvas.create_rectangle(x, 2, x+self.TILE-7, 74, fill=HANGARS[unit.player],
                                         outline=edge, width=2 if selected else 1)
            photo = self.app.photos.get(timeline_portrait, system.image if system else unit.card.image, (58, 68), 0)
            if photo is not None:
                self.photos.append(photo)
                self.canvas.create_image(x+2, 4, image=photo, anchor="nw")
            self.canvas.create_rectangle(x+2, 57, x+34, 72, fill=CELL, outline="")
            self.canvas.create_text(x+18, 64, text=f"{unit.slot:02d}", font=(mono, 8), fill=SIDES[unit.player])
            label = system.name if system else unit.card.name
            lines = []
            while label and len(lines) < 2:
                end = len(label)
                while end > 1 and self.name_font.measure(label[:end]) > 82:
                    end -= 1
                if end < len(label) and " " in label[:end]:
                    end = label.rfind(" ", 0, end)+1
                line, label = label[:end].strip(), label[end:].strip()
                if len(lines) == 1 and label:
                    while line and self.name_font.measure(line+"…") > 82:
                        line = line[:-1]
                    line += "…"
                lines.append(line)
            self.canvas.create_text(x+66, 7, anchor="nw", text="\n".join(lines),
                                    font=self.name_font, fill=INK)
            self.canvas.create_text(x+66, 63, anchor="w", text="RWS" if system else f"P{unit.player+1}",
                                    font=(mono, 8), fill=AMBER if selected else MUTED)
            if selected:
                self.canvas.create_text(x+self.TILE-16, 63, text="●", fill=AMBER, font=(mono, 9))
