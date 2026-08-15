"""Scoring methods for decision-matrix (Sprint 1 + Sprint 2, stdlib only).

Score-matrix contract
---------------------
score_matrix[opt_id][crit_id] = float

For weighted_sum and Pugh/TOPSIS, values are confidence-adjusted raw scores
in the 0-100 range.  Direction inversion (lower-is-better → 100 - value) is
applied *inside* each method; callers pass raw values.

For RICE / WSJF / ICE / Kano the values are raw metric magnitudes specific to
each framework (not 0-100); callers set them directly in the spec scores.
"""
import math
from typing import Union


# ── Exceptions ────────────────────────────────────────────────────────────────

class WeightNormalizationError(Exception):
    """Raised when criteria weights sum to zero and cannot be normalized."""


class MethodError(Exception):
    """Raised when a scoring method cannot run due to missing or invalid data."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_weights(criteria: list) -> dict:
    """Return {criterion_id: normalized_weight} summing to 1.0.

    Raises WeightNormalizationError when total weight is 0.
    """
    total = sum(
        c.get("weight", 0) for c in criteria
        if isinstance(c.get("weight"), (int, float)) and not isinstance(c.get("weight"), bool)
    )
    if total == 0:
        raise WeightNormalizationError(
            "total weight across all criteria is 0; cannot normalize"
        )
    return {
        c["id"]: c.get("weight", 0) / total
        for c in criteria
    }


def _assign_ranks(scored: list) -> list:
    """Add 'rank' to each entry in a list already sorted by score descending.

    Ties share the lowest rank number among equals.
    """
    if not scored:
        return scored
    ranked: list = []
    for i, entry in enumerate(scored):
        if i == 0:
            rank = 1
        elif math.isclose(entry["score"], scored[i - 1]["score"], rel_tol=1e-9, abs_tol=1e-9):
            # Treat float-equal scores as a genuine tie (avoids last-bit summation
            # differences splitting a mathematically tied pair into ranks 1 and 2).
            rank = ranked[i - 1]["rank"]
        else:
            rank = i + 1
        ranked.append({**entry, "rank": rank})
    return ranked


def _effective_value(raw: float, direction: str) -> float:
    """Apply direction inversion: lower-is-better → (100 - raw)."""
    return (100.0 - raw) if direction == "lower-is-better" else raw


# ── Sprint 1 methods ──────────────────────────────────────────────────────────

def weighted_sum(
    active_options: list,
    criteria: list,
    score_matrix: dict,
) -> list:
    """Compute weighted-sum scores for each active option.

    score_matrix[opt_id][crit_id] = float (confidence_adjusted or mean value).

    For direction == "lower-is-better", the value is inverted via (100 - value)
    before weighting.

    Returns a list of {"option": id, "score": float, "rank": int} sorted by
    score descending.  Ties share the lowest rank number among equals.
    """
    normed = normalize_weights(criteria)
    crit_directions: dict = {c["id"]: c.get("direction", "higher-is-better") for c in criteria}

    scored: list = []
    for opt_id in active_options:
        opt_scores = score_matrix.get(opt_id, {})
        total_score = 0.0
        for crit in criteria:
            cid = crit["id"]
            raw = float(opt_scores.get(cid, 0.0))
            effective = _effective_value(raw, crit_directions[cid])
            total_score += effective * normed[cid]
        scored.append({"option": opt_id, "score": total_score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return _assign_ranks(scored)


# ── Sprint 2 methods ──────────────────────────────────────────────────────────

def pugh_matrix(
    active_options: list,
    criteria: list,
    score_matrix: dict,
    baseline_id: Union[str, None] = None,
) -> list:
    """Classic Pugh concept selection matrix.

    For each option, compare its direction-adjusted value to the baseline's on
    each criterion:  +1 if better, -1 if worse, 0 if equal.  Sum gives the
    Pugh score (unweighted counts — classic Pugh convention).

    baseline_id defaults to the weighted_sum rank-1 option when None.

    Returns list of {"option", "score", "rank"} sorted desc.  Ties share the
    lowest rank number.

    Design note: Classic Pugh uses unweighted +1/0/-1 counts.  Weighted Pugh
    (multiply each vote by the normalized criterion weight) is a common
    extension but changes the method semantics; use weighted_sum for that.
    """
    if baseline_id is None:
        ws = weighted_sum(active_options, criteria, score_matrix)
        baseline_id = ws[0]["option"]

    crit_directions = {c["id"]: c.get("direction", "higher-is-better") for c in criteria}
    baseline_scores = score_matrix.get(baseline_id, {})

    scored: list = []
    for opt_id in active_options:
        if opt_id == baseline_id:
            scored.append({"option": opt_id, "score": 0})
            continue
        opt_scores = score_matrix.get(opt_id, {})
        total = 0
        for crit in criteria:
            cid = crit["id"]
            direction = crit_directions[cid]
            eff_opt = _effective_value(float(opt_scores.get(cid, 0.0)), direction)
            eff_base = _effective_value(float(baseline_scores.get(cid, 0.0)), direction)
            if eff_opt > eff_base:
                total += 1
            elif eff_opt < eff_base:
                total -= 1
            # equal → 0
        scored.append({"option": opt_id, "score": total})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return _assign_ranks(scored)


def topsis(
    active_options: list,
    criteria: list,
    score_matrix: dict,
) -> list:
    """TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution).

    Algorithm:
      1. Apply direction adjustment (lower-is-better → 100 - value).
      2. Vector-normalize each criterion column.
      3. Apply normalized weights to get weighted normalized matrix.
      4. Identify positive ideal solution (PIS, max per column) and
         negative ideal solution (NIS, min per column).
      5. Compute Euclidean distances D+ (to PIS) and D- (to NIS).
      6. Closeness coefficient C = D- / (D+ + D-); range [0, 1].
      7. Rank by C descending.

    Returns list of {"option", "score" (= C), "rank"} sorted desc.

    Edge case: when D+ + D- == 0 (all options identical on all criteria),
    C is set to 0.5 for all options so ranking is stable.
    """
    normed_weights = normalize_weights(criteria)
    crit_ids = [c["id"] for c in criteria]
    crit_directions = {c["id"]: c.get("direction", "higher-is-better") for c in criteria}

    # Step 1: build direction-adjusted matrix
    adj: dict = {}
    for opt_id in active_options:
        opt_scores = score_matrix.get(opt_id, {})
        adj[opt_id] = {}
        for cid in crit_ids:
            raw = float(opt_scores.get(cid, 0.0))
            adj[opt_id][cid] = _effective_value(raw, crit_directions[cid])

    # Step 2: vector-normalize each column
    col_norms: dict = {}
    for cid in crit_ids:
        sq_sum = sum(adj[opt][cid] ** 2 for opt in active_options)
        col_norms[cid] = math.sqrt(sq_sum) if sq_sum > 0 else 1.0

    vn: dict = {}
    for opt_id in active_options:
        vn[opt_id] = {cid: adj[opt_id][cid] / col_norms[cid] for cid in crit_ids}

    # Step 3: weighted normalized matrix
    wn: dict = {}
    for opt_id in active_options:
        wn[opt_id] = {cid: vn[opt_id][cid] * normed_weights[cid] for cid in crit_ids}

    # Step 4: PIS and NIS
    pis = {cid: max(wn[opt][cid] for opt in active_options) for cid in crit_ids}
    nis = {cid: min(wn[opt][cid] for opt in active_options) for cid in crit_ids}

    # Steps 5–6: distances and closeness
    scored: list = []
    for opt_id in active_options:
        d_pos = math.sqrt(sum((wn[opt_id][cid] - pis[cid]) ** 2 for cid in crit_ids))
        d_neg = math.sqrt(sum((wn[opt_id][cid] - nis[cid]) ** 2 for cid in crit_ids))
        denom = d_pos + d_neg
        closeness = d_neg / denom if denom > 0 else 0.5
        scored.append({"option": opt_id, "score": closeness})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return _assign_ranks(scored)


def ahp_weights(pairwise: list, criteria_ids: list) -> dict:
    """AHP weight derivation via geometric-mean eigenvector approximation.

    Computes the geometric mean of each row, then normalises to get priority
    weights summing to 1.  This is a well-known fast approximation to the
    exact eigenvector method; error is negligible for n ≤ 7.

    Args:
        pairwise: n×n list of lists.  pairwise[i][j] = how much more important
                  criterion i is than criterion j (reciprocal scale).
        criteria_ids: list of criterion ids corresponding to matrix rows/cols.

    Returns:
        {criterion_id: weight} summing to 1.

    Also see: ahp_consistency_ratio()
    """
    n = len(pairwise)
    # Geometric mean of each row
    geo_means = []
    for row in pairwise:
        product = 1.0
        for val in row:
            product *= float(val)
        geo_means.append(product ** (1.0 / n))

    total = sum(geo_means)
    weights = {criteria_ids[i]: geo_means[i] / total for i in range(n)}
    return weights


def ahp_consistency_ratio(pairwise: list) -> float:
    """Compute the AHP Consistency Ratio (CR).

    CR = CI / RI, where:
      CI = (lambda_max - n) / (n - 1)
      lambda_max ≈ sum of column sums × priority weight
      RI = random index (Saaty's table)

    CR < 0.1 is considered acceptably consistent.
    CR > 0.1 signals the pairwise judgments should be revised.

    Returns 0.0 for 1×1 or 2×2 matrices (always consistent by definition).
    """
    # Saaty's random index table (index = n-1, values for n=1..10)
    ri_table = [0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]

    n = len(pairwise)
    if n <= 2:
        return 0.0

    # Derive weights using geometric mean approximation
    criteria_ids = [str(i) for i in range(n)]
    weights = ahp_weights(pairwise, criteria_ids)
    w = [weights[str(i)] for i in range(n)]

    # Compute lambda_max: (A w)[i] / w[i] where (Aw)[i] = sum_j pairwise[i][j] * w[j]
    lambdas = []
    for i in range(n):
        aw_i = sum(float(pairwise[i][j]) * w[j] for j in range(n))
        lambdas.append(aw_i / w[i])
    lambda_max = sum(lambdas) / n

    ci = (lambda_max - n) / (n - 1)
    ri = ri_table[n - 1] if n - 1 < len(ri_table) else 1.49
    cr = ci / ri if ri > 0 else 0.0
    return float(cr)


def _product_score_method(
    active_options: list,
    score_matrix: dict,
    required_ids: list,
    formula_fn,
    method_name: str,
) -> list:
    """Generic helper for multiplicative/formula-based product-scoring methods.

    Validates required criterion ids are present, then applies formula_fn to
    each option's raw values.  Raises MethodError on missing fields or invalid
    values (e.g. zero denominator).
    """
    for opt_id in active_options:
        opt_scores = score_matrix.get(opt_id, {})
        for rid in required_ids:
            if rid not in opt_scores:
                raise MethodError(
                    f"{method_name}: option {opt_id!r} is missing required criterion {rid!r}"
                )

    scored: list = []
    for opt_id in active_options:
        opt_scores = score_matrix[opt_id]
        score = formula_fn(opt_id, opt_scores)
        scored.append({"option": opt_id, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return _assign_ranks(scored)


def rice_score(active_options: list, score_matrix: dict) -> list:
    """RICE prioritisation: score = reach * impact * confidence / effort.

    Required criterion ids (must be present in score_matrix[opt]):
      reach, impact, confidence, effort

    Raises MethodError if any required id is missing or if effort == 0.

    Uses raw score_matrix values directly (not 0-100 weighted).
    """
    required = ["reach", "impact", "confidence", "effort"]

    def formula(opt_id, scores):
        effort = float(scores["effort"])
        if effort == 0:
            raise MethodError(
                f"rice_score: option {opt_id!r} has effort=0; division by zero"
            )
        return float(scores["reach"]) * float(scores["impact"]) * float(scores["confidence"]) / effort

    return _product_score_method(active_options, score_matrix, required, formula, "rice_score")


def wsjf_score(active_options: list, score_matrix: dict) -> list:
    """WSJF (Weighted Shortest Job First): score = (ubv + tc + rr) / job_size.

    Required criterion ids:
      user_business_value, time_criticality, risk_reduction, job_size

    Raises MethodError if any required id is missing or if job_size == 0.
    """
    required = ["user_business_value", "time_criticality", "risk_reduction", "job_size"]

    def formula(opt_id, scores):
        job_size = float(scores["job_size"])
        if job_size == 0:
            raise MethodError(
                f"wsjf_score: option {opt_id!r} has job_size=0; division by zero"
            )
        return (
            float(scores["user_business_value"])
            + float(scores["time_criticality"])
            + float(scores["risk_reduction"])
        ) / job_size

    return _product_score_method(active_options, score_matrix, required, formula, "wsjf_score")


def ice_score(active_options: list, score_matrix: dict) -> list:
    """ICE prioritisation: score = impact * confidence * ease.

    Required criterion ids: impact, confidence, ease

    Raises MethodError if any required id is missing.
    """
    required = ["impact", "confidence", "ease"]

    def formula(opt_id, scores):
        return (
            float(scores["impact"])
            * float(scores["confidence"])
            * float(scores["ease"])
        )

    return _product_score_method(active_options, score_matrix, required, formula, "ice_score")


def kano_classify(active_options: list, score_matrix: dict) -> list:
    """Kano model classification and ranking.

    Criteria are identified by id prefix/suffix conventions:
      must_be*     → Must-be (threshold) criterion.  Options scoring < 50 on
                     any must_be criterion are penalised (score set to 0 for
                     that dimension and ranked last among failing options).
      performance* → Performance criterion.  Contributes linearly to score.
      delighter*   → Delighter criterion.  Contributes first (highest weight)
                     to enable options with strong delighters to rank above
                     those with high performance but no delight.

    Composite score = 2 * sum(delighter values) + 1 * sum(performance values)
    Options failing a must_be threshold (< 50) receive a large penalty (-1e9)
    so they sink to the bottom of the ranking regardless of other scores.

    Ranking: sorted desc by composite score, ties share lowest rank.

    Raises MethodError if no kano-tagged criteria are found in score_matrix
    (i.e. no key starting with must_be, performance, or delighter).
    """
    if not active_options:
        return []

    # Discover kano-tagged criterion ids from the first option's scores
    first_opt = active_options[0]
    all_crit_ids = list(score_matrix.get(first_opt, {}).keys())

    must_be_ids = [cid for cid in all_crit_ids if cid.startswith("must_be")]
    perf_ids = [cid for cid in all_crit_ids if cid.startswith("performance")]
    delighter_ids = [cid for cid in all_crit_ids if cid.startswith("delighter")]

    if not must_be_ids and not perf_ids and not delighter_ids:
        raise MethodError(
            "kano_classify: no kano-tagged criteria found; criterion ids must start "
            "with 'must_be', 'performance', or 'delighter'"
        )

    MUST_BE_THRESHOLD = 50.0
    DELIGHTER_WEIGHT = 2.0
    PERF_WEIGHT = 1.0
    FAIL_PENALTY = -1e9

    scored: list = []
    for opt_id in active_options:
        opt_scores = score_matrix.get(opt_id, {})

        # Check must_be threshold
        fails_must_be = any(
            float(opt_scores.get(cid, 0)) < MUST_BE_THRESHOLD
            for cid in must_be_ids
        )

        perf_sum = sum(float(opt_scores.get(cid, 0)) for cid in perf_ids)
        delighter_sum = sum(float(opt_scores.get(cid, 0)) for cid in delighter_ids)
        composite = DELIGHTER_WEIGHT * delighter_sum + PERF_WEIGHT * perf_sum

        if fails_must_be:
            composite += FAIL_PENALTY

        scored.append({"option": opt_id, "score": composite})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return _assign_ranks(scored)
