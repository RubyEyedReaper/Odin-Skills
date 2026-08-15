"""Sensitivity analysis for decision-matrix (Sprint 2, stdlib only).

Functions
---------
break_even_analysis  -- per-criterion weight shift needed to dethrone winner
tornado_data         -- score swing under ±perturbation of each weight
fragility_flag       -- boolean flag + reason when winner is fragile
disagreement_report  -- cross-method rank-1 agreement check
"""
from scripts.methods import normalize_weights, weighted_sum


# ── break_even_analysis ───────────────────────────────────────────────────────

def break_even_analysis(
    winner_id: str,
    active_options: list,
    criteria: list,
    score_matrix: dict,
    weight_step: float = 0.01,
) -> dict:
    """Find the minimum weight shift per criterion that causes winner to lose rank 1.

    Algorithm
    ---------
    For each criterion C with non-zero weight:
      1. Increment C's normalized weight in steps of weight_step (as a fraction
         of total, i.e. 1% increments), deflating all other criteria
         proportionally so weights still sum to 1.
      2. After each step, re-run weighted_sum; if winner_id is no longer rank 1
         record the cumulative shift percentage and which option overtook it.
      3. Search stops when shift reaches 100% (i.e. C gets all weight) or a
         flip is found.

    Returns
    -------
    {
        crit_id: {
            "weight_shift_to_flip_pct": float | None,
            "favors_if_flipped": option_id | None,
        },
        ...
    }

    weight_shift_to_flip_pct is expressed as percentage points of the
    normalized weight (e.g. 15.0 means adding 15 pp to that criterion's
    normalized weight flipped the winner).  None means no flip was found
    within the full 0→100% range.
    """
    base_normed = normalize_weights(criteria)
    result: dict = {}

    for target_crit in criteria:
        tcid = target_crit["id"]
        base_w = base_normed[tcid]

        flip_pct = None
        favors = None

        # Walk from base weight toward 1.0 in weight_step increments
        step_count = 0
        max_steps = int((1.0 - base_w) / weight_step) + 1

        for _ in range(max_steps):
            step_count += 1
            new_target_w = min(base_w + step_count * weight_step, 1.0)
            remaining = 1.0 - new_target_w
            other_total = sum(base_normed[c["id"]] for c in criteria if c["id"] != tcid)

            # Build a synthetic criteria list with adjusted weights
            synthetic_criteria = []
            for c in criteria:
                cid = c["id"]
                if cid == tcid:
                    synthetic_w = new_target_w * 100.0  # un-normalize to raw scale
                else:
                    if other_total > 0:
                        prop = base_normed[cid] / other_total
                    else:
                        prop = 1.0 / max(len(criteria) - 1, 1)
                    synthetic_w = prop * remaining * 100.0
                synthetic_criteria.append({**c, "weight": synthetic_w})

            ranking = weighted_sum(active_options, synthetic_criteria, score_matrix)
            rank1_opt = ranking[0]["option"]

            if rank1_opt != winner_id:
                shift_pct = (new_target_w - base_w) * 100.0
                flip_pct = round(shift_pct, 4)
                favors = rank1_opt
                break

            if new_target_w >= 1.0:
                break

        result[tcid] = {
            "weight_shift_to_flip_pct": flip_pct,
            "favors_if_flipped": favors,
        }

    return result


# ── tornado_data ──────────────────────────────────────────────────────────────

def tornado_data(
    winner_id: str,
    active_options: list,
    criteria: list,
    score_matrix: dict,
    perturbation_pct: float = 0.2,
) -> list:
    """Tornado chart data: score swing of winner under ±perturbation of each weight.

    For each criterion, two scenarios are evaluated:
      high scenario: criterion weight × (1 + perturbation_pct), others deflated
      low  scenario: criterion weight × (1 - perturbation_pct), others inflated

    swing_impact = |winner_score_high - winner_score_low|

    Returns
    -------
    List of {
        "criterion": crit_id,
        "swing_impact": float,
        "baseline_rank_of_winner": int,
        "perturbed_rank_of_winner": int,   # rank in the HIGH perturbation scenario
    } sorted by swing_impact descending.
    """
    base_normed = normalize_weights(criteria)

    def _perturbed_ranking(target_cid: str, direction: float) -> list:
        """Return weighted_sum ranking with target criterion weight scaled by (1 ± pct)."""
        raw_target = base_normed[target_cid]
        new_target = raw_target * (1.0 + direction * perturbation_pct)
        new_target = max(0.0, min(1.0, new_target))
        remaining = 1.0 - new_target
        other_total = sum(base_normed[c["id"]] for c in criteria if c["id"] != target_cid)

        synthetic = []
        for c in criteria:
            cid = c["id"]
            if cid == target_cid:
                w = new_target * 100.0
            else:
                if other_total > 0:
                    prop = base_normed[cid] / other_total
                else:
                    prop = 1.0 / max(len(criteria) - 1, 1)
                w = prop * remaining * 100.0
            synthetic.append({**c, "weight": w})

        return weighted_sum(active_options, synthetic, score_matrix)

    # Baseline ranking
    baseline_ranking = weighted_sum(active_options, criteria, score_matrix)
    baseline_by_opt = {r["option"]: r for r in baseline_ranking}
    baseline_winner_rank = baseline_by_opt[winner_id]["rank"]

    entries: list = []
    for crit in criteria:
        tcid = crit["id"]

        high_ranking = _perturbed_ranking(tcid, +1.0)
        low_ranking = _perturbed_ranking(tcid, -1.0)

        high_by_opt = {r["option"]: r for r in high_ranking}
        low_by_opt = {r["option"]: r for r in low_ranking}

        winner_score_high = high_by_opt[winner_id]["score"]
        winner_score_low = low_by_opt[winner_id]["score"]
        swing = abs(winner_score_high - winner_score_low)

        perturbed_rank = high_by_opt[winner_id]["rank"]

        entries.append({
            "criterion": tcid,
            "swing_impact": round(swing, 6),
            "baseline_rank_of_winner": baseline_winner_rank,
            "perturbed_rank_of_winner": perturbed_rank,
        })

    entries.sort(key=lambda x: x["swing_impact"], reverse=True)
    return entries


# ── fragility_flag ────────────────────────────────────────────────────────────

def fragility_flag(
    break_even: dict,
    fragile_threshold_pct: float = 10.0,
) -> tuple:
    """Return (is_fragile: bool, reason: str).

    Fragile when any criterion's weight_shift_to_flip_pct is not None and
    <= fragile_threshold_pct (inclusive — a shift exactly equal to the
    threshold is still fragile because the recommendation is not robust to
    that level of weight uncertainty).
    """
    for crit_id, entry in break_even.items():
        shift = entry.get("weight_shift_to_flip_pct")
        if shift is not None and shift <= fragile_threshold_pct:
            reason = (
                f"winner flips if '{crit_id}' weight shifts by "
                f"{shift:.1f} pp (threshold: {fragile_threshold_pct:.1f} pp)"
            )
            return True, reason
    return False, ""


# ── disagreement_report ───────────────────────────────────────────────────────

def disagreement_report(method_results: dict) -> dict:
    """Compare rank-1 winners across methods.

    Parameters
    ----------
    method_results : dict
        Keys are method names; values are either:
          - list of {"option", "score", "rank", ...} (a valid ranking), or
          - dict with an "error" key (skipped).

    Returns
    -------
    {
        "methods_agree": bool,
        "winner_by_method": {method_name: option_id},
        "disagreement_pairs": [
            {"methods": [m1, m2], "winners": [opt1, opt2]}, ...
        ],
    }

    Only methods that produced valid rankings (not error dicts) are included.
    If zero or one valid method exists, methods_agree is True and
    disagreement_pairs is [].
    """
    winner_by_method: dict = {}
    for method_name, ranking in method_results.items():
        # Skip error entries
        if isinstance(ranking, dict) and "error" in ranking:
            continue
        if not isinstance(ranking, list) or not ranking:
            continue
        # rank-1 entry (list already sorted desc, rank=1 is first)
        rank1_entries = [r for r in ranking if r.get("rank") == 1]
        if rank1_entries:
            winner_by_method[method_name] = rank1_entries[0]["option"]

    # Build disagreement pairs
    method_names = list(winner_by_method.keys())
    disagreement_pairs: list = []
    for i in range(len(method_names)):
        for j in range(i + 1, len(method_names)):
            m1, m2 = method_names[i], method_names[j]
            w1, w2 = winner_by_method[m1], winner_by_method[m2]
            if w1 != w2:
                disagreement_pairs.append({"methods": [m1, m2], "winners": [w1, w2]})

    winners = set(winner_by_method.values())
    methods_agree = len(winners) <= 1

    return {
        "methods_agree": methods_agree,
        "winner_by_method": winner_by_method,
        "disagreement_pairs": disagreement_pairs,
    }
