# QA thresholds

`scripts/render_diff.py` renders the optimized SVG with resvg at the reference raster's exact size
and scores it with `scripts/diffmetric.py`. Defaults live in `DEFAULT_THRESHOLDS` there.

| Metric | Default | Catches |
|---|---|---|
| `iou` — alpha silhouette overlap (α ≥ 128) | ≥ 0.95 | missing or extra shapes, lost transparency, background left in |
| `mae` — mean abs RGB error on visible pixels, 0–255 | ≤ 12 | wrong colours, merged regions, over-quantization |
| `edge_f1` — Sobel edge agreement within ±1px | ≥ 0.80 | jagged or drifted outlines, lost detail, over-smoothing |
| `scale_smoke` — renders at 24px wide and at 4× | both visible | an asset that vanishes or fails to render when resized |

## Rules

- **The reference is the keyed, scaled raster, never the trace input.** Scoring against the
  quantized or thresholded image hides exactly the loss those steps introduce. Observed: the same
  mark scored MAE 4.9 against its quantized input and 31.8 against the real reference.
- **`--mono`** (set automatically for `currentColor`) paints both images black before scoring. A
  component with no colour of its own has only a silhouette to compare.
- **A threshold is changed in `DEFAULT_THRESHOLDS`, with a reason, and never per run to get a
  pass.** Per-run `--iou/--mae/--edge-f1` exist for measuring, not for shipping.
- Read `<Name>.compare.png` too — source, render, and amplified difference side by side. The numbers
  decide; the sheet tells you which flag to change.

## Known limits

- MAE on soft anti-aliased edges is inflated by the α ≥ 128 cut; a thin-stroke logo can fail `mae`
  while looking correct. Prefer re-cropping at a larger `--scale` over loosening.
- Gradients and glows do not survive flat-fill tracing. If `mae` cannot pass without breaching the
  budget, the asset needs a hand-authored SVG gradient, not a looser threshold.
