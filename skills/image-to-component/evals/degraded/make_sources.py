"""Build the degraded eval's sources from the RubyTech crops. Committed with its output.

Needs Pillow (run through toolchain.sh `i2c_py`, or `uv run --with pillow==12.3.0`).

    python3 evals/degraded/make_sources.py

Each crop is downscaled ×0.5 (bilinear), blurred (Gaussian σ 0.6), given seeded Gaussian RGB noise
(σ 6) and JPEG-encoded at quality 30 — a small, soft, blocky, noisy copy of a real brand asset. The
wrench is also written as a transparent PNG (ground below Chebyshev distance 40 cleared), the input
shape the RubyTech set never exercised. Sources are committed rather than generated per run: JPEG
output follows the encoder, so a pin bump would otherwise move the input under the eval.
"""
from __future__ import annotations

import io
import os
import random

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(HERE, "..", "rubytech", "src")
OUT = os.path.join(HERE, "src")
ASSETS = ("computer-icon", "gear-icon", "controller-icon", "wrench-icon", "rubytech-mark")
SCALE, BLUR, NOISE, QUALITY, SEED = 0.5, 0.6, 6.0, 30, 20260915


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    img = img.convert("RGB")
    img = img.resize((round(img.width * SCALE), round(img.height * SCALE)), Image.BILINEAR)
    img = img.filter(ImageFilter.GaussianBlur(BLUR))
    img.putdata([tuple(max(0, min(255, round(c + rng.gauss(0, NOISE)))) for c in px)
                 for px in img.get_flattened_data()])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=QUALITY)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def transparent(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    ground = img.getpixel((0, 0))
    img.putdata([(r, g, b, 0 if max(abs(r - ground[0]), abs(g - ground[1]), abs(b - ground[2])) <= 40 else 255)
                 for r, g, b, _ in img.get_flattened_data()])
    return img


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name in ASSETS:
        rng = random.Random(f"{SEED}:{name}")
        degrade(Image.open(os.path.join(CLEAN, f"{name}.png")), rng).save(os.path.join(OUT, f"{name}.low.png"))
    transparent(Image.open(os.path.join(CLEAN, "wrench-icon.png"))).save(os.path.join(OUT, "wrench-icon.alpha.png"))


if __name__ == "__main__":
    main()
