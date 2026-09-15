"""autogrid: the --auto search's prep rules, its bounded grid, and how a winner is chosen."""
from __future__ import annotations

import unittest

from ._fixtures import SKILL_DIR  # noqa: F401  (puts the skill on sys.path)
from scripts import autogrid, edges


def _rgba(alphas: list[list[int]]) -> tuple[bytes, int, int]:
    height, width = len(alphas), len(alphas[0])
    return bytes(v for row in alphas for a in row for v in (255, 255, 255, a)), width, height


def _result(nbytes: int, failures=(), check=(), tier=0):
    return {"bytes": nbytes, "check": list(check), "tier": tier,
            "qa": {"pass": not failures, "failures": list(failures),
                   "iou": 0.90 if "iou" in failures else 0.99, "edge_f1": 0.95, "mae": 3.0,
                   "jaggedness": 2.0, "staircase": None,
                   "thresholds": {"iou": 0.95, "edge_f1": 0.80, "mae": 12.0, "jaggedness": 15.0, "staircase": 0.35}}}


class EdgeRamp(unittest.TestCase):
    def test_hard_edge_has_no_ramp(self):
        buf, w, h = _rgba([[0, 0, 255, 255, 255, 0, 0]] * 3)
        self.assertEqual(edges.edge_ramp(buf, w, h), 0.0)

    def test_blurred_edge_is_wider_than_an_antialiased_one(self):
        crisp, w, h = _rgba([[0, 0, 128, 255, 255, 128, 0, 0, 0]] * 3)
        blurred, _, _ = _rgba([[0, 60, 120, 200, 255, 200, 120, 60, 0]] * 3)
        self.assertGreater(edges.edge_ramp(blurred, w, h), edges.edge_ramp(crisp, w, h))
        self.assertGreaterEqual(edges.edge_ramp(blurred, w, h), autogrid.BLURRED_RAMP)
        self.assertLess(edges.edge_ramp(crisp, w, h), autogrid.BLURRED_RAMP)

    def test_no_boundary_is_undetermined_not_zero(self):
        buf, w, h = _rgba([[255, 255], [255, 255]])
        self.assertIsNone(edges.edge_ramp(buf, w, h))


class DerivePrep(unittest.TestCase):
    def test_blurred_glyph_is_sharpened(self):
        prep = autogrid.derive_prep(mono=True, ramp=2.0)
        self.assertEqual(prep["sharpen"], autogrid.SHARPEN_RADIUS)
        self.assertEqual((prep["key"], prep["matte"]), ("global", "soft"))

    def test_clean_or_hard_glyph_is_not_sharpened(self):
        self.assertEqual(autogrid.derive_prep(mono=True, ramp=0.7)["sharpen"], 0)
        self.assertEqual(autogrid.derive_prep(mono=True, ramp=0.0)["sharpen"], 0)
        self.assertEqual(autogrid.derive_prep(mono=True, ramp=None)["sharpen"], 0)

    def test_colour_keeps_flood_key_and_is_never_sharpened(self):
        prep = autogrid.derive_prep(mono=False, ramp=3.0)
        self.assertEqual((prep["key"], prep["sharpen"]), ("flood", 0))


class Grid(unittest.TestCase):
    def test_grid_is_deterministic_and_bounded(self):
        for kind in ("icon", "logo", "illustration"):
            for mono in (True, False):
                grid = autogrid.candidates(kind, mono, size=(20, 20))
                self.assertEqual(grid, autogrid.candidates(kind, mono, size=(20, 20)))
                self.assertLessEqual(len(grid), autogrid.MAX_CANDIDATES)
                self.assertEqual(len({repr(c) for c in grid}), len(grid), "a candidate is repeated")

    def test_glyph_grid_varies_smoothing_and_starts_at_auto(self):
        grid = autogrid.candidates("icon", True, size=(52, 44))
        self.assertEqual(grid[0]["smooth"], "auto")
        self.assertGreater(len({c["smooth"] for c in grid}), 1)

    def test_small_glyph_also_tries_a_larger_scale(self):
        # A 1-2 px stroke at x8 is 8-16 render px: the spline fit's error is a tenth of it, and IoU fails.
        small = {c["scale"] for c in autogrid.candidates("icon", True, size=(21, 18))}
        large = {c["scale"] for c in autogrid.candidates("icon", True, size=(52, 44))}
        self.assertEqual(large, {autogrid.GLYPH_SCALE})
        self.assertEqual(small, {autogrid.GLYPH_SCALE, autogrid.SMALL_GLYPH_SCALE})

    def test_smoothing_follows_the_candidate_scale(self):
        grid = autogrid.candidates("icon", True, size=(21, 18))
        at16 = [c["smooth"] for c in grid if c["scale"] == autogrid.SMALL_GLYPH_SCALE]
        self.assertEqual(at16, ["auto", "9", "3", "1"])

    def test_colour_grid_varies_palette_and_speckle(self):
        grid = autogrid.candidates("logo", False, size=(132, 160))
        self.assertGreater(len({c["colors"] for c in grid}), 1)
        self.assertGreater(len({c["sets"] for c in grid}), 1)

    def test_every_colour_setting_is_tried_with_and_without_region_smoothing(self):
        grid = autogrid.candidates("logo", False, size=(60, 70))
        smoothed = [c for c in grid if c["smooth"] != "auto"]
        plain = [c for c in grid if c["smooth"] == "auto"]
        self.assertEqual(len(smoothed), len(plain))
        for c in smoothed:
            self.assertEqual(float(c["smooth"]), autogrid.REGION_RADIUS_PER_SCALE * c["scale"])
            self.assertEqual(c["tier"], 0)
        self.assertTrue(all(c["tier"] == 1 for c in plain))

    def test_glyph_candidates_share_one_tier(self):
        self.assertEqual({c["tier"] for c in autogrid.candidates("icon", True, size=(21, 18))}, {0})

    def test_small_colour_mark_also_tries_larger_scales(self):
        small = {c["scale"] for c in autogrid.candidates("logo", False, size=(53, 64))}
        large = {c["scale"] for c in autogrid.candidates("logo", False, size=(132, 160))}
        self.assertEqual(large, {autogrid.COLOUR_SCALE["logo"]})
        self.assertEqual(small, {autogrid.COLOUR_SCALE["logo"]} | {s for s, _, _ in autogrid.SMALL_COLOUR_EXTRA})

    def test_args_round_trip_to_i2c_flags(self):
        prep = autogrid.derive_prep(mono=False, ramp=1.0)
        args = autogrid.to_args(prep, {"smooth": "auto", "scale": 2, "colors": 48, "sets": ("filter_speckle=7",)})
        self.assertIn("--colors", args)
        self.assertEqual(args[args.index("--colors") + 1], "48")
        self.assertEqual(args[args.index("--set") + 1], "filter_speckle=7")
        self.assertNotIn("--sharpen", args)  # zero is the default; the recorded flags stay minimal


class Select(unittest.TestCase):
    def test_smallest_passing_candidate_wins(self):
        results = [_result(3000), _result(2000, failures=["iou"]), _result(2500), _result(2600)]
        chosen, _ = autogrid.select(results)
        self.assertEqual(chosen, 2)

    def test_a_budget_finding_is_not_a_pass(self):
        results = [_result(900, check=["budget-paths"]), _result(1500)]
        self.assertEqual(autogrid.select(results)[0], 1)

    def test_a_passing_preferred_tier_beats_a_smaller_fallback(self):
        # Region smoothing costs bytes; "smallest" would never pick it, so it is tier 0 and wins when it passes.
        results = [_result(2000, tier=1), _result(2600, tier=0), _result(2400, tier=0, failures=["mae"])]
        self.assertEqual(autogrid.select(results)[0], 1)

    def test_the_fallback_tier_is_chosen_when_no_preferred_candidate_passes(self):
        results = [_result(2000, tier=1), _result(2600, tier=0, failures=["mae"])]
        self.assertEqual(autogrid.select(results)[0], 0)

    def test_equal_size_keeps_grid_order(self):
        self.assertEqual(autogrid.select([_result(1000), _result(1000)])[0], 0)

    def test_nothing_passes_names_the_nearest_miss(self):
        far = _result(1000, failures=["iou", "mae"])
        near = _result(1200, failures=["iou"])
        near["qa"]["iou"] = 0.949
        chosen, nearest = autogrid.select([far, near])
        self.assertIsNone(chosen)
        self.assertEqual(nearest, 1)

    def test_empty_grid_is_refused_rather_than_chosen(self):
        with self.assertRaises(ValueError):
            autogrid.select([])


class Report(unittest.TestCase):
    def _report(self):
        results = [dict(_result(2000, failures=["iou"]), flags=["--scale", "8"]),
                   dict(_result(1500), flags=["--scale", "16"])]
        prep = autogrid.derive_prep(True, 0.7)
        return autogrid.report(results, {"edge": "soft", "ramp": 0.7, "prep": prep}, bound_seconds=300)

    def test_the_report_is_deterministic_and_carries_no_wall_clock(self):
        # qa.json is a committed golden: a timing field dirties it on every rerun with no change.
        report = self._report()
        self.assertEqual(report, self._report())
        self.assertNotIn("seconds", report)
        self.assertEqual(report["bound_seconds"], 300)

    def test_the_report_names_the_winner_and_its_flags(self):
        report = self._report()
        self.assertEqual((report["chosen"], report["nearest"]), (1, 1))
        self.assertEqual(report["flags"], ["--scale", "16"])
        self.assertEqual([g["pass"] for g in report["grid"]], [False, True])


if __name__ == "__main__":
    unittest.main()
