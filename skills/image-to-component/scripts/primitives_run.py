"""Run the primitive route for one source: is this asset a container shape, and which one?

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py primitives_run`). Every decision is
stdlib (`primitives.py`, `scale.py`); this file only keys, renders and writes.

    primitives_run.py <image> --report primitive.json
                      [--family auto|rect|rounded-rect|circle|ellipse|pill]
                      [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--mono]
                      [--name Pascal --kind icon|logo --out dir]

Steps (ADR-0175, and DEC-0179's comparison reused unchanged):

1. Key the source once, the way `--auto` keys it for this colour mode.
2. Candidacy: `primitives.candidate` — one component, convex enough, fills its box, symmetric. A
   knockout tile, a letterform and every glyph refuse here, cheaply. One concentric hole is a band
   (fitted stroked, harness:RM-0679); a second flat colour is a backplate plus an interior that is
   traced and must match on its own (harness:RM-0678). `examine` is steps 1-4, shared with the eval.
3. Fit the two general families in closed form — `rect`, `pill` and `circle` ARE those two at
   particular parameters — derive each onto the name its parameters carry, then render the derived
   shape supersampled, box-reduce to source size and blur by the sigma whose edge ramp matches the
   source's. The source is never cleaned, and the shape that is scored is the shape that ships.
4. Families whose **clean** renders agree above `equivalent` are not adversaries — they are the same
   shape, because the families are nested. `primitives.select` names the one that is emitted.
5. `primitives.decide`: the selected family must clear `bar` and beat every remaining family by
   `margin`, on at least `min_weight` pixels of disagreement.

With --out, an accepted primitive writes <Name>.svg, <Name>.tsx and <Name>.compare.png. The report is
always written: `i2c.sh` files it into qa.json under `primitive`.

Exit codes: 0 emitted; 4 refused (the run continues to the trace route unchanged); 2 usage,
unreadable input, or a render failure.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys

import resvg_py
from PIL import Image, ImageFilter

from . import autogrid, edges, keying, prep, primitives, quality, replace, scale, svg2tsx, svgcheck
from .render_diff import sheet

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SUPERSAMPLE = 4
SHEET_PX = 192


def _render_alpha(svg_text: str, width: int, height: int) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=svg_text, width=width, height=height)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA").getchannel("A")


class Canvas:
    """The source's keyed alpha and the render/degrade ladder every family is compared through."""

    def __init__(self, alpha: bytes, width: int, height: int, sigmas: list[float], gamma: float):
        self.alpha, self.width, self.height = alpha, width, height
        self.sigmas, self.gamma = sigmas, gamma
        rgba = b"".join(bytes((0, 0, 0, a)) for a in alpha)
        self.ramp = edges.edge_ramp(rgba, width, height)
        self.view_box = (0.0, 0.0, float(width), float(height))

    def clean(self, fit: dict, supersample: int = SUPERSAMPLE) -> Image.Image:
        return _render_alpha(primitives.svg(fit, self.view_box),
                             self.width * supersample, self.height * supersample)

    def degrade(self, clean: Image.Image, sigma: float) -> bytes:
        small = clean.resize((self.width, self.height), Image.BOX)
        blurred = small.filter(ImageFilter.GaussianBlur(sigma)) if sigma > 0 else small
        return replace.normalise_peak(blurred.tobytes(), self.gamma)

    def sigma_for(self, fit: dict) -> float:
        """The blur whose degraded render of `fit` has an edge ramp nearest the source's."""
        ramps = {}
        for sigma in self.sigmas:
            alpha = self.degrade(self.clean(fit), sigma)
            ramp = edges.edge_ramp(b"".join(bytes((0, 0, 0, a)) for a in alpha), self.width, self.height)
            if ramp is not None:
                ramps[sigma] = ramp
        return replace.choose_sigma(self.ramp, ramps) if ramps else 0.0


# A rounded rect's closed-form radius is taken from the area its corners remove, and blur widens the
# alpha-128 box slightly — a wider box holding the same area implies deeper corners, so the estimate
# runs high (7.9 px measured for a true 6 px at 24 px). The radius is the one number a reader sees,
# so it is refined against the render rather than left at the estimate: a radius that is wrong by a
# third passes every silhouette number and looks wrong on the page.
# Fractions of the maximum radius (half the short side), NOT multipliers of the closed-form
# estimate. Multipliers bottomed out at 0.55x, so a square corner was unreachable from any estimate
# above zero and the cap was unreachable from any estimate below it — measured, nine drawn rects
# derived as rounded rects at 20-40 px and two pills likewise. The two ends of the family are
# exactly the two names that are read off this number, so both must be in the sweep.
RADIUS_FRACTIONS = (0.0, 0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0)
# Blur widens the alpha-128 box, so every family is fitted a little large at once. A 6 px-tall pill
# measured at 7 px is a fat stadium and loses to an ellipse fitted to the same box — measured, two
# wrong acceptances at 10 px on the held-out split. Each family gets its best box, the correction
# `replace_run.SCALE_STEPS` already makes for a library icon.
SCALE_STEPS = (0.88, 0.94, 1.0, 1.06)


def refine_radius(canvas: Canvas, fit: dict, sigma: float, tolerance: float) -> dict:
    """The `rx` whose degraded render fits best, over RADIUS_FRACTIONS of the cap plus the estimate.

    Each candidate is derived before it is rendered, so a radius inside `snap_tolerance` of 0 or of
    the cap is scored as the `rect` or `pill` it would be emitted as — see `best_fit`.
    """
    limit = min(fit["params"]["width"], fit["params"]["height"]) / 2
    radii = sorted({min(f * limit, limit) for f in RADIUS_FRACTIONS} | {min(fit["params"]["rx"], limit)})
    best = None
    for radius in radii:
        candidate = primitives.derive(
            {"family": "rounded-rect", "params": {**fit["params"], "rx": radius}}, tolerance)
        score = replace.soft_iou(canvas.alpha, canvas.degrade(canvas.clean(candidate), sigma))
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1]


def rename_rival(canvas: Canvas, fit: dict, sigma: float, tolerance: float) -> dict | None:
    """The best-fitting radius, at the winner's own box, whose shape carries a DIFFERENT name.

    `rect`, `rounded-rect` and `pill` are one family split by one number, so the winner's name is a
    claim that the source sides with its radius over every radius that would rename it — and a
    claim is what an adversary tests. Measured: a 20 px rounded square drawn as a 3 px band at
    sigma 0.83 fitted `rect` at 0.854, beating the true 3.5 px corner on score; `radius_is_resolved`
    passed it, because a square corner renders exactly like a square corner. None when the winner
    is not a rounded box.
    """
    if "width" not in fit["params"]:
        return None
    limit = min(fit["params"]["width"], fit["params"]["height"]) / 2
    best = None
    for f in RADIUS_FRACTIONS:
        rival = primitives.derive(
            {"family": "rounded-rect", "params": {**fit["params"], "rx": min(f * limit, limit)}}, tolerance)
        if rival["family"] == fit["family"]:
            continue
        score = replace.soft_iou(canvas.alpha, canvas.degrade(canvas.clean(rival), sigma))
        if best is None or score > best[0]:
            best = (score, rival)
    return best[1] if best else None


def radius_is_resolved(canvas: Canvas, fit: dict, sigma: float, tolerance: float,
                       agreement: float) -> bool:
    """Can this source tell the winning radius from the two that would rename the shape?

    `rect`, `rounded-rect` and `pill` are one family split by one number, so the name turns on
    whether that number is 0, the cap, or between. The fit score cannot always resolve it: measured
    at 24 px, a drawn stadium's joint best was a 6 % narrower box at 0.8 of the cap, beating the
    true shape on score and shipping a 4.89 px radius where the source had 6.5. That is batch 1's
    `indistinguishable` refusal one level down — the verifier says so instead of guessing, and the
    run falls through to the trace route with the shape intact.

    `agreement` is its OWN parameter, never the family-tie `equivalent`, because the two run in
    opposite directions: a stricter tie threshold means fewer ties and a safer emission, while a
    stricter agreement here means fewer radii called unresolved and a riskier one. Sharing the
    number made tightening the tie loosen this guard, and three drawn squares at 10-12 px shipped as
    rounded rects because their 1.5 px corner agreed with a square corner at 0.97 and not at 0.99.
    """
    limit = min(fit["params"]["width"], fit["params"]["height"]) / 2
    winner = canvas.clean(fit).resize((canvas.width, canvas.height), Image.BOX).tobytes()
    names = {fit["family"]}
    for radius in (0.0, limit):
        rival = {"family": "rounded-rect", "params": {**fit["params"], "rx": radius}}
        other = canvas.clean(rival).resize((canvas.width, canvas.height), Image.BOX).tobytes()
        if replace.equivalent(winner, other, agreement):
            names.add(primitives.derive(rival, tolerance)["family"])
    return len(names) == 1


# Fractions of the closed-form stroke width, which reads the band from the alpha-128 boxes and so
# carries the same blur bias the radius does. Refined against the render, like the radius, because
# the width is a number a reader sees (harness:RM-0679).
STROKE_FRACTIONS = (0.6, 0.8, 1.0, 1.25, 1.5)
STROKE_STEPS = (-1.0, -0.5, 0.5, 1.0)


def _short_side(params: dict) -> float:
    if "width" in params:
        return min(params["width"], params["height"])
    if "r" in params:
        return 2 * params["r"]
    return 2 * min(params["rx"], params["ry"])


def refine_stroke(canvas: Canvas, fit: dict, sigma: float) -> dict:
    """The `stroke_width` whose degraded render fits best, over STROKE_FRACTIONS of the estimate.

    Capped below half the short side, so every candidate still HAS a hole — a band as wide as the
    shape is the filled shape, which is the adversary, not a candidate.
    """
    estimate = fit["params"]["stroke_width"]
    cap = 0.45 * _short_side(fit["params"])
    # Half-pixel steps too: the alpha-128 margins read a 4.5 px band as 4, and 4 × 1.25 overshoots
    # it — measured, the 40 px stroked sources fitted a whole half pixel thin.
    widths = sorted({min(max(0.5, w), cap) for w in
                     [f * estimate for f in STROKE_FRACTIONS] + [estimate + d for d in STROKE_STEPS]})
    best = None
    for width in widths:
        candidate = {"family": fit["family"], "params": {**fit["params"], "stroke_width": width}}
        score = replace.soft_iou(canvas.alpha, canvas.degrade(canvas.clean(candidate), sigma))
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1]


def best_fit(canvas: Canvas, family: str, m: dict, sigma: float,
             tolerance: float, stroke: float | None = None) -> tuple[dict, "Image.Image", float]:
    """(fit, clean render, score) at the box scale — and for a rounded rect, the radius — that fits best.

    **The candidate that is scored is the candidate that would be emitted.** `derive` snaps a fitted
    shape onto the name its parameters carry, and that snap moves pixels: an ellipse at rx 8, ry 7
    becomes a circle at r 7.5, a whole pixel on each axis of a 16 px asset. Scoring the ellipse,
    winning the adversary margin with it and then shipping the circle is scoring one artifact and
    emitting another — measured, two near-square stadiums at 12 and 16 px were named `circle` on an
    ellipse's score, which is the exact failure the eval's own README says this route exists to
    prevent. So the derivation happens here, before the render, and every number downstream — the
    fit, the tie, the pair margin — is about the SVG that ships.
    """
    best = None
    for step in SCALE_STEPS:
        fit = primitives.fit_family(family, primitives.scaled(m, step), stroke=stroke)
        if family == "rounded-rect":
            fit = refine_radius(canvas, fit, sigma, tolerance)
        else:
            fit = primitives.derive(fit, tolerance)
        if stroke is not None:
            fit = refine_stroke(canvas, fit, sigma)
        clean = canvas.clean(fit)
        score = replace.soft_iou(canvas.alpha, canvas.degrade(clean, sigma))
        if best is None or score > best[2]:
            best = (fit, clean, score)
    return best


def measure(canvas: Canvas, m: dict, tolerance: float, stroke: float | None = None,
            agreements: tuple = ()) -> dict:
    """Everything a decision needs, rendered once — JSON-shaped, so the eval stores it and re-decides.

    Only `primitives.FITTED` is fitted — two families, because the other three ARE those two at
    particular parameters. The sigma is estimated from the better-fitting family at zero blur, never
    from the caller's name, so how the candidates are degraded does not depend on what the asset was
    called. Agreement is stored as raw IoUs so `equivalent` can be swept without re-rendering, and
    radius resolution once per agreement in `agreements`.

    With `stroke` (harness:RM-0679) every fit carries a stroke width, and `fixed` holds each
    family's margin against its own geometry FILLED — the adversary a stroked verdict must beat.
    """
    alpha = canvas.alpha
    crude_fits = {f: primitives.fit_family(f, m, stroke=stroke) for f in primitives.FITTED}
    crude = {f: replace.soft_iou(alpha, canvas.degrade(canvas.clean(fit), 0.0))
             for f, fit in crude_fits.items()}
    sigma = canvas.sigma_for(crude_fits[max(crude, key=crude.get)])

    best = {f: best_fit(canvas, f, m, sigma, tolerance, stroke) for f in primitives.FITTED}
    fits_by_family = {f: b[0] for f, b in best.items()}
    degraded = {f: canvas.degrade(b[1], sigma) for f, b in best.items()}
    full = {f: b[1].resize((canvas.width, canvas.height), Image.BOX).tobytes() for f, b in best.items()}
    fitted = primitives.FITTED
    fixed, hole_fit = {}, {}
    if stroke is not None:
        # The hole the band encloses must be the shape the band implies. `concentric` reads only the
        # hole's box, and a glyph centred in a tile has a concentric box — measured, a gear on a dark
        # square keyed as a centred cut-out and was accepted as a stroked rect four times over.
        hole = bytes(max(0, f - a) for f, a in zip(primitives.fill_holes(alpha, canvas.width, canvas.height), alpha))
        for f in fitted:
            solid = canvas.degrade(canvas.clean(primitives.filled(fits_by_family[f])), sigma)
            fixed[f] = replace.pair_margin(alpha, degraded[f], solid)
            hole_fit[f] = replace.soft_iou(hole, bytes(max(0, s - b) for s, b in zip(solid, degraded[f])))
    rival = rename_rival(canvas, fits_by_family["rounded-rect"], sigma, tolerance)
    rename = None if rival is None else {
        "name": rival["family"],
        "pair": replace.pair_margin(alpha, degraded["rounded-rect"], canvas.degrade(canvas.clean(rival), sigma))}
    return {
        "sigma": sigma,
        "fits": {f: b[2] for f, b in best.items()},
        "agreement": {f"{a}|{b}": replace.soft_iou(full[a], full[b])
                      for i, a in enumerate(fitted) for b in fitted[i + 1:]},
        "pairs": {f"{a}|{b}": replace.pair_margin(alpha, degraded[a], degraded[b])
                  for a in fitted for b in fitted if a != b},
        "fixed": fixed,
        "hole_fit": hole_fit,
        "rename": rename,
        # The name each fitted family carries, read off the shape that was actually scored.
        "derived": {f: fit["family"] for f, fit in fits_by_family.items()},
        "resolved": {str(a): radius_is_resolved(canvas, fits_by_family["rounded-rect"], sigma, tolerance, a)
                     for a in agreements},
        "params": {f: fit["params"] for f, fit in fits_by_family.items()},
    }


def verdict_from(measured: dict, params: dict) -> dict:
    """The shipped decision over a `measure` record — the one the eval re-runs, never a copy of it."""
    fits = measured["fits"]
    leader = max(fits, key=lambda f: (fits[f], -primitives.PARAM_COUNT[f]))

    def agree(a: str, b: str) -> float:
        return measured["agreement"].get(f"{a}|{b}", measured["agreement"].get(f"{b}|{a}", 0.0))

    ties = {f for f in fits if f != leader and agree(leader, f) >= params["equivalent"]}
    chosen = primitives.select(fits, ties)
    pairs = {f: tuple(measured["pairs"][f"{chosen}|{f}"]) for f in fits if f != chosen}
    stroked = bool(measured.get("fixed"))
    fixed = {"filled": tuple(measured["fixed"][chosen])} if stroked else {}
    if stroked and chosen == "rounded-rect" and measured.get("rename"):
        # The radius that would rename a BAND is an adversary like any other (`rename_rival`). Only
        # a band: a filled corner is read off a solid area, a band's off a thin arc the blur has
        # already half-erased. Measured on the eval split, applying it to filled shapes too cost 30
        # of 147 correct ladder acceptances and removed no wrong one — there were none to remove.
        fixed[f"radius:{measured['rename']['name']}"] = tuple(measured["rename"]["pair"])
    # A band's soft IoU is not comparable with a filled shape's: the same edge noise is spread over
    # far less area, so the right geometry at the right width scored 0.77-0.85 at 40 px where a
    # filled shape scores above 0.9. A stroked verdict clears its own calibrated bar; the filled
    # bar is unchanged, and the adversaries — the other family and the filled shape — still decide.
    rule = {**params, "bar": params["stroke_bar"]} if stroked else params
    verdict = primitives.decide(fits, pairs, ties, rule, names=measured["derived"], fixed=fixed)
    verdict["stroked"] = stroked
    if verdict["fitted"] == "rounded-rect" and not measured["resolved"][str(params["radius_resolved"])]:
        verdict.update(accepted=False, reason="radius")
    if stroked and verdict["accepted"] and measured["hole_fit"][chosen] < params["bar"]:
        # The filled `bar`, reused: the hole is a filled region, and asks the filled question.
        verdict.update(accepted=False, reason="hole-shape")
    # harness:RM-0678: a composite is accepted only when its backplate is AND its interior traced
    # and matched on its own. The refusal names the region, never merely the tile.
    region = measured.get("interior")
    verdict["composite"] = region is not None
    if region is not None and verdict["accepted"]:
        if region["reason"]:
            verdict.update(accepted=False, reason=f"composite-interior:{region['reason']}")
        elif region["fit"] < params["interior_bar"]:
            verdict.update(accepted=False, reason="composite-interior:fit")
        verdict["interior_fit"] = region["fit"]
    return verdict


def decided(measured: dict, params: dict, family: str | None = None) -> dict:
    """The verdict over a measurement, with the winner's parameters and a caller's named family."""
    verdict = verdict_from(measured, params)
    verdict["sigma"] = measured["sigma"]
    verdict["fits"] = {f: round(v, 4) for f, v in sorted(measured["fits"].items())}
    verdict["params"] = measured["params"][verdict["fitted"]]
    if family and family != "auto" and verdict["family"] != family:
        verdict.update(accepted=False, reason="named", named=family)
    return verdict


def source_quality(image: str, crop: str | None, mono: bool) -> dict:
    """`quality.assess` on the cropped source — and unlike `--replace`, this route obeys it.

    `--replace` runs ahead of the check on purpose: a 12 px JPEG'd Facebook "f" fails source-quality
    and a library icon is exactly the right answer for it, because the truth lives outside the
    source. A primitive has no external truth — the source IS the evidence — so a source whose own
    noise decides its silhouette cannot support the claim "this shape is what the image shows".
    Measured: the `computer-icon.destroyed` fixture degraded to 16 px is a solid blob that fits
    `rect` at 0.898 with hull and bbox fill both exactly 1.000. No silhouette predicate separates
    that from a real 16 px rect, because at the pixels there is nothing left to separate.
    """
    img = prep._open(image, crop)
    return quality.assess(img.tobytes(), *img.size, mono=mono)


def keyed_reading(image: str, crop: str | None, bg: str, mono: bool) -> tuple[bytes, int, int, tuple | None]:
    """(alpha, width, height, composite), keying exactly as the `--auto` route keys it.

    `composite` is `replace.knockout`'s answer — (plate alpha, plate colour, second colour), or None
    when the ink holds one flat colour. `replace` reads it to find the hole in a knockout tile; here
    it means something is drawn ON the shape: a backplate plus an interior (harness:RM-0678).
    """
    shape = autogrid.derive_prep(mono, None)
    keyed, _ = prep.keyed_source(image, crop, bg, shape["key"], shape["matte"], shape["tolerance"])
    width, height = keyed.size
    raw = prep._open(image, crop)
    ground = keying.border_background(raw.tobytes(), *raw.size) if bg == "auto" else prep._background(bg, raw)
    composite = replace.knockout(keyed.tobytes(), width, height, ground)
    if composite is None:
        # `knockout`'s share floor is the replace route's; a glyph under it is still drawn ON the
        # shape, and a plain primitive would ship without it (`primitives.second_colour`).
        composite = primitives.second_colour(keyed.tobytes(), width, height, replace.OPAQUE,
                                             replace.KNOCKOUT_MIN_DISTANCE, INTERIOR_MIN_PX)
    if composite is not None:
        composite = (*composite, primitives.third_colour_share(
            keyed.tobytes(), composite[1], composite[2], replace.OPAQUE, replace.KNOCKOUT_MIN_DISTANCE))
    return keyed.getchannel("A").tobytes(), width, height, composite


# A tile's interior is traced by vtracer, whose `filter_speckle` drops any region under six pixels —
# which at 12-16 px is the whole glyph. It is traced at this multiple and scaled back in the path's
# own transform, so the preset keeps its meaning and the component keeps the source's viewBox.
TRACE_SCALE = 4
# Fewer visible interior pixels than this is not a glyph that keying found; it is a blend.
INTERIOR_MIN_PX = 4


def trace_interior(ink: bytes, width: int, height: int) -> list[tuple[str, str]]:
    """The interior as (d, transform) paths: vtracer's binary trace, at TRACE_SCALE, scaled back."""
    import tempfile
    import xml.etree.ElementTree as ET

    import vtracer  # toolchain-only, like trace.py

    from . import trace

    grey = Image.frombytes("L", (width, height), bytes(255 - v for v in ink))
    big = grey.resize((width * TRACE_SCALE, height * TRACE_SCALE), Image.LANCZOS).convert("RGB")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "interior.png"), os.path.join(tmp, "interior.svg")
        big.save(src)
        vtracer.convert_image_to_svg_py(src, dst, **trace.options("icon", True, []))
        root = ET.parse(dst).getroot()
    scale_back = f"scale({1 / TRACE_SCALE:g})"
    return [(el.get("d", "").strip(), f"{scale_back} {el.get('transform', '')}".strip())
            for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "path" and el.get("d")]


def measure_interior(canvas: Canvas, ink: bytes, sigma: float) -> dict:
    """{"reason", "fit", "paths"} for the interior region: traced, rendered, degraded, compared.

    `reason` names what failed — `key` when keying left no glyph to trace, `trace` when the tracer
    returned nothing — so a refusal says which REGION it could not reproduce, not merely "the tile".
    """
    if sum(1 for v in ink if v >= primitives.VISIBLE) < INTERIOR_MIN_PX:
        return {"reason": "key", "fit": 0.0, "paths": []}
    paths = trace_interior(ink, canvas.width, canvas.height)
    if not paths:
        return {"reason": "trace", "fit": 0.0, "paths": []}
    body = "".join(f'<path d="{d}" transform="{t}"/>' for d, t in paths)
    svg = f'<svg viewBox="0 0 {canvas.width} {canvas.height}">{body}</svg>'
    clean = _render_alpha(svg, canvas.width * SUPERSAMPLE, canvas.height * SUPERSAMPLE)
    return {"reason": None, "fit": replace.soft_iou(ink, canvas.degrade(clean, sigma)), "paths": paths}


def examine(image: str, crop: str | None, bg: str, mono: bool, params: dict, gamma: float,
            agreements: tuple) -> dict:
    """Source quality, keying, candidacy and measurement — the whole route short of the decision.

    The runner and the eval both call this, so the eval measures the pipeline that ships rather
    than a copy of it assembled beside it.
    """
    assessment = source_quality(image, crop, mono)
    if not assessment["pass"]:
        return {"candidate": False, "reason": "source-quality", "candidacy": {},
                "source_quality": assessment}
    alpha, width, height, composite = keyed_reading(image, crop, bg, mono)
    gate = primitives.candidate(alpha, width, height, params, composite=composite is not None)
    if not gate["ok"]:
        return {"candidate": False, "reason": gate["reason"], "candidacy": gate}
    stroke = gate["stroke"] if gate["stroked"] else None
    # A stroked shape is fitted to the outline its band draws; the canvas still holds the band.
    m = primitives.moments(primitives.fill_holes(alpha, width, height) if stroke else alpha, width, height)
    canvas = Canvas(alpha, width, height, params["sigmas"], gamma)
    scales = scale.load(os.path.join(SCRIPTS, "scales.json"))
    measured = measure(canvas, m, scales["snap_tolerance"], stroke, agreements)
    if composite is not None:
        plate, plate_colour, ink_colour, third = composite
        if third >= replace.KNOCKOUT_MIN_SHARE:
            # The same share that makes a second colour a knockout makes a third one a region.
            region = {"reason": "colours", "fit": 0.0, "paths": []}
        else:
            region = measure_interior(canvas, primitives.interior(alpha, plate), measured["sigma"])
        measured["interior"] = {**region, "plate": list(plate_colour), "ink": list(ink_colour),
                                "third": third}
    return {"candidate": True, "candidacy": gate, "canvas": canvas, **measured}


def keyed_alpha(image: str, crop: str | None, bg: str, mono: bool) -> tuple[bytes, int, int]:
    """`keyed_reading` without the colour reading, for callers that only need the silhouette."""
    alpha, width, height, _ = keyed_reading(image, crop, bg, mono)
    return alpha, width, height


def header_lines(verdict: dict, size: dict, radius: dict | None, stroke: dict | None = None,
                 interior: dict | None = None) -> list[str]:
    """The provenance comment: this shape was fitted and verified, not traced."""
    shape = f"stroked {verdict['family']}" if stroke is not None else verdict["family"]
    lines = [f"Fitted {shape} — verified against the other primitive families"
             + (" and its own filled shape" if stroke is not None else ""),
             f"(fit {verdict['fit']:.3f}, runner-up {verdict['runner_up']} at margin {verdict['margin']:.3f})."
             if verdict["runner_up"] else f"(fit {verdict['fit']:.3f}; every other family renders the same shape).",
             f"Size {size['measured']:.3g} px" + (f", snapped to the {size['step']} px step." if size["step"]
                                                  else ", matching no declared step.")]
    if radius is not None:
        lines.append(f"Corner radius {radius['measured']:.3g} px" +
                     (f", the '{radius['step']}' step." if radius["step"] is not None
                      else ", matching no declared step."))
    if stroke is not None:
        lines.append(f"Stroke width {stroke['measured']:.3g} px" +
                     (f", the {stroke['step']} px border step." if stroke["step"] is not None
                      else ", matching no declared border step."))
    if interior is not None:
        lines.append(f"Composite (harness:RM-0678): the interior is traced, not fitted — {len(interior['paths'])}"
                     f" path(s), matching the source at {interior['fit']:.3f}.")
    lines.append("image-to-component --primitive (ADR-0175). Not traced: edit the numbers, not a path.")
    return lines


def emit(canvas: Canvas, verdict: dict, args: argparse.Namespace, scales: dict,
         interior: dict | None = None) -> dict:
    """Write the primitive's SVG, TSX and compare sheet; returns what the record adds.

    With `interior` (harness:RM-0678) the document is the backplate in its own colour followed by
    the traced interior in the second one — one component, two flat fills.
    """
    fit = {"family": verdict["family"], "params": verdict["params"]}
    p = verdict["params"]
    width = p.get("width", 2 * p.get("rx", p.get("r", 0.0)))
    height = p.get("height", 2 * p.get("ry", p.get("r", 0.0)))
    size = scale.snap(max(width, height), scales["icon_px"], scales["snap_tolerance"])
    radius = None
    if verdict["family"] in ("rounded-rect", "pill"):
        radius = primitives.snap_radius(p["rx"], scales["radius_px"], scales["snap_tolerance"], min(width, height))
    stroke = None
    if "stroke_width" in p:
        stroke = scale.snap(p["stroke_width"], scales["border_px"], scales["snap_tolerance"])

    def rounded(snapped):
        return None if snapped is None else {k: round(v, 3) if isinstance(v, float) else v
                                             for k, v in snapped.items()}
    record = {"size": rounded(size), "radius": rounded(radius), "stroke": rounded(stroke)}

    if radius is not None:
        # DEC-0181's rule, applied to radius: a value that matched a step IS that step; one that
        # matched none is emitted as measured, and the record says so.
        fit = {"family": fit["family"], "params": {**fit["params"], "rx": radius["value"]}}
    if stroke is not None:
        # The same rule for the band, against `border_px`.
        fit = {"family": fit["family"], "params": {**fit["params"], "stroke_width": stroke["value"]}}
    if interior is not None:
        svg = primitives.composite_svg(fit, canvas.view_box, interior["paths"], interior["plate"],
                                       interior["ink"])
    else:
        svg = primitives.svg(fit, canvas.view_box)
    findings = [f.code for f in svgcheck.check(svg, args.kind)]
    if findings:
        return {**record, "refused": "check:" + ",".join(findings)}
    color_mode = "currentColor" if args.mono else "original"
    tsx = svg2tsx.convert(svg, args.name, color_mode, header=header_lines(verdict, size, radius, stroke, interior),
                          size=size["value"])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, f"{args.name}.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg + "\n")
    with open(os.path.join(args.out, f"{args.name}.tsx"), "w", encoding="utf-8") as fh:
        fh.write(tsx)
    _compare_sheet(canvas, svg, verdict["sigma"]).save(os.path.join(args.out, f"{args.name}.compare.png"))
    return record


def _compare_sheet(canvas: Canvas, svg: str, sigma: float) -> Image.Image:
    def panel(alpha: bytes) -> Image.Image:
        img = Image.new("RGBA", (canvas.width, canvas.height), (255, 255, 255, 255))
        img.putalpha(Image.frombytes("L", (canvas.width, canvas.height), alpha))
        k = max(1, -(-SHEET_PX // canvas.height))
        return img.resize((canvas.width * k, canvas.height * k), Image.NEAREST)
    rendered = _render_alpha(svg, canvas.width * SUPERSAMPLE, canvas.height * SUPERSAMPLE)
    return sheet(panel(canvas.alpha), panel(canvas.degrade(rendered, sigma)))


def run(args: argparse.Namespace) -> tuple[int, dict]:
    params = primitives.load_params(os.path.join(SCRIPTS, "primitives.json"))
    scales = scale.load(os.path.join(SCRIPTS, "scales.json"))
    seen = examine(args.image, args.crop, args.bg, args.mono, params,
                   keying.COVERAGE_GAMMA if args.mono else 1.0, (params["radius_resolved"],))
    if not seen["candidate"]:
        return 4, {"accepted": False, **{k: v for k, v in seen.items() if k != "candidate"}}
    canvas = seen["canvas"]
    verdict = {**decided(seen, params, args.family), "candidacy": seen["candidacy"]}
    if not verdict["accepted"]:
        return 4, verdict
    if verdict["composite"] and args.mono:
        # One currentColor for a plate AND the glyph drawn on it paints the glyph out of existence.
        return 4, {**verdict, "accepted": False, "reason": "composite-interior:mono"}
    if args.out:
        record = emit(canvas, verdict, args, scales, seen.get("interior"))
        verdict.update(record)
        if record.get("refused"):
            return 4, {**verdict, "accepted": False, "reason": record["refused"]}
    return 0, verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primitives_run", description=__doc__.splitlines()[0])
    parser.add_argument("image")
    parser.add_argument("--report", required=True)
    parser.add_argument("--family", default="auto", choices=("auto",) + primitives.FAMILIES)
    parser.add_argument("--crop")
    parser.add_argument("--bg", default="auto")
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--kind", default="icon", choices=sorted(svgcheck.BUDGETS))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.out and not args.name:
        print("primitives_run: --out needs --name", file=sys.stderr)
        return 2
    try:
        rc, report = run(args)
    except prep.NothingLeft:
        rc, report = 4, {"accepted": False, "reason": "nothing-left-after-keying"}
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"primitives_run: {exc}", file=sys.stderr)
        return 2
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    if rc == 0:
        print(f"primitives_run: fitted {report['family']} (fit {report['fit']:.3f}, runner-up "
              f"{report['runner_up']} at margin {report['margin']})", file=sys.stderr)
    else:
        print(f"primitives_run: no primitive ({report.get('reason')}; nearest {report.get('family')})",
              file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
