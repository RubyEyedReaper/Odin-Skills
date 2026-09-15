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
| `--smooth R` | an upscaled 45px glyph traces its pixel staircase as wobble. RubyTech: `1.5` kept IoU ≥ 0.96; `3` fell to 0.94 and QA refused it |
| `--colors N` | a rendered gem with gradients traced to 388 shapes / 75 KB; 32 colours gave 31 KB and MAE 11.5 |
| `--scale N` | tiny sources trace coarse curves; scale before tracing, never after |

## Background tolerance

`--tolerance` is a Chebyshev distance on RGB from the median border colour. 40 suits a flat dark or
light ground. A textured or gradient ground needs more — or a tighter `--crop` that excludes it.
Exit 1 from prep ("nothing left after keying") means the tolerance swallowed the subject.
