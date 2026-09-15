"""Render an SVG with resvg and score it against the prepared source raster.

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py render_diff`). The metric itself
is stdlib (`diffmetric.py`); this file only decodes and draws.

    render_diff.py source.png asset.svg --report qa.json [--sheet compare.png]
                   [--iou 0.95] [--mae 12] [--edge-f1 0.80] [--jaggedness N] [--staircase N] [--features N] [--mono]
                   [--scale N --source-edge hard|soft]

--mono  compares silhouettes only: both images are painted black before scoring, because a
        currentColor component has no colour of its own to compare. The reference's silhouette is
        its alpha >= 128 — the same cut IoU uses. A soft-matted reference otherwise has an edge
        ramp several pixels wide that no Sobel threshold reads as an edge, and edge_f1 scores 0.

--scale, --source-edge  how many render px one source px became, and prep's edge character of the
        source before upscaling. Together they turn on the `staircase` bound (a hard source at
        scale >= 2); without them it is not scored, which is the standalone default.

Exit codes: 0 pass, 1 below threshold, 2 unreadable input or render failure.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import resvg_py
from PIL import Image, ImageChops

from scripts import diffmetric
from scripts.jaggedness import jaggedness


def render(svg_text: str, width: int, height: int) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=svg_text, width=width, height=height)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def sheet(source: Image.Image, rendered: Image.Image) -> Image.Image:
    """source | render | amplified difference, each over a checkerboard."""
    width, height = source.size
    board = Image.new("RGBA", (width, height), (40, 40, 48, 255))
    for y in range(0, height, 8):
        for x in range((y // 8) % 2 * 8, width, 16):
            board.paste((64, 64, 72, 255), (x, y, x + 8, y + 8))
    bands = [ImageChops.difference(a, b) for a, b in zip(source.split(), rendered.split())]
    diff = bands[0]
    for band in bands[1:]:
        diff = ImageChops.lighter(diff, band)
    diff = diff.point(lambda v: min(255, v * 4))
    out = Image.new("RGBA", (width * 3, height))
    out.paste(Image.alpha_composite(board, source), (0, 0))
    out.paste(Image.alpha_composite(board, rendered), (width, 0))
    out.paste(Image.merge("RGBA", (diff, diff, diff, Image.new("L", diff.size, 255))), (width * 2, 0))
    return out


def paint_black(img: Image.Image, cut: bool = False) -> Image.Image:
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    alpha = img.getchannel("A")
    black.putalpha(alpha.point(lambda v: 255 if v >= 128 else 0) if cut else alpha)
    return black


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render_diff", description=__doc__.splitlines()[0])
    parser.add_argument("source")
    parser.add_argument("svg")
    parser.add_argument("--report", required=True)
    parser.add_argument("--sheet")
    parser.add_argument("--iou", type=float, default=diffmetric.DEFAULT_THRESHOLDS["iou"])
    parser.add_argument("--mae", type=float, default=diffmetric.DEFAULT_THRESHOLDS["mae"])
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--edge-f1", type=float, default=diffmetric.DEFAULT_THRESHOLDS["edge_f1"])
    parser.add_argument("--jaggedness", type=float, default=diffmetric.DEFAULT_THRESHOLDS["jaggedness"])
    parser.add_argument("--staircase", type=float, default=diffmetric.DEFAULT_THRESHOLDS["staircase"])
    parser.add_argument("--features", type=float, default=diffmetric.DEFAULT_THRESHOLDS["features"])
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--source-edge", choices=("hard", "soft"))
    args = parser.parse_args(argv)

    try:
        source = Image.open(args.source).convert("RGBA")
        with open(args.svg, encoding="utf-8") as fh:
            svg_text = fh.read()
        rendered = render(svg_text, *source.size)
    except Exception as exc:  # any renderer failure is a tool failure (2), never a QA refusal (1)
        print(f"render_diff: {exc}", file=sys.stderr)
        return 2

    if args.mono:
        source, rendered = paint_black(source, cut=True), paint_black(rendered)
    result = diffmetric.compare(source.tobytes(), rendered.tobytes(), *source.size,
                                thresholds={"iou": args.iou, "mae": args.mae, "edge_f1": args.edge_f1,
                                            "jaggedness": args.jaggedness, "staircase": args.staircase,
                                            "features": args.features},
                                scale=args.scale, source_edge=args.source_edge)
    result.update(source=os.path.basename(args.source), svg=os.path.basename(args.svg), size=list(source.size),
                  svg_bytes=len(svg_text.encode()), mono=args.mono,
                  scale=args.scale, source_edge=args.source_edge,
                  reference_jaggedness=round(jaggedness(source.tobytes(), *source.size), 4))

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    if args.sheet:
        sheet(source, rendered).save(args.sheet)
    print(json.dumps({k: result[k] for k in ("iou", "mae", "edge_f1", "jaggedness", "staircase", "features", "pass", "failures")}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
