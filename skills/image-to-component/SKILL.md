---
name: image-to-component
description: Use when a raster — PNG, JPG, WebP, screenshot, mockup crop — must become an SVG asset or a typed React component. Also on "vectorize", "trace this", "convert to SVG", "icon from this image", "logo to component", "SVG component from a mockup".
---

# image-to-component

> A traced SVG is only as good as the diff that checked it. Numbers decide, not a glance.

## What this is not for

| The task | Its owner |
|---|---|
| A page, screen, card, form or any layout in a mockup | **Rebuild it** — [references/rebuild-route.md](references/rebuild-route.md), then `frontend-design` / `interface-design` |
| Text of any size | Real text in markup. Never traced |
| Designing a new icon or logo | `frontend-design`, `impeccable` |
| A static HTML export | `web-artifacts-builder` |
| A known icon or brand mark, recognisable but too small or degraded to trace | **here, `--replace`** — the pinned library vector, verified against its look-alikes ([references/replacement.md](references/replacement.md)) |
| An asset that is WHOLLY a container shape — an app tile, a badge disc, a status pill, a rounded-rect backplate | **here, `--primitive`** — one fitted `<circle>`/`<rect rx>`/`<ellipse>`, verified against the family it could be instead ([ADR-0175](../../docs/adr/0175-in-asset-containers-are-fitted-primitives.md)) |
| **One isolated icon, logo mark, illustration or object → SVG + TSX** | **here** |

## Pipeline

```sh
bash scripts/doctor.sh          # 0 ready · 1 launcher missing · 3 tools could not resolve
bash scripts/i2c.sh <image> --name <Pascal> --kind icon|logo|illustration --out <dir> --auto [--color currentColor]
bash scripts/i2c.sh <image> --name <Pascal> --kind icon|logo|illustration --out <dir> [flags]   # hand-tuned
bash scripts/i2c.sh <image> --name <Pascal> --kind icon|logo --out <dir> --replace material:build|simple-icons:facebook|auto [--auto]
bash scripts/i2c.sh <image> --name <Pascal> --kind icon --out <dir> --primitive auto [--auto]
bash scripts/typecheck.sh <dir> # strict tsc over every .tsx + writes index.ts
```

`i2c.sh` runs [replace] → [primitive] → prep → trace (vtracer) → optimize (SVGO) → check → generate → QA,
stops at the first failed stage and names it. `--replace` runs first: an accepted replacement ends the run
with the library vector; anything else continues exactly as without it, with the verdict filed in
`qa.json` → `replacement`. `--primitive` runs next and behaves the same way, filing under
`qa.json` → `primitive`; it accepts only an asset that is wholly one container shape and refuses
everything else, including a tile with a glyph on it. Any vtracer parameter passes through as `--set key=value`. Exit 1 = a check refused; 2 = usage or tool failure. Nothing is installed
globally — pins live in `scripts/toolchain.sh`.

## Start with `--auto`

`--auto` takes only what the asset is — `--kind`, `--color currentColor` for a glyph, and optionally
`--crop`/`--bg` — and chooses everything else. It measures the keyed source's edge (`edges.edge_ramp`)
to decide the prep once (a blurred glyph is sharpened; a colour mark is flood-keyed), then runs a
fixed grid of at most 36 candidates in one process — smoothing and, for a ≤ 40 px glyph, `--scale 16`;
palette and `filter_speckle`, each with its colour-region borders voted smooth and without, and for a
≤ 80 px colour source `--scale` 3–4 — and keeps the **smallest SVG that passes every check and QA bar**,
preferring a smoothed colour trace whenever one passes. The winner is re-run through the
ordinary stages; `qa.json` carries the whole grid under `search`. Nothing passing is exit 1 with the
nearest miss named. Measured: 7–85 s per asset; bounded at 300 s. A tuning flag beside `--auto` is
refused. Why the grid varies only trace-side axes: [references/tracing-presets.md](references/tracing-presets.md#auto).

Held-out assets no flag was tuned on (`evals/heldout/`): 5/20 pass on the rows below, 10/20 under `--auto`.
Of the 10 refused, eight are refused at prep as too degraded to read (`source-quality`) — three glyphs
that passed at 13/20 as blobs, and five colour marks, one of which passed with a ragged "f" — and two
are clean marks drawn in thin gradient strokes that fail `mae` (`references/qa-thresholds.md` § Known limits). Every pass looks right on its compare sheet; every search also
holds `features`, so a smaller SVG that drops a dot or fills a hole is never the one chosen.
Under `--replace` the same held-out marks and glyphs give 0 wrong replacements, 2 replaced, 4 refused — both Facebook marks are the pre-2023 artwork and fall through by design (DEC-0182); counts and reasons in [evals/replace/README.md](evals/replace/README.md#held-out--scored-never-calibrated-on).

## Starting flags — when tuning by hand

A prior, not a formula. Start from the row that matches the asset, or from the flags `--auto` recorded;
the refusal table below says what to change next.

| Asset | Flags |
|---|---|
| Single-colour glyph, should inherit text colour | `--kind icon --key global --matte soft --color currentColor --scale 8` |
| Same, from a hard-edged pixel staircase — aliased PNG, pixel art, nearest-neighbour upscale | `--kind icon --color currentColor --scale 8` — `--smooth auto`, the default, sees the hard edge and smooths its outline; a number is a Gaussian that erases 2 px detail before the steps |
| Same, from a blurred, JPEG-soft or ≤ 32 px source | `--kind icon --key global --matte soft --tolerance 25 --color currentColor --scale 8 --smooth 1.5 --sharpen 0.8` |
| Multi-colour logo mark | `--kind logo --scale 2 --colors 32 --matte soft` (one integer; raise toward 48 if `mae` fails) |
| Same, from a noisy or JPEG-soft source | `--kind logo --scale 2 --colors 64 --matte soft --set filter_speckle=7` (never `--scale 4`: upscaled noise is path detail) |
| Illustration | `--kind illustration --colors 24 --matte soft` (raise toward 48 if `mae` fails) |
| Dark shape inside the subject on a dark ground | keep `--key flood` (default) — only edge-connected background is keyed |
| Transparent PNG | nothing extra — a mostly transparent border is not keyed |

`--smooth auto` (the default) reads the source's alpha before upscaling. A hard edge — every
alpha-128 crossing fully on or off — is smoothed along its own outline at σ 0.8 source px, so holes
and 2 px features survive; a soft edge gets a Gaussian of 0.375 × `--scale`. A number overrides it
with that Gaussian radius; the prep stage line says which route ran.

`--matte soft` places the edge halfway between ground and subject instead of wherever colour first
leaves `--tolerance`; without it a soft or glowing edge traces fat and stepped. `--matte hard` (the
default) remains for pixel-exact crisp sources.

Why each exists, and the vtracer numbers: [references/tracing-presets.md](references/tracing-presets.md).

## When a stage refuses

| Refusal | Do | Never |
|---|---|---|
| prep `source-quality` | if a person recognises it as a library icon or brand mark, name it: `--replace <lib>:<slug>` ([references/replacement.md](references/replacement.md)). Otherwise the source is too degraded to read — a glyph or a colour mark, each against its own bars. `qa.json` → `source_quality.reason` says which way: `stability` — its own noise decides its silhouette; `ramp-extent` — its blur is wide next to the subject carrying it, so features have merged. Either way, get a larger or cleaner source (`references/qa-thresholds.md` § Source quality, § Colour source quality) | trace it anyway with hand flags — every trace of it is the wrong shape |
| `opaque-background` | fix keying (`--bg`, `--tolerance`); `--allow-background` only if the ground is part of the design | delete the path by hand |
| `budget-bytes` / `budget-paths` | fewer `--colors`, `--set filter_speckle=12` and up; if it still fails, the input is a layout — rebuild route | raise the budget |
| QA `iou` / `edge_f1` | `--smooth 1.0` or lower, `--scale 6`, re-crop tighter | lower the threshold to pass |
| QA `jaggedness` | `--matte soft`; for a glyph raise `--scale` (8), leaving `--smooth` at `auto` | smooth the SVG by hand |
| QA `staircase` | the source is aliased and its steps were traced: drop the numeric `--smooth` so `auto` smooths the outline | raise the bound; it only applies to a hard source |
| QA `mae` | more `--colors`, `--set layer_difference=12` | score against the quantized raster |
| QA `features` | a named shape (`qa.json` → `lost_features`) is gone: lower `--set filter_speckle`, or more `--colors` when a detail merged into its surround | accept a smaller SVG that drops a dot or fills a hole |

Thresholds and what each metric catches: [references/qa-thresholds.md](references/qa-thresholds.md).
Generated component shape and a11y contract: [references/component-contract.md](references/component-contract.md).

## Worked evals

`evals/heldout/run.sh [dir] [-- --auto]` — ten assets nothing was tuned on, clean and degraded; the
pass rate is the record, and nothing is tuned by reading its per-asset results (its README).
`evals/rubytech/run.sh` — four currentColor glyphs and a colour mark that must pass, and a full
logo lockup (tagline in ~9px type) that **must be refused at the budget**. `evals/degraded/run.sh`
— the same assets half-size, blurred, noisy and JPEG-soft, run under `--auto` with no hand flags: glyphs must pass and agree with a frozen
clean trace, and the noisy colour mark must pass inside the logo budget. Rerun all three after any pin, preset, grid, flag or
threshold change; commit a regeneration on its own. `evals/replace/run.sh` — a seeded ladder of library
icons at 8–40 px, confusers and negatives, scored with `scripts/replace.json`; any wrong replacement is exit 1.
Its numbers are chosen on the `calibrate` split only (its README).

## Red flags

| Thought | Reality |
|---|---|
| "Trace the whole mockup, then split it" | Megabytes of paths, text as outlines, no semantics. Rebuild route. |
| "QA fails by a hair, loosen it" | Thresholds are the product. Change the input, not the bar. |
| "Binary mode on the RGBA file" | vtracer binary ignores alpha → one full square. `i2c.sh` feeds it a silhouette. |
| "It's obviously the Facebook f — lower the margin so it replaces" | A wrong replacement passes every silhouette number and ships the wrong mark. The margin is calibrated on the ladder; a refusal falls through, which is correct. |
| "SVGR would do this" | Considered: traced output is `svg/g/path` only, and `svg2tsx.py` is what the offline gate can test. |

Tests: `python3 -m unittest discover -s tests -t .` (stdlib only, no toolchain).
