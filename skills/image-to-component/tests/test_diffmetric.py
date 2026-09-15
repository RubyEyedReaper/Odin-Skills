"""diffmetric: how close is the rendered SVG to the source raster?

Expected values are derived from the geometry of the fixtures by hand, never by calling the
function under test — a test against its own function asserts wiring, not correctness.
"""
from __future__ import annotations

import unittest

from ._fixtures import rgba, square
from scripts import diffmetric

W = H = 20


class AlphaIoU(unittest.TestCase):
    def test_identical_is_one(self):
        a = square(W, H, 4, 4, 8)
        self.assertEqual(diffmetric.alpha_iou(a, a), 1.0)

    def test_shifted_square_matches_hand_count(self):
        # 8x8 squares offset by 2px in x: overlap 6*8=48, union 64+64-48=80.
        a = square(W, H, 4, 4, 8)
        b = square(W, H, 6, 4, 8)
        self.assertAlmostEqual(diffmetric.alpha_iou(a, b), 48 / 80)

    def test_both_empty_is_one(self):
        empty = rgba(W, H, lambda x, y: (0, 0, 0, 0))
        self.assertEqual(diffmetric.alpha_iou(empty, empty), 1.0)


class MeanAbsError(unittest.TestCase):
    def test_uniform_colour_offset(self):
        a = square(W, H, 0, 0, W, colour=(100, 100, 100, 255))
        b = square(W, H, 0, 0, W, colour=(110, 90, 100, 255))
        # per pixel |10|+|10|+|0| over 3 channels = 20/3
        self.assertAlmostEqual(diffmetric.mae_rgb(a, b), 20 / 3)

    def test_transparent_pixels_ignored(self):
        a = square(W, H, 4, 4, 8, colour=(0, 0, 0, 255))
        b = bytearray(a)
        # repaint a fully transparent pixel's colour channels: invisible, must not count
        b[0:3] = bytes((255, 255, 255))
        self.assertEqual(diffmetric.mae_rgb(a, bytes(b)), 0.0)


class EdgeF1(unittest.TestCase):
    def test_identical_is_one(self):
        a = square(W, H, 5, 5, 10)
        self.assertEqual(diffmetric.edge_f1(a, a, W, H), 1.0)

    def test_one_pixel_shift_within_tolerance(self):
        a = square(W, H, 5, 5, 10)
        b = square(W, H, 6, 5, 10)
        self.assertEqual(diffmetric.edge_f1(a, b, W, H, tolerance=1), 1.0)

    def test_distant_shapes_score_zero(self):
        a = square(W, H, 0, 0, 4)
        b = square(W, H, 14, 14, 4)
        self.assertEqual(diffmetric.edge_f1(a, b, W, H, tolerance=1), 0.0)


class Compare(unittest.TestCase):
    def test_pass_and_named_failures(self):
        a = square(W, H, 4, 4, 8)
        ok = diffmetric.compare(a, a, W, H)
        self.assertTrue(ok["pass"])
        self.assertEqual(ok["failures"], [])

        far = square(W, H, 12, 12, 8)
        bad = diffmetric.compare(a, far, W, H)
        self.assertFalse(bad["pass"])
        self.assertIn("iou", bad["failures"])

    def test_thresholds_are_inclusive_bounds(self):
        a = square(W, H, 4, 4, 8)
        b = square(W, H, 6, 4, 8)  # iou exactly 0.6
        self.assertNotIn("iou", diffmetric.compare(a, b, W, H, thresholds={"iou": 0.6})["failures"])
        self.assertIn("iou", diffmetric.compare(a, b, W, H, thresholds={"iou": 0.61})["failures"])

    def test_jaggedness_of_the_render_is_reported_and_bounded(self):
        # A convex square has none (tests/test_jaggedness.py derives why), so a limit of 0.5 holds;
        # a staircase render fails it by name while IoU and edge-F1 stay out of the failures.
        a = square(40, 40, 10, 10, 20)
        ok = diffmetric.compare(a, a, 40, 40, thresholds={"jaggedness": 0.5})
        self.assertEqual(ok["jaggedness"], 0.0)
        self.assertTrue(ok["pass"])

        def stairs(x, y):
            inside = 4 <= x < 36 and 4 <= y < 36 and (x - 4) // 4 >= (y - 4) // 4
            return (0, 0, 0, 255) if inside else (0, 0, 0, 0)
        jagged = rgba(40, 40, stairs)
        bad = diffmetric.compare(jagged, jagged, 40, 40, thresholds={"jaggedness": 0.5})
        self.assertEqual(bad["failures"], ["jaggedness"])

    def test_default_limit_refuses_a_stepped_diamond(self):
        # |i|+|j| <= 4 in 8 px blocks: four staircases of four stairs, 16 concave right angles, so
        # 16π of excess turning at 3 px and ~none at 12 px. Orthogonally convex, so the perimeter is
        # 2·(72+72) = 288, less 36 cut corners of 0.29 = 277.5. Scaled by the 96√2 diagonal:
        # 16π·135.8/277.5 ≈ 24.6 — well over the default 15.
        def diamond(x, y):
            return (0, 0, 0, 255) if abs((x - 48) // 8) + abs((y - 48) // 8) <= 4 else (0, 0, 0, 0)
        buf = rgba(96, 96, diamond)
        result = diffmetric.compare(buf, buf, 96, 96)
        self.assertAlmostEqual(result["jaggedness"], 24.6, delta=0.15 * 24.6)
        self.assertIn("jaggedness", result["failures"])

    def test_default_limit_passes_an_anti_aliased_disc(self):
        def coverage(x, y):
            hits = sum((x + (i + 0.5) / 4 - 48) ** 2 + (y + (j + 0.5) / 4 - 48) ** 2 <= 36 ** 2
                       for i in range(4) for j in range(4))
            return (0, 0, 0, round(255 * hits / 16))
        disc = rgba(96, 96, coverage)
        self.assertTrue(diffmetric.compare(disc, disc, 96, 96)["pass"])

    def test_size_mismatch_refused(self):
        with self.assertRaises(ValueError):
            diffmetric.compare(b"\0" * 4, b"\0" * 8, 1, 1)


if __name__ == "__main__":
    unittest.main()
