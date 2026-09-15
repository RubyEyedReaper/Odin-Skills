"""Prepare a raster for tracing: crop, key out the background, trim, upscale.

Needs Pillow (run through toolchain.sh `i2c_py prep`). Keying itself is stdlib (`keying.py`).

    prep.py in.png reference.png --trace-input trace.png [--crop x,y,w,h]
            [--bg auto|none|#rrggbb] [--tolerance 40] [--key flood|global] [--matte hard|soft] [--scale 2]
            [--mono] [--smooth 1.5] [--colors 8]

Two outputs, on purpose. `reference.png` is the keyed, trimmed, scaled asset — what QA compares
against. `--trace-input` is what vtracer sees: palette-reduced or thresholded. QA never scores
against the trace input, because that would hide exactly the loss quantization introduces.

--bg auto  samples the border, takes its median colour, and flood-fills from every border pixel
           within tolerance — so a background colour that also appears *inside* the subject (a
           dark glyph on a dark card) survives, because it is not connected to the edge. A border
           that is already mostly transparent is not keyed at all.
--key global  keys every pixel near the background, connected or not — for single-colour glyphs,
           whose enclosed holes (a gear's centre, a wrench's eye) must be transparent too.
--matte soft  alpha follows colour distance instead of stepping at --tolerance: a blurred, JPEG-soft
           or low-resolution edge lands halfway between ground and subject rather than wherever
           the colour first leaves the tolerance. Flood keying softens only a 3 px band at the
           boundary; global keying mattes every pixel by coverage (see keying.soft_matte).
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
import sys

from PIL import Image, ImageFilter

from . import keying

PAD = 2


def _parse_box(text: str) -> tuple[int, int, int, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    return x, y, x + w, y + h


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
        return keying.border_background(img.tobytes(), *img.size)
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
    parser.add_argument("--trace-input", required=True)
    parser.add_argument("--crop")
    parser.add_argument("--bg", default="auto")
    parser.add_argument("--tolerance", type=int, default=40)
    parser.add_argument("--key", choices=("flood", "global"), default="flood")
    parser.add_argument("--matte", choices=("soft", "hard"), default="hard")
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--smooth", type=float, default=0.0)
    parser.add_argument("--colors", type=int, default=0)
    parser.add_argument("--scale", type=float, default=1.0)
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
        keyer = keying.key_flood if args.key == "flood" else keying.key_global
        original = img.tobytes()
        keyed = keyer(original, *img.size, bg, args.tolerance)
        if args.matte == "soft":
            keyed = keying.soft_matte(original, keyed, *img.size, bg, args.tolerance, key=args.key)
        img = Image.frombytes("RGBA", img.size, keyed)

    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        print(f"prep: nothing left after keying background {bg}; lower --tolerance", file=sys.stderr)
        return 1
    left, top, right, bottom = bbox
    img = img.crop((max(left - PAD, 0), max(top - PAD, 0),
                    min(right + PAD, img.width), min(bottom + PAD, img.height)))
    if args.scale != 1.0:
        img = img.resize((round(img.width * args.scale), round(img.height * args.scale)), Image.LANCZOS)
    img.save(args.dst)
    trace_input(img, args.mono, args.smooth, args.colors).save(args.trace_input)
    return 0


if __name__ == "__main__":
    sys.exit(main())
