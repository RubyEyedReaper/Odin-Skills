"""Synthetic inputs for the image-to-component engine tests.

Named with a leading underscore so `unittest discover` does not collect it. Nothing here
shells out to vtracer, svgo, resvg or node: the gated suite runs on system python3 with no
network, so it tests the three stdlib modules and nothing that needs a toolchain.
"""
from __future__ import annotations

import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

# The widest input svg2tsx accepts: a sized root, a group, paths with fill rule, transform and
# opacity, a title and a prolog to drop. The pipeline's real output is narrower still (GLYPH_SVG).
TRACED_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Generator: visioncortex VTracer -->
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="64" height="48">
  <title>ignored</title>
  <path d="M0 0h10v10H0z" fill="#E11D2E" fill-rule="evenodd" transform="translate(4 4)"/>
  <g opacity="0.5"><path d="M20 20h8v8h-8z" fill="rgb(36,200,255)" fill-opacity="0.8"/></g>
</svg>
"""

# Verbatim shape of a --color currentColor golden (evals/rubytech/out/*Icon.svg, path shortened):
# vtracer binary mode + SVGO leave no paint at all — no fill attribute anywhere.
GLYPH_SVG = '<svg viewBox="0 0 152 152"><path d="M100 7.81q1.96 0 3.97-.04h3.78z"/></svg>'


def rgba(width: int, height: int, fn) -> bytes:
    """Build an RGBA buffer from fn(x, y) -> (r, g, b, a)."""
    out = bytearray()
    for y in range(height):
        for x in range(width):
            out.extend(fn(x, y))
    return bytes(out)


def square(width: int, height: int, x0: int, y0: int, size: int, colour=(225, 29, 46, 255)) -> bytes:
    """A transparent canvas with one opaque square."""
    def px(x, y):
        inside = x0 <= x < x0 + size and y0 <= y < y0 + size
        return colour if inside else (0, 0, 0, 0)
    return rgba(width, height, px)


def upscaled_disc(radius: int, scale: int, samples: int, margin: int = 2):
    """A disc of `radius` source px drawn at `scale`: samples=1 gives the nearest-neighbour upscale
    of an aliased source (every step `scale` px), 4 gives the anti-aliased disc it should become."""
    size = (2 * radius + 2 * margin) * scale
    centre = size / 2
    limit = (radius * scale) ** 2

    def px(x, y):
        if samples == 1:  # decide per source pixel, then repeat it scale×scale
            sx, sy = (x // scale + 0.5) * scale, (y // scale + 0.5) * scale
            return (0, 0, 0, 255 if (sx - centre) ** 2 + (sy - centre) ** 2 <= limit else 0)
        hits = sum((x + (i + 0.5) / samples - centre) ** 2 + (y + (j + 0.5) / samples - centre) ** 2 <= limit
                   for i in range(samples) for j in range(samples))
        return (0, 0, 0, round(255 * hits / samples ** 2))
    return rgba(size, size, px), size


def box_blur_alpha(buf: bytes, width: int, height: int, radius: int, passes: int) -> bytes:
    alpha = list(buf[3::4])
    for _ in range(passes):
        for horizontal in (True, False):
            out = []
            for y in range(height):
                for x in range(width):
                    span = [(x + d, y) if horizontal else (x, y + d) for d in range(-radius, radius + 1)]
                    vals = [alpha[sy * width + sx] for sx, sy in span if 0 <= sx < width and 0 <= sy < height]
                    out.append(sum(vals) / len(vals))
            alpha = out
    return rgba(width, height, lambda x, y: (0, 0, 0, round(alpha[y * width + x])))
