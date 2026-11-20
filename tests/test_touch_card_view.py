"""Gesture precedence and cleanup, independent of the native input driver."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from companion.card_gestures import CardDismissGesture


class Scheduler:
    def __init__(self):
        self.jobs = {}
        self.serial = 0
    def bind(self, *args, **kwargs): pass
    def after(self, delay, callback):
        self.serial += 1
        self.jobs[self.serial] = callback
        return self.serial
    def after_cancel(self, job): self.jobs.pop(job, None)
    def flush(self):
        jobs, self.jobs = self.jobs, {}
        for callback in jobs.values(): callback()


class CardDismissTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Scheduler()
        self.mount = Mock(canvas=self.canvas)
        self.mount.remote.target.return_value = None
        self.mount.attack.target.return_value = object()
        self.dialog = Mock()
        self.dialog.window.winfo_exists.return_value = True
        self.dialog.window.grab_current.return_value = self.dialog.window
        self.gesture = CardDismissGesture(self.dialog, self.mount)
        self.event = SimpleNamespace(x=12, y=24)

    def test_double_tap_cancels_weapon_action_before_closing(self):
        self.gesture.click(self.event)
        self.gesture.close(self.event)
        self.canvas.flush()
        self.mount.click.assert_not_called()
        self.dialog.cancel.assert_called_once()

    def test_single_link_tap_still_activates_once(self):
        self.gesture.click(self.event)
        self.canvas.flush()
        self.canvas.flush()
        self.mount.click.assert_called_once()
        self.assertEqual(self.mount.click.call_args.args[0].x,12)
        self.dialog.cancel.assert_not_called()

    def test_plain_art_tap_does_not_queue_an_action(self):
        self.mount.attack.target.return_value = None
        self.gesture.click(self.event)
        self.assertFalse(self.canvas.jobs)
        self.dialog.cancel.assert_not_called()

    def test_destroy_or_resize_cancels_pending_action(self):
        self.gesture.click(self.event)
        self.gesture.cancel()
        self.canvas.flush()
        self.mount.click.assert_not_called()

    def test_nested_dialog_keeps_its_parent_open(self):
        self.dialog.window.grab_current.return_value = object()
        self.gesture.close()
        self.dialog.cancel.assert_not_called()

if __name__ == '__main__': unittest.main(verbosity=2)
