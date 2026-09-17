"""library: pinned icon libraries, their normalised markup, and the silhouette geometry that indexes them."""
from __future__ import annotations

import os
import unittest

from ._fixtures import SKILL_DIR
from scripts import library, svg2tsx, svgcheck

FIXTURES = os.path.join(SKILL_DIR, "tests", "fixtures", "lib")


def fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def mask(rows: list[str]) -> tuple[bytes, int, int]:
    """'#' opaque, '.' clear, as an alpha-only byte buffer."""
    return bytes(255 if c == "#" else 0 for row in rows for c in row), len(rows[0]), len(rows)


class RefsTest(unittest.TestCase):
    def test_named_candidates_split_into_library_and_slug(self):
        self.assertEqual(library.parse_refs("simple-icons:facebook,material:build"),
                         [("simple-icons", "facebook"), ("material", "build")])

    def test_auto_names_no_candidate(self):
        self.assertIsNone(library.parse_refs("auto"))

    def test_an_unknown_library_or_a_path_like_slug_is_refused(self):
        for bad in ("lucide:wrench", "material:../../etc/passwd", "material:", "facebook", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                library.parse_refs(bad)


class PinsTest(unittest.TestCase):
    def test_pins_come_from_the_toolchain_environment(self):
        pins = library.pins({"I2C_SIMPLE_ICONS": "simple-icons@16.31.0", "I2C_MATERIAL": "0.47.3"})
        self.assertEqual(pins, {"simple-icons": "16.31.0", "material": "0.47.3"})

    def test_a_missing_pin_is_refused_rather_than_defaulted(self):
        with self.assertRaisesRegex(ValueError, "toolchain.sh"):
            library.pins({"I2C_SIMPLE_ICONS": "simple-icons@16.31.0"})

    def test_icon_files_resolve_inside_the_versioned_cache(self):
        pins = {"simple-icons": "16.31.0", "material": "0.47.3"}
        self.assertEqual(library.icon_file("/c", pins, "simple-icons", "x"),
                         "/c/simple-icons@16.31.0/package/icons/x.svg")
        self.assertEqual(library.icon_file("/c", pins, "material", "alarm", weight=700),
                         "/c/material-symbols-svg-700@0.47.3/package/outlined/alarm.svg")

    def test_a_material_weight_off_the_published_set_is_refused(self):
        with self.assertRaises(ValueError):
            library.icon_file("/c", {"simple-icons": "1", "material": "1"}, "material", "alarm", weight=450)


class NormaliseTest(unittest.TestCase):
    def test_simple_icons_loses_role_and_title_and_keeps_its_view_box(self):
        icon = library.normalise(fixture("simple-icons-facebook.svg"))
        self.assertEqual(icon.view_box, (0.0, 0.0, 24.0, 24.0))
        self.assertEqual(len(icon.paths), 1)
        self.assertNotIn("role", library.to_svg(icon))
        self.assertNotIn("title", library.to_svg(icon))

    def test_material_keeps_its_negative_view_box_and_drops_its_size(self):
        icon = library.normalise(fixture("material-alarm.svg"))
        self.assertEqual(icon.view_box, (0.0, -960.0, 960.0, 960.0))
        self.assertNotIn("width", library.to_svg(icon))

    def test_normalised_markup_is_inside_the_pipeline_dialect(self):
        for name in ("simple-icons-facebook.svg", "material-alarm.svg", "material-error-fill.svg"):
            with self.subTest(name=name):
                svg = library.to_svg(library.normalise(fixture(name)), fills=["#0866FF"])
                self.assertEqual(svgcheck.check(svg, "icon"), [])
                svg2tsx.convert(svg, "Probe")  # raises outside the dialect

    def test_a_backplate_path_is_drawn_first(self):
        icon = library.normalise(fixture("material-error-fill.svg"))
        svg = library.to_svg(icon, fills=["#E11D2E"], backplate=("M0 0H1V1H0Z", "#FFFFFF"))
        self.assertLess(svg.index('fill="#FFFFFF"'), svg.index('fill="#E11D2E"'))

    def test_markup_outside_a_single_path_icon_is_refused(self):
        for bad in ('<svg viewBox="0 0 24 24"><circle r="3"/></svg>',
                    '<svg viewBox="0 0 24 24"><path d="M0 0h1" style="x"/></svg>',
                    '<svg><path d="M0 0h1"/></svg>',
                    '<svg viewBox="0 0 24 24"></svg>'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                library.normalise(bad)


class GeometryTest(unittest.TestCase):
    def test_moments_find_the_centre_and_spread_of_the_ink(self):
        buf, w, h = mask(["....", ".##.", ".##.", "...."])
        cx, cy, r, mass = library.moments(buf, w, h)
        self.assertEqual((cx, cy, mass), (2.0, 2.0, 4.0))
        self.assertAlmostEqual(r, (0.25 + 0.25 + 2 / 12) ** 0.5)  # two pixel-box variances

    def test_moments_of_empty_ink_are_refused(self):
        with self.assertRaises(ValueError):
            library.moments(bytes(16), 4, 4)

    def test_descriptors_count_enclosed_holes_but_not_open_ground(self):
        ring, w, h = mask(["#####", "#...#", "#.#.#", "#...#", "#####"])
        self.assertEqual(library.descriptors(ring, w, h)["holes"], 1)
        cup, w, h = mask(["#...#", "#...#", "#####"])
        self.assertEqual(library.descriptors(cup, w, h)["holes"], 0)

    def test_descriptors_measure_aspect_and_fill_inside_the_ink_box(self):
        buf, w, h = mask(["......", ".####.", ".#..#.", ".####.", "......"])
        d = library.descriptors(buf, w, h)
        self.assertAlmostEqual(d["aspect"], 4 / 3)
        self.assertAlmostEqual(d["fill"], 10 / 12)

    def test_thumbnail_is_size_squared_and_ignores_where_the_ink_sits(self):
        a, w, h = mask(["##......", "##......", "........", "........"])
        b, _, _ = mask(["........", "........", "......##", "......##"])
        ta, tb = library.thumbnail(a, w, h, 8), library.thumbnail(b, w, h, 8)
        self.assertEqual(len(ta), 64)
        self.assertEqual(ta, tb)

    def test_thumbnail_follows_the_shape_not_the_scale(self):
        small, w, h = mask(["........", ".##.....", ".##.....", "........"])
        big, W, H = mask(["........", "####....", "####....", "####....", "####....", "........"])
        self.assertLess(sum(abs(x - y) for x, y in zip(library.thumbnail(small, w, h, 8),
                                                        library.thumbnail(big, W, H, 8))) / 64, 2)


class IndexEntryTest(unittest.TestCase):
    def test_an_entry_places_the_ink_in_view_box_units(self):
        # A 2x2 block at pixels 4..6 of an 8 px render of a Material viewBox (120 units per pixel).
        buf, w, h = mask(["........"] * 4 + ["....##..", "....##.."] + ["........"] * 2)
        entry = library.index_entry(buf, w, h, (0.0, -960.0, 960.0, 960.0))
        self.assertEqual((entry["cx"], entry["cy"]), (600.0, -360.0))
        self.assertAlmostEqual(entry["r"], (0.5 + 2 / 12) ** 0.5 * 120, places=3)
        self.assertEqual(entry["holes"], 0)
        self.assertEqual(len(bytes.fromhex(entry["thumb"])), library.THUMB_SIZE ** 2)

    def test_an_icon_that_renders_no_ink_has_no_entry(self):
        self.assertIsNone(library.index_entry(bytes(64), 8, 8, (0.0, 0.0, 24.0, 24.0)))


class BlurredThumbTest(unittest.TestCase):
    def test_a_blurred_thumbnail_spreads_ink_but_keeps_its_mass_centred(self):
        thumb = bytes(255 if (x, y) == (3, 3) else 0 for y in range(7) for x in range(7))
        out = library.blur_thumb(thumb, 7, 1.0)
        self.assertEqual(out[3 * 7 + 3], max(out))
        self.assertGreater(out[3 * 7 + 2], 0)
        self.assertEqual(out[3 * 7 + 2], out[3 * 7 + 4])
        self.assertEqual(out[2 * 7 + 3], out[4 * 7 + 3])

    def test_zero_sigma_is_the_thumbnail_itself(self):
        thumb = bytes(range(0, 250, 10))[:25]
        self.assertEqual(library.blur_thumb(thumb, 5, 0.0), thumb)

    def test_an_index_row_carries_a_thumbnail_per_blur_level(self):
        buf, w, h = mask(["........", "..####..", "..####..", "..####..", "..####..", "........", "........", "........"])
        entry = library.index_entry(buf, w, h, (0.0, 0.0, 24.0, 24.0))
        self.assertEqual(len(entry["thumbs"]), len(library.THUMB_BLURS))
        self.assertEqual(entry["thumbs"][0], entry["thumb"])


if __name__ == "__main__":
    unittest.main()
