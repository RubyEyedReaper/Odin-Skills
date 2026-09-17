"""pathgeom: the stdlib SVG path reader the replace route uses for backplates and content boxes."""
from __future__ import annotations

import unittest

from . import _fixtures  # noqa: F401  (puts the skill on sys.path)
from scripts import pathgeom

# A 10x10 square with a 4x4 hole drawn the other way round — how a nonzero-fill icon cuts a hole.
SQUARE_WITH_HOLE = "M0 0H10V10H0Z M3 3V7H7V3Z"


class SubpathsTest(unittest.TestCase):
    def test_absolute_lines_close_back_to_the_start(self):
        polys = pathgeom.subpaths("M0 0L10 0L10 10Z")
        self.assertEqual(polys, [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 0.0)]])

    def test_relative_commands_and_implicit_repeats_resolve_to_absolute_points(self):
        # m then bare pairs are relative linetos; h/v are relative too.
        polys = pathgeom.subpaths("m1 1 4 0 0 4h-4v-4z")
        self.assertEqual(polys[0][:5], [(1.0, 1.0), (5.0, 1.0), (5.0, 5.0), (1.0, 5.0), (1.0, 1.0)])

    def test_a_relative_move_after_close_starts_from_the_closed_subpath_start(self):
        polys = pathgeom.subpaths("M10 10h5v5z m2 2h1v1z")
        self.assertEqual(polys[1][0], (12.0, 12.0))

    def test_numbers_packed_the_way_svgo_writes_them_parse(self):
        # "1.5.5" is 1.5 then .5; "-1-2" is -1 then -2.
        polys = pathgeom.subpaths("M1.5.5l-1-2")
        self.assertEqual(polys[0], [(1.5, 0.5), (0.5, -1.5)])

    def test_curves_end_at_their_endpoints(self):
        for d, end in (("M0 0C1 1 2 1 3 0", (3.0, 0.0)), ("M0 0Q5 5 10 0T20 0", (20.0, 0.0)),
                       ("M0 0c1 1 2 1 3 0s2-1 3 0", (6.0, 0.0)), ("M0 0A5 5 0 0 1 10 0", (10.0, 0.0))):
            with self.subTest(d=d):
                self.assertEqual(pathgeom.subpaths(d)[0][-1], end)

    def test_an_arc_bulges_away_from_its_chord(self):
        # A half circle of radius 5 from (0,0) to (10,0), sweep 1: it passes through y = -5 or 5.
        ys = [y for _, y in pathgeom.subpaths("M0 0A5 5 0 0 1 10 0")[0]]
        self.assertAlmostEqual(max(abs(y) for y in ys), 5.0, delta=0.2)

    def test_arc_flags_packed_against_the_next_number_parse(self):
        # Arc flags are single digits and may touch what follows: "0 011 1" is flags 0,1 then x=1.
        # simple-icons ships this shape (e.g. abstract.svg); a plain number tokenizer reads "011".
        polys = pathgeom.subpaths("M0 0a1 1 0 011 1z")
        self.assertEqual(polys[0][-2], (1.0, 1.0))
        self.assertEqual(pathgeom.subpaths("M0 0a1 1 0 1 0 2 0")[0][-1], (2.0, 0.0))

    def test_an_unknown_command_is_refused(self):
        with self.assertRaises(ValueError):
            pathgeom.subpaths("M0 0 X 3 3")


class AreaTest(unittest.TestCase):
    def test_signed_area_sign_follows_winding(self):
        outer, hole = pathgeom.subpaths(SQUARE_WITH_HOLE)
        self.assertAlmostEqual(abs(pathgeom.signed_area(outer)), 100.0)
        self.assertAlmostEqual(abs(pathgeom.signed_area(hole)), 16.0)
        self.assertLess(pathgeom.signed_area(outer) * pathgeom.signed_area(hole), 0)

    def test_bbox_spans_every_subpath(self):
        self.assertEqual(pathgeom.bbox("M2 3h4v1z M-1 8h1v1z"), (-1.0, 3.0, 6.0, 9.0))


class OuterTest(unittest.TestCase):
    def test_outer_keeps_the_subpaths_wound_like_the_largest_and_drops_the_holes(self):
        outer = pathgeom.outer(SQUARE_WITH_HOLE)
        polys = pathgeom.subpaths(outer)
        self.assertEqual(len(polys), 1)
        self.assertAlmostEqual(abs(pathgeom.signed_area(polys[0])), 100.0)

    def test_outer_rewrites_a_relative_leading_move_so_the_subpath_stands_alone(self):
        # The second subpath's "m" is relative to the first one's start; kept alone it must not move.
        d = "M0 0h10v10h-10z m20 0h10v10h-10z m3 3v4h4v-4z"
        polys = pathgeom.subpaths(pathgeom.outer(d))
        self.assertEqual([p[0] for p in polys], [(0.0, 0.0), (20.0, 0.0)])

    def test_an_island_inside_a_hole_stays_in_the_backplate(self):
        # disc, hole, island: the island winds like the disc and is kept; only the hole goes.
        d = "M0 0H20V20H0Z M4 4V16H16V4Z M8 8H12V12H8Z"
        self.assertEqual(len(pathgeom.subpaths(pathgeom.outer(d))), 2)


if __name__ == "__main__":
    unittest.main()
