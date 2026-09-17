"""Synthesise the replacement eval's sources from the pinned libraries: a ladder, confusers and negatives.

Needs resvg-py and Pillow, and the library cache (`toolchain.sh i2c_lib_fetch`). Deterministic: every
degradation is drawn from a seeded generator, so a rerun writes identical pixels.

    make_sources.py <out-dir>

Writes <out-dir>/<split>/<id>.png and <out-dir>/manifest.json. Nothing here is committed: the sources are
library artwork, which is fetched, never vendored. Two splits, from two seeds:

- `calibrate` — the only split `evaluate.py calibrate` reads to choose the bar and margins;
- `eval`      — scored with the committed numbers, never used to choose them.

Every ladder entry is an icon rendered at a size from LADDER_PX onto a flat ground, then blurred, noised and
JPEG-compressed. Glyphs are drawn in near-black (`--color currentColor` runs); brand marks in their own hex.
Tiles draw a coloured icon over a light plate of its own outline, on a dark or white page, so the knockout
reading is exercised. Negatives are shapes no library icon is: the RubyTech mark and its custom glyphs, and a
letter "f".
"""
from __future__ import annotations

import io
import json
import os
import random
import sys

import resvg_py
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL)
from scripts import library, pathgeom  # noqa: E402

LADDER_PX = (8, 10, 12, 16, 20, 24, 32, 40)
SEEDS = {"calibrate": 1, "eval": 2}
GLYPHS = ("build", "hardware", "handyman", "schedule", "alarm", "timer", "close", "cancel", "home", "search",
          "settings", "delete", "favorite", "mail", "lock", "person", "star", "warning", "info", "thermostat")
MARKS = ("facebook", "x", "github", "youtube", "whatsapp", "apple", "spotify", "discord")
# Confusers: a source of one member is also named as each other member, and must never be replaced by it.
CONFUSERS = (("material:build", "material:hardware", "material:handyman"),
             ("material:schedule", "material:alarm", "material:timer"),
             ("material:close", "material:cancel", "simple-icons:x"))
NEGATIVE_SOURCES = ("rubytech-mark.png", "gear-icon.png", "wrench-icon.png", "computer-icon.png", "controller-icon.png")
NEGATIVE_NAMES = {"gear-icon.png": ["material:settings"], "wrench-icon.png": ["material:build"],
                  "computer-icon.png": ["material:computer"], "controller-icon.png": ["material:sports_esports"],
                  "rubytech-mark.png": ["simple-icons:ruby"], "letter-f.png": ["simple-icons:facebook"]}
# Tiles: a coloured icon whose holes show a light second colour, over a page that is dark or white — the
# knockout reading (a white "!" cut out of a red disc) the ladder above never exercises.
TILES = (("material:error-fill", (218, 48, 48)), ("material:cancel-fill", (60, 64, 72)),
         ("material:info-fill", (25, 118, 210)), ("material:check_circle-fill", (46, 160, 67)),
         ("material:help-fill", (120, 60, 180)), ("simple-icons:facebook", None))
TILE_GROUNDS = ((28, 28, 34), (255, 255, 255))
TILE_HOLE = (250, 250, 250)
PAD = 0.2
GLYPH_INK = (24, 24, 28)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _render(ref: str, cache: str, pins: dict, px: int) -> Image.Image:
    lib, slug = ref.split(":", 1)
    with open(library.icon_file(cache, pins, lib, slug), encoding="utf-8") as fh:
        icon = library.normalise(fh.read())
    png = resvg_py.svg_to_bytes(svg_string=library.to_svg(icon), width=px, height=px)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA").getchannel("A")


def degrade(alpha: Image.Image, px: int, ink: tuple, rng: random.Random, ground=(255, 255, 255)) -> Image.Image:
    """An icon alpha drawn at `px` inside a padded canvas, then blurred, noised and JPEG-compressed."""
    canvas = round(px * (1 + 2 * PAD))
    big = 8
    art = alpha.resize((px * big, px * big), Image.LANCZOS)
    img = Image.new("RGB", (canvas * big, canvas * big), ground)
    offset = (round(px * PAD * big + rng.uniform(-big, big)), round(px * PAD * big + rng.uniform(-big, big)))
    img.paste(Image.new("RGB", art.size, ink), offset, art)
    img = img.resize((canvas, canvas), Image.BOX)
    blur = rng.uniform(0.0, 0.9)
    if blur > 0.15:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    noise = rng.uniform(0, 8)
    pixels = [tuple(max(0, min(255, round(v + rng.gauss(0, noise)))) for v in p) for p in img.getdata()]
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(20, 60))
    return Image.open(buf).convert("RGB")


def tile(ref: str, colour: tuple, cache: str, pins: dict, px: int, ground: tuple, rng: random.Random) -> Image.Image:
    """The icon in `colour` over its own outer outline in TILE_HOLE, on `ground`, then degraded like the ladder."""
    lib, slug = ref.split(":", 1)
    with open(library.icon_file(cache, pins, lib, slug), encoding="utf-8") as fh:
        icon = library.normalise(fh.read())
    hexed = "#" + "".join(f"{v:02X}" for v in colour)
    plate = "#" + "".join(f"{v:02X}" for v in TILE_HOLE)
    svg = library.to_svg(icon, [hexed], (pathgeom.outer(" ".join(icon.paths)), plate))
    rgba = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=512, height=512)))).convert("RGBA")
    canvas = round(px * (1 + 2 * PAD))
    big = 8
    art = rgba.resize((px * big, px * big), Image.LANCZOS)
    img = Image.new("RGB", (canvas * big, canvas * big), ground)
    offset = (round(px * PAD * big + rng.uniform(-big, big)), round(px * PAD * big + rng.uniform(-big, big)))
    img.paste(art.convert("RGB"), offset, art.getchannel("A"))
    img = img.resize((canvas, canvas), Image.BOX)
    blur = rng.uniform(0.0, 0.9)
    if blur > 0.15:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    noise = rng.uniform(0, 8)
    img.putdata([tuple(max(0, min(255, round(v + rng.gauss(0, noise)))) for v in p) for p in img.getdata()])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(20, 60))
    return Image.open(buf).convert("RGB")


def letter_f(px: int) -> Image.Image:
    img = Image.new("L", (px * 8, px * 8), 0)
    ImageDraw.Draw(img).text((px * 2, -px), "f", fill=255, font=ImageFont.truetype(FONT, px * 9))
    return img.resize((px, px), Image.BOX)


def main(argv: list[str]) -> int:
    out = argv[0]
    pins = library.pins(os.environ)
    cache = os.environ["I2C_LIB_CACHE"]
    with open(f"{library.package_dir(cache, pins, 'simple-icons')}/package/data/simple-icons.json", encoding="utf-8") as fh:
        hexes = {e["slug"]: tuple(int(e["hex"][i:i + 2], 16) for i in (0, 2, 4)) for e in json.load(fh) if "slug" in e}
    confuser_of = {ref: [o for o in group if o != ref] for group in CONFUSERS for ref in group}
    ladder = [(f"material:{g}", True) for g in GLYPHS] + [(f"simple-icons:{m}", False) for m in MARKS]
    names = [ref for ref, _ in ladder]
    manifest = []
    for split, seed in SEEDS.items():
        rng = random.Random(seed)
        os.makedirs(os.path.join(out, split), exist_ok=True)
        for ref, mono in ladder:
            art = _render(ref, cache, pins, 512)
            ink = GLYPH_INK if mono else hexes[ref.split(":", 1)[1]]
            for px in LADDER_PX:
                sid = f"{ref.replace(':', '-')}-{px}"
                path = os.path.join(split, f"{sid}.png")
                degrade(art, px, ink, rng).save(os.path.join(out, path))
                wrong = confuser_of.get(ref) or [rng.choice([n for n in names if n != ref])]
                manifest.append({"id": sid, "split": split, "set": "ladder", "path": path, "truth": ref, "px": px,
                                 "mono": mono, "wrong_names": wrong})
        tile_refs = [ref for ref, _ in TILES]
        for ref, colour in TILES:
            colour = colour or hexes[ref.split(":", 1)[1]]
            for rung, px in enumerate(LADDER_PX):
                ground = TILE_GROUNDS[rung % 2]
                sid = f"tile-{ref.replace(':', '-')}-{px}"
                path = os.path.join(split, f"{sid}.png")
                tile(ref, colour, cache, pins, px, ground, rng).save(os.path.join(out, path))
                manifest.append({"id": sid, "split": split, "set": "ladder", "path": path, "truth": ref, "px": px,
                                 "mono": False, "wrong_names": [rng.choice([n for n in tile_refs if n != ref])]})
        for px in (16, 24, 40):
            path = os.path.join(split, f"letter-f-{px}.png")
            degrade(letter_f(512), px, GLYPH_INK, rng).save(os.path.join(out, path))
            manifest.append({"id": f"letter-f-{px}", "split": split, "set": "negative", "path": path, "truth": None,
                             "px": px, "mono": True, "wrong_names": NEGATIVE_NAMES["letter-f.png"]})
    for name in NEGATIVE_SOURCES:
        src = os.path.join(SKILL, "evals", "rubytech", "src", name)
        mono = name != "rubytech-mark.png"
        manifest.append({"id": name[:-4], "split": "eval", "set": "negative", "path": src, "truth": None, "px": None,
                         "mono": mono, "wrong_names": NEGATIVE_NAMES[name]})
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"make_sources: {len(manifest)} sources in {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
