import ctypes
import logging
import sys
import tkinter as tk
from ctypes import wintypes
from math import ceil
from time import monotonic

from PIL import Image, ImageTk

from companion.artwork import hangar_art
from companion.catalog import ASSETS
from .garrison_effect import GARRISON_EFFECT_SECONDS, draw_garrison, particles
from .energize_effect import ENERGIZE_SECONDS, draw_energize
from .dash_effect import DASH_SECONDS, draw_dash
from .goal_effect import GOAL_SECONDS, draw_goal


DEPLOYMENT_ART_BY_SIDE = (
    ASSETS / "Video" / "Deploy_P1.webp",
    ASSETS / "Video" / "Deploy_P2.webp",
)
DEFEAT_ART = ASSETS / "Video" / "UNIT-DEFEATED.webp"
TRANSPARENT = "#ff00ff"
SHADE_OPACITY = .465
SHADE_FADE_SECONDS = .35
SHADE_TICK_MS = 16
DOOR_TRAVEL_SECONDS = .45
DOOR_TICK_MS = 16
RESERVE_HOLD_MS = 250
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000


def allow_click_through(window):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_style, set_style = user32.GetWindowLongW, user32.SetWindowLongW
    get_style.argtypes = (wintypes.HWND, ctypes.c_int)
    set_style.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
    get_style.restype = set_style.restype = wintypes.LONG
    handle = int(window.frame(), 0)
    style = get_style(handle, GWL_EXSTYLE)
    ctypes.set_last_error(0)
    previous = set_style(handle, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
    if not previous and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())


class DeploymentOverlay:
    """Play match overlays and animate the active Hangar door."""

    def __init__(self, root, card_screen_bounds):
        self.root = root
        self.card_screen_bounds = card_screen_bounds
        self.window = None
        self.shade = None
        self.image = None
        self.job = None
        self.fade_job = None
        self.opacity = 0.0
        self.hangar = None
        self.door_job = None
        self.last_door_frame = 0

    def create_layer(self, background):
        layer = tk.Toplevel(self.root)
        layer.withdraw()
        layer.overrideredirect(True)
        layer.transient(self.root)
        layer.configure(background=background)
        return layer

    def play(self, hangar, *, with_clip=True):
        self.stop()
        if not self.root.winfo_viewable():
            return
        self.hangar = hangar
        self.last_door_frame = max(0, len(hangar_art()) - 1)
        self.draw_door(True, monotonic(), with_clip)

    def play_defeat(self):
        self.stop()
        if self.root.winfo_viewable():
            self.start_video(DEFEAT_ART)

    def play_garrison(self, *, rescue, side, points):
        self.start_effect(draw_garrison, GARRISON_EFFECT_SECONDS, rescue, side, points, particles())

    def play_energize(self, *, side):
        self.start_effect(draw_energize, ENERGIZE_SECONDS, side)

    def play_dash(self, *, side):
        self.start_effect(draw_dash, DASH_SECONDS, side)

    def play_goal(self, *, side, points):
        self.start_effect(draw_goal, GOAL_SECONDS, side, points)

    def start_effect(self, draw, duration, *args):
        self.stop()
        if sys.platform != "win32" or not self.root.winfo_viewable():
            return
        try:
            self.window = self.create_layer(TRANSPARENT)
            self.window.attributes("-transparentcolor", TRANSPARENT)
            canvas = tk.Canvas(self.window, background=TRANSPARENT, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            self.bounds = None
            self.effect_frame(canvas, monotonic(), draw, duration, args)
            if self.window is None:
                return
            self.window.update_idletasks()
            allow_click_through(self.window)
            self.window.deiconify()
        except (OSError, tk.TclError):
            self.playback_failed()

    def effect_frame(self, canvas, started, draw, duration, args):
        self.job = None
        t = (monotonic() - started) / duration
        card = self.card_screen_bounds()
        if t >= 1 or not card or not self.root.winfo_viewable():
            self.stop()
            return
        left, top, card_width, card_height = card
        width, height = min(790, card_width), min(370, card_height)
        x = left + (card_width - width) // 2
        y = top + (card_height - height) // 2
        bounds = f"{width}x{height}+{x}+{y}"
        if bounds != self.bounds:
            self.window.geometry(bounds)
            self.bounds = bounds
        draw(canvas, width, height, t, *args)
        self.job = self.root.after(20, self.effect_frame, canvas, started, draw, duration, args)

    def restore_hangar(self, hangars):
        if self.hangar is not None:
            previous = self.hangar
            self.hangar = hangars[previous.side]
            self.hangar.set_door_frame(previous.door_frame)

    def draw_door(self, opening, started, with_clip=False):
        self.door_job = None
        if not self.root.winfo_viewable() or not self.hangar.winfo_exists():
            self.stop()
            return
        progress = min(1.0, (monotonic() - started) / DOOR_TRAVEL_SECONDS) if self.last_door_frame else 1.0
        eased = progress * progress * (3 - 2 * progress)
        frame = round(self.last_door_frame * (eased if opening else 1 - eased))
        self.hangar.set_door_frame(frame)
        if progress < 1:
            self.door_job = self.root.after(DOOR_TICK_MS, self.draw_door, opening, started, with_clip)
        elif opening and with_clip:
            self.start_video(DEPLOYMENT_ART_BY_SIDE[self.hangar.side])
        elif opening:
            self.door_job = self.root.after(RESERVE_HOLD_MS, self.finish_transition)
        else:
            self.stop()

    def start_video(self, path):
        if sys.platform != "win32":
            self.finish_transition()
            return
        try:
            self.image = Image.open(path)
            self.shade = self.create_layer("#000000")
            self.shade.attributes("-alpha", self.opacity)
            self.window = self.create_layer(TRANSPARENT)
            self.window.attributes("-transparentcolor", TRANSPARENT)
            self.label = tk.Label(
                self.window, background=TRANSPARENT, borderwidth=0, highlightthickness=0, padx=0, pady=0,
            )
            self.label.pack(fill="both", expand=True)
            self.bounds = None
            self.shade_bounds = None
            self.index = 0
            self.deadline = monotonic()
            self.draw_frame()
            if self.window is not None:
                self.window.update_idletasks()
                for layer in (self.shade, self.window):
                    allow_click_through(layer)
                    layer.deiconify()
                self.window.lift(self.shade)
                self.fade_to(SHADE_OPACITY)
        except (OSError, tk.TclError):
            self.playback_failed()

    def draw_frame(self):
        self.job = None
        if not self.root.winfo_viewable():
            self.stop()
            return
        try:
            now = monotonic()
            while self.deadline <= now:
                if self.index >= self.image.n_frames:
                    self.release_video()
                    self.fade_to(0.0)
                    return
                self.image.seek(self.index)
                self.image.load()
                self.index += 1
                self.deadline += max(1, self.image.info["duration"]) / 1000

            # Fit the original 16:9 canvas to the window, then draw only its visible strip.
            area_width, area_height, area_x, area_y = self.position_shade()
            width = min(self.image.width, area_width, round(area_height * 16 / 9))
            height = max(1, round(width * self.image.height / self.image.width))
            x = area_x + (area_width - width) // 2
            y = area_y + (area_height - height) // 2
            bounds = f"{width}x{height}+{x}+{y}"
            if bounds != self.bounds:
                self.window.geometry(bounds)
                self.bounds = bounds
            frame = self.image.resize((width, height), Image.Resampling.BILINEAR)
            self.label.image = ImageTk.PhotoImage(frame, master=self.window)
            self.label.configure(image=self.label.image)
            delay = max(1, ceil((self.deadline - monotonic()) * 1000))
            self.job = self.root.after(delay, self.draw_frame)
        except (OSError, tk.TclError, EOFError, KeyError):
            self.playback_failed()

    def position_shade(self):
        width, height = self.root.winfo_width(), self.root.winfo_height()
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        bounds = f"{width}x{height}+{x}+{y}"
        if bounds != self.shade_bounds:
            self.shade.geometry(bounds)
            self.shade_bounds = bounds
        return width, height, x, y

    def fade_to(self, target):
        self.cancel_fade()
        self.fade_step(self.opacity, target, monotonic())

    def fade_step(self, start, target, started):
        self.fade_job = None
        if not self.root.winfo_viewable():
            self.stop()
            return
        try:
            progress = min(1.0, (monotonic() - started) / SHADE_FADE_SECONDS)
            eased = progress * progress * (3 - 2 * progress)
            self.opacity = start + (target - start) * eased
            self.shade.attributes("-alpha", self.opacity)
            if self.window is None:
                self.position_shade()
            if progress < 1:
                self.fade_job = self.root.after(SHADE_TICK_MS, self.fade_step, start, target, started)
            elif target == 0:
                self.finish_transition()
        except tk.TclError:
            self.playback_failed()

    def cancel_fade(self):
        if self.fade_job is not None:
            self.root.after_cancel(self.fade_job)
            self.fade_job = None

    def release_video(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
            self.label = None
        if self.image is not None:
            self.image.close()
            self.image = None

    def stop_video(self):
        self.cancel_fade()
        self.release_video()
        if self.shade is not None:
            self.shade.destroy()
            self.shade = None
        self.opacity = 0.0

    def finish_transition(self):
        self.stop_video()
        if self.hangar is not None:
            self.draw_door(False, monotonic())

    def stop(self):
        if self.door_job is not None:
            self.root.after_cancel(self.door_job)
            self.door_job = None
        self.stop_video()
        if self.hangar is not None:
            if self.hangar.winfo_exists():
                self.hangar.set_door_frame(0)
            self.hangar = None

    def playback_failed(self):
        logging.getLogger(__name__).warning("Could not play match overlay artwork", exc_info=True)
        self.finish_transition()
