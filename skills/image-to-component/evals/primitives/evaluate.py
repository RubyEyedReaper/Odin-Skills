"""Measure once, score many times: the primitives eval's three verbs.

    evaluate.py measure <src-dir> <raw.jsonl>
    evaluate.py score <raw.jsonl> <primitives.json> --split eval [--tsv <per-source.tsv>]
    evaluate.py calibrate <raw.jsonl>                   # reads the CALIBRATE split only

`measure` renders every family for every source once and stores the fits, the pair margins, the
equivalence ties and the candidacy record. `score` and `calibrate` then re-decide through
`primitives.decide` — the verifier's own rule, never a re-implementation of it — so a parameter
sweep costs no renders and the scored rule is the shipped one.

Three counts, always together, because the expensive failure is the one that looks right:

| Set | correct | WRONG | missed |
|---|---|---|---|
| ladder | the decided family is the truth, or ties with it | any other accepted family | refused |
| confusers | same | same | refused — the intended answer at these sizes |
| negatives | — | **any** acceptance | refused |

Any WRONG anywhere makes `score` exit 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts import primitives, primitives_run, replace, scale  # noqa: E402

SWEEP_BAR = [0.3, 0.45, 0.55, 0.65, 0.7, 0.75, 0.85]
SWEEP_MARGIN = [0.08, 0.12, 0.16, 0.2, 0.3, 0.4, 0.5]
SWEEP_MIN_WEIGHT = [0, 4, 12, 24]
# Recall against the margin has no knee on this split — 144 correct at 0.0, 140 at 0.08, 136 at 0.2,
# about one source per step — so the margin is a judgement, not a measurement, and "the value that
# costs no recall" lands on 0.0, which switches the adversary test off entirely and contradicts the
# acceptance rule ADR-0175 states. The floor is the replace route's own calibrated margin: where the
# evidence does not discriminate, the tree's existing number wins over a new invented one.
MARGIN_FLOOR = 0.08
# A tie means "these two render the same shape", and it is what lets the FEWEST-parameter family be
# emitted instead of the best-fitting one. At 0.90 a 24 px square and the same square with a 6 px
# radius tie, and the squircle ships as a square — measured on a real run, and invisible in the
# counts because `classify` reads a tie as correct. The floor keeps a tie near-identical, so the two
# readings of "correct" coincide instead of one excusing the other.
SWEEP_EQUIVALENT = [0.95, 0.97, 0.99]
SWEEP_HULL = [0.80, 0.85, 0.88, 0.90, 0.92, 0.94]
SWEEP_BBOX = [0.45, 0.5, 0.55, 0.6, 0.65, 0.7]
SWEEP_SYMMETRY = [0.0, 0.80, 0.85, 0.88, 0.90, 0.92, 0.94, 0.96]
SWEEP_MIN_PX = [0, 8, 10, 12, 14, 16, 20]
# The radius-resolution agreement runs OPPOSITE to the family tie: looser means more
# radii called unresolved, which is the SAFE direction. Its own parameter for that reason.
SWEEP_RADIUS_RESOLVED = [0.90, 0.95, 0.97, 0.99]


# Candidacy is measured with the floors OFF, so `hull_fill` and `bbox_fill` are swept from the
# stored numbers exactly as `bar` and `margin` are. They are the floors the negatives actually bound
# — every product glyph refuses there and never reaches a family decision — so leaving them out of
# the sweep would call the eval calibrated while its main defence was a guess. Structural refusals
# (empty, multi-component, a hole) are not thresholds and short-circuit here as they do in the skill.
NO_FLOORS = {"hull_fill": 0.0, "bbox_fill": 0.0, "symmetry": 0.0, "min_px": 0}
REFUSED = {"accepted": False, "reason": "floor", "family": None, "ties": []}


def measure_one(path: str, params: dict) -> dict:
    """Everything a later decision needs, rendered once. `equivalent` is stored as raw pair IoUs."""
    assessment = primitives_run.source_quality(path, None, True)
    if not assessment["pass"]:
        return {"candidate": False, "reason": "source-quality", "candidacy": {}}
    alpha, width, height, composite = primitives_run.keyed_reading(path, None, "auto", True)
    gate = primitives.candidate(alpha, width, height, NO_FLOORS, composite=composite)
    if not gate["ok"]:
        return {"candidate": False, "reason": gate["reason"], "candidacy": gate}
    m = primitives.moments(alpha, width, height)
    canvas = primitives_run.Canvas(alpha, width, height, params["sigmas"], 1.0)

    scales = scale.load(os.path.join(os.path.dirname(os.path.abspath(primitives.__file__)), "scales.json"))
    crude_fits = {f: primitives.fit_family(f, m) for f in primitives.FITTED}
    crude = {f: replace.soft_iou(alpha, canvas.degrade(canvas.clean(fit), 0.0))
             for f, fit in crude_fits.items()}
    sigma = canvas.sigma_for(crude_fits[max(crude, key=crude.get)])
    best = {f: primitives_run.best_fit(canvas, f, m, sigma, scales["snap_tolerance"])
            for f in primitives.FITTED}
    fits_by_family = {f: b[0] for f, b in best.items()}
    cleans = {f: b[1] for f, b in best.items()}
    degraded = {f: canvas.degrade(c, sigma) for f, c in cleans.items()}
    fits = {f: b[2] for f, b in best.items()}
    full = {f: c.resize((width, height), primitives_run.Image.BOX).tobytes() for f, c in cleans.items()}
    # Stored as IoUs rather than as booleans so `equivalent` itself can be swept without re-rendering.
    agreement = {f"{a}|{b}": replace.soft_iou(full[a], full[b])
                 for i, a in enumerate(primitives.FITTED) for b in primitives.FITTED[i + 1:]}
    pairs = {f"{a}|{b}": replace.pair_margin(alpha, degraded[a], degraded[b])
             for a in primitives.FITTED for b in primitives.FITTED if a != b}
    # The name each fitted family carries. `best_fit` derived it before rendering, so this is read
    # off the shape that was actually scored rather than computed a second time beside it.
    derived = {f: fit["family"] for f, fit in fits_by_family.items()}
    # Whether the winning radius is separable from the two that would rename the shape. Stored per
    # `equivalent` in the sweep, because that is the parameter it turns on.
    resolved = {str(a): primitives_run.radius_is_resolved(
        canvas, fits_by_family["rounded-rect"], sigma, scales["snap_tolerance"], a)
        for a in SWEEP_RADIUS_RESOLVED}
    return {"candidate": True, "sigma": sigma, "fits": fits, "agreement": agreement,
            "pairs": pairs, "candidacy": gate, "derived": derived, "resolved": resolved,
            "params": {f: fit["params"] for f, fit in fits_by_family.items()}}


def redecide(row: dict, params: dict, apply_floors: bool = True) -> dict:
    """The shipped rule, re-run over stored measurements. No renders, no second implementation."""
    if not row["candidate"]:
        return {"accepted": False, "reason": row["reason"], "family": None, "ties": []}
    if apply_floors:
        refusal = floor_refusal(row, params)
        if refusal:
            return refusal
    fits = row["fits"]
    leader = max(fits, key=lambda f: (fits[f], -primitives.PARAM_COUNT[f]))

    def agree(a: str, b: str) -> float:
        return row["agreement"].get(f"{a}|{b}", row["agreement"].get(f"{b}|{a}", 0.0))

    ties = {f for f in fits if f != leader and agree(leader, f) >= params["equivalent"]}
    chosen = primitives.select(fits, ties)
    pairs = {f: tuple(row["pairs"][f"{chosen}|{f}"]) for f in fits if f != chosen}
    verdict = primitives.decide(fits, pairs, ties, params, names=row["derived"])
    if verdict["fitted"] == "rounded-rect" and not row["resolved"][str(params["radius_resolved"])]:
        verdict.update(accepted=False, reason="radius")
    return verdict


def floor_refusal(row: dict, params: dict) -> dict | None:
    """The candidacy floors, applied to the stored numbers. None when both pass."""
    gate = row["candidacy"]
    if gate.get("hull_fill", 0.0) < params["hull_fill"]:
        return {"accepted": False, "reason": "convexity", "family": None, "ties": []}
    if gate.get("bbox_fill", 0.0) < params["bbox_fill"]:
        return {"accepted": False, "reason": "bbox-fill", "family": None, "ties": []}
    if gate.get("symmetry", 0.0) < params["symmetry"]:
        return {"accepted": False, "reason": "asymmetry", "family": None, "ties": []}
    if gate.get("extent", 0.0) < params["min_px"]:
        return {"accepted": False, "reason": "too-small", "family": None, "ties": []}
    return None


def classify(row: dict, verdict: dict) -> str:
    """correct | WRONG | missed, per the table in this module's docstring."""
    if row["set"] == "negatives":
        return "WRONG" if verdict["accepted"] else "refused"
    if not verdict["accepted"]:
        return "missed"
    if verdict["family"] == row["truth"] or row["truth"] in verdict.get("ties", []):
        return "correct"
    return "WRONG"


def cmd_measure(args: argparse.Namespace) -> int:
    skill = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    params = primitives.load_params(os.path.join(skill, "scripts", "primitives.json"))
    with open(os.path.join(args.src, "manifest.jsonl"), encoding="utf-8") as fh:
        manifest = [json.loads(line) for line in fh if line.strip()]
    with open(args.raw, "w", encoding="utf-8") as out:
        for n, row in enumerate(manifest, 1):
            path = row["file"] if os.path.isabs(row["file"]) else os.path.join(args.src, row["file"])
            try:
                measured = measure_one(path, params)
            except Exception as exc:  # a source that cannot be keyed is a refusal, recorded as one
                measured = {"candidate": False, "reason": f"error:{type(exc).__name__}", "candidacy": {}}
            out.write(json.dumps({**row, **measured}) + "\n")
            if n % 25 == 0:
                print(f"primitives-eval: measured {n}/{len(manifest)}", file=sys.stderr)
    return 0


def _counts(rows: list[dict], params: dict) -> tuple[dict, list[tuple]]:
    table: dict[tuple[str, str], int] = {}
    detail = []
    for row in rows:
        verdict = redecide(row, params)
        outcome = classify(row, verdict)
        table[(row["set"], outcome)] = table.get((row["set"], outcome), 0) + 1
        detail.append((row, verdict, outcome))
    return table, detail


def cmd_score(args: argparse.Namespace) -> int:
    params = primitives.load_params(args.params)
    with open(args.raw, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    rows = [r for r in rows if r["split"] == args.split]
    table, detail = _counts(rows, params)

    print("set\tpx\toutcome\tcount")
    for (name, outcome), count in sorted(table.items()):
        print(f"{name}\t-\t{outcome}\t{count}")
    by_rung: dict[tuple, int] = {}
    for row, _, outcome in detail:
        if row["set"] == "ladder":
            by_rung[(row["px"], outcome)] = by_rung.get((row["px"], outcome), 0) + 1
    for (px, outcome), count in sorted(by_rung.items()):
        print(f"ladder\t{px}\t{outcome}\t{count}")

    if args.tsv:
        with open(args.tsv, "w", encoding="utf-8") as fh:
            fh.write("file\tset\tpx\ttruth\toutcome\tdecided\taccepted\treason\tfit\trunner_up\tmargin\tweight\tties\n")
            for row, verdict, outcome in detail:
                fh.write("\t".join(str(v) for v in [
                    os.path.basename(row["file"]), row["set"], row["px"], row["truth"], outcome,
                    verdict.get("family"), verdict["accepted"], verdict["reason"],
                    round(verdict["fit"], 4) if verdict.get("fit") is not None else "",
                    verdict.get("runner_up"),
                    round(verdict["margin"], 4) if verdict.get("margin") is not None else "",
                    round(verdict["weight"], 2) if verdict.get("weight") is not None else "",
                    ",".join(verdict.get("ties", [])),
                ]) + "\n")

    wrong = sum(count for (_, outcome), count in table.items() if outcome == "WRONG")
    print(f"primitives-eval: wrong acceptances on the {args.split} split: {wrong}", file=sys.stderr)
    return 1 if wrong else 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Sweep on the calibrate split only, and take the TIGHTEST setting that costs no recall.

    The replace eval calibrates the other way round — the loosest setting with no wrong naming —
    because there a wrong naming exists to bound from below. Here none does at any setting: the
    families are five, not thousands, and what keeps a glyph out is candidacy rather than the
    margin. Reading that as "0.0 margin is calibrated" would record the loosest value in the sweep
    as though evidence had chosen it. So the rule is the dual: among the settings that reach the
    best correct count with zero wrong acceptances, take the strictest, and report the worst margin
    any correct acceptance actually cleared — that number is the headroom, and it is measured.
    """
    with open(args.raw, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip() and json.loads(line)["split"] == "calibrate"]
    skill = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base = primitives.load_params(os.path.join(skill, "scripts", "primitives.json"))

    # The decision does not depend on the floors, so it is computed once per decision setting and
    # the floors are applied as a filter over the stored candidacy numbers — 36x fewer decisions.
    clean: list[tuple[int, dict]] = []
    for equivalent in SWEEP_EQUIVALENT:
        for bar in SWEEP_BAR:
            for margin in [m for m in SWEEP_MARGIN if m >= MARGIN_FLOOR]:
                for min_weight in SWEEP_MIN_WEIGHT:
                  for resolved_at in SWEEP_RADIUS_RESOLVED:
                    decision = {**base, "equivalent": equivalent, "bar": bar, "margin": margin,
                                "min_weight": min_weight, "radius_resolved": resolved_at}
                    # A floor can only turn an acceptance into a refusal, so each row's outcome is
                    # computed once and the floors are a filter over four stored scalars. The WRONG
                    # list is a handful of rows, so most floor combinations are rejected on it
                    # before the correct count is ever taken — the full product was 1.2e9 row-tests
                    # and did not finish in twenty minutes.
                    gates = {"correct": [], "WRONG": []}
                    for row in rows:
                        outcome = classify(row, redecide(row, decision, apply_floors=False))
                        if outcome in gates:
                            g = row["candidacy"]
                            gates[outcome].append((g.get("hull_fill", 0.0), g.get("bbox_fill", 0.0),
                                                   g.get("symmetry", 0.0), g.get("extent", 0.0)))
                    for hull in SWEEP_HULL:
                        for bbox in SWEEP_BBOX:
                            for sym in SWEEP_SYMMETRY:
                                for min_px in SWEEP_MIN_PX:
                                    if any(h >= hull and b >= bbox and y >= sym and e >= min_px
                                           for h, b, y, e in gates["WRONG"]):
                                        continue
                                    correct = sum(1 for h, b, y, e in gates["correct"]
                                                  if h >= hull and b >= bbox and y >= sym and e >= min_px)
                                    clean.append((correct, {**decision, "hull_fill": hull,
                                                            "bbox_fill": bbox, "symmetry": sym,
                                                            "min_px": min_px}))
    if not clean:
        print("primitives-eval: no parameter set reaches zero wrong acceptances", file=sys.stderr)
        return 1

    best_correct = max(c for c, _ in clean)
    at_best = [p for c, p in clean if c == best_correct]
    chosen = max(at_best, key=lambda p: (p["min_px"], p["symmetry"], p["hull_fill"], p["bbox_fill"],
                                        p["bar"], p["margin"], p["min_weight"], p["equivalent"],
                                        -p["radius_resolved"]))

    _, detail = _counts(rows, chosen)
    margins = [v["margin"] for _, v, o in detail if o == "correct" and v.get("margin") is not None]
    weights = [v["weight"] for _, v, o in detail if o == "correct" and v.get("weight") is not None]
    fits = [v["fit"] for _, v, o in detail if o == "correct"]
    print(json.dumps({k: chosen[k] for k in ("bar", "margin", "min_weight", "equivalent",
                                            "radius_resolved", "hull_fill", "bbox_fill",
                                            "symmetry", "min_px")}, indent=2))
    print(f"\nzero wrong at {len(clean)} of the swept settings; best correct {best_correct} of "
          f"{len(rows)}, reached by {len(at_best)}; the strictest is above.", file=sys.stderr)
    print(f"headroom on the correct acceptances: worst margin {min(margins):.3f} (bar {chosen['margin']}), "
          f"worst fit {min(fits):.3f} (bar {chosen['bar']}), worst weight {min(weights):.2f} "
          f"(bar {chosen['min_weight']})", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("src")
    m.add_argument("raw")
    m.set_defaults(func=cmd_measure)
    s = sub.add_parser("score")
    s.add_argument("raw")
    s.add_argument("params")
    s.add_argument("--split", default="eval")
    s.add_argument("--tsv")
    s.set_defaults(func=cmd_score)
    c = sub.add_parser("calibrate")
    c.add_argument("raw")
    c.set_defaults(func=cmd_calibrate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
