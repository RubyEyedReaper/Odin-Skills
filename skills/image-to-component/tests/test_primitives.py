"""primitives: is this asset a container shape, which family, and may it be emitted as one?"""
from __future__ import annotations

import math
import unittest

from ._fixtures import SKILL_DIR  # noqa: F401  (puts the skill dir on sys.path)
from .test_library import mask
from scripts import primitives


def disc(size: int, radius: float) -> tuple[bytes, int, int]:
    """An anti-aliased disc centred in a `size`x`size` alpha buffer."""
    c = size / 2
    out = bytearray()
    for y in range(size):
        for x in range(size):
            hits = sum((x + (i + 0.5) / 4 - c) ** 2 + (y + (j + 0.5) / 4 - c) ** 2 <= radius ** 2
                       for i in range(4) for j in range(4))
            out.append(round(255 * hits / 16))
    return bytes(out), size, size


def box(size: int, w: float, h: float, r: float = 0.0) -> tuple[bytes, int, int]:
    """An anti-aliased rounded rect of `w`x`h` with corner radius `r`, centred in `size`x`size`."""
    cx = cy = size / 2
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    r = min(r, w / 2, h / 2)

    def inside(px: float, py: float) -> bool:
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            return False
        qx = min(max(px, x0 + r), x1 - r)
        qy = min(max(py, y0 + r), y1 - r)
        return (px - qx) ** 2 + (py - qy) ** 2 <= r * r + 1e-9

    out = bytearray()
    for y in range(size):
        for x in range(size):
            hits = sum(inside(x + (i + 0.5) / 4, y + (j + 0.5) / 4) for i in range(4) for j in range(4))
            out.append(round(255 * hits / 16))
    return bytes(out), size, size


class MomentsTest(unittest.TestCase):
    def test_a_centred_disc_reports_its_centre_and_its_area(self):
        alpha, w, h = disc(24, 8.0)
        m = primitives.moments(alpha, w, h)
        self.assertAlmostEqual(m["cx"], 12.0, delta=0.15)
        self.assertAlmostEqual(m["cy"], 12.0, delta=0.15)
        self.assertAlmostEqual(m["area"], math.pi * 64, delta=math.pi * 64 * 0.03)

    def test_the_box_is_the_visible_extent_not_the_buffer(self):
        alpha, w, h = box(24, 10.0, 6.0)
        m = primitives.moments(alpha, w, h)
        self.assertAlmostEqual(m["w"], 10.0, delta=1.0)
        self.assertAlmostEqual(m["h"], 6.0, delta=1.0)

    def test_an_empty_buffer_has_no_box(self):
        self.assertIsNone(primitives.moments(bytes(64), 8, 8))


class CandidateTest(unittest.TestCase):
    PARAMS = {"hull_fill": 0.9, "bbox_fill": 0.6, "symmetry": 0.0, "min_px": 0}

    def test_a_filled_disc_is_a_candidate(self):
        alpha, w, h = disc(24, 8.0)
        self.assertTrue(primitives.candidate(alpha, w, h, self.PARAMS)["ok"])

    def test_two_separate_blobs_are_refused_as_multi_component(self):
        alpha, w, h = mask(["##..##",
                            "##..##",
                            "......",
                            "......"])
        self.assertEqual(primitives.candidate(alpha, w, h, self.PARAMS)["reason"], "components")

    def test_a_ring_is_refused_because_its_hole_is_unreachable_from_the_border(self):
        alpha, w, h = mask(["......",
                            ".####.",
                            ".#..#.",
                            ".#..#.",
                            ".####.",
                            "......"])
        self.assertEqual(primitives.candidate(alpha, w, h, self.PARAMS)["reason"], "hole")

    def test_a_cross_is_refused_as_not_convex(self):
        alpha, w, h = mask(["..##..",
                            "..##..",
                            "######",
                            "######",
                            "..##..",
                            "..##.."])
        self.assertEqual(primitives.candidate(alpha, w, h, self.PARAMS)["reason"], "convexity")

    def test_a_thin_diagonal_bar_is_refused_for_filling_too_little_of_its_box(self):
        alpha, w, h = mask(["#.....",
                            ".#....",
                            "..#...",
                            "...#..",
                            "....#.",
                            ".....#"])
        reason = primitives.candidate(alpha, w, h, self.PARAMS)["reason"]
        self.assertIn(reason, ("convexity", "bbox-fill"))

    def test_a_filled_square_touching_the_border_still_has_no_hole(self):
        alpha, w, h = mask(["####", "####", "####", "####"])
        self.assertTrue(primitives.candidate(alpha, w, h, self.PARAMS)["ok"])

    def test_a_tile_with_a_glyph_on_it_is_refused_as_composite(self):
        """The alert mark and the old Facebook square are a rounded tile with a knocked-out glyph.
        Keying leaves some of them with no interior hole at all, so they clear predicates 1 and 2
        and then fit a rounded rect at 0.88 — a wrong acceptance that drops the glyph and that no
        threshold catches, because the container really is a rounded rect. The caller reads the
        second flat colour and says so; this predicate is what turns that into a refusal."""
        alpha, w, h = mask(["####", "####", "####", "####"])
        self.assertEqual(primitives.candidate(alpha, w, h, self.PARAMS, composite=True)["reason"],
                         "composite")
        self.assertTrue(primitives.candidate(alpha, w, h, self.PARAMS, composite=False)["ok"])

    def test_every_admissible_family_is_symmetric_about_both_axes_of_its_own_box(self):
        for alpha, w, h in (disc(24, 8.0), box(24, 12.0, 8.0), box(32, 20.0, 14.0, 5.0)):
            self.assertGreater(primitives.symmetry(alpha, w, h), 0.97)

    def test_a_shape_with_a_bulb_at_one_end_is_not_symmetric(self):
        """A thermometer glyph keyed at 11x15 px is a 5x11 blob: wide at the bulb, narrow at the
        stem. It is convex, fills its box and has no hole, and it fits an ellipse at 0.72 — a wrong
        acceptance on the held-out split. What separates it from a real ellipse is not its size but
        that every admissible family is mirror-symmetric about both axes and a glyph is not."""
        alpha, w, h = mask(["..##..",
                            "..##..",
                            ".####.",
                            ".####.",
                            "######",
                            "######"])
        self.assertLess(primitives.symmetry(alpha, w, h), 0.8)

    def test_asymmetry_is_refused_by_name(self):
        alpha, w, h = mask(["..##..", "..##..", ".####.", ".####.", "######", "######"])
        params = {**self.PARAMS, "symmetry": 0.9, "hull_fill": 0.0, "bbox_fill": 0.0}
        self.assertEqual(primitives.candidate(alpha, w, h, params)["reason"], "asymmetry")

    def test_a_shape_thinner_than_the_floor_is_refused_for_being_too_small_to_name(self):
        """Five names for one kind of object need pixels to separate them. Below the floor the eval
        shows near-zero correct acceptances and most of the wrong ones — the same refusal
        `--replace` makes with `auto_min_px`, for the same reason."""
        alpha, w, h = mask(["########", "########", "########"])
        params = {**self.PARAMS, "min_px": 6}
        self.assertEqual(primitives.candidate(alpha, w, h, params)["reason"], "too-small")
        self.assertTrue(primitives.candidate(alpha, w, h, {**params, "min_px": 3})["ok"])

    def test_a_solid_square_is_exactly_as_convex_as_its_own_hull(self):
        alpha, w, h = mask(["......", ".####.", ".####.", ".####.", ".####.", "......"])
        self.assertAlmostEqual(primitives.candidate(alpha, w, h, self.PARAMS)["hull_fill"], 1.0, delta=1e-9)

    def test_the_ratios_count_visible_pixels_on_both_sides(self):
        """Both ratios are area over area in the same units. Mixing the soft alpha sum over a
        visible-pixel hull reads a blurred disc as non-convex — it refused 86 of 92 ladder sources
        at 24 px and under, because blur shrinks the numerator while the hull keeps its size."""
        solid, w, h = mask(["......", ".####.", ".####.", ".####.", ".####.", "......"])
        half = bytes(160 if v else 0 for v in solid)   # every visible pixel at alpha 160, not 255
        self.assertAlmostEqual(primitives.candidate(half, w, h, self.PARAMS)["hull_fill"],
                               primitives.candidate(solid, w, h, self.PARAMS)["hull_fill"], delta=1e-9)
        self.assertAlmostEqual(primitives.candidate(half, w, h, self.PARAMS)["bbox_fill"],
                               primitives.candidate(solid, w, h, self.PARAMS)["bbox_fill"], delta=1e-9)


class FitTest(unittest.TestCase):
    def test_a_disc_fits_a_circle_at_its_centre_and_radius(self):
        alpha, w, h = disc(24, 8.0)
        fit = primitives.fit_family("circle", primitives.moments(alpha, w, h))
        self.assertAlmostEqual(fit["params"]["cx"], 12.0, delta=0.2)
        self.assertAlmostEqual(fit["params"]["r"], 8.0, delta=0.4)

    def test_a_plain_rect_fits_a_rect_at_its_box(self):
        alpha, w, h = box(24, 12.0, 8.0)
        fit = primitives.fit_family("rect", primitives.moments(alpha, w, h))
        self.assertAlmostEqual(fit["params"]["width"], 12.0, delta=0.6)
        self.assertAlmostEqual(fit["params"]["height"], 8.0, delta=0.6)

    def test_a_rounded_rect_recovers_its_corner_radius_from_the_area_it_removes(self):
        alpha, w, h = box(32, 20.0, 14.0, 5.0)
        fit = primitives.fit_family("rounded-rect", primitives.moments(alpha, w, h))
        self.assertAlmostEqual(fit["params"]["rx"], 5.0, delta=1.0)

    def test_a_rects_fitted_radius_is_zero_not_negative(self):
        alpha, w, h = box(24, 12.0, 8.0)
        fit = primitives.fit_family("rounded-rect", primitives.moments(alpha, w, h))
        self.assertGreaterEqual(fit["params"]["rx"], 0.0)
        self.assertLess(fit["params"]["rx"], 1.2)

    def test_a_pill_takes_half_its_short_side_whatever_the_area_says(self):
        alpha, w, h = box(32, 24.0, 10.0, 5.0)
        fit = primitives.fit_family("pill", primitives.moments(alpha, w, h))
        self.assertAlmostEqual(fit["params"]["rx"], fit["params"]["height"] / 2, delta=1e-9)

    def test_an_ellipse_takes_both_half_axes_from_the_box(self):
        alpha, w, h = box(32, 20.0, 12.0)
        fit = primitives.fit_family("ellipse", primitives.moments(alpha, w, h))
        self.assertAlmostEqual(fit["params"]["rx"] / fit["params"]["ry"], 20.0 / 12.0, delta=0.2)

    def test_a_scaled_box_keeps_its_centre_and_scales_its_area_by_the_square(self):
        """Blur widens the alpha-128 box, so every family is fitted a little too large — a 6 px-tall
        pill measured at 7 px is a fat stadium that loses to an ellipse fitted to the same box. The
        caller sweeps a few box scales per family, exactly as `replace_run` sweeps SCALE_STEPS, and
        the arithmetic is here so it is one implementation and testable without a renderer."""
        m = primitives.moments(*box(32, 20.0, 12.0))
        k = 0.9
        scaled = primitives.scaled(m, k)
        self.assertAlmostEqual(scaled["w"], m["w"] * k)
        self.assertAlmostEqual(scaled["h"], m["h"] * k)
        self.assertAlmostEqual(scaled["area"], m["area"] * k * k)
        self.assertAlmostEqual(scaled["x0"] + scaled["w"] / 2, m["x0"] + m["w"] / 2)
        self.assertAlmostEqual(scaled["y0"] + scaled["h"] / 2, m["y0"] + m["h"] / 2)

    def test_a_scale_of_one_changes_nothing(self):
        m = primitives.moments(*box(32, 20.0, 12.0))
        self.assertEqual(primitives.scaled(m, 1.0), m)

    def test_every_family_fits_and_names_itself(self):
        m = primitives.moments(*disc(24, 8.0))
        for family in primitives.FAMILIES:
            self.assertEqual(primitives.fit_family(family, m)["family"], family)


class SnapRadiusTest(unittest.TestCase):
    STEPS = [0, 2, 4, 6, 8, 12, 16, 24, "pill"]

    def test_a_radius_of_half_the_short_side_is_the_pill_step(self):
        self.assertEqual(primitives.snap_radius(5.0, self.STEPS, 0.125, 10.0)["step"], "pill")

    def test_a_radius_near_a_numeric_step_snaps_to_it(self):
        self.assertEqual(primitives.snap_radius(6.4, self.STEPS, 0.125, 40.0),
                         {"measured": 6.4, "step": 6, "value": 6})

    def test_a_radius_off_every_step_is_kept_as_measured_and_says_so(self):
        self.assertEqual(primitives.snap_radius(10.0, self.STEPS, 0.125, 40.0),
                         {"measured": 10.0, "step": None, "value": 10.0})

    def test_a_square_corner_snaps_to_zero(self):
        self.assertEqual(primitives.snap_radius(0.05, self.STEPS, 0.125, 40.0)["step"], 0)


class ElementTest(unittest.TestCase):
    def test_a_circle_is_emitted_as_a_circle_element(self):
        el = primitives.element({"family": "circle", "params": {"cx": 12.0, "cy": 12.0, "r": 8.0}})
        self.assertEqual(el, '<circle cx="12" cy="12" r="8"/>')

    def test_a_rect_carries_no_radius_attribute(self):
        el = primitives.element({"family": "rect",
                                 "params": {"x": 2.0, "y": 4.0, "width": 20.0, "height": 16.0}})
        self.assertEqual(el, '<rect x="2" y="4" width="20" height="16"/>')

    def test_a_rounded_rect_carries_its_radius(self):
        el = primitives.element({"family": "rounded-rect",
                                 "params": {"x": 2.0, "y": 4.0, "width": 20.0, "height": 16.0, "rx": 4.0}})
        self.assertEqual(el, '<rect x="2" y="4" width="20" height="16" rx="4"/>')

    def test_an_ellipse_carries_both_half_axes(self):
        el = primitives.element({"family": "ellipse",
                                 "params": {"cx": 10.0, "cy": 6.0, "rx": 10.0, "ry": 6.0}})
        self.assertEqual(el, '<ellipse cx="10" cy="6" rx="10" ry="6"/>')

    def test_the_svg_wraps_the_element_in_a_view_box_and_nothing_else(self):
        svg = primitives.svg({"family": "circle", "params": {"cx": 12.0, "cy": 12.0, "r": 8.0}}, (0, 0, 24, 24))
        self.assertEqual(svg, '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>')


class DeriveTest(unittest.TestCase):
    """Only two families are fitted and judged; the other three ARE those two at particular
    parameters, and deriving them removes the whole question of whether they tie.

    Fitting five independently made three of them compete with the shapes they are special cases
    of, and each got its own best box scale, so a pill and the rounded rect that IS that pill
    rendered at different sizes and failed to tie — measured, three wrong acceptances on the
    calibrate split, plus a 24 px squircle shipping as a square because rect and rounded-rect tied
    at 0.90. A name that is a special case is read off the parameters, never contested."""

    def test_the_two_fitted_families_are_the_general_cases(self):
        self.assertEqual(primitives.FITTED, ("rounded-rect", "ellipse"))

    def test_a_rounded_rect_with_no_radius_is_a_rect(self):
        fit = {"family": "rounded-rect", "params": {"x": 0, "y": 0, "width": 24, "height": 16, "rx": 0.2}}
        self.assertEqual(primitives.derive(fit, 0.125)["family"], "rect")

    def test_a_rounded_rect_at_half_its_short_side_is_a_pill(self):
        fit = {"family": "rounded-rect", "params": {"x": 0, "y": 0, "width": 24, "height": 16, "rx": 7.9}}
        self.assertEqual(primitives.derive(fit, 0.125)["family"], "pill")

    def test_a_rounded_rect_in_between_stays_a_rounded_rect(self):
        fit = {"family": "rounded-rect", "params": {"x": 0, "y": 0, "width": 24, "height": 16, "rx": 4.0}}
        self.assertEqual(primitives.derive(fit, 0.125)["family"], "rounded-rect")

    def test_an_ellipse_with_equal_axes_is_a_circle(self):
        fit = {"family": "ellipse", "params": {"cx": 12, "cy": 12, "rx": 8.0, "ry": 8.2}}
        derived = primitives.derive(fit, 0.125)
        self.assertEqual(derived["family"], "circle")
        self.assertIn("r", derived["params"])

    def test_an_ellipse_with_unequal_axes_stays_an_ellipse(self):
        fit = {"family": "ellipse", "params": {"cx": 12, "cy": 12, "rx": 12.0, "ry": 6.0}}
        self.assertEqual(primitives.derive(fit, 0.125)["family"], "ellipse")

    def test_a_derived_name_renders_the_same_shape_it_was_derived_from(self):
        """A pill emitted as `<rect rx>` and the rounded rect it came from are the same element."""
        fit = {"family": "rounded-rect", "params": {"x": 0, "y": 0, "width": 24, "height": 16, "rx": 8.0}}
        self.assertEqual(primitives.element(primitives.derive(fit, 0.125)), primitives.element(fit))


class SelectTest(unittest.TestCase):
    """The one implementation of "which family is emitted", so the caller building the pair margins
    and `decide` cannot disagree about which render is the named one."""

    def test_the_best_fitting_family_is_selected_when_nothing_ties_it(self):
        self.assertEqual(primitives.select({"circle": 0.93, "rect": 0.61, "ellipse": 0.70}, set()), "circle")

    def test_among_tied_families_the_one_with_fewest_parameters_wins(self):
        chosen = primitives.select({"rounded-rect": 0.94, "circle": 0.93, "rect": 0.61},
                                   {"circle", "rounded-rect"})
        self.assertEqual(chosen, "circle")

    def test_a_tie_that_does_not_include_the_leader_does_not_change_the_answer(self):
        chosen = primitives.select({"circle": 0.93, "rect": 0.61, "rounded-rect": 0.62}, {"rect", "rounded-rect"})
        self.assertEqual(chosen, "circle")


class DecideTest(unittest.TestCase):
    PARAMS = {"bar": 0.55, "margin": 0.08, "min_weight": 4}

    def test_the_best_family_wins_when_it_beats_every_adversary_by_the_margin(self):
        verdict = primitives.decide(
            fits={"circle": 0.93, "ellipse": 0.70, "rect": 0.61, "rounded-rect": 0.66, "pill": 0.69},
            pairs={"ellipse": (0.42, 30.0), "rect": (0.55, 60.0), "rounded-rect": (0.48, 40.0),
                   "pill": (0.40, 25.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual((verdict["family"], verdict["accepted"]), ("circle", True))
        self.assertEqual(verdict["reason"], "accepted")

    def test_a_best_fit_below_the_bar_is_refused_naming_the_bar(self):
        verdict = primitives.decide(
            fits={"circle": 0.40, "ellipse": 0.32, "rect": 0.30, "rounded-rect": 0.31, "pill": 0.33},
            pairs={"ellipse": (0.9, 50.0), "rect": (0.9, 50.0), "rounded-rect": (0.9, 50.0),
                   "pill": (0.9, 50.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "bar"))

    def test_an_adversary_the_source_does_not_side_against_refuses(self):
        verdict = primitives.decide(
            fits={"circle": 0.93, "ellipse": 0.91, "rect": 0.60, "rounded-rect": 0.62, "pill": 0.64},
            pairs={"ellipse": (0.02, 30.0), "rect": (0.5, 50.0), "rounded-rect": (0.5, 50.0),
                   "pill": (0.5, 50.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "adversary"))
        self.assertEqual(verdict["runner_up"], "ellipse")

    def test_an_adversary_with_too_little_disagreement_to_judge_on_refuses(self):
        verdict = primitives.decide(
            fits={"circle": 0.93, "ellipse": 0.70, "rect": 0.61, "rounded-rect": 0.66, "pill": 0.69},
            pairs={"ellipse": (0.9, 1.5), "rect": (0.5, 50.0), "rounded-rect": (0.5, 50.0),
                   "pill": (0.5, 50.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "indistinguishable"))

    def test_a_tied_family_is_not_an_adversary_and_the_simpler_one_is_emitted(self):
        # A rounded rect fitted to a disc renders the same pixels as the circle: not an adversary,
        # and `circle` carries one parameter where `rounded-rect` carries three.
        verdict = primitives.decide(
            fits={"circle": 0.93, "rounded-rect": 0.94, "ellipse": 0.70, "rect": 0.61, "pill": 0.69},
            pairs={"ellipse": (0.42, 30.0), "rect": (0.55, 60.0), "pill": (0.40, 25.0)},
            ties={"circle", "rounded-rect"}, params=self.PARAMS)
        self.assertEqual((verdict["family"], verdict["accepted"]), ("circle", True))
        self.assertEqual(sorted(verdict["ties"]), ["circle", "rounded-rect"])

    def test_every_name_in_the_verdict_is_the_name_that_would_be_emitted(self):
        # The fitted families are two; what ships is the name read off the winner's parameters. A
        # verdict that reports `family` in one vocabulary and `ties` in the other is comparing two
        # languages: `--family pill` refused a source whose pill tied with the emitted circle at
        # agreement 1.000, and the eval read the same row as a wrong acceptance.
        verdict = primitives.decide(
            fits={"ellipse": 0.92, "rounded-rect": 0.92},
            pairs={"rounded-rect": (0.4, 30.0)},
            ties={"rounded-rect"}, params=self.PARAMS,
            names={"ellipse": "circle", "rounded-rect": "pill"})
        self.assertEqual(verdict["family"], "circle")
        self.assertEqual(verdict["ties"], ["circle", "pill"])
        self.assertEqual(verdict["fitted"], "ellipse")

    def test_the_runner_up_is_named_in_that_vocabulary_too(self):
        verdict = primitives.decide(
            fits={"ellipse": 0.93, "rounded-rect": 0.66},
            pairs={"rounded-rect": (0.48, 40.0)},
            ties=set(), params=self.PARAMS,
            names={"ellipse": "circle", "rounded-rect": "rect"})
        self.assertEqual(verdict["runner_up"], "rect")

    def test_a_family_with_no_entry_names_itself(self):
        verdict = primitives.decide(
            fits={"circle": 0.93, "ellipse": 0.70},
            pairs={"ellipse": (0.42, 30.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual((verdict["family"], verdict["fitted"]), ("circle", "circle"))

    def test_the_verdict_names_the_runner_up_and_its_margin_even_when_accepted(self):
        verdict = primitives.decide(
            fits={"circle": 0.93, "ellipse": 0.70, "rect": 0.61, "rounded-rect": 0.66, "pill": 0.69},
            pairs={"ellipse": (0.42, 30.0), "rect": (0.55, 60.0), "rounded-rect": (0.48, 40.0),
                   "pill": (0.40, 25.0)},
            ties=set(), params=self.PARAMS)
        self.assertEqual(verdict["runner_up"], "pill")
        self.assertAlmostEqual(verdict["margin"], 0.40)


class ParamsFileTest(unittest.TestCase):
    def test_the_shipped_params_file_declares_every_parameter(self):
        params = primitives.load_params(f"{SKILL_DIR}/scripts/primitives.json")
        for key in ("bar", "margin", "min_weight", "equivalent", "hull_fill", "bbox_fill",
                    "symmetry", "min_px", "sigmas"):
            self.assertIn(key, params)

    def test_a_params_file_missing_a_parameter_is_refused(self):
        import json
        import os
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"bar": 0.5}, fh)
        self.addCleanup(os.unlink, fh.name)
        with self.assertRaisesRegex(ValueError, "margin"):
            primitives.load_params(fh.name)


if __name__ == "__main__":
    unittest.main()
