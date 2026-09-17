"""Measure the replace verifier on the synthesised sources, score it with a params file, and calibrate one.

Needs resvg-py and Pillow and the library cache. Three subcommands:

    evaluate.py measure <sources-dir> <raw.jsonl>          # renders; slow, parallel, params-free
    evaluate.py score <raw.jsonl> <replace.json> [--split eval] [--tsv out.tsv]
    evaluate.py calibrate <raw.jsonl>                       # reads the calibrate split ONLY

`measure` records, per source and interpretation, every naming's fit and its pair margin against each
adversary, with the adversary's clean-render equivalence. Nothing in it depends on a threshold, so `score` and
`calibrate` re-decide from the record through `replace.decide_pairs` — the verifier's own rule, not a copy.

Namings per source: the truth (a ladder source only), each wrong name from the manifest, and auto.
Outcomes: a truth naming accepted is `correct`, refused `missed`; a wrong naming accepted is `WRONG`; auto
accepting the truth (or a render-equivalent of it) is `correct`, anything else accepted is `WRONG`.
A negative has no truth: every acceptance on it is `WRONG`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL)
from scripts import replace  # noqa: E402

PARAMS_DIR = os.path.join(SKILL, "scripts")
_worker = {}


def _init() -> None:
    from scripts import replace_run
    params = replace.load_params(os.path.join(PARAMS_DIR, "replace.json"))
    cache, pins, indexes = replace_run.open_libraries(None)
    _worker.update(rr=replace_run, params=params, cache=cache, pins=pins, indexes=indexes)


def _measure_one(job: tuple[str, dict]) -> dict:
    root, entry = job
    rr, params = _worker["rr"], _worker["params"]
    path = entry["path"] if os.path.isabs(entry["path"]) else os.path.join(root, entry["path"])
    renderer = rr.Renderer(_worker["cache"], _worker["pins"], _worker["indexes"], params["sigmas"], rr.gamma_for(entry["mono"]))
    try:
        sources, _, _ = rr.load_sources(path, None, "auto", entry["mono"])
    except Exception as exc:  # a source keying cannot read is recorded, never skipped silently
        return {**entry, "error": str(exc), "interpretations": []}
    names = ([entry["truth"]] if entry["truth"] else []) + entry["wrong_names"]
    out = []
    for src in sources:
        gathered = rr.gather(renderer, src, names, params)
        if not gathered:
            continue
        fits = gathered["fits"]
        top = max((r for r in gathered["pool"] if r in fits), key=lambda r: fits[r], default=None)
        record = {"kind": src.kind, "sigma": gathered["sigma"], "namings": {},
                  "extent": replace.ink_extent(src.alpha, src.width, src.height)}
        for ref in dict.fromkeys([n for n in names if n in fits] + ([top] if top else [])):
            reference = gathered["clean"][ref].tobytes()
            pairs = {}
            for other in gathered["degraded"]:
                if other == ref:
                    continue
                t, weight = replace.pair_margin(src.alpha, gathered["degraded"][ref], gathered["degraded"][other])
                pairs[other] = [round(t, 5), round(weight, 3),
                                round(replace.soft_iou(reference, gathered["clean"][other].tobytes()), 5)]
            record["namings"][ref] = {"fit": round(fits[ref], 5), "pairs": pairs}
        record["auto"] = top
        if entry["truth"] and top and top in record["namings"] and entry["truth"] in gathered["clean"]:
            record["auto_truth_iou"] = round(replace.soft_iou(gathered["clean"][top].tobytes(),
                                                              gathered["clean"][entry["truth"]].tobytes()), 5)
        out.append(record)
    return {**entry, "interpretations": out}


def measure(sources_dir: str, raw: str) -> int:
    with open(os.path.join(sources_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2), initializer=_init) as pool, \
            open(raw, "w", encoding="utf-8") as fh:
        for done, result in enumerate(pool.map(_measure_one, [(sources_dir, e) for e in manifest], chunksize=2), 1):
            fh.write(json.dumps(result) + "\n")
            if done % 50 == 0:
                print(f"measure: {done}/{len(manifest)}", file=sys.stderr)
    return 0


def _verdict(naming: dict, ref: str, params: dict, margin: float) -> dict:
    pairs = {slug: (t, w) for slug, (t, w, equiv) in naming["pairs"].items() if equiv < params["equivalent"]}
    return replace.decide_pairs(ref, naming["fit"], pairs, params["bar"], margin, params["min_weight"])


def _best(record: dict, ref_of, params: dict, margin: float):
    """The accepted-first, best-fit verdict over interpretations, as `replace_run.verify` picks it."""
    best = None
    for interp in record["interpretations"]:
        ref = ref_of(interp)
        if ref is None or ref not in interp["namings"]:
            continue
        verdict = {**_verdict(interp["namings"][ref], ref, params, margin), "interp": interp}
        if best is None or (verdict["accepted"], verdict["fit"]) > (best["accepted"], best["fit"]):
            best = verdict
    return best


def outcomes(record: dict, params: dict) -> list[tuple[str, str, dict | None]]:
    """(naming, outcome, verdict) for one source: truth, each wrong name, auto."""
    out = []
    truth = record["truth"]
    if truth:
        v = _best(record, lambda i: truth, params, params["margin"])
        out.append(("truth", "correct" if v and v["accepted"] else "missed", v))
    for wrong in record["wrong_names"]:
        v = _best(record, lambda i, w=wrong: w, params, params["margin"])
        out.append(("wrong", "WRONG" if v and v["accepted"] else "refused", v))
    v = _best(record, lambda i: i.get("auto") if i.get("extent", 0) >= params["auto_min_px"] else None,
              params, params["auto_margin"])
    if v is None or not v["accepted"]:
        out.append(("auto", "missed" if truth else "refused", v))
    else:
        interp = v["interp"]
        same = truth and (v["named"] == truth or interp.get("auto_truth_iou", 0) >= params["equivalent"])
        out.append(("auto", "correct" if same else "WRONG", v))
    return out


def _load(raw: str) -> list[dict]:
    with open(raw, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def table(records: list[dict], params: dict) -> dict:
    counts = Counter()
    for record in records:
        for naming, outcome, _ in outcomes(record, params):
            counts[(record["set"], naming, outcome)] += 1
            if record["set"] == "ladder" and (record["px"] or 0) >= 12 and naming == "truth":
                counts[("ladder>=12", naming, outcome)] += 1
    return counts


def score(raw: str, params_path: str, split: str, tsv: str | None) -> int:
    params = replace.load_params(params_path)
    records = [r for r in _load(raw) if r["split"] == split]
    counts = table(records, params)
    for key in sorted(counts):
        print("\t".join(key) + f"\t{counts[key]}")
    if tsv:
        with open(tsv, "w", encoding="utf-8") as fh:
            fh.write("id\tset\tpx\ttruth\tnaming\tnamed\toutcome\treason\tfit\trunner_up\tmargin\tweight\n")
            for record in records:
                for naming, outcome, v in outcomes(record, params):
                    v = v or {}
                    fh.write("\t".join(str(x) for x in (
                        record["id"], record["set"], record["px"] or "-", record["truth"] or "-", naming,
                        v.get("named", "-"), outcome, v.get("reason") or "-", v.get("fit", "-"),
                        v.get("runner_up") or "-", v.get("margin") if v.get("margin") is not None else "-",
                        v.get("weight") if v.get("weight") is not None else "-")) + "\n")
    wrong = sum(n for (s, _, o), n in counts.items() if o == "WRONG" and s != "ladder>=12")
    print(f"score: {split}: wrong replacements {wrong}", file=sys.stderr)
    return 0


def calibrate(raw: str) -> int:
    """Sweep the named rule (bar × margin × min_weight) and auto's margin separately, on the calibrate split only.

    Prints, for each, the settings with zero wrong replacements ranked by what they recover. The committed
    numbers are chosen from this table with headroom above the smallest zero-wrong margin, and the choice and
    its measurement are recorded in the eval README.
    """
    base = replace.load_params(os.path.join(PARAMS_DIR, "replace.json"))
    records = [r for r in _load(raw) if r["split"] == "calibrate"]
    named, auto = [], []
    for bar in (0.5, 0.55, 0.6, 0.65, 0.7):
        for min_weight in (1, 2, 3, 4, 6):
            for margin in (0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6):
                params = {**base, "bar": bar, "margin": margin, "auto_margin": margin, "min_weight": min_weight}
                counts = table(records, params)
                wrong_named = counts[("ladder", "wrong", "WRONG")] + counts[("negative", "wrong", "WRONG")]
                wrong_auto = counts[("ladder", "auto", "WRONG")] + counts[("negative", "auto", "WRONG")]
                total12 = counts[("ladder>=12", "truth", "correct")] + counts[("ladder>=12", "truth", "missed")]
                named.append((wrong_named, -counts[("ladder>=12", "truth", "correct")] / max(total12, 1), bar, margin, min_weight))
                auto.append((wrong_auto, -counts[("ladder", "auto", "correct")], bar, margin, min_weight))
    for title, rows, head in (("named", named, "wrong\trecall>=12"), ("auto", auto, "wrong\tauto_correct")):
        rows.sort()
        print(f"# {title}\n{head}\tbar\tmargin\tmin_weight")
        for row in rows[:15]:
            print("\t".join(f"{-v:.3f}" if i == 1 and isinstance(v, float) else str(abs(v) if i == 1 else v)
                            for i, v in enumerate(row)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("sources")
    m.add_argument("raw")
    s = sub.add_parser("score")
    s.add_argument("raw")
    s.add_argument("params")
    s.add_argument("--split", default="eval")
    s.add_argument("--tsv")
    c = sub.add_parser("calibrate")
    c.add_argument("raw")
    args = parser.parse_args(argv)
    if args.cmd == "measure":
        return measure(args.sources, args.raw)
    if args.cmd == "score":
        return score(args.raw, args.params, args.split, args.tsv)
    return calibrate(args.raw)


if __name__ == "__main__":
    sys.exit(main())
