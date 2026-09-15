"""svgcheck: is this SVG safe, scalable, and small enough to be a component?

Each finding is asserted by its code *and* its message where the message is the remedy —
a budget breach must name the rebuild route, because a budget that only says "too big"
sends the next agent to tune the tracer harder on a layout that should never be traced.
"""
from __future__ import annotations

import unittest

from ._fixtures import TRACED_SVG
from scripts import svgcheck


def codes(findings):
    return sorted(f.code for f in findings)


class Clean(unittest.TestCase):
    def test_minimal_icon_passes(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2 2h20v20z" fill="#000"/></svg>'
        self.assertEqual(svgcheck.check(svg, kind="icon"), [])


class Structure(unittest.TestCase):
    def test_missing_viewbox(self):
        self.assertIn("no-viewbox", codes(svgcheck.check(TRACED_SVG, kind="logo")))

    def test_parse_error(self):
        self.assertEqual(codes(svgcheck.check("<svg", kind="icon")), ["parse-error"])

    def test_forbidden_elements_and_handlers(self):
        svg = ('<svg viewBox="0 0 4 4"><script/><foreignObject/><image href="x.png"/>'
               '<path d="M0 0" onload="x()"/></svg>')
        found = codes(svgcheck.check(svg, kind="icon"))
        self.assertEqual(found.count("forbidden-element"), 3)
        self.assertIn("event-handler", found)

    def test_bad_viewbox_reported(self):
        for vb in ("0 0 10", "0 0 1 1&quot; x=&quot;", "a b c d"):
            svg = f'<svg viewBox="{vb}"><path d="M0 0"/></svg>'
            self.assertIn("bad-viewbox", codes(svgcheck.check(svg, kind="icon")), vb)

    def test_style_element_and_external_url_paint(self):
        svg = ('<svg viewBox="0 0 4 4"><style>@import url(https://x);</style>'
               '<path d="M0 0" fill="url(https://evil/#g)"/><path d="M0 0" fill="url(#ok)"/></svg>')
        found = codes(svgcheck.check(svg, kind="icon"))
        self.assertEqual(found, ["external-ref", "forbidden-element"])

    def test_use_is_forbidden_in_both_modules(self):
        from scripts import svg2tsx
        self.assertIs(svg2tsx.FORBIDDEN, svgcheck.FORBIDDEN)
        self.assertIn("use", svgcheck.FORBIDDEN)

    def test_external_reference(self):
        svg = '<svg viewBox="0 0 4 4"><a href="https://evil/x"/><a href="#ok"/></svg>'
        self.assertEqual(codes(svgcheck.check(svg, kind="icon")), ["external-ref"])

    def test_embedded_raster_data_uri_is_forbidden_image(self):
        svg = '<svg viewBox="0 0 4 4"><image href="data:image/png;base64,AAAA"/></svg>'
        self.assertEqual(codes(svgcheck.check(svg, kind="icon")), ["forbidden-element"])


class Background(unittest.TestCase):
    def test_full_bleed_opaque_rect(self):
        svg = '<svg viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/><path d="M1 1h2"/></svg>'
        self.assertIn("opaque-background", codes(svgcheck.check(svg, kind="icon")))

    def test_full_bleed_rect_path(self):
        svg = '<svg viewBox="0 0 10 10"><path d="M0 0H10V10H0Z" fill="#101010"/><path d="M1 1h2"/></svg>'
        self.assertIn("opaque-background", codes(svgcheck.check(svg, kind="icon")))

    def test_svgo_compact_numbers_parse(self):
        # SVGO writes "4.32.01" for "4.32 0.01"; seen on the first real RubyTech icon run.
        svg = '<svg viewBox="0 0 10 10"><path d="M4.32.01 1.5.5.2.2Z" fill="#000"/></svg>'
        self.assertEqual(svgcheck.check(svg, kind="icon"), [])
        bleed = '<svg viewBox="0 0 10 10"><path d="M0 0H10V10H.0Z" fill="#000"/></svg>'
        self.assertIn("opaque-background", codes(svgcheck.check(bleed, kind="icon")))

    def test_partial_or_transparent_rect_is_fine(self):
        for rect in ('<rect width="5" height="10" fill="#fff"/>',
                     '<rect width="10" height="10" fill="none"/>',
                     '<rect width="10" height="10" fill="#fff" opacity="0.2"/>'):
            svg = f'<svg viewBox="0 0 10 10">{rect}</svg>'
            self.assertNotIn("opaque-background", codes(svgcheck.check(svg, kind="icon")), rect)

    def test_background_allowed_when_declared(self):
        svg = '<svg viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/></svg>'
        self.assertEqual(svgcheck.check(svg, kind="icon", allow_background=True), [])


class Budget(unittest.TestCase):
    def many_paths(self, n):
        return '<svg viewBox="0 0 10 10">' + '<path d="M0 0h1"/>' * n + "</svg>"

    def test_path_budget_per_kind(self):
        limit = svgcheck.BUDGETS["icon"]["paths"]
        self.assertEqual(svgcheck.check(self.many_paths(limit), kind="icon"), [])
        found = svgcheck.check(self.many_paths(limit + 1), kind="icon")
        self.assertEqual(codes(found), ["budget-paths"])
        self.assertIn("rebuild-route.md", found[0].message)

    def test_byte_budget(self):
        limit = svgcheck.BUDGETS["icon"]["bytes"]
        svg = '<svg viewBox="0 0 10 10"><path d="M0 0' + " l1 1" * (limit // 5) + '"/></svg>'
        self.assertIn("budget-bytes", codes(svgcheck.check(svg, kind="icon")))

    def test_illustration_budget_is_larger(self):
        svg = self.many_paths(svgcheck.BUDGETS["icon"]["paths"] + 1)
        self.assertEqual(svgcheck.check(svg, kind="illustration"), [])

    def test_unknown_kind_refused(self):
        with self.assertRaises(ValueError):
            svgcheck.check('<svg viewBox="0 0 1 1"/>', kind="webpage")


class Cli(unittest.TestCase):
    def test_exit_codes(self):
        import io
        import os
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            good = os.path.join(d, "g.svg")
            bad = os.path.join(d, "b.svg")
            with open(good, "w") as fh:
                fh.write('<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>')
            with open(bad, "w") as fh:
                fh.write('<svg><path d="M0 0"/></svg>')
            self.assertEqual(svgcheck.main([good, "--kind", "icon"]), 0)
            self.assertEqual(svgcheck.main([bad, "--kind", "icon"]), 1)
            self.assertEqual(svgcheck.main([os.path.join(d, "missing.svg"), "--kind", "icon"]), 2)


if __name__ == "__main__":
    unittest.main()
