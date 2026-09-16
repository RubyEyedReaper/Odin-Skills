# QA thresholds

`scripts/render_diff.py` renders the optimized SVG with resvg at the reference raster's exact size
and scores it with `scripts/diffmetric.py`. Defaults live in `DEFAULT_THRESHOLDS` there.

| Metric | Default | Catches |
|---|---|---|
| `iou` — alpha silhouette overlap (α ≥ 128) | ≥ 0.95 | missing or extra shapes, lost transparency, background left in |
| `mae` — mean abs RGB error on visible pixels, 0–255 | ≤ 12 | wrong colours, merged regions, over-quantization |
| `edge_f1` — Sobel edge agreement within ±1px | ≥ 0.80 | drifted outlines, lost detail, over-smoothing |
| `jaggedness` — the render's outline zig-zag finer than its shape (`scripts/jaggedness.py`) | ≤ 15 | pixel staircases and tracer wobble, which IoU and edge_f1 both absorb |
| `features` — lowest recall of any counted reference feature (`scripts/features.py`) | ≥ 0.5 | a dropped dot, a filled hole, a detail painted over — which every average above absorbs (#1392) |
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
- **`--auto` selects among candidates that clear the bars; it never moves one.** Each candidate is
  scored with `DEFAULT_THRESHOLDS` against a reference its prep derived once, so every candidate faces
  the same bar at a given scale. `qa.json` → `search.grid` holds each candidate's scores and failures;
  a refused search writes `"failures": ["auto"]` and names the nearest miss.
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

## Why features exists, and its numbers

`--auto` shipped the held-out alert mark with the dot of its "!" gone: its smallest passing candidate
(`filter_speckle=12`) scored iou 0.9785, mae 11.79, edge_f1 0.905 — a 7 px² dot is a fraction of a
percent of every average. `features` counts shapes instead of pixels.

The reference is segmented into regions of one colour or of transparency (region growing within
Chebyshev 40 of the running mean; the ground — transparent and touching the border — is not a feature).
A region counts when, eroded by 0.5 source px, it still covers 1 source px², and its whole area is at
least 0.5 % of the reference's visible pixels. A core pixel is kept when a render pixel within the
erosion radius is its colour: transparent for a hole; otherwise within 48 of the region's mean, or no
farther from it than from any other counted region's colour plus 24. The score is the lowest kept
share; below 0.5 the region is named in `qa.json` → `lost_features` with its colour, area and position.

| Number | Why |
|---|---|
| erode 0.5 source px | the anti-aliased band between two colours grows into a ring region of its own; eroding removes it at every scale |
| 1 source px² core | a single-pixel noise speck never counts (`tests/test_features.py`, specks removed and passed) |
| 0.5 % of visible px | the clean RubyTech mark's neon streaks and rim highlights are 10–33 source px² of ~17 000 (0.06–0.19 %) and its flat trace drops them; the alert dot is 7 of ~800 (0.9 %) |
| within 48 outright | a flat fill replaces a shaded region with one palette colour — the rim's cyan traced a shade away read as lost at recall 0 without it; colour error is `mae`'s |
| recall 0.5 | a lost feature scores 0; every kept one on the RubyTech and degraded evals scores ≥ 0.93; the bar sits between |

Measured with the bar in place: every `evals/rubytech` and `evals/degraded` run keeps its verdict
(glyphs 1.0; the clean mark 0.928, the degraded mark 0.965), and the held-out set stays 13/20 — the
same assets pass and fail, except that `--auto` now chooses a 762-byte alert mark that keeps its dot
(mae 9.78, edge_f1 0.977). The shipped dot-less render is frozen as a refusal case in
`tests/fixtures/`. Cost: ≈ 0.8 s to segment a ×8 glyph reference once, ≈ 0.1 s per candidate after.

## Source quality — refused at prep, before any trace (#1391)

A glyph source the degradation has destroyed yields a destroyed reference, and QA scores a trace against
that reference: the held-out X, clock and thermometer passed every bar at `--auto` while their compare
sheets showed blobs (agreement with their clean traces 0.53–0.63). No fidelity metric can refuse a
faithful trace of the wrong shape, so `scripts/quality.py` asks the source, for `--color currentColor`
runs only, before keying it: prep exits 3 and `i2c.sh` exits 1 `FAILED at prep`, `qa.json` →
`failures: ["source-quality"]`.

**Silhouette stability.** The ground's noise σ is read from neighbouring pixel pairs that are both
ground. The source is keyed as `--auto` keys a glyph, re-keyed under six seeded draws of that noise, and
the α ≥ 128 silhouettes are compared by IoU. Below **0.90** mean IoU the source is refused. A transparent
or noiseless source has nothing to perturb and passes.

**The ladder's labels were re-derived, and three moved (#1410).** The `UNREADABLE` set was a frozen
literal written by an earlier pass. Every one of the 48 rungs was traced again under `--auto`,
against a scratch copy of the skill whose `MIN_STABILITY` is 0 so a refused rung still produces a
sheet, and read again. The criterion, stated so a reader can check it: **does the trace still show
the feature that makes the glyph that glyph** — the monitor's frame, the gear's toothed rim, the
controller's body and holes, the wrench's *open* jaw.

| Rung | Was | Is | What its sheet shows |
|---|---|---|---|
| `wrench-icon.s40.q15` | reads | **unreadable** | a smooth diagonal lump with no opening at either end |
| `wrench-icon.s33.q30` | reads | **unreadable** | a rounded top with a shallow dent where the jaw was |
| `wrench-icon.s25.q30` | reads | **unreadable** | the same: a dent, not an opening |

The 45 other rungs kept their labels, including two that were re-examined and left alone:
`gear-icon.s40.q30` (**reads** — its rim is unmistakably toothed, though its bore has become a
squiggle) and `wrench-icon.s33.q20` (**reads** — its top is forked into a V, which is a jaw).

**Stated plainly, because it is the obvious objection:** all three relabelled rungs are ones the new
measure refuses, so the re-derivation improves the measure's apparent score. Three things bound
that. The re-labelling ran **before** either threshold was chosen; **all 48** rungs were judged, not
only the contested ones; and `gear-icon.s40.q30` was left `reads` although calling it unreadable
would have *raised* the catch count. The criterion above is the check a reader can run.

**Calibration — never on the held-out set.** A severity ladder built from the four clean RubyTech
glyphs (×0.5 / 0.4 / 0.33 / 0.25, each at JPEG 30 with blur 0.6 and noise 6, JPEG 20 with noise 4, and
JPEG 15 with blur 0.8 and noise 8: 48 sources), each traced under `--auto` and labelled by reading its
compare sheet — does the trace read as the glyph — with agreement against `evals/degraded/truth/` as
context. Then every candidate measure was computed on every rung, on the committed degraded glyphs and on
the clean glyphs (RubyTech and held-out crops, which must all pass):

| Measure | Why it lost |
|---|---|
| edge ramp ÷ stroke thickness | clean held-out glyphs reach 0.72, a readable degraded computer 0.996, unreadable rungs 0.62–1.72 |
| subject extent, α ≥ 128 | unreadable rungs 7–18 px, readable ones 7–19 px: a 9 px controller reads, a 16 px gear does not |
| extent ÷ ramp, luminance edge width | every threshold that kept the committed degraded glyphs refused 18 of 28 readable rungs |
| topology stability (components and holes under noise) | a clean clock glyph flips topology in 5 draws of 6 |
| **silhouette stability** | **kept** — the table below |

| Glyph | unreadable rungs refused | readable rungs refused |
|---|---|---|
| computer | 8 of 8 | 0 of 4 |
| gear | 2 of 7 | 0 of 5 |
| controller | 0 of 1 | 0 of 11 |
| wrench | 0 of 3 | 3 of 9 (7–9 px across) |
| committed degraded glyphs, clean RubyTech and clean held-out glyphs | – | 0 of 15 (lowest 0.911, the degraded computer) |

0.90 sits below the committed degraded computer's 0.911 and above the three small wrenches at
0.84–0.88. **It is a partial answer, stated as one:** it refuses a thin-stroked glyph whose strokes its
noise rivals, and misses a thick glyph the blur has merged — a gear whose teeth are gone is stable
under noise and still wrong. `evals/degraded/src/computer-icon.destroyed.png` is one refused rung,
committed as the eval's refusal case; `evals/degraded/ladder.py` rebuilds the ladder and prints every rung's label and verdict.

**Edge ramp ÷ subject extent — the second measure, for the half stability misses (#1410).**
`edges.edge_ramp` of the keyed, soft-matted source over the longest side of its α ≥ 128 bounding
box. Above **0.20** the source is refused, with `reason: "ramp-extent"`.

A blur destroys features smaller than its own width, and a glyph's features scale with the glyph, so
an edge ramp means nothing until it is read against the size of the subject carrying it: the same
2 px of softness is nothing on a 40 px mark and the whole of a 9 px one. It is the one dimensionless
number among the candidates, and it is **not** the rejected "edge ramp ÷ stroke thickness" — median
distance-transform thickness quantises to 1.0 px on almost every degraded rung, which is why that
denominator carried no signal.

Six further candidates were computed on all 48 rungs, the 4 clean RubyTech glyphs, the 7 committed
degraded sources and the 10 held-out glyph crops:

| Candidate | Why it lost |
|---|---|
| threshold IoU (α ≥ 96 against α ≥ 160) | clean glyphs 0.80–0.97, readable degraded 0.66–0.81, unreadable 0.66–0.84 — total overlap inside the degraded population |
| ramp mass — share of visible pixels at partial alpha | separates clean from degraded and nothing inside degraded |
| interior dimness | a shape property: clean glyphs span 0.19–1.0 |
| blur robustness — IoU after a further 1 px box blur | high for a chunky clean glyph and for a destroyed one alike; it measures blobness, not damage |
| interior valleys — the residue of a merged gap | works on the controller family and is identically zero for every wrench rung, readable or not |
| **edge ramp ÷ subject extent** | **kept** |

**The two combine as an OR, and the verdict names which fired.** A single blended score would hide
both: they are answers to different questions, and `qa.json` carries each. Swept jointly over the
relabelled ladder, subject to every clean RubyTech glyph, every clean held-out glyph and every
committed degraded glyph the eval expects to pass passing, and `computer-icon.destroyed` being
refused:

| Measure(s) at `MIN_STABILITY` 0.90 | unreadable rungs refused | readable rungs refused |
|---|---|---|
| stability alone, against the *frozen* labels (the state #1410 reports) | 10 of 19 | 3 of 29 |
| stability alone, against the relabelled ladder | 11 of 22 | 2 of 26 |
| **both, `MAX_RAMP_EXTENT` 0.20** | **20 of 22** | **2 of 26** |

Of the 20, **9 are refused by `ramp_extent` alone**, 5 by stability alone and 6 by both — which is
the case for keeping two measures rather than replacing one with the other. The two still missed are
`gear-icon.s33.q20` (ramp 0.136) and `wrench-icon.s50.q15` (0.188); the two false refusals are
`wrench-icon.s33.q20` and `.s25.q20`, both on **stability**, both wrenches 7–9 px across, and both
already refused before this measure existed.

`MIN_STABILITY` did not move. A pair at 0.89 scores identically and sits further from the nearest
must-pass source (`computer-icon.low`, 0.906), but every catch it adds is one this measure already
makes, and lowering a bound that changes no verdict is a loosening with nothing to show for it.

**Its residue, stated:** it says nothing about a source that is uniformly crisp and simply too
small, which is what stability covers. Neither replaces the other, and together they still miss two
rungs a reader can see are destroyed.

## Colour source quality — the same two measures, keyed as a mark (#1409)

A colour mark was assessed by nothing: `prep.check_source` returned without measuring unless
`--mono` was passed, so `facebook-banner-mark.low` passed every bar at `--auto` — iou 0.970, mae
11.74, edge_f1 0.802 — while its compare sheet shows a lumpy badge and a mangled "f". It was the one
wrong-looking pass left on the held-out set.

**What ships is `stability` and `ramp_extent` unchanged, computed on a source keyed the way `--auto`
keys a colour mark** — flood at tolerance 40 with a soft matte, rather than globally at
`GLYPH_TOLERANCE`. Bars of its own: **0.97** and **0.06**.

Keying was the whole difficulty, and getting it wrong is what made three colour-specific candidates
read backwards. A global key at a glyph's tolerance cuts a mark's own dark regions out of it, so the
"subject" whose extent the ramp is divided by is whatever fragments survive: clean
`facebook-banner-mark` scored `ramp_extent` 0.201 that way — higher than every degraded *glyph* in
the corpus, and higher than its own degraded twin. Keyed as a mark it scores 0.043, and the twin
0.111.

| Candidate, measured on 21 ladder rungs, 8 clean colour assets and 5 degraded held-out marks | Why it lost |
|---|---|
| palette-region agreement under seeded noise (the shape #1409 proposes) | reads a mark's palette complexity, not its damage: clean `alert-mark` 0.884 against degraded `facebook-banner-mark.low` 0.849 |
| the same, restricted to region interiors | inverted — clean `alert-mark` 0.963 and clean `facebook-banner-mark` 0.927 both score *below* the degraded twin's 1.000 |
| disagreement ÷ label-boundary share | separates, but clean marks span 0.018–0.132 across six assets: 7× on a population whose degraded members span 0.115–0.166 |
| transition width ÷ characteristic region size | collapses to 1 ÷ region size — clean `alert-mark` 0.0593 above degraded `facebook-banner-mark.low` 0.0561 |
| **the two shipped measures, keyed as a mark** | **kept** |

**The colour ladder goes further down than the glyph one, and its rungs carry no hand-read label.**
`evals/degraded/colour_ladder.py` degrades `rubytech-mark.png` under the glyph ladder's three
recipes at ×0.5 down to ×0.12 — 21 rungs. Two reasons it differs: at the glyph ladder's floor
(×0.25) the mark is still 33×40 px and every rung reads, so a ladder stopping there carries no
positive example; and below that, **a rung's `--auto` run leaves no trace to read**, because nothing
in the grid passes. So the label is the run's own verdict — `traceable` or not — rather than a
reading of a sheet that does not exist.

| At `MIN_COLOUR_STABILITY` 0.97, `MAX_COLOUR_RAMP_EXTENT` 0.06 | Refused at prep |
|---|---|
| ladder rungs the `--auto` grid can still trace (7) | **0 of 7** |
| ladder rungs nothing in the grid can trace (14) | **11 of 14** |
| clean colour assets — RubyTech mark and lockup, 5 held-out marks (7) | **0 of 7** |
| `evals/degraded/src/rubytech-mark.low.png`, which must pass | **kept** (0.991 / 0.016) |

The bound sits just above the highest clean colour asset (`facebook-mark`, 0.0476) rather than
anywhere higher: every rung above it is one nothing can trace, so the lowest feasible bound is the
one that refuses the most, and the 26 % margin to that asset is what keeps it honest.
`rubytech-logo` is deliberately in the must-pass set — the RubyTech eval requires it to fail at the
**budget**, never at prep, and `evals/rubytech/run.sh` asserts that reason by name.

**Its residue, stated:** three untraceable rungs are still kept (`s50.q20`, `s33.q30`, `s25.q20`)
— they fail QA for reasons that are not degradation of the source, and a source measure cannot see
them. And the calibration's positive examples are all one mark: the ladder is `rubytech-mark`
degraded seven ways, so the bound is bounded-below by seven clean assets and bounded-above by one
subject's ladder. A second colour subject would make it stronger.

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
  budget, the asset needs a hand-authored SVG gradient, not a looser threshold. The skill neither fits
  gradients nor names the failure anything but `mae` (DEC-0168), and both were measured before being
  declined, on a synthetic four-stop radial mark whose best flat `--auto` candidate scores `mae` 12.33
  (never on the held-out gradient marks):

  | Attempt | Result |
  |---|---|
  | per-path linear gradient fitted to each traced path at 32–64 colours | ≤ 0.5 of a path's colour variance explained; `mae` unchanged — each path is already one band |
  | 4–16 colour trace, per-path linear fit | `mae` 12.3–17.7, never below the flat trace |
  | one shared linear or radial 4-stop gradient over every high-variance path, with and without iterative path reassignment | `mae` 27–40: vtracer's stacked paths lie under the glyph, so the white outline is repainted with the gradient |
  | naming the refusal `gradient-fill` from a smooth-region share of the reference | the RubyTech gem scores 0.53–0.99 and synthetic gradient marks 0.0–0.97 at every step size tried — a shaded facet and a gradient are one class to any stdlib measure found |

  Fitting would also widen `svg2tsx`'s dialect (#1352) to `defs` and gradients with `useId`-scoped ids;
  that stays undone until a fit passes `mae` on a calibration mark.
