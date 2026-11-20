import math
import unittest
from unittest.mock import Mock

from companion.battlefield_stars import SPACE_STARS, _make_star_field, draw_ground_stars


class SpaceStarTests(unittest.TestCase):
    def test_field_is_repeatable_sparse_and_inside_hexes(self):
        self.assertEqual(SPACE_STARS, _make_star_field())
        self.assertEqual(len(SPACE_STARS), 203)
        self.assertGreater(sum(bool(stars) for stars in SPACE_STARS.values()), 40)
        self.assertLess(sum(map(len, SPACE_STARS.values())), 140)
        self.assertGreater(sum(not stars for stars in SPACE_STARS.values()), 90)
        for stars in SPACE_STARS.values():
            for dx, dy, size, color in stars:
                self.assertLess(abs(dy) + size, math.sqrt(3) / 2)
                self.assertLess(math.sqrt(3) * abs(dx) + abs(dy) + 2 * size, math.sqrt(3))
                self.assertIn(color, ('#293B49', '#6D8A8D', '#BFC3C6'))

    def test_only_space_ground_gets_stars_and_resizing_keeps_positions(self):
        canvas = Mock()
        key = next(key for key, stars in SPACE_STARS.items() if stars)
        for palette, terrain in [('urban', 'ground'), ('space', 'height1'), ('space', 'height2')]:
            draw_ground_stars(canvas, palette, terrain, key, 0, 0, 20)
        canvas.create_oval.assert_not_called()
        draw_ground_stars(canvas, 'space', 'ground', key, 100, 200, 20)
        first = canvas.create_oval.call_args_list[:]
        canvas.reset_mock()
        draw_ground_stars(canvas, 'space', 'ground', key, 200, 400, 40)
        for small, large in zip(first, canvas.create_oval.call_args_list):
            for axis in (0, 1):
                self.assertAlmostEqual(large.args[axis] + large.args[axis + 2],
                                       2 * (small.args[axis] + small.args[axis + 2]))
            self.assertEqual(small.kwargs['fill'], large.kwargs['fill'])
            self.assertEqual(large.kwargs['tags'], (key, 'hex-star', 'battlefield'))
