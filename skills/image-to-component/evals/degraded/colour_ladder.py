"""Rebuild the colour severity ladder the colour source-quality refusal was calibrated on, and score it.

Needs Pillow (`uv run --no-project --with pillow==12.3.0`). Writes into a scratch directory, never into
the eval: the ladder is a calibration record, not an expectation.

    PYTHONPATH=<skill dir> python3 evals/degraded/colour_ladder.py <scratch-dir>

`evals/rubytech/src/rubytech-mark.png` under the same three recipes `ladder.py` uses, at seven scales.
**It goes further down than the glyph ladder on purpose.** At the glyph ladder's floor (×0.25) the mark
is still 33×40 px and every rung reads, so a ladder stopping there carries no positive example and can
calibrate nothing; ×0.20 to ×0.10 is where the mark's regions start to merge.

`UNTRACEABLE` is the rung's own `--auto --kind logo` verdict: nothing in the grid produced an SVG
that passed every check. `references/qa-thresholds.md` § Colour source quality tabulates it against
the measures. Prints one row per rung: name, that verdict, both measures, the measure that refused,
and whether `quality.assess` refuses it.
"""
from __future__ import annotations

import os
import random
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(HERE, "..", "rubytech", "src", "rubytech-mark.png")
SCALES = (0.5, 0.4, 0.33, 0.25, 0.2, 0.15, 0.12)
# A colour rung carries no hand-read label, and deliberately so. Every rung below x0.33 fails QA
# under `--auto` outright, leaving no trace to read: the calibration question for a colour source is
# not "does this read" but "can anything in the grid trace it", and that is a verdict the run itself
# produces. `--traceable` records it; the table in references/qa-thresholds.md is what it produced.
UNTRACEABLE: frozenset[str] = frozenset(f"rubytech-mark.s{s}.q{q}" for s, q in (
    (50, 20), (33, 30), (25, 15), (25, 20), (25, 30),
    (20, 15), (20, 20), (20, 30), (15, 15), (15, 20), (15, 30), (12, 15), (12, 20), (12, 30)))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.splitlines()[5].strip(), file=sys.stderr)
        return 2
    sys.path.insert(0, HERE)
    from ladder import RECIPES, degrade  # the glyph ladder owns the degradation recipes
    from scripts import quality

    out = argv[0]
    os.makedirs(out, exist_ok=True)
    for scale in SCALES:
        for blur, noise, q in RECIPES:
            name = f"rubytech-mark.s{int(scale * 100)}.q{q}"
            img = degrade(Image.open(CLEAN), scale, blur, noise, q,
                          random.Random(f"colour-ladder:{scale}:{q}"))
            img.save(os.path.join(out, f"{name}.png"))
            rgba = img.convert("RGBA")
            verdict = quality.assess(rgba.tobytes(), *rgba.size, mono=False)
            print(name, "untraceable" if name in UNTRACEABLE else "traceable",
                  verdict["stability"], verdict["ramp_extent"], verdict["reason"] or "-",
                  "kept" if verdict["pass"] else "refused", sep="\t")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
