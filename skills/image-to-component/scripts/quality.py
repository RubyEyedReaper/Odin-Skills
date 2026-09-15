"""Source quality: is a glyph source still readable, or has its degradation already destroyed it?

Stdlib only; straight-alpha RGBA buffers, like `keying.py`. `prep.py` and `auto.py` ask it of the
cropped source before keying for tracing, and refuse by name (`source-quality`) when it fails (#1391).

Why a separate refusal: QA scores a trace against its own prepared reference. A source the recipe
has destroyed produces a destroyed reference, and a faithful trace of it passes every fidelity bar —
the held-out X, clock and thermometer glyphs did, broken into blobs. No metric on the trace can see
that; only the source can.

**The measure is silhouette stability under the source's own noise.** The ground's noise σ is read
from neighbouring pixel pairs that are both ground (within `GROUND_TOLERANCE` of the border colour).
The source is keyed as `--auto` keys a glyph (global, soft matte, `autogrid.GLYPH_TOLERANCE`), then
re-keyed `SEEDS` times with fresh Gaussian noise of that σ added, and the α ≥ 128 silhouettes are
compared by IoU. A stroke whose contrast the noise already rivals moves with every draw, and so does
a shape the blur has half-dissolved; a readable stroke does not.

What else was measured, and lost (`references/qa-thresholds.md` § Source quality): edge ramp over
stroke thickness, subject extent, extent over ramp, luminance edge width, and topology stability. On
a severity ladder built from the RubyTech glyphs, none separated the traces that read from the ones
that do not, because readability depends on the glyph — a 14 px controller reads, a 16 px gear does
not. Stability separated best, and not perfectly.

A source with no ground (transparent PNG) or no measurable noise has nothing to perturb and passes.
"""
from __future__ import annotations

import math
import random

from . import autogrid, keying

ALPHA_VISIBLE = 128
GROUND_TOLERANCE = 25
SEEDS = 6
# Calibrated on the ladder (references/qa-thresholds.md): every clean RubyTech and clean held-out glyph
# scores >= 0.978 and every committed evals/degraded glyph >= 0.911; the ladder's unreadable rungs
# score 0.79-0.97 and its readable ones 0.83-0.99. Below 0.90 are 10 of 19 unreadable rungs and 3 of 44
# readable sources, all three a degraded wrench at 7-9 px across.
MIN_STABILITY = 0.90


def ground_noise(buf: bytes, width: int, height: int, bg: tuple[int, int, int]) -> float:
    """σ of the ground's per-channel noise, from horizontal neighbour pairs that are both ground."""
    def ground(o: int) -> bool:
        return buf[o + 3] >= ALPHA_VISIBLE and all(abs(buf[o + c] - bg[c]) <= GROUND_TOLERANCE for c in range(3))

    total = count = 0
    for y in range(height):
        for x in range(width - 1):
            o = (y * width + x) * 4
            if ground(o) and ground(o + 4):
                for c in range(3):
                    total += (buf[o + c] - buf[o + 4 + c]) ** 2
                count += 3
    return 0.0 if count == 0 else math.sqrt(total / count / 2)


def _silhouette(buf: bytes, width: int, height: int, bg: tuple[int, int, int]) -> list[bool]:
    tolerance = autogrid.GLYPH_TOLERANCE
    keyed = keying.key_global(buf, width, height, bg, tolerance)
    keyed = keying.soft_matte(buf, keyed, width, height, bg, tolerance, key="global")
    return [a >= ALPHA_VISIBLE for a in keyed[3::4]]


def assess(buf: bytes, width: int, height: int) -> dict:
    """{"sigma", "stability", "pass"}: mean silhouette IoU across SEEDS noise draws, against MIN_STABILITY."""
    bg = keying.border_background(buf, width, height)
    sigma = 0.0 if bg is None else ground_noise(buf, width, height, bg)
    if bg is None or sigma == 0:
        return {"sigma": round(sigma, 2), "stability": 1.0, "pass": True}
    base = _silhouette(buf, width, height, bg)
    scores = []
    for seed in range(SEEDS):
        rng = random.Random(seed)
        noisy = bytearray(buf)
        for i in range(len(noisy)):
            if i % 4 != 3:
                noisy[i] = max(0, min(255, round(buf[i] + rng.gauss(0, sigma))))
        other = _silhouette(bytes(noisy), width, height, bg)
        union = sum(1 for a, b in zip(base, other) if a or b)
        scores.append(1.0 if union == 0 else sum(1 for a, b in zip(base, other) if a and b) / union)
    stability = sum(scores) / len(scores)
    return {"sigma": round(sigma, 2), "stability": round(stability, 4), "pass": stability >= MIN_STABILITY}
