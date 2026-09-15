"""Smooth the borders between colour regions of a quantized trace input, before vtracer sees it.

Stdlib only; the blur is passed in (`prep.py` hands it a Pillow Gaussian), so the gated suite tests the
vote with a stdlib box blur and no toolchain.

A noisy or JPEG-soft colour source quantizes into regions whose borders follow the noise pixel by
pixel, and vtracer traces every one of those steps as a wobble. Blurring the RGB first mints
in-between shades that trace as slivers, and a mode filter erases small facets
(`references/tracing-presets.md`). The vote does neither: each palette label's indicator mask is
blurred, and every opaque pixel takes the label with the most support there. A border moves only where
its neighbourhood disagrees with it, no colour is created, the silhouette is kept pixel for pixel, and a
region wider than the radius keeps its core.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable

TRANSPARENT = -1
Blur = Callable[[bytes, int, int, float], bytes]


def vote(labels: list[int], width: int, height: int, radius: float, blur: Blur) -> list[int]:
    """Each opaque pixel's label becomes the one whose blurred mask is highest there.

    `labels` holds a palette index per pixel, or TRANSPARENT. Ties keep the more frequent label, then
    the lower index, so the result does not depend on dictionary order. Radius 0 returns a copy.
    """
    if radius <= 0:
        return list(labels)
    counts = Counter(v for v in labels if v != TRANSPARENT)
    order = sorted(counts, key=lambda label: (-counts[label], label))
    best = bytearray(width * height)
    out = list(labels)
    for label in order:
        support = blur(bytes(255 if v == label else 0 for v in labels), width, height, radius)
        for i, value in enumerate(support):
            if value > best[i] and labels[i] != TRANSPARENT:
                best[i] = value
                out[i] = label
    return out
