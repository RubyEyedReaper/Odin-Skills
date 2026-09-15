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
        self.assertIn('strokeWidth="2"', self.tsx)
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


class StyleAndQuoting(unittest.TestCase):
    def test_style_string_becomes_object(self):
        svg = '<svg viewBox="0 0 1 1"><path d="M0 0" style="fill-opacity:.4;stroke-linecap:round"/></svg>'
        tsx = svg2tsx.convert(svg, "X")
        self.assertIn('style={{"fillOpacity": ".4", "strokeLinecap": "round"}}', tsx)

    def test_braces_in_values_are_quoted_as_expressions(self):
        svg = '<svg viewBox="0 0 1 1"><path d="M0 0" data-note="{x}"/></svg>'
        self.assertIn('data-note={"{x}"}', svg2tsx.convert(svg, "X"))


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

    def test_xml_space_maps_to_jsx_name(self):
        svg = '<svg viewBox="0 0 1 1"><g xml:space="preserve"><path d="M0 0"/></g></svg>'
        tsx = svg2tsx.convert(svg, "X")
        self.assertIn('xmlSpace="preserve"', tsx)
        self.assertNotIn("{http", tsx)

    def test_custom_property_keeps_its_name(self):
        svg = '<svg viewBox="0 0 1 1"><path d="M0 0" style="--accent:red;stroke-width:2"/></svg>'
        self.assertIn('{"--accent": "red", "strokeWidth": "2"}', svg2tsx.convert(svg, "X"))

    def test_barrel_refuses_non_identifier_names(self):
        with self.assertRaises(ValueError):
            svg2tsx.barrel(["my-icon"])


class Barrel(unittest.TestCase):
    def test_sorted_named_and_unique(self):
        out = svg2tsx.barrel(["ZIcon", "AIcon", "AIcon"])
        self.assertEqual(out, 'export { AIcon } from "./AIcon";\nexport { ZIcon } from "./ZIcon";\n')


if __name__ == "__main__":
    unittest.main()
