"""Run the primitive route for one source: is this asset a container shape, and which one?

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py primitives_run`). Every decision is
stdlib (`primitives.py`, `scale.py`); this file only keys, renders and writes.

    primitives_run.py <image> --report primitive.json
                      [--family auto|rect|rounded-rect|circle|ellipse|pill]
                      [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--mono]
                      [--name Pascal --kind icon|logo --out dir]

Steps (ADR-0175, and DEC-0179's comparison reused unchanged):

1. Key the source once, the way `--auto` keys it for this colour mode.
2. Candidacy: `primitives.candidate` — one component, no interior hole, convex enough, fills its
   box. A ring, a knockout tile, a letterform and every glyph refuse here, cheaply.
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


def best_fit(canvas: Canvas, family: str, m: dict, sigma: float,
             tolerance: float) -> tuple[dict, "Image.Image", float]:
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
        fit = primitives.fit_family(family, primitives.scaled(m, step))
        if family == "rounded-rect":
            fit = refine_radius(canvas, fit, sigma, tolerance)
        else:
            fit = primitives.derive(fit, tolerance)
        clean = canvas.clean(fit)
        score = replace.soft_iou(canvas.alpha, canvas.degrade(clean, sigma))
        if best is None or score > best[2]:
            best = (fit, clean, score)
    return best


def judge(canvas: Canvas, m: dict, params: dict, tolerance: float, family: str | None = None) -> dict:
    """Fit, render, compare, decide, then read the winner's name off its parameters.

    Only `primitives.FITTED` is judged — two families, because the other three ARE those two at
    particular parameters. The sigma is estimated from the better-fitting family at zero blur, never
    from the caller's name, so how the candidates are degraded does not depend on what the asset was
    called.
    """
    crude_fits = {f: primitives.fit_family(f, m) for f in primitives.FITTED}
    crude = {f: replace.soft_iou(canvas.alpha, canvas.degrade(canvas.clean(fit), 0.0))
             for f, fit in crude_fits.items()}
    sigma = canvas.sigma_for(crude_fits[max(crude, key=crude.get)])

    best = {f: best_fit(canvas, f, m, sigma, tolerance) for f in primitives.FITTED}
    fits_by_family = {f: b[0] for f, b in best.items()}
    cleans = {f: b[1] for f, b in best.items()}
    degraded = {f: canvas.degrade(clean, sigma) for f, clean in cleans.items()}
    fits = {f: b[2] for f, b in best.items()}
    full = {f: clean.resize((canvas.width, canvas.height), Image.BOX).tobytes() for f, clean in cleans.items()}

    leader = max(fits, key=lambda f: (fits[f], -primitives.PARAM_COUNT[f]))
    ties = {f for f in fits if f != leader and replace.equivalent(full[leader], full[f], params["equivalent"])}
    chosen = primitives.select(fits, ties)
    pairs = {f: replace.pair_margin(canvas.alpha, degraded[chosen], degraded[f])
             for f in fits if f != chosen}

    names = {f: fit["family"] for f, fit in fits_by_family.items()}
    verdict = primitives.decide(fits, pairs, ties, params, names=names)
    verdict["sigma"] = sigma
    verdict["fits"] = {f: round(v, 4) for f, v in sorted(fits.items())}
    verdict["params"] = fits_by_family[verdict["fitted"]]["params"]
    if verdict["fitted"] == "rounded-rect" and not radius_is_resolved(
            canvas, fits_by_family["rounded-rect"], sigma, tolerance, params["radius_resolved"]):
        verdict.update(accepted=False, reason="radius")
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


def keyed_reading(image: str, crop: str | None, bg: str, mono: bool) -> tuple[bytes, int, int, bool]:
    """(alpha, width, height, composite), keying exactly as the `--auto` route keys it.

    `composite` is `replace.knockout`'s answer: the ink holds a second flat colour, so something is
    drawn ON this shape. `replace` reads that to find the hole in a knockout tile; here it means the
    asset is a figure on a ground rather than a whole container, and candidacy refuses it.
    """
    shape = autogrid.derive_prep(mono, None)
    keyed, _ = prep.keyed_source(image, crop, bg, shape["key"], shape["matte"], shape["tolerance"])
    width, height = keyed.size
    raw = prep._open(image, crop)
    ground = keying.border_background(raw.tobytes(), *raw.size) if bg == "auto" else prep._background(bg, raw)
    composite = replace.knockout(keyed.tobytes(), width, height, ground) is not None
    return keyed.getchannel("A").tobytes(), width, height, composite


def keyed_alpha(image: str, crop: str | None, bg: str, mono: bool) -> tuple[bytes, int, int]:
    """`keyed_reading` without the colour reading, for callers that only need the silhouette."""
    alpha, width, height, _ = keyed_reading(image, crop, bg, mono)
    return alpha, width, height


def header_lines(verdict: dict, size: dict, radius: dict | None) -> list[str]:
    """The provenance comment: this shape was fitted and verified, not traced."""
    lines = [f"Fitted {verdict['family']} — verified against the other primitive families",
             f"(fit {verdict['fit']:.3f}, runner-up {verdict['runner_up']} at margin {verdict['margin']:.3f})."
             if verdict["runner_up"] else f"(fit {verdict['fit']:.3f}; every other family renders the same shape).",
             f"Size {size['measured']:.3g} px" + (f", snapped to the {size['step']} px step." if size["step"]
                                                  else ", matching no declared step.")]
    if radius is not None:
        lines.append(f"Corner radius {radius['measured']:.3g} px" +
                     (f", the '{radius['step']}' step." if radius["step"] is not None
                      else ", matching no declared step."))
    lines.append("image-to-component --primitive (ADR-0175). Not traced: edit the numbers, not a path.")
    return lines


def emit(canvas: Canvas, verdict: dict, args: argparse.Namespace, scales: dict) -> dict:
    """Write the primitive's SVG, TSX and compare sheet; returns what the record adds."""
    fit = {"family": verdict["family"], "params": verdict["params"]}
    p = verdict["params"]
    width = p.get("width", 2 * p.get("rx", p.get("r", 0.0)))
    height = p.get("height", 2 * p.get("ry", p.get("r", 0.0)))
    size = scale.snap(max(width, height), scales["icon_px"], scales["snap_tolerance"])
    radius = None
    if verdict["family"] in ("rounded-rect", "pill"):
        radius = primitives.snap_radius(p["rx"], scales["radius_px"], scales["snap_tolerance"], min(width, height))
    record = {"size": {k: round(v, 3) if isinstance(v, float) else v for k, v in size.items()},
              "radius": None if radius is None
              else {k: round(v, 3) if isinstance(v, float) else v for k, v in radius.items()}}

    if radius is not None:
        # DEC-0181's rule, applied to radius: a value that matched a step IS that step; one that
        # matched none is emitted as measured, and the record says so.
        fit = {"family": fit["family"], "params": {**fit["params"], "rx": radius["value"]}}
    svg = primitives.svg(fit, canvas.view_box)
    findings = [f.code for f in svgcheck.check(svg, args.kind)]
    if findings:
        return {**record, "refused": "check:" + ",".join(findings)}
    color_mode = "currentColor" if args.mono else "original"
    tsx = svg2tsx.convert(svg, args.name, color_mode, header=header_lines(verdict, size, radius),
                          size=size["value"])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, f"{args.name}.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg + "\n")
    with open(os.path.join(args.out, f"{args.name}.tsx"), "w", encoding="utf-8") as fh:
        fh.write(tsx)
    _compare_sheet(canvas, fit, verdict["sigma"]).save(os.path.join(args.out, f"{args.name}.compare.png"))
    return record


def _compare_sheet(canvas: Canvas, fit: dict, sigma: float) -> Image.Image:
    def panel(alpha: bytes) -> Image.Image:
        img = Image.new("RGBA", (canvas.width, canvas.height), (255, 255, 255, 255))
        img.putalpha(Image.frombytes("L", (canvas.width, canvas.height), alpha))
        k = max(1, -(-SHEET_PX // canvas.height))
        return img.resize((canvas.width * k, canvas.height * k), Image.NEAREST)
    return sheet(panel(canvas.alpha), panel(canvas.degrade(canvas.clean(fit), sigma)))


def run(args: argparse.Namespace) -> tuple[int, dict]:
    params = primitives.load_params(os.path.join(SCRIPTS, "primitives.json"))
    scales = scale.load(os.path.join(SCRIPTS, "scales.json"))
    assessment = source_quality(args.image, args.crop, args.mono)
    if not assessment["pass"]:
        return 4, {"accepted": False, "reason": "source-quality", "source_quality": assessment}
    alpha, width, height, composite = keyed_reading(args.image, args.crop, args.bg, args.mono)

    gate = primitives.candidate(alpha, width, height, params, composite=composite)
    if not gate["ok"]:
        return 4, {"accepted": False, "reason": gate["reason"], "candidacy": gate}
    m = primitives.moments(alpha, width, height)
    canvas = Canvas(alpha, width, height, params["sigmas"],
                    keying.COVERAGE_GAMMA if args.mono else 1.0)
    verdict = {**judge(canvas, m, params, scales["snap_tolerance"], args.family), "candidacy": gate}
    if not verdict["accepted"]:
        return 4, verdict
    if args.out:
        record = emit(canvas, verdict, args, scales)
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
