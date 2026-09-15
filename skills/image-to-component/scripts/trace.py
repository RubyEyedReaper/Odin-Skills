"""Trace a prepared raster into SVG paths with vtracer.

Needs vtracer (run through toolchain.sh `i2c_py trace`). Presets are documented, with the
reason for each number, in references/tracing-presets.md.

    trace.py in.png out.svg --kind icon|logo|illustration [--binary] [--set key=value ...]

Exit codes: 0 written, 2 usage/unreadable.
"""
from __future__ import annotations

import argparse
import sys

BASE = dict(colormode="color", hierarchical="stacked", mode="spline", corner_threshold=60,
            length_threshold=4.0, splice_threshold=45, path_precision=2)
PRESETS = {
    "icon": dict(BASE, filter_speckle=6, color_precision=5, layer_difference=32),
    "logo": dict(BASE, filter_speckle=4, color_precision=6, layer_difference=20),
    "illustration": dict(BASE, filter_speckle=8, color_precision=6, layer_difference=24),
}
INT_KEYS = {"filter_speckle", "color_precision", "layer_difference", "corner_threshold",
            "splice_threshold", "path_precision", "max_iterations"}


def options(kind: str, binary: bool, overrides: list[str]) -> dict:
    opts = dict(PRESETS[kind])
    if binary:
        opts["colormode"] = "binary"
    for item in overrides:
        key, value = item.split("=", 1)
        opts[key] = int(value) if key in INT_KEYS else float(value) if key == "length_threshold" else value
    return opts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trace", description=__doc__.splitlines()[0])
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--kind", required=True, choices=sorted(PRESETS))
    parser.add_argument("--binary", action="store_true", help="single-colour trace, for currentColor icons")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args(argv)
    import vtracer  # toolchain-only; keeps options() testable on system python3

    try:
        vtracer.convert_image_to_svg_py(args.src, args.dst, **options(args.kind, args.binary, args.set))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"trace: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
