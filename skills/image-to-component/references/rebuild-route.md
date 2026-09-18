# The rebuild route — mockups, layouts, and anything with text

A mockup screenshot contains four kinds of thing, and only one of them is traced.

| In the mockup | Becomes | Route |
|---|---|---|
| Glyphs, logo marks, illustrations, product cut-outs | SVG + TSX | `i2c.sh`, one asset per run |
| Headings, labels, prices, body copy, button text | real text in semantic markup | typed by hand from the image |
| Cards, panels, buttons, nav, grids, tabs, forms | components built with CSS | `frontend-design` / `interface-design` |
| An app tile, badge disc, status pill or rounded-rect backplate that is the **whole** of one asset | a fitted SVG primitive | `i2c.sh --primitive` |

The last two rows are both containers, and the line between them is not their shape — a card is a
rounded rectangle too. It is whether the container is a **region of the page** or the **entire
content of one crop**. A layout container holds text, state, focus and reflow, so it is CSS; an
in-asset container holds nothing, so it is one `<circle>` or `<rect rx>` instead of a polygon
approximating one. `--primitive` enforces that mechanically — predicates over the keyed alpha
(one component, convex, fills its box, symmetric) and then an adversarial fit that must beat every
other primitive family it could have been. Two shapes that used to refuse are decomposed instead:
a **ring or stroked container** — one hole, concentric with the outline — is one element with a
`stroke-width`, and a **tile with a glyph drawn on it** in a second flat colour is the fitted
backplate plus the glyph traced as a path. Anything with text, an off-centre hole, a third colour or
a second component still refuses and falls through to the row above.

The boundary and its residue: [ADR-0175](../../../docs/adr/0175-in-asset-containers-are-fitted-primitives.md).

`svgcheck` enforces the boundary mechanically: a layout traced as an SVG blows the byte and shape
budget, and the refusal names this file. `evals/rubytech/` records the case — the full logo lockup
(tagline in ~9px type) is refused at 54 KB / 233 shapes, while the mark alone passes at 31 KB.

## Procedure

1. **Inventory.** List every region of the mockup and assign each row of the table above.
2. **Measure tokens from the pixels, don't guess them.** Palette: quantize a crop and read the
   dominant colours. Spacing and radii: measure crop geometry at the mockup's scale factor. Record
   them as CSS custom properties (see `.claude/rules/web/coding-style.md`).
3. **Crop each traceable asset** with a margin, on the cleanest ground the mockup offers — a print
   card or a flat panel beats a textured hero.
4. **Run `i2c.sh` per asset**, then `typecheck.sh` over the directory.
5. **Build the layout** with the design skills, importing the generated components. Text is text.
6. **Compare the built page** against the mockup at the breakpoints in
   `.claude/rules/web/testing.md` — that is visual regression, not this skill's QA.

## Why not trace it anyway

- Text as outlines is invisible to screen readers, search, translation and copy-paste.
- A traced card cannot hover, focus, resize or reflow.
- The file is megabytes of paths nobody can edit, and every design change means re-tracing.
