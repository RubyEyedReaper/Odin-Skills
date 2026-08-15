"""Validation and aggregation for decision-spec JSON (Sprint 1, stdlib only)."""
from typing import Tuple

VALID_REVERSIBILITY = {"two-way", "one-way"}
VALID_DIRECTIONS = {"higher-is-better", "lower-is-better"}


class ValidationError(Exception):
    """Raised when a spec is structurally invalid and cannot be processed."""


def validate_spec(spec: dict) -> list:
    """Return a list of human-readable error strings (empty list = valid).

    Checks all fields and collects ALL errors before returning.
    """
    errors: list = []

    # ── goal ────────────────────────────────────────────────────────────────
    goal = spec.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("goal must be a non-empty string")

    # ── reversibility ────────────────────────────────────────────────────────
    rev = spec.get("reversibility")
    if rev is None:
        errors.append("reversibility is required")
    elif rev not in VALID_REVERSIBILITY:
        errors.append(
            f"reversibility must be one of {sorted(VALID_REVERSIBILITY)}, got {rev!r}"
        )

    # ── options ──────────────────────────────────────────────────────────────
    options = spec.get("options", [])
    if len(options) < 2:
        errors.append(f"at least 2 options required, got {len(options)}")

    option_ids = {o.get("id") for o in options if isinstance(o, dict)}

    # ── criteria ─────────────────────────────────────────────────────────────
    criteria = spec.get("criteria", [])
    if len(criteria) < 1:
        errors.append("at least 1 criterion required")

    criterion_ids = set()
    for crit in criteria:
        if not isinstance(crit, dict):
            errors.append("each criterion must be an object")
            continue
        cid = crit.get("id", "<unknown>")
        criterion_ids.add(cid)

        weight = crit.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            errors.append(f"criterion {cid!r}: weight must be a number, got {weight!r}")
        elif not (0 <= weight <= 100):
            errors.append(f"criterion {cid!r}: weight must be in [0, 100], got {weight}")

        direction = crit.get("direction")
        if direction not in VALID_DIRECTIONS:
            errors.append(
                f"criterion {cid!r}: direction must be one of "
                f"{sorted(VALID_DIRECTIONS)}, got {direction!r}"
            )

    # ── scorers ──────────────────────────────────────────────────────────────
    scorers = spec.get("scorers", [])
    if len(scorers) < 1:
        errors.append("at least 1 scorer required")

    for scorer in scorers:
        if not isinstance(scorer, dict):
            errors.append("each scorer must be an object")
            continue
        sid = scorer.get("id", "<unknown>")
        scores = scorer.get("scores", {})

        for opt_id in option_ids:
            if opt_id not in scores:
                errors.append(
                    f"scorer {sid!r}: missing scores for option {opt_id!r}"
                )
                continue
            opt_scores = scores[opt_id]
            for crit_id in criterion_ids:
                if crit_id not in opt_scores:
                    errors.append(
                        f"scorer {sid!r}: missing score for option {opt_id!r}, "
                        f"criterion {crit_id!r}"
                    )
                    continue
                entry = opt_scores[crit_id]
                if not isinstance(entry, dict):
                    errors.append(
                        f"scorer {sid!r}: score entry for {opt_id!r}/{crit_id!r} "
                        f"must be an object"
                    )
                    continue

                value = entry.get("value")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(
                        f"scorer {sid!r}: score value for {opt_id!r}/{crit_id!r} "
                        f"must be a number, got {value!r}"
                    )
                elif not (0 <= value <= 100):
                    errors.append(
                        f"scorer {sid!r}: score value for {opt_id!r}/{crit_id!r} "
                        f"must be in [0, 100], got {value}"
                    )

                confidence = entry.get("confidence")
                if confidence is not None:
                    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                        errors.append(
                            f"scorer {sid!r}: confidence for {opt_id!r}/{crit_id!r} "
                            f"must be a number, got {confidence!r}"
                        )
                    elif not (0 <= confidence <= 1):
                        errors.append(
                            f"scorer {sid!r}: confidence for {opt_id!r}/{crit_id!r} "
                            f"must be in [0, 1], got {confidence}"
                        )

    return errors


def apply_constraints(spec: dict) -> Tuple[list, list]:
    """Return (vetoed_ids, active_ids).

    An option is vetoed if any value in constraint_results is False.
    Options without constraint_results are active.
    """
    vetoed: list = []
    active: list = []

    for option in spec.get("options", []):
        opt_id = option.get("id")
        constraint_results = option.get("constraint_results", {})
        if any(v is False for v in constraint_results.values()):
            vetoed.append(opt_id)
        else:
            active.append(opt_id)

    return vetoed, active


def criteria_quality_warnings(spec: dict) -> list:
    """Return a list of warning dicts: {"type": str, "criterion": str, "message": str}.

    Detects:
      - overweight: normalized weight > 0.6
      - zero-weight: weight == 0
      - redundant: duplicate criterion label
      - non-discriminating: all options have identical scores for a criterion
    Uses the first (single) scorer's scores.
    """
    warnings: list = []
    criteria = spec.get("criteria", [])
    scorers = spec.get("scorers", [])

    if not criteria:
        return warnings

    # ── weight checks ────────────────────────────────────────────────────────
    total_weight = sum(
        c.get("weight", 0) for c in criteria
        if isinstance(c.get("weight"), (int, float)) and not isinstance(c.get("weight"), bool)
    )

    seen_labels: dict = {}  # label → first criterion id
    for crit in criteria:
        cid = crit.get("id", "")
        label = crit.get("label", "")
        weight = crit.get("weight", 0)

        if weight == 0:
            warnings.append({
                "type": "zero-weight",
                "criterion": cid,
                "message": f"criterion {cid!r} has weight 0 and will not influence results",
            })

        if total_weight > 0:
            norm = weight / total_weight
            if norm > 0.6:
                warnings.append({
                    "type": "overweight",
                    "criterion": cid,
                    "message": (
                        f"criterion {cid!r} has normalized weight {norm:.0%}, "
                        f"dominating other criteria"
                    ),
                })

        if label in seen_labels:
            warnings.append({
                "type": "redundant",
                "criterion": cid,
                "message": (
                    f"criterion {cid!r} has the same label as "
                    f"{seen_labels[label]!r} ({label!r})"
                ),
            })
        else:
            seen_labels[label] = cid

    # ── non-discriminating check (requires scorer scores) ────────────────────
    if scorers:
        scorer_scores = scorers[0].get("scores", {})
        option_ids = [o.get("id") for o in spec.get("options", [])]

        for crit in criteria:
            cid = crit.get("id", "")
            values = []
            for opt_id in option_ids:
                entry = scorer_scores.get(opt_id, {}).get(cid, {})
                if isinstance(entry, dict) and "value" in entry:
                    values.append(entry["value"])

            if len(values) >= 2 and len(set(values)) == 1:
                warnings.append({
                    "type": "non-discriminating",
                    "criterion": cid,
                    "message": (
                        f"criterion {cid!r}: all options score {values[0]}, "
                        f"providing no differentiation"
                    ),
                })

    return warnings


def aggregate_scores(spec: dict) -> dict:
    """Pass-through aggregation for a single scorer.

    Superseded by scripts.aggregation.aggregate_scores (Sprint 3), which handles
    N >= 1 scorers uniformly (true mean/std_dev across scorers; this single-scorer
    pass-through is now just the N=1 case of that function). scripts/score.py
    imports the Sprint 3 version. This function is kept for backward-compat
    direct callers/tests but is no longer used by the orchestration pipeline.

    Returns:
        {option_id: {criterion_id: {"mean": float, "std_dev": 0.0,
                                     "confidence_adjusted": float}}}
    """
    scorers = spec.get("scorers", [])
    options = spec.get("options", [])
    criteria = spec.get("criteria", [])

    result: dict = {}

    if not scorers:
        return result

    scorer_scores = scorers[0].get("scores", {})

    for option in options:
        opt_id = option.get("id")
        result[opt_id] = {}
        for crit in criteria:
            cid = crit.get("id")
            entry = scorer_scores.get(opt_id, {}).get(cid, {})
            value = float(entry.get("value", 0))
            confidence = float(entry.get("confidence", 1.0))
            result[opt_id][cid] = {
                "mean": value,
                "std_dev": 0.0,
                "confidence_adjusted": value * confidence,
            }

    return result
