import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from companion.artwork import PhotoCache
from companion.catalog import load_tactics
from companion.tactics import TacticsScreen
from companion.theme import setup_theme
from companion.workspace import Workspace


class TacticsTouchTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        setup_theme(self.root)
        self.root.geometry('1366x688+0+0')
        self.root.columnconfigure(0,weight=1)
        self.root.rowconfigure(1,weight=1)
        tk.Frame(self.root,height=86).grid(row=0,column=0,sticky='ew')
        self.app=SimpleNamespace(workspace=Workspace(self.root),photos=PhotoCache(self.root),tactics=load_tactics())
        self.screen=TacticsScreen(self.root,self.app)
        self.screen.show()
        self.settle()

    def tearDown(self):
        self.root.destroy()

    def settle(self,ms=50):
        self.root.update()
        self.root.after(ms,self.root.quit);self.root.mainloop()

    def event(self,x,y,**kw):
        return SimpleNamespace(x=x,y=y,**kw)

    def test_both_swipes_change_only_the_pressed_rail_and_never_select(self):
        s=self.screen
        with patch.object(s,'pick') as pick:
            for side,x in enumerate((20,s.width-20)):
                s.press_fan(self.event(x,400))
                s.drag_fan(self.event(x,225))
                self.assertEqual(s.offsets[side],3)
                s.release_fan(self.event(x,225))
                pick.assert_not_called()
            self.assertEqual(s.offsets,[3,3])
            # Reverse and clamp; dragging across the middle still owns its original rail.
            s.press_fan(self.event(20,200))
            s.release_fan(self.event(s.width-20,600))
            self.assertEqual(s.offsets,[0,3])
            pick.assert_not_called()

    def test_tap_waits_for_release_and_small_jitter_remains_a_tap(self):
        s=self.screen
        number=next(iter(s.slots))
        with patch.object(s,'card_at',return_value=number),patch.object(s,'pick') as pick:
            s.press_fan(self.event(20,200));pick.assert_not_called()
            s.release_fan(self.event(24,203));pick.assert_called_once_with(number)
            pick.reset_mock()
            s.press_fan(self.event(20,200));s.cancel_gesture()
            s.release_fan(self.event(20,200));pick.assert_not_called()
            s.press_fan(self.event(20,200));s.release_fan(self.event(70,200))
            pick.assert_not_called()

    def test_buttons_wheel_limits_and_return_animation_lock(self):
        s=self.screen
        self.assertTrue(s.rail_buttons[0][0].instate(['disabled']))
        s.rail_buttons[0][1].invoke();self.assertEqual(s.offsets,[1,0])
        s.scroll_fan(self.event(s.width-20,200,delta=-120));self.assertEqual(s.offsets,[1,1])
        s.scroll_fan(self.event(s.width/2,200,delta=-120));self.assertEqual(s.offsets,[1,1])
        s.move_fan(0,999)
        self.assertEqual(s.offsets[0],len(s.rails[0])-s.fan_count)
        self.assertTrue(s.rail_buttons[0][1].instate(['disabled']))
        before=s.offsets[:];s.returning=True;s.origin=(0,before[0]);s.move_fan(0,-1)
        self.assertEqual(s.offsets,before)
        s.returning=False

    def test_controls_results_and_keyboard_fit_both_sizes(self):
        s=self.screen
        for width,height in ((1366,688),(1920,1080)):
            with self.subTest(size=(width,height)):
                self.root.geometry(f'{width}x{height}+0+0');self.settle()
                s.query.set('a');self.settle()
                self.assertGreater(len(s.result_buttons),0)
                for button in [s.clear_button,*s.rail_buttons[0],*s.rail_buttons[1],*s.result_buttons]:
                    self.assertGreaterEqual(button.winfo_height(),48)
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),s.canvas.winfo_rooty()+s.height)
                    self.assertGreaterEqual(button.winfo_rootx(),s.canvas.winfo_rootx())
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),s.canvas.winfo_rootx()+s.width)
                self.assertTrue(s.entry.touch_keyboard_options['live'])
                with patch('companion.dialogs.monitor_bounds',return_value=(0,0,width,768 if width==1366 else 1080)):
                    s.entry.event_generate('<ButtonRelease-1>',x=10,y=10);self.settle()
                    keyboard=self.root.touch_keyboard
                    keyboard.clear();keyboard.insert('a')
                    self.assertTrue(s.matches)
                    keyboard.accept();self.settle()
                expected=s.matches[0]
                s.result_buttons[0].invoke();self.settle(450)
                self.assertEqual(s.selected,expected)
                s.clear();self.settle(450)
                self.assertIsNone(s.selected)

    def test_return_after_resize_and_scrolling_keeps_card_reachable(self):
        s=self.screen
        s.pick(s.rails[0][-1]);self.settle(450)
        s.move_fan(0,-999)
        s.clear()
        self.root.geometry('1020x595+0+0');self.settle(500)
        self.assertIsNone(s.selected)
        self.assertLessEqual(s.offsets[0],len(s.rails[0])-s.fan_count)

