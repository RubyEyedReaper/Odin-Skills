"""scale: the declared scale system a replacement is fitted to, and the transform that fits it."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from ._fixtures import SKILL_DIR
from .test_library import mask
from scripts import scale


class ScalesFileTest(unittest.TestCase):
    def test_the_shipped_scales_file_declares_every_scale(self):
        scales = scale.load(os.path.join(SKILL_DIR, "scripts", "scales.json"))
        self.assertEqual(scales["icon_px"], [12, 16, 20, 24, 32, 40, 48])
        self.assertEqual(scales["radius_px"], [0, 2, 4, 6, 8, 12, 16, 24, "pill"])
        self.assertEqual((scales["spacing_base_px"], scales["border_px"]), (4, [1, 1.5, 2]))

    def test_a_scales_file_missing_a_scale_is_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"icon_px": [16], "snap_tolerance": 0.1}, fh)
        self.addCleanup(os.unlink, fh.name)
        with self.assertRaisesRegex(ValueError, "radius_px"):
            scale.load(fh.name)


class SnapTest(unittest.TestCase):
    def test_a_value_within_tolerance_snaps_to_the_nearest_step(self):
        self.assertEqual(scale.snap(22.6, [16, 20, 24, 32], 0.1),
                         {"measured": 22.6, "step": 24, "value": 24})

    def test_a_value_off_every_step_is_kept_as_measured_and_says_so(self):
        self.assertEqual(scale.snap(28.0, [16, 20, 24, 32], 0.1),
                         {"measured": 28.0, "step": None, "value": 28.0})

    def test_non_numeric_steps_are_not_snap_targets(self):
        self.assertEqual(scale.snap(8.2, [0, 8, "pill"], 0.1)["step"], 8)


class StrokeTest(unittest.TestCase):
    def test_a_thicker_stroke_of_the_same_box_has_a_larger_ratio(self):
        thin, w, h = mask(["##########"] + ["#........#"] * 8 + ["##########"])
        thick, _, _ = mask(["##########"] * 2 + ["##......##"] * 6 + ["##########"] * 2)
        self.assertLess(scale.stroke_ratio(thin, w, h), scale.stroke_ratio(thick, w, h))

    def test_a_one_pixel_frame_measures_about_one_pixel_over_its_box(self):
        frame, w, h = mask(["##########"] + ["#........#"] * 8 + ["##########"])
        self.assertAlmostEqual(scale.stroke_ratio(frame, w, h), 1 / 10, delta=0.03)

    def test_the_nearest_measured_weight_is_chosen(self):
        self.assertEqual(scale.nearest_weight(0.11, {300: 0.07, 400: 0.09, 500: 0.12}), 500)


class FitTest(unittest.TestCase):
    ICON = {"cx": 480.0, "cy": -480.0, "r": 200.0}

    def test_the_transform_puts_the_icon_centroid_on_the_source_centroid_at_the_source_radius(self):
        k, ox, oy = scale.fit(self.ICON, (10.0, 12.0, 5.0))
        self.assertEqual(k, 5.0 / 200.0)
        self.assertAlmostEqual(ox + 480.0 * k, 10.0)
        self.assertAlmostEqual(oy + -480.0 * k, 12.0)

    def test_the_canvas_view_box_maps_px_back_to_icon_units(self):
        k, ox, oy = scale.fit(self.ICON, (10.0, 12.0, 5.0))
        x, y, w, h = scale.canvas_view_box((k, ox, oy), 20, 24, pad=1)
        # pixel -1 (the pad) is icon unit (-1 - ox) / k; the canvas is (20 + 2) px wide.
        self.assertAlmostEqual(x, (-1 - ox) / k)
        self.assertAlmostEqual(w, 22 / k)
        self.assertAlmostEqual(y * k + oy, -1)
        self.assertAlmostEqual(h, 26 / k)

    def test_the_rendered_size_is_the_view_box_width_at_the_fitted_scale(self):
        self.assertAlmostEqual(scale.rendered_px((0.025, 0.0, 0.0), (0.0, -960.0, 960.0, 960.0)), 24.0)


if __name__ == "__main__":
    unittest.main()
