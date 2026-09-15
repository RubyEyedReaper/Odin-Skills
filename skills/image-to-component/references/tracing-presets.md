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
| `--smooth auto` (default) | an upscaled glyph traces its pixel staircase as wobble. `auto` reads the source before upscaling (`scripts/edges.py`). **Hard edge** (≥ 75 % of alpha-128 crossings fully on or off): the marching-squares outline is smoothed along its arc at σ 0.8 source px (`scripts/outline.py`, `2G − G²` so nothing shrinks) and rasterised 4× supersampled. On the degraded aliased wrench this scores IoU 0.967 / edge_f1 0.951 / staircase 0.105, against `--smooth 7`'s 0.961 / 0.901 / 0.137 with rounded jaw tips; on the 32 px aliased controller it keeps the buttons (edge_f1 0.942) where `--smooth 7` erases them (0.728, refused). **Soft edge**: a Gaussian of 0.375 × scale, which is `3` at ×8 — the RubyTech glyphs regenerate byte-identical |
| `--smooth R` | a Gaussian radius on the upscaled alpha, whatever the edge. It acts on area, so on a hard source the radius that removes a one-pixel step (≈ 0.9 × scale) also closes 1–2 px holes: `--smooth 3` at ×8 reproduced every step of the aliased wrench and `7` rounded its jaws. `jaggedness` cannot rank those (6.76 / 7.55 / 6.09); QA's `staircase` bound does (0.41 refused / 0.14 / 0.11). Use a number to tune a soft source: `--scale 8 --smooth 1.5` on the degraded glyphs |
| `--sharpen R` | a blur below the stroke width half-fills holes and gaps, and the α ≥ 128 cut closes them: the degraded controller's buttons merge and the gear's teeth and ring soften. Unsharp-masks the keyed alpha at source resolution against a Gaussian of R source px, amount 2, before upscaling. On the four degraded glyphs at `--smooth 1.5`, `0.8` raised agreement with the clean trace from 0.688 / 0.730 / 0.813 / 0.838 to 0.694 / 0.824 / 0.830 / 0.872, no glyph lower and every QA pass kept. Measured and not taken: amount 3 or radius 1.2–1.5 gained on the gear and lost the computer below its baseline; sharpening only the trace input fails QA IoU against the unsharpened reference; smoothing a soft outline along its arc (`auto`'s hard-edge route) lost 0.01–0.03 on every glyph. Never on a clean source: the RubyTech glyphs fall to 0.94–0.97 agreement with themselves |
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
before keying, a mode filter on palette indices, and local-maximum normalisation for glyphs. For a
noisy colour mark, a median, an edge-preserving mean or a palette region merge before quantize
never lowered `mae` — scale 2, 64 colours and `filter_speckle=7` pass without one
(`evals/degraded/README.md`).

## Background tolerance

`--tolerance` is a Chebyshev distance on RGB from the median border colour. 40 suits a flat dark or
light ground. A textured or gradient ground needs more — or a tighter `--crop` that excludes it.
Exit 1 from prep ("nothing left after keying") means the tolerance swallowed the subject.
