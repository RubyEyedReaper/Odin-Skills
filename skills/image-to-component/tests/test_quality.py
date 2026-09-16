"""quality: a glyph source too degraded to trace is refused before tracing, by name (#1391)."""
from __future__ import annotations

import random
import unittest

from ._fixtures import SKILL_DIR, rgba  # noqa: F401  (puts the skill on sys.path)
from scripts import keying, quality

GROUND, INK = (24, 26, 34), (120, 200, 230)


def _glyph(size: int, inside, noise: float, seed: int = 1) -> bytes:
    """A cyan glyph on a dark card, with seeded Gaussian RGB noise over every pixel."""
    rng = random.Random(seed)

    def px(x, y):
        base = INK if inside(x, y) else GROUND
        return tuple(max(0, min(255, round(c + rng.gauss(0, noise)))) for c in base) + (255,)
    return rgba(size, size, px)


def _ring(size: int, width: float):
    c, r = size / 2, size / 2 - 3
    return lambda x, y: abs(((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5 - r) <= width / 2


def _blurred_disc(size: int, radius: float, ramp: float) -> bytes:
    """A cyan disc on a dark card whose edge fades from ground to ink over `ramp` px."""
    c = size / 2

    def px(x, y):
        d = ((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5
        share = max(0.0, min(1.0, (radius + ramp / 2 - d) / ramp))
        return tuple(round(g + (i - g) * share) for g, i in zip(GROUND, INK)) + (255,)
    return rgba(size, size, px)


class RampExtent(unittest.TestCase):
    """Edge ramp read against the subject's own size: how blurred is this source, for its scale."""

    def test_a_crisp_disc_has_almost_no_ramp_for_its_extent(self):
        buf = _blurred_disc(40, 14, ramp=0.5)
        bg = keying.border_background(buf, 40, 40)
        self.assertLess(quality.ramp_extent(buf, 40, 40, bg), 0.05)

    def test_a_disc_blurred_across_a_quarter_of_itself_scores_far_higher(self):
        crisp = _blurred_disc(40, 14, ramp=0.5)
        blurred = _blurred_disc(40, 14, ramp=7)
        bg = keying.border_background(crisp, 40, 40)
        self.assertGreater(quality.ramp_extent(blurred, 40, 40, bg),
                           4 * quality.ramp_extent(crisp, 40, 40, bg))

    def test_the_same_blur_on_a_bigger_subject_scores_lower(self):
        """The measure is dimensionless: the same edge over more glyph is less damage."""
        small = _blurred_disc(40, 7, ramp=3)
        large = _blurred_disc(40, 16, ramp=3)
        bg = keying.border_background(small, 40, 40)
        self.assertLess(quality.ramp_extent(large, 40, 40, bg),
                        quality.ramp_extent(small, 40, 40, bg))

    def test_a_source_with_nothing_visible_scores_zero(self):
        buf = rgba(12, 12, lambda x, y: GROUND + (255,))
        bg = keying.border_background(buf, 12, 12)
        self.assertEqual(quality.ramp_extent(buf, 12, 12, bg), 0.0)


def _noisy_disc(size: int, radius: float, ramp: float, noise: float, seed: int = 5) -> bytes:
    """A blurred disc whose ground carries seeded noise, so `assess` has a sigma to perturb with."""
    rng = random.Random(seed)
    c = size / 2

    def px(x, y):
        d = ((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5
        share = max(0.0, min(1.0, (radius + ramp / 2 - d) / ramp))
        base = tuple(g + (i - g) * share for g, i in zip(GROUND, INK))
        return tuple(max(0, min(255, round(v + rng.gauss(0, noise)))) for v in base) + (255,)
    return rgba(size, size, px)


class CombinedVerdict(unittest.TestCase):
    """Two measures, one refusal name: `assess` says which one fired (#1410)."""

    def test_a_readable_glyph_passes_and_names_no_reason(self):
        buf = _glyph(24, lambda x, y: 5 <= x < 19 and 5 <= y < 19, noise=6)
        result = quality.assess(buf, 24, 24)
        self.assertTrue(result["pass"], result)
        self.assertIsNone(result["reason"])

    def test_a_source_the_blur_merged_is_refused_by_name(self):
        """Stable under its own noise — a thick shape stays put — and blurred across its own extent."""
        buf = _noisy_disc(28, radius=8, ramp=9, noise=3)
        result = quality.assess(buf, 28, 28)
        self.assertGreaterEqual(result["stability"], quality.MIN_STABILITY)
        self.assertGreater(result["ramp_extent"], quality.MAX_RAMP_EXTENT)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "ramp-extent")

    def test_a_source_whose_noise_moves_its_silhouette_is_refused_by_the_other_name(self):
        faint = (60, 80, 95)
        rng = random.Random(3)
        inside = _ring(18, 1.0)

        def px(x, y):
            base = faint if inside(x, y) else GROUND
            return tuple(max(0, min(255, round(c + rng.gauss(0, 14)))) for c in base) + (255,)
        result = quality.assess(rgba(18, 18, px), 18, 18)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "stability")

    def test_both_measures_are_reported_whatever_the_verdict(self):
        buf = _glyph(24, lambda x, y: 5 <= x < 19 and 5 <= y < 19, noise=6)
        self.assertEqual(set(quality.assess(buf, 24, 24)),
                         {"sigma", "stability", "ramp_extent", "mono", "reason", "pass"})


def _two_region_mark(size: int, bleed: float, noise: float, seed: int = 7) -> bytes:
    """Two coloured halves of a disc on a dark card, their shared border fading over `bleed` px."""
    rng = random.Random(seed)
    left, right = (210, 60, 70), (70, 110, 210)
    c = size / 2

    def px(x, y):
        d = ((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5
        if d > size / 2 - 3:
            base = GROUND
        else:
            edge = max(0.0, min(1.0, (size / 2 - 3 - d) / max(bleed, 0.5)))
            share = max(0.0, min(1.0, (x + 0.5 - c) / max(bleed, 0.5) + 0.5))
            mark = tuple(l + (r - l) * share for l, r in zip(left, right))
            base = tuple(g + (m - g) * edge for g, m in zip(GROUND, mark))
        return tuple(max(0, min(255, round(v + rng.gauss(0, noise)))) for v in base) + (255,)
    return rgba(size, size, px)


class ColourSourceQuality(unittest.TestCase):
    """A colour mark is assessed too, by the same measures under the keying a mark actually gets (#1409)."""

    def test_a_crisp_mark_passes(self):
        result = quality.assess(_two_region_mark(48, bleed=0.5, noise=3), 48, 48, mono=False)
        self.assertTrue(result["pass"], result)
        self.assertIsNone(result["reason"])

    def test_a_mark_whose_blur_is_wide_for_its_size_is_refused_by_its_ramp(self):
        """Blurred enough to have merged, not so far gone that its outline moves as well."""
        result = quality.assess(_two_region_mark(48, bleed=6, noise=3), 48, 48, mono=False)
        self.assertGreaterEqual(result["stability"], quality.MIN_COLOUR_STABILITY)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "ramp-extent")

    def test_a_mark_dissolved_into_its_ground_is_refused_by_its_stability(self):
        result = quality.assess(_two_region_mark(48, bleed=14, noise=3), 48, 48, mono=False)
        self.assertFalse(result["pass"], result)
        self.assertEqual(result["reason"], "stability")

    def test_the_colour_bars_are_their_own(self):
        """A mark is keyed and bounded differently from a glyph; the verdict records which bar it met."""
        buf = _two_region_mark(48, bleed=0.5, noise=3)
        self.assertFalse(quality.assess(buf, 48, 48, mono=False)["mono"])
        self.assertTrue(quality.assess(buf, 48, 48)["mono"])
        self.assertNotEqual(quality.MAX_RAMP_EXTENT, quality.MAX_COLOUR_RAMP_EXTENT)

    def test_a_refused_mark_is_told_it_is_a_mark(self):
        message = quality.refusal_message(quality.assess(_two_region_mark(48, bleed=6, noise=3), 48, 48, mono=False))
        self.assertIn("mark", message)
        self.assertNotIn("glyph", message)

    def test_the_colour_verdict_is_deterministic(self):
        buf = _two_region_mark(40, bleed=4, noise=4)
        self.assertEqual(quality.assess(buf, 40, 40, mono=False), quality.assess(buf, 40, 40, mono=False))


class RefusalMessage(unittest.TestCase):
    """What the user reads has to say which measure refused; the two mean different things."""

    def test_a_merged_source_is_told_about_its_blur(self):
        message = quality.refusal_message(quality.assess(_noisy_disc(28, radius=8, ramp=9, noise=3), 28, 28))
        self.assertIn("edge ramp over subject extent", message)
        self.assertNotIn("silhouette stability", message)

    def test_a_moving_silhouette_is_told_about_its_noise(self):
        faint = (60, 80, 95)
        rng = random.Random(3)
        inside = _ring(18, 1.0)

        def px(x, y):
            base = faint if inside(x, y) else GROUND
            return tuple(max(0, min(255, round(c + rng.gauss(0, 14)))) for c in base) + (255,)
        message = quality.refusal_message(quality.assess(rgba(18, 18, px), 18, 18))
        self.assertIn("silhouette stability", message)
        self.assertNotIn("edge ramp", message)


class Stability(unittest.TestCase):
    def test_a_bold_glyph_on_a_noisy_card_is_readable(self):
        buf = _glyph(24, lambda x, y: 5 <= x < 19 and 5 <= y < 19, noise=6)
        result = quality.assess(buf, 24, 24)
        self.assertTrue(result["pass"], result)
        self.assertGreater(result["sigma"], 3)

    def test_a_hairline_whose_noise_rivals_its_contrast_is_refused(self):
        faint = (60, 80, 95)
        rng = random.Random(3)
        inside = _ring(18, 1.0)

        def px(x, y):
            base = faint if inside(x, y) else GROUND
            return tuple(max(0, min(255, round(c + rng.gauss(0, 14)))) for c in base) + (255,)
        result = quality.assess(rgba(18, 18, px), 18, 18)
        self.assertFalse(result["pass"], result)
        self.assertLess(result["stability"], quality.MIN_STABILITY)

    def test_a_noiseless_source_is_stable_by_construction(self):
        buf = _glyph(20, _ring(20, 1.0), noise=0)
        result = quality.assess(buf, 20, 20)
        self.assertEqual((result["sigma"], result["stability"], result["pass"]), (0.0, 1.0, True))

    def test_a_transparent_source_has_no_ground_to_measure_and_passes(self):
        buf = rgba(16, 16, lambda x, y: (0, 0, 0, 255 if 4 <= x < 12 and 4 <= y < 12 else 0))
        self.assertTrue(quality.assess(buf, 16, 16)["pass"])

    def test_the_verdict_is_deterministic(self):
        buf = _glyph(20, _ring(20, 2.0), noise=10)
        self.assertEqual(quality.assess(buf, 20, 20), quality.assess(buf, 20, 20))


if __name__ == "__main__":
    unittest.main()
