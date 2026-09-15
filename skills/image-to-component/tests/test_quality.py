"""quality: a glyph source too degraded to trace is refused before tracing, by name (#1391)."""
from __future__ import annotations

import random
import unittest

from ._fixtures import SKILL_DIR, rgba  # noqa: F401  (puts the skill on sys.path)
from scripts import quality

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
