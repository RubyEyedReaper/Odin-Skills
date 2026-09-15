"""edges: whether a source's alpha boundary is a hard pixel staircase or an anti-aliased ramp."""
from __future__ import annotations

import unittest

from ._fixtures import rgba, square
from scripts import edges


def disc(size: int, radius: float, samples: int):
    """A black disc; `samples`² supersampled coverage (1 = aliased)."""
    centre = size / 2

    def px(x, y):
        hits = sum((x + (i + 0.5) / samples - centre) ** 2 + (y + (j + 0.5) / samples - centre) ** 2 <= radius ** 2
                   for i in range(samples) for j in range(samples))
        return (0, 0, 0, round(255 * hits / samples ** 2))
    return rgba(size, size, px)


class HardEdgeFraction(unittest.TestCase):
    def test_binary_alpha_is_all_hard(self):
        self.assertEqual(edges.hard_edge_fraction(disc(40, 14, 1), 40, 40), 1.0)

    def test_anti_aliased_disc_is_mostly_soft(self):
        # Coverage puts almost every boundary pixel strictly between the two extremes.
        self.assertLess(edges.hard_edge_fraction(disc(40, 14, 4), 40, 40), 0.3)

    def test_axis_aligned_square_is_hard_even_when_its_edge_is_exact(self):
        # A pixel-aligned square has no partial coverage to show; it is indistinguishable from an
        # aliased one, and tracing it as a staircase costs nothing because it has no stairs.
        self.assertEqual(edges.hard_edge_fraction(square(20, 20, 5, 5, 10), 20, 20), 1.0)

    def test_no_boundary_is_none(self):
        self.assertIsNone(edges.hard_edge_fraction(rgba(6, 6, lambda x, y: (0, 0, 0, 0)), 6, 6))
        self.assertIsNone(edges.hard_edge_fraction(rgba(6, 6, lambda x, y: (0, 0, 0, 255)), 6, 6))

    def test_classification_follows_the_threshold(self):
        self.assertEqual(edges.classify(disc(40, 14, 1), 40, 40), "hard")
        self.assertEqual(edges.classify(disc(40, 14, 4), 40, 40), "soft")
        self.assertEqual(edges.classify(rgba(6, 6, lambda x, y: (0, 0, 0, 0)), 6, 6), "soft")


class SmoothingFor(unittest.TestCase):
    def test_auto_smooths_a_hard_edge_along_its_outline_whatever_the_scale(self):
        for scale in (2, 4, 8):
            self.assertEqual(edges.smoothing_for("auto", "hard", scale), ("outline", 0.8))

    def test_auto_blurs_a_soft_edge_in_proportion_to_scale(self):
        # 3 at ×8 is what the RubyTech glyph row shipped with before auto existed.
        self.assertEqual(edges.smoothing_for("auto", "soft", 8), ("gaussian", 3.0))
        self.assertEqual(edges.smoothing_for("auto", "soft", 4), ("gaussian", 1.5))

    def test_a_number_is_a_gaussian_radius_whatever_the_edge(self):
        self.assertEqual(edges.smoothing_for("7", "hard", 8), ("gaussian", 7.0))
        self.assertEqual(edges.smoothing_for("0", "soft", 8), ("gaussian", 0.0))

    def test_anything_else_is_refused_by_name(self):
        for bad in ("", "smooth", "-1", "nan"):
            with self.assertRaisesRegex(ValueError, "--smooth"):
                edges.smoothing_for(bad, "hard", 8)


if __name__ == "__main__":
    unittest.main()
