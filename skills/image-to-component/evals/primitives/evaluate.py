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
# How equal the four margins between a band's outer box and its hole must be (harness:RM-0679).
# 1.0 would refuse every real ring — a blurred JPEG band is never pixel-exact on all four sides.
SWEEP_CONCENTRIC = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


# Candidacy is measured with the floors OFF, so `hull_fill` and `bbox_fill` are swept from the
# stored numbers exactly as `bar` and `margin` are. They are the floors the negatives actually bound
# — every product glyph refuses there and never reaches a family decision — so leaving them out of
# the sweep would call the eval calibrated while its main defence was a guess. Structural refusals
# (empty, multi-component, a hole) are not thresholds and short-circuit here as they do in the skill.
# `concentric` 0.0 admits every single-hole source to measurement, so the floor is swept from the
# stored reading exactly as the other floors are (harness:RM-0679). Two or more holes still refuse
# structurally: that has no stroke reading at all.
NO_FLOORS = {"hull_fill": 0.0, "bbox_fill": 0.0, "symmetry": 0.0, "min_px": 0, "concentric": 0.0,
             "interior_bar": 0.0}
REFUSED = {"accepted": False, "reason": "floor", "family": None, "ties": []}
# The sets drawn down the size ladder, reported per rung.
RUNG_SETS = ("ladder", "stroked", "composite")


def measure_one(path: str, params: dict, mono: bool = True) -> dict:
    """Everything a later decision needs, rendered once, by the runner's own `examine`.

    Radius resolution is stored per agreement in the sweep, because that is the parameter it turns on.
    """
    seen = primitives_run.examine(path, None, "auto", mono, {**params, **NO_FLOORS}, 1.0,
                                  tuple(SWEEP_RADIUS_RESOLVED))
    seen.pop("canvas", None)
    seen.pop("source_quality", None)
    return seen


def redecide(row: dict, params: dict, apply_floors: bool = True) -> dict:
    """The shipped rule, re-run over stored measurements. No renders, no second implementation."""
    if not row["candidate"]:
        return {"accepted": False, "reason": row["reason"], "family": None, "ties": []}
    if apply_floors:
        refusal = floor_refusal(row, params)
        if refusal:
            return refusal
    return primitives_run.verdict_from(row, params)


def floor_refusal(row: dict, params: dict) -> dict | None:
    """The candidacy floors, applied to the stored numbers. None when every one passes."""
    gate = row["candidacy"]
    if gate.get("stroked") and gate.get("concentric", 0.0) < params["concentric"]:
        return {"accepted": False, "reason": "hole", "family": None, "ties": []}
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
    # A ring accepted as a filled disc, a disc as a ring, or a tile shipped without the glyph drawn
    # on it, is the wrong shape whatever its family.
    if bool(verdict.get("stroked")) != bool(row.get("stroked")):
        return "WRONG"
    if bool(verdict.get("composite")) != bool(row.get("composite")):
        return "WRONG"
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
                # A composite is a two-colour asset, so its caller runs in original colour mode —
                # `--mono` refuses a composite outright. The flag is the caller's, not a label.
                measured = measure_one(path, params, mono=not row.get("composite"))
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
        if row["set"] in RUNG_SETS and row["px"] is not None:
            key = (row["set"], row["px"], outcome)
            by_rung[key] = by_rung.get(key, 0) + 1
    for (name, px, outcome), count in sorted(by_rung.items()):
        print(f"{name}\t{px}\t{outcome}\t{count}")

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


# Stage 1 closes the band admission, so the shared parameters are calibrated on exactly the
# population batch 2 calibrated them on — every hole refuses, whatever its concentricity.
CLOSED = 2.0
SWEEP_STROKE_BAR = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85]
# The interior's own match against the traced glyph (harness:RM-0678).
SWEEP_INTERIOR_BAR = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def calibrate_decomposition(rows: list[dict], shared: dict) -> dict:
    """Stage 2: `concentric`, `stroke_bar` (harness:RM-0679) and `interior_bar` (harness:RM-0678),
    with every shared parameter held.

    Two stages, not one product, and on purpose. The two new parameters only ever decide a row whose
    candidacy read a band, and the shared sweep is already 4 x 10^6 floor combinations; multiplying
    it by 36 turns a two-minute calibration into an hour to learn nothing the sequential one cannot.
    The rule is stage 1's: among the settings with zero wrong acceptances on the WHOLE calibrate
    split — negatives included, since a letterform's counter is exactly what `concentric` refuses —
    the best correct count, then the strictest.
    """
    clean = []
    for conc in SWEEP_CONCENTRIC:
        for stroke_bar in SWEEP_STROKE_BAR:
            for interior_bar in SWEEP_INTERIOR_BAR:
                params = {**shared, "concentric": conc, "stroke_bar": stroke_bar,
                          "interior_bar": interior_bar}
                table, _ = _counts(rows, params)
                if any(outcome == "WRONG" for (_, outcome) in table):
                    continue
                correct = sum(n for (_, outcome), n in table.items() if outcome == "correct")
                clean.append((correct, params))
    if not clean:
        raise SystemExit("primitives-eval: no stroke setting reaches zero wrong acceptances")
    best = max(c for c, _ in clean)
    return max((p for c, p in clean if c == best),
               key=lambda p: (p["concentric"], p["stroke_bar"], p["interior_bar"]))


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
                                "min_weight": min_weight, "radius_resolved": resolved_at,
                                "concentric": CLOSED, "interior_bar": CLOSED}
                    # A floor can only turn an acceptance into a refusal, so each row's outcome is
                    # computed once and the floors are a filter over four stored scalars. The WRONG
                    # list is a handful of rows, so most floor combinations are rejected on it
                    # before the correct count is ever taken — the full product was 1.2e9 row-tests
                    # and did not finish in twenty minutes.
                    gates = {"correct": [], "WRONG": []}
                    for row in rows:
                        outcome = classify(row, redecide(row, decision, apply_floors=False))
                        # Stage 1 admits no band and no interior, so neither row can count here.
                        if outcome in gates and not row["candidacy"].get("stroked") and not row.get("interior"):
                            g = row["candidacy"]
                            # A filled row has no band, so no concentric floor can refuse it.
                            concentric = g.get("concentric", 0.0) if g.get("stroked") else 1.0
                            gates[outcome].append((g.get("hull_fill", 0.0), g.get("bbox_fill", 0.0),
                                                   g.get("symmetry", 0.0), g.get("extent", 0.0),
                                                   concentric))

                    def passes(gate: tuple, floors: tuple) -> bool:
                        return all(value >= floor for value, floor in zip(gate, floors))
                    for hull in SWEEP_HULL:
                        for bbox in SWEEP_BBOX:
                            for sym in SWEEP_SYMMETRY:
                                for min_px in SWEEP_MIN_PX:
                                    # Stage 1 already left every band out of `gates`, so the
                                    # concentric floor has nothing to decide here.
                                    floors = (hull, bbox, sym, min_px, 0.0)
                                    if any(passes(g, floors) for g in gates["WRONG"]):
                                        continue
                                    correct = sum(1 for g in gates["correct"] if passes(g, floors))
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
    chosen = calibrate_decomposition(rows, chosen)

    _, detail = _counts(rows, chosen)
    margins = [v["margin"] for _, v, o in detail if o == "correct" and v.get("margin") is not None]
    weights = [v["weight"] for _, v, o in detail if o == "correct" and v.get("weight") is not None]
    fits = [v["fit"] for _, v, o in detail if o == "correct"]
    print(json.dumps({k: chosen[k] for k in ("bar", "margin", "min_weight", "equivalent",
                                            "radius_resolved", "hull_fill", "bbox_fill",
                                            "symmetry", "min_px", "concentric", "stroke_bar",
                                            "interior_bar")},
                     indent=2))
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
