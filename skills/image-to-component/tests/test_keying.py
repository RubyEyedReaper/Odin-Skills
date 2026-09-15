"""keying: background detection and removal on straight-alpha RGBA buffers.

Expected values are derived by hand from the fixtures, never by calling the module a second way.
"""
from __future__ import annotations

import unittest

from ._fixtures import rgba, square
from scripts import keying

DARK = (10, 10, 10, 255)
GROUND = (200, 200, 200, 255)


def alpha_at(buf: bytes, width: int, x: int, y: int) -> int:
    return buf[(y * width + x) * 4 + 3]


class BorderBackground(unittest.TestCase):
    def test_transparent_border_means_nothing_to_key(self):
        # The incident: a transparent PNG's border median is (0,0,0), which keyed a dark glyph away.
        buf = square(20, 20, 6, 6, 8, colour=DARK)
        self.assertIsNone(keying.border_background(buf, 20, 20))

    def test_opaque_border_median_colour(self):
        buf = rgba(10, 10, lambda x, y: GROUND if (x + y) % 5 else (190, 210, 200, 255))
        self.assertEqual(keying.border_background(buf, 10, 10), (200, 200, 200))

    def test_mostly_opaque_border_with_a_few_clear_pixels_still_keys(self):
        buf = rgba(10, 10, lambda x, y: (0, 0, 0, 0) if (x, y) == (0, 0) else GROUND)
        self.assertEqual(keying.border_background(buf, 10, 10), (200, 200, 200))


class Keying(unittest.TestCase):
    def setUp(self):
        # 9x9 ground, a 5x5 dark ring at 2..6 whose centre (4,4) is ground-coloured.
        def px(x, y):
            ring = 2 <= x <= 6 and 2 <= y <= 6 and (x, y) != (4, 4)
            return DARK if ring else GROUND
        self.buf = rgba(9, 9, px)

    def test_flood_keys_edge_connected_ground_only(self):
        out = keying.key_flood(self.buf, 9, 9, (200, 200, 200), 40)
        self.assertEqual(alpha_at(out, 9, 0, 0), 0)
        self.assertEqual(alpha_at(out, 9, 2, 2), 255)
        self.assertEqual(alpha_at(out, 9, 4, 4), 255)  # enclosed: flood cannot reach it

    def test_global_keys_enclosed_holes_too(self):
        out = keying.key_global(self.buf, 9, 9, (200, 200, 200), 40)
        self.assertEqual(alpha_at(out, 9, 4, 4), 0)
        self.assertEqual(alpha_at(out, 9, 2, 2), 255)

    def test_keying_keeps_rgb_and_input_untouched(self):
        out = keying.key_global(self.buf, 9, 9, (200, 200, 200), 40)
        self.assertEqual(out[0:3], bytes((200, 200, 200)))
        self.assertEqual(alpha_at(self.buf, 9, 0, 0), 255)


def grey_row(values):
    return rgba(len(values), 1, lambda x, y: (values[x], values[x], values[x], 255))


class SoftMatte(unittest.TestCase):
    """Alpha across the keyed boundary follows colour distance, so a blurred edge sits at its middle."""

    def matte(self, values, tolerance=40):
        buf = grey_row(values)
        keyed = keying.key_flood(buf, len(values), 1, (0, 0, 0), tolerance)
        out = keying.soft_matte(buf, keyed, len(values), 1, (0, 0, 0), tolerance)
        return [alpha_at(out, len(values), x, 0) for x in range(len(values))]

    def test_blurred_ramp_alpha_is_distance_over_local_subject_distance(self):
        # Ground 0, subject 200, ramp 50/100/150. Within 3 px of the keyed ground each ramp pixel
        # takes d/200: 50 -> 63.75 -> 64, 100 -> 127.5 -> 128, 150 -> 191.25 -> 191. Pixel 6 is 4 px
        # from the ground and keeps 255; the ground keeps 0.
        alphas = self.matte([0, 0, 0, 50, 100, 150, 200, 200, 200, 200])
        self.assertEqual(alphas, [0, 0, 0, 64, 128, 191, 255, 255, 255, 255])

    def test_hard_key_would_have_made_the_whole_ramp_opaque(self):
        keyed = keying.key_flood(grey_row([0, 0, 0, 50, 100, 150, 200]), 7, 1, (0, 0, 0), 40)
        self.assertEqual([alpha_at(keyed, 7, x, 0) for x in range(7)], [0, 0, 0, 255, 255, 255, 255])

    def test_ground_noise_floor_is_subtracted(self):
        # Keyed ground reads 20 at its median, so 20 is zero alpha: (110-20)/(200-20) = 0.5 -> 128.
        alphas = self.matte([20, 0, 20, 20, 110, 200, 200, 200, 200])
        self.assertEqual(alphas[:5], [0, 0, 0, 0, 128])

    def test_global_key_mattes_every_pixel_by_coverage(self):
        # --key global has no enclosed detail to protect, so alpha is coverage everywhere: a pixel
        # halfway to the subject's colour is about half covered, however far it is from the ground.
        # Subject distances 200 (x9) and 100 (x1): the peak is 200, floor 0. Coverage 0.5 is lifted
        # to the power COVERAGE_GAMMA, so it lands just under the 128 cut: 255 * 0.5 ** 1.15 = 115.
        values = [0, 0, 0, 200, 200, 200, 200, 100, 200, 200, 200, 200, 200]
        buf = grey_row(values)
        keyed = keying.key_global(buf, len(values), 1, (0, 0, 0), 40)
        out = keying.soft_matte(buf, keyed, len(values), 1, (0, 0, 0), 40, key="global")
        self.assertEqual(alpha_at(out, len(values), 7, 0), 115)
        banded = keying.soft_matte(buf, keyed, len(values), 1, (0, 0, 0), 40)
        self.assertEqual(alpha_at(banded, len(values), 7, 0), 255)

    def test_global_peak_is_the_near_maximum_subject_distance(self):
        # 49 subject pixels at distance 100 and one at 200. A 95th-percentile peak reads 100 and calls
        # the whole dim body fully covered; the 99th reads 200, so a glow at half the stroke's
        # brightness is half covered instead of fattening the stroke.
        values = [0] * 10 + [100] * 49 + [200]
        buf = grey_row(values)
        keyed = keying.key_global(buf, len(values), 1, (0, 0, 0), 40)
        out = keying.soft_matte(buf, keyed, len(values), 1, (0, 0, 0), 40, key="global")
        self.assertEqual(alpha_at(out, len(values), 20, 0), 115)

    def test_enclosed_ground_coloured_detail_stays_opaque(self):
        # Flood keying leaves the ring's ground-coloured centre opaque; it is within 3 px of the
        # keyed outside, but it is not background, and soft matting must not hollow it out.
        def px(x, y):
            ring = 2 <= x <= 6 and 2 <= y <= 6 and (x, y) != (4, 4)
            return DARK if ring else GROUND
        buf = rgba(9, 9, px)
        keyed = keying.key_flood(buf, 9, 9, (200, 200, 200), 40)
        out = keying.soft_matte(buf, keyed, 9, 9, (200, 200, 200), 40)
        self.assertEqual(alpha_at(out, 9, 4, 4), 255)
        self.assertEqual(alpha_at(out, 9, 0, 0), 0)


class SharpenAlpha(unittest.TestCase):
    """Unsharp masking of alpha: a + amount·(a − blurred), clamped to 0–255."""

    def test_a_half_closed_hole_is_pushed_back_below_the_cut(self):
        # A blurred hole's centre at 180 among a local mean of 230 reads as covered (≥ 128); at
        # amount 2 it becomes 180 + 2·(180 − 230) = 80, open again.
        self.assertEqual(keying.sharpen_alpha(bytes([180]), bytes([230]), 2.0), bytes([80]))

    def test_the_result_is_clamped(self):
        self.assertEqual(keying.sharpen_alpha(bytes([250, 10]), bytes([200, 60]), 2.0), bytes([255, 0]))

    def test_flat_alpha_and_amount_zero_are_unchanged(self):
        self.assertEqual(keying.sharpen_alpha(bytes([90, 200]), bytes([90, 200]), 2.0), bytes([90, 200]))
        self.assertEqual(keying.sharpen_alpha(bytes([90, 200]), bytes([10, 10]), 0.0), bytes([90, 200]))

    def test_mismatched_lengths_are_refused(self):
        with self.assertRaises(ValueError):
            keying.sharpen_alpha(bytes([1, 2]), bytes([1]), 2.0)


if __name__ == "__main__":
    unittest.main()
