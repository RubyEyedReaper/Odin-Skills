# Multi-Scorer Aggregation

When more than one scorer (interviewer, reviewer, stakeholder) rates the same option ×
criterion cells, the engine aggregates across all of them rather than reading just the
first scorer. A single scorer is the degenerate N=1 case of the same model — no special
casing is needed by callers.

---

## Aggregation Model

For each `option × criterion` cell, collect the `value` and `confidence` from every
scorer's entry (confidence defaults to `1.0` when absent), then compute:

| Field | Formula | Notes |
|---|---|---|
| `mean` | population mean of raw `value` across scorers | |
| `std_dev` | population standard deviation of raw `value` across scorers (`statistics.pstdev`) | `0.0` for a single scorer |
| `confidence_adjusted` | mean of `(value × confidence)` across scorers | feeds the score matrix used by every method |

```python
from scripts.aggregation import aggregate_scores

aggregated = aggregate_scores(spec)
# aggregated["postgres"]["relational-fit"] ==
#   {"mean": 88.3, "std_dev": 6.2, "confidence_adjusted": 81.7}
```

`scripts/score.py` builds `score_matrix[opt][crit] = confidence_adjusted` exactly as
before — multi-scorer aggregation is transparent to every downstream method
(weighted-sum, Pugh, TOPSIS, RICE/WSJF/ICE/Kano).

**Why population std_dev, not sample std_dev**: the scorers present in the spec are
treated as the complete population of opinions being aggregated for this decision, not
a sample drawn from a larger population. `statistics.pstdev` (divides by N) is used
instead of `statistics.stdev` (divides by N-1).

---

## Conflict Detection

A cell is flagged as a **conflict** when scorers disagree enough that the aggregated
number is hiding a real difference of opinion.

```python
from scripts.aggregation import conflict_detect

conflicts = conflict_detect(spec, conflict_threshold_std=25.0)
# [{"option": "postgres", "criterion": "ops-complexity", "std_dev": 28.4,
#   "scorer_values": {"alice": 90, "bob": 40, "carol": 35}}, ...]
```

- Threshold is on the **raw value** std_dev (0–100 scale), default `25.0` — roughly
  "scorers are a quarter of the scale apart on average."
- Requires at least 2 scorers; with 0 or 1 scorer, `conflict_detect` always returns `[]`.
- `scorer_values` preserves every scorer's raw value for the cell so the conflict can
  be inspected and discussed directly, not just summarized.

**In the result JSON**: surfaced as `multi_scorer_analysis.conflicts`. If any conflict
cell involves the recommended winner, `scripts/score.py` appends a caveat to
`recommendation.caveats` and caps `recommendation.confidence` at `"medium"` (even if
the rest of the signal — agreement across methods, no fragility, no near-tie — would
otherwise justify `"high"`). A conflicted winner is not a confidently recommended
winner; the disagreement needs to be resolved or explicitly accepted first.

---

## Scorer Variance Summary

Beyond per-cell conflicts, it's useful to know whether one *scorer* is consistently out
of step with the rest of the group across the whole matrix — a calibration issue rather
than a one-off disagreement.

```python
from scripts.aggregation import scorer_variance_summary

summary = scorer_variance_summary(spec)
# {"alice": 4.1, "bob": 22.7, "carol": 5.3, "outliers": ["bob"]}
```

- For each scorer, compute the mean absolute deviation of that scorer's values from the
  per-cell group mean, averaged across every option × criterion cell.
- A scorer is an **outlier** when its mean absolute deviation exceeds `1.5×` the median
  deviation across all scorers (a simple, dependency-free analogue of an IQR-style
  outlier rule).
- With a single scorer, deviation is `0.0` and `outliers` is always `[]` — there is
  nothing to compare against.

Outliers are a prompt to ask *why*: a scorer rating everything systematically higher or
lower may be using a different scale, weighting a sub-criterion the others aren't, or
simply have a different risk appetite. It does not automatically mean their input should
be discounted.

---

## Worked Example

Three scorers rate two database options on `ops-complexity` (`lower-is-better`, raw
0–100 = "how complex," inverted before weighting):

| Scorer | postgres | dynamodb |
|---|---|---|
| alice | 35 | 20 |
| bob | 70 | 25 |
| carol | 40 | 15 |

```python
aggregated = aggregate_scores(spec)["postgres"]["ops-complexity"]
# mean = 48.33, std_dev ≈ 15.5, confidence_adjusted ≈ 46.0 (confidence ~0.95 avg)

conflicts = conflict_detect(spec, conflict_threshold_std=15.0)
# flags postgres/ops-complexity: std_dev 15.5 > 15.0
#   scorer_values: {"alice": 35, "bob": 70, "carol": 40}
```

Bob rates `postgres` operational complexity roughly double what Alice and Carol do.
`scorer_variance_summary` would likely also flag `bob` as an outlier if this pattern
holds across other criteria too — worth a quick conversation before trusting the
aggregated number on its own.

If `postgres` is the recommended winner, the conflict on `ops-complexity` surfaces as a
caveat and the recommendation confidence is capped at `"medium"` until the disagreement
is resolved.
