"""Jaggedness: how much an outline zig-zags at a scale finer than its real shape.

Stdlib only; operates on straight-alpha RGBA byte buffers, like `diffmetric.py`.

IoU and edge-F1 both absorb a pixel staircase or a tracer wobble: the outline is in the right
place, it just is not smooth. This measures that directly. Contours are extracted with marching
squares at sub-pixel precision, resampled at 1 px, and walked with a chord of `FINE` and of
`COARSE` pixels. Along each, *excess turning* is total absolute turning minus the net turning of
the loop — zero for a convex outline, π for each concave right angle. A real corner persists at
both chords; a stair or a wobble cancels against its neighbour at the fine chord and has vanished
at the coarse one. The difference, per pixel of outline, scaled by the image diagonal so it does
not depend on render size, is the score.

Contours are taken on alpha, and on luma composited over mid-grey at three levels, so boundaries
between colour regions count in a colour asset and not only its silhouette.
"""
from __future__ import annotations

import math

ALPHA_ISO = 128.0
LUMA_ISOS = (64.0, 128.0, 192.0)
GREY = 127.5
FINE, COARSE = 3, 12


def alpha_field(buf: bytes, width: int, height: int) -> list[float]:
    return [float(buf[i]) for i in range(3, width * height * 4, 4)]


def luma_field(buf: bytes, width: int, height: int) -> list[float]:
    out = []
    for i in range(0, width * height * 4, 4):
        alpha = buf[i + 3] / 255
        luma = 0.299 * buf[i] + 0.587 * buf[i + 1] + 0.114 * buf[i + 2]
        out.append(luma * alpha + GREY * (1 - alpha))
    return out


def contours(field: list[float], width: int, height: int, iso: float,
             pad: float = 0.0) -> list[list[tuple[float, float]]]:
    """Closed iso-lines of `field` through pixel centres; outside the image reads as `pad`."""
    def at(x, y):
        return field[y * width + x] if 0 <= x < width and 0 <= y < height else pad

    def point(edge):
        kind, x, y = edge
        a, b = (at(x, y), at(x + 1, y)) if kind == "h" else (at(x, y), at(x, y + 1))
        t = (iso - a) / (b - a)
        return (x + t + 0.5, y + 0.5) if kind == "h" else (x + 0.5, y + t + 0.5)

    links: dict[tuple, list[tuple]] = {}

    def link(e1, e2):
        links.setdefault(e1, []).append(e2)
        links.setdefault(e2, []).append(e1)

    for y in range(-1, height):
        for x in range(-1, width):
            tl, tr, br, bl = at(x, y), at(x + 1, y), at(x + 1, y + 1), at(x, y + 1)
            itl, itr, ibr, ibl = tl >= iso, tr >= iso, br >= iso, bl >= iso
            top, right, bottom, left = ("h", x, y), ("v", x + 1, y), ("h", x, y + 1), ("v", x, y)
            crossed = [e for e, c in ((top, itl != itr), (right, itr != ibr),
                                      (bottom, ibr != ibl), (left, ibl != itl)) if c]
            if len(crossed) == 2:
                link(*crossed)
            elif len(crossed) == 4:  # saddle: the cell centre decides which diagonal is joined
                if ((tl + tr + br + bl) / 4 >= iso) == itl:
                    link(top, right)
                    link(bottom, left)
                else:
                    link(top, left)
                    link(bottom, right)

    loops, seen = [], set()
    for start in links:
        if start in seen:
            continue
        loop, previous, current = [], None, start
        while current not in seen:
            seen.add(current)
            loop.append(point(current))
            a, b = links[current]
            previous, current = current, (b if a == previous else a)
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def loop_length(loop: list[tuple[float, float]]) -> float:
    return sum(math.dist(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop)))


def _resample(loop: list[tuple[float, float]]) -> list[tuple[float, float]]:
    closed = loop + [loop[0]]
    segments = [math.dist(closed[i], closed[i + 1]) for i in range(len(loop))]
    count = max(3, round(sum(segments)))
    spacing = sum(segments) / count
    out, index, walked = [], 0, 0.0
    for k in range(count):
        target = k * spacing
        while walked + segments[index] < target:
            walked += segments[index]
            index += 1
        t = (target - walked) / segments[index] if segments[index] else 0.0
        (x0, y0), (x1, y1) = closed[index], closed[index + 1]
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def excess_turning(loop: list[tuple[float, float]], stride: int) -> float:
    """Absolute minus net turning along chords of `stride` px, averaged over every phase."""
    points = _resample(loop)
    n = len(points)
    stride = min(stride, n // 4)
    if stride < 1:
        return 0.0
    total = 0.0
    for phase in range(stride):
        starts = range(phase, phase + n - n % stride, stride)
        angles = [math.atan2(points[(i + stride) % n][1] - points[i % n][1],
                             points[(i + stride) % n][0] - points[i % n][0]) for i in starts]
        turns = [math.remainder(angles[(j + 1) % len(angles)] - angles[j], math.tau)
                 for j in range(len(angles))]
        total += sum(abs(t) for t in turns) - abs(sum(turns))
    return total / stride


def _source_pixel_turning(buf: bytes, width: int, height: int, scale: int) -> float:
    """Alpha-outline turning that cancels at one source pixel and is gone by two, per px, × diagonal."""
    cancelled = length = 0.0
    for loop in contours(alpha_field(buf, width, height), width, height, ALPHA_ISO):
        cancelled += max(0.0, excess_turning(loop, scale) - excess_turning(loop, 2 * scale))
        length += loop_length(loop)
    return 0.0 if length == 0 else cancelled * math.hypot(width, height) / length


def staircase(render: bytes, reference: bytes, width: int, height: int, scale: float) -> float:
    """Share of the reference's source-pixel staircase the render keeps: 1.0 is every step.

    `jaggedness` walks strides fixed in render pixels, so at `--scale 8` a one-pixel source step is
    a real corner at both of them and never cancels (#1353). Striding in source pixels sees the
    step, but a render's turning at that stride alone does not separate a kept staircase from
    genuine small shape — a 26 px gear's teeth score as high. Its ratio to the reference's own does:
    measured over four hard-alpha glyphs at ×4/×6/×8, a Gaussian `--smooth` of 0.375 × scale kept
    0.36–0.65, and every smoothing that removed the steps kept 0.09–0.37. Only meaningful against a
    hard-edged reference (`edges.py`): a soft one's turning is its shape, and a faithful render
    keeps most of it.
    """
    stride = round(scale)
    if stride < 2:
        raise ValueError(f"staircase needs a scale of at least 2 (a source pixel of 2+ render px), got {scale}")
    kept = _source_pixel_turning(reference, width, height, stride)
    return 0.0 if kept == 0 else _source_pixel_turning(render, width, height, stride) / kept


def jaggedness(buf: bytes, width: int, height: int) -> float:
    fields = [(alpha_field(buf, width, height), (ALPHA_ISO,), 0.0),
              (luma_field(buf, width, height), LUMA_ISOS, GREY)]
    cancelled = length = 0.0
    for field, isos, pad in fields:
        for iso in isos:
            for loop in contours(field, width, height, iso, pad):
                cancelled += max(0.0, excess_turning(loop, FINE) - excess_turning(loop, COARSE))
                length += loop_length(loop)
    return 0.0 if length == 0 else cancelled * math.hypot(width, height) / length
