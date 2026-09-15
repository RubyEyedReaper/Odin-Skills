"""features: a small feature the reference has — a dot, a hole — must survive into the render."""
from __future__ import annotations

import os
import unittest
import zlib

from ._fixtures import SKILL_DIR, rgba  # noqa: F401  (puts the skill on sys.path)
from scripts import diffmetric, features

RED, WHITE, CLEAR = (225, 29, 46), (250, 250, 250), (0, 0, 0, 0)


def _alert(scale: int, dot: bool = True, bar: bool = True, specks: tuple = ()) -> tuple[bytes, int]:
    """A 36 px red disc carrying a white "!" — bar and a 3 px dot — drawn anti-aliased at `scale`.

    Shapes are in source px and supersampled 4x, the way an upscaled anti-aliased source looks. `specks`
    are (x, y) source pixels painted white: single-pixel noise, which is not a feature.
    """
    size = 36 * scale
    samples = 4

    def inside(sx: float, sy: float) -> tuple[int, int, int] | None:
        if (sx - 18) ** 2 + (sy - 18) ** 2 > 16 ** 2:
            return None
        if bar and 16.5 <= sx <= 19.5 and 7 <= sy <= 21:
            return WHITE
        if dot and 16.5 <= sx <= 19.5 and 24 <= sy <= 27:
            return WHITE
        if any(int(sx) == x and int(sy) == y for x, y in specks):
            return WHITE
        return RED

    def px(x, y):
        hits = [inside((x + (i + 0.5) / samples) / scale, (y + (j + 0.5) / samples) / scale)
                for i in range(samples) for j in range(samples)]
        solid = [h for h in hits if h is not None]
        if not solid:
            return CLEAR
        colour = tuple(round(sum(c[k] for c in solid) / len(solid)) for k in range(3))
        return colour + (round(255 * len(solid) / len(hits)),)

    return rgba(size, size, px), size


def _frame(scale: int, hole: bool) -> tuple[bytes, int]:
    """A 14 px black square glyph with a 3 px square hole in its middle, aliased, at `scale`."""
    size = 14 * scale

    def px(x, y):
        sx, sy = x // scale, y // scale
        if not (1 <= sx <= 12 and 1 <= sy <= 12):
            return CLEAR
        if hole and 6 <= sx <= 8 and 6 <= sy <= 8:
            return CLEAR
        return (0, 0, 0, 255)

    return rgba(size, size, px), size


class ColourFeatures(unittest.TestCase):
    def test_a_render_that_drops_the_dot_is_refused_by_name(self):
        reference, size = _alert(2)
        dropped, _ = _alert(2, dot=False)
        result = features.recall(reference, dropped, size, size, scale=2)
        self.assertLess(result["features"], diffmetric.DEFAULT_THRESHOLDS["features"])
        self.assertEqual(len(result["lost"]), 1)
        scored = diffmetric.compare(reference, dropped, size, size, scale=2)
        self.assertIn("features", scored["failures"])

    def test_a_faithful_render_keeps_every_feature(self):
        reference, size = _alert(2)
        result = features.recall(reference, reference, size, size, scale=2)
        self.assertEqual(result["lost"], [])
        self.assertGreaterEqual(result["features"], diffmetric.DEFAULT_THRESHOLDS["features"])

    def test_noise_specks_below_the_minimum_area_may_be_removed(self):
        noisy, size = _alert(2, specks=((10, 14), (25, 22), (13, 28)))
        clean, _ = _alert(2)
        result = features.recall(noisy, clean, size, size, scale=2)
        self.assertEqual(result["lost"], [])

    def test_a_traced_colour_near_the_feature_still_keeps_it(self):
        # A flat trace replaces a shaded region with one palette colour; that is mae's to judge, not a lost feature.
        reference, size = _alert(2)
        shifted = bytes(min(255, v + 30) if i % 4 == 2 else v for i, v in enumerate(reference))
        self.assertEqual(features.recall(reference, shifted, size, size, scale=2)["lost"], [])

    def test_a_feature_too_small_a_share_of_the_subject_is_not_counted(self):
        # A 3 px mark on a 60 px panel is 0.25 % of what is visible: texture at the size the asset renders.
        def panel(mark):
            return rgba(120, 120, lambda x, y: WHITE + (255,) if mark and 60 <= x < 66 and 60 <= y < 66 else RED + (255,))
        self.assertEqual(features.recall(panel(True), panel(False), 120, 120, scale=2)["lost"], [])
        # The same mark on a 12 px panel is 6 %, and losing it is refused.
        small = rgba(24, 24, lambda x, y: WHITE + (255,) if 10 <= x < 16 and 10 <= y < 16 else RED + (255,))
        self.assertTrue(features.recall(small, rgba(24, 24, lambda x, y: RED + (255,)), 24, 24, scale=2)["lost"])

    def test_a_dot_is_lost_at_any_scale(self):
        for scale in (2, 4):
            reference, size = _alert(scale)
            dropped, _ = _alert(scale, dot=False)
            self.assertTrue(features.recall(reference, dropped, size, size, scale=scale)["lost"], f"scale {scale}")


class HoleFeatures(unittest.TestCase):
    def test_a_filled_hole_is_refused(self):
        reference, size = _frame(4, hole=True)
        filled, _ = _frame(4, hole=False)
        result = features.recall(reference, filled, size, size, scale=4)
        self.assertEqual(len(result["lost"]), 1)
        self.assertEqual(result["lost"][0]["colour"], None)

    def test_the_ground_around_the_glyph_is_not_a_feature(self):
        reference, size = _frame(4, hole=False)
        self.assertEqual(features.recall(reference, reference, size, size, scale=4)["counted"], 1)

    def test_a_hole_shifted_by_a_render_pixel_is_kept(self):
        reference, size = _frame(4, hole=True)
        shifted = rgba(size, size, lambda x, y: tuple(reference[(y * size + max(x - 1, 0)) * 4:][:4]))
        self.assertEqual(features.recall(reference, shifted, size, size, scale=4)["lost"], [])


class HeldOutAlertMark(unittest.TestCase):
    """#1392 as it shipped: `--auto`'s smallest passing AlertMark, rendered, against its prepared reference.

    Frozen RGBA (74x70, zlib) from `evals/heldout/out/AlertMark.svg` at 3e85ad9f, which passed every
    other bar — iou 0.9785, mae 11.79, edge_f1 0.905 — with the "!" dot gone.
    """

    def _load(self, name: str) -> bytes:
        with open(os.path.join(SKILL_DIR, "tests", "fixtures", f"alert-mark.{name}.rgba.z"), "rb") as fh:
            return zlib.decompress(fh.read())

    def test_the_render_that_shipped_without_its_dot_is_refused(self):
        result = diffmetric.compare(self._load("reference"), self._load("render-without-dot"), 74, 70, scale=2)
        self.assertEqual(result["failures"], ["features"])
        self.assertEqual(len(result["lost_features"]), 1)

    def test_the_reference_keeps_its_own_features(self):
        reference = self._load("reference")
        self.assertEqual(features.recall(reference, reference, 74, 70, scale=2)["lost"], [])


class Contract(unittest.TestCase):
    def test_nothing_to_count_is_a_pass(self):
        empty = bytes(4 * 16)
        self.assertEqual(features.recall(empty, empty, 4, 4, scale=1)["features"], 1.0)

    def test_sizes_must_match(self):
        with self.assertRaises(ValueError):
            features.recall(bytes(16), bytes(12), 2, 2, scale=1)


if __name__ == "__main__":
    unittest.main()
