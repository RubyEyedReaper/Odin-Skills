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

## auto

`i2c.sh --auto` (`scripts/auto.py`, decisions in `scripts/autogrid.py`). Every number below is in
`autogrid.py`; this says why.

**Prep is derived, not searched.** QA scores a run against its own prepared reference, and every prep
flag changes that reference. Candidates that differ in `--matte`, `--sharpen` or `--tolerance` are held
to different bars, and "smallest passing" then picks whichever erased detail: the degraded glyphs pass
their own QA unsharpened at IoU 0.98 with their holes closed, smaller than the sharpened traces that
agree 0.09 better with the clean truth. So the prep is fixed per asset by rule:

| Rule | Measured on |
|---|---|
| glyph: `--key global --matte soft --tolerance 25`; colour: `--key flood --matte soft` | the SKILL.md rows |
| glyph `--sharpen 0.8` when `edges.edge_ramp` (partial-coverage pixels per alpha-128 crossing, keyed source) ≥ 1.35 | clean RubyTech glyphs 0.55–1.10, degraded 1.59–2.19, hard-alpha 0 |

**The grid varies what the reference does not depend on,** plus scale for small sources:

| Kind | Axes | Size |
|---|---|---|
| glyph | `--smooth` auto, 0.5625 / 0.1875 / 0.0625 × scale; at ≤ 40 px also all four at `--scale 16` | 4 or 8 |
| colour | `--colors` (logo 32/48/64/96) × `filter_speckle` 4/7/12 at `--scale 2`; at ≤ 80 px also (scale/colours/speckle) 3/48/7, 3/64/7, 3/64/12, 4/48/12, 4/64/12, 4/64/24 — each once with its regions voted smooth at `--smooth` 0.5 × scale and once without | 24 or 36 |

Why the small-source scales: on the RubyTech glyphs downscaled ×0.4–×0.5 (21–27 px) no smoothing
passes IoU at ×8 for the computer (0.919–0.942) or the ×0.4 controller (0.913–0.948) — a 1–2 px stroke is
8–16 render px and the spline fit's error is a tenth of it — and all pass at ×16. The mark at ×0.5 and
×0.4 (53–80 px) fails `mae` at ×2 across every palette tried (13.0–18.9, up to 128 colours and
`layer_difference=6`) and passes at 3/64/7 and 4/48–64/12. A larger scale costs bytes, so the
smallest-passing rule keeps ×2 or ×8 whenever those pass; the degraded evals choose exactly the
scales they were tuned at.

**Before the grid:** a `--mono` source is assessed first (`scripts/quality.py`), and a glyph whose own noise
decides its silhouette is refused as `source-quality` without tracing a candidate
(`qa-thresholds.md` § Source quality).

**Selection:** smallest optimized SVG passing `svgcheck` and every QA bar — `features` among them, so a
candidate that drops a small shape is not a pass however small it is — ties in grid order — except that a colour candidate with voted regions is preferred to any without, whenever one passes. Smoothing costs bytes (the degraded mark: +1.2 KB at 64 colours), so smallest-alone would never choose it; the owner's requirement is smoothed edges, and the unsmoothed setting stays the fallback. `layer_difference=12`, an axis in the first grid, was chosen by no search measured and was dropped. Nothing
passing: exit 1, and the nearest miss — fewest failed bars, then smallest shortfall as a fraction of
each limit — is printed and recorded. Measured wall-clock on this host: 5–8 s for a degraded glyph at
×8 only, 17–33 s with ×16 or a 50 px clean glyph, 14–35 s for a colour mark; bounded at 300 s
(`--seconds` in `auto.py`), past which the search is a tool failure, never a verdict.

**What was not added, and why:** `mode=polygon` passes the small computer glyph at 345 bytes, but its
straight facets are exactly what a glyph must not look like and no QA bar measures that; `length_threshold`,
`corner_threshold` and `filter_speckle` at ×8 moved the small-glyph IoU by 0.004 or less.

## Prep flags, and the failure each one answers

| Flag | Failure without it |
|---|---|
| `--key flood` (default) | a flat background colour is traced as a full-bleed path — `svgcheck` reports `opaque-background` |
| `--key global` | a glyph's enclosed holes (gear centre, wrench eye) stay opaque, because flood fill cannot reach them from the edge |
| `--color currentColor` → silhouette trace input | vtracer's binary mode ignores alpha; an RGBA input traces as one square covering the viewBox |
| `--matte soft` | a soft, anti-aliased, glowing or blurred edge is keyed at the tolerance boundary, so strokes fatten and holes close. RubyTech glyphs: jaggedness 2.9–8.9 → 2.3–2.5; degraded glyphs: agreement with the clean trace 0.57–0.66 → 0.69–0.84 |
| `--smooth auto` (default) | an upscaled glyph traces its pixel staircase as wobble. `auto` reads the source before upscaling (`scripts/edges.py`). **Hard edge** (≥ 75 % of alpha-128 crossings fully on or off): the marching-squares outline is smoothed along its arc at σ 0.8 source px (`scripts/outline.py`, `2G − G²` so nothing shrinks) and rasterised 4× supersampled. On the degraded aliased wrench this scores IoU 0.967 / edge_f1 0.951 / staircase 0.105, against `--smooth 7`'s 0.961 / 0.901 / 0.137 with rounded jaw tips; on the 32 px aliased controller it keeps the buttons (edge_f1 0.942) where `--smooth 7` erases them (0.728, refused). **Soft edge**: a Gaussian of 0.375 × scale, which is `3` at ×8 — the RubyTech glyphs regenerate byte-identical |
| `--smooth R` on a colour trace | quantized regions keep every noise step of their borders, and vtracer traces each as a wobble (the degraded mark's facet borders). A number votes the borders smooth (`scripts/regions.py`): each palette label's mask is Gaussian-blurred at R upscaled px, and every opaque pixel takes the best-supported label — no colour created, the silhouette unchanged, a facet wider than R kept. Degraded mark, ×2 / 64 colours / speckle 7: R 0.75 → jaggedness 7.05, 1 → 5.99 with edge_f1 0.846 → 0.866 and `mae` 11.35 → 11.66, 1.5 → `mae` 12.54 refused, 2 → 13.28 refused; agreement with the clean mark 0.887 at every radius. Measured and not taken: vtracer's `corner_threshold` 90–120, `length_threshold` 8, `splice_threshold` 90 (jaggedness 7.03–7.36, no visible change); a blur of the whole label map that also moved the silhouette; quantizing at source size and upscaling each label mask (jaggedness 17.4, refused). `auto` leaves colour regions as quantized, so every hand-tuned colour run is unchanged |
| `--smooth R` | a Gaussian radius on the upscaled alpha, whatever the edge. It acts on area, so on a hard source the radius that removes a one-pixel step (≈ 0.9 × scale) also closes 1–2 px holes: `--smooth 3` at ×8 reproduced every step of the aliased wrench and `7` rounded its jaws. `jaggedness` cannot rank those (6.76 / 7.55 / 6.09); QA's `staircase` bound does (0.41 refused / 0.14 / 0.11). Use a number to tune a soft source: `--scale 8 --smooth 1.5` on the degraded glyphs |
| `--sharpen R` | a blur below the stroke width half-fills holes and gaps, and the α ≥ 128 cut closes them: the degraded controller's buttons merge and the gear's teeth and ring soften. Unsharp-masks the keyed alpha at source resolution against a Gaussian of R source px, amount 2, before upscaling. On the four degraded glyphs at `--smooth 1.5`, `0.8` raised agreement with the clean trace from 0.688 / 0.730 / 0.813 / 0.838 to 0.694 / 0.824 / 0.830 / 0.872, no glyph lower and every QA pass kept. Measured and not taken: amount 3 or radius 1.2–1.5 gained on the gear and lost the computer below its baseline; sharpening only the trace input fails QA IoU against the unsharpened reference; smoothing a soft outline along its arc (`auto`'s hard-edge route) lost 0.01–0.03 on every glyph. Never on a clean source: the RubyTech glyphs fall to 0.94–0.97 agreement with themselves |
| `--colors N` | a rendered gem with gradients traced to 388 shapes / 75 KB; 32 colours gave 31 KB and MAE 11.5 |
| `--scale N` | tiny sources trace coarse curves; scale before tracing, never after |

## Soft matte, and what it does under each key

`--key flood` + `--matte soft`: alpha follows colour distance only within 3 px of the keyed
boundary, over the largest subject distance nearby — enclosed ground-coloured detail stays opaque.
`--key global` + `--matte soft`: alpha is coverage everywhere — distance over the 99th-percentile
subject distance, less the ground's median noise, raised to the power 1.15 (`PEAK_PERCENTILE`,
`COVERAGE_GAMMA` in `scripts/keying.py`). Coverage reaches the centre of a hole a blur has nearly
closed, which the band cannot. The near-maximum peak and the gamma stop a dim glow or screen inside a
blurred stroke reading as stroke: at the 95th percentile and no gamma the degraded computer's frame
traced fat on its inner side (agreement 0.694); now 0.732, and the other degraded glyphs rose too
(`evals/degraded/README.md`, The computer glyph's gap). Lower `--tolerance` (25) for a noisy ground: it only
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
