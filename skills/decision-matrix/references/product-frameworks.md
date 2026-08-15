# Product Prioritization Frameworks

Three lightweight formulas for ranking features/options without constructing a full
weighted criteria matrix.  All three read raw metric values directly from the
score_matrix (not 0-100 weighted scores).

---

## RICE

**Formula**: `score = reach × impact × confidence / effort`

| Field        | Criterion id  | Meaning                                               |
|--------------|---------------|-------------------------------------------------------|
| Reach        | `reach`       | Users or events affected per time period (raw count)  |
| Impact       | `impact`      | Per-user impact; Intercom scale: 0.25/0.5/1/2/3       |
| Confidence   | `confidence`  | Estimate certainty, 0-1 (e.g. 0.8 = 80% confident)   |
| Effort       | `effort`      | Person-months or person-weeks of engineering work     |

**When to use**: Feature backlog prioritization with heterogeneous options where
reach and impact vary widely.  The division by effort ensures big-effort items
are penalized even when they have high impact.

**Edge cases**:
- `effort = 0` → `MethodError` (division by zero; set minimum effort = 0.1).
- Very large `reach` values dominate; normalize reach to a consistent unit
  (e.g. users/quarter) across all options.
- `confidence` should be the same scale for all options; mixing 0-1 and
  0-100 scales will produce nonsense rankings.

**Worked example**:

| Feature       | Reach | Impact | Confidence | Effort | RICE   |
|---------------|-------|--------|------------|--------|--------|
| CSV Export    | 800   | 1      | 0.9        | 1      | 720    |
| Saved Filters | 600   | 2      | 0.8        | 2      | 480    |
| Audit Log     | 200   | 3      | 0.6        | 4      | 90     |

Winner: CSV Export (720).

---

## WSJF — Weighted Shortest Job First (SAFe)

**Formula**: `score = (user_business_value + time_criticality + risk_reduction) / job_size`

| Field                | Criterion id          | Meaning                                          |
|----------------------|-----------------------|--------------------------------------------------|
| User/Business Value  | `user_business_value` | Value delivered to users or business (1-10 scale)|
| Time Criticality     | `time_criticality`    | Urgency — cost of delay (1-10 scale)             |
| Risk Reduction       | `risk_reduction`      | Risk or opportunity enablement value (1-10 scale)|
| Job Size             | `job_size`            | Relative size (story points or T-shirt sizing)   |

**When to use**: SAFe or PI planning ceremonies where cost-of-delay decomposition
is already part of the team's vocabulary.  WSJF favours small, high-value work
and penalises large jobs even when valuable.

**Edge cases**:
- `job_size = 0` → `MethodError`.
- All three cost-of-delay components use the same relative scale (e.g. Fibonacci
  1/2/3/5/8/13); mixing scales invalidates comparisons.

**Worked example**:

| Feature       | UBV | TC | RR | Size | WSJF |
|---------------|-----|----|----|------|------|
| Feature A     | 8   | 5  | 3  | 4    | 4.00 |
| Feature B     | 5   | 8  | 5  | 8    | 2.25 |
| Feature C     | 3   | 2  | 1  | 1    | 6.00 |

Winner: Feature C (high value, very small).

---

## ICE

**Formula**: `score = impact × confidence × ease`

| Field      | Criterion id  | Meaning                                  |
|------------|---------------|------------------------------------------|
| Impact     | `impact`      | Expected outcome if it works (1-10)      |
| Confidence | `confidence`  | How sure you are it will work (1-10)     |
| Ease       | `ease`        | How easy it is to implement (1-10)       |

**When to use**: Fast team scoring sessions (growth experiments, A/B tests,
marketing campaigns).  All three dimensions use the same 1-10 scale; the
product is quick to compute mentally.

**vs RICE**: ICE does not include reach — it assumes all options reach
roughly the same audience.  Use RICE when audience size varies significantly.

**Edge cases**:
- No division; `MethodError` is raised only for missing fields.
- Extremely high `ease` can overpower low-confidence items; calibrate the
  scale consistently across options.

**Worked example**:

| Experiment     | Impact | Confidence | Ease | ICE  |
|----------------|--------|------------|------|------|
| Onboarding flow| 9      | 7          | 6    | 378  |
| Email drip     | 6      | 9          | 8    | 432  |
| Pricing page   | 8      | 5          | 4    | 160  |

Winner: Email drip (432).

---

## Kano Model Classification

Kano classifies feature attributes into three tiers that respond differently to
satisfaction:

| Tier        | Criterion id prefix | Satisfaction curve                      |
|-------------|---------------------|-----------------------------------------|
| Must-be     | `must_be`           | Absence causes dissatisfaction; presence is neutral |
| Performance | `performance`       | Linear — more is better                 |
| Delighter   | `delighter`         | Absence is neutral; presence delights   |

**Implementation scoring**:
```
composite(O) = 2 × sum(delighter values) + 1 × sum(performance values)
```
Options failing a must-be threshold (< 50) receive a large penalty (-1e9)
and rank last regardless of other scores.

**When to use**: Roadmap decisions where you want to distinguish hygiene
requirements (must-be) from differentiators (delighters) rather than treating
all criteria uniformly.

**Limitation**: This implementation uses a simple composite score as a proxy
for full Kano survey analysis.  Full Kano requires functional/dysfunctional
question pairs per customer segment.
