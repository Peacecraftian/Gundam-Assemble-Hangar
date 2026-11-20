"""Double-tap dismissal for the full Unit Card window."""
from types import SimpleNamespace

CLICK_DELAY_MS = 500


class CardDismissGesture:
    def __init__(self, dialog, mount):
        self.dialog, self.mount = dialog, mount
        self.pending = None
        canvas = mount.canvas
        # Defer only links inside the artwork, so a second tap can close instead
        # of opening an attack dialog. Footer buttons keep immediate activation.
        canvas.bind('<Button-1>', self.click)
        canvas.bind('<Double-Button-1>', self.close)
        canvas.bind('<Destroy>', self.cancel, add='+')
        canvas.bind('<Configure>', self.cancel, add='+')
        dialog.window.bind('<Double-Button-1>', self.background_double, add='+')

    def cancel(self, _event=None):
        if self.pending is not None:
            self.mount.canvas.after_cancel(self.pending)
            self.pending = None

    def click(self, event):
        self.cancel()
        if self.mount.remote.target(event.x, event.y) is None and self.mount.attack.target(event) is None:
            return 'break'
        point = SimpleNamespace(x=event.x, y=event.y)

        def activate():
            self.pending = None
            if self.dialog.window.winfo_exists():
                self.mount.click(point)

        self.pending = self.mount.canvas.after(CLICK_DELAY_MS, activate)
        return 'break'

    def close(self, _event=None):
        self.cancel()
        window = self.dialog.window
        if window.winfo_exists() and window.grab_current() in (None, window):
            self.dialog.cancel()
        return 'break'

    def background_double(self, event):
        if event.widget.winfo_class() in ('Canvas', 'Frame', 'TFrame', 'Label', 'TLabel'):
            return self.close(event)
