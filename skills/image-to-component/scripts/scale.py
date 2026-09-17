"""The declared scale system a replacement lands on, and the transform that fits a library icon to a source.

Stdlib only. `scales.json` beside this file is the one declaration (DEC-0181): icon steps, container
radius, spacing base and border widths. A measured value snaps to the nearest step within
`snap_tolerance` (relative); otherwise it is kept as measured and the record says no step matched —
an off-scale source is reported, not bent onto a scale it does not use.

A fit is (k, ox, oy): source px = o + icon unit × k. It is taken from moments — centroid onto centroid,
radius of gyration onto radius of gyration — because blur moves an alpha-128 box edge and leaves both
moments nearly where they were.
"""
from __future__ import annotations

import json

REQUIRED = ("icon_px", "snap_tolerance", "radius_px", "spacing_base_px", "border_px")
VISIBLE = 128


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        scales = json.load(fh)
    missing = [key for key in REQUIRED if key not in scales]
    if missing:
        raise ValueError(f"{path} declares no {', '.join(missing)}")
    return scales


def snap(value: float, steps: list, tolerance: float) -> dict:
    """{"measured", "step", "value"}: the nearest numeric step within a relative tolerance, else the value kept."""
    numeric = [s for s in steps if isinstance(s, (int, float)) and not isinstance(s, bool)]
    best = min(numeric, key=lambda s: abs(value - s), default=None)
    if best is not None and abs(value - best) <= tolerance * max(best, 1):
        return {"measured": value, "step": best, "value": best}
    return {"measured": value, "step": None, "value": value}


def stroke_ratio(alpha: bytes, width: int, height: int) -> float:
    """Mean stroke width over the ink box's longer side: 2 × ink area / boundary length.

    For a stroke of width w and length L, area is wL and boundary about 2L, so 2A/P is w. Boundary
    length is counted as 4-neighbour inside/outside transitions, the image edge included.
    """
    ink = [v >= VISIBLE for v in alpha]
    area = sum(ink)
    if area == 0:
        raise ValueError("no ink: nothing reaches alpha 128")
    perimeter = 0
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if not ink[y * width + x]:
                continue
            xs.append(x)
            ys.append(y)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                perimeter += not (0 <= nx < width and 0 <= ny < height and ink[ny * width + nx])
    box = max(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    return 2 * area / perimeter / box


def nearest_weight(ratio: float, ratios: dict[int, float]) -> int:
    """The weight whose own measured stroke ratio is closest to the source's."""
    return min(ratios, key=lambda weight: (abs(ratios[weight] - ratio), weight))


def fit(icon: dict, source: tuple[float, float, float]) -> tuple[float, float, float]:
    """(k, ox, oy) placing an index entry's centroid and radius onto a source's (cx, cy, r) in px."""
    cx, cy, r = source
    k = r / icon["r"]
    return k, cx - icon["cx"] * k, cy - icon["cy"] * k


def canvas_view_box(transform: tuple[float, float, float], width: int, height: int,
                    pad: float = 0.0) -> tuple[float, float, float, float]:
    """The icon-unit viewBox that renders onto a (width + 2·pad) × (height + 2·pad) px canvas under `transform`."""
    k, ox, oy = transform
    return (-pad - ox) / k, (-pad - oy) / k, (width + 2 * pad) / k, (height + 2 * pad) / k


def rendered_px(transform: tuple[float, float, float], view_box: tuple[float, float, float, float]) -> float:
    """How many px the icon's own viewBox spans on the source: the component's natural size."""
    return view_box[2] * transform[0]
