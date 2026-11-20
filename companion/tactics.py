import tkinter as tk
from collections import deque
from math import cos, pi, radians, sin
from time import monotonic
from tkinter import ttk
from unicodedata import combining, normalize

from PIL import Image, ImageTk

from .tactics_art import tactics_fan_card, tactics_preview_card
from .theme import AMBER, AMBER_WELL, BORDER, INK, MUTED, PANEL, families


def search_key(value):
    text = normalize("NFKD", value.strip().casefold().replace("’", "'"))
    return "".join(char for char in text if not combining(char))


def inside_card(x, y, pose):
    center_x, center_y, (width, height), angle = pose
    dx, dy = x - center_x, y - center_y
    turn = radians(angle)
    sine, cosine = sin(turn), cos(turn)
    return abs(dx * cosine - dy * sine) <= width / 2 and abs(dx * sine + dy * cosine) <= height / 2


def between_poses(start, target, fraction):
    x, y, (width, height), angle = start
    tx, ty, (tw, th), ta = target
    return (x + (tx - x) * fraction, y + (ty - y) * fraction,
            (max(1, round(width + (tw - width) * fraction)), max(1, round(height + (th - height) * fraction))),
            round(angle + (ta - angle) * fraction, 1))


class TacticsScreen:
    FAN_COUNT = 8
    SWIPE_SLOP = 12
    SWIPE_STEP = 54
    DRAW_SECONDS = .38
    HUD_SECONDS = .30
    HOVER_SECONDS = .18
    HOVER_SCALE = 1.24

    def __init__(self, parent, app):
        self.canvas = app.workspace.layer(parent)
        self.photos = app.photos
        self.cards = app.tactics
        numbers = tuple(self.cards)
        self.rails = numbers[::2], numbers[1::2]
        self.offsets = [0, 0]
        self.fan_count = self.FAN_COUNT
        self.fan_press = None
        self.fan_dragged = False
        self.slots = {}
        self.fan_items = {}
        self.fan_poses = {}
        self.fan_photos = {}
        self.hover_photos = {}
        self.hovered = None
        self.hover_job = None
        self.pending = deque()
        self.fan_job = None
        self.animation_job = None
        self.selected = None
        self.next_card = None
        self.origin = None
        self.returning = False
        self.preview_fraction = 0
        self.matches = []
        self.preview = None
        self.preview_photo = None
        self.preview_pose = None
        self.hud_job = None
        self.hud_fraction = 0
        self.hud_target = 0
        self.search_font_size = 20
        self.width = self.height = 1
        self.heading_font, self.body_font = families(self.canvas)
        style = ttk.Style(self.canvas)
        style.configure('Tactics.Quiet.TButton', font=(self.heading_font, -18, 'bold'), padding=(8, 3), width=0)
        style.configure('TacticsResult.Quiet.TButton', font=(self.heading_font, -16, 'bold'), padding=(10, 2), anchor='w', width=0)
        style.configure('Tactics.Sortie.TEntry', padding=(10, 9))
        self.rail_controls = []
        self.rail_buttons = []
        for side in range(2):
            controls = ttk.Frame(self.canvas, style='Rail.TFrame', padding=3)
            buttons = []
            for delta, label in ((-1, '↑'), (1, '↓')):
                box = ttk.Frame(controls, style='RailFill.TFrame', width=54, height=48)
                box.pack(side='left', padx=3)
                box.pack_propagate(False)
                button = ttk.Button(box, text=label, style='Tactics.Quiet.TButton',
                                    command=lambda side=side, delta=delta: self.move_fan(side, delta))
                button.pack(fill='both', expand=True)
                buttons.append(button)
            self.rail_buttons.append(buttons)
            self.rail_controls.append(self.canvas.create_window(0, 0, window=controls, anchor='sw' if side == 0 else 'se'))

        self.title = self.canvas.create_text(0, 0, text="TACTICS", fill=INK, tags="hud-copy")
        self.hint = self.canvas.create_text(0, 0, text="SEARCH BY CARD NAME OR NUMBER", fill=MUTED,
                                            font=(self.body_font, -12, "bold"), tags="hud-copy")
        self.message = self.canvas.create_text(0, 0, fill=MUTED, justify="center", font=(self.body_font, -15))
        self.query = tk.StringVar(master=self.canvas)
        search = ttk.Frame(self.canvas, style="Rail.TFrame", padding=3)
        self.entry = ttk.Entry(search, textvariable=self.query, style="Tactics.Sortie.TEntry", font=(self.body_font, -20))
        self.entry.pack(side="left", fill="both", expand=True)
        from .dialogs import touch_keyboard
        touch_keyboard(self.entry, "Search Tactics Cards", live=True)
        clear_box = ttk.Frame(search, style='RailFill.TFrame', width=88, height=48)
        clear_box.pack(side='right', padx=(4, 0))
        clear_box.pack_propagate(False)
        self.clear_button = ttk.Button(clear_box, text='Clear', style='Tactics.Quiet.TButton', command=self.clear)
        self.clear_button.pack(fill='both', expand=True)
        self.search_window = self.canvas.create_window(0, 0, window=search, anchor="n")

        self.results = ttk.Frame(self.canvas, style='Rail.TFrame', padding=3)
        self.result_buttons = []
        self.result_window = self.canvas.create_window(0, 0, window=self.results, anchor='n', state='hidden')
        self.search_trace = self.query.trace_add('write', self.search)
        self.entry.bind('<Return>', self.choose_match)
        self.entry.bind('<Down>', self.focus_results)
        self.results.bind('<Configure>', self.wrap_results)
        self.canvas.bind("<Configure>", self.layout, add="+")
        self.canvas.bind("<MouseWheel>", self.scroll_fan)
        self.canvas.bind("<Motion>", self.hover_fan)
        self.canvas.bind("<Leave>", lambda _event: self.set_hover(None))
        self.canvas.bind('<ButtonPress-1>', self.press_fan)
        self.canvas.bind('<B1-Motion>', self.drag_fan)
        self.canvas.bind('<ButtonRelease-1>', self.release_fan)
        self.canvas.bind('<FocusOut>', self.cancel_gesture)
        self.canvas.bind('<Unmap>', self.cancel_gesture)
        self.canvas.bind("<Destroy>", self.cancel, add="+")

    def show(self):
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.entry.focus_set()

    def layout(self, event):
        if (event.width, event.height) == (self.width, self.height):
            return
        self.cancel_gesture()
        self.width, self.height = event.width, event.height
        card_height = min(260, max(70, round(self.height * .27)))
        self.fan_count = min(self.FAN_COUNT, max(3, int((self.height - 116 - card_height) / 48) + 1))
        for side, rail in enumerate(self.rails):
            self.offsets[side] = min(self.offsets[side], max(0, len(rail) - self.fan_count))
            self.canvas.coords(self.rail_controls[side], 12 if side == 0 else self.width - 12, self.height - 10)
        if self.returning and self.selected is not None:
            side = self.origin[0]
            index = self.rails[side].index(self.selected)
            if not self.offsets[side] <= index < self.offsets[side] + self.fan_count:
                self.offsets[side] = min(index, max(0, len(self.rails[side]) - self.fan_count))
            self.origin = side, self.offsets[side]
        font_size = min(68, max(32, round(self.height * .083)))
        title_y = max(37, round(self.height * .14))
        search_y = title_y + font_size // 2 + 33
        search_width = min(570, max(200, round(self.width * .44)))
        compact_font = max(24, round(font_size * .53))
        compact_title_y = max(25, compact_font // 2 + 9)
        compact_search_y = compact_title_y + compact_font // 2 + 20
        self.hud_expanded = title_y, font_size, search_y, search_width, 20
        self.hud_compact = compact_title_y, compact_font, compact_search_y, max(300, round(search_width * .82)), 18
        self.preview_top = compact_search_y + 72
        self.paint_hud()
        self.paint_fans()
        if self.selected is not None:
            self.stop_animation()
            self.prepare_preview()
        if self.returning:
            if self.preview is None:
                self.finish_return()
            else:
                self.animate(monotonic(), self.slots[self.selected], self.preview_fraction, 0, self.preview_pose)
        elif self.preview is not None:
            self.set_hud_compact(True)
            self.preview_fraction = 1
            self.preview_pose = (*self.preview_center, self.preview.size, 0)
            self.draw_preview(self.preview, *self.preview_center)
        self.update_message()

    def paint_hud(self):
        title_y, font_size, search_y, search_width, search_font = (
            round(expanded + (compact - expanded) * self.hud_fraction)
            for expanded, compact in zip(self.hud_expanded, self.hud_compact)
        )
        center = self.width / 2
        self.canvas.itemconfigure(self.title, font=(self.heading_font, -font_size, "bold"))
        self.canvas.coords(self.title, center, title_y)
        self.canvas.coords(self.hint, center, search_y - 10)
        if search_font != self.search_font_size:
            self.search_font_size = search_font
            self.entry.configure(font=(self.body_font, -search_font))
        self.canvas.coords(self.search_window, center, search_y)
        self.canvas.itemconfigure(self.search_window, width=search_width)
        self.canvas.coords(self.result_window, center, search_y + 62)
        self.canvas.itemconfigure(self.result_window, width=search_width)
        self.canvas.coords(self.message, center, (search_y + 72 + self.height - 22) / 2)
        self.canvas.itemconfigure(self.message, width=search_width)

    def set_hud_compact(self, compact):
        target = int(compact)
        if self.hud_target != target:
            self.stop_hud_animation()
            self.hud_target = target
            self.animate_hud(monotonic(), self.hud_fraction)

    def animate_hud(self, started, initial):
        self.hud_job = None
        duration = self.HUD_SECONDS if self.hud_target else self.DRAW_SECONDS
        progress = min(1, (monotonic() - started) / duration)
        ease = 1 - (1 - progress) ** 3 if self.hud_target else progress ** 3
        self.hud_fraction = initial + (self.hud_target - initial) * ease
        self.paint_hud()
        if progress < 1:
            self.hud_job = self.canvas.after(16, self.animate_hud, started, initial)

    def stop_hud_animation(self):
        if self.hud_job is not None:
            self.canvas.after_cancel(self.hud_job)
            self.hud_job = None

    def paint_fans(self):
        self.stop_hover_animation()
        self.hovered = None
        if self.fan_job is not None:
            self.canvas.after_cancel(self.fan_job)
            self.fan_job = None
        self.canvas.delete("fan")
        self.fan_items.clear()
        self.fan_poses.clear()
        self.fan_photos.clear()
        self.hover_photos.clear()
        self.pending.clear()
        self.slots.clear()
        card_height = min(260, max(70, round(self.height * .27)))
        card_width = round(card_height * .715)
        size = card_width, card_height
        top = 28 + card_height * .47
        bottom = max(top, self.height - 100 - card_height * .53)
        for side, numbers in enumerate(self.rails):
            start = self.offsets[side]
            visible = numbers[start:start + self.fan_count]
            for index, number in enumerate(visible):
                fraction = index / max(1, len(visible) - 1)
                inset = card_width * .29 + 9 * sin(fraction * pi)
                x = inset if side == 0 else self.width - inset
                y = top + (bottom - top) * fraction
                angle = (13 - round(4 * sin(fraction * pi))) * (1 if side == 0 else -1)
                self.slots[number] = (x, y, size, angle)
                if number == self.selected:
                    continue
                tags = ("fan", number)
                photo = self.photos.get(tactics_fan_card, self.cards[number].image, size, angle, load=False)
                if photo is not None:
                    self.fan_photos[number] = photo
                placeholder = None
                if photo is None:
                    placeholder = self.canvas.create_rectangle(
                        x - card_width / 2, y - card_height / 2, x + card_width / 2, y + card_height / 2,
                        fill=PANEL, outline=BORDER, tags=tags,
                    )
                item = self.canvas.create_image(x, y, image=photo or "", tags=tags)
                self.fan_items[number] = item
                self.fan_poses[number] = self.slots[number]
                if placeholder is not None:
                    self.pending.append((number, item, placeholder, size, angle))
            if visible:
                self.canvas.create_text(12 if side == 0 else self.width - 12, self.height - 72,
                                        text=f"{start + 1}–{start + len(visible)} / {len(numbers)}  ·  SWIPE",
                                        anchor="sw" if side == 0 else "se", fill=MUTED,
                                        font=(self.body_font, -11), tags=("fan", "fan-count"))
        self.update_rail_buttons()
        if self.pending:
            self.fan_job = self.canvas.after(12, self.load_fan_card)
        self.canvas.tag_raise("preview")

    def load_fan_card(self):
        self.fan_job = None
        deadline = monotonic() + .012
        while self.pending:
            number, item, placeholder, size, angle = self.pending.popleft()
            photo = self.photos.get(tactics_fan_card, self.cards[number].image, size, angle)
            if photo is not None:
                self.fan_photos[number] = photo
                self.canvas.itemconfigure(item, image=photo)
                self.canvas.delete(placeholder)
            if monotonic() >= deadline:
                break
        if self.pending:
            self.fan_job = self.canvas.after(1, self.load_fan_card)

    def card_at(self, x, y):
        focused = self.hovered
        inside_focus = focused is not None and inside_card(x, y, self.fan_poses[focused])
        # Keep the rail's original hit areas stable as the cards move under the pointer.
        if inside_focus and min(x, self.width - x) > self.slots[focused][2][0] * .65:
            return focused
        for number in reversed(self.fan_items):
            if inside_card(x, y, self.slots[number]):
                return number
        return focused if inside_focus else None

    def hover_fan(self, event):
        if self.animation_job is None and self.fan_press is None:
            number = self.card_at(event.x, event.y)
            self.set_hover(number if number in self.fan_photos else None)

    def set_hover(self, number):
        if number == self.hovered:
            return
        self.stop_hover_animation()
        self.hovered = number
        start = self.fan_poses.copy()
        targets = {card: self.slots[card] for card in start}
        if number is not None:
            x, y, (width, height), angle = self.slots[number]
            side = int(x > self.width / 2)
            inward = 1 if side == 0 else -1
            zoomed = round(width * self.HOVER_SCALE), round(height * self.HOVER_SCALE)
            edge_inset = max(zoomed[0] / 2 + 18, min(x, self.width - x) + height * .35)
            center_x = edge_inset if side == 0 else self.width - edge_inset
            center_y = min(max(y, zoomed[1] / 2 + 12), self.height - zoomed[1] / 2 - 100)
            targets[number] = center_x, center_y, zoomed, angle / 3
            for card in self.rails[side]:
                if card == number or card not in targets:
                    continue
                card_x, card_y, size, tilt = targets[card]
                distance = max(1, abs(card_y - y))
                spread = min(48, height * .18) * (1 - min(1, distance / max(1, height * .95)))
                direction = 1 if card_y > y else -1
                targets[card] = card_x + inward * spread * .36, card_y + direction * spread, size, tilt
            self.raise_fan()
        self.animate_hover(start, targets, monotonic())

    def raise_fan(self):
        for number in self.fan_items:
            self.canvas.tag_raise(number)
        if self.hovered is not None:
            self.canvas.tag_raise(self.hovered)
        self.canvas.tag_raise("fan-count")
        self.canvas.tag_raise("preview")

    def animate_hover(self, start, targets, started):
        self.hover_job = None
        progress = min(1, (monotonic() - started) / self.HOVER_SECONDS)
        ease = 1 - (1 - progress) ** 3
        for number, target in targets.items():
            x, y, size, angle = target if progress == 1 else between_poses(start[number], target, ease)
            old_x, old_y, old_size, old_angle = self.fan_poses[number]
            if (x, y) != (old_x, old_y):
                self.canvas.move(number, x - old_x, y - old_y)
            if (size, angle) != (old_size, old_angle) and number in self.fan_photos:
                if (size, angle) == self.slots[number][2:]:
                    photo = self.fan_photos[number]
                    self.hover_photos.pop(number, None)
                else:
                    art = tactics_fan_card(self.cards[number].image, size, angle)
                    photo = ImageTk.PhotoImage(art, master=self.canvas) if art is not None else self.fan_photos[number]
                    self.hover_photos[number] = photo
                self.canvas.itemconfigure(self.fan_items[number], image=photo)
            self.fan_poses[number] = x, y, size, angle
        if progress < 1:
            self.hover_job = self.canvas.after(16, self.animate_hover, start, targets, started)
        elif self.hovered is None:
            self.raise_fan()

    def stop_hover_animation(self):
        if self.hover_job is not None:
            self.canvas.after_cancel(self.hover_job)
            self.hover_job = None

    def edge_side(self, x):
        edge = min(220, self.width * .22)
        return None if edge < x < self.width - edge else int(x >= self.width / 2)

    def update_rail_buttons(self):
        for side, buttons in enumerate(self.rail_buttons):
            locked = self.returning and self.origin is not None and side == self.origin[0]
            limit = max(0, len(self.rails[side]) - self.fan_count)
            for button, enabled in zip(buttons, (self.offsets[side] > 0, self.offsets[side] < limit)):
                button.state(['!disabled'] if enabled and not locked else ['disabled'])

    def move_fan(self, side, change):
        if self.returning and self.origin is not None and side == self.origin[0]:
            return
        limit = max(0, len(self.rails[side]) - self.fan_count)
        offset = min(limit, max(0, self.offsets[side] + change))
        if offset != self.offsets[side]:
            self.offsets[side] = offset
            self.paint_fans()

    def scroll_fan(self, event):
        side = self.edge_side(event.x)
        if side is not None and event.delta:
            self.move_fan(side, -1 if event.delta > 0 else 1)
            return 'break'

    def press_fan(self, event):
        side = self.edge_side(event.x)
        number = self.card_at(event.x, event.y)
        if side is None and number is None:
            self.cancel_gesture()
            return
        if side is None:
            side = next(index for index, rail in enumerate(self.rails) if number in rail)
        self.fan_press = (side, event.x, event.y, self.offsets[side], number)
        self.fan_dragged = False
        return 'break'

    def drag_fan(self, event):
        if self.fan_press is None:
            return
        side, x, y, offset, number = self.fan_press
        if max(abs(event.x - x), abs(event.y - y)) >= self.SWIPE_SLOP:
            self.fan_dragged = True
        if self.fan_dragged:
            self.set_hover(None)
            change = int((y - event.y) / self.SWIPE_STEP)
            self.move_fan(side, offset + change - self.offsets[side])
        return 'break'

    def release_fan(self, event):
        if self.fan_press is None:
            return
        self.drag_fan(event)
        number = self.fan_press[4]
        tapped = not self.fan_dragged
        self.cancel_gesture()
        if tapped and number is not None:
            self.pick(number)
        return 'break'

    def cancel_gesture(self, _event=None):
        self.fan_press = None
        self.fan_dragged = False

    def wrap_results(self, event):
        ttk.Style(self.canvas).configure('TacticsResult.Quiet.TButton', wraplength=max(100, event.width - 30))

    def search(self, *_args):
        query = search_key(self.query.get())
        self.matches = []
        for child in self.results.winfo_children():
            child.destroy()
        self.result_buttons.clear()
        self.canvas.itemconfigure(self.result_window, state="hidden")
        if not query:
            self.set_selected(None)
            return
        partial = []
        exact = []
        for number, card in self.cards.items():
            name, code = search_key(card.name), search_key(number)
            if query == code:
                self.set_selected(number)
                return
            if query == name:
                exact.append(number)
            elif query in name or query in code:
                partial.append((not (name.startswith(query) or code.startswith(query)), name, number))
        if len(exact) == 1:
            self.set_selected(exact[0])
            return
        self.matches = (exact + [number for _, _, number in sorted(partial)])[:6]
        for index, number in enumerate(self.matches):
            box = ttk.Frame(self.results, style='RailFill.TFrame', height=48, width=1)
            box.pack(fill='x', pady=2)
            box.pack_propagate(False)
            button = ttk.Button(box, text=f'{self.cards[number].name}  ·  {number}',
                style='TacticsResult.Quiet.TButton', command=lambda number=number: self.pick(number))
            button.pack(fill='both', expand=True)
            button.bind('<Down>', lambda _event, index=index: self.focus_result(index + 1))
            button.bind('<Up>', lambda _event, index=index: self.focus_result(index - 1))
            button.bind('<Return>', lambda _event, number=number: self.pick(number))
            self.result_buttons.append(button)
        if self.matches:
            self.canvas.itemconfigure(self.result_window, state="normal")
        self.update_message()

    def focus_results(self, _event):
        if self.matches:
            self.result_buttons[0].focus_set()
            return "break"

    def focus_result(self, index):
        if self.result_buttons:
            self.result_buttons[index % len(self.result_buttons)].focus_set()
        return 'break'

    def choose_match(self, _event):
        if self.matches:
            self.pick(self.matches[0])
        return "break"

    def pick(self, number):
        name = self.cards[number].name
        duplicate = any(card.number != number and search_key(card.name) == search_key(name)
                        for card in self.cards.values())
        self.query.set(number if duplicate else name)
        self.entry.icursor("end")
        self.entry.focus_set()

    def pick_fan(self, event):
        number = self.card_at(event.x, event.y)
        if number is not None:
            self.pick(number)

    def clear(self):
        self.query.set("")
        self.entry.focus_set()

    def escape(self):
        if self.query.get() or self.selected:
            self.clear()
            return "break"

    def set_selected(self, number):
        self.next_card = number if number != self.selected else None
        if number is None:
            self.set_hud_compact(False)
        elif self.preview is not None:
            self.set_hud_compact(True)
        if self.selected is None:
            if self.animation_job is None:
                self.draw_next_card()
        elif number != self.selected:
            self.return_to_fan()
        elif self.returning:
            self.stop_animation()
            self.returning = False
            self.update_rail_buttons()
            self.animate(monotonic(), self.slots[number], self.preview_fraction, 1, self.preview_pose)
        self.update_message()

    def draw_next_card(self):
        self.animation_job = None
        number = self.next_card
        self.next_card = None
        if number is None:
            self.update_message()
            return
        draw_from = self.fan_poses.get(number)
        self.selected = number
        for side, rail in enumerate(self.rails):
            if number in rail:
                if number not in self.slots:
                    index = rail.index(number)
                    self.offsets[side] = min(max(0, index - self.fan_count // 2),
                                             max(0, len(rail) - self.fan_count))
                self.origin = side, self.offsets[side]
                break
        self.paint_fans()
        self.prepare_preview()
        self.set_hud_compact(self.preview is not None)
        if self.preview is not None:
            self.animate(monotonic(), draw_from or self.slots[number], 0, 1)
        self.update_message()

    def return_to_fan(self):
        if self.selected is None or self.returning:
            return
        self.stop_animation()
        side, offset = self.origin
        index = self.rails[side].index(self.selected)
        offset = min(max(0, offset), max(0, len(self.rails[side]) - self.fan_count))
        if not offset <= index < offset + self.fan_count:
            offset = min(index, max(0, len(self.rails[side]) - self.fan_count))
        self.origin = side, offset
        moved = self.offsets[side] != offset
        self.offsets[side] = offset
        if self.preview is None or self.preview_fraction == 0:
            self.finish_return()
            return
        self.returning = True
        self.update_rail_buttons()
        if moved:
            self.paint_fans()
        else:
            self.set_hover(None)
        slot = self.slots[self.selected]
        _, _, size, angle = slot
        self.photos.get(tactics_fan_card, self.cards[self.selected].image, size, angle)
        self.animate(monotonic(), slot, self.preview_fraction, 0, self.preview_pose)

    def finish_return(self):
        self.selected = None
        self.origin = None
        self.returning = False
        self.preview_fraction = 0
        self.preview = self.preview_photo = None
        self.preview_pose = None
        self.canvas.delete("preview")
        self.paint_fans()
        if self.next_card is not None:
            # Let the restored fan paint before drawing the next card.
            self.animation_job = self.canvas.after(16, self.draw_next_card)
        else:
            self.set_hud_compact(False)
        self.update_message()

    def prepare_preview(self):
        self.preview = None
        if self.selected is None or self.height < 100:
            return
        height = max(1, self.height - self.preview_top - 20)
        self.preview = tactics_preview_card(self.cards[self.selected].image, (round(self.width * .63), height))
        self.preview_center = (self.width / 2, self.preview_top + height / 2)

    def draw_preview(self, art, x, y):
        self.preview_photo = ImageTk.PhotoImage(art, master=self.canvas)
        self.canvas.delete("preview")
        self.canvas.create_image(x, y, image=self.preview_photo, tags="preview")
        self.canvas.tag_raise("hud-copy")

    def animate(self, started, slot, initial, target, start_pose=None):
        self.animation_job = None
        progress = min(1, (monotonic() - started) / self.DRAW_SECONDS)
        center = (*self.preview_center, self.preview.size, 0)
        if progress == 1:
            self.preview_fraction = target
            if target == 0:
                self.finish_return()
            else:
                self.preview_pose = center
                self.draw_preview(self.preview, *self.preview_center)
            return
        ease = progress ** 3 if target == 0 else 1 - (1 - progress) ** 3
        fraction = initial + (target - initial) * ease
        self.preview_fraction = fraction
        if start_pose is None:
            self.preview_pose = between_poses(slot, center, fraction)
        else:
            self.preview_pose = between_poses(start_pose, center if target else slot, ease)
        x, y, size, angle = self.preview_pose
        frame = self.preview.resize(size, Image.Resampling.BILINEAR)
        frame = frame.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        self.draw_preview(frame, x, y)
        self.animation_job = self.canvas.after(16, self.animate, started, slot, initial, target, start_pose)

    def update_message(self):
        if self.selected is not None:
            text = "" if self.preview is not None else "Tactics Card image unavailable."
        elif self.next_card is not None:
            text = ""
        elif not self.cards:
            text = "No Tactics Cards found."
        elif self.query.get().strip() and not self.matches:
            text = "No Tactics Cards match that search."
        else:
            text = "Swipe either edge to browse, or tap a card. Search by name or number."
        self.canvas.itemconfigure(self.message, text=text)

    def stop_animation(self):
        if self.animation_job is not None:
            self.canvas.after_cancel(self.animation_job)
            self.animation_job = None

    def cancel(self, _event):
        if _event.widget is not self.canvas:
            return
        self.cancel_gesture()
        self.query.trace_remove("write", self.search_trace)
        self.stop_animation()
        self.stop_hover_animation()
        self.stop_hud_animation()
        if self.fan_job is not None:
            self.canvas.after_cancel(self.fan_job)
            self.fan_job = None
