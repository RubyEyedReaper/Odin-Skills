# TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution)

## Formula

**Step 1 — Direction adjustment**

For each criterion C and option O:
```
effective(O, C) = raw(O, C)         if direction == "higher-is-better"
               = 100 - raw(O, C)   if direction == "lower-is-better"
```

**Step 2 — Vector normalization**

```
norm_col(C) = sqrt( sum_O( effective(O, C)^2 ) )
r(O, C)     = effective(O, C) / norm_col(C)
```

**Step 3 — Weighted normalized matrix**

```
v(O, C) = r(O, C) * w(C)    where w(C) is the normalized criterion weight
```

**Step 4 — Positive ideal (PIS) and negative ideal (NIS)**

```
PIS(C) = max_O( v(O, C) )   (best weighted-normalized value per column)
NIS(C) = min_O( v(O, C) )   (worst weighted-normalized value per column)
```

**Step 5 — Euclidean distances**

```
D+(O) = sqrt( sum_C( (v(O,C) - PIS(C))^2 ) )
D-(O) = sqrt( sum_C( (v(O,C) - NIS(C))^2 ) )
```

**Step 6 — Closeness coefficient**

```
C(O) = D-(O) / ( D+(O) + D-(O) )    ∈ [0, 1]
```

Rank by C descending.  C = 1 → identical to ideal.  C = 0 → identical to anti-ideal.

## When to Use

- When you want a multi-criteria ranking that accounts for both distance to the
  best outcome *and* distance from the worst outcome simultaneously.
- Especially useful when criteria have very different natural scales (the
  vector-normalization step removes scale differences before weighting).
- As a cross-check alongside weighted-sum; divergence between the two signals
  that the choice is sensitive to the aggregation method.

## Edge Cases

- **All options identical on all criteria**: every column norm is the same;
  D+ and D- both equal 0 for all options.  Implementation sets C = 0.5 so
  ranking remains stable (no division by zero).
- **Single option**: D+ = D- = 0; C = 0.5 by convention.
- **Zero-weight criterion**: contributes zero to the weighted normalized matrix;
  PIS and NIS are both 0 for that column, so it has no effect on distances.
- **All scores 0 on a criterion**: column norm = 0; normalized value = 0/1 = 0
  (implementation guards with `col_norm if col_norm > 0 else 1.0`).

## Worked Example

**3 options, 2 criteria (equal weight = 0.5 each)**

| Option | Perf (higher) | Cost (lower) |
|--------|--------------|-------------|
| A      | 80           | 20  → eff 80 |
| B      | 50           | 50  → eff 50 |
| C      | 20           | 80  → eff 20 |

Vector norms: Perf = sqrt(80²+50²+20²) = sqrt(9300) ≈ 96.44
              Cost = sqrt(80²+50²+20²) = 96.44  (symmetric in this example)

Weighted normalized (w=0.5 each):
  A: (0.415, 0.415)   B: (0.259, 0.259)   C: (0.104, 0.104)

PIS = (0.415, 0.415)   NIS = (0.104, 0.104)

D+(A) = 0,  D-(A) = sqrt(2*(0.311²)) ≈ 0.440  → C(A) = 1.0
D+(B) = sqrt(2*(0.156²)) ≈ 0.220, D-(B) ≈ 0.220  → C(B) = 0.5
D+(C) ≈ 0.440, D-(C) = 0  → C(C) = 0.0

Ranking: A(1.0) > B(0.5) > C(0.0)
