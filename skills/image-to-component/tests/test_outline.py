"""outline: smoothing a hard alpha edge along its own arc, before it is ever upscaled.

Expected values come from the fixture geometry: a staircase's residual around the line it
approximates, a disc's area, a square's straight sides. None is computed by the function under test.
"""
from __future__ import annotations

import math
import unittest

from ._fixtures import rgba
from scripts import outline
from scripts.jaggedness import alpha_field, contours


def hard(width: int, height: int, inside) -> bytes:
    return rgba(width, height, lambda x, y: (0, 0, 0, 255) if inside(x, y) else (0, 0, 0, 0))


def area(loop) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]))) / 2


def residual_about_line(points) -> float:
    """RMS distance from the least-squares line through `points`."""
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for _, y in points)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    nx, ny = -math.sin(angle), math.cos(angle)
    return math.sqrt(sum(((x - mx) * nx + (y - my) * ny) ** 2 for x, y in points) / n)


def on_slope(points, lo: float, hi: float):
    """Points of a y = x / 2 hypotenuse, away from the triangle's corners."""
    return [(x, y) for x, y in points if lo < x < hi and abs(y - x / 2) < 1.5]


class SmoothedOutlines(unittest.TestCase):
    def test_a_two_to_one_staircase_becomes_its_line(self):
        # Opaque below y = x/2: each row's run is two pixels, so the edge steps every 2 px across and
        # 1 px down. Marching squares chamfers the corners, which leaves a zig-zag about the line.
        buf = hard(60, 36, lambda x, y: 4 <= x < 56 and 2 <= y < 30 and y <= x // 2)
        (loop,) = outline.smoothed_outlines(buf, 60, 36, sigma=outline.SIGMA)
        (raw,) = contours(alpha_field(buf, 60, 36), 60, 36, 128)
        before = residual_about_line(on_slope(outline.resample(raw, 0.25), 14, 46))
        after = residual_about_line(on_slope(loop, 14, 46))
        self.assertGreater(before, 0.1)
        self.assertLess(after, before / 4)

    def test_a_small_disc_keeps_its_area(self):
        # A single Gaussian pulls a closed curve inward by ~σ²/2R: 0.08 px on a radius-4 disc, a
        # band of 2π·4·0.08 ≈ 2 px² out of ~51 — 4 %. 2G − G² cancels it to well under 1 %.
        buf = hard(20, 20, lambda x, y: (x + 0.5 - 10) ** 2 + (y + 0.5 - 10) ** 2 <= 4 ** 2)
        (raw,) = contours(alpha_field(buf, 20, 20), 20, 20, 128)
        (loop,) = outline.smoothed_outlines(buf, 20, 20, sigma=outline.SIGMA)
        self.assertAlmostEqual(area(loop), area(raw), delta=0.01 * area(raw))

    def test_straight_sides_stay_where_they_are(self):
        buf = hard(30, 30, lambda x, y: 5 <= x < 25 and 5 <= y < 25)
        (loop,) = outline.smoothed_outlines(buf, 30, 30, sigma=outline.SIGMA)
        mid_left = [x for x, y in loop if 12 < y < 18 and x < 15]
        self.assertTrue(mid_left)
        for x in mid_left:
            self.assertAlmostEqual(x, 5.0, delta=0.05)

    def test_holes_and_a_one_pixel_hole_survive(self):
        # A ring with a separate 1 px hole elsewhere: every loop is smoothed on its own arc, so
        # none can merge with another, and a loop shorter than the kernel is not collapsed to a point.
        def inside(x, y):
            in_ring = 3 <= x < 17 and 3 <= y < 17 and not (7 <= x < 13 and 7 <= y < 13)
            in_block = 20 <= x < 27 and 5 <= y < 12 and (x, y) != (23, 8)
            return in_ring or in_block
        loops = outline.smoothed_outlines(hard(30, 20, inside), 30, 20, sigma=outline.SIGMA)
        self.assertEqual(len(loops), 4)
        self.assertGreater(min(area(loop) for loop in loops), 0.3)

    def test_nothing_visible_has_no_outline(self):
        self.assertEqual(outline.smoothed_outlines(hard(8, 8, lambda x, y: False), 8, 8), [])


if __name__ == "__main__":
    unittest.main()
