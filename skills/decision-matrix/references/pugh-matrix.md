# Pugh Matrix (Concept Selection Matrix)

## Formula

For each option O (excluding the baseline B), and for each criterion C:

```
vote(O, C) = +1  if effective(O, C) > effective(B, C)
             -1  if effective(O, C) < effective(B, C)
              0  if equal

pugh_score(O) = sum of vote(O, C) over all criteria
pugh_score(B) = 0  (baseline is the reference, always 0)
```

Where `effective(opt, crit)` applies direction adjustment:
- `higher-is-better`: effective = raw value
- `lower-is-better`:  effective = 100 − raw value

## Weighted vs Unweighted

Classic Pugh uses **unweighted** +1/0/-1 counts.  This implementation follows
the classic convention.  A weighted extension multiplies each vote by the
criterion's normalized weight; that variant collapses toward weighted-sum and
is usually not worth the added complexity.

## When to Use

- Early-stage concept screening with 3–8 options.
- When you want a transparent, auditable, criterion-by-criterion comparison
  against a known reference (existing solution, industry standard, best option).
- As a sanity-check alongside weighted-sum: if they disagree, investigate why.

## Baseline Selection

The baseline should be the current best option or the status quo.  When
`baseline_id` is `None`, the implementation defaults to the `weighted_sum`
rank-1 option, making the comparison self-referential but still useful for
revealing how far other options trail.

## Edge Cases

- **All criteria equal**: every option scores 0; result is a tie with baseline.
- **Single criterion**: Pugh collapses to a simple better/worse/equal judgment.
- **Baseline is weakest option**: all others score positive; choose a stronger
  baseline or interpret results cautiously.
- **Direction matters**: a lower-is-better score of 20 is *better* than 80;
  the effective value (80 vs 20) is used for comparison, not the raw value.

## Worked Example

**Goal**: Choose a database.  Baseline = MySQL.

| Criterion          | weight | direction         | PostgreSQL vs MySQL | MongoDB vs MySQL |
|--------------------|--------|-------------------|---------------------|------------------|
| Relational fit     | 35     | higher-is-better  | 95 > 85 → +1        | 30 < 85 → -1     |
| Ops complexity     | 20     | lower-is-better   | 35 < 30 → -1 (eff 65 < 70) | 40 > 30 → -1 (eff 60 < 70) |
| Ecosystem          | 20     | higher-is-better  | 90 > 80 → +1        | 75 < 80 → -1     |
| Scalability        | 15     | higher-is-better  | 65 > 60 → +1        | 85 > 60 → +1     |
| Cost               | 10     | lower-is-better   | 30 > 28 → -1 (worse) | 50 > 28 → -1     |

PostgreSQL Pugh score: +1 -1 +1 +1 -1 = **+1**
MongoDB Pugh score: -1 -1 -1 +1 -1 = **-3**
MySQL (baseline): **0**

PostgreSQL wins Pugh despite MySQL being the baseline.
