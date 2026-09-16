# Degraded evals

The RubyTech assets as a low-quality source would hand them over: half size (the glyphs are 23–27
px), blurred, noisy and JPEG-soft — plus the wrench as a transparent PNG. Built from
`evals/rubytech/src/` by `make_sources.py`; the outputs in `src/` are committed so a Pillow bump
cannot move the input under the eval.

| Source | Expectation |
|---|---|
| `src/{computer,gear,controller,wrench}-icon.low.png` | pass every stage under `--auto` as a `currentColor` glyph, no hand flags; `agreement_iou` ≥ 0.68 against `truth/` |
| `src/computer-icon.destroyed.png` | **refused** at prep by `source-quality` under `--auto` — the computer at ×0.25, whose one-pixel strokes its own noise moves (#1391) |
| `src/rubytech-mark.low.png` | pass under `--auto`, no hand flags, inside the logo budget — see below |
| `src/wrench-icon.alpha.png` | pass with `--bg auto`: a transparent border is not keyed. `--smooth auto` sees its hard edge and smooths the outline |
| `src/wrench-icon.alpha.png` at `--smooth 7` | pass — the Gaussian route `auto` replaced, kept as the comparison |
| `src/wrench-icon.alpha.png` at `--smooth 3` | **refused** at QA by `staircase`, and by nothing else — its steps are kept, and `jaggedness` passes it (#1353) |
| `src/controller-icon.alpha.small.png` | pass with `--smooth auto`: a 32 px aliased glyph whose buttons are 2 px wide |
| `src/controller-icon.alpha.small.png` at `--smooth 7` | **refused** at QA on `edge_f1` — a Gaussian large enough to remove the steps erases the buttons |

## Why a second score, and why a frozen truth

Each run's own QA compares the render with its own prepared reference — which, for a degraded
source, is degraded too. A trace of a blob scores well against a blob: the "before" glyphs below
pass QA at IoU 0.98 with their holes closed. `agreement.py` compares silhouettes with `truth/`
instead, bounding-box normalised because prep trims and pads each run differently.

`truth/` is the clean RubyTech traces at the soft-matte flags, frozen. Two reasons it is frozen and
why it is those: agreement against the live goldens moves every time the clean set improves, so a
before/after needs one fixed reference; and the hard-keyed goldens before them were not a truth at
all — the tolerance cut counted the source's glow halo as subject, fattening every stroke. Against
the source crop, the soft-matte traces are the faithful ones (clean hard vs soft golden agreement:
ComputerIcon 0.85, GearIcon 0.87, ControllerIcon 0.91, WrenchIcon 0.91).

**The ceiling.** No per-pixel method recovers what the degradation destroyed. The best single
threshold on each degraded glyph's upscaled distance map — chosen per image, with the answer in
hand — agrees 0.75 (computer), 0.84 (gear), 0.84 (controller), 0.89 (wrench). The bound sits above
every "before" and below every "after"; it was first written as 0.93, before the ceiling was
measured, and no algorithm can meet that.

**The mark passes — on flags, not on a denoiser.** It was refused for as long as the eval traced it
at `--scale 4`: every upscaled noise boundary becomes path detail, and no colour or speckle setting
brought that under the 40 KB logo budget while keeping `mae` ≤ 12 (the earlier attempts: 32/16
colours, `filter_speckle` 12–32, soft or hard matte, a median denoise, a mode filter on the
palette). SKILL.md's logo row already said `--scale 2`. Colour cleanup before quantize was then
measured in a scratch copy of prep, `mae` always against the run's own noisy reference and the
budget unchanged:

| trace input | scale | colors | speckle | bytes | paths | mae | edge_f1 | verdict |
|---|---|---|---|---|---|---|---|---|
| as before | 4 | 32 | 12 | 85 299 | 135 | – | – | budget |
| median 3 | 4 | 32 | 12 | 87 265 | 135 | – | – | budget |
| palette regions < 16 px merged | 4 | 32 | 12 | 75 905 | 124 | – | – | budget |
| edge-preserving mean (d 60) + merge < 64 px | 4 | 16 | 24 | 34 858 | 33 | 16.80 | 0.692 | mae, edge_f1, jaggedness |
| none | 2 | 32 | 12 | 24 144 | 46 | 13.98 | 0.796 | mae, edge_f1 |
| median 3 | 2 | 32 | 12 | 22 730 | 43 | 14.05 | 0.772 | mae, edge_f1 |
| edge-preserving mean (d 30) | 2 | 32 | 12 | 22 445 | 44 | 13.97 | 0.789 | mae, edge_f1 |
| palette regions < 16 px merged | 2 | 16 | 12 | 18 518 | 34 | 18.91 | 0.719 | mae, edge_f1 |
| none | 2 | 32 | 8 | 30 916 | 81 | 12.07 | 0.861 | mae |
| edge-preserving mean (d 30) | 2 | 64 | 8 | 33 494 | 95 | 11.87 | 0.832 | pass |
| none | 2 | 64 | 9 | 28 889 | 76 | 12.19 | 0.837 | mae |
| none | 2 | 64 | 8 | 32 114 | 94 | 11.56 | 0.836 | pass |
| **none** | **2** | **64** | **7** | **36 123** | **123** | **11.08** | **0.844** | **pass — the eval's flags** |
| none | 2 | 96 | 8 | 34 773 | 102 | 11.29 | 0.874 | pass |
| none | 2 | 64 | 6 | 40 962 | 156 | – | – | budget |

Every denoiser costs `mae`: a flat-colour trace is scored against the noisy pixels, and cleaning
the trace input moves the colours it picks away from the mean of what it is scored against. What
buys `mae` is more colours following the facets' shading and a lower speckle filter keeping the
small facets, and what buys the budget is `--scale 2`. Speckle 7 sits in the middle of the passing
window (6 is over budget, 9 over `mae`), with margins of 3.9 KB and 0.92. The compare sheet keeps
every facet and the controller glyph, and its silhouette agrees 0.887 with the frozen clean mark;
no denoiser lands.

## Regenerate

```sh
bash evals/degraded/run.sh          # 0 all held · 1 one failed · 2 toolchain unavailable
bash evals/degraded/run.sh <dir>    # same, into a scratch directory
uv run --no-project --with pillow==12.3.0 python3 evals/degraded/make_sources.py   # rebuild src/
```

`out/summary.tsv` is the record; `out/*.qa.json` carry every score. Jaggedness is the render's
(`references/qa-thresholds.md`); agreement is against `truth/`.

## Before — the flags SKILL.md recommended

Glyphs `--kind icon --key global --scale 8 --smooth 1.5 --color currentColor`; mark
`--kind logo --scale 4 --colors 32 --set filter_speckle=12 --set layer_difference=12`.

| asset | exit | iou | edge_f1 | jaggedness | agreement_iou | svg_bytes |
|---|---|---|---|---|---|---|
| computer-icon.low | 0 | 0.9784 | 0.9965 | 3.52 | 0.5709 | 2272 |
| gear-icon.low | 0 | 0.9834 | 1.0000 | 8.67 | 0.6629 | 1686 |
| controller-icon.low | 0 | 0.9781 | 0.9997 | 7.26 | 0.6412 | 1756 |
| wrench-icon.low | 0 | 0.9782 | 1.0000 | 8.59 | 0.6631 | 1744 |
| rubytech-mark.low | 1 (`budget-bytes` 89 776) | – | – | – | – | – |

(edge_f1 here is re-scored with the silhouette cut at alpha 128; the eval's first commit recorded
0.91–0.92 against the uncut reference.)

## After — `--matte soft --tolerance 25`

Glyphs `--kind icon --key global --matte soft --tolerance 25 --scale 8 --smooth 1.5 --color
currentColor`; mark as before plus `--matte soft`.

| asset | exit | iou | edge_f1 | jaggedness | agreement_iou | svg_bytes |
|---|---|---|---|---|---|---|
| computer-icon.low | 0 | 0.9535 | 0.9990 | 3.24 | 0.6880 | 2296 |
| gear-icon.low | 0 | 0.9738 | 0.9945 | 2.16 | 0.7299 | 1679 |
| controller-icon.low | 0 | 0.9793 | 1.0000 | 2.88 | 0.8132 | 1152 |
| wrench-icon.low | 0 | 0.9729 | 0.9996 | 1.92 | 0.8375 | 1018 |
| rubytech-mark.low | 1 (budget) | – | – | – | – | – |
| wrench-icon.alpha (`--smooth 7`) | 0 | 0.9614 | 0.9014 | 7.55 | 0.9092 | 2078 |

Agreement rises 0.11–0.17 on every glyph, to within 0.06–0.11 of the ceiling; jaggedness falls
2.5–4.5× on three of four. The computer's own-QA IoU drops 0.025 because its reference stopped
counting the halo — the silhouette it is measured against is thinner, and closer to the source.

## After — `--sharpen 0.8`

Glyphs as above plus `--sharpen 0.8`: the keyed alpha is unsharp-masked at source resolution before
upscaling, so holes and gaps the blur half-filled open again.

| asset | exit | iou | edge_f1 | jaggedness | agreement_iou | ceiling | svg_bytes |
|---|---|---|---|---|---|---|---|
| computer-icon.low | 0 | 0.9526 | 0.9965 | 4.08 | 0.6936 | 0.75 | 2574 |
| gear-icon.low | 0 | 0.9663 | 0.9975 | 2.96 | 0.8237 | 0.84 | 2084 |
| controller-icon.low | 0 | 0.9664 | 0.9926 | 2.05 | 0.8301 | 0.84 | 1602 |
| wrench-icon.low | 0 | 0.9665 | 0.9982 | 2.98 | 0.8720 | 0.89 | 1395 |

Mean agreement 0.767 → 0.805 against a mean ceiling of 0.83: the gap to the ceiling falls from
0.063 to 0.025. The gear gains most (+0.094), the computer least (+0.006). Compare sheets: the
controller's four buttons are separate again, the gear shows its inner ring and hub, the wrench's
jaw is deeper. Own-QA IoU falls 0.001–0.013 and jaggedness rises to 2.0–4.1 — the reference is the
sharpened asset, and a sharper outline turns more; both stay inside their bounds. SVGs grow
300–450 bytes, the detail that came back.

The swept alternatives and why each lost are in `references/tracing-presets.md` (`--sharpen R`).

## After — `--auto`, no hand flags

`run.sh` gives the five assets only `--kind` and, for glyphs, `--color currentColor`. The flags are the
search's (`qa.json` → `search`).

| asset | chose | iou | mae | edge_f1 | jaggedness | agreement_iou | svg_bytes | hand-tuned agreement / bytes |
|---|---|---|---|---|---|---|---|---|
| computer-icon.low | ×8 `--sharpen 0.8 --smooth 1.5` | 0.9526 | – | 0.9965 | 4.08 | 0.6936 | 2574 | 0.6936 / 2574 |
| gear-icon.low | ×8 `--sharpen 0.8 --smooth 0.5` | 0.9629 | – | 0.9967 | 2.84 | 0.8267 | 2045 | 0.8237 / 2084 |
| controller-icon.low | ×8 `--sharpen 0.8 --smooth 1.5` | 0.9664 | – | 0.9926 | 2.05 | 0.8301 | 1602 | 0.8301 / 1602 |
| wrench-icon.low | ×8 `--sharpen 0.8`, smooth auto | 0.9609 | – | 0.9924 | 2.04 | 0.8670 | 1296 | 0.8720 / 1395 |
| rubytech-mark.low | ×2, 64 colours, `filter_speckle=7` | 0.9628 | 11.35 | 0.8458 | 7.17 | 0.8872 | 32524 | 0.887 / 36123 |

Every asset passes with no flag chosen by hand, and every glyph clears `AGREEMENT_MIN`. The search picks
the tuned point exactly for two glyphs; for the gear and the wrench it picks the smallest passing
smoothing, which agrees +0.003 and −0.005 against truth and saves 39 and 99 bytes. For the mark it drops
`layer_difference=12` — 3.6 KB smaller, `mae` 11.35 instead of 11.08, same agreement. Compare sheets:
the gear keeps its inner ring and hub, the wrench its jaw and eye, the mark every facet and the
controller glyph. Wall-clock 22–27 s per asset (the degraded glyphs are ≤ 40 px, so the grid also runs
×16), 3 min 24 s for the whole eval.

## After — colour regions voted smooth

The grid now tries every colour setting with its quantized regions' borders voted smooth
(`--smooth` 0.5 × scale, `scripts/regions.py`) and prefers one that passes. The mark:

| run | iou | mae | edge_f1 | jaggedness | agreement_iou | paths | svg_bytes |
|---|---|---|---|---|---|---|---|
| `--auto` before, ×2 / 64 / speckle 7 | 0.9628 | 11.35 | 0.8458 | 7.17 | 0.8872 | 108 | 32524 |
| same flags `--smooth 1` | 0.9628 | 11.66 | 0.8660 | 5.99 | 0.8870 | 108 | 33717 |
| **`--auto` now**, ×2 / 96 / speckle 7 / `--smooth 1` | 0.9643 | 11.80 | 0.8568 | 7.07 | 0.8853 | 98 | 31122 |

The search takes the smallest smoothed candidate that passes, which is 96 colours rather than 64: fewer
paths and bytes, edge_f1 +0.011, agreement −0.002. Compare sheets: facet borders and the hexagon's
rim run clean where the unsmoothed trace steps along the noise; the controller's buttons are round;
no facet disappears. `jaggedness` is not a reliable judge here — voting at 0.75, 1, 1.5 and 2 px gave
7.05, 5.99, 7.43 and 6.46, non-monotonic, because the render's luma contours cross the noisy shading
inside every facet as well as the borders — so the sheet decides, and `mae` bounds how far it may go.
Wall-clock for the mark 39 s (36 candidates).

## The computer glyph's gap

Under `--auto` the degraded computer agreed 0.694 against a measured ceiling of 0.75; every other glyph
was within 0.03 of its own. Its difference against `truth/`, region by region: the frame is fat on
its **inner** side all the way round, and the leaf is oversized — the dim teal screen and the leaf's
glow, blurred into the cyan stroke, were being counted as coverage. Global soft matte divided distance
by the 95th-percentile subject distance, and with that much mid-bright interior the percentile landed
low, so every mid-distance pixel crossed the α 128 cut.

What was tried, all four degraded glyphs under `--auto`, agreement with `truth/`:

| peak percentile | coverage gamma | computer | gear | controller | wrench | mean |
|---|---|---|---|---|---|---|
| 0.95 | 1 | 0.6936 | 0.8267 | 0.8301 | 0.8670 | 0.8044 |
| 0.99 | 1 | 0.7056 | 0.8246 | 0.8297 | 0.8771 | 0.8093 |
| 0.995 | 1 | 0.7304 | 0.8266 | 0.8272 | 0.8733 | 0.8144 |
| 1.0 | 1 | 0.7217 | 0.8337 | 0.8357 | 0.8694 | 0.8151 |
| **0.99** | **1.15** | **0.7316** | **0.8282** | **0.8459** | **0.8885** | **0.8236** |
| 0.99 | 1.3 | 0.7225 | 0.8127 | 0.8495 | 0.8782 | 0.8157 |
| 0.95 | 1.3 | 0.7190 | 0.8204 | 0.8477 | 0.8888 | 0.8190 |
| 0.95 | 1.6 (hand flags, ×8) | 0.7488 | 0.8041 | 0.8398 | 0.8395 | 0.8081 |
| 0.95 | 2 (hand flags, ×8) | 0.7588 | 0.7749 | 0.8028 | 0.7930 | 0.7824 |

0.99 / 1.15 is the only setting that raises every glyph; it is what `keying.py` ships. The computer's
gap to its ceiling falls from 0.056 to 0.018 and is **not closed**: gamma 1.6–2 reaches 0.749–0.759 on
the computer, but costs the gear, controller and wrench up to 0.07 and fails the computer's own QA at
×8, so it is a per-image threshold, which is what the ceiling already assumes and a pipeline cannot
pick. The remaining difference in the sheet is the leaf, still oversized where its glow meets the
screen. Clean RubyTech glyphs move by at most 0.002 own-QA IoU and agree 0.964–0.984 with their own
earlier traces — thinner by the halo, and all regenerate passing. Held-out pass rate unchanged at 13/20.

## Hard-alpha sources — `--smooth auto`

| asset | exit | iou | edge_f1 | jaggedness | staircase | agreement_iou | svg_bytes |
|---|---|---|---|---|---|---|---|
| wrench-icon.alpha (`--smooth 3`, before auto) | 1 (`staircase`) | 0.979 | 0.9917 | 6.76 | 0.4065 | – | 2690 |
| wrench-icon.alpha (`--smooth 7`) | 0 | 0.9614 | 0.9014 | 7.55 | 0.1367 | 0.9092 | 2078 |
| wrench-icon.alpha (`auto` → outline) | 0 | 0.9666 | 0.9509 | 4.15 | 0.1054 | 0.9090 | 2141 |
| controller-icon.alpha.small (`--smooth 7`) | 1 (`edge_f1`, `iou`) | 0.9323 | 0.7278 | 1.10 | 0.1239 | – | 989 |
| controller-icon.alpha.small (`auto` → outline) | 0 | 0.9573 | 0.9423 | 1.08 | 0.1962 | 0.7973 | 1774 |

Compare sheets: `--smooth 3` keeps every step; `7` rounds both jaw tips of the wrench and fills the
controller's buttons into one blob; `auto` gives clean curves with the jaw tips, the eye and all
eight buttons kept. The controller's agreement is lower than the wrench's because truth/ is the
full-size clean trace and a 32 px source has lost the D-pad's inner corners before tracing starts.

Own-QA IoU and edge_f1 fall for every smoothed hard source because the reference *is* the staircase;
agreement with the clean golden is the score that says the curves are right.

## Source quality and features — the fidelity pass

`computer-icon.destroyed` is one rung of the 48-source ladder the `source-quality` refusal was calibrated
on (`ladder.py` rebuilds it; `references/qa-thresholds.md` § Source quality has the table). It is refused
at prep, before tracing, at silhouette stability 0.806. The four `.low` glyphs, the lowest of which is
the computer at 0.906, keep passing with unchanged SVGs.

The refusal now carries a second measure and a second keying, and neither moves a row here — which is
the point of saying so. Every source in this eval, scored the way its own kind is keyed:

| source | kind | stability | ramp over extent | verdict |
|---|---|---|---|---|
| `computer-icon.destroyed` | glyph | 0.8057 | 0.2500 | **refused**, `stability` (both bounds fail; stability is reported first) |
| `computer-icon.low` | glyph | 0.9063 | 0.0927 | pass |
| `gear-icon.low` | glyph | 0.9566 | 0.1124 | pass |
| `controller-icon.low` | glyph | 0.9723 | 0.1257 | pass |
| `wrench-icon.low` | glyph | 0.9601 | 0.1192 | pass |
| `wrench-icon.alpha`, `controller-icon.alpha.small` | glyph | 1.0 | 0.0 | pass — transparent PNGs, no ground noise to measure |
| `rubytech-mark.low` | colour mark | 0.9912 | 0.0158 | pass |

Bounds are 0.90 / 0.20 for a glyph and 0.97 / 0.06 for a colour mark, keyed globally at tolerance 25
and by flood fill at 40 respectively (`references/qa-thresholds.md` §§ Source quality, Colour source
quality). `computer-icon.low` is the closest pass on this set, 0.006 above the stability bound; the
margin is small because the bound was calibrated on the ladder to sit just under the readable
population, not padded to keep this eval comfortable.

Every row above also carries `features` now: glyphs 1.0, the mark 0.9645 — no expectation moved, and
`--auto` chose the same candidate for every asset.
