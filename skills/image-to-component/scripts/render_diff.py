"""Render an SVG with resvg and score it against the prepared source raster.

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py render_diff`). The metric itself
is stdlib (`diffmetric.py`); this file only decodes and draws.

    render_diff.py source.png asset.svg --report qa.json [--sheet compare.png]
                   [--iou 0.95] [--mae 12] [--edge-f1 0.80] [--mono]

--mono  compares silhouettes only: both images are painted black before scoring, because a
        currentColor component has no colour of its own to compare.

Also renders at 24px and at 4x as a scale smoke test: both must produce visible pixels.
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


def paint_black(img: Image.Image) -> Image.Image:
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(img.getchannel("A"))
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
    args = parser.parse_args(argv)

    try:
        source = Image.open(args.source).convert("RGBA")
        with open(args.svg, encoding="utf-8") as fh:
            svg_text = fh.read()
        rendered = render(svg_text, *source.size)
        small = render(svg_text, 24, max(1, round(24 * source.height / source.width)))
        large = render(svg_text, source.width * 4, source.height * 4)
    except (OSError, ValueError) as exc:
        print(f"render_diff: {exc}", file=sys.stderr)
        return 2

    if args.mono:
        source, rendered = paint_black(source), paint_black(rendered)
    result = diffmetric.compare(source.tobytes(), rendered.tobytes(), *source.size,
                                thresholds={"iou": args.iou, "mae": args.mae, "edge_f1": args.edge_f1})
    scale_ok = {"24px": small.getchannel("A").getbbox() is not None,
                "4x": large.getchannel("A").getbbox() is not None}
    if not all(scale_ok.values()):
        result["failures"] = sorted(result["failures"] + ["scale"])
        result["pass"] = False
    result.update(source=os.path.basename(args.source), svg=os.path.basename(args.svg), size=list(source.size),
                  svg_bytes=len(svg_text.encode()), scale_smoke=scale_ok, mono=args.mono)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    if args.sheet:
        sheet(source, rendered).save(args.sheet)
    print(json.dumps({k: result[k] for k in ("iou", "mae", "edge_f1", "pass", "failures")}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
