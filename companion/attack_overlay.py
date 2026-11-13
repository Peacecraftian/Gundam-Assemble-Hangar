from .remote_overlay import contains


class AttackOverlay:
    """Map printed stat bands to the canvas's fitted card rectangle."""

    def __init__(self):
        self.boxes = {}

    def place(self, profiles, card_box):
        self.boxes.clear()
        if card_box is None:
            return
        left, top, right, bottom = card_box
        width, height = right - left, bottom - top
        for profile in profiles:
            x1, y1, x2, y2 = profile.bounds
            self.boxes[profile] = left + x1 * width, top + y1 * height, left + x2 * width, top + y2 * height

    def target(self, event):
        return next((profile for profile, box in self.boxes.items() if contains(box, event.x, event.y)), None)
