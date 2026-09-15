"""Smooth a hard alpha edge along its own outline, at source resolution, before it is upscaled.

Stdlib only; operates on straight-alpha RGBA byte buffers. `prep.py` rasterises the result.

A Gaussian blur of alpha, the `--smooth R` route, is a poor smoother for an aliased source: it acts
on area, so the radius that removes a one-pixel step also closes a two-pixel hole and erases a
controller's buttons, and on a 25-32 px glyph the steps outlast the detail. This instead takes the
marching-squares outline of the unscaled alpha — one closed loop per boundary, holes included —
resamples each at `SPACING` px and convolves its coordinates along the arc with a Gaussian of
`SIGMA` source pixels. Steps have a period of one to three pixels and are removed; features wider
than that keep their shape; and no loop can merge with another, because each is smoothed alone.

A plain Gaussian pulls a closed curve inward by about σ²/2R. `2G − G²` (smoothing the smoothed
curve once more and subtracting) cancels that to second order, so a disc keeps its area.
"""
from __future__ import annotations

import math

from .jaggedness import ALPHA_ISO, alpha_field, contours

SIGMA = 0.8     # source px. Measured: removes the steps of every RubyTech glyph made hard-alpha
SPACING = 0.25  # source px between resampled points
MIN_TURNS = 1.5  # a loop shorter than 2π·MIN_TURNS·σ smooths at a σ it can carry, not to a point


def resample(loop: list[tuple[float, float]], spacing: float) -> list[tuple[float, float]]:
    closed = loop + [loop[0]]
    segments = [math.dist(closed[i], closed[i + 1]) for i in range(len(loop))]
    total = sum(segments)
    count = max(4, round(total / spacing))
    step = total / count
    out, index, walked = [], 0, 0.0
    for k in range(count):
        target = k * step
        while index < len(segments) - 1 and walked + segments[index] < target:
            walked += segments[index]
            index += 1
        t = (target - walked) / segments[index] if segments[index] else 0.0
        (x0, y0), (x1, y1) = closed[index], closed[index + 1]
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def _convolve(points: list[tuple[float, float]], sigma: float, spacing: float) -> list[tuple[float, float]]:
    n = len(points)
    reach = min(max(1, int(3 * sigma / spacing)), (n - 1) // 2)
    offsets = range(-reach, reach + 1)
    weights = [math.exp(-0.5 * (k * spacing / sigma) ** 2) for k in offsets]
    total = sum(weights)
    return [(sum(w * points[(i + k) % n][0] for k, w in zip(offsets, weights)) / total,
             sum(w * points[(i + k) % n][1] for k, w in zip(offsets, weights)) / total)
            for i in range(n)]


def smooth_loop(loop: list[tuple[float, float]], sigma: float = SIGMA,
                spacing: float = SPACING) -> list[tuple[float, float]]:
    points = resample(loop, spacing)
    sigma = min(sigma, len(points) * spacing / (2 * math.pi * MIN_TURNS))
    once = _convolve(points, sigma, spacing)
    twice = _convolve(once, sigma, spacing)
    return [(2 * a - c, 2 * b - d) for (a, b), (c, d) in zip(once, twice)]


def smoothed_outlines(buf: bytes, width: int, height: int,
                      sigma: float = SIGMA) -> list[list[tuple[float, float]]]:
    """Every alpha-128 outline of `buf`, smoothed; coordinates in pixel-edge units (x ∈ [0, width])."""
    return [smooth_loop(loop, sigma) for loop in contours(alpha_field(buf, width, height), width, height, ALPHA_ISO)]
