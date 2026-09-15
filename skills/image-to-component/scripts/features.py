"""Feature preservation: does every small shape the reference has survive into the render?

Stdlib only; same-sized straight-alpha RGBA buffers, like `diffmetric.py`, which calls it. IoU, `mae`
and `edge_f1` all average over the image, so a missing dot or a filled hole costs them a fraction of a
percent — `--auto` once shipped an alert mark without the dot of its "!" (#1392). This counts features
instead of pixels.

A **feature** is a region of the reference that one colour — or transparency — holds together:
seeded region growing, a pixel joining while it stays within `SEGMENT_TOLERANCE` of the region's
running mean. A region counts only when its **core** — what is left after eroding it by
`ERODE_SOURCE_PX` source px — still covers `MIN_CORE_AREA` source px², and whose whole area is `MIN_SHARE` of the reference's
visible pixels or more. Erosion is what removes the
anti-aliased band between two colours, which grows into a thin ring of its own; the area is stated in
source px so a noise speck is ignored at every `--scale`. Transparent regions touching the image border
are the ground, not a feature; an enclosed one is a hole.

A core pixel is **kept** when some render pixel within the erosion radius is the feature's colour: for
a hole, transparent; otherwise visible, and no farther from the feature's mean colour than from any
other counted feature's, plus `MATCH_SLACK` — or within `MATCH_TOLERANCE` of it outright, so a flat
fill that shifts a shaded region's colour is `mae`'s to judge. A render that paints the dot red is
nearer the disc and far from white.
`recall` of a feature is its kept share of the core; the score is the lowest recall, 1.0 when nothing
counts, and a feature below `LOST_RECALL` is named in `lost`.
"""
from __future__ import annotations

import hashlib
from collections import deque

ALPHA_VISIBLE = 128
SEGMENT_TOLERANCE = 40      # Chebyshev RGB distance from a region's running mean
ERODE_SOURCE_PX = 0.5
MIN_CORE_AREA = 1.0         # source px², measured after erosion
MIN_SHARE = 0.005           # of the reference's visible px: a feature smaller than this is texture
MATCH_TOLERANCE = 48        # a render pixel this near the feature's mean is its colour, whatever else is near
MATCH_SLACK = 24
LOST_RECALL = 0.5


def _check_sizes(a: bytes, b: bytes, width: int, height: int) -> None:
    expected = width * height * 4
    if len(a) != expected or len(b) != expected:
        raise ValueError(f"buffers must both be {width}x{height} RGBA ({expected} bytes); got {len(a)} and {len(b)}")


def _segment(buf: bytes, width: int, height: int) -> list[dict]:
    """Regions of one colour or of transparency, in scan order: {"pixels", "colour" (None = clear), "border"}."""
    n = width * height
    label = [-1] * n
    regions = []
    for start in range(n):
        if label[start] != -1:
            continue
        index = len(regions)
        clear = buf[start * 4 + 3] < ALPHA_VISIBLE
        total = [0, 0, 0]
        pixels = []
        border = False
        label[start] = index
        queue = deque([start])
        while queue:
            p = queue.popleft()
            pixels.append(p)
            x, y = p % width, p // width
            border = border or x == 0 or y == 0 or x == width - 1 or y == height - 1
            o = p * 4
            if not clear:
                total[0] += buf[o]
                total[1] += buf[o + 1]
                total[2] += buf[o + 2]
            count = len(pixels)
            for q in (p - 1 if x > 0 else -1, p + 1 if x < width - 1 else -1,
                      p - width if y > 0 else -1, p + width if y < height - 1 else -1):
                if q < 0 or label[q] != -1:
                    continue
                qo = q * 4
                if clear:
                    if buf[qo + 3] >= ALPHA_VISIBLE:
                        continue
                elif (buf[qo + 3] < ALPHA_VISIBLE
                      or abs(buf[qo] - total[0] / count) > SEGMENT_TOLERANCE
                      or abs(buf[qo + 1] - total[1] / count) > SEGMENT_TOLERANCE
                      or abs(buf[qo + 2] - total[2] / count) > SEGMENT_TOLERANCE):
                    continue
                label[q] = index
                queue.append(q)
        count = len(pixels)
        colour = None if clear else tuple(round(t / count) for t in total)
        regions.append({"pixels": pixels, "colour": colour, "border": border})
    return regions


def _window_counts(mask: list[int], w: int, h: int, r: int) -> list[int]:
    """For each cell of a w×h 0/1 mask, how many set cells lie within Chebyshev radius r (clipped)."""
    sat = [0] * ((w + 1) * (h + 1))
    for y in range(h):
        run = 0
        row, above = (y + 1) * (w + 1), y * (w + 1)
        for x in range(w):
            run += mask[y * w + x]
            sat[row + x + 1] = sat[above + x + 1] + run
    out = [0] * (w * h)
    for y in range(h):
        y0, y1 = max(y - r, 0), min(y + r + 1, h)
        for x in range(w):
            x0, x1 = max(x - r, 0), min(x + r + 1, w)
            out[y * w + x] = (sat[y1 * (w + 1) + x1] - sat[y0 * (w + 1) + x1]
                              - sat[y1 * (w + 1) + x0] + sat[y0 * (w + 1) + x0])
    return out


def _core(pixels: list[int], width: int, height: int, r: int) -> list[int]:
    """The region's pixels whose whole (2r+1)² window lies inside the region (and inside the image)."""
    if r == 0:
        return pixels
    xs, ys = [p % width for p in pixels], [p // width for p in pixels]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    mask = [0] * (w * h)
    for x, y in zip(xs, ys):
        mask[(y - y0) * w + (x - x0)] = 1
    counts = _window_counts(mask, w, h, r)
    full = (2 * r + 1) ** 2
    return [p for p, x, y in zip(pixels, xs, ys)
            if r <= x < width - r and r <= y < height - r and counts[(y - y0) * w + (x - x0)] == full]


def _distance(buf: bytes, o: int, colour: tuple[int, int, int]) -> int:
    return max(abs(buf[o] - colour[0]), abs(buf[o + 1] - colour[1]), abs(buf[o + 2] - colour[2]))


def _kept(core: list[int], colour, palette: list, rendered: bytes, width: int, height: int, r: int) -> int:
    xs, ys = [p % width for p in core], [p // width for p in core]
    x0, y0 = max(min(xs) - r, 0), max(min(ys) - r, 0)
    x1, y1 = min(max(xs) + r + 1, width), min(max(ys) + r + 1, height)
    w, h = x1 - x0, y1 - y0
    match = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            o = (y * width + x) * 4
            visible = rendered[o + 3] >= ALPHA_VISIBLE
            if colour is None:
                hit = not visible
            elif not visible:
                hit = False
            else:
                own = _distance(rendered, o, colour)
                hit = own <= MATCH_TOLERANCE or (len(palette) > 1 and
                                                 own <= min(_distance(rendered, o, c) for c in palette) + MATCH_SLACK)
            match[(y - y0) * w + (x - x0)] = hit
    counts = _window_counts(match, w, h, r)
    return sum(1 for x, y in zip(xs, ys) if counts[(y - y0) * w + (x - x0)])


_COUNTED: dict = {}  # (reference digest, width, height, scale) -> counted features; --auto scores one reference many times


def _counted(reference: bytes, width: int, height: int, scale: float) -> list:
    key = (hashlib.blake2b(reference, digest_size=16).digest(), width, height, scale)
    if key not in _COUNTED:
        r = max(1, round(ERODE_SOURCE_PX * scale))
        min_core = MIN_CORE_AREA * scale * scale
        min_area = max(min_core, MIN_SHARE * sum(1 for i in range(3, len(reference), 4) if reference[i] >= ALPHA_VISIBLE))
        counted = []
        for region in _segment(reference, width, height):
            if region["colour"] is None and region["border"]:
                continue
            if len(region["pixels"]) < min_area:
                continue
            core = _core(region["pixels"], width, height, r)
            if len(core) >= min_core:
                counted.append((region["colour"], len(region["pixels"]), core))
        _COUNTED.clear()
        _COUNTED[key] = counted
    return _COUNTED[key]


def recall(reference: bytes, rendered: bytes, width: int, height: int, scale: float = 1.0) -> dict:
    """{"features": lowest recall (1.0 if none counted), "counted": n, "lost": [{"colour", "area", "recall", "at"}]}.

    `scale` is how many render px one source px became; areas and the erosion radius are in source px.
    """
    _check_sizes(reference, rendered, width, height)
    r = max(1, round(ERODE_SOURCE_PX * scale))
    counted = _counted(reference, width, height, scale)
    palette = [colour for colour, _, _ in counted if colour is not None]
    lowest, lost = 1.0, []
    for colour, area, core in counted:
        share = _kept(core, colour, palette, rendered, width, height, r) / len(core)
        lowest = min(lowest, share)
        if share < LOST_RECALL:
            first = core[0]
            lost.append({"colour": None if colour is None else "#%02x%02x%02x" % colour,
                         "area": round(area / (scale * scale), 1), "recall": round(share, 4),
                         "at": [round(first % width / scale, 1), round(first // width / scale, 1)]})
    return {"features": lowest, "counted": len(counted), "lost": lost}
