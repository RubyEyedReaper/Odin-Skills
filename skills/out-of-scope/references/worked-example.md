# Worked example — a real finding, scored end to end

The finding is real, the numbers are the engine's, and the repository's own handling of it is what
makes it worth reading.

## The finding

`.claude/scripts/pre-push` states at line 41 that the budget is a hard constraint, not a preference,
and names three gates excluded from the push set for cost alone. It computes `elapsed_ms`, prints it
beside `PRE_PUSH_BUDGET_MS`, and **never compares them**. `.claude/tests/pre-push-set.test.sh` checks
only the *declared* total — the sum of the per-entry cost comments — so the gate verifies the
arithmetic of a table nobody re-measures.

Three observed runs on 2026-09-03: 42028 ms, 39690 ms, 52959 ms, against a declared budget of
30000 ms. All three passed. All three failed nobody.

It surfaced while capturing timing measurements for a different item — the definition of a finding
nobody was looking for.

## The spec

[`../assets/worked-example.json`](../assets/worked-example.json), scored against the anchors in
SKILL.md. The two scores that carry the decision:

- **silence** — `defer` scores **95**. The hook prints both numbers and returns a clean verdict it
  cannot support, which is the top anchor almost exactly.
- **next-session cost** — `defer` scores **70**. Every push in this repository runs the hook, so the
  next worker inherits the unenforced budget without going looking for it.

Against them, `defer` scores well on this-session cost (5) and scope integrity (95) — it really was
outside the work in hand, and the fix really would have cost the run something.

## The engine output

```sh
cd .claude/skills/decision-matrix && python3 -m scripts.score --spec ../out-of-scope/assets/worked-example.json
```

```json
{
  "method_results": {"weighted-sum": {"ranking": [
    {"option": "fix-now", "score": 81.755, "rank": 1},
    {"option": "defer",   "score": 49.105, "rank": 2}
  ]}},
  "recommendation": {"winner": "fix-now", "confidence": "high", "caveats": []},
  "ties": {"near_tie_pairs": []},
  "sensitivity": {"fragile": false}
}
```

Not a near-tie, and not fragile. The sensitivity run says `scope-integrity` would have to take a
32 % weight shift, and `this-session-cost` a 44 % shift, to flip the winner — and the three
dimensions that decide it (`next-session-cost`, `silence`, `contamination`) cannot flip it at any
weight. **Verdict: fix-now.**

## What the repository actually did

It deferred: the finding was captured as `harness:RM-0519`, linked to issue 952, with four
acceptance criteria — and it is still open, still on the next-unblocked list, while every push in
the repository runs the unenforced budget.

That is not automatically the wrong call. The session that found it may have been under an
authorization bar on `.claude/scripts/pre-push`, in which case `fix-now` was **vetoed** rather than
outscored, and the honest record is a deferral carrying `blocked_by` and the event that lifts it.

**Nothing on record says which.** No score, no constraint, no lifting condition — only an item and
an issue. Reconstructing the reasoning today means finding the session that made the call, and that
session is gone. That gap is precisely what this skill exists to close, and this example is here
because it is the gap rather than a demonstration of it.

## The vetoed variant

Flip one field — `constraint_results.authorized-to-fix` on `fix-now` — and the same spec produces:

```json
{
  "vetoed_options": ["fix-now"],
  "method_results": {"weighted-sum": {"ranking": [{"option": "defer", "score": 49.105, "rank": 1}]}},
  "recommendation": {"winner": "defer", "confidence": "high"}
}
```

`defer` now wins by being the only option left, at an unchanged 49.105. A record of this run must
carry `blocked_by`, because the winner beat a smaller field — and `out-of-scope-check.sh` refuses it
otherwise. Without that field the two runs are indistinguishable on paper, and they are opposite
decisions.
