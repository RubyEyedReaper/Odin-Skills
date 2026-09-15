# QA thresholds

`scripts/render_diff.py` renders the optimized SVG with resvg at the reference raster's exact size
and scores it with `scripts/diffmetric.py`. Defaults live in `DEFAULT_THRESHOLDS` there.

| Metric | Default | Catches |
|---|---|---|
| `iou` — alpha silhouette overlap (α ≥ 128) | ≥ 0.95 | missing or extra shapes, lost transparency, background left in |
| `mae` — mean abs RGB error on visible pixels, 0–255 | ≤ 12 | wrong colours, merged regions, over-quantization |
| `edge_f1` — Sobel edge agreement within ±1px | ≥ 0.80 | drifted outlines, lost detail, over-smoothing |
| `jaggedness` — the render's outline zig-zag finer than its shape (`scripts/jaggedness.py`) | ≤ 15 | pixel staircases and tracer wobble, which IoU and edge_f1 both absorb |

## Rules

- **The reference is the keyed, scaled raster, never the trace input.** Scoring against the
  quantized or thresholded image hides exactly the loss those steps introduce. Observed: the same
  mark scored MAE 4.9 against its quantized input and 31.8 against the real reference.
- **`--mono`** (set automatically for `currentColor`) paints both images black before scoring, and
  takes the reference's silhouette at alpha ≥ 128. A component with no colour of its own has only a
  silhouette to compare; a soft-matted reference's edge ramp is otherwise too wide for Sobel to read.
- **A threshold is changed in `DEFAULT_THRESHOLDS`, with a reason, and never per run to get a
  pass.** Per-run `--iou/--mae/--edge-f1` exist for measuring, not for shipping.
- Read `<Name>.compare.png` too — source, render, and amplified difference side by side. The numbers
  decide; the sheet tells you which flag to change.

## Why jaggedness is 15

Excess turning — absolute minus net — along 3 px chords, less the same along 12 px chords, per
pixel of outline, times the image diagonal. A real corner persists at both chords and cancels; a
stair or a wobble alternates at 3 px and has vanished by 12. Measured, render-side:

| Outline | jaggedness |
|---|---|
| anti-aliased disc; any convex polygon | 0–0.3 |
| RubyTech glyphs at the soft-matte flags | 2.3–2.5 |
| anti-aliased 8-tooth gear (real corners) | 5.6 |
| RubyTech glyphs at the old hard-key flags | 2.9–8.9 |
| RubyTechMark, 32 colours, soft matte | 12.4 |
| RubyTechMark, 32 colours, hard key | 19.5 |
| hard-keyed disc upscaled ×4 with LANCZOS | 22.4 |
| stepped diamond (8 px stairs), `tests/test_diffmetric.py` | 22.3 |
| nearest-neighbour ×4 staircase disc | 40.1 |

15 clears every asset at the flags the evals ship and refuses the hard-keyed mark and every
staircase measured. `reference_jaggedness` in `qa.json` is the prepared raster's own score — context
for reading the render's, never a bound.

## Known limits

- MAE on soft anti-aliased edges is inflated by the α ≥ 128 cut; a thin-stroke logo can fail `mae`
  while looking correct. Prefer re-cropping at a larger `--scale` over loosening.
- Gradients and glows do not survive flat-fill tracing. If `mae` cannot pass without breaching the
  budget, the asset needs a hand-authored SVG gradient, not a looser threshold.
