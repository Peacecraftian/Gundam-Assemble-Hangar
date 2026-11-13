from .artwork import fitted_card
from .theme import AMBER, CELL, MUTED


def contains(box, x, y):
    left, top, right, bottom = box
    return left <= x <= right and top <= y <= bottom


class RemoteWeaponOverlay:
    def __init__(self, canvas, app):
        self.canvas = canvas
        self.photos = app.photos
        self.weapons = app.remote_weapons.values()
        self.parent = None
        self.card_box = None
        self.icon_boxes = {}
        self.active = None
        self.photo = None

    def place(self, number, card_box, *, selection=None):
        parent = number, selection
        if parent != self.parent:
            self.parent = parent
            self.active = None
        self.card_box = card_box
        self.icon_boxes.clear()
        if card_box is not None:
            left, top, right, bottom = card_box
            width, height = right - left, bottom - top
            for weapon in self.weapons:
                if weapon.parent == number:
                    x1, y1, x2, y2 = weapon.icon_bounds
                    self.icon_boxes[weapon] = (left + width * x1, top + height * y1,
                                               left + width * x2, top + height * y2)
        self.draw()

    def target(self, x, y):
        if self.active is not None:
            return self.active if self.card_box is not None and contains(self.card_box, x, y) else None
        return next((weapon for weapon, box in self.icon_boxes.items() if contains(box, x, y)), None)

    def click(self, event):
        weapon = self.target(event.x, event.y)
        if weapon is None:
            return False
        self.active = None if self.active else weapon
        self.draw()
        return True

    def hover(self, event):
        self.clear_hover()
        weapon = self.target(event.x, event.y)
        if weapon is None:
            return None
        if self.active is not None:
            return "Click to return to Unit Card"
        self.canvas.create_rectangle(*self.icon_boxes[weapon], outline=AMBER, tags="remote_hover")
        return f"View {weapon.name}"

    def clear_hover(self):
        self.canvas.delete("remote_hover")

    def draw(self):
        canvas = self.canvas
        canvas.delete("remote_overlay")
        self.clear_hover()
        self.photo = None
        if self.active is None or self.card_box is None:
            return
        left, top, right, bottom = self.card_box
        x, y = (left + right) / 2, (top + bottom) / 2
        self.photo = self.photos.get(fitted_card, self.active.image, (right - left, bottom - top))
        canvas.create_rectangle(left, top, right, bottom, fill=CELL, width=0, tags="remote_overlay")
        if self.photo is not None:
            canvas.create_image(x, y, image=self.photo, tags="remote_overlay")
        else:
            canvas.create_text(x, y, text=f"{self.active.name}\nCard image unavailable", fill=MUTED,
                               width=right - left, justify="center", tags="remote_overlay")
