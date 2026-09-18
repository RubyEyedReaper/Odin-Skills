# Primitives eval

Does `--primitive` fit the right container shape, and never the wrong one? The expensive failure is a
**wrong acceptance**: a shape that passes every silhouette number and looks wrong on the page. So the
record is three counts, always together — correct, wrong, missed — and any wrong acceptance is exit 1.

```sh
bash evals/primitives/run.sh                                        # sources, measure, score
python3 evals/primitives/evaluate.py calibrate out/.work/raw.jsonl  # reads the calibrate split ONLY
```

**This eval is offline.** No library is fetched and no index is built: the positives are drawn from
parameters and the negatives are artwork this repository already commits. It needs `resvg` and
`Pillow` (exit 2 without them) because every candidate is scored as the SVG that would actually be
emitted — scoring an analytic raster instead would let the emitted artifact differ from the thing
that passed, which is the failure mode this route exists to prevent.

## Sources — synthesised, never committed

`make_sources.py` writes into `out/.work/src`, in two splits from two seeds:

| Set | What | Per split |
|---|---|---|
| ladder | 5 families × 8 rungs (8–40 px) × 3, aspect and radius jittered | 120 |
| confusers | a rounded rect just under the pill snap band, a near-square pill, a near-circular ellipse, at 8–16 px | 24 |
| negatives | the product's own glyphs and marks — `evals/degraded/src/`, `evals/heldout/src/` — each at every rung | 118–126 |

Every source is padded, blurred (σ 0–0.9), noised (σ 0–8) and JPEG-compressed at quality 20–60.

**A confuser sits just OUTSIDE the snap band, never inside it.** `scales.json` declares a relative
`snap_tolerance` of 0.125, so `derive` reads any axis ratio at or above 0.875 as equal: a 10×9
ellipse **is** a circle and a radius at 0.9 of its cap **is** a pill, by the vocabulary this skill
declares (DEC-0181). A source drawn inside that band and labelled `ellipse` asserts a distinction
the vocabulary forbids — it can only ever score WRONG or missed, whatever the verifier does, and it
measured WRONG twice on the eval split before the range moved. The pill confuser is the exception
and stays as it was: its radius is exactly half its short side at every aspect, so `pill` remains
the name its parameters carry, and the near-square case tests the tie machinery, which is what
should answer it.

**The negatives are dealt between the splits, not shared.** The candidacy floors are what the
negatives bound, and calibrating a floor on the same negatives it is then scored against proves
nothing. They are also run down the same degradation ladder as the positives: the 28 committed files
at one size each gave the calibrate split no near-miss at all, so a floor read as costing pure recall
while the held-out split had the one source that needed it.

**One fixture is deliberately excluded from the ladder.** `computer-icon.destroyed.png` is the
degraded eval's *unusable source* case; resized to 16 px its keyed silhouette is a perfect 16×14
solid rectangle — hull fill and bbox fill both exactly 1.000, and `quality.assess` passes it at
stability 1.0 because the blob has a clean edge. It **is** a rectangle. Scoring the fit as a wrong
acceptance would require the verifier to know the file's provenance rather than read the image. The
committed file itself stays a negative; the guard against this class is upstream — crop something
that still depicts the asset.

## What is counted

| Set | correct | WRONG | missed |
|---|---|---|---|
| ladder | the emitted family is the truth, or ties with it | any other accepted family | refused |
| confusers | same | same | refused — the intended answer at these sizes |
| negatives | — | **any** acceptance | refused |

`measure` renders each family once and stores the fits, the pair margins, the equivalence IoUs, the
candidacy numbers and the derived names; `score` and `calibrate` re-decide through
`primitives.decide` — the shipped rule, never a second copy of it — so a parameter sweep costs no
renders and the scored rule is the one that runs.

**The candidate that is scored is the candidate that would be emitted**, which is the same rule as
"no analytic raster" one level down. `derive` snaps a fitted shape onto the name its parameters
carry, and that snap moves pixels — an ellipse at rx 8, ry 7 becomes a circle at r 7.5, a whole
pixel on each axis of a 16 px asset. Deriving *after* the comparison let a shape win the adversary
margin on one render and ship a different one: two near-square stadiums at 12 and 16 px were named
`circle` that way, the second on an ellipse score of 0.905 that fell to 0.865 as soon as the circle
itself was the thing rendered. Every name the verdict reports is in that same emitted vocabulary —
`family`, `ties` and `runner_up` alike — because a verdict that mixes the two languages makes
`--primitive pill` refuse a source whose pill ties with the emitted circle at agreement 1.000.

## Calibration — `scripts/primitives.json`

Chosen on the `calibrate` split, then scored once on `eval`. **The rule is the dual of the replace
eval's**: there, the loosest setting with no wrong naming, because a wrong naming exists to bound
from below; here, the *tightest* setting that costs no recall, because with five names for one kind
of object there is no wrong acceptance at any setting on some splits, and "the value that costs no
recall" would land on the loosest end of every sweep and call it calibrated.

Two constraints are stated rather than swept to their edge:

- **`margin` has a floor of 0.08**, the replace route's own calibrated value. Recall against the
  margin has no knee — about one source per 0.02 step — so the margin is a judgement, not a
  measurement, and letting the sweep choose would switch the adversary test off entirely.
- **`equivalent` is swept from 0.95 up.** A tie is what lets the fewest-parameter family be emitted
  instead of the best-fitting one; at 0.90 a 24 px square and the same square with a 6 px radius tied
  and the squircle shipped as a square.

## What the verifier refuses, and why each one exists

| Refusal | The source | Why no threshold catches it |
|---|---|---|
| `components` | two blobs | — |
| `hole` | a ring, a knockout tile, a letterform | — |
| `composite` | a tile with a glyph on it — the alert mark, the old Facebook square | the container underneath really **is** a rounded rect and fits like one (0.884 and 0.778). Keying leaves some of them with no interior hole at all. The caller reads the second flat colour; the predicate turns that into a refusal |
| `too-small` | fewer pixels than five names can be told apart with | the same refusal `--replace` makes with `auto_min_px` |
| `convexity`, `bbox-fill` | a glyph | both ratios count visible pixels on **both** sides; a soft numerator over a visible-pixel hull read a blurred disc as non-convex and refused 86 of 92 ladder sources |
| `asymmetry` | a bulb at one end — a thermometer, an arrow | every admissible family mirrors about both axes of its own box; a glyph does not |
| `source-quality` | degraded past the point where its own noise decides its silhouette | `--replace` runs ahead of this check on purpose, because the truth lives in a library. A primitive has no external truth: the source **is** the evidence |
| `radius` | a stadium whose best radius is 0.8 of its cap | `rect`, `rounded-rect` and `pill` are one family split by one number. When the winning radius renders the same as the one that would rename the shape, the name is undetermined and saying so beats guessing |
| `bar`, `adversary`, `indistinguishable` | the family itself is not resolved | batch 1's rule, unchanged |

## Results — eval split, committed numbers

`out/counts.tsv` and `out/eval.tsv` are the record. See those files; the headline is below.

**Eval split, 462 sources, at the parameters in `scripts/primitives.json`: 0 wrong acceptances.**

| Set | correct | WRONG | missed / refused |
|---|---|---|---|
| ladder (320) | 147 | **0** | 173 |
| confusers (24) | 1 | **0** | 23 — the intended answer |
| negatives (118) | — | **0** | 118 refused |

Per rung, and it is a size story from end to end:

| px | 8 | 10 | 12 | 16 | 20 | 24 | 32 | 40 |
|---|---|---|---|---|---|---|---|---|
| correct | 0 | 4 | 9 | 17 | 18 | 30 | 34 | 35 |
| of | 40 | 40 | 40 | 40 | 40 | 40 | 40 | 40 |

Correct acceptances by family: `circle` 52, `rect` 35, `rounded-rect` 23, `pill` 21, `ellipse` 16 —
every family is reached, and the one-parameter family is reached most, which is what a fewest-
parameters tie-break should do.

Why the 173 ladder refusals happened, and why each is the right answer at that size:

| Reason | n | |
|---|---|---|
| `too-small` | 98 | below the `min_px` floor of 10 — every 8 px source and most of the 10 px ones |
| `adversary` | 24 | a family the source does not side against by `margin` |
| `radius` | 21 | the winning radius renders the same as one that would rename the shape |
| `indistinguishable` | 16 | fewer than `min_weight` pixels of disagreement to judge on |
| `bar` | 11 | nothing fitted well enough |
| `source-quality`, `asymmetry`, `convexity` | 26 | the source's own noise decides its silhouette, or the degradation broke the shape |

And the negatives, which is the count that matters: 52 refused at `hole`, 32 at `composite`, 24 at
`source-quality`, 5 at `convexity`, 4 at `components`, 1 at `asymmetry`. **Not one reached a family
decision.** Candidacy is the defence; the margin is the second one.

## Residue

- **Recall is 46 % on the ladder and 0 % at 8 px, reported rather than tuned away.** Five names for
  one kind of object need pixels to separate them, and below the `min_px` floor of 10 the verifier
  refuses outright. A refusal costs one trace-route run; a wrong acceptance ships a shape that looks
  wrong on the page, and the calibration rule — the tightest setting that costs no recall — spends
  recall to buy that asymmetry deliberately.
- **`primitives_run.py` has no stdlib matrix.** Every function in it renders, so its evidence is
  this eval rather than `tests/test_primitives.py`, which covers the decision module alone. Two of
  the findings above — the derive-before-render rule and the scale sweep — are visible only here.
- **The predicate cannot separate a lone card crop from a lone badge crop** — at the pixels they are
  the same rounded rectangle. What separates them is the inventory step of
  [`references/rebuild-route.md`](../../references/rebuild-route.md), which is an agent's judgement
  (ADR-0175, stated residue).
- **A composite tile is refused, not decomposed.** Fitting the backplate and routing its interior
  through the trace route is a later batch; each extra region is an independent chance at a wrong
  acceptance, and measuring one acceptance had to come first.
- **Stroked and ringed containers refuse** at `hole`. Admitting them needs a stroke width and a
  second calibration axis.
