"""Are five family names separable below 10 px at all? An oracle bound, not a verifier (harness:RM-0680).

    separability.py <src-dir> [--split calibrate|eval] [--rungs 8,10,12,16]

`<src-dir>` is what `make_sources.py` wrote (`run.sh` leaves it at `<out>/.work/src`).

The shipped verifier refuses every source under `min_px` 10, and 98 of the eval split's 173 ladder
refusals are that one floor. Lowering the floor to find out would be moving a threshold to raise a
number, which the item forbids. This asks the prior question instead: **does the source carry the
distinction at all?**

The oracle is told everything the verifier has to estimate — the family the source was drawn as,
its exact box, radius and position, and the exact blur it was degraded with — and is given a
generous search for the best-fitting shape of every OTHER name. It is the best any verifier reading
these pixels could do. A source is separable when the true shape beats that best rival by the
shipped `margin`, on at least the shipped `min_weight` pixels of disagreement: the acceptance rule
the verifier applies, fed perfect parameters. Where the oracle cannot separate a rung, no change to
the verifier can, and `min_px` is a floor on the information rather than on the verifier.

Rivals that render the same pixels as the truth — agreement at or above `equivalent` — are the same
shape at this size (a 4 px corner on an 8 px square IS its square): ties, exactly as `decide` treats
them, and never adversaries.

Needs resvg-py and Pillow; run through `run.sh`'s toolchain. Writes nothing; prints a TSV.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts import primitives, primitives_run, replace  # noqa: E402

# The rival search. Deliberately wider than the verifier's own: an oracle that searched less than
# the verifier would under-state what a rival can reach and over-state separability.
BOX_STEPS = (-1.0, -0.5, 0.0, 0.5, 1.0)
RADIUS_FRACTIONS = (0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0)


def _truth(row: dict, cx: float, cy: float) -> dict:
    """The drawn shape at its exact size, centred where the keyed source's ink is.

    The size and radius come from the manifest; the position cannot, because keying crops the
    canvas — a 28 px source keys to 20 x 28 — so the centre is the keyed alpha's soft centroid,
    which a symmetric shape puts at its own centre whatever the blur.
    """
    w, h = row["w"], row["h"]
    x, y = cx - w / 2, cy - h / 2
    family = row["truth"]
    if family in ("circle", "ellipse"):
        return {"family": "ellipse", "params": {"cx": x + w / 2, "cy": y + h / 2, "rx": w / 2, "ry": h / 2}}
    return {"family": "rounded-rect", "params": {"x": x, "y": y, "width": w, "height": h,
                                                 "rx": min(row["radius"], w / 2, h / 2)}}


def _rivals(truth: dict, tolerance: float):
    """Every shape of the OTHER fitted family near the truth's box, each with the name it carries."""
    p = truth["params"]
    if "width" in p:
        cx, cy, w, h = p["x"] + p["width"] / 2, p["y"] + p["height"] / 2, p["width"], p["height"]
    else:
        cx, cy, w, h = p["cx"], p["cy"], 2 * p["rx"], 2 * p["ry"]
    for dw in BOX_STEPS:
        for dh in BOX_STEPS:
            bw, bh = w + dw, h + dh
            if bw < 1 or bh < 1:
                continue
            if truth["family"] == "rounded-rect":
                yield primitives.derive({"family": "ellipse", "params": {
                    "cx": cx, "cy": cy, "rx": bw / 2, "ry": bh / 2}}, tolerance)
                continue
            for f in RADIUS_FRACTIONS:
                yield primitives.derive({"family": "rounded-rect", "params": {
                    "x": cx - bw / 2, "y": cy - bh / 2, "width": bw, "height": bh,
                    "rx": f * min(bw, bh) / 2}}, tolerance)


def judge_one(path: str, row: dict, params: dict, tolerance: float) -> dict:
    """The verifier's two questions, asked with perfect parameters.

    1. **Family** — does the source side with the true shape over the best shape of the other fitted
       family, by `margin` on at least `min_weight` pixels? Rivals that render the same pixels as
       the truth (above `equivalent`) tie with it and are not adversaries, exactly as in `decide`.
    2. **Name** — for a rounded box, does the true radius render differently, above
       `radius_resolved`, from the two radii that would rename it? `radius_is_resolved`'s question.
    """
    alpha, width, height, _ = primitives_run.keyed_reading(path, None, "auto", True)
    canvas = primitives_run.Canvas(alpha, width, height, params["sigmas"], 1.0)
    sigma = row["sigma"]
    m = primitives.moments(alpha, width, height)
    raw = _truth(row, m["cx"], m["cy"])
    truth = primitives.derive(raw, tolerance)
    truth_clean = canvas.clean(truth)
    truth_deg = canvas.degrade(truth_clean, sigma)
    truth_full = truth_clean.resize((width, height), primitives_run.Image.BOX).tobytes()

    best = None
    for rival in _rivals(raw, tolerance):
        clean = canvas.clean(rival)
        if replace.soft_iou(truth_full, clean.resize((width, height), primitives_run.Image.BOX).tobytes()) \
                >= params["equivalent"]:
            continue
        degraded = canvas.degrade(clean, sigma)
        score = replace.soft_iou(alpha, degraded)
        if best is None or score > best[0]:
            best = (score, rival, degraded)
    t, weight = replace.pair_margin(alpha, truth_deg, best[2]) if best else (1.0, float("inf"))
    got = {"rival": best[1]["family"] if best else None, "t": t, "weight": weight,
           "truth_fit": replace.soft_iou(alpha, truth_deg), "rival_fit": best[0] if best else None}
    if weight < params["min_weight"]:
        return {**got, "outcome": "family:too-few-pixels"}
    if t < params["margin"]:
        return {**got, "outcome": "family:rival-fits"}
    if raw["family"] == "rounded-rect" and not primitives_run.radius_is_resolved(
            canvas, {"family": truth["family"], "params": {**raw["params"], **truth["params"]}},
            sigma, tolerance, params["radius_resolved"]):
        return {**got, "outcome": "name:unresolved"}
    return {**got, "outcome": "separable"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="separability", description=__doc__.splitlines()[0])
    parser.add_argument("src")
    parser.add_argument("--split", default="calibrate", choices=("calibrate", "eval"))
    parser.add_argument("--rungs", default="8,10,12,16")
    args = parser.parse_args(argv)
    skill = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    params = primitives.load_params(os.path.join(skill, "scripts", "primitives.json"))
    tolerance = json.load(open(os.path.join(skill, "scripts", "scales.json"), encoding="utf-8"))["snap_tolerance"]
    rungs = {int(r) for r in args.rungs.split(",")}
    with open(os.path.join(args.src, "manifest.jsonl"), encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    rows = [r for r in rows if r["set"] == "ladder" and r["split"] == args.split and r["px"] in rungs]

    table: dict[tuple, int] = {}
    print("file\tpx\ttruth\toutcome\trival\tt\tweight\ttruth_fit\trival_fit")
    for row in rows:
        try:
            got = judge_one(os.path.join(args.src, row["file"]), row, params, tolerance)
        except primitives_run.prep.NothingLeft:
            got = {"outcome": "nothing-keyed", "rival": None, "t": None, "weight": None}
        key = (row["px"], got["outcome"])
        table[key] = table.get(key, 0) + 1
        print("\t".join(str(v) for v in (row["file"], row["px"], row["truth"], got["outcome"], got["rival"],
                                          *(round(got[k], 3) if isinstance(got.get(k), float) else got.get(k)
                                            for k in ("t", "weight", "truth_fit", "rival_fit")))))
    for (px, outcome), n in sorted(table.items()):
        print(f"separability: {args.split} {px} px {outcome}: {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
