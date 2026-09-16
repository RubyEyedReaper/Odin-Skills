"""Rebuild the severity ladder the source-quality refusal was calibrated on, and score it.

Needs Pillow (`uv run --no-project --with pillow==12.3.0`). Writes into a scratch directory, never into
the eval: the ladder is a calibration record, not an expectation.

    PYTHONPATH=<skill dir> python3 evals/degraded/ladder.py <scratch-dir>

The four clean RubyTech glyphs at x0.5 / 0.4 / 0.33 / 0.25, each under three recipes, 48 sources.
`UNREADABLE` is the label read from each rung's `--auto` compare sheet — does the trace read as the
glyph — which `references/qa-thresholds.md` § Source quality tabulates. Prints one row per rung:
name, label, silhouette stability, ramp over extent, the measure that refused, and the verdict.

**The labels are re-derived, not inherited.** Every rung in this literal was read again from a sheet
regenerated against a copy of the skill with the refusal disabled, so that refused rungs still
produce one; the diff against the previous set, and the rungs that were contested, are in
`references/qa-thresholds.md`. A threshold calibrated against a label nobody re-checked is
calibrated against nothing.
"""
from __future__ import annotations

import io
import os
import random
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(HERE, "..", "rubytech", "src")
GLYPHS = ("computer-icon", "gear-icon", "controller-icon", "wrench-icon")
SCALES = (0.5, 0.4, 0.33, 0.25)
RECIPES = ((0.6, 6, 30), (0, 4, 20), (0.8, 8, 15))  # (blur, noise, JPEG quality)
# The criterion, so a reader can check these against the sheets rather than take them on trust: does
# the trace still show the feature that makes the glyph that glyph — the monitor's frame, the gear's
# toothed rim, the controller's body and holes, the wrench's OPEN jaw. A dent where the jaw was is
# not a jaw.
UNREADABLE = frozenset(f"{g}.s{s}.q{q}" for g, s, q in (
    ("computer-icon", 25, 15), ("computer-icon", 25, 20), ("computer-icon", 25, 30), ("computer-icon", 33, 15),
    ("computer-icon", 33, 20), ("computer-icon", 33, 30), ("computer-icon", 40, 15), ("computer-icon", 50, 15),
    ("gear-icon", 25, 15), ("gear-icon", 25, 20), ("gear-icon", 25, 30), ("gear-icon", 33, 15),
    ("gear-icon", 33, 20), ("gear-icon", 33, 30), ("gear-icon", 40, 15), ("controller-icon", 25, 15),
    # The three the re-derivation moved, all wrenches whose jaw had closed to a dent (#1410).
    ("wrench-icon", 25, 15), ("wrench-icon", 25, 30), ("wrench-icon", 33, 15), ("wrench-icon", 33, 30),
    ("wrench-icon", 40, 15), ("wrench-icon", 50, 15)))


def degrade(img: Image.Image, scale: float, blur: float, noise: float, quality: int, rng: random.Random) -> Image.Image:
    img = img.convert("RGB")
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.BILINEAR)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    img.putdata([tuple(max(0, min(255, round(c + rng.gauss(0, noise)))) for c in px) for px in img.get_flattened_data()])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.splitlines()[5].strip(), file=sys.stderr)
        return 2
    from scripts import quality

    out = argv[0]
    os.makedirs(out, exist_ok=True)
    for glyph in GLYPHS:
        for scale in SCALES:
            for blur, noise, q in RECIPES:
                name = f"{glyph}.s{int(scale * 100)}.q{q}"
                img = degrade(Image.open(os.path.join(CLEAN, f"{glyph}.png")), scale, blur, noise, q,
                              random.Random(f"ladder:{glyph}:{scale}:{q}"))
                img.save(os.path.join(out, f"{name}.png"))
                rgba = img.convert("RGBA")
                verdict = quality.assess(rgba.tobytes(), *rgba.size)
                print(name, "unreadable" if name in UNREADABLE else "reads", verdict["stability"],
                      verdict["ramp_extent"], verdict["reason"] or "-",
                      "kept" if verdict["pass"] else "refused", sep="\t")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
