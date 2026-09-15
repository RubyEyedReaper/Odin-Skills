# Held-out evals

Ten assets cropped from the two RubyTech mockups that no preset, flag or threshold in this skill was
ever tuned on — none of them appears in `evals/rubytech` or `evals/degraded` — each committed clean
and degraded. Every run uses only the SKILL.md starting row for its class. The pass rate is the
number that says how the skill does on an image nobody picked flags for.

## The freeze rule

The set, its recipe and its flags were committed before any `--auto` or smoothing code existed.
**Nothing in the skill is chosen by reading this set's per-asset metrics, compare sheets or failure
reasons.** Grid axes, derivation rules and smoothing parameters are chosen on `evals/rubytech` and
`evals/degraded`; this set contributes one number to those decisions, the pass rate, read after a
choice is made. A new asset may be added; an existing one is never re-cropped, re-degraded or given
its own flags.

Stated honestly: the baseline's per-asset table below was read once, when it was recorded, and four
compare sheets (MonitorGlyph, ClockGlyph, FacebookMark, WhatsappMark) were looked at to confirm the
eval measures tracing rather than a bad crop — each traces the right shape; the failures are
fidelity, not keying. That table showed small glyphs refused on IoU, which is knowledge the later
work had; the `--scale 16` axis it points towards was justified and sized on RubyTech glyphs
downscaled ×0.4–×0.5 instead (`references/tracing-presets.md`), and no held-out row was read again.

## Sources

`make_sources.py` crops from the two 1536×1024 sheets (the print set and the website set) and writes
`src/<name>.png` unscaled plus `src/<name>.low.png`: ×0.7 bicubic, an additive colour ramp across the
image (the ground becomes a gradient), seeded Gaussian RGB noise σ 4, JPEG quality 20. The recipe is
deliberately unlike `evals/degraded/` (×0.5, blur 0.6, noise 6, JPEG 30). Crops, not the mockups,
are the committed input.

| Asset | Sheet | Box `x,y,w,h` | Class |
|---|---|---|---|
| `monitor-glyph` | print, flyer back, Computer Services | `568,267,39,34` | glyph |
| `gamepad-glyph` | print, flyer back, Console + Modding Services | `839,271,37,30` | glyph |
| `x-glyph` | print, business card back, X | `1141,548,24,28` | glyph |
| `clock-glyph` | website, console services, Clock / Date | `1043,868,21,21` | glyph |
| `thermometer-glyph` | website, console services, Overheating | `856,868,16,22` | glyph |
| `facebook-mark` | print, business card back | `1140,479,26,26` | mark |
| `instagram-mark` | print, business card back | `1139,512,26,26` | mark |
| `whatsapp-mark` | print, business card back | `1139,574,26,29` | mark |
| `alert-mark` | print, flyer back, price notice | `569,192,37,35` | mark |
| `facebook-banner-mark` | print, banner footer | `505,918,32,32` | mark |

## Flags — the SKILL.md rows, by class, never by asset

| Class | Flags |
|---|---|
| clean glyph | `--kind icon --key global --matte soft --color currentColor --scale 8` |
| degraded glyph | `--kind icon --key global --matte soft --tolerance 25 --color currentColor --scale 8 --smooth 1.5 --sharpen 0.8` |
| clean mark | `--kind logo --scale 2 --colors 32 --matte soft` |
| degraded mark | `--kind logo --scale 2 --colors 64 --matte soft --set filter_speckle=7` |

`agreement_iou` is context, never a bar: a degraded glyph's silhouette against its clean crop's own
trace, reported only when that clean run passed.

## Regenerate

```sh
bash evals/heldout/run.sh                      # exit 0 recorded · 1 a run failed as a tool · 2 toolchain unavailable
bash evals/heldout/run.sh <dir> -- --auto      # the same set, extra i2c args on every run
uv run --no-project --with pillow==12.3.0 python3 evals/heldout/make_sources.py   # rebuild src/ from the mockups
```

`out/summary.tsv` and `out/pass-rate.txt` are the record; a refused run keeps its row and nothing else.

## Baseline — starting rows, before `--auto`

Pass rate **5/20**. Wall-clock 90 s for the set.

| asset | exit | failed at | iou | mae | edge_f1 | jaggedness | agreement_iou | svg_bytes |
|---|---|---|---|---|---|---|---|---|
| monitor-glyph | 1 | qa: iou | 0.9463 | 0.0 | 0.9759 | 1.46 | – | 2746 |
| monitor-glyph.low | 1 | qa: iou | 0.9224 | 0.0 | 0.9583 | 2.46 | – | 2739 |
| gamepad-glyph | 0 | – | 0.9766 | 0.0 | 0.9968 | 2.04 | – | 2512 |
| gamepad-glyph.low | 0 | – | 0.9695 | 0.0 | 0.9991 | 3.32 | 0.8659 | 2616 |
| x-glyph | 1 | qa: iou | 0.9234 | 0.0 | 0.9979 | 1.65 | – | 2059 |
| x-glyph.low | 1 | qa: iou | 0.9197 | 0.0 | 0.9760 | 8.00 | – | 2099 |
| clock-glyph | 1 | qa: iou | 0.9172 | 0.0 | 0.9885 | 1.50 | – | 1426 |
| clock-glyph.low | 1 | qa: iou | 0.9343 | 0.0 | 0.9926 | 3.64 | – | 1548 |
| thermometer-glyph | 1 | qa: iou | 0.9285 | 0.0 | 0.9265 | 0.99 | – | 1094 |
| thermometer-glyph.low | 0 | – | 0.9682 | 0.0 | 0.9984 | 1.75 | – | 525 |
| facebook-mark | 1 | qa: edge_f1 | 0.9517 | 11.49 | 0.5101 | 2.20 | – | 1687 |
| facebook-mark.low | 1 | qa: iou, mae | 0.9242 | 15.64 | 0.8838 | 2.91 | – | 1121 |
| instagram-mark | 1 | qa: iou, mae | 0.9457 | 18.49 | 0.9631 | 1.81 | – | 4032 |
| instagram-mark.low | 1 | qa: mae | 0.9505 | 18.09 | 0.8327 | 4.32 | – | 1374 |
| whatsapp-mark | 1 | qa: iou, mae | 0.9290 | 21.85 | 0.9448 | 4.11 | – | 4065 |
| whatsapp-mark.low | 1 | qa: iou, mae | 0.9101 | 32.62 | 0.8955 | 4.75 | – | 1265 |
| alert-mark | 0 | – | 0.9760 | 8.62 | 0.9913 | 1.55 | – | 1457 |
| alert-mark.low | 1 | qa: edge_f1, iou, mae | 0.9385 | 16.17 | 0.5084 | 1.75 | – | 2362 |
| facebook-banner-mark | 0 | – | 0.9735 | 10.16 | 0.9914 | 3.88 | – | 1696 |
| facebook-banner-mark.low | 1 | qa: mae | 0.9606 | 15.37 | 0.8019 | 4.17 | – | 2212 |

Every refusal is at QA; none at the budget or the background check. The starting rows were written
for 42–54 px glyphs and a 132 px mark, and these assets are 16–39 px: thin strokes at that size are
where they fall short.

## Pass rate under `--auto`

Read after each choice was made on `evals/rubytech`, `evals/degraded` and scratch copies of the
RubyTech assets downscaled ×0.4–×0.5 — never on this set's rows.

| Step | Pass rate | Wall-clock |
|---|---|---|
| baseline, starting rows | 5/20 | 90 s |
| `--auto`, smoothing and palette grid at ×8 / ×2 | 7/20 | 166 s |
| + `--scale 16` for a ≤ 40 px glyph | 12/20 | 421 s |
| + `--scale` 3–4 for a ≤ 80 px colour source | 13/20 | 416 s |
| + colour regions voted smooth, preferred when passing | 13/20 | 455 s |
| + global soft matte peak 0.99, coverage gamma 1.15 | 13/20 | 382 s |

## Final — `--auto`, every item landed

`out/` holds this run: `bash evals/heldout/run.sh evals/heldout/out -- --auto`. Pass rate **13/20**, up
from 5/20 on the starting rows (6/20 on those rows after the matte change). A refusal names the nearest
miss's failures and scores.

| asset | exit | failed at | iou | mae | edge_f1 | jaggedness | agreement_iou | svg_bytes |
|---|---|---|---|---|---|---|---|---|
| monitor-glyph | 0 | – | 0.9542 | 0.0 | 0.9913 | 2.0098 | – | 2684 |
| monitor-glyph.low | 0 | – | 0.9607 | 0.0 | 0.9863 | 4.2028 | 0.8181 | 3707 |
| gamepad-glyph | 0 | – | 0.9718 | 0.0 | 0.9899 | 1.5733 | – | 2435 |
| gamepad-glyph.low | 0 | – | 0.9575 | 0.0 | 0.9874 | 2.1296 | 0.8682 | 2536 |
| x-glyph | 0 | – | 0.9609 | 0.0 | 0.996 | 3.9776 | – | 3832 |
| x-glyph.low | 0 | – | 0.9543 | 0.0 | 0.9999 | 3.6532 | 0.5307 | 2894 |
| clock-glyph | 0 | – | 0.9529 | 0.0 | 0.9867 | 2.7107 | – | 2948 |
| clock-glyph.low | 0 | – | 0.9556 | 0.0 | 0.9975 | 1.7039 | 0.6253 | 1920 |
| thermometer-glyph | 0 | – | 0.9652 | 0.0 | 0.9816 | 1.7264 | – | 2005 |
| thermometer-glyph.low | 0 | – | 0.9518 | 0.0 | 0.9717 | 0.9444 | 0.5983 | 436 |
| facebook-mark | 1 | auto:edge_f1 | 0.9558 | 9.7118 | 0.6342 | 2.5938 | – | 2219 |
| facebook-mark.low | 1 | auto:mae | 0.9569 | 14.1763 | 0.8517 | 4.3489 | – | 2372 |
| instagram-mark | 1 | auto:mae | 0.9693 | 16.4778 | 0.8462 | 4.1936 | – | 7864 |
| instagram-mark.low | 1 | auto:mae | 0.9565 | 13.1768 | 0.8625 | 4.956 | – | 3503 |
| whatsapp-mark | 1 | auto:mae | 0.9502 | 15.464 | 0.9019 | 6.0119 | – | 7911 |
| whatsapp-mark.low | 1 | auto:iou,mae | 0.8855 | 19.497 | 0.8903 | 4.6432 | – | 2897 |
| alert-mark | 0 | – | 0.9785 | 11.7877 | 0.9047 | 0.1799 | – | 486 |
| alert-mark.low | 1 | auto:edge_f1 | 0.9604 | 10.9025 | 0.5724 | 1.6002 | – | 5290 |
| facebook-banner-mark | 0 | – | 0.967 | 11.963 | 0.986 | 3.3372 | – | 988 |
| facebook-banner-mark.low | 0 | – | 0.9702 | 11.7418 | 0.8018 | 4.7821 | – | 5787 |

**Read the sheets, not only the rate.** Every glyph passes, and five of them look right — the clean
monitor, gamepad, X, clock and thermometer, plus the degraded monitor and gamepad (agreement 0.82–0.87
with their clean traces). Three degraded glyphs pass while looking wrong: the X's strokes break into
blobs (agreement 0.53), the clock's ring fragments (0.63), and the thermometer becomes a silhouette
with no bulb or tube (0.60). Each is a faithful trace of a reference the ×0.7 JPEG-20 recipe has already
destroyed, and QA compares against that reference — the blind spot `evals/degraded/README.md` names. The
clean alert mark passes with its "!" dot dropped: the search's smallest passing candidate uses
`filter_speckle=12`, and neither `edge_f1` (0.905) nor `mae` counts one dot. Colour marks on the
business-card back fail `mae` at every setting: 26 px gradient marks (Instagram, WhatsApp) are the
case the flat-fill limit in `references/qa-thresholds.md` describes. These are recorded as the
honest state, not tuned away; the follow-ups are #1391 (a destroyed reference passes) and #1392 (a dropped small feature).

