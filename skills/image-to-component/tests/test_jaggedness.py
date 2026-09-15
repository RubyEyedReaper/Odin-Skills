"""jaggedness: turning along a contour that cancels at 3 px and is gone by 12 px.

Expected values are derived from fixture geometry by hand. The quantity is excess turning — total
absolute turning minus the net 2π of a closed loop — which is zero for a convex shape and exactly
π per concave right angle. A corner that is still there at 12 px is geometry; one that cancels
against its neighbour at 3 px and has vanished by 12 px is a staircase or a wobble.
"""
from __future__ import annotations

import math
import unittest

from ._fixtures import box_blur_alpha, rgba, square, upscaled_disc
from scripts import jaggedness as jag

CUT = 1 - math.sqrt(0.5)  # marching squares cuts each pixel corner: two half-edges become a diagonal


def mask(width: int, height: int, inside) -> bytes:
    return rgba(width, height, lambda x, y: (0, 0, 0, 255) if inside(x, y) else (0, 0, 0, 0))


class Contours(unittest.TestCase):
    def test_empty_image_has_no_contour(self):
        self.assertEqual(jag.contours([0.0] * 100, 10, 10, 128), [])

    def test_square_is_one_loop_with_corner_cut_perimeter(self):
        # 10x10 opaque square: axis perimeter 40, four corners each shortened by CUT.
        buf = square(20, 20, 5, 5, 10)
        loops = jag.contours(jag.alpha_field(buf, 20, 20), 20, 20, 128)
        self.assertEqual(len(loops), 1)
        self.assertAlmostEqual(jag.loop_length(loops[0]), 40 - 4 * CUT, places=1)

    def test_crossing_is_interpolated_between_pixel_centres(self):
        # Right-hand column at alpha 191: the 128 crossing sits (191-128)/191 of the way from that
        # column's centre (15.5) toward the next (16.5) — x = 15.5 + 63/191.
        buf = rgba(20, 20, lambda x, y: (0, 0, 0, (255 if x < 15 else 191)) if 5 <= x <= 15 and 5 <= y < 15
                   else (0, 0, 0, 0))
        (loop,) = jag.contours(jag.alpha_field(buf, 20, 20), 20, 20, 128)
        self.assertAlmostEqual(max(x for x, _ in loop), 15.5 + 63 / 191, places=6)

    def test_diagonal_neighbours_stay_separate_at_a_saddle(self):
        # Two blocks touching only at a corner: the saddle cell averages 127.5 < 128, so the
        # blocks are not joined through it — two loops, not one.
        buf = mask(12, 12, lambda x, y: (2 <= x < 6 and 2 <= y < 6) or (6 <= x < 10 and 6 <= y < 10))
        self.assertEqual(len(jag.contours(jag.alpha_field(buf, 12, 12), 12, 12, 128)), 2)

    def test_hole_is_its_own_loop(self):
        buf = mask(20, 20, lambda x, y: 4 <= x < 16 and 4 <= y < 16 and not (8 <= x < 12 and 8 <= y < 12))
        self.assertEqual(len(jag.contours(jag.alpha_field(buf, 20, 20), 20, 20, 128)), 2)


class ExcessTurning(unittest.TestCase):
    def test_convex_square_has_none(self):
        buf = square(60, 60, 10, 10, 40)
        (loop,) = jag.contours(jag.alpha_field(buf, 60, 60), 60, 60, 128)
        for stride in (3, 12):
            self.assertAlmostEqual(jag.excess_turning(loop, stride), 0.0, places=6)

    def test_one_concave_corner_is_pi_at_both_scales(self):
        # An L: 5 convex right angles and 1 concave. |turn| = 6·π/2 = 3π, net 2π, excess π.
        buf = mask(80, 80, lambda x, y: 10 <= x < 70 and 10 <= y < 70 and not (x >= 40 and y >= 40))
        (loop,) = jag.contours(jag.alpha_field(buf, 80, 80), 80, 80, 128)
        self.assertAlmostEqual(jag.excess_turning(loop, 3), math.pi, places=2)
        self.assertAlmostEqual(jag.excess_turning(loop, 12), math.pi, places=2)


def staircase(steps: int, size: int):
    """An upper-right triangle whose hypotenuse is `steps` stairs of `size` px, 10 px margin."""
    extent = steps * size + 20

    def inside(x, y):
        return 10 <= x < 10 + steps * size and 10 <= y < 10 + steps * size and (x - 10) // size >= (y - 10) // size
    return mask(extent, extent, inside), extent


class Jaggedness(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(jag.jaggedness(rgba(8, 8, lambda x, y: (0, 0, 0, 0)), 8, 8), 0.0)

    def test_square_and_l_shape_are_zero(self):
        self.assertAlmostEqual(jag.jaggedness(square(60, 60, 10, 10, 40), 60, 60), 0.0, places=6)
        ell = mask(80, 80, lambda x, y: 10 <= x < 70 and 10 <= y < 70 and not (x >= 40 and y >= 40))
        self.assertAlmostEqual(jag.jaggedness(ell, 80, 80), 0.0, places=2)

    def test_staircase_matches_hand_derivation(self):
        # N stairs of 6 px: N-1 concave right angles → excess (N-1)π at 3 px, ~0 at 12 px, where
        # the stairs read as one straight hypotenuse. Axis perimeter: top + right + N·6 across +
        # N·6 down = 24N; 2N+2 corners each cut by CUT. Normalised by the image diagonal.
        n, size = 10, 6
        buf, extent = staircase(n, size)
        length = 4 * n * size - (2 * n + 2) * CUT
        expected = (n - 1) * math.pi * math.hypot(extent, extent) / length
        self.assertAlmostEqual(jag.jaggedness(buf, extent, extent), expected, delta=0.1 * expected)

    def test_anti_aliased_disc_is_smooth(self):
        # A convex outline has no excess turning at any chord; 4x4 supersampled coverage keeps the
        # sub-pixel contour within a few hundredths of a pixel of the true circle.
        def coverage(x, y):
            hits = sum((x + (i + 0.5) / 4 - 40) ** 2 + (y + (j + 0.5) / 4 - 40) ** 2 <= 30 ** 2
                       for i in range(4) for j in range(4))
            return (0, 0, 0, round(255 * hits / 16))
        self.assertLess(jag.jaggedness(rgba(80, 80, coverage), 80, 80), 0.5)

    def test_finer_stairs_of_one_pixel_are_a_straight_edge(self):
        # 1 px stairs: marching squares joins the edge midpoints into one straight diagonal.
        buf, extent = staircase(30, 1)
        self.assertLess(jag.jaggedness(buf, extent, extent), 0.5)


class Staircase(unittest.TestCase):
    """Share of a hard reference's source-pixel staircase that the render keeps.

    A step `scale` px long reads as a real corner at the render-pixel strides `jaggedness` uses
    (issue #1353), so this walks strides of one and two *source* pixels, and divides by the
    reference's own score: what separates a kept staircase from genuine shape is not the render's
    turning, which a small gear's teeth also have, but how much of the source's it still carries.
    """

    @classmethod
    def setUpClass(cls):
        cls.stairs, cls.size = upscaled_disc(6, 6, 1)
        cls.smooth, _ = upscaled_disc(6, 6, 3)

    def test_a_render_that_is_the_staircase_keeps_all_of_it(self):
        self.assertAlmostEqual(jag.staircase(self.stairs, self.stairs, self.size, self.size, 6), 1.0, places=6)

    def test_a_smooth_render_of_a_staircase_keeps_little(self):
        self.assertLess(jag.staircase(self.smooth, self.stairs, self.size, self.size, 6), 0.2)

    def test_render_pixel_strides_miss_a_rounded_staircase_that_source_pixel_strides_keep(self):
        # The #1353 blind spot: the steps rounded a little, as a small `--smooth` leaves them.
        # jaggedness passes it; the staircase score still finds most of the source's steps.
        # Measured: jaggedness 10.5, staircase 0.57; the smooth disc keeps 0.0.
        rounded = box_blur_alpha(self.stairs, self.size, self.size, radius=2, passes=2)
        self.assertLess(jag.jaggedness(rounded, self.size, self.size), 15)
        self.assertGreater(jag.staircase(rounded, self.stairs, self.size, self.size, 6), 0.35)

    def test_a_reference_without_a_staircase_gives_nothing_to_keep(self):
        self.assertEqual(jag.staircase(self.smooth, self.smooth, self.size, self.size, 6), 0.0)
        empty = rgba(16, 16, lambda x, y: (0, 0, 0, 0))
        self.assertEqual(jag.staircase(empty, empty, 16, 16, 6), 0.0)

    def test_scale_below_two_has_no_source_pixel_stride(self):
        with self.assertRaises(ValueError):
            jag.staircase(self.stairs, self.stairs, self.size, self.size, 1)


if __name__ == "__main__":
    unittest.main()
