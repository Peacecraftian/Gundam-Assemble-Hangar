import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Video import ANIMATION_FILES
from Video import dash_effect


class DashEffectTests(unittest.TestCase):
    def tearDown(self):
        dash_effect.dash_frames.cache_clear()

    def test_published_clip_has_safe_coverage_and_clear_ending(self):
        dash_effect.dash_frames.cache_clear()
        self.assertIn(dash_effect.DASH_ART.name, ANIMATION_FILES)
        frames, deadlines = dash_effect.dash_frames()
        self.assertEqual(len(frames), 25)
        self.assertEqual(deadlines[-1], 1.5)
        self.assertTrue(all(a < b for a, b in zip(deadlines, deadlines[1:])))
        self.assertIsNone(frames[-1].getbbox())
        for frame in frames:
            self.assertEqual(frame.size, (256, 256))
            self.assertFalse(any(frame.getchannel("A").histogram()[1:255]))
        self.assertIs(dash_effect.dash_frames()[0], frames)

    def test_missing_or_corrupt_art_retains_action_notification(self):
        class Canvas:
            def delete(self, *_args):
                pass

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "animation.webp"
            for corrupt in (False, True):
                if corrupt:
                    path.write_bytes(b"broken webp")
                dash_effect.dash_frames.cache_clear()
                with patch.object(dash_effect, "DASH_ART", path), \
                        patch.object(dash_effect, "draw_placard") as placard, \
                        self.assertLogs(dash_effect.__name__, level="WARNING"):
                    dash_effect.draw_dash(Canvas(), 790, 370, .2, 1)
                self.assertEqual(placard.call_args.args[4:6],
                                 ("DASH", "PLAYER 2  ·  TIMELINE +2"))


if __name__ == "__main__":
    unittest.main()
