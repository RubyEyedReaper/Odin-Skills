"""Build the held-out eval's sources from the two RubyTech mockups. Committed with its output.

Needs Pillow (`uv run --no-project --with pillow==12.3.0`). The mockups are read from the path in
I2C_MOCKUPS (default: the owner's upload directory) and are only ever cropped; the crops in `src/`
are the committed input, so the eval never needs the mockups again.

    python3 evals/heldout/make_sources.py

Every asset is written twice. `<name>.png` is the crop, unscaled. `<name>.low.png` is degraded by a
recipe deliberately unlike `evals/degraded/`'s (×0.5, blur 0.6, noise 6, JPEG 30): ×0.7 bicubic, an
additive colour ramp across the whole image so the ground is a gradient rather than flat, seeded
Gaussian RGB noise σ 4, JPEG quality 20. No blur step — JPEG 20 at this size supplies its own.
"""
from __future__ import annotations

import io
import os
import random

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "src")
UPLOADS = os.environ.get("I2C_MOCKUPS", os.path.expanduser("~/.claude/uploads/180d2921-beac-51d5-b3cd-37ba71f1505d"))
PRINT, WEB = "4189b698-image.png", "17b501a3-image.png"

# name: (sheet, (x, y, w, h), kind). Boxes are in the 1536x1024 sheets; none overlaps an evals/ crop.
CROPS = {
    "monitor-glyph": (PRINT, (568, 267, 39, 34), "glyph"),       # flyer back, Computer Services
    "gamepad-glyph": (PRINT, (839, 271, 37, 30), "glyph"),       # flyer back, Console + Modding
    "x-glyph": (PRINT, (1141, 548, 24, 28), "glyph"),            # business card back, X
    "clock-glyph": (WEB, (1043, 868, 21, 21), "glyph"),          # console services, Clock / Date
    "thermometer-glyph": (WEB, (856, 868, 16, 22), "glyph"),     # console services, Overheating
    "facebook-mark": (PRINT, (1140, 479, 26, 26), "mark"),       # business card back
    "instagram-mark": (PRINT, (1139, 512, 26, 26), "mark"),      # business card back
    "whatsapp-mark": (PRINT, (1139, 574, 26, 29), "mark"),       # business card back
    "alert-mark": (PRINT, (569, 192, 37, 35), "mark"),           # flyer back, price notice
    "facebook-banner-mark": (PRINT, (505, 918, 32, 32), "mark"),  # banner footer
}
SCALE, NOISE, QUALITY, SEED = 0.7, 4.0, 20, 20260916
RAMP = (28, 6, 34)  # added RGB at the right-hand edge, 0 at the left


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    img = img.convert("RGB")
    img = img.resize((round(img.width * SCALE), round(img.height * SCALE)), Image.BICUBIC)
    width = img.width
    pixels = []
    for i, px in enumerate(img.get_flattened_data()):
        t = (i % width) / max(width - 1, 1)
        pixels.append(tuple(max(0, min(255, round(c + ramp * t + rng.gauss(0, NOISE)))) for c, ramp in zip(px, RAMP)))
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=QUALITY)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    sheets = {name: Image.open(os.path.join(UPLOADS, name)).convert("RGB") for name in (PRINT, WEB)}
    for name, (sheet, (x, y, w, h), _kind) in CROPS.items():
        crop = sheets[sheet].crop((x, y, x + w, y + h))
        crop.save(os.path.join(OUT, f"{name}.png"))
        degrade(crop, random.Random(f"{SEED}:{name}")).save(os.path.join(OUT, f"{name}.low.png"))


if __name__ == "__main__":
    main()
