# Decision-Spec Schema Reference

Field-by-field documentation for the input spec JSON and the result JSON produced by
`scripts/score.py`. Sprint 1 implements `weighted-sum` only.

> Multi-scorer aggregation (`mean`/`std_dev` over N scorers), conflict detection, and the
> `multi_scorer_analysis` result field are documented in `references/multi-scorer.md` (Sprint 3).
> The DEC ledger, recall, and the `--record`/`prior_decisions`/`dec_record_path` result fields
> are documented inline in `SKILL.md` and `scripts/ledger.py`/`scripts/recall.py` (Sprint 4).

---

## Input Spec (`decision-spec.json`)

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `goal` | string | yes | Non-empty statement of what is being decided |
| `reversibility` | `"two-way"` \| `"one-way"` | yes | Whether the decision can be undone cheaply |
| `constraints` | `Constraint[]` | no | Hard requirements; options that fail any are vetoed |
| `options` | `Option[]` | yes | Min 2. The alternatives under consideration |
| `criteria` | `Criterion[]` | yes | Min 1. The dimensions on which options are scored |
| `scorers` | `Scorer[]` | yes | Min 1. Sprint 1: exactly 1 scorer |
| `methods` | `string[]` | yes | Scoring methods to apply. Sprint 1: `["weighted-sum"]` |
| `tie_threshold` | number | no | Percent of total score range within which two options are considered a near-tie. Default 5 |
| `decisions_dir` | string | no | Ledger this decision is recorded into. **Set it whenever the decision belongs to a project** — `projects/<name>/docs/decisions`. Relative paths resolve against the repository root, not the process CWD (the engine runs from the skill directory, so CWD names the skill). Omitted → the harness ledger `.claude/docs/decisions`. `--decisions-dir` overrides it. |

---

### `Constraint`

```json
{
  "id": "open-source",
  "description": "Must be open-source or have a free tier",
  "lifted_by": "The vendor's Q3 licence change, which adds a free tier"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique slug, referenced in `option.constraint_results` |
| `description` | string | Human-readable requirement |
| `lifted_by` | string, optional | The event that would remove this requirement, recorded into every DEC a veto by it produces |

**Why `lifted_by` cannot be derived.** A vetoed option means the winner beat a *smaller field*,
so a record that names the constraint but not what would lift it is not re-runnable. That
condition is an event **outside** the decision — an issue closing, a budget review, a dependency
shipping — and no traversal of `{id, description}` produces it. A sentence computed from the
description ("lifts when the option satisfies the constraint") restates the veto in future tense
and asserts nothing, while reading as though it carries information. Left undeclared, the record
says so plainly instead.

Constraint ids are **not** cross-checked against `option.constraint_results`: an id answered
there but never declared here is accepted, and is reported with a null description rather than
an invented one.

---

### `Option`

```json
{
  "id": "postgres",
  "label": "PostgreSQL",
  "description": "Battle-tested relational DB",
  "constraint_results": {
    "open-source": true,
    "managed-cloud": true
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | URL-safe slug, unique within the spec |
| `label` | string | yes | Display name |
| `description` | string | no | Optional longer description |
| `constraint_results` | `{[constraint_id]: boolean}` | no | Map of constraint id → pass/fail. Any `false` vetoes the option |

---

### `Criterion`

```json
{
  "id": "relational-fit",
  "label": "Relational Query Fit",
  "weight": 35,
  "direction": "higher-is-better",
  "description": "How well the DB supports complex joins"
}
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | string | unique | Slug used as score matrix key |
| `label` | string | | Display name |
| `weight` | number | `[0, 100]` | Relative importance; normalized internally to proportions summing to 1.0 |
| `direction` | `"higher-is-better"` \| `"lower-is-better"` | | Whether a higher raw score is beneficial. `lower-is-better` scores are inverted via `100 - value` before weighting |
| `description` | string | optional | Clarifies what is being measured |

**Quality warnings** (non-fatal, surface in `criteria_quality.warnings`):
- `overweight` — normalized weight > 60 %
- `zero-weight` — weight == 0 (criterion has no influence)
- `redundant` — duplicate `label` across criteria
- `non-discriminating` — all options share the same score for this criterion

---

### `Scorer`

```json
{
  "id": "engineering-team",
  "label": "Engineering Team",
  "scores": {
    "postgres": {
      "relational-fit": {"value": 95, "confidence": 0.95},
      "ops-complexity":  {"value": 35, "confidence": 0.85}
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique slug |
| `label` | string | Display name |
| `scores` | `{[option_id]: {[criterion_id]: ScoreEntry}}` | Complete score matrix; every active option × criterion pair must be present |

#### `ScoreEntry`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `value` | number | `[0, 100]` | Raw score on this criterion |
| `confidence` | number | `[0, 1]`, optional | Scorer's confidence in the value. Defaults to `1.0` if absent. Scales the effective score: `confidence_adjusted = value × confidence` |

---

## Result JSON

Emitted to **stdout** on success by `python3 -m scripts.score`.  
Emitted to **stderr** (with `exit 1`) on validation or runtime error.

```json
{
  "schema_version": "1",
  "vetoed_options": ["audit-log"],
  "active_options": ["csv-export", "bulk-actions", "saved-filters"],
  "aggregated_scores": {
    "csv-export": {
      "customer-demand": {
        "mean": 85.0,
        "std_dev": 0.0,
        "confidence_adjusted": 76.5
      }
    }
  },
  "criteria_quality": {
    "warnings": [
      {
        "type": "overweight",
        "criterion": "customer-demand",
        "message": "criterion 'customer-demand' has normalized weight 40%, dominating other criteria"
      }
    ]
  },
  "method_results": {
    "weighted-sum": {
      "ranking": [
        {"option": "csv-export", "score": 74.2, "rank": 1},
        {"option": "bulk-actions", "score": 71.8, "rank": 2},
        {"option": "saved-filters", "score": 70.1, "rank": 3}
      ]
    }
  },
  "ties": {
    "near_tie_pairs": [
      {
        "options": ["bulk-actions", "saved-filters"],
        "gap": 1.7,
        "threshold": 4.05
      }
    ]
  },
  "recommendation": {
    "winner": "csv-export",
    "winner_label": "CSV Export",
    "rationale": "CSV Export ranks first by weighted-sum across 4 criteria",
    "confidence": "medium",
    "caveats": []
  }
}
```

### Result fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | `"1"` | Schema version for forward compatibility |
| `vetoed_options` | `string[]` | Option ids eliminated by constraint failures |
| `veto_reasons` | `VetoReason[]` | Which constraint eliminated each vetoed option, in option order. `[]` when nothing was vetoed |
| `active_options` | `string[]` | Option ids that passed all constraints |
| `aggregated_scores` | object | Per-option, per-criterion aggregation. Sprint 1 (1 scorer): `mean == value`, `std_dev == 0.0`, `confidence_adjusted == value * confidence` |
| `criteria_quality.warnings` | `Warning[]` | Non-fatal quality signals about the criteria design |
| `method_results["weighted-sum"].ranking` | `RankEntry[]` | Sorted descending by score; ties share the lowest rank number among equals |
| `ties.near_tie_pairs` | `TiePair[]` | Pairs whose score gap ≤ `tie_threshold` % of the total score range |
| `recommendation.winner` | `string \| null` | Id of the rank-1 option, or `null` if all options were vetoed |
| `recommendation.confidence` | `"low" \| "medium" \| "high"` | `"low"` when winner is in a near-tie pair; `"medium"` otherwise (Sprint 1) |
| `recommendation.caveats` | `string[]` | Auto-generated cautions (near-tie notices, etc.) |

#### `VetoReason`

One entry per vetoed option — an option that passed is **absent**, never an empty entry, so
there is exactly one way to say "not vetoed". `[o["option"] for o in veto_reasons]` equals
`vetoed_options`, order included.

| Field | Description |
|---|---|
| `option` | Option id, in `spec.options` order |
| `option_label` | Display name, falling back to the id |
| `constraints` | The constraints this option failed: declared `spec.constraints` order first, then ids answered but never declared |
| `constraints[].id` | Constraint id — the machine handle a re-run needs |
| `constraints[].description` | The requirement, or `null` when the id was never declared in `spec.constraints` |
| `constraints[].lifted_by` | The declared expiry condition, or `null` |

The veto predicate is identity-strict: only `false` vetoes, so `0`, `"false"` and `null` in
`constraint_results` do not. An **unanswered** constraint is a pass — `constraint_results` may
be partial, and an option that never answered a constraint is active. The record's veto section
therefore names what failed, and never implies that every other option answered everything.

#### `Warning`

| Field | Description |
|---|---|
| `type` | `"overweight"` \| `"zero-weight"` \| `"redundant"` \| `"non-discriminating"` |
| `criterion` | Criterion id the warning applies to |
| `message` | Human-readable explanation |

#### `RankEntry`

| Field | Description |
|---|---|
| `option` | Option id |
| `score` | Weighted-sum score (0–100 scale, float) |
| `rank` | 1-based rank; tied options share the lowest rank number in their group |

#### `TiePair`

| Field | Description |
|---|---|
| `options` | Two-element array of option ids |
| `gap` | Absolute score difference |
| `threshold` | The tie_threshold converted to points for this run |

---

## Worked Example

### Input

```json
{
  "goal": "Pick a cache layer for the API",
  "reversibility": "two-way",
  "constraints": [],
  "options": [
    {"id": "redis",     "label": "Redis"},
    {"id": "memcached", "label": "Memcached"}
  ],
  "criteria": [
    {"id": "features", "label": "Feature Set",      "weight": 60, "direction": "higher-is-better"},
    {"id": "ops",      "label": "Ops Simplicity",   "weight": 40, "direction": "higher-is-better"}
  ],
  "scorers": [
    {
      "id": "s1", "label": "Team",
      "scores": {
        "redis":     {"features": {"value": 90, "confidence": 1.0}, "ops": {"value": 70, "confidence": 1.0}},
        "memcached": {"features": {"value": 50, "confidence": 1.0}, "ops": {"value": 85, "confidence": 1.0}}
      }
    }
  ],
  "methods": ["weighted-sum"],
  "tie_threshold": 5
}
```

### Manual calculation

Normalized weights: `features = 0.6`, `ops = 0.4`

Both criteria are `higher-is-better` — no inversion.

| Option | features contribution | ops contribution | total |
|---|---|---|---|
| redis | 90 × 0.6 = 54 | 70 × 0.4 = 28 | **82.0** |
| memcached | 50 × 0.6 = 30 | 85 × 0.4 = 34 | **64.0** |

Score range = 82 − 64 = 18.  Tie threshold = 5 % × 18 = 0.9.  Gap = 18 → not a near-tie.

### Expected result (abridged)

```json
{
  "schema_version": "1",
  "vetoed_options": [],
  "active_options": ["redis", "memcached"],
  "method_results": {
    "weighted-sum": {
      "ranking": [
        {"option": "redis",     "score": 82.0, "rank": 1},
        {"option": "memcached", "score": 64.0, "rank": 2}
      ]
    }
  },
  "ties": {"near_tie_pairs": []},
  "recommendation": {
    "winner": "redis",
    "winner_label": "Redis",
    "rationale": "Redis ranks first by weighted-sum across 2 criteria",
    "confidence": "medium",
    "caveats": []
  }
}
```
