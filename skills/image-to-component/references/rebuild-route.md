# The rebuild route — mockups, layouts, and anything with text

A mockup screenshot contains three kinds of thing, and only one of them is traced.

| In the mockup | Becomes | Route |
|---|---|---|
| Glyphs, logo marks, illustrations, product cut-outs | SVG + TSX | `i2c.sh`, one asset per run |
| Headings, labels, prices, body copy, button text | real text in semantic markup | typed by hand from the image |
| Cards, panels, buttons, nav, grids, tabs, forms | components built with CSS | `frontend-design` / `interface-design` |

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
