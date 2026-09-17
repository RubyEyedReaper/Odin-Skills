# Replacement eval

Does `--replace` put the right library icon in, and never the wrong one? The expensive failure is a
**wrong replacement**: it passes every silhouette number and ships the wrong mark. So the record is three
counts, always together — correct, wrong, missed — and any wrong replacement is exit 1.

```sh
bash evals/replace/run.sh                                        # ~15 min: sources, measure, score, held-out
python3 evals/replace/evaluate.py calibrate out/.work/raw.jsonl  # reads the calibrate split ONLY
```

## Sources — synthesised, never committed

`make_sources.py` renders from the pinned libraries into `out/.work/` (library artwork is fetched, not
vendored), in two splits from two seeds:

| Set | What | Per split |
|---|---|---|
| glyphs | 20 Material outlined glyphs in near-black, `--color currentColor` | 160 |
| marks | 8 simple-icons marks in their own hex | 64 |
| tiles | 5 Material `-fill` glyphs and the Facebook mark in colour over a light plate of their outline, on a dark or white page: a knockout | 48 |
| negatives | letter "f" (3 sizes); the RubyTech mark and its four custom glyphs (eval split only) | 3 / 8 |

Every ladder source is drawn at 8, 10, 12, 16, 20, 24, 32 or 40 px, padded, jittered, blurred (σ 0–0.9),
noised (σ 0–8) and JPEG-compressed at quality 20–60.

Each source is named three ways: its **truth** (accepted = correct, refused = missed); **wrong names** —
the other members of its confuser group (wrench/hammer/handyman, schedule/alarm/timer, close/cancel/X), or
one random other ladder icon (accepted = WRONG); and **auto** (accepting anything but the truth = WRONG).
A negative's every acceptance is WRONG.

## Calibration — `scripts/replace.json`

Chosen on the `calibrate` split, then scored once on `eval`. `measure` stores every naming's fit and its
pair margin against each adversary, so `calibrate` and `score` re-decide through `replace.decide_pairs`
— the verifier's own rule — without re-rendering.

| Parameter | Value | Why |
|---|---|---|
| `bar` | 0.55 | lowest swept bar with no wrong naming; recall is flat from 0.5 to 0.6 |
| `margin` | 0.08 | worst wrong naming's margin is −0.0105 (a 8 px info tile named help); 0.08 keeps 0.09 of headroom |
| `min_weight` | 4 | the one wrong naming that cleared the margin had 2.51 px of disagreement evidence; recall is unchanged from 3 |
| `auto_margin` | 0.4 | worst wrong auto candidate sits at 0.242 (a cancel tile read as `mobile_ticket`); 0.4 keeps 0.16 |
| `auto_min_px` | 16 | below 16 px of ink the true icon leaves the shortlist and auto accepts whatever fits best |
| `equivalent`, `shortlist`, `sigmas` | 0.95, 24, 0–1.9 | not swept |

## Results — eval split, committed numbers

`out/counts.tsv` and `out/eval.tsv` are the record.

| Naming | Correct | Wrong | Missed / refused |
|---|---|---|---|
| truth, all rungs | 193 | — | 79 missed |
| truth, rungs ≥ 12 px | 173 / 204 | — | 31 missed |
| wrong names | — | **0** | 344 refused |
| auto (ladder) | 102 | **0** | 170 missed |
| negatives (named and auto) | — | **0** | 16 refused |

Truth recall by class and rung, eval split:

| px | 8 | 10 | 12 | 16 | 20 | 24 | 32 | 40 |
|---|---|---|---|---|---|---|---|---|
| glyphs (of 20) | 3 | 9 | 16 | 18 | 20 | 18 | 20 | 20 |
| marks (of 8) | 3 | 3 | 4 | 7 | 8 | 8 | 8 | 8 |
| tiles (of 6) | 1 | 1 | 0 | 1 | 1 | 6 | 4 | 6 |

Glyphs and marks at ≥ 12 px: **155 / 168 (92.3 %)**. Tiles at ≥ 12 px: 18 / 36 — below 20 px a cut-out
"!" or "i" is two pixels, and the tile's disc is the same disc in every `-fill` icon, so most refuse as
indistinguishable. That is a refusal, not a defect to tune away; it is the re-arm item for knockouts.

## Held-out — scored, never calibrated on

`out/heldout.tsv`, run through `replace_run` with the name a person reading the asset gives it.

| Asset | Named | Result | Why |
|---|---|---|---|
| facebook-mark.low | simple-icons:facebook | refused (bar) | the pre-2023 rounded square; simple-icons ships the circle — falling through is correct (DEC-0182) |
| facebook-banner-mark.low | simple-icons:facebook | refused (adversary) | same older mark |
| alert-mark.low | material:error-fill | **replaced** | knockout reading, margin 0.41 over `video_call-fill`; red fill, light backplate, weight 700, size 24 |
| x-glyph.low | simple-icons:x | **replaced** | margin 0.40 over `hourglass`; `currentColor` |
| clock-glyph.low | material:schedule | refused (bar) | fit 0.44 |
| thermometer-glyph.low | material:device_thermostat, material:thermostat | refused (adversary) | the source sides with `chessdotcom` |

**Wrong replacements: 0 of 6. Replaced: 2 of the 4 marks and glyphs a pinned library draws** (both Facebook
marks are the older version and fall through by design). The handoff's "≥ 5 of 6" counted the two Facebook
marks; under DEC-0182 the ceiling is 4, and 2 were reached. Both compare sheets were read: each is the
right icon.
