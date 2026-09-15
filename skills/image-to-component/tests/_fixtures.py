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

# The shape vtracer + svgo actually emit: a sized root, grouped coloured paths.
TRACED_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Generator: visioncortex VTracer -->
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="64" height="48">
  <title>ignored</title>
  <path d="M0 0h10v10H0z" fill="#E11D2E" fill-rule="evenodd" transform="translate(4 4)"/>
  <g opacity="0.5"><path d="M20 20h8v8h-8z" fill="rgb(36,200,255)" stroke-width="2" stroke="#000"/></g>
</svg>
"""


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
