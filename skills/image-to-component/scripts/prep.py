"""Prepare a raster for tracing: crop, key out the background, trim, upscale.

Needs Pillow (run through toolchain.sh `i2c_py prep`).

    prep.py in.png reference.png [--trace-input trace.png] [--crop x,y,w,h]
            [--bg auto|none|#rrggbb] [--tolerance 40] [--key flood|global] [--scale 2] [--pad 2]
            [--mono] [--smooth 1.5] [--colors 8] [--report]

Two outputs, on purpose. `reference.png` is the keyed, trimmed, scaled asset — what QA compares
against. `--trace-input` is what vtracer sees: palette-reduced or thresholded. QA never scores
against the trace input, because that would hide exactly the loss quantization introduces.

--bg auto  samples the border, takes its median colour, and flood-fills from every border pixel
           within tolerance — so a background colour that also appears *inside* the subject (a
           dark glyph on a dark card) survives, because it is not connected to the edge.
--key global  keys every pixel near the background, connected or not — for single-colour glyphs,
           whose enclosed holes (a gear's centre, a wrench's eye) must be transparent too.
--mono     trace input is a black-on-white opaque silhouette (alpha >= 128): vtracer's binary
           mode ignores alpha, so an RGBA input traces as one full square.
--smooth   Gaussian radius applied to alpha before the silhouette is thresholded: an upscaled
           small glyph otherwise traces its pixel staircase as wobble.
--colors   trace input is quantized to an N-colour palette. Rendered artwork carries gradients
           and noise that trace as hundreds of slivers; a palette is what a logo is.
Exit codes: 0 written, 1 nothing left after keying (tolerance too high), 2 usage/unreadable.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import deque

from PIL import Image, ImageFilter


def _parse_box(text: str) -> tuple[int, int, int, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    return x, y, x + w, y + h


def _border(width: int, height: int):
    for x in range(width):
        yield x, 0
        yield x, height - 1
    for y in range(1, height - 1):
        yield 0, y
        yield width - 1, y


def _median_border_colour(img: Image.Image) -> tuple[int, int, int]:
    px = img.load()
    samples = [px[x, y][:3] for x, y in _border(*img.size)]
    return tuple(int(statistics.median(c[i] for c in samples)) for i in range(3))


def key_background(img: Image.Image, bg: tuple[int, int, int], tolerance: int) -> Image.Image:
    """Return a copy whose edge-connected pixels near `bg` are transparent."""
    out = img.convert("RGBA").copy()
    px = out.load()
    width, height = out.size

    def near(p):
        return max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) <= tolerance

    seen = bytearray(width * height)
    queue = deque(pt for pt in _border(width, height) if near(px[pt]))
    for x, y in queue:
        seen[y * width + x] = 1
    while queue:
        x, y = queue.popleft()
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and not seen[ny * width + nx]:
                seen[ny * width + nx] = 1
                if near(px[nx, ny]):
                    queue.append((nx, ny))
    return out


def key_global(img: Image.Image, bg: tuple[int, int, int], tolerance: int) -> Image.Image:
    """Return a copy whose every pixel near `bg` is transparent."""
    out = img.convert("RGBA").copy()
    out.putdata([(r, g, b, 0) if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) <= tolerance
                 else (r, g, b, a) for r, g, b, a in out.get_flattened_data()])
    return out


def silhouette(img: Image.Image, smooth: float = 0.0) -> Image.Image:
    """Black where visible, white elsewhere, fully opaque."""
    alpha = img.getchannel("A")
    if smooth > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(smooth))
    return alpha.point(lambda v: 0 if v >= 128 else 255).convert("RGB")


def quantize(img: Image.Image, colors: int) -> Image.Image:
    """Palette-reduce RGB, keep alpha, and snap alpha to 0/255 so no colour is traced twice."""
    alpha = img.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    rgb = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT,
                                      dither=Image.Dither.NONE).convert("RGB")
    rgb.putalpha(alpha)
    return rgb


def _background(spec: str, img: Image.Image) -> tuple[int, int, int] | None:
    if spec == "auto":
        return _median_border_colour(img)
    if spec == "none":
        return None
    if spec.startswith("#") and len(spec) == 7:
        return tuple(int(spec[i:i + 2], 16) for i in (1, 3, 5))
    raise ValueError("--bg must be auto, none or #rrggbb")


def trace_input(reference: Image.Image, mono: bool, smooth: float, colors: int) -> Image.Image:
    if mono:
        return silhouette(reference, smooth)
    if colors:
        return quantize(reference, colors)
    return reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prep", description=__doc__.splitlines()[0])
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--trace-input")
    parser.add_argument("--crop")
    parser.add_argument("--bg", default="auto")
    parser.add_argument("--tolerance", type=int, default=40)
    parser.add_argument("--key", choices=("flood", "global"), default="flood")
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--smooth", type=float, default=0.0)
    parser.add_argument("--colors", type=int, default=0)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--pad", type=int, default=2)
    parser.add_argument("--report", action="store_true", help="print a JSON summary on stdout")
    args = parser.parse_args(argv)

    try:
        img = Image.open(args.src).convert("RGBA")
        if args.crop:
            img = img.crop(_parse_box(args.crop))
        bg = _background(args.bg, img)
    except (OSError, ValueError) as exc:
        print(f"prep: {exc}", file=sys.stderr)
        return 2
    if bg is not None:
        keyer = key_background if args.key == "flood" else key_global
        img = keyer(img, bg, args.tolerance)

    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        print(f"prep: nothing left after keying background {bg}; lower --tolerance", file=sys.stderr)
        return 1
    left, top, right, bottom = bbox
    img = img.crop((max(left - args.pad, 0), max(top - args.pad, 0),
                    min(right + args.pad, img.width), min(bottom + args.pad, img.height)))
    if args.scale != 1.0:
        img = img.resize((round(img.width * args.scale), round(img.height * args.scale)), Image.LANCZOS)
    img.save(args.dst)
    if args.trace_input:
        trace_input(img, args.mono, args.smooth, args.colors).save(args.trace_input)
    if args.report:
        print(json.dumps({"size": img.size, "background": bg, "tolerance": args.tolerance}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
