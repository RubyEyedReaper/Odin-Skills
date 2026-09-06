# The deferral record — field by field, and what each refusal catches

One file per deferral, in `.claude/docs/out-of-scope/`, named `OS-<YYYYMMDD>-<slug>.json`. The
directory's `README.md` is the anchor and is not a record.

**Only a deferral produces a record.** A `fix-now` verdict leaves the fix in the history, where git
owns it; a record duplicating that is a second opinion about a fact that already has one.

```json
{
  "id": "OS-20260903-pre-push-budget-uncompared",
  "recorded": "2026-09-03",
  "finding": "pre-push declares PRE_PUSH_BUDGET_MS a hard constraint, computes elapsed_ms, prints both and compares nothing",
  "found_while": "capturing pre-push timing measurements for a different item",
  "verdict": "defer",
  "reason": "The deciding input, in one line",
  "routed_to": {"roadmap": "harness:RM-0519", "issue": "952"},
  "resolved_by": null,
  "spec": { "…the decision-spec that produced the verdict, verbatim…" }
}
```

| Field | Required | Rule | What its refusal catches |
|---|---|---|---|
| `id` | yes | Matches the filename stem; `OS-` + 8 digits + a kebab slug | A record renamed without its id, so two copies read as two decisions |
| `recorded` | yes | `YYYY-MM-DD` | A record whose age cannot be read |
| `finding` | yes | Non-empty; states the defect in terms a reader who was not there can check | "Something was off" — a record that cannot be acted on later |
| `found_while` | yes | Non-empty; the work in flight when it surfaced | The out-of-scope claim with nothing to be out of scope *of* |
| `verdict` | yes | Exactly `defer` | A `fix-now` written to the store instead of being done |
| `reason` | yes | Non-empty, one line | A score with no human-readable deciding input |
| `routed_to` | yes | An object with at least one of `roadmap` (an item id) or `issue` (a number) | A deferral naming no owner — work that exists only in a file nobody reads |
| `blocked_by` | conditional | Required **only** when the recomputed winner is `fix-now`: `{"constraint": "<id>", "lifted_by": "<the event>"}` | A deferral the evidence contradicts, recorded as though the evidence agreed |
| `resolved_by` | no | `null`, or a commit sha this repository resolves | A closure asserted against a commit that does not exist |
| `spec` | yes | The complete decision-spec, exactly as scored | A verdict that cannot be recomputed, which is a verdict that cannot be audited |

## Forbidden keys, at any depth

`status`, `state`, `progress`, `parent`, `depth`.

The first three are refused for the reason `campaign` refuses a stored status (ADR-0113): it reads
identically whether it is current or six hours old. Closure here is `resolved_by` — a sha the tree
can verify — and openness is its absence, computed rather than stored.

`parent` and `depth` are refused because recursion is refused (SKILL.md § Recursion). A key that may
not appear is a predicate; a prose rule against recursion is not.

## The central predicate

> A deferral is either supported by its own score, or it names the bar that made fixing unavailable.

`out-of-scope-check.sh` re-runs `spec` through the `decision-matrix` engine and reads two things
from the result: the weighted-sum winner, and whether `fix-now` was **vetoed** by a constraint.

| Recomputation | `blocked_by` | Verdict |
|---|---|---|
| `defer` wins, `fix-now` not vetoed | absent | Clean |
| `defer` wins, `fix-now` not vetoed | present | **Finding.** The record claims a bar the spec does not encode. A bar belongs in `constraint_results`, where it is scored |
| `fix-now` vetoed | present, naming a constraint the result actually vetoed on, with a non-empty `lifted_by` | Clean — fixing was unavailable, and the event that lifts it is on record |
| `fix-now` vetoed | absent | **Finding.** The record reads as though the evidence favoured deferring, when the field was simply smaller |
| `fix-now` wins, not vetoed | any | **Finding.** The evidence favoured fixing and the work was deferred anyway |

The last row is the whole reason the spec is embedded rather than summarised. A hand-written
verdict, a copied record, or weights edited after the fact all land there. The two middle rows exist
because a veto is the only honest way to say fixing was unavailable: it shrinks the field, and a
winner that beat a smaller field must say so.

## Re-scoring later

A record is not immutable — the point of embedding a re-runnable spec is that a call can be
revisited when the weights or the facts change. Append a second record rather than editing the
first, cite the earlier `id` in the new `reason`, and let both stand: a reversal that erases what it
reverses is indistinguishable from a decision nobody ever made.
