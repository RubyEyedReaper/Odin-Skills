"""svg2tsx: traced SVG text in, a typed React component out.

Asserts the emitted source, not the converter's internals: the viewBox survives, attributes
become JSX names, the a11y contract holds in both labelled and decorative use, currentColor
mode rewrites paint but never `none`, and unsafe input is refused rather than transcribed.
"""
from __future__ import annotations

import unittest

from ._fixtures import GLYPH_SVG, TRACED_SVG
from scripts import svg2tsx


class ComponentName(unittest.TestCase):
    def test_pascal_cases_file_style_names(self):
        self.assertEqual(svg2tsx.component_name("ruby-tech_logo"), "RubyTechLogo")
        self.assertEqual(svg2tsx.component_name("search icon"), "SearchIcon")

    def test_leading_digit_gets_prefix(self):
        self.assertEqual(svg2tsx.component_name("404-illustration"), "Svg404Illustration")

    def test_empty_name_refused(self):
        with self.assertRaises(ValueError):
            svg2tsx.component_name("--")


class Convert(unittest.TestCase):
    def setUp(self):
        self.tsx = svg2tsx.convert(TRACED_SVG, "RubyTechLogo")

    def test_viewbox_derived_from_width_height(self):
        self.assertIn('viewBox="0 0 64 48"', self.tsx)
        self.assertNotIn('width="64"', self.tsx)

    def test_typed_props_extend_svg_props(self):
        self.assertIn("export interface RubyTechLogoProps extends SVGProps<SVGSVGElement>", self.tsx)
        self.assertIn("title?: string;", self.tsx)
        self.assertIn("export function RubyTechLogo(", self.tsx)
        self.assertIn("export default RubyTechLogo;", self.tsx)

    def test_hyphenated_attributes_become_jsx_names(self):
        self.assertIn('fillRule="evenodd"', self.tsx)
        self.assertIn('fillOpacity="0.8"', self.tsx)
        self.assertNotIn("fill-rule", self.tsx)

    def test_paint_and_geometry_preserved(self):
        self.assertIn('d="M0 0h10v10H0z"', self.tsx)
        self.assertIn('fill="#E11D2E"', self.tsx)
        self.assertIn('transform="translate(4 4)"', self.tsx)
        self.assertIn('opacity="0.5"', self.tsx)

    def test_source_title_comment_and_prolog_dropped(self):
        self.assertNotIn("ignored", self.tsx)
        self.assertNotIn("VTracer", self.tsx)
        self.assertNotIn("<?xml", self.tsx)

    def test_accessibility_contract(self):
        # Labelled when a title or aria-label is given, hidden otherwise.
        self.assertIn("useId()", self.tsx)
        self.assertIn('role={labelled ? "img" : undefined}', self.tsx)
        self.assertIn("aria-hidden={labelled ? undefined : true}", self.tsx)
        self.assertIn("{title ? <title id={titleId}>{title}</title> : null}", self.tsx)
        self.assertIn('props["aria-label"]', self.tsx)

    def test_props_spread_after_defaults(self):
        root = self.tsx[self.tsx.index("<svg"): self.tsx.index(">", self.tsx.index("{...props}"))]
        self.assertLess(root.index('viewBox='), root.index("{...props}"))


class CurrentColor(unittest.TestCase):
    def test_paint_rewritten_but_none_kept(self):
        svg = '<svg viewBox="0 0 8 8"><path d="M0 0h8" fill="#fff" stroke="none"/></svg>'
        tsx = svg2tsx.convert(svg, "Mono", color_mode="currentColor")
        self.assertIn('fill="currentColor"', tsx)
        self.assertIn('stroke="none"', tsx)
        self.assertNotIn("#fff", tsx)

    def test_fill_less_glyph_inherits_text_colour(self):
        # The incident: every shipped currentColor glyph had no fill, so it rendered black.
        tsx = svg2tsx.convert(GLYPH_SVG, "WrenchIcon", color_mode="currentColor")
        root = tsx[tsx.index("<svg"): tsx.index(">", tsx.index("{...props}"))]
        self.assertIn('fill="currentColor"', root)
        self.assertLess(root.index('fill="currentColor"'), root.index("{...props}"))

    def test_original_mode_adds_no_root_paint(self):
        tsx = svg2tsx.convert(GLYPH_SVG, "WrenchIcon")
        self.assertNotIn("fill=", tsx)

    def test_original_mode_leaves_paint(self):
        svg = '<svg viewBox="0 0 8 8"><path d="M0 0h8" fill="#fff"/></svg>'
        self.assertIn('fill="#fff"', svg2tsx.convert(svg, "Mono"))

    def test_unknown_mode_refused(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert('<svg viewBox="0 0 1 1"/>', "X", color_mode="blue")


class Refusals(unittest.TestCase):
    def test_no_viewbox_and_no_size_refused(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert('<svg><path d="M0 0"/></svg>', "X")

    def test_script_and_image_refused(self):
        for bad in ('<svg viewBox="0 0 1 1"><script>x</script></svg>',
                    '<svg viewBox="0 0 1 1"><image href="a.png"/></svg>',
                    '<svg viewBox="0 0 1 1"><path d="M0 0" onclick="x()"/></svg>'):
            with self.assertRaises(ValueError, msg=bad):
                svg2tsx.convert(bad, "X")

    def test_non_svg_root_refused(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert("<html/>", "X")


class Dialect(unittest.TestCase):
    """svg2tsx transcribes what vtracer + SVGO emit and refuses the rest by name (#1352).

    A general SVG→JSX surface — style objects, namespaced and data attributes, text, shapes — was
    untested against any real input and wider than any trace. Hand-authored SVG is a component to
    write, not to transcribe.
    """

    def test_elements_outside_the_dialect_are_refused_by_name(self):
        for tag in ("text", "linearGradient", "polygon", "line"):
            with self.assertRaisesRegex(ValueError, rf"<{tag}> is outside the dialect", msg=tag):
                svg2tsx.convert(f'<svg viewBox="0 0 1 1"><{tag}/></svg>', "X")

    def test_attributes_outside_paint_and_geometry_are_refused_by_name(self):
        for attr in ('style="fill:red"', 'class="a"', 'data-note="{x}"', 'stroke-width="2"',
                     'xml:space="preserve"', 'id="p"'):
            with self.assertRaisesRegex(ValueError, "outside the dialect", msg=attr):
                svg2tsx.convert(f'<svg viewBox="0 0 1 1"><path d="M0 0" {attr}/></svg>', "X")

    def test_the_cli_names_the_dialect_in_its_refusal(self):
        import io
        import os
        import tempfile
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.svg")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write('<svg viewBox="0 0 1 1"><text>hi</text></svg>')
            err = io.StringIO()
            with redirect_stderr(err):
                rc = svg2tsx.main([src, "--name", "X", "--out", os.path.join(tmp, "X.tsx")])
            self.assertEqual(rc, 1)
            self.assertIn("svg2tsx: refused: <text> is outside the dialect", err.getvalue())
            self.assertFalse(os.path.exists(os.path.join(tmp, "X.tsx")))


class PrimitiveDialect(unittest.TestCase):
    """DEC-0186 widened the dialect to the three primitive elements a fitted container is emitted as.

    A radius expressed as path data is a number nowhere, which is the defect ADR-0175 exists to
    remove — so the primitive reaches the component as `<circle>`, `<rect rx>` or `<ellipse>`, and
    the attribute allow-list is PER ELEMENT so the refusal that stops a foreign SVG being
    transcribed keeps its precision.
    """

    def test_a_circle_is_transcribed(self):
        tsx = svg2tsx.convert('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>', "Disc")
        self.assertIn('<circle cx="12" cy="12" r="8" />', tsx)

    def test_a_rounded_rect_keeps_its_radius_as_a_number(self):
        tsx = svg2tsx.convert(
            '<svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="4"/></svg>', "Tile")
        self.assertIn('rx="4"', tsx)

    def test_an_ellipse_is_transcribed(self):
        tsx = svg2tsx.convert('<svg viewBox="0 0 24 24"><ellipse cx="12" cy="8" rx="10" ry="6"/></svg>', "E")
        self.assertIn('<ellipse cx="12" cy="8" rx="10" ry="6" />', tsx)

    def test_a_primitives_geometry_attribute_is_refused_on_a_path(self):
        with self.assertRaisesRegex(ValueError, "outside the dialect"):
            svg2tsx.convert('<svg viewBox="0 0 1 1"><path d="M0 0" cx="1"/></svg>', "X")

    def test_a_paths_geometry_attribute_is_refused_on_a_circle(self):
        with self.assertRaisesRegex(ValueError, "outside the dialect"):
            svg2tsx.convert('<svg viewBox="0 0 1 1"><circle cx="1" cy="1" r="1" d="M0 0"/></svg>', "X")

    def test_a_rect_attribute_is_refused_on_a_circle(self):
        with self.assertRaisesRegex(ValueError, "outside the dialect"):
            svg2tsx.convert('<svg viewBox="0 0 1 1"><circle cx="1" cy="1" r="1" width="2"/></svg>', "X")

    def test_a_primitive_takes_currentcolor_like_a_path_does(self):
        tsx = svg2tsx.convert('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="#e11d2e"/></svg>',
                              "Disc", color_mode="currentColor")
        self.assertIn('fill="currentColor"', tsx)
        self.assertNotIn("#e11d2e", tsx)


    def test_a_stroked_primitive_carries_its_stroke_width(self):
        """harness:RM-0679: a ring or a stroked tile is ONE element with a stroke width, so the width
        is a number a reader edits. It is legal on the three primitive elements and nowhere else —
        a traced path never carries one, and the refusal above still says so."""
        svg = ('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="#e11d2e"'
               ' stroke-width="2"/></svg>')
        tsx = svg2tsx.convert(svg, "Ring", color_mode="currentColor")
        self.assertIn('fill="none"', tsx)
        self.assertIn('stroke="currentColor"', tsx)
        self.assertIn('strokeWidth="2"', tsx)


class ReviewFindings(unittest.TestCase):
    """Each case is an input an adversarial review ran against the converter and broke it."""

    def test_viewbox_injection_refused(self):
        svg = '<svg viewBox="0 0 1 1&quot; onClick={()=&gt;alert(1)} x=&quot;"><path d="M0 0"/></svg>'
        with self.assertRaises(ValueError):
            svg2tsx.convert(svg, "X")

    def test_viewbox_must_be_four_numbers(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert('<svg viewBox="0 0 10"><path d="M0 0"/></svg>', "X")

    def test_style_element_and_external_paint_refused(self):
        for bad in ('<svg viewBox="0 0 1 1"><style>@import url(https://x/a.css);</style></svg>',
                    '<svg viewBox="0 0 1 1"><path d="M0 0" fill="url(https://evil/#g)"/></svg>'):
            with self.assertRaises(ValueError, msg=bad):
                svg2tsx.convert(bad, "X")

    def test_local_paint_reference_allowed(self):
        svg = '<svg viewBox="0 0 1 1"><path d="M0 0" fill="url(#g)"/></svg>'
        self.assertIn('fill="url(#g)"', svg2tsx.convert(svg, "X"))

    def test_barrel_refuses_non_identifier_names(self):
        with self.assertRaises(ValueError):
            svg2tsx.barrel(["my-icon"])


class Barrel(unittest.TestCase):
    def test_sorted_named_and_unique(self):
        out = svg2tsx.barrel(["ZIcon", "AIcon", "AIcon"])
        self.assertEqual(out, 'export { AIcon } from "./AIcon";\nexport { ZIcon } from "./ZIcon";\n')


class ReplacementComponent(unittest.TestCase):
    """What a --replace run adds: provenance in a header comment, and a size prop on the declared scale."""

    HEADER = ["Material Symbols 0.47.3 outlined/alarm, weight 400 — Apache-2.0, Copyright Google LLC"]

    def test_a_header_is_emitted_as_a_leading_comment_block(self):
        tsx = svg2tsx.convert(GLYPH_SVG, "AlarmIcon", header=self.HEADER)
        self.assertTrue(tsx.startswith("/**\n * Material Symbols 0.47.3 outlined/alarm"))
        self.assertLess(tsx.index(" */"), tsx.index("import "))

    def test_a_header_line_cannot_close_the_comment_early(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert(GLYPH_SVG, "AlarmIcon", header=["evil */ export const x = 1;"])

    def test_size_becomes_a_prop_defaulting_to_the_snapped_step_that_the_caller_overrides(self):
        tsx = svg2tsx.convert(GLYPH_SVG, "AlarmIcon", size=24)
        self.assertIn("size?: number | string;", tsx)
        self.assertIn("{ title, size = 24, ...props }", tsx)
        self.assertLess(tsx.index("width={size}"), tsx.index("{...props}"))
        self.assertIn("height={size}", tsx)

    def test_without_either_the_component_is_byte_identical_to_before(self):
        self.assertEqual(svg2tsx.convert(GLYPH_SVG, "GearIcon", "currentColor"),
                         svg2tsx.convert(GLYPH_SVG, "GearIcon", "currentColor", header=None, size=None))
        self.assertNotIn("size", svg2tsx.convert(GLYPH_SVG, "GearIcon"))

    def test_a_non_positive_size_is_refused(self):
        with self.assertRaises(ValueError):
            svg2tsx.convert(GLYPH_SVG, "AlarmIcon", size=0)


if __name__ == "__main__":
    unittest.main()
