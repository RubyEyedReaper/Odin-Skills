"""Synthesise the primitives eval: a degradation ladder, confusers, and the committed negatives.

    make_sources.py <out-dir>        # writes <out-dir>/*.png and <out-dir>/manifest.jsonl

Nothing is fetched. The positives are drawn from parameters, and the negatives are the product's own
glyphs and marks already committed under `evals/degraded/src/` and `evals/heldout/src/` — which is
the whole reason this eval runs offline where the replacement eval cannot (the batch-2 plan, fork 4).

Every source records its truth: the family it was drawn as, its rung, and its split. Two splits from
two seeds; `calibrate` reads one and `score` reads the other, never both.
"""
from __future__ import annotations

import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

SS = 4                                            # supersample the drawing, then box-reduce
RUNGS = (8, 10, 12, 16, 20, 24, 32, 40)
FAMILIES = ("rect", "rounded-rect", "circle", "ellipse", "pill")
# Eight, not three. Three instances per (family, rung) is 15 sources per rung per split, and the
# two splits then disagree about which failure classes they contain: three separate floors in a row
# calibrated to their loosest value because the calibrate split held no source that needed them,
# and the held-out split did. A floor calibrated on a sample that lacks the case is not calibrated.
PER_RUNG = 8
PAD = 6
SPLITS = {"calibrate": 20260917, "eval": 20260918}
INK = (20, 24, 33)
NEGATIVE_DIRS = ("evals/degraded/src", "evals/heldout/src")


def draw(family: str, px: int, rng: random.Random, stroked: bool = False) -> tuple[Image.Image, dict]:
    """One source at `px` on its long side, with the family's own parameters jittered.

    `stroked` draws the same outer shape as a band (harness:RM-0679): PIL draws an outline INSIDE
    its box, so the box stays the outer edge and the truth is the family plus a stroke width.
    """
    long_side = px
    if family in ("rect", "rounded-rect"):
        short = max(4, round(long_side * rng.uniform(0.55, 1.0)))
    elif family == "ellipse":
        short = max(4, round(long_side * rng.uniform(0.45, 0.85)))
    elif family == "pill":
        short = max(4, round(long_side * rng.uniform(0.35, 0.7)))
    else:  # circle
        short = long_side
    w, h = (long_side, short) if rng.random() < 0.5 else (short, long_side)
    if family == "circle":
        w = h = long_side

    radius = 0.0
    if family == "rounded-rect":
        radius = max(1.0, min(w, h) / 2 * rng.uniform(0.2, 0.75))
    elif family == "pill":
        radius = min(w, h) / 2

    canvas = (max(w, h) + 2 * PAD)
    img = Image.new("RGBA", (canvas * SS, canvas * SS), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    x0 = (canvas - w) // 2 * SS
    y0 = (canvas - h) // 2 * SS
    box = [x0, y0, x0 + w * SS - 1, y0 + h * SS - 1]
    # A band at least one pixel wide, and never so wide that the hole closes at this size.
    stroke = max(1.0, round(min(w, h) * rng.uniform(0.1, 0.22) * 2) / 2) if stroked else 0.0
    paint = ({"outline": INK + (255,), "width": round(stroke * SS)} if stroked
             else {"fill": INK + (255,)})
    if family in ("circle", "ellipse"):
        d.ellipse(box, **paint)
    elif family == "rect":
        d.rectangle(box, **paint)
    else:
        d.rounded_rectangle(box, radius=radius * SS, **paint)
    img = img.resize((canvas, canvas), Image.BOX)
    return img, {"w": w, "h": h, "radius": round(radius, 3), "canvas": canvas,
                 "stroked": stroked, "stroke": stroke}


def degrade(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    """Blur, jitter and noise the drawing the way a mockup crop arrives."""
    sigma = round(rng.uniform(0.0, 0.9), 2)
    noise = round(rng.uniform(0.0, 8.0), 2)
    out = img.convert("RGB")
    if sigma:
        out = out.filter(ImageFilter.GaussianBlur(sigma))
    if noise:
        pixels = bytearray(out.tobytes())
        for i, v in enumerate(pixels):
            pixels[i] = max(0, min(255, v + round(rng.gauss(0, noise))))
        out = Image.frombytes("RGB", out.size, bytes(pixels))
    return out, {"sigma": sigma, "noise": noise, "quality": rng.randint(20, 60)}


# `scales.json`'s snap_tolerance is 0.125 relative, so `derive` reads any axis ratio at or above
# 0.875 as equal — a 10x9 ellipse IS a circle and a radius at 0.9 of its cap IS a pill, by the
# vocabulary this skill declares (DEC-0181). A fixture drawn inside that band and labelled `ellipse`
# or `rounded-rect` asserts a distinction the vocabulary forbids: it can only ever score WRONG or
# missed, whatever the verifier does, and it measured WRONG twice on the eval split. The confusers
# therefore sit just OUTSIDE the band, which is the hardest case that still has an answer.
SNAP_BAND = 0.875


def confusers(rng: random.Random) -> list[tuple[str, int, dict]]:
    """Parameters that sit deliberately between two families, where a refusal is the right answer.

    A rounded rect whose radius is nearly half its short side is nearly a pill; a pill whose sides
    are nearly equal is nearly a circle; an ellipse with nearly equal axes is nearly a circle. At
    8-16 px the difference is a pixel or two, so the verifier should refuse as indistinguishable
    rather than guess — a guess there is a wrong acceptance that every number agrees with.

    Two of the three are drawn just below `SNAP_BAND`. The pill is not: its radius is exactly half
    its short side whatever its aspect, so `pill` stays the name its parameters carry and the near-
    square case tests the tie machinery instead — which is what should answer it.
    """
    out = []
    for px in (8, 10, 12, 16):
        for _ in range(2):
            out.append(("rounded-rect", px, {"radius_ratio": rng.uniform(0.72, SNAP_BAND - 0.035)}))
            out.append(("pill", px, {"aspect": rng.uniform(0.85, 0.99)}))
            out.append(("ellipse", px, {"aspect": rng.uniform(0.72, SNAP_BAND - 0.035)}))
    return out


def draw_confuser(family: str, px: int, tweak: dict, rng: random.Random) -> tuple[Image.Image, dict]:
    if family == "rounded-rect":
        w, h = px, max(4, round(px * 0.7))
        radius = min(w, h) / 2 * tweak["radius_ratio"]
    elif family == "pill":
        w, h = px, max(4, round(px * tweak["aspect"]))
        radius = min(w, h) / 2
    else:
        w, h = px, max(4, round(px * tweak["aspect"]))
        radius = 0.0
    canvas = max(w, h) + 2 * PAD
    img = Image.new("RGBA", (canvas * SS, canvas * SS), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    x0, y0 = (canvas - w) // 2 * SS, (canvas - h) // 2 * SS
    box = [x0, y0, x0 + w * SS - 1, y0 + h * SS - 1]
    if family == "ellipse":
        d.ellipse(box, fill=INK + (255,))
    else:
        d.rounded_rectangle(box, radius=radius * SS, fill=INK + (255,))
    return img.resize((canvas, canvas), Image.BOX), {"w": w, "h": h, "radius": round(radius, 3),
                                                     "canvas": canvas}


# The committed tiles that are one backplate with one glyph on it, read off the pixels: the alert
# mark is a red disc under a white "!", both Facebook marks a blue rounded square under an "f". A
# hand label is a claim, so it is stated once, here, with what it rests on. Every other committed
# file stays a negative — a gamepad, a gear or a thermometer has no backplate to be right about.
COMPOSITE_TRUTH = {"alert-mark": "circle", "facebook-banner-mark": "rounded-rect",
                   "facebook-mark": "rounded-rect"}
PLATES = ((24, 119, 242), (225, 29, 46), (22, 163, 74), (124, 58, 237))
GLYPHS = ("plus", "triangle", "bang", "chevron")


def _glyph(d: ImageDraw.ImageDraw, kind: str, cx: float, cy: float, g: float, colour: tuple) -> None:
    """One glyph of size `g` centred at (cx, cy), in supersampled pixels."""
    t = g / 4
    if kind == "plus":
        d.rectangle([cx - t / 2, cy - g / 2, cx + t / 2, cy + g / 2], fill=colour)
        d.rectangle([cx - g / 2, cy - t / 2, cx + g / 2, cy + t / 2], fill=colour)
    elif kind == "triangle":
        d.polygon([(cx, cy - g / 2), (cx + g / 2, cy + g / 2), (cx - g / 2, cy + g / 2)], fill=colour)
    elif kind == "bang":
        d.rectangle([cx - t / 2, cy - g / 2, cx + t / 2, cy + g / 5], fill=colour)
        d.rectangle([cx - t / 2, cy + g / 2 - t, cx + t / 2, cy + g / 2], fill=colour)
    else:  # chevron
        d.line([(cx - g / 2, cy - g / 4), (cx, cy + g / 4), (cx + g / 2, cy - g / 4)], fill=colour,
               width=max(1, round(t)))


def draw_composite(family: str, px: int, rng: random.Random) -> tuple[Image.Image, dict]:
    """A filled backplate with a glyph drawn ON it in a second flat colour (harness:RM-0678).

    Half on a white page with a pale glyph, half on a dark page with a white one — the white glyph
    on a white page keys as a HOLE, not a second colour, and is the hole predicate's case.
    """
    img, shape = draw(family, px, rng)
    dark = rng.random() < 0.5
    page = (20, 24, 33) if dark else (255, 255, 255)
    plate_colour = rng.choice(PLATES)
    glyph_colour = (255, 255, 255) if dark else (250, 204, 21)
    kind = rng.choice(GLYPHS)
    canvas = shape["canvas"]
    big = Image.new("RGB", (canvas * SS, canvas * SS), page)
    mask = img.convert("L").resize(big.size, Image.BOX).point(lambda v: 255 - v)
    big.paste(plate_colour, mask=mask)
    d = ImageDraw.Draw(big)
    g = min(shape["w"], shape["h"]) * rng.uniform(0.35, 0.55) * SS
    _glyph(d, kind, canvas * SS / 2, canvas * SS / 2, g, glyph_colour)
    return big.resize((canvas, canvas), Image.BOX), {**shape, "glyph": kind, "dark": dark}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    out = argv[0]
    skill = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(out, exist_ok=True)
    rows = []
    for split, seed in SPLITS.items():
        rng = random.Random(seed)
        for family in FAMILIES:
            for px in RUNGS:
                for n in range(PER_RUNG):
                    img, shape = draw(family, px, rng)
                    img, noise = degrade(img, rng)
                    name = f"{split}-{family}-{px}-{n}.jpg"
                    img.save(os.path.join(out, name), quality=noise["quality"])
                    rows.append({"file": name, "set": "ladder", "split": split, "truth": family,
                                 "px": px, **shape, **noise})
        for i, (family, px, tweak) in enumerate(confusers(rng)):
            img, shape = draw_confuser(family, px, tweak, rng)
            img, noise = degrade(img, rng)
            name = f"{split}-confuser-{family}-{px}-{i}.jpg"
            img.save(os.path.join(out, name), quality=noise["quality"])
            rows.append({"file": name, "set": "confusers", "split": split, "truth": family,
                         "px": px, **shape, **noise})
        # The stroked ladder (harness:RM-0679): the same five outer shapes drawn as a band. Its own
        # set and its own seed, so every batch-2 source is drawn byte-identically and the filled
        # ladder's counts stay comparable; half as many per rung.
        stroked_rng = random.Random(seed + 2)
        for family in FAMILIES:
            for px in RUNGS:
                for n in range(PER_RUNG // 2):
                    img, shape = draw(family, px, stroked_rng, stroked=True)
                    img, noise = degrade(img, stroked_rng)
                    name = f"{split}-stroked-{family}-{px}-{n}.jpg"
                    img.save(os.path.join(out, name), quality=noise["quality"])
                    rows.append({"file": name, "set": "stroked", "split": split, "truth": family,
                                 "px": px, **shape, **noise})

    # Negatives: the product's own glyphs and marks, committed and unmodified. Every acceptance is
    # WRONG — a glyph is never a container shape (ADR-0175). The source files are DEALT between the
    # splits rather than shared, because the candidacy floors are what the negatives bound and
    # calibrating a floor on the same negatives it is then scored against proves nothing.
    #
    # Each is then run down the SAME degradation ladder as the positives. The committed files alone
    # are 28 sources at one size each, and a floor can only be calibrated against the near-misses:
    # measured, only one of them needed the symmetry floor and it was on the held-out side, so the
    # calibrate split could not choose that floor at all and the sweep read it as costing pure
    # recall. A glyph degraded to 8 px is exactly the blob that tests a container predicate.
    negatives = []
    for rel in NEGATIVE_DIRS:
        directory = os.path.join(skill, rel)
        negatives += [os.path.join(directory, e) for e in sorted(os.listdir(directory)) if e.endswith(".png")]
    rng = {split: random.Random(seed + 1) for split, seed in SPLITS.items()}
    for i, path in enumerate(sorted(negatives)):
        split = "calibrate" if i % 2 else "eval"
        rows.append({"file": path, "set": "negatives", "truth": None, "px": None, "split": split})
        stem = os.path.splitext(os.path.basename(path))[0]
        if ".destroyed" in os.path.basename(path):
            # The committed file stays a negative; its LADDER does not exist. That fixture is the
            # degraded eval's "unusable source" case, and resized to 16 px its keyed silhouette is a
            # perfect 16x14 solid rectangle — measured, hull fill and bbox fill both 1.000, and
            # `quality.assess` passes it at stability 1.0 because the blob has a clean edge. It IS a
            # rectangle. Calling the fit a wrong acceptance would require the verifier to know the
            # file's provenance rather than read the image, which is a truth the pixels do not carry.
            # The real guard is upstream: crop something that still depicts the asset.
            continue
        # A committed tile that IS one backplate with a glyph on it is a composite positive, not a
        # negative, from batch 3 on (harness:RM-0678). Its truth is the backplate's family.
        tile = COMPOSITE_TRUTH.get(stem.split(".")[0])
        if tile:
            rows[-1].update({"set": "composite", "truth": tile, "composite": True})
        source = Image.open(path).convert("RGBA")
        # The page the crop was taken from, continued. 26 of the 28 committed files are opaque crops
        # of a DARK UI, and padding them with white invented a dark square tile around every glyph —
        # a container the product never drew. Batch 2 refused those at `composite` and `hole`, so the
        # invention was invisible; batch 3 decomposes composites, and read it as a tile with a glyph
        # on it, correctly, from pixels that were wrong (harness:RM-0678).
        corner = source.getpixel((0, 0))
        page = corner[:3] + (255,) if corner[3] == 255 else (255, 255, 255, 255)
        for px in RUNGS:
            long_side = max(source.size)
            k = px / long_side
            size = (max(3, round(source.size[0] * k)), max(3, round(source.size[1] * k)))
            plate = Image.new("RGBA", (size[0] + 2 * PAD, size[1] + 2 * PAD), page)
            plate.alpha_composite(source.resize(size, Image.LANCZOS), (PAD, PAD))
            img, noise = degrade(plate, rng[split])
            name = f"{split}-negative-{stem}-{px}.jpg"
            img.save(os.path.join(out, name), quality=noise["quality"])
            row = {"file": name, "set": "negatives", "truth": None, "px": px, "split": split, **noise}
            if tile:
                row.update({"set": "composite", "truth": tile, "composite": True})
            rows.append(row)

    # The synthetic composite set: each backplate family with a glyph drawn ON it in a second flat
    # colour. Its own seed per split, so every batch-2 source is drawn byte-identically.
    for split, seed in SPLITS.items():
        composite_rng = random.Random(seed + 3)
        for family in FAMILIES:
            for px in RUNGS:
                for n in range(PER_RUNG // 2):
                    img, shape = draw_composite(family, px, composite_rng)
                    img, noise = degrade(img, composite_rng)
                    # Half lossless. A tile in a mockup is usually a PNG screenshot, and JPEG's 4:2:0
                    # chroma subsampling smears a coloured edge across two pixels: measured, 170 of
                    # 187 all-JPEG composites refused at `source-quality` on ramp extent, so the set
                    # measured almost nothing about the decomposition. The JPEG half keeps that case.
                    ext = "png" if n % 2 == 0 else "jpg"
                    name = f"{split}-composite-{family}-{px}-{n}.{ext}"
                    img.save(os.path.join(out, name), **({"quality": noise["quality"]} if ext == "jpg" else {}))
                    rows.append({"file": name, "set": "composite", "split": split, "truth": family,
                                 "px": px, "composite": True, **shape, **noise})

    with open(os.path.join(out, "manifest.jsonl"), "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        counts[(row["split"], row["set"])] = counts.get((row["split"], row["set"]), 0) + 1
    for key in sorted(counts):
        print(f"make_sources: {key[0]} {key[1]}: {counts[key]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
