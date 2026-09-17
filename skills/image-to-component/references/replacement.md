# Replacement — recognise, verify, emit the library vector

`--replace` is the route for a source a human recognises at a glance: a 16 px JPEG'd Facebook "f", an
8 px wrench, an `X` close glyph. Cleaning a source like that into a trace costs more than it is worth and
usually fails `source-quality`. The canonical vector already exists in a pinned library; the only hard
part is being sure it is the right one.

```sh
bash scripts/i2c.sh <image> --name <Pascal> --kind icon --out <dir> --color currentColor --replace material:build
bash scripts/i2c.sh <image> --name <Pascal> --kind logo --out <dir> --replace simple-icons:facebook
bash scripts/i2c.sh <image> --name <Pascal> --kind icon --out <dir> --color currentColor --replace auto
```

It runs before prep. Accepted → `<Name>.svg`, `<Name>.tsx`, `<Name>.compare.png` and a passing `qa.json`
whose `replacement` block says why. Not accepted → the run continues exactly as it would without the flag,
and `qa.json` still carries the verdict under `replacement`.

## Libraries

| Library | Pin (`scripts/toolchain.sh`) | Licence | Used for |
|---|---|---|---|
| `simple-icons` | `simple-icons@16.31.0` | CC0-1.0 icon data; every mark is a trademark of its owner | brand marks |
| `material` | `@material-symbols/svg-<weight>@0.47.3`, outlined (and `-fill`) | Apache-2.0, Copyright Google LLC | generic glyphs |

Both are single fill-only paths, so a replacement stays inside the dialect `svg2tsx` transcribes (#1352).
They are fetched into `$I2C_LIB_CACHE` with `npm pack`, never vendored; the index a search reads
(`i2c-index-v<N>.json`, one per package version) is built there on first use, about three minutes. A version
bump is a recorded decision and re-runs `evals/replace`.

## How a name is verified (DEC-0178, DEC-0179)

Naming a candidate does not make it true. The verifier is adversarial by construction:

1. **Key once, choose the readings.** The source is keyed as `--auto` keys it. Its silhouette is read as
   `alpha` (the keyed alpha), `knockout` (two flat colours: the one on the silhouette's edge is the ink,
   the other a hole — a white "!" cut out of a red disc), or `ground` (page the flood key could not reach,
   left opaque inside the mark, read as holes). A cut-out that never meets the edge, or holes the colour of
   the page, drop the filled `alpha` reading, so a filled disc cannot stand in for a mark with a hole in it.
2. **Shortlist the adversaries.** Every library icon is ranked by thumbnail distance (at four blur
   levels), the nearest 400 are rendered at source size and re-ranked by fit; the best `shortlist` go on.
   The shortlist never depends on the name — the icon the source really is sits in it either way.
3. **Degrade to match, never clean.** Every candidate — named and adversary alike — is fitted by moments,
   rendered supersampled, box-reduced to source size, blurred by the sigma whose edge ramp matches the
   source's, and stretched the way keying stretched the source.
4. **Decide.** The named candidate must clear `bar` (soft IoU) and, against every distinguishable
   adversary, the source must side with it by `margin` on the pixels where the two renders disagree. An
   adversary that differs by fewer than `min_weight` pixels refuses too: a replacement nobody can verify at
   this size is not accepted. `auto` names the best-fitting shortlist entry, holds it to `auto_margin`, and
   refuses a source with less than `auto_min_px` of ink, where the true icon falls out of the shortlist.

A misnamed object therefore cannot force a replacement. The numbers live in `scripts/replace.json`, chosen
on the `calibrate` split of `evals/replace` only; held-out is never read to choose them. Measured on the eval
split: no wrong replacement, 92 % of glyphs and marks at ≥ 12 px replaced, knockout tiles below 24 px
mostly refused as indistinguishable ([evals/replace/README.md](../evals/replace/README.md)).

## Scale

`scripts/scales.json` is the one declaration (DEC-0181). The component keeps the library `viewBox`, so the
library's optical padding survives, and takes a `size` prop defaulting to the rendered size snapped to the
nearest icon step (12/16/20/24/32/40/48) within `snap_tolerance`; off-scale sizes are kept as measured and
the record says no step matched. A Material glyph's weight (100–700) is the one whose own stroke ratio,
rendered and degraded at source size, is nearest the source's; the weight packages are fetched on first use.

## Brand marks and trademarks (DEC-0182)

- The generated component's header names library, slug, version and licence, and for a simple-icons mark:
  "`<Title>` is a trademark of its owner — follow its brand guidelines", with the guidelines URL when the
  library records one. Using the component is still subject to those guidelines.
- A brand mark is never recoloured. In original colour it is drawn in its own hex, and a source drawn in a
  different colour is refused (`brand-colour`) and falls through; `--color currentColor` is the only way
  to paint it otherwise.
- An older version of a mark (the pre-2023 Facebook rounded square) is a different shape; it fails the
  match and falls through. That is the correct outcome, not a miss to tune away.
- Gradient marks (Instagram, WhatsApp's older tile) are replaced only as `currentColor` glyphs; DEC-0168
  stands.

## The record

`qa.json` → `replacement`: `named`, `fit`, `runner_up`, `margin`, `weight` (the disagreement evidence, in
pixels), `accepted`, `reason` (`bar`, `adversary`, `indistinguishable`, `brand-colour`, `check:<finding>`),
`interpretation`, `sigma`, `step`, `mode`, `libraries`; when emitted also `library`, `slug`, `version`,
`licence`, `emission`, `material_weight` with the measured `stroke_ratio`, and the snapped `size`.

## What is not replaced

- Anything no pinned library ships: a product's own glyphs and logos. `evals/replace` holds the RubyTech mark
  and custom glyphs as negatives; replacing one is a wrong replacement.
- Containers, cards and buttons — the rebuild route ([rebuild-route.md](rebuild-route.md)).
- Text. Never traced, never replaced.
