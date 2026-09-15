# Degraded evals

The RubyTech assets as a low-quality source would hand them over: half size (the glyphs are 23–27
px), blurred, noisy and JPEG-soft — plus the wrench as a transparent PNG. Built from
`evals/rubytech/src/` by `make_sources.py`; the outputs in `src/` are committed so a Pillow bump
cannot move the input under the eval.

| Source | Expectation |
|---|---|
| `src/{computer,gear,controller,wrench}-icon.low.png` | pass every stage as a `currentColor` glyph; `agreement_iou` ≥ 0.68 against `truth/` |
| `src/rubytech-mark.low.png` | **refused** — see below |
| `src/wrench-icon.alpha.png` | pass with `--bg auto`: a transparent border is not keyed |

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

**The mark is refused.** Noise and JPEG blocking on a gradient-faceted gem trace as slivers past
the logo budget at every setting tried (32/16 colours, `filter_speckle` 12–32, soft or hard matte,
a median denoise, a mode filter on the palette) — and the runs that fit the budget fail `mae` 12
against their own noisy reference (15–18). The route for a noisy multi-colour asset is a cleaner
source, not a looser bar.

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

The alpha wrench moved from `--smooth 3` to `--smooth 7` at integration: its source is a hard 1px
staircase, which `3` traced step for step (6.76, 2690 bytes) and `7` rounds into clean curves. Its
own-QA IoU and edge_f1 fall because the reference *is* the staircase; agreement with the clean
golden holds at 0.909. `jaggedness` cannot rank these — see `references/tracing-presets.md`.
