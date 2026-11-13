import tkinter as tk
from functools import lru_cache
from math import hypot
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .theme import BACKGROUND


@lru_cache(maxsize=1)
def radial_mask():
    mask = Image.new("L", (97, 65))
    mask.putdata([
        round(255 * max(0, 1 - hypot((x / 96 - .46) / .70, (y / 64) / .78)))
        for y in range(65) for x in range(97)
    ])
    return mask


def workspace_art(size):
    width, height = size
    image = Image.new("RGB", size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    for x in range(32, width, 64):
        draw.line((x, 0, x, height - 1), fill="#1B2223")
    for y in range(24, height, 64):
        draw.line((0, y, width - 1, y), fill="#1B2223")
    image.paste("#273235", (0, 0, width, height), radial_mask().resize(size, Image.Resampling.BILINEAR))
    return image


class Workspace:
    """Share one static wallpaper across the exposed layout layers in a window."""

    def __init__(self, window):
        self.window = window
        self.layers = {}
        self.photo = None
        self.size = None
        self.resize_job = None
        background = self.layer(window)
        background.place(relwidth=1, relheight=1)
        window.bind("<Configure>", self.schedule, add="+")
        window.bind("<Destroy>", self.cancel, add="+")

    def layer(self, parent, *, width=1, height=1):
        canvas = tk.Canvas(parent, background=BACKGROUND, highlightthickness=0, takefocus=False,
                           width=width, height=height)
        self.layers[canvas] = canvas.create_image(0, 0, anchor="nw", image=self.photo or "")
        canvas.bind("<Configure>", lambda _event: self.align(canvas))
        canvas.bind("<Map>", lambda _event: self.align(canvas))
        canvas.bind("<Destroy>", lambda _event: self.layers.pop(canvas, None))
        return canvas

    def align(self, canvas):
        x = canvas.winfo_rootx() - self.window.winfo_rootx()
        y = canvas.winfo_rooty() - self.window.winfo_rooty()
        canvas.coords(self.layers[canvas], canvas.canvasx(0) - x, canvas.canvasy(0) - y)

    def schedule(self, event):
        if event.widget is self.window and (event.width, event.height) != self.size and self.resize_job is None:
            self.resize_job = self.window.after(30, self.paint)

    def paint(self):
        self.resize_job = None
        size = self.window.winfo_width(), self.window.winfo_height()
        if size == self.size or min(size) < 2:
            return
        self.photo = ImageTk.PhotoImage(workspace_art(size), master=self.window)
        self.size = size
        for canvas, item in self.layers.items():
            canvas.itemconfigure(item, image=self.photo)
            self.align(canvas)

    def cancel(self, event):
        if event.widget is self.window and self.resize_job is not None:
            self.window.after_cancel(self.resize_job)
            self.resize_job = None

    def caption(self, parent, text, style="Heading.TLabel"):
        canvas = self.layer(parent)
        caption = canvas.create_text(2, 1, text=text, anchor="nw")
        theme = ttk.Style(canvas)

        def restyle(_event=None):
            canvas.itemconfigure(caption, font=theme.lookup(style, "font"), fill=theme.lookup(style, "foreground"))
            _, _, right, bottom = canvas.bbox(caption)
            canvas.configure(width=right + 1, height=bottom + 1)

        restyle()
        canvas.bind("<<ThemeChanged>>", restyle)
        return canvas
