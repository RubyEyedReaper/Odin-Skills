"""Entry-point CLI for the decision-matrix scoring engine (Sprints 1-4, stdlib only).

Usage:
    python3 -m scripts.score --spec path/to/spec.json
    cat spec.json | python3 -m scripts.score
    python3 -m scripts.score --spec path/to/spec.json --record --decisions-dir PATH
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.validate import (
    validate_spec,
    apply_constraints,
    criteria_quality_warnings,
)
from scripts.aggregation import (
    aggregate_scores,
    conflict_detect,
    scorer_variance_summary,
)
from scripts.methods import (
    weighted_sum,
    pugh_matrix,
    topsis,
    ahp_weights,
    rice_score,
    wsjf_score,
    ice_score,
    kano_classify,
    MethodError,
)
from scripts.sensitivity import (
    break_even_analysis,
    tornado_data,
    fragility_flag,
    disagreement_report,
)
from scripts.ledger import (
    next_dec_number,
    write_dec_record,
    update_readme_index,
    promote_to_adr_hint,
)
from scripts.recall import search_prior_decisions

SCHEMA_VERSION = "1"

# Default decisions ledger directory: <skill-root>/../../docs/decisions resolved relative
# to this file (scripts/score.py), i.e. the repo's .claude/docs/decisions.
_DEFAULT_DECISIONS_DIR = (Path(__file__).resolve().parent / ".." / ".." / ".." / "docs" / "decisions").resolve()

# Bundled Node visual generator (scripts/visual.mjs), used to render the HTML artifact.
_VISUAL_SCRIPT = Path(__file__).resolve().parent / "visual.mjs"


def _render_visual(result: dict, dec_path: Path) -> tuple:
    """Render the HTML artifact next to the DEC record via the bundled visual.mjs.

    Returns (html_path: str | None, error: str | None). Never raises — if Node is
    unavailable or the generator fails, the rest of the result still succeeds
    (graceful degradation, no silent math: only the visual is optional).
    """
    node = shutil.which("node")
    if node is None:
        return None, "node not available"
    if not _VISUAL_SCRIPT.exists():
        return None, "visual.mjs not found"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(result, tmp)
            tmp_path = tmp.name
        completed = subprocess.run(
            [node, str(_VISUAL_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            return None, f"visual.mjs exited {completed.returncode}: {completed.stderr.strip()}"
        html_path = dec_path.with_suffix(".html")
        html_path.write_text(completed.stdout, encoding="utf-8")
        return str(html_path), None
    except Exception as exc:  # noqa: BLE001 — visual is best-effort
        return None, f"visual generation failed: {exc}"
    finally:
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)

# Map spec method names → callable.
# ahp is handled separately (requires pairwise matrix from spec).
_METHOD_MAP = {
    "weighted-sum": weighted_sum,
    "pugh": pugh_matrix,
    "topsis": topsis,
    "rice": rice_score,
    "wsjf": wsjf_score,
    "ice": ice_score,
    "kano": kano_classify,
}

# Methods that accept the full (active_options, criteria, score_matrix) signature.
_CRITERIA_METHODS = {"weighted-sum", "pugh", "topsis"}
# Methods that accept only (active_options, score_matrix) — framework-specific.
_FRAMEWORK_METHODS = {"rice", "wsjf", "ice", "kano"}


def _build_error_response(message: str, details: list = None) -> dict:
    return {"error": message, "details": details or []}


def _detect_ties(ranking: list, tie_threshold: float, score_range: float) -> dict:
    """Return tie info dict with near_tie_pairs list.

    A pair is a near-tie when the absolute score gap ≤ tie_threshold percent
    of the total score range (or tie_threshold points when range is 0).
    """
    near_tie_pairs: list = []
    if len(ranking) < 2:
        return {"near_tie_pairs": near_tie_pairs}

    threshold_points = (score_range * tie_threshold / 100.0) if score_range > 0 else tie_threshold

    for i in range(len(ranking)):
        for j in range(i + 1, len(ranking)):
            a, b = ranking[i], ranking[j]
            gap = abs(a["score"] - b["score"])
            if gap <= threshold_points:
                near_tie_pairs.append({
                    "options": [a["option"], b["option"]],
                    "gap": round(gap, 4),
                    "threshold": round(threshold_points, 4),
                })

    return {"near_tie_pairs": near_tie_pairs}


def _build_recommendation(
    ranking: list,
    active_options: list,
    spec: dict,
    ties: dict,
    method_results: dict,
    sensitivity_result: dict,
) -> dict:
    if not ranking:
        return {
            "winner": None,
            "winner_label": None,
            "rationale": "no active options to rank",
            "confidence": "low",
            "caveats": [],
        }

    winner_entry = ranking[0]
    winner_id = winner_entry["option"]

    options_by_id = {o["id"]: o for o in spec.get("options", [])}
    winner_label = options_by_id.get(winner_id, {}).get("label", winner_id)

    caveats: list = []

    # Near-tie caveat
    near_ties = ties.get("near_tie_pairs", [])
    winner_near_ties = [p for p in near_ties if winner_id in p["options"]]
    winner_in_near_tie = bool(winner_near_ties)
    if winner_in_near_tie:
        rivals = [
            opt for p in winner_near_ties for opt in p["options"] if opt != winner_id
        ]
        rival_labels = [options_by_id.get(r, {}).get("label", r) for r in rivals]
        caveats.append(
            f"near-tie with {', '.join(rival_labels)}; "
            f"small score gap — weight sensitivity may change the outcome"
        )

    # Disagreement caveat
    disagree = sensitivity_result.get("disagreement_report", {})
    methods_agree = disagree.get("methods_agree", True)
    if not methods_agree:
        winner_by_m = disagree.get("winner_by_method", {})
        caveats.append(
            f"methods disagree on winner: "
            + "; ".join(f"{m}→{w}" for m, w in winner_by_m.items())
        )

    # Fragility caveat
    be = sensitivity_result.get("break_even", {})
    is_fragile, fragile_reason = fragility_flag(be) if be else (False, "")
    if is_fragile:
        caveats.append(f"fragile recommendation: {fragile_reason}")

    # Confidence logic:
    #   high  — all ranking methods agree on rank-1 AND not fragile AND no near-tie
    #   medium — methods agree OR not fragile (at least one good signal)
    #   low   — disagreement AND fragile (both bad signals) OR near-tie
    if methods_agree and not is_fragile and not winner_in_near_tie:
        confidence = "high"
    elif methods_agree or not is_fragile:
        confidence = "medium"
    else:
        confidence = "low"

    # Override to low when winner is in a near-tie regardless
    if winner_in_near_tie:
        confidence = "low"

    rationale = (
        f"{winner_label} ranks first by weighted-sum across "
        f"{len(spec.get('criteria', []))} criteria"
    )

    return {
        "winner": winner_id,
        "winner_label": winner_label,
        "rationale": rationale,
        "confidence": confidence,
        "caveats": caveats,
    }


_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _apply_conflict_caveat(recommendation: dict, conflicts: list) -> None:
    """Mutate recommendation in place: cap confidence at "medium" and append a
    caveat when any scorer-conflict cell involves the winner option.
    """
    winner_id = recommendation.get("winner")
    if winner_id is None or not conflicts:
        return

    winner_conflicts = [c for c in conflicts if c["option"] == winner_id]
    if not winner_conflicts:
        return

    criteria_list = ", ".join(sorted({c["criterion"] for c in winner_conflicts}))
    recommendation["caveats"].append(
        f"scorers disagree on the winner's score for: {criteria_list} "
        f"(high variance across scorers) — confirm before acting"
    )

    if _CONFIDENCE_RANK.get(recommendation["confidence"], 2) > _CONFIDENCE_RANK["medium"]:
        recommendation["confidence"] = "medium"


def _run_methods(
    spec: dict,
    active_ids: list,
    criteria: list,
    score_matrix: dict,
) -> dict:
    """Run each method listed in spec['methods'].

    Returns {method_name: ranking_list | {"error": str}}.
    """
    requested = spec.get("methods", ["weighted-sum"])
    results: dict = {}

    for method_name in requested:
        if method_name == "ahp":
            # AHP: recompute weights from pairwise matrix, then run weighted_sum
            ahp_pairwise = spec.get("ahp_pairwise")
            if ahp_pairwise is None:
                results["ahp"] = {"error": "ahp_pairwise not present in spec; skipping AHP"}
                continue
            try:
                ahp_w = ahp_weights(ahp_pairwise, [c["id"] for c in criteria])
                # Build synthetic criteria with AHP-derived weights (×100 for raw scale)
                synthetic_criteria = [
                    {**c, "weight": ahp_w[c["id"]] * 100.0}
                    for c in criteria
                ]
                ranking = weighted_sum(active_ids, synthetic_criteria, score_matrix)
                results["ahp"] = {"ranking": ranking}
            except Exception as exc:  # noqa: BLE001
                results["ahp"] = {"error": str(exc)}
            continue

        if method_name in _CRITERIA_METHODS:
            fn = _METHOD_MAP[method_name]
            try:
                ranking = fn(active_ids, criteria, score_matrix)
                results[method_name] = {"ranking": ranking}
            except MethodError as exc:
                results[method_name] = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                results[method_name] = {"error": str(exc)}

        elif method_name in _FRAMEWORK_METHODS:
            fn = _METHOD_MAP[method_name]
            try:
                ranking = fn(active_ids, score_matrix)
                results[method_name] = {"ranking": ranking}
            except MethodError as exc:
                results[method_name] = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                results[method_name] = {"error": str(exc)}

        else:
            results[method_name] = {"error": f"unknown method {method_name!r}"}

    return results


def _revisit_reminder(spec: dict) -> dict:
    """Return a revisit_reminder dict, or None when not applicable.

    Applies when spec.revisit_after_days is set AND reversibility == "two-way"
    (a one-way decision is not something you casually "revisit" on a timer).
    """
    revisit_after_days = spec.get("revisit_after_days")
    if not revisit_after_days or spec.get("reversibility") != "two-way":
        return None

    due_date = (datetime.now(timezone.utc).date() + timedelta(days=int(revisit_after_days)))
    return {
        "due_date": due_date.isoformat(),
        "message": (
            f"Revisit this decision by {due_date.isoformat()} "
            f"({revisit_after_days} days) — confirm the recommendation still holds."
        ),
    }


def run(spec: dict, *, decisions_dir: Path = None, record: bool = False) -> tuple:
    """Core orchestration. Returns (result_dict, exit_code).

    decisions_dir/record control DEC-ledger recording (Sprint 4):
      - record=False (default): NO file writes. prior_decisions=[], dec_record_path=None.
      - record=True: search prior decisions before scoring, write a DEC record + update
        the README index after scoring. decisions_dir defaults to the repo's
        .claude/docs/decisions when not provided.
    """
    resolved_decisions_dir = Path(decisions_dir) if decisions_dir is not None else _DEFAULT_DECISIONS_DIR

    # 1. Validate
    errors = validate_spec(spec)
    if errors:
        return _build_error_response("invalid decision spec", errors), 1

    # Prior-decision recall (only when recording; never touches disk otherwise)
    prior_decisions = []
    if record:
        option_labels = [o.get("label", o.get("id", "")) for o in spec.get("options", [])]
        prior_decisions = search_prior_decisions(spec.get("goal", ""), option_labels, resolved_decisions_dir)

    # 2. Apply constraints
    vetoed_ids, active_ids = apply_constraints(spec)

    if not active_ids:
        result = {
            "schema_version": SCHEMA_VERSION,
            "vetoed_options": vetoed_ids,
            "active_options": [],
            "aggregated_scores": {},
            "criteria_quality": {"warnings": []},
            "method_results": {"weighted-sum": {"ranking": []}},
            "ties": {"near_tie_pairs": []},
            "disagreement_report": {
                "methods_agree": True,
                "winner_by_method": {},
                "disagreement_pairs": [],
            },
            "sensitivity": {},
            "multi_scorer_analysis": {"conflicts": [], "variance": {"outliers": []}},
            "recommendation": {
                "winner": None,
                "winner_label": None,
                "rationale": "all options vetoed",
                "confidence": "low",
                "caveats": [],
            },
            "prior_decisions": prior_decisions if record else [],
            "dec_record_path": None,
            "promote_to_adr_hint": False,
            "revisit_reminder": _revisit_reminder(spec),
        }
        return result, 0

    # 3. Criteria quality warnings
    warnings = criteria_quality_warnings(spec)

    # 4. Aggregate scores (pass-through for single scorer)
    aggregated = aggregate_scores(spec)

    # 5. Build score matrix for active options only (use confidence_adjusted)
    criteria = spec.get("criteria", [])
    score_matrix: dict = {}
    for opt_id in active_ids:
        score_matrix[opt_id] = {}
        for crit_id, agg in aggregated.get(opt_id, {}).items():
            score_matrix[opt_id][crit_id] = agg["confidence_adjusted"]

    # 6. Run all requested methods
    method_results = _run_methods(spec, active_ids, criteria, score_matrix)

    # 7. Extract weighted-sum ranking (always present; used for tie + sensitivity)
    ws_result = method_results.get("weighted-sum", {})
    if "ranking" in ws_result:
        ws_ranking = ws_result["ranking"]
    else:
        # weighted-sum not requested or errored — compute it anyway for tie detection
        ws_ranking = weighted_sum(active_ids, criteria, score_matrix)

    # 8. Tie detection on weighted-sum
    scores = [r["score"] for r in ws_ranking]
    score_range = (max(scores) - min(scores)) if len(scores) >= 2 else 0.0
    tie_threshold = float(spec.get("tie_threshold", 5))
    ties = _detect_ties(ws_ranking, tie_threshold, score_range)

    # 9. Disagreement report (across all methods that produced rankings)
    ranking_results_flat = {}
    for mname, mresult in method_results.items():
        if isinstance(mresult, dict) and "ranking" in mresult:
            ranking_results_flat[mname] = mresult["ranking"]
        else:
            ranking_results_flat[mname] = mresult  # error passthrough
    disagree = disagreement_report(ranking_results_flat)

    # 10. Sensitivity analysis (on weighted-sum winner)
    sensitivity: dict = {}
    if ws_ranking:
        ws_winner_id = ws_ranking[0]["option"]
        be = break_even_analysis(ws_winner_id, active_ids, criteria, score_matrix)
        tornado = tornado_data(ws_winner_id, active_ids, criteria, score_matrix)
        is_fragile, fragile_reason = fragility_flag(be)
        sensitivity = {
            "winner_analyzed": ws_winner_id,
            "break_even": be,
            "tornado": tornado,
            "fragile": is_fragile,
            "fragile_reason": fragile_reason,
        }

    # 11. Build recommendation
    sensitivity_for_rec = {
        "disagreement_report": disagree,
        "break_even": sensitivity.get("break_even", {}),
    }
    recommendation = _build_recommendation(
        ws_ranking, active_ids, spec, ties, method_results, sensitivity_for_rec
    )

    # 12. Multi-scorer analysis (conflicts + per-scorer variance)
    conflicts = conflict_detect(spec)
    variance_summary = scorer_variance_summary(spec)
    multi_scorer_analysis = {
        "conflicts": conflicts,
        "variance": variance_summary,
    }
    _apply_conflict_caveat(recommendation, conflicts)

    result = {
        "schema_version": SCHEMA_VERSION,
        "vetoed_options": vetoed_ids,
        "active_options": active_ids,
        "aggregated_scores": aggregated,
        "criteria_quality": {"warnings": warnings},
        "method_results": method_results,
        "ties": ties,
        "disagreement_report": disagree,
        "sensitivity": sensitivity,
        "multi_scorer_analysis": multi_scorer_analysis,
        "recommendation": recommendation,
        "reversibility": spec.get("reversibility"),
    }

    # 13. DEC ledger recording (only when record=True — no file writes otherwise)
    if record:
        result["prior_decisions"] = prior_decisions
        result["dec_record_path"] = None
        result["html_artifact_path"] = None
        result["promote_to_adr_hint"] = promote_to_adr_hint(result)

        if recommendation.get("winner") is not None:
            title = spec.get("goal", "Untitled decision")
            dec_number = next_dec_number(resolved_decisions_dir)
            dec_id = f"DEC-{dec_number:04d}"
            dec_path = write_dec_record(dec_id, spec, result, resolved_decisions_dir)
            update_readme_index(
                dec_id, title, dec_path, resolved_decisions_dir, winner=recommendation.get("winner")
            )
            result["dec_record_path"] = str(dec_path)
            html_path, html_err = _render_visual(result, dec_path)
            result["html_artifact_path"] = html_path
            if html_err is not None:
                result["html_artifact_error"] = html_err
    else:
        result["prior_decisions"] = []
        result["dec_record_path"] = None
        result["html_artifact_path"] = None
        result["promote_to_adr_hint"] = promote_to_adr_hint(result)

    result["revisit_reminder"] = _revisit_reminder(spec)

    return result, 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score a decision-spec JSON and emit a result JSON."
    )
    parser.add_argument(
        "--spec",
        metavar="PATH",
        help="Path to decision-spec JSON file (default: read from stdin)",
    )
    parser.add_argument(
        "--record",
        dest="record",
        action="store_true",
        help="Record this run as a numbered DEC decision (writes files). Default: off.",
    )
    parser.add_argument(
        "--no-record",
        dest="record",
        action="store_false",
        help="Do not record this run (default — no file writes).",
    )
    parser.set_defaults(record=False)
    parser.add_argument(
        "--decisions-dir",
        metavar="PATH",
        default=None,
        help="DEC ledger directory (default: .claude/docs/decisions in this repo).",
    )
    args = parser.parse_args()

    try:
        if args.spec:
            with open(args.spec, "r", encoding="utf-8") as fh:
                spec = json.load(fh)
        else:
            spec = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as exc:
        payload = _build_error_response(f"failed to load spec: {exc}")
        print(json.dumps(payload, indent=2), file=sys.stderr)
        sys.exit(1)

    decisions_dir = Path(args.decisions_dir) if args.decisions_dir else None

    try:
        result, exit_code = run(spec, decisions_dir=decisions_dir, record=args.record)
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        payload = _build_error_response(f"unexpected error: {exc}")
        print(json.dumps(payload, indent=2), file=sys.stderr)
        sys.exit(1)

    if exit_code != 0:
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(exit_code)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
