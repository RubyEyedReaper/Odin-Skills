"""How closely does a trace of a degraded source match the trace of its clean original?

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py`). Eval-only — not part of the pipeline.

    agreement.py degraded.svg clean.svg

The degraded run's own QA scores it against its own prepared reference, which is itself degraded:
a faithful trace of a blob scores well against a blob. This compares silhouettes against the clean
golden instead, without pixel registration — prep trims and pads each run differently — by
rendering both at 512 px wide, cropping each to its alpha bounding box, resizing the degraded crop
onto the clean one's size, and taking IoU at alpha ≥ 128. Prints one JSON object.
Exit codes: 0 scored, 2 unreadable or empty render.
"""
from __future__ import annotations

import io
import json
import sys

import resvg_py
from PIL import Image

WIDTH = 512


def silhouette(path: str) -> Image.Image:
    with open(path, encoding="utf-8") as fh:
        png = resvg_py.svg_to_bytes(svg_string=fh.read(), width=WIDTH)
    alpha = Image.open(io.BytesIO(bytes(png))).convert("RGBA").getchannel("A")
    box = alpha.getbbox()
    if box is None:
        raise ValueError(f"{path} renders nothing")
    return alpha.crop(box).point(lambda v: 255 if v >= 128 else 0)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.splitlines()[3].strip(), file=sys.stderr)
        return 2
    try:
        degraded, clean = silhouette(argv[0]), silhouette(argv[1])
    except (OSError, ValueError) as exc:
        print(f"agreement: {exc}", file=sys.stderr)
        return 2
    degraded = degraded.resize(clean.size, Image.BILINEAR).point(lambda v: 255 if v >= 128 else 0)
    a, b = degraded.tobytes(), clean.tobytes()
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    print(json.dumps({"agreement_iou": round(inter / union, 4) if union else 1.0}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
