"""Edge character: is a source's alpha boundary a hard pixel staircase or an anti-aliased ramp?

Stdlib only; operates on straight-alpha RGBA byte buffers, like `keying.py`. `prep.py` asks it of
the keyed, trimmed source *before* upscaling, because an upscale turns a hard edge into a ramp.

A crossing is a pair of 4-neighbours on opposite sides of alpha 128. An aliased edge has only fully
transparent and fully opaque pixels at its crossings; an anti-aliased or soft-matted edge has
partial coverage on one side or both. The answer decides two things downstream: how `--smooth auto` smooths the
silhouette (`outline.py` for hard, a Gaussian for soft), and whether QA holds the render to the
`staircase` bound, which only means something against a hard reference.
"""
from __future__ import annotations

import math

ALPHA_VISIBLE = 128
EXTREME = 16  # alpha within this of 0 or 255 counts as uncovered or fully covered
HARD_EDGE = 0.75
AUTO_RADIUS_PER_SCALE = 0.375


def _extreme(value: int) -> bool:
    return value <= EXTREME or value >= 255 - EXTREME


def hard_edge_fraction(buf: bytes, width: int, height: int) -> float | None:
    """Share of boundary crossings with no partial coverage on either side; None when there are none.

    A crossing is a horizontal or vertical neighbour pair on opposite sides of alpha 128. Counting
    pairs rather than pixels matters: an anti-aliased edge still has a fully opaque pixel inside
    every partial one, and a per-pixel count would call half of it hard.
    """
    alpha = buf[3::4]
    crossings = hard = 0
    for y in range(height):
        for x in range(width):
            value = alpha[y * width + x]
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx < width and ny < height:
                    other = alpha[ny * width + nx]
                    if (value >= ALPHA_VISIBLE) != (other >= ALPHA_VISIBLE):
                        crossings += 1
                        hard += _extreme(value) and _extreme(other)
    return None if crossings == 0 else hard / crossings


def edge_ramp(buf: bytes, width: int, height: int) -> float | None:
    """How wide the boundary is: partially covered pixels per alpha-128 crossing; None when there are none.

    A hard staircase scores 0, an anti-aliased edge about 0.5–1.1 (one partial pixel per side at
    most), a blurred or JPEG-soft edge 1.6 and up — measured on the keyed RubyTech and degraded
    sources (`evals/degraded/README.md`). `autogrid.derive_prep` reads it to decide whether a glyph
    source was blurred enough that its holes need `--sharpen`.
    """
    alpha = buf[3::4]
    partial = sum(1 for v in alpha if EXTREME * 2 <= v <= 255 - EXTREME * 2)
    crossings = 0
    for y in range(height):
        row = y * width
        for x in range(width):
            inside = alpha[row + x] >= ALPHA_VISIBLE
            if x + 1 < width and (alpha[row + x + 1] >= ALPHA_VISIBLE) != inside:
                crossings += 1
            if y + 1 < height and (alpha[row + width + x] >= ALPHA_VISIBLE) != inside:
                crossings += 1
    return None if crossings == 0 else partial / crossings


def smoothing_for(smooth: str, edge: str, scale: float) -> tuple[str, float]:
    """What `--smooth` means for a silhouette: ("outline", σ source px) or ("gaussian", radius px).

    `auto` follows the edge. A hard edge is smoothed along its outline (`outline.py`), because a
    Gaussian radius large enough to remove a one-pixel step also closes holes one or two pixels
    wide. A soft edge keeps the Gaussian, at 0.375 × scale — 3 at ×8, the flag the anti-aliased
    RubyTech glyphs were tuned at. A number is today's Gaussian radius, whatever the edge.
    """
    if smooth == "auto":
        from .outline import SIGMA
        return ("outline", SIGMA) if edge == "hard" else ("gaussian", AUTO_RADIUS_PER_SCALE * scale)
    try:
        radius = float(smooth)
    except ValueError:
        radius = math.nan
    if not radius >= 0:  # also refuses nan
        raise ValueError(f"--smooth must be auto or a radius >= 0, got {smooth!r}")
    return ("gaussian", radius)


def classify(buf: bytes, width: int, height: int) -> str:
    """"hard" or "soft". No boundary at all has no staircase to keep, so it reads as soft."""
    fraction = hard_edge_fraction(buf, width, height)
    return "hard" if fraction is not None and fraction >= HARD_EDGE else "soft"
