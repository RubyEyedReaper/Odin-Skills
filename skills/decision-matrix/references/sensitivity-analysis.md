# Sensitivity Analysis for Decision Matrices

Sensitivity analysis answers: *how much would the inputs have to change before
we'd pick a different option?*  A recommendation robust to large input changes
is worth acting on; one that flips with a 5% weight shift deserves more scrutiny.

---

## Break-even Analysis

**Question**: For each criterion, by how many percentage points must its
normalized weight increase before the current winner loses rank 1?

**Algorithm**:

1. For each criterion C:
   a. Start from the current normalized weight `w(C)`.
   b. Increment `w(C)` by `weight_step` (default 1%) and deflate all other
      criteria proportionally so weights still sum to 1.
   c. Re-run weighted_sum with the perturbed weights.
   d. If the winner is dethroned, record the cumulative shift and the new
      rank-1 option.
2. If no flip is found across the full range, record `None`.

**Output** per criterion:
```json
{
  "weight_shift_to_flip_pct": 12.5,   // or null if no flip found
  "favors_if_flipped": "option-b"     // or null
}
```

**Interpretation**:
- `weight_shift_to_flip_pct < 10` → fragile; reconsider or gather more data.
- `weight_shift_to_flip_pct = null` → robust; winner dominates regardless of
  how much that criterion is weighted up.

---

## Tornado Chart Data

**Question**: Which criteria have the largest effect on the winner's score when
their weights are perturbed?

**Algorithm**:

For each criterion C:
1. Compute `score_high`: winner's score when C's weight is scaled up by
   `perturbation_pct` (default 20%), with other weights deflated proportionally.
2. Compute `score_low`: winner's score when C's weight is scaled down by 20%.
3. `swing_impact = |score_high - score_low|`

Results are sorted by `swing_impact` descending.  The top bars of the tornado
chart are the criteria the decision is most sensitive to.

**Output** per criterion:
```json
{
  "criterion": "relational-fit",
  "swing_impact": 8.3,
  "baseline_rank_of_winner": 1,
  "perturbed_rank_of_winner": 1
}
```

When `perturbed_rank_of_winner > 1` the winner actually lost rank 1 under the
perturbation — a stronger signal than a large swing alone.

---

## Fragility Flag

**Definition**: A recommendation is *fragile* when any criterion's
`weight_shift_to_flip_pct` is ≤ `fragile_threshold_pct` (default 10 pp).

```python
fragile, reason = fragility_flag(break_even, fragile_threshold_pct=10.0)
```

The threshold is inclusive: a shift of exactly 10 pp is still flagged as
fragile.  Callers can tighten (5 pp) or relax (20 pp) the threshold to match
the team's appetite for weight uncertainty.

**In the recommendation block**:
- Fragile + methods agree → `confidence = "medium"` with a caveat.
- Fragile + methods disagree → `confidence = "low"` with two caveats.

---

## Disagreement Report

**Question**: Do all scoring methods agree on who should win?

```python
report = disagreement_report(method_results)
# {
#   "methods_agree": bool,
#   "winner_by_method": {"weighted-sum": "A", "topsis": "B"},
#   "disagreement_pairs": [{"methods": ["weighted-sum","topsis"], "winners": ["A","B"]}]
# }
```

**When methods disagree**:
- The two methods are emphasizing different aspects of the data.
- Common cause: weighted-sum uses additive aggregation; TOPSIS penalizes
  distance to the anti-ideal; Pugh uses the rank-1 option as baseline.
- Investigate which criterion drives the difference, then revisit weights or
  scores before deciding.

**Worked example** — architecture-pattern fixture:

| Method       | Winner          | Notes                                         |
|--------------|-----------------|-----------------------------------------------|
| weighted-sum | monolith        | Lowest operational burden dominates           |
| pugh         | monolith        | Baseline is weighted-sum winner; itself scores 0 |
| TOPSIS       | modular-services| Balanced distance to ideal and anti-ideal     |

Disagreement between weighted-sum/pugh and TOPSIS here signals that
`monolith`'s strong performance on operational-burden pulls it ahead in
additive models, but `modular-services` is geometrically closer to the ideal
profile across all four criteria simultaneously.

---

## Interpretation Guide

| Signal                              | Confidence | Recommended action              |
|-------------------------------------|------------|---------------------------------|
| All methods agree, not fragile      | High       | Proceed with recommendation     |
| Methods agree, fragile              | Medium     | Gather more data on flip criterion |
| Methods disagree, not fragile       | Medium     | Understand method divergence    |
| Methods disagree, fragile           | Low        | Do not decide yet; recalibrate  |
| Winner in near-tie (< threshold)    | Low        | Consider additional criteria    |
