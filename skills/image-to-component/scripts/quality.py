"""Source quality: is a glyph source still readable, or has its degradation already destroyed it?

Stdlib only; straight-alpha RGBA buffers, like `keying.py`. `prep.py` and `auto.py` ask it of the
cropped source before keying for tracing, and refuse by name (`source-quality`) when it fails (#1391).

Why a separate refusal: QA scores a trace against its own prepared reference. A source the recipe
has destroyed produces a destroyed reference, and a faithful trace of it passes every fidelity bar —
the held-out X, clock and thermometer glyphs did, broken into blobs. No metric on the trace can see
that; only the source can.

**Two measures, combined as an OR, and the verdict names the one that refused.** They answer
different questions and a blended score would hide both.

*Silhouette stability.* The ground's noise σ is read from neighbouring pixel pairs that are both
ground (within `GROUND_TOLERANCE` of the border colour). The source is keyed as `--auto` keys a
glyph (global, soft matte, `autogrid.GLYPH_TOLERANCE`), then re-keyed `SEEDS` times with fresh
Gaussian noise of that σ added, and the α ≥ 128 silhouettes are compared by IoU. A stroke whose
contrast the noise already rivals moves with every draw; a readable stroke does not.

*Edge ramp over subject extent.* How soft the source's boundary is, read against the size of the
subject carrying it. This is the half stability misses: a thick glyph the blur has merged sits
perfectly still under noise and is still the wrong shape — a gear whose teeth are gone is stable and
wrong. Nine of the ladder's twenty catches are this measure's alone.

What else was measured, and lost (`references/qa-thresholds.md` § Source quality): edge ramp over
stroke thickness, subject extent, extent over ramp, luminance edge width, topology stability,
threshold IoU, ramp mass, interior dimness, blur robustness and interior valleys. None separated the
traces that read from the ones that do not, because readability depends on the glyph — a 14 px
controller reads, a 16 px gear does not.

A source with no ground (transparent PNG) or no measurable noise has nothing to perturb and passes.
"""
from __future__ import annotations

import math
import random

from . import autogrid, edges, keying

ALPHA_VISIBLE = 128
GROUND_TOLERANCE = 25
SEEDS = 6
# Calibrated on the ladder (references/qa-thresholds.md): every clean RubyTech and clean held-out glyph
# scores >= 0.978 and every committed evals/degraded glyph >= 0.911; the ladder's unreadable rungs
# score 0.79-0.97 and its readable ones 0.83-0.99. Below 0.90 are 10 of 19 unreadable rungs and 3 of 44
# readable sources, all three a degraded wrench at 7-9 px across.
MIN_STABILITY = 0.90
# Calibrated jointly with MIN_STABILITY on the relabelled ladder (references/qa-thresholds.md
# § Source quality). At this pair 20 of the ladder's 22 unreadable rungs are refused and 2 of its 26
# readable ones, against 11 and 2 for stability alone; 9 of the catches are this measure's alone.
# MIN_STABILITY did not move: every catch above its own is this measure's, and a wider margin was
# available at 0.89 but buys nothing a verdict can see.
MAX_RAMP_EXTENT = 0.20

# A colour mark is assessed by the same two measures, keyed the way `--auto` keys a colour source
# (#1409). Nothing about a blur being wide next to its subject is specific to a glyph; what is
# specific is the keying, and getting that wrong is what made three colour-only candidates read
# backwards (references/qa-thresholds.md, Colour source quality).
#
# The bars are the mark's own because a mark is a different object: it is keyed by flood rather than
# globally, so its extent is the whole mark rather than a glyph's strokes, and a ramp that leaves a
# glyph readable has already merged a mark's regions. Calibrated on the colour ladder
# (evals/degraded/colour_ladder.py, 21 rungs) and the clean colour assets, never on held-out:
# no rung the `--auto` grid can still trace is refused, no clean colour asset is refused, and 11 of
# the 14 rungs nothing in the grid can trace are refused before the grid is entered.
COLOUR_TOLERANCE = 40
MIN_COLOUR_STABILITY = 0.97
MAX_COLOUR_RAMP_EXTENT = 0.06



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


def _matted(buf: bytes, width: int, height: int, bg: tuple[int, int, int], mono: bool = True) -> bytes:
    """The source keyed the way `--auto` keys it: a glyph globally at GLYPH_TOLERANCE, a colour mark
    flood at COLOUR_TOLERANCE. Both take the soft matte, and the measures below read the result.

    Keying a colour mark the glyph way is what made an earlier attempt read backwards: a global key
    at tolerance 25 cuts a mark's own dark regions out of it, so the "subject" whose extent the ramp
    is divided by was the surviving fragments.
    """
    tolerance = autogrid.GLYPH_TOLERANCE if mono else COLOUR_TOLERANCE
    key = "global" if mono else "flood"
    keyed = (keying.key_global if mono else keying.key_flood)(buf, width, height, bg, tolerance)
    return keying.soft_matte(buf, keyed, width, height, bg, tolerance, key=key)


def _silhouette(buf: bytes, width: int, height: int, bg: tuple[int, int, int], mono: bool = True) -> list[bool]:
    return [a >= ALPHA_VISIBLE for a in _matted(buf, width, height, bg, mono)[3::4]]


def ramp_extent(buf: bytes, width: int, height: int, bg: tuple[int, int, int], mono: bool = True) -> float:
    """`edges.edge_ramp` of the keyed source over the longest side of its silhouette's bounding box.

    A blur destroys features smaller than its own width, and a glyph's features scale with the
    glyph, so an edge ramp only means something next to the size of the subject carrying it. The
    same 2 px of softness is nothing on a 40 px mark and the whole of a 9 px one. 0.0 when nothing
    is visible or there is no boundary to measure.
    """
    keyed = _matted(buf, width, height, bg, mono)
    ramp = edges.edge_ramp(keyed, width, height)
    if ramp is None:
        return 0.0
    visible = [i for i, a in enumerate(keyed[3::4]) if a >= ALPHA_VISIBLE]
    if not visible:
        return 0.0
    xs = [i % width for i in visible]
    ys = [i // width for i in visible]
    extent = max(max(xs) - min(xs), max(ys) - min(ys)) + 1
    return ramp / extent


def _noise_draws(buf: bytes, sigma: float):
    """SEEDS copies of `buf` with fresh Gaussian RGB noise of `sigma`, alpha untouched."""
    for seed in range(SEEDS):
        rng = random.Random(seed)
        noisy = bytearray(buf)
        for i in range(len(noisy)):
            if i % 4 != 3:
                noisy[i] = max(0, min(255, round(buf[i] + rng.gauss(0, sigma))))
        yield bytes(noisy)


def stability(buf: bytes, width: int, height: int, bg: tuple[int, int, int], sigma: float,
              mono: bool = True) -> float:
    """Mean silhouette IoU across `SEEDS` draws of the source's own ground noise."""
    base = _silhouette(buf, width, height, bg, mono)
    scores = []
    for noisy in _noise_draws(buf, sigma):
        other = _silhouette(noisy, width, height, bg, mono)
        union = sum(1 for a, b in zip(base, other) if a or b)
        scores.append(1.0 if union == 0 else sum(1 for a, b in zip(base, other) if a and b) / union)
    return sum(scores) / len(scores)


def assess(buf: bytes, width: int, height: int, mono: bool = True) -> dict:
    """Is this source readable enough to trace? `reason` names the measure that refused, or None.

    Returns `{"sigma", "stability", "ramp_extent", "reason", "pass"}`. The two measures are
    independent and combine as an OR: stability catches a stroke the source's own noise rivals,
    `ramp_extent` a shape its blur has merged, and neither sees what the other does — which is why
    the verdict names the one that fired rather than averaging them into a single score. A source
    with no ground, or none with measurable noise, has nothing to perturb and passes.
    """
    min_stability = MIN_STABILITY if mono else MIN_COLOUR_STABILITY
    max_ramp = MAX_RAMP_EXTENT if mono else MAX_COLOUR_RAMP_EXTENT
    bg = keying.border_background(buf, width, height)
    sigma = 0.0 if bg is None else ground_noise(buf, width, height, bg)
    if bg is None or sigma == 0:
        return {"sigma": round(sigma, 2), "stability": 1.0, "ramp_extent": 0.0,
                "mono": mono, "reason": None, "pass": True}
    moved = stability(buf, width, height, bg, sigma, mono)
    merged = ramp_extent(buf, width, height, bg, mono)
    reason = "stability" if moved < min_stability else "ramp-extent" if merged > max_ramp else None
    return {"sigma": round(sigma, 2), "stability": round(moved, 4), "ramp_extent": round(merged, 4),
            "mono": mono, "reason": reason, "pass": reason is None}


def refusal_message(assessment: dict) -> str:
    """Name the measure that refused, not just the fact of the refusal — they mean different things."""
    mono = assessment["mono"]
    subject = "glyph" if mono else "mark"
    tail = (f"the degradation has already decided this {subject}'s shape; supply a larger or cleaner source, "
            "or --replace <lib>:<slug>")
    if assessment["reason"] == "ramp-extent":
        bound = MAX_RAMP_EXTENT if mono else MAX_COLOUR_RAMP_EXTENT
        return (f"source-quality: edge ramp over subject extent {assessment['ramp_extent']:.3f} is above "
                f"{bound:g} — the blur is wide next to the {subject} carrying it, so its "
                f"features have merged; {tail}")
    bound = MIN_STABILITY if mono else MIN_COLOUR_STABILITY
    return (f"source-quality: silhouette stability {assessment['stability']:.3f} under the source's own noise "
            f"(sigma {assessment['sigma']:g}) is below {bound:g} — {tail}")

