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
| **One isolated icon, logo mark, illustration or object → SVG + TSX** | **here** |

## Pipeline

```sh
bash scripts/doctor.sh          # 0 ready · 1 launcher missing · 3 tools could not resolve
bash scripts/i2c.sh <image> --name <Pascal> --kind icon|logo|illustration --out <dir> [flags]
bash scripts/typecheck.sh <dir> # strict tsc over every .tsx + writes index.ts
```

`i2c.sh` runs prep → trace (vtracer) → optimize (SVGO) → check → generate → QA, stops at the first
failed stage and names it. Any vtracer parameter passes through as `--set key=value`. Exit 1 = a check refused; 2 = usage or tool failure. Nothing is installed
globally — pins live in `scripts/toolchain.sh`.

## Starting flags — a prior, not a formula

Start from the row that matches the asset; the refusal table below says what to change next.

| Asset | Flags |
|---|---|
| Single-colour glyph, should inherit text colour | `--kind icon --key global --color currentColor --smooth 1.5`, `--scale 4`–`6` if under ~64px |
| Multi-colour logo mark | `--kind logo --scale 2 --colors 16` (one integer; raise toward 32 if `mae` fails) |
| Illustration | `--kind illustration --colors 24` (raise toward 48 if `mae` fails) |
| Dark shape inside the subject on a dark ground | keep `--key flood` (default) — only edge-connected background is keyed |

Why each exists, and the vtracer numbers: [references/tracing-presets.md](references/tracing-presets.md).

## When a stage refuses

| Refusal | Do | Never |
|---|---|---|
| `opaque-background` | fix keying (`--bg`, `--tolerance`); `--allow-background` only if the ground is part of the design | delete the path by hand |
| `budget-bytes` / `budget-paths` | fewer `--colors`, `--set filter_speckle=12` and up; if it still fails, the input is a layout — rebuild route | raise the budget |
| QA `iou` / `edge_f1` | `--smooth 1.0` or lower, `--scale 6`, re-crop tighter | lower the threshold to pass |
| QA `mae` | more `--colors`, `--set layer_difference=12` | score against the quantized raster |

Thresholds and what each metric catches: [references/qa-thresholds.md](references/qa-thresholds.md).
Generated component shape and a11y contract: [references/component-contract.md](references/component-contract.md).

## Worked evals

`evals/rubytech/run.sh` — four currentColor glyphs and a colour mark that must pass, and a full
logo lockup (tagline in ~9px type) that **must be refused at the budget**. Rerun after any pin,
preset or threshold change; commit a regeneration on its own.

## Red flags

| Thought | Reality |
|---|---|
| "Trace the whole mockup, then split it" | Megabytes of paths, text as outlines, no semantics. Rebuild route. |
| "QA fails by a hair, loosen it" | Thresholds are the product. Change the input, not the bar. |
| "Binary mode on the RGBA file" | vtracer binary ignores alpha → one full square. `i2c.sh` feeds it a silhouette. |
| "Looks right at 400px" | Also rendered at 24px and 4×; `scale_smoke` in `qa.json` says so. |
| "SVGR would do this" | Considered: traced output is `svg/g/path` only, and `svg2tsx.py` is what the offline gate can test. |

Tests: `python3 -m unittest discover -s tests -t .` (stdlib only, no toolchain).
