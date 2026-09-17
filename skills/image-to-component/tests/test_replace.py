"""replace: the verifier that decides whether a library icon may stand in for a source."""
from __future__ import annotations

import unittest

from .test_library import mask
from scripts import library, replace

# 6x6 silhouettes: a wide bar, a plus and a cross — three shapes a verifier must keep apart.
BAR = mask(["......", ".####.", ".####.", "......", "......", "......"])[0]
PLUS = mask(["......", "..##..", "######", "######", "..##..", "......"])[0]
CROSS = mask(["#....#", ".#..#.", "..##..", "..##..", ".#..#.", "#....#"])[0]


def blend(a: bytes, b: bytes, weight: float) -> bytes:
    """A source that is `weight` of b and the rest of a — a noisy, partial resemblance."""
    return bytes(round(x * (1 - weight) + y * weight) for x, y in zip(a, b))


class MetricTest(unittest.TestCase):
    def test_soft_iou_is_one_for_identical_masks_and_zero_for_disjoint(self):
        self.assertEqual(replace.soft_iou(PLUS, PLUS), 1.0)
        self.assertEqual(replace.soft_iou(bytes([255, 0]), bytes([0, 255])), 0.0)

    def test_pair_margin_is_plus_one_when_the_source_is_the_named_render(self):
        t, weight = replace.pair_margin(PLUS, PLUS, CROSS)
        self.assertEqual(t, 1.0)
        self.assertGreater(weight, 0)

    def test_pair_margin_is_minus_one_when_the_source_is_the_adversary(self):
        self.assertEqual(replace.pair_margin(CROSS, PLUS, CROSS)[0], -1.0)

    def test_pair_margin_ignores_pixels_both_candidates_agree_on(self):
        # Where both renders are fully inked, a source that is clear there counts against neither.
        top = lambda buf: bytes(255 if i < 6 else v for i, v in enumerate(buf))  # noqa: E731
        source = bytes(0 if i < 6 else v for i, v in enumerate(PLUS))
        self.assertEqual(replace.pair_margin(source, top(PLUS), top(CROSS))[0], 1.0)

    def test_pair_margin_of_identical_renders_has_no_weight(self):
        self.assertEqual(replace.pair_margin(PLUS, PLUS, PLUS), (0.0, 0.0))


class ShortlistTest(unittest.TestCase):
    INDEX = {
        "material:plus": {"thumb": library.thumbnail(PLUS, 6, 6, 4).hex(), "aspect": 1.0},
        "material:cross": {"thumb": library.thumbnail(CROSS, 6, 6, 4).hex(), "aspect": 1.0},
        "material:bar": {"thumb": library.thumbnail(BAR, 6, 6, 4).hex(), "aspect": 2.0},
    }

    def test_the_nearest_thumbnails_come_first(self):
        thumb = library.thumbnail(PLUS, 6, 6, 4)
        self.assertEqual(replace.shortlist(self.INDEX, thumb, 1.0, 2), ["material:plus", "material:cross"])

    def test_an_aspect_far_from_the_source_is_not_shortlisted(self):
        self.assertNotIn("material:bar", replace.shortlist(self.INDEX, library.thumbnail(PLUS, 6, 6, 4), 1.0, 5))

    def test_excluded_slugs_are_skipped_without_shortening_the_list(self):
        self.assertEqual(replace.shortlist(self.INDEX, library.thumbnail(PLUS, 6, 6, 4), 1.0, 1,
                                           exclude={"material:plus"}), ["material:cross"])


class KnockoutTest(unittest.TestCase):
    @staticmethod
    def tile(inner=(255, 255, 255)) -> bytes:
        """A blue 6x6 tile with a 2x2 inner square of `inner`, fully opaque."""
        out = bytearray()
        for y in range(6):
            for x in range(6):
                out += bytes((*inner, 255)) if 2 <= x < 4 and 2 <= y < 4 else bytes((8, 102, 255, 255))
        return bytes(out)

    def test_a_second_colour_inside_the_ink_becomes_a_hole(self):
        result = replace.knockout(self.tile(), 6, 6)
        self.assertIsNotNone(result)
        alpha, dominant, other = result
        self.assertEqual((alpha[0], alpha[2 * 6 + 2]), (255, 0))
        self.assertEqual((dominant, other), ((8, 102, 255), (255, 255, 255)))

    def test_the_colour_on_the_edge_is_the_ink_whichever_covers_more(self):
        # A green ring on a white page, flood-keyed: the page inside it stays opaque and outnumbers the green.
        out = bytearray()
        for y in range(8):
            for x in range(8):
                out += bytes((255, 255, 255, 255)) if 1 <= x < 7 and 1 <= y < 7 else bytes((37, 211, 102, 255))
        alpha, dominant, other = replace.knockout(bytes(out), 8, 8, ground=(255, 255, 255))
        self.assertEqual((dominant, other), ((37, 211, 102), (255, 255, 255)))
        self.assertEqual((alpha[0], alpha[3 * 8 + 3]), (255, 0))

    def test_the_ink_is_the_colour_on_the_silhouette_edge_even_when_the_hole_is_farther_from_the_ground(self):
        # A white glyph on a red disc on a dark card: white is farther from the card, but red is what meets it.
        out = bytearray()
        for y in range(6):
            for x in range(6):
                if x in (0, 5) or y in (0, 5):
                    out += bytes((20, 20, 24, 0))
                elif 2 <= x < 4 and 2 <= y < 4:
                    out += bytes((255, 255, 255, 255))
                else:
                    out += bytes((218, 40, 40, 255))
        alpha, dominant, other = replace.knockout(bytes(out), 6, 6, ground=(20, 20, 24))
        self.assertEqual((dominant, other), ((218, 40, 40), (255, 255, 255)))
        self.assertEqual((alpha[1 * 6 + 1], alpha[2 * 6 + 2]), (255, 0))

    def test_the_edge_share_of_a_cut_out_colour_is_zero_and_of_a_side_by_side_colour_is_not(self):
        tile = self.tile()
        self.assertEqual(replace.edge_share(tile, 6, 6, (8, 102, 255), (255, 255, 255)), 0.0)
        halves = bytes(b for y in range(6) for x in range(6)
                       for b in ((8, 102, 255, 255) if x < 3 else (255, 255, 255, 255)))
        self.assertAlmostEqual(replace.edge_share(halves, 6, 6, (8, 102, 255), (255, 255, 255)), 0.5)

    def test_the_knockout_colour_is_its_purest_pixels_not_a_mean_with_the_blended_edge(self):
        # A white cut-out whose JPEG'd border is pink: the backplate must be white, not the average pink.
        out = bytearray()
        for y in range(8):
            for x in range(8):
                if 3 <= x < 5 and 2 <= y < 6:
                    colour = (255, 255, 255)
                elif 2 <= x < 6 and 1 <= y < 7:
                    colour = (245, 175, 185)
                else:
                    colour = (220, 30, 60)
                out += bytes((*colour, 255))
        _, dominant, other = replace.knockout(bytes(out), 8, 8, ground=(20, 20, 24))
        self.assertLess(replace._dist(other, (255, 255, 255)), 20)

    def test_a_single_colour_subject_has_no_knockout(self):
        self.assertIsNone(replace.knockout(self.tile(inner=(10, 100, 250)), 6, 6))


class DecideTest(unittest.TestCase):
    PARAMS = {"bar": 0.6, "margin": 0.4, "min_weight": 1.0}

    def test_a_named_candidate_that_fits_and_beats_every_adversary_is_accepted(self):
        verdict = replace.decide("material:plus", PLUS, 0.9, {"material:cross": (CROSS, 0.5)}, PLUS, **self.PARAMS)
        self.assertTrue(verdict["accepted"])
        self.assertEqual(verdict["runner_up"], "material:cross")
        self.assertEqual(verdict["margin"], 1.0)

    def test_a_named_candidate_beaten_by_an_adversary_is_refused_and_names_it(self):
        source = blend(PLUS, CROSS, 0.6)
        verdict = replace.decide("material:plus", PLUS, 0.9, {"material:cross": (CROSS, 0.8)}, source, **self.PARAMS)
        self.assertFalse(verdict["accepted"])
        self.assertEqual((verdict["reason"], verdict["runner_up"]), ("adversary", "material:cross"))

    def test_a_named_candidate_below_the_bar_is_refused_before_any_adversary(self):
        verdict = replace.decide("material:plus", PLUS, 0.5, {"material:cross": (CROSS, 0.2)}, PLUS, **self.PARAMS)
        self.assertEqual(verdict["reason"], "bar")

    def test_an_adversary_the_source_size_cannot_tell_apart_refuses_rather_than_passes(self):
        near = bytes(v if i != 0 else 40 for i, v in enumerate(PLUS))
        verdict = replace.decide("material:plus", PLUS, 0.9, {"material:near": (near, 0.9)}, PLUS, **self.PARAMS)
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "indistinguishable"))

    def test_the_worst_adversary_decides_not_the_best_fitting_one(self):
        source = blend(PLUS, CROSS, 0.7)
        adversaries = {"material:bar": (BAR, 0.95), "material:cross": (CROSS, 0.5)}
        verdict = replace.decide("material:plus", PLUS, 0.9, adversaries, source, **self.PARAMS)
        self.assertEqual(verdict["runner_up"], "material:cross")

    def test_with_no_adversary_to_beat_nothing_is_verified_and_nothing_is_accepted(self):
        verdict = replace.decide("material:plus", PLUS, 0.9, {}, PLUS, **self.PARAMS)
        self.assertEqual((verdict["accepted"], verdict["reason"]), (False, "no-adversary"))


class EquivalentTest(unittest.TestCase):
    def test_renders_identical_at_full_size_are_equivalent(self):
        self.assertTrue(replace.equivalent(PLUS, PLUS, 0.95))
        self.assertFalse(replace.equivalent(PLUS, CROSS, 0.95))


class ColourTest(unittest.TestCase):
    def test_a_source_colour_near_the_brand_hex_matches(self):
        self.assertTrue(replace.colour_matches((10, 100, 250), "0866FF", 60))

    def test_a_recoloured_brand_mark_does_not(self):
        self.assertFalse(replace.colour_matches((40, 190, 230), "0866FF", 60))

    def test_hex_formats_the_measured_colour_for_a_fill(self):
        self.assertEqual(replace.hex_colour((8, 102, 255)), "#0866FF")


class EmissionTest(unittest.TestCase):
    BLUE, WHITE = (8, 102, 255), (250, 250, 250)

    def test_current_color_carries_no_fill_and_no_backplate(self):
        self.assertEqual(replace.emission("simple-icons", "currentColor", self.BLUE, self.WHITE, "0866FF"),
                         {"fills": None, "backplate": None, "refused": None})

    def test_a_material_glyph_takes_the_measured_colour_and_its_knockout_backplate(self):
        self.assertEqual(replace.emission("material", "original", self.BLUE, self.WHITE, None),
                         {"fills": ["#0866FF"], "backplate": "#FAFAFA", "refused": None})

    def test_a_brand_mark_is_drawn_in_its_own_hex_never_the_measured_one(self):
        out = replace.emission("simple-icons", "original", (12, 100, 250), None, "0866FF")
        self.assertEqual(out, {"fills": ["#0866FF"], "backplate": None, "refused": None})

    def test_a_recoloured_brand_mark_is_refused_in_original_colour(self):
        out = replace.emission("simple-icons", "original", (40, 190, 230), None, "0866FF")
        self.assertEqual(out["refused"], "brand-colour")


class HeaderTest(unittest.TestCase):
    def test_a_material_header_names_version_slug_weight_and_licence(self):
        lines = replace.header_lines("material", "alarm", "0.47.3", 500, {})
        self.assertIn("Material Symbols 0.47.3", lines[0])
        self.assertIn("outlined/alarm", lines[0])
        self.assertIn("weight 500", lines[0])
        self.assertIn("Apache-2.0", " ".join(lines))

    def test_a_brand_header_carries_the_trademark_note_and_guidelines(self):
        lines = replace.header_lines("simple-icons", "facebook", "16.31.0", None,
                                     {"title": "Facebook", "guidelines": "https://about.meta.com/brand/resources/"})
        text = " ".join(lines)
        self.assertIn("simple-icons 16.31.0 icons/facebook.svg", text)
        self.assertIn("CC0-1.0", text)
        self.assertIn("Facebook is a trademark of its owner", text)
        self.assertIn("https://about.meta.com/brand/resources/", text)


class DegradeTest(unittest.TestCase):
    def test_blur_is_taken_out_of_the_source_radius_before_a_fit(self):
        # A Gaussian of sigma adds sigma squared of variance per axis, two axes.
        self.assertAlmostEqual(replace.unblurred_radius(5.0, 2.0), (25 - 8) ** 0.5)

    def test_a_blur_larger_than_the_shape_never_makes_the_radius_vanish(self):
        self.assertEqual(replace.unblurred_radius(1.0, 3.0), 0.5)

    def test_the_sigma_whose_render_ramp_is_nearest_the_source_ramp_is_chosen(self):
        self.assertEqual(replace.choose_sigma(1.7, {0.0: 0.6, 0.8: 1.5, 1.2: 2.1}), 0.8)

    def test_a_source_with_no_measurable_ramp_is_taken_as_unblurred(self):
        self.assertEqual(replace.choose_sigma(None, {0.0: 0.6, 0.8: 1.5}), 0.0)


class ParamsTest(unittest.TestCase):
    def test_every_calibrated_number_is_declared(self):
        import json, os, tempfile
        path = os.path.join(tempfile.mkdtemp(), "replace.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"bar": 0.8}, fh)
        with self.assertRaises(ValueError) as caught:
            replace.load_params(path)
        self.assertIn("margin", str(caught.exception))
        os.unlink(path)

    def test_the_committed_params_file_loads(self):
        import os
        params = replace.load_params(os.path.join(os.path.dirname(replace.__file__), "replace.json"))
        self.assertGreater(params["auto_margin"], params["margin"])


class PeakTest(unittest.TestCase):
    def test_a_render_is_stretched_so_its_peak_reads_as_full_ink_like_a_keyed_source(self):
        # keying.soft_matte maps the subject's 99th-percentile distance to full alpha; a thin stroke's
        # render never reaches full coverage, so it gets the same stretch before it is compared.
        out = replace.normalise_peak(bytes([0, 50, 100, 150]), gamma=1.0)
        self.assertEqual(out, bytes([0, 85, 170, 255]))

    def test_the_stretch_applies_the_keying_gamma(self):
        out = replace.normalise_peak(bytes([0, 75, 150]), gamma=2.0)
        self.assertEqual(out, bytes([0, 64, 255]))

    def test_an_empty_render_stays_empty(self):
        self.assertEqual(replace.normalise_peak(bytes(4), gamma=1.15), bytes(4))


class DecidePairsTest(unittest.TestCase):
    def test_stored_pairs_decide_exactly_as_the_renders_they_were_measured_from(self):
        source, adversaries = blend(PLUS, CROSS, 0.2), {"cross": (CROSS, 0.3), "bar": (BAR, 0.2)}
        pairs = {slug: replace.pair_margin(source, PLUS, render) for slug, (render, _) in adversaries.items()}
        self.assertEqual(replace.decide_pairs("plus", 0.9, pairs, 0.5, 0.2, 1.0),
                         replace.decide("plus", PLUS, 0.9, adversaries, source, 0.5, 0.2, 1.0))


class ShortlistLevelsTest(unittest.TestCase):
    def test_an_entry_is_as_near_as_its_nearest_blur_level(self):
        source = bytes([100] * 4)
        index = {"crisp": {"aspect": 1.0, "thumb": bytes([255, 0, 255, 0]).hex()},
                 "levels": {"aspect": 1.0, "thumb": bytes([255, 0, 255, 0]).hex(), "thumbs": [bytes([255, 0, 255, 0]).hex(), bytes([110] * 4).hex()]},
                 "other": {"aspect": 1.0, "thumb": bytes([60] * 4).hex()}}
        self.assertEqual(replace.shortlist(index, source, 1.0, 3), ["levels", "other", "crisp"])


class ReadingsTest(unittest.TestCase):
    def test_holes_the_colour_of_the_ground_are_ground_so_only_the_knockout_is_read(self):
        # A white play arrow inside a red mark on a white page: flood keying kept it, but it is the page.
        self.assertEqual(replace.readings((250, 250, 250), (255, 255, 255)), ["knockout"])

    def test_a_second_colour_unlike_the_ground_keeps_both_readings(self):
        # A white "f" on a blue tile on a dark card, or a two-colour mark: either could be the silhouette.
        self.assertEqual(replace.readings((255, 255, 255), (20, 20, 30), knockout_edge_share=0.5), ["alpha", "knockout"])

    def test_a_second_colour_that_never_meets_the_edge_is_a_cut_out_so_only_the_knockout_is_read(self):
        # A white "!" inside a red disc on a dark card: the filled disc would let any filled circle stand in.
        self.assertEqual(replace.readings((255, 255, 255), (20, 20, 30), knockout_edge_share=0.0), ["knockout"])

    def test_a_second_colour_on_the_edge_keeps_both_readings(self):
        self.assertEqual(replace.readings((255, 255, 255), (20, 20, 30), knockout_edge_share=0.4), ["alpha", "knockout"])

    def test_no_knockout_is_read_as_alpha(self):
        self.assertEqual(replace.readings(None, (255, 255, 255)), ["alpha"])
        self.assertEqual(replace.readings((255, 255, 255), None, knockout_edge_share=0.5), ["alpha", "knockout"])


class GroundReadingTest(unittest.TestCase):
    WHITE, GREEN = (255, 255, 255), (30, 215, 96)

    def disc_with_bar(self) -> bytes:
        """A 6x6 green block, flood-keyed opaque, with a one-pixel white bar through it: enclosed page."""
        out = bytearray()
        for y in range(6):
            for x in range(6):
                out += bytes((*(self.WHITE if y == 3 and 1 <= x < 5 else self.GREEN), 255))
        return bytes(out)

    def test_enclosed_ground_share_counts_opaque_pixels_the_colour_of_the_ground(self):
        self.assertAlmostEqual(replace.enclosed_ground_share(self.disc_with_bar(), self.WHITE, 6, 6), 4 / 36)

    def test_a_blended_bar_pixel_nearer_the_page_than_the_ink_is_enclosed_page(self):
        # JPEG and a sub-pixel bar leave (190, 240, 205): far from white by any fixed tolerance, nearer it than green.
        buf = bytearray(self.disc_with_bar())
        for x in range(1, 5):
            buf[(3 * 6 + x) * 4:(3 * 6 + x) * 4 + 3] = bytes((190, 240, 205))
        self.assertAlmostEqual(replace.enclosed_ground_share(bytes(buf), self.WHITE, 6, 6), 4 / 36)

    def test_a_light_cut_out_on_a_dark_card_is_not_enclosed_page(self):
        out = bytearray()
        for y in range(6):
            for x in range(6):
                if x in (0, 5) or y in (0, 5):
                    out += bytes((20, 20, 24, 0))
                elif 2 <= x < 4 and 2 <= y < 4:
                    out += bytes((255, 255, 255, 255))
                else:
                    out += bytes((218, 40, 40, 255))
        self.assertEqual(replace.enclosed_ground_share(bytes(out), (20, 20, 24), 6, 6), 0.0)

    def test_a_ground_reading_clears_enclosed_page_and_keeps_the_ink(self):
        alpha = replace.ground_alpha(self.disc_with_bar(), self.WHITE)
        self.assertEqual((alpha[0], alpha[3 * 6 + 2]), (255, 0))

    def test_a_ground_reading_leaves_keyed_transparency_transparent(self):
        buf = bytearray(self.disc_with_bar())
        buf[3] = 0
        self.assertEqual(replace.ground_alpha(bytes(buf), self.WHITE)[0], 0)

    def test_readings_swap_alpha_for_ground_when_enough_page_is_enclosed(self):
        self.assertEqual(replace.readings(None, self.WHITE, enclosed_share=0.05), ["ground"])
        self.assertEqual(replace.readings(None, self.WHITE, enclosed_share=0.0), ["alpha"])


class AutoSizeTest(unittest.TestCase):
    def test_ink_extent_is_the_longer_side_of_the_visible_box(self):
        from .test_library import mask
        buf, w, h = mask(["......", ".####.", ".####.", "......"])
        self.assertEqual(replace.ink_extent(buf, w, h), 4)


if __name__ == "__main__":
    unittest.main()
