# Tracing presets

Source of truth: `PRESETS` in `scripts/trace.py`. This file says why, not what — read the numbers
there. Override one per run with `--set key=value`; a change that should outlive the run belongs in
`PRESETS` plus a regenerated `evals/rubytech/`.

## vtracer parameters that matter

| Parameter | Raises → | Lowers → |
|---|---|---|
| `filter_speckle` | drops more small blobs; fewer paths | keeps anti-alias crumbs as paths |
| `color_precision` | more colour bits kept; more layers | merges nearby shades |
| `layer_difference` | fewer, broader colour layers | a layer per gradient step |
| `corner_threshold` | rounder corners | sharper corners (UI geometry) |
| `length_threshold` | fewer, longer segments | wobble on noisy edges |
| `path_precision` | more decimals; bigger file | SVGO trims to 2 anyway |

`hierarchical=stacked` keeps overlapping regions stacked in draw order, so a black glyph over a red
facet renders correctly. `mode=spline` gives Bézier curves; `polygon` suits pixel art only.

## Prep flags, and the failure each one answers

| Flag | Failure without it |
|---|---|
| `--key flood` (default) | a flat background colour is traced as a full-bleed path — `svgcheck` reports `opaque-background` |
| `--key global` | a glyph's enclosed holes (gear centre, wrench eye) stay opaque, because flood fill cannot reach them from the edge |
| `--color currentColor` → silhouette trace input | vtracer's binary mode ignores alpha; an RGBA input traces as one square covering the viewBox |
| `--matte soft` | a soft, anti-aliased, glowing or blurred edge is keyed at the tolerance boundary, so strokes fatten and holes close. RubyTech glyphs: jaggedness 2.9–8.9 → 2.3–2.5; degraded glyphs: agreement with the clean trace 0.57–0.66 → 0.69–0.84 |
| `--smooth R` | an upscaled glyph traces its pixel staircase as wobble. Scale it with `--scale`: at `--scale 4`, `1.5` held IoU ≥ 0.96 on a hard key and `3` fell to 0.94; with `--matte soft`, `--scale 8 --smooth 3` holds IoU 0.96–0.98. A hard 1px staircase needs ≈ 0.9 × scale: on `evals/degraded`'s aliased wrench, `--smooth 3` reproduced every step and `7` gave clean curves at IoU 0.961 / edge_f1 0.901, while `9` rounded the jaw tips. `jaggedness` does not separate those three (6.76 / 7.55 / 6.09) — its strides are fixed in render pixels, so a step 8 px long reads as a real corner; judge a staircase source on the compare sheet |
| `--colors N` | a rendered gem with gradients traced to 388 shapes / 75 KB; 32 colours gave 31 KB and MAE 11.5 |
| `--scale N` | tiny sources trace coarse curves; scale before tracing, never after |

## Soft matte, and what it does under each key

`--key flood` + `--matte soft`: alpha follows colour distance only within 3 px of the keyed
boundary, over the largest subject distance nearby — enclosed ground-coloured detail stays opaque.
`--key global` + `--matte soft`: alpha is coverage everywhere, distance over the 95th-percentile
subject distance, less the ground's median noise. Coverage reaches the centre of a hole a blur has
nearly closed, which the band cannot; on the degraded glyphs it lands within 0.06–0.11 of the best
any single per-image threshold achieves. Lower `--tolerance` (25) for a noisy ground: it only
decides which pixels count as ground for that noise estimate.

Measured and dropped, so nobody re-tries them blind: blurring RGB before `--colors` quantizes
(mints in-between shades that trace as slivers: the mark went 31 → 39–58 KB), a median denoise
before keying, a mode filter on palette indices, and local-maximum normalisation for glyphs.

## Background tolerance

`--tolerance` is a Chebyshev distance on RGB from the median border colour. 40 suits a flat dark or
light ground. A textured or gradient ground needs more — or a tighter `--crop` that excludes it.
Exit 1 from prep ("nothing left after keying") means the tolerance swallowed the subject.
