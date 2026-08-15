---
name: decision-matrix
description: >-
  Use when choosing between options or prioritizing — "decide", "choose between", "which should I
  pick", "compare options", "trade-off", "which library/framework/database/vendor", "build vs buy",
  "best option for", "prioritize", "rank these", "RICE/WSJF". A quantitative weighted-decision
  engine: scores options against weighted criteria with multiple methods (weighted-sum, Pugh,
  TOPSIS/AHP, RICE/WSJF/ICE/Kano), runs sensitivity analysis, flags when methods disagree, applies
  hard-constraint vetoes, aggregates multiple scorers, and records a numbered DEC decision. Fire this
  for ANY non-trivial multi-option choice or prioritization, even a mid-task internal fork — the math
  is deterministic and the decision is recorded. Not for qualitative-only trade-off framing
  (use decision-mapping) or stochastic rollout search (use recursive-decision-ledger).
version: 0.2.0
user-invocable: true
argument-hint: "[decision to make, e.g. 'which database for a tight-budget SaaS']"
license: Apache 2.0
metadata:
  origin: Odin
allowed-tools:
  - Bash(python3 -m scripts.score *)
  - Bash(python -m scripts.score *)
  - Bash(node *)
---

# Decision Matrix — quantitative weighted-decision engine

Turn a choice into a deterministic, recorded decision. The agent elicits and frames; **the script does
all math** (scoring, sensitivity, ties, aggregation). Never compute scores by hand — if the script
errors, surface it and stop; do not guess.

**Decide, do not ask.** A fork that reaches this skill is the agent's to resolve. Score it, record the
DEC, report the winner and the deciding reason in one line, and keep working. Handing the user a menu
of options is the failure this skill exists to prevent (`.claude/rules/common/decision-authority.md`).

## Workflow

1. **Frame** — restate the decision goal in one line, and its reversibility (`two-way` / `one-way`).
   A one-way door with a non-low-confidence winner gets promoted to an ADR at the end.
2. **Options** — 2+ real alternatives. "Do nothing" is a legitimate option and usually belongs in the
   set. If you cannot state what distinguishes two options, they are one option.
3. **Criteria + weights** — propose criteria with default weights (0–100); flag if one criterion
   dominates (>60% of weight). Mark each `higher-is-better` or `lower-is-better`.
4. **Constraints** — hard disqualifiers, captured *before* scoring. A vetoed option is eliminated
   regardless of how well it scores; that is the point of a constraint rather than a heavy weight.
5. **Score** — 0–100 per option × criterion, per scorer. Elicit them the way `grilling` elicits
   anything: **one at a time, always with a recommended value and its reasoning, and by reading the
   codebase instead of asking whenever the answer is on disk.** See
   [references/elicitation.md](references/elicitation.md).
6. **Run** — serialize to a decision spec JSON and run the engine:
   `python3 -m scripts.score --spec <spec.json> --record`.
7. **Present** — the scored matrix, the ranked recommendation, disagreement/fragility, the HTML
   artifact, and the recorded `DEC-####`. Say plainly that the decision is reversible by re-running
   with different weights.

## Engine interface

- Input: decision-spec JSON (`references/decision-spec-schema.md`).
- Run: `python3 -m scripts.score [--spec <path>] [--record]` from this skill directory; JSON spec on
  stdin if `--spec` omitted. Result JSON to stdout; errors to stderr with exit 1.
- `--record` writes `DEC-####-<slug>.md` under `.claude/docs/decisions/` and upserts the ledger index.
  Without it, nothing is written — a decision worth making is worth recording, so default to recording.
- Visual: `node scripts/visual.mjs <result.json>` → self-contained HTML to stdout.

**The engine refuses an incomplete spec on purpose.** A missing score is a question nobody answered;
filling it with a plausible number launders a guess as arithmetic.

## Method selection

The engine runs every applicable method and compares them; **method disagreement is a headline
signal**, not an error. Default winner = weighted-sum rank 1, cross-checked against the others.

| Decision shape | Methods emphasized |
|---|---|
| Few options, clear weighted criteria | weighted-sum, TOPSIS |
| Compare against an incumbent/baseline | Pugh matrix |
| Prioritize a backlog | RICE / WSJF / ICE |
| Feature satisfaction tiers | Kano |

## Reading the result

| Signal | What it means | What to do |
|---|---|---|
| Methods disagree on rank 1 | The winner depends on the aggregation, not the evidence | Report both; pick the reversible option |
| `near_tie_pairs` includes the winner | The lead is inside the noise | Say so; decide on a tiebreaker criterion and name it |
| `criteria_quality.warnings` → `overweight` | One criterion is the decision | Either accept that explicitly, or rebalance and re-run |
| `non-discriminating` criterion | It scores every option alike | Drop it — it adds arithmetic, not information |
| All options vetoed | The constraints are the real decision | Report the binding constraint; do not relax one silently |
| `promote_to_adr_hint` true | One-way door, decided with confidence | Write the ADR (`architecture-decision-records`) |

## Hand-offs

| Situation | Next |
|---|---|
| Options and criteria are still fuzzy | `decision-mapping` first, then come back to score |
| Prioritizing roadmap items | `roadmap prioritize --export` → score → `roadmap prioritize --from` |
| Criteria need an interview to pin down | `grilling` / `grill-with-docs` |
| Winner is irreversible | `architecture-decision-records` — promote the DEC to an ADR |
| The chosen option is a multi-PR effort | `blueprint`, then register its steps in `roadmap` |
| Problem needs rollout search, not scoring | `recursive-decision-ledger` |

A DEC produced while prioritizing lands on each roadmap item as `priority.dec`, so the ordering in
`roadmap next` carries the audit trail of why it is ordered that way.

## Failure modes

- **Scoring to a predetermined winner.** If you already know the answer, say so and skip the theatre;
  a rigged matrix is worse than an opinion, because it looks like evidence.
- **Criteria that are really one criterion.** Three flavours of "developer experience" triple that
  concern's weight silently. The `redundant` warning catches labels, not synonyms — you catch synonyms.
- **Constraints entered as heavy weights.** A must-have is a veto. A 90-weight criterion still lets a
  strong option win without it.
- **Stopping to ask which option to take.** See the top of this file.
- **Not recording.** An unrecorded decision gets re-litigated in three weeks with none of the reasoning.

## Related skills

- `decision-mapping` — qualitative trade-off framing (use first to surface criteria; this skill scores them).
- `recursive-decision-ledger` — stochastic rollout search; this skill reuses its numbered-ledger notion (`DEC-####`).
- `architecture-decision-records` — promote an irreversible DEC to a full ADR.
- `roadmap` — owns the prioritization hand-off in both directions.
