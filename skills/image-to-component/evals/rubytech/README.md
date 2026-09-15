# RubyTech evals

Six assets cropped from two RubyTech brand mockups (a print set: flyer, business card, banner),
supplied by the user on 2026-09-14. Crops are unscaled; `run.sh` applies every transform.

| Source crop | From | Box `x,y,w,h` in the 1536×1024 print sheet | Expectation |
|---|---|---|---|
| `src/computer-icon.png` | flyer front, Computer Services | `44,364,52,44` | pass → `ComputerIcon` (currentColor) |
| `src/gear-icon.png` | flyer front, Recovery + Optimization | `279,364,48,44` | pass → `GearIcon` (currentColor) |
| `src/controller-icon.png` | flyer front, Console Services | `44,488,54,42` | pass → `ControllerIcon` (currentColor) |
| `src/wrench-icon.png` | flyer front, Console Modding | `280,486,46,46` | pass → `WrenchIcon` (currentColor) |
| `src/rubytech-mark.png` | business card front, hexagon mark | `1244,74,132,160` | pass → `RubyTechMark` (colour, 32-colour palette) |
| `src/rubytech-logo.png` | business card front, full lockup | `1117,57,393,249` | **refused** at `budget-bytes`/`budget-paths` — the tagline is text |

The business card is the source for the brand mark because its ground is flat black; the banner's
textured ground keys less cleanly.

## Regenerate

```sh
bash evals/rubytech/run.sh    # 0 all expectations held · 1 one failed · 2 toolchain unavailable
```

Committed goldens in `out/`: `*.svg`, `*.tsx`, `*.qa.json`, `index.ts`. The PNGs `run.sh` writes
beside them (prepared reference, compare sheet) are ignored — regenerate and read
`<Name>.compare.png` when a score moves.

Scores at the pins in `scripts/toolchain.sh` live in `out/<Name>.qa.json` — read them there; a copy
here drifts.

The mark's `mae` sits close to the 12 bound on purpose: the source is a rendered gem with facet
gradients, and 32 flat colours is the fewest that clear it inside the logo budget.
