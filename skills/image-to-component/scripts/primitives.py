"""Is this asset a container shape, which primitive family is it, and may it be emitted as one?

Stdlib only. The route is ADR-0175: an *in-asset* container — a tile, a badge disc, a status pill, a
rounded-rect backplate that is the whole of one asset — is emitted as a fitted SVG primitive rather
than traced into a polygon. A *layout* container stays CSS, and nothing here changes that.

Two halves, deliberately separate:

**Candidacy** is cheap and topological. Predicates over the keyed alpha the `--auto` route already
produces: one 8-connected component; no background pixel unreachable from the border; nothing drawn
ON the shape (a second flat colour, read by the caller); area over convex-hull area above a floor;
area over bounding-box area above a floor; and mirror symmetry about both axes of its own box above
a floor, because every admissible family has it and a glyph does not. A knockout tile, a
letterform and every glyph fail one of them.

Two shapes that fail the first two predicates are decomposed instead of refused (batch 3): ONE hole
concentric with the outline is a band, fitted as a stroked primitive (`stroke_reading`,
harness:RM-0679); a second flat colour is a backplate judged here plus an interior the caller traces
(`second_colour`, `interior`, `composite_svg`, harness:RM-0678). Each is switched off by leaving its
parameter out — `concentric` and `interior_bar` — which is how the eval closes them to calibrate the
rest on batch 2's population.

**Acceptance** is adversarial, and is DEC-0178's rule transposed from a library index to a
parametric family: every family is fitted, rendered and degraded to the source, and the best must
clear `bar` *and* beat every **distinguishable** other family by `margin`, on at least `min_weight`
pixels of disagreement. The families are nested — `rect` is `rounded-rect(r=0)`, `pill` is
`rounded-rect(r=min(w,h)/2)`, `circle` is both `ellipse(rx=ry)` and `pill(w=h)` — so families whose
renders agree above `equivalent` are **not** adversaries: the fewest-parameter family among them
wins and the tie is recorded. Rendering and the equivalence test live with the caller
(`primitives_run`), because they need the toolchain; everything here is arithmetic.

Fitting takes the box from the visible extent and the radius from the area the corners remove, both
in closed form. An imprecise fit can only lower a score, so it can only cause a refusal — never a
wrong acceptance, which is the failure this route exists to prevent.
"""
from __future__ import annotations

import json

VISIBLE = 128
FAMILIES = ("rect", "rounded-rect", "circle", "ellipse", "pill")
# Only two of them are FITTED and judged. The other three are those two at particular parameters —
# `rect` is `rounded-rect(rx=0)`, `pill` is `rounded-rect(rx=min(w,h)/2)`, `circle` is
# `ellipse(rx=ry)` — so their names are READ OFF the winner rather than contested against it.
# Fitting all five made each special case compete with the shape it is a special case of, and gave
# it its own best box scale, so a pill and the rounded rect that IS that pill rendered at different
# sizes and did not tie. What remains is the one question that is genuinely a question: is this
# shape a rounded box or an ellipse?
FITTED = ("rounded-rect", "ellipse")
# Free shape parameters per family, the tie-break when two families render the same pixels.
PARAM_COUNT = {"circle": 1, "rect": 2, "ellipse": 2, "pill": 2, "rounded-rect": 3}
REQUIRED = ("bar", "margin", "min_weight", "equivalent", "radius_resolved", "hull_fill", "concentric",
            "stroke_bar", "interior_bar",
            "bbox_fill", "symmetry", "min_px", "sigmas")
# A rect of w×h with corner radius r loses (4 - pi)r² of area to its corners.
CORNER = 4 - 3.141592653589793


def load_params(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        params = json.load(fh)
    missing = [key for key in REQUIRED if key not in params]
    if missing:
        raise ValueError(f"{path} declares no {', '.join(missing)}")
    return params


def moments(alpha: bytes, width: int, height: int) -> dict | None:
    """Area, centroid and visible box of an alpha-only buffer; None when nothing is visible.

    Area is the soft alpha sum, so a blurred edge contributes its coverage rather than a hard
    in-or-out vote. The box is the extent of the pixels at or above `VISIBLE`, plus one — a run of
    columns x0..x1 inclusive is x1 - x0 + 1 wide.
    """
    area = 0.0
    sx = sy = 0.0
    x0 = y0 = None
    x1 = y1 = -1
    for y in range(height):
        row = alpha[y * width:(y + 1) * width]
        for x, a in enumerate(row):
            if not a:
                continue
            area += a / 255.0
            sx += x * a / 255.0
            sy += y * a / 255.0
            if a >= VISIBLE:
                x0 = x if x0 is None else min(x0, x)
                y0 = y if y0 is None else min(y0, y)
                x1, y1 = max(x1, x), max(y1, y)
    if not area or x0 is None:
        return None
    return {"area": area, "cx": sx / area + 0.5, "cy": sy / area + 0.5,
            "x0": float(x0), "y0": float(y0), "w": float(x1 - x0 + 1), "h": float(y1 - y0 + 1)}


def _components(alpha: bytes, width: int, height: int) -> int:
    """8-connected components of the visible foreground."""
    seen = bytearray(width * height)
    found = 0
    for start in range(width * height):
        if seen[start] or alpha[start] < VISIBLE:
            continue
        found += 1
        stack = [start]
        seen[start] = 1
        while stack:
            i = stack.pop()
            x, y = i % width, i // width
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        j = ny * width + nx
                        if not seen[j] and alpha[j] >= VISIBLE:
                            seen[j] = 1
                            stack.append(j)
    return found


def _flood(alpha: bytes, width: int, height: int, seeds: list[int], seen: bytearray) -> list[int]:
    """Every background pixel 4-connected to `seeds`, marking `seen`; the seeds must be background."""
    region = []
    stack = []
    for i in seeds:
        if not seen[i]:
            seen[i] = 1
            stack.append(i)
    while stack:
        i = stack.pop()
        region.append(i)
        x, y = i % width, i // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                j = ny * width + nx
                if not seen[j] and alpha[j] < VISIBLE:
                    seen[j] = 1
                    stack.append(j)
    return region


def holes(alpha: bytes, width: int, height: int) -> list[list[int]]:
    """The background regions a 4-connected flood from the border cannot reach, one list each."""
    seen = bytearray(width * height)
    border = [y * width + x for x in range(width) for y in (0, height - 1)]
    border += [y * width + x for y in range(height) for x in (0, width - 1)]
    _flood(alpha, width, height, [i for i in border if alpha[i] < VISIBLE], seen)
    return [_flood(alpha, width, height, [i], seen) for i in range(width * height)
            if not seen[i] and alpha[i] < VISIBLE]


def _has_hole(alpha: bytes, width: int, height: int) -> bool:
    return bool(holes(alpha, width, height))


def fill_holes(alpha: bytes, width: int, height: int) -> bytes:
    """The silhouette a stroked shape outlines: every enclosed background pixel made opaque."""
    out = bytearray(alpha)
    for region in holes(alpha, width, height):
        for i in region:
            out[i] = 255
    return bytes(out)


def stroke_reading(alpha: bytes, width: int, height: int) -> dict | None:
    """{"concentric", "width"} when the shape has exactly ONE interior hole, else None.

    harness:RM-0679. A stroked container's band is the same width all the way round, so the four
    margins between the outer visible box and the hole's box are equal. `concentric` is the smallest
    margin over the largest — 1.0 for a ring, near 0 for a hole pushed to one side, which is what a
    knocked-out glyph and a letterform's counter look like. `width` is their mean, the closed-form
    stroke width the runner refines against the render.
    """
    found = holes(alpha, width, height)
    if len(found) != 1:
        return None
    m = moments(alpha, width, height)
    xs = [i % width for i in found[0]]
    ys = [i // width for i in found[0]]
    margins = (min(xs) - m["x0"], m["x0"] + m["w"] - (max(xs) + 1),
               min(ys) - m["y0"], m["y0"] + m["h"] - (max(ys) + 1))
    widest = max(margins)
    concentric = min(margins) / widest if min(margins) > 0 and widest > 0 else 0.0
    return {"concentric": concentric, "width": sum(margins) / 4}


def _hull_area(alpha: bytes, width: int, height: int) -> float:
    """Area of the convex hull of the visible pixels' corners (monotone chain, shoelace)."""
    points = set()
    for y in range(height):
        for x in range(width):
            if alpha[y * width + x] >= VISIBLE:
                points.update(((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)))
    pts = sorted(points)
    if len(pts) < 3:
        return 0.0

    def half(seq):
        out: list[tuple[int, int]] = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0:
                    break
                out.pop()
            out.append(p)
        return out

    hull = half(pts)[:-1] + half(reversed(pts))[:-1]
    twice = sum(hull[i][0] * hull[i - 1][1] - hull[i - 1][0] * hull[i][1] for i in range(len(hull)))
    return abs(twice) / 2.0


def symmetry(alpha: bytes, width: int, height: int) -> float:
    """How well the visible box mirrors itself about each of its own axes; the worse of the two.

    Every admissible family is symmetric about both axes of its bounding box — that is what makes
    them five shapes rather than a vocabulary. A glyph is not: a thermometer is a bulb at one end,
    an arrow a head at one end. The measure is a soft IoU against the reflection, so a blurred edge
    counts as its coverage rather than voting in or out.
    """
    m = moments(alpha, width, height)
    if m is None:
        return 0.0
    x0, y0, w, h = int(m["x0"]), int(m["y0"]), int(m["w"]), int(m["h"])
    crop = [alpha[(y0 + y) * width + x0:(y0 + y) * width + x0 + w] for y in range(h)]
    flat = b"".join(crop)
    horizontal = b"".join(bytes(reversed(row)) for row in crop)
    vertical = b"".join(reversed(crop))
    return min(_soft_iou(flat, horizontal), _soft_iou(flat, vertical))


def _soft_iou(a: bytes, b: bytes) -> float:
    """Sum min over sum max. `replace.soft_iou` is the same rule; this module stays import-free."""
    top = sum(map(max, a, b))
    return sum(map(min, a, b)) / top if top else 0.0


def candidate(alpha: bytes, width: int, height: int, params: dict, composite: bool = False) -> dict:
    """ADR-0175's predicates. {"ok", "reason", "components", "hole", "composite", "hull_fill", "bbox_fill"}.

    `composite` is the caller's reading of the source's colour: True when the ink holds a second
    flat colour, i.e. something is drawn ON the container. That is a figure on a ground, not a whole
    asset, so it is out of scope for this route (ADR-0175, fork 1) — and it is the one shape a
    threshold cannot catch, because the container underneath really is a rounded rect and fits like
    one. Measured on the committed negatives: the alert mark fits `rounded-rect` at 0.884 and the
    old Facebook square at 0.778, both with no interior hole after keying.
    """
    record: dict = {"ok": False, "reason": None, "components": 0, "hole": False,
                    "composite": bool(composite), "extent": 0.0, "hull_fill": 0.0,
                    "bbox_fill": 0.0, "symmetry": 0.0}
    m = moments(alpha, width, height)
    if m is None:
        record["reason"] = "empty"
        return record
    record["components"] = _components(alpha, width, height)
    if record["components"] != 1:
        record["reason"] = "components"
        return record
    record["hole"] = _has_hole(alpha, width, height)
    record["stroked"] = False
    outline = alpha
    if record["hole"]:
        # harness:RM-0679: one hole concentric with the outer contour is a stroke, not a knockout.
        # Without a `concentric` floor every hole refuses, exactly as batch 2 did.
        reading = stroke_reading(alpha, width, height)
        record["concentric"] = reading["concentric"] if reading else 0.0
        if reading is None or params.get("concentric") is None or reading["concentric"] < params["concentric"]:
            record["reason"] = "hole"
            return record
        record["stroked"], record["stroke"] = True, reading["width"]
        # The floors below ask about the shape the band OUTLINES. Symmetry too: measured, a thin
        # JPEG band mirrors worse than its outline does, and the band's evenness is `concentric`'s job.
        outline = fill_holes(alpha, width, height)
    if composite:
        # harness:RM-0678: something drawn ON the shape is a backplate plus an interior, judged as a
        # whole-asset container here and traced by the caller. Without an `interior_bar` it refuses
        # as batch 2 did; a band with a glyph on it is two decompositions at once and still refuses.
        if params.get("interior_bar") is None or record["stroked"]:
            record["reason"] = "composite"
            return record
    record["extent"] = min(m["w"], m["h"])
    if record["extent"] < params["min_px"]:
        record["reason"] = "too-small"
        return record
    # Both ratios are area over area in the SAME units — visible pixels on both sides. The soft
    # alpha sum is the right numerator for *fitting*, where a blurred edge should contribute its
    # coverage, and the wrong one here: divided by a hull drawn around the visible pixels it reads
    # a blurred disc as non-convex, which refused 86 of 92 ladder sources at 24 px and under.
    visible = sum(1 for v in outline if v >= VISIBLE)
    hull = _hull_area(outline, width, height)
    record["hull_fill"] = visible / hull if hull else 0.0
    record["bbox_fill"] = visible / (m["w"] * m["h"])
    if record["hull_fill"] < params["hull_fill"]:
        record["reason"] = "convexity"
        return record
    if record["bbox_fill"] < params["bbox_fill"]:
        record["reason"] = "bbox-fill"
        return record
    record["symmetry"] = symmetry(outline, width, height)
    if record["symmetry"] < params["symmetry"]:
        record["reason"] = "asymmetry"
        return record
    record["ok"], record["reason"] = True, "candidate"
    return record


def scaled(m: dict, k: float) -> dict:
    """The same measurement with its box scaled by `k` about its own centre, area by `k²`.

    Blur widens the alpha-128 box, so a closed-form fit runs a little large in every family at once.
    The caller sweeps a few scales per family and keeps the best-fitting one — the same correction
    `replace_run`'s SCALE_STEPS makes for a library icon, for the same reason.
    """
    if k == 1.0:
        return m
    w, h = m["w"] * k, m["h"] * k
    return {**m, "w": w, "h": h, "area": m["area"] * k * k,
            "x0": m["x0"] + m["w"] / 2 - w / 2, "y0": m["y0"] + m["h"] / 2 - h / 2}


def fit_family(family: str, m: dict, stroke: float | None = None) -> dict:
    """Closed-form parameters for one family. Box from the visible extent, radius from the area.

    With `stroke`, the geometry is the OUTER edge of the band — `m` is read from `fill_holes` — and
    the params carry `stroke_width`; `element` insets by half of it, because SVG strokes straddle
    their geometry.
    """
    fit = _fit_filled(family, m)
    if stroke is not None:
        fit["params"]["stroke_width"] = stroke
    return fit


def filled(fit: dict) -> dict:
    """The same geometry with no stroke: the adversary every stroked verdict must beat."""
    return {"family": fit["family"],
            "params": {k: v for k, v in fit["params"].items() if k != "stroke_width"}}


def _fit_filled(family: str, m: dict) -> dict:
    if family not in PARAM_COUNT:
        raise ValueError(f"{family!r} is not one of {', '.join(FAMILIES)}")
    x, y, w, h = m["x0"], m["y0"], m["w"], m["h"]
    if family == "rect":
        params = {"x": x, "y": y, "width": w, "height": h}
    elif family == "rounded-rect":
        removed = max(0.0, w * h - m["area"])
        radius = min((removed / CORNER) ** 0.5, w / 2, h / 2)
        params = {"x": x, "y": y, "width": w, "height": h, "rx": radius}
    elif family == "pill":
        params = {"x": x, "y": y, "width": w, "height": h, "rx": min(w, h) / 2}
    elif family == "circle":
        params = {"cx": x + w / 2, "cy": y + h / 2, "r": (w + h) / 4}
    else:  # ellipse
        params = {"cx": x + w / 2, "cy": y + h / 2, "rx": w / 2, "ry": h / 2}
    return {"family": family, "params": params}


def derive(fit: dict, tolerance: float) -> dict:
    """The name this fit actually carries, and the parameters that name expects.

    `tolerance` is `scales.json`'s relative `snap_tolerance`, reused rather than invented: the same
    "near enough to be that value" the size and radius snapping already uses.
    """
    p = fit["params"]
    if fit["family"] == "rounded-rect":
        short = min(p["width"], p["height"])
        if p["rx"] <= tolerance * short:
            return {"family": "rect", "params": {k: v for k, v in p.items() if k != "rx"}}
        if abs(p["rx"] - short / 2) <= tolerance * (short / 2):
            return {"family": "pill", "params": {**p, "rx": p["rx"]}}
        return fit
    if fit["family"] == "ellipse" and abs(p["rx"] - p["ry"]) <= tolerance * max(p["rx"], p["ry"]):
        circle = {"cx": p["cx"], "cy": p["cy"], "r": (p["rx"] + p["ry"]) / 2}
        if "stroke_width" in p:
            circle["stroke_width"] = p["stroke_width"]
        return {"family": "circle", "params": circle}
    return fit


def snap_radius(radius: float, steps: list, tolerance: float, short_side: float) -> dict:
    """`scale.snap` plus the `pill` sentinel: half the short side is a step, not an off-scale value."""
    from scripts import scale

    if "pill" in steps and short_side > 0 and abs(radius - short_side / 2) <= tolerance * max(short_side / 2, 1):
        return {"measured": radius, "step": "pill", "value": short_side / 2}
    return scale.snap(radius, steps, tolerance)


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def element(fit: dict) -> str:
    """The primitive as one SVG element, in the dialect DEC-0186 widened svg2tsx to transcribe.

    A stroked fit (harness:RM-0679) is drawn on its centre line: its params hold the OUTER edge of
    the band, and every dimension is inset by half the stroke width so the band's outer edge lands
    there. Its paint is `fill="none"` and a stroke, which `svg2tsx` rewrites to currentColor.
    """
    p = dict(fit["params"])
    stroke = p.pop("stroke_width", None)
    half = stroke / 2 if stroke else 0.0
    paint = f' fill="none" stroke="#000" stroke-width="{_num(stroke)}"' if stroke else ""
    if fit["family"] == "circle":
        return f'<circle cx="{_num(p["cx"])}" cy="{_num(p["cy"])}" r="{_num(p["r"] - half)}"{paint}/>'
    if fit["family"] == "ellipse":
        return (f'<ellipse cx="{_num(p["cx"])}" cy="{_num(p["cy"])}"'
                f' rx="{_num(p["rx"] - half)}" ry="{_num(p["ry"] - half)}"{paint}/>')
    box = (f'<rect x="{_num(p["x"] + half)}" y="{_num(p["y"] + half)}"'
           f' width="{_num(p["width"] - stroke if stroke else p["width"])}"'
           f' height="{_num(p["height"] - stroke if stroke else p["height"])}"')
    if fit["family"] == "rect":
        return box + paint + "/>"
    return box + f' rx="{_num(max(0.0, p["rx"] - half))}"' + paint + "/>"


def svg(fit: dict, view_box: tuple[float, float, float, float]) -> str:
    """The one-element document rendered for scoring, and emitted when accepted."""
    box = " ".join(_num(v) for v in view_box)
    return f'<svg viewBox="{box}">{element(fit)}</svg>'


def interior(keyed: bytes, plate: bytes) -> bytes:
    """The ink the backplate does not account for: the keyed silhouette minus the plate's own alpha.

    `plate` is `replace.knockout`'s alpha — the keyed alpha scaled by how near each pixel sits to
    the dominant colour — so what is left is the second colour, blended edge included.
    """
    return bytes(max(0, k - p) for k, p in zip(keyed, plate))


def third_colour_share(rgba: bytes, plate: tuple, ink: tuple, opaque_at: int, distance: float) -> float:
    """The share of opaque ink that is neither colour, nor a blend of the two.

    `knockout` is a two-means: it finds two colours whether or not there are three, and the pixels
    of a third are folded into whichever side is nearer. A dark tile holding a red disc with a white
    "!" on it then traces the disc and the "!" as ONE interior colour, and the "!" is gone from a
    component whose every number passes. Distance is taken to the SEGMENT between the two colours,
    so the anti-aliased blend where plate meets glyph is not a third colour. `opaque_at` and
    `distance` are `replace`'s knockout constants, passed in so this module stays import-free.
    """
    axis = [i - p for i, p in zip(ink, plate)]
    norm = sum(v * v for v in axis) or 1.0
    opaque = far = 0
    for i in range(0, len(rgba), 4):
        if rgba[i + 3] < opaque_at:
            continue
        opaque += 1
        px = rgba[i:i + 3]
        t = min(1.0, max(0.0, sum((px[c] - plate[c]) * axis[c] for c in range(3)) / norm))
        nearest = [plate[c] + t * axis[c] for c in range(3)]
        if sum((px[c] - nearest[c]) ** 2 for c in range(3)) ** 0.5 >= distance:
            far += 1
    return far / opaque if opaque else 0.0


def second_colour(rgba: bytes, width: int, height: int, opaque_at: int, distance: float,
                  min_px: int) -> tuple | None:
    """(plate alpha, plate colour, ink colour) when anything is drawn ON the shape, else None.

    `replace.knockout` answers this for the replace route with a share floor — a second colour
    under 3 % of the ink is not a knockout there, because a library icon is the truth and a speck is
    noise. Here the source IS the truth, and a glyph under that floor is still a glyph: measured, a
    white "!" covering 2.4 % of a 32 px tile keyed in colour mode read as no second colour at all,
    and the tile shipped as a plain rounded rect with the "!" gone — four times on the eval split.

    So the question is asked of the INTERIOR alone: opaque pixels whose four neighbours are opaque
    too, at least `distance` from the colour of the silhouette's own edge. The edge is excluded
    because that is where JPEG ringing and keying blend live, and a glyph drawn on a tile is not
    there. `min_px` of them is a glyph; fewer is noise.
    """
    def at(x, y):
        return rgba[(y * width + x) * 4:(y * width + x) * 4 + 4]

    def opaque(x, y):
        return 0 <= x < width and 0 <= y < height and at(x, y)[3] >= opaque_at

    edge, inner = [], []
    for y in range(height):
        for x in range(width):
            if not opaque(x, y):
                continue
            px = tuple(at(x, y)[:3])
            (inner if all(opaque(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
             else edge).append(px)
    if not edge:
        return None
    plate = tuple(sum(p[c] for p in edge) / len(edge) for c in range(3))
    far = [p for p in inner if sum((p[c] - plate[c]) ** 2 for c in range(3)) ** 0.5 >= distance]
    if len(far) < min_px:
        return None
    ink = tuple(sum(p[c] for p in far) / len(far) for c in range(3))
    axis = [i - p for i, p in zip(ink, plate)]
    norm = sum(v * v for v in axis)
    alpha = bytearray()
    for i in range(0, len(rgba), 4):
        t = sum((rgba[i + c] - plate[c]) * axis[c] for c in range(3)) / norm
        alpha.append(round(rgba[i + 3] * min(1.0, max(0.0, 1.0 - t))))
    return bytes(alpha), plate, ink


def _hex(colour: tuple) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in colour)


def composite_svg(fit: dict, view_box: tuple, paths: list[tuple[str, str | None]],
                  plate: tuple, ink: tuple) -> str:
    """The backplate element, then each traced interior path, each in its own flat colour.

    `paths` are (d, transform) pairs as vtracer writes them. The backplate carries an explicit fill
    because the interior does, and one painted element beside one default-black one is two colour
    conventions in a single document.
    """
    box = " ".join(_num(v) for v in view_box)
    head = element(fit)[:-2] + f' fill="{_hex(plate)}"/>'
    body = "".join(f'<path d="{d}"' + (f' transform="{t}"' if t else "") + f' fill="{_hex(ink)}"/>'
                   for d, t in paths)
    return f'<svg viewBox="{box}">{head}{body}</svg>'


def tied_with_leader(fits: dict, ties: set) -> set:
    """The leader plus the families whose renders agree with it; none of them is an adversary."""
    leader = max(fits, key=lambda f: (fits[f], -PARAM_COUNT[f]))
    return {leader} | {f for f in ties if f in fits}


def select(fits: dict, ties: set) -> str:
    """The family that is emitted: fewest parameters among those tied with the best-fitting one.

    The **one** implementation of that question. The caller building the pair margins needs to know
    which render is the named one before `decide` runs, and two answers computed separately are two
    answers that can disagree (`.claude/rules/ci/rule-enforcement.md`).
    """
    tied = tied_with_leader(fits, ties)
    return min(tied, key=lambda f: (PARAM_COUNT[f], -fits[f], f))


def decide(fits: dict, pairs: dict, ties: set, params: dict, names: dict | None = None,
           fixed: dict | None = None) -> dict:
    """DEC-0178's rule over families. `fits` family → soft IoU; `pairs` family → (t, weight).

    `fixed` holds adversaries that are not fitted families and never tie — `filled`, the same
    geometry with no stroke, which every stroked verdict must beat (harness:RM-0679). They are
    judged exactly as a family adversary is.

    `ties` are the families whose renders agree with the leader's above `equivalent`; they are not
    adversaries, and the fewest-parameter family among them is the one emitted.

    `names` maps each fitted family to the name its parameters actually carry — `rounded-rect` at
    half the short side is a `pill`, an `ellipse` with equal axes is a `circle`. **Every name the
    verdict reports passes through it**, because a verdict that reads `family` in one vocabulary and
    `ties` in the other is comparing two languages: measured, `--family pill` refused a 12 px source
    whose pill tied with the emitted circle at agreement 1.000, and the eval read that same row as a
    wrong acceptance. `fitted` keeps the lineage, which is what the radius guard turns on.
    """
    names = names or {}

    def named(family):
        return names.get(family, family) if family is not None else None

    tied = tied_with_leader(fits, ties)
    chosen = select(fits, ties)
    adversaries = {f: pairs[f] for f in fits if f not in tied and f in pairs}
    adversaries.update(fixed or {})

    worst = min(adversaries, key=lambda f: adversaries[f][0], default=None)
    verdict = {"family": named(chosen), "fitted": chosen, "fit": fits[chosen],
               "ties": sorted({named(f) for f in tied}),
               "runner_up": named(worst), "margin": adversaries[worst][0] if worst else None,
               "weight": adversaries[worst][1] if worst else None,
               "accepted": False, "reason": "bar"}
    if fits[chosen] < params["bar"]:
        return verdict
    for family, (t, weight) in sorted(adversaries.items()):
        if weight < params["min_weight"]:
            verdict.update(runner_up=named(family), margin=t, weight=weight,
                           reason="indistinguishable")
            return verdict
        if t < params["margin"]:
            verdict.update(runner_up=named(family), margin=t, weight=weight, reason="adversary")
            return verdict
    verdict.update(accepted=True, reason="accepted")
    return verdict
