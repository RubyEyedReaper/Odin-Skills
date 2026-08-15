"""Multi-scorer aggregation, conflict detection, and variance summary (Sprint 3, stdlib only).

Supersedes scripts.validate.aggregate_scores (single-scorer pass-through). This module handles
N >= 1 scorers uniformly: a single scorer is just the N=1 case (std_dev collapses to 0.0).
"""
import statistics


def _option_criterion_ids(spec: dict) -> tuple:
    option_ids = [o.get("id") for o in spec.get("options", [])]
    criterion_ids = [c.get("id") for c in spec.get("criteria", [])]
    return option_ids, criterion_ids


def _entry(scorer: dict, opt_id, crit_id) -> dict:
    return scorer.get("scores", {}).get(opt_id, {}).get(crit_id, {})


def aggregate_scores(spec: dict) -> dict:
    """Aggregate scores across ALL scorers for each option x criterion cell.

    Returns:
        {option_id: {criterion_id: {"mean": float, "std_dev": float,
                                     "confidence_adjusted": float}}}

    mean / std_dev are computed over the raw "value" across scorers (population
    std_dev — statistics.pstdev — since scorers are the full population being
    aggregated, not a sample).  confidence_adjusted is the mean of
    (value * confidence) across scorers (confidence defaults to 1.0 per entry).

    A single scorer is the natural N=1 case: std_dev is 0.0 and
    confidence_adjusted == value * confidence (pass-through).
    """
    scorers = spec.get("scorers", [])
    option_ids, criterion_ids = _option_criterion_ids(spec)

    result: dict = {}
    if not scorers:
        return result

    for opt_id in option_ids:
        result[opt_id] = {}
        for crit_id in criterion_ids:
            values: list = []
            adjusted: list = []
            for scorer in scorers:
                entry = _entry(scorer, opt_id, crit_id)
                value = float(entry.get("value", 0))
                confidence = float(entry.get("confidence", 1.0))
                values.append(value)
                adjusted.append(value * confidence)

            result[opt_id][crit_id] = {
                "mean": statistics.mean(values) if values else 0.0,
                "std_dev": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "confidence_adjusted": statistics.mean(adjusted) if adjusted else 0.0,
            }

    return result


def conflict_detect(spec: dict, conflict_threshold_std: float = 25.0) -> list:
    """Flag option x criterion cells where scorer disagreement exceeds the threshold.

    A cell is flagged when its population std_dev across scorers is strictly
    greater than conflict_threshold_std.

    Returns:
        [{"option": str, "criterion": str, "std_dev": float,
          "scorer_values": {scorer_id: value, ...}}, ...]

    With 0 or 1 scorers there is no disagreement to detect — returns [].
    """
    scorers = spec.get("scorers", [])
    if len(scorers) < 2:
        return []

    option_ids, criterion_ids = _option_criterion_ids(spec)
    conflicts: list = []

    for opt_id in option_ids:
        for crit_id in criterion_ids:
            scorer_values: dict = {}
            values: list = []
            for scorer in scorers:
                sid = scorer.get("id")
                entry = _entry(scorer, opt_id, crit_id)
                value = entry.get("value", 0)
                scorer_values[sid] = value
                values.append(float(value))

            std_dev = statistics.pstdev(values) if len(values) > 1 else 0.0
            if std_dev > conflict_threshold_std:
                conflicts.append({
                    "option": opt_id,
                    "criterion": crit_id,
                    "std_dev": std_dev,
                    "scorer_values": scorer_values,
                })

    return conflicts


def scorer_variance_summary(spec: dict) -> dict:
    """Per-scorer mean absolute deviation from the group mean across all cells.

    Returns:
        {scorer_id: mean_abs_dev, ..., "outliers": [scorer_id, ...]}

    An "outlier" scorer is one whose mean_abs_dev exceeds 1.5x the median
    mean_abs_dev across all scorers. With <= 1 scorer, every scorer's
    deviation is 0.0 and there are no outliers.
    """
    scorers = spec.get("scorers", [])
    if not scorers:
        return {"outliers": []}

    option_ids, criterion_ids = _option_criterion_ids(spec)

    # Group mean per cell (raw "value", across scorers).
    cell_means: dict = {}
    for opt_id in option_ids:
        for crit_id in criterion_ids:
            values = [
                float(_entry(scorer, opt_id, crit_id).get("value", 0))
                for scorer in scorers
            ]
            cell_means[(opt_id, crit_id)] = statistics.mean(values) if values else 0.0

    deviations: dict = {}
    for scorer in scorers:
        sid = scorer.get("id")
        abs_devs: list = []
        for opt_id in option_ids:
            for crit_id in criterion_ids:
                value = float(_entry(scorer, opt_id, crit_id).get("value", 0))
                abs_devs.append(abs(value - cell_means[(opt_id, crit_id)]))
        deviations[sid] = statistics.mean(abs_devs) if abs_devs else 0.0

    summary: dict = dict(deviations)

    if len(scorers) > 1:
        median_dev = statistics.median(deviations.values())
        outliers = [
            sid for sid, dev in deviations.items()
            if median_dev > 0 and dev > 1.5 * median_dev
        ]
    else:
        outliers = []

    summary["outliers"] = outliers
    return summary
