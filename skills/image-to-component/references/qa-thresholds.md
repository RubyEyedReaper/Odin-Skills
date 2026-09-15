# QA thresholds

`scripts/render_diff.py` renders the optimized SVG with resvg at the reference raster's exact size
and scores it with `scripts/diffmetric.py`. Defaults live in `DEFAULT_THRESHOLDS` there.

| Metric | Default | Catches |
|---|---|---|
| `iou` — alpha silhouette overlap (α ≥ 128) | ≥ 0.95 | missing or extra shapes, lost transparency, background left in |
| `mae` — mean abs RGB error on visible pixels, 0–255 | ≤ 12 | wrong colours, merged regions, over-quantization |
| `edge_f1` — Sobel edge agreement within ±1px | ≥ 0.80 | drifted outlines, lost detail, over-smoothing |
| `jaggedness` — the render's outline zig-zag finer than its shape (`scripts/jaggedness.py`) | ≤ 15 | pixel staircases and tracer wobble, which IoU and edge_f1 both absorb |
| `staircase` — share of a hard source's one-pixel steps the render keeps (`scripts/jaggedness.py`) | ≤ 0.35 | an aliased source's steps traced at `--scale` ≥ 2, which `jaggedness` reads as real corners. Scored only when prep reports a hard source edge; `null` otherwise |

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

## Why staircase exists, and why 0.35

`jaggedness` walks strides fixed in render pixels. At `--scale 8` a one-pixel source step is 8 px
long, a real corner at both strides, so it never cancels: on the aliased wrench `--smooth 3` kept
every step and scored 6.76, `--smooth 7` scored 7.55 (#1353).

Striding in source pixels instead does not fix it on its own. Scaled strides make the score
scale-invariant and just as blind (3.52 vs 1.19 at best), and no render-only statistic tried —
turning, displacement from a moving average, grid phase, turning autocorrelation — ranked the
stepped wrench above a degraded gear's genuine wobble. The render alone cannot tell a kept
staircase from small shape.

The reference can. `staircase` is excess turning at a stride of one source pixel less two source
pixels, render over reference: 1.0 is every step kept, 0 none. `scripts/edges.py` decides whether
the source was hard (≥ 75 % of alpha-128 crossings with no partial coverage on either side) before
prep upscales it; a soft reference's turning is its shape, and a faithful render keeps 0.65–0.85 of
it, so the bound would refuse exactly the runs that are right.

Measured on the four RubyTech glyphs made hard-alpha, at full size (42–54 px) and ×0.6 (25–32 px),
traced at `--scale` 4, 6 and 8:

| Run | staircase |
|---|---|
| Gaussian `--smooth` 0.375 × scale (steps visibly kept) | 0.36–0.65 |
| Gaussian `--smooth` 0.9 × scale (steps gone, detail lost on ×0.6) | 0.10–0.37 |
| `--smooth auto` on a hard source — outline smoothing | 0.09–0.34 |
| `evals/degraded` aliased wrench, `--smooth 3` / `7` / `9` | 0.41 / 0.14 / 0.11 |

The overlap is the 25–32 px set: the ×0.6 gear keeps 0.33–0.37 whatever removes its steps, because
its teeth are one source pixel deep. Everything else separates with room either side of 0.35.

## Known limits

- MAE on soft anti-aliased edges is inflated by the α ≥ 128 cut; a thin-stroke logo can fail `mae`
  while looking correct. Prefer re-cropping at a larger `--scale` over loosening.
- `staircase` needs `--scale` ≥ 2 and a hard source. A soft low-resolution source traced with a
  visible stair residue is not bounded by it; its only bound is `jaggedness`.
- Gradients and glows do not survive flat-fill tracing. If `mae` cannot pass without breaching the
  budget, the asset needs a hand-authored SVG gradient, not a looser threshold.
