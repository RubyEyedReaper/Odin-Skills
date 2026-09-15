"""Compare a rendered SVG against its source raster.

Stdlib only; operates on same-sized straight-alpha RGBA byte buffers. The renderer
(`render_diff.py`) supplies the buffers — this module never decodes an image, which is what
lets the gated suite test the metric with no toolchain installed.

Three numbers, each catching a different failure:
  iou      alpha silhouette overlap        — missing or extra shapes, lost transparency
  mae      mean abs RGB error, visible px  — wrong colours, merged colour regions
  edge_f1  Sobel edge agreement ±tolerance — jagged curves, lost detail, drifted outlines

and two about the outline, which the three above cannot see (`jaggedness.py`):
  jaggedness  outline zig-zag finer than the shape — tracer wobble, render-pixel staircases
  staircase   share of a hard source's one-pixel steps the render keeps — only for a hard-edged
              source traced at scale >= 2, where each step is a render corner jaggedness passes
"""
from __future__ import annotations

from .jaggedness import jaggedness, staircase

ALPHA_VISIBLE = 128
EDGE_THRESHOLD = 96.0
DEFAULT_THRESHOLDS = {"iou": 0.95, "mae": 12.0, "edge_f1": 0.80, "jaggedness": 15.0, "staircase": 0.35}


def _check_sizes(a: bytes, b: bytes, width: int, height: int) -> None:
    expected = width * height * 4
    if len(a) != expected or len(b) != expected:
        raise ValueError(f"buffers must both be {width}x{height} RGBA ({expected} bytes); got {len(a)} and {len(b)}")


def alpha_iou(a: bytes, b: bytes) -> float:
    inter = union = 0
    for i in range(3, len(a), 4):
        va, vb = a[i] >= ALPHA_VISIBLE, b[i] >= ALPHA_VISIBLE
        inter += va and vb
        union += va or vb
    return 1.0 if union == 0 else inter / union


def mae_rgb(a: bytes, b: bytes) -> float:
    total = count = 0
    for i in range(0, len(a), 4):
        if a[i + 3] < ALPHA_VISIBLE and b[i + 3] < ALPHA_VISIBLE:
            continue
        total += abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2])
        count += 3
    return 0.0 if count == 0 else total / count


def _luma_over_grey(buf: bytes, width: int, height: int) -> list[float]:
    # Composite over mid-grey so an alpha boundary is an edge even where the colour is not.
    out = []
    for i in range(0, width * height * 4, 4):
        alpha = buf[i + 3] / 255
        luma = 0.299 * buf[i] + 0.587 * buf[i + 1] + 0.114 * buf[i + 2]
        out.append(luma * alpha + 127.5 * (1 - alpha))
    return out


def _edges(buf: bytes, width: int, height: int) -> set[tuple[int, int]]:
    lum = _luma_over_grey(buf, width, height)

    def at(x, y):
        return lum[min(max(y, 0), height - 1) * width + min(max(x, 0), width - 1)]

    edges = set()
    for y in range(height):
        for x in range(width):
            gx = (at(x + 1, y - 1) + 2 * at(x + 1, y) + at(x + 1, y + 1)
                  - at(x - 1, y - 1) - 2 * at(x - 1, y) - at(x - 1, y + 1))
            gy = (at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1)
                  - at(x - 1, y - 1) - 2 * at(x, y - 1) - at(x + 1, y - 1))
            if (gx * gx + gy * gy) ** 0.5 >= EDGE_THRESHOLD:
                edges.add((x, y))
    return edges


def _near(point: tuple[int, int], pool: set[tuple[int, int]], tolerance: int) -> bool:
    x, y = point
    return any((x + dx, y + dy) in pool
               for dx in range(-tolerance, tolerance + 1)
               for dy in range(-tolerance, tolerance + 1))


def edge_f1(a: bytes, b: bytes, width: int, height: int, tolerance: int = 1) -> float:
    ea, eb = _edges(a, width, height), _edges(b, width, height)
    if not ea and not eb:
        return 1.0
    if not ea or not eb:
        return 0.0
    precision = sum(_near(p, ea, tolerance) for p in eb) / len(eb)
    recall = sum(_near(p, eb, tolerance) for p in ea) / len(ea)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def compare(source: bytes, rendered: bytes, width: int, height: int,
            thresholds: dict[str, float] | None = None, tolerance: int = 1,
            scale: float = 1.0, source_edge: str | None = None) -> dict:
    """Score `rendered` against `source`. `scale` is how many render px one source px became, and
    `source_edge` is `edges.classify` of the source before upscaling; `staircase` is scored only
    when the edge is hard and a source pixel spans 2+ render px, and is None otherwise."""
    _check_sizes(source, rendered, width, height)
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    scores = {
        "iou": alpha_iou(source, rendered),
        "mae": mae_rgb(source, rendered),
        "edge_f1": edge_f1(source, rendered, width, height, tolerance),
        "jaggedness": jaggedness(rendered, width, height),
    }
    if source_edge == "hard" and round(scale) >= 2:
        scores["staircase"] = staircase(rendered, source, width, height, scale)
    failures = [k for k in ("iou", "edge_f1") if scores[k] < limits[k]]
    failures += [k for k in ("mae", "jaggedness", "staircase") if k in scores and k in limits and scores[k] > limits[k]]
    return {**{k: round(v, 4) for k, v in scores.items()}, "staircase": round(scores["staircase"], 4)
            if "staircase" in scores else None, "thresholds": limits,
            "failures": sorted(failures), "pass": not failures}
