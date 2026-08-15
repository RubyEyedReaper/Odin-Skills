# Upstream: `test-driven-development`

| | |
|---|---|
| Upstream | https://github.com/obra/superpowers |
| License | MIT — Copyright (c) 2025 Jesse Vincent (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `b36e082` (2026-08-12) |
| Modified by Odin | **Yes — one bounded delta, listed below** |

## The merge is resolved

The previous version of this file flagged an **open** decision: upstream had replaced ~60 lines of
"Why Order Matters" prose in `SKILL.md` with a pointer to a new file of its own,
`writing-good-tests.md`, which is not the same document as this fork's `testing-anti-patterns.md`.
The 2026-08-15 elicitation audit (`.claude/docs/audits/2026-08-15-elicitation-tdd.md`, T-D1..T-D4)
resolved it four ways. All four are now applied.

| Upstream hunk | Decision | Why |
|---|---|---|
| 1 — delete "Why Order Matters", replace with a 5-line pointer | **adopt** | The section is rationalization prose the "Common Rationalizations" table 50 lines below already covers row for row — all five arguments appear in both. It was injected on *every* TDD invocation; the table is the scannable form and the argument belongs in an on-demand reference. `SKILL.md` 9,894 B → ~8.4 KB. |
| 2 — expand five rows of the Common Rationalizations table into paragraph-length cells | **decline** | It re-injects, inside the table, most of the prose hunk 1 just removed: a wash on bytes and a loss on scannability, which is the table's only reason to exist. |
| new file `writing-good-tests.md` | **adopt, verbatim** | Strictly greater coverage than the file it replaces — see the coverage check below. |
| local `testing-anti-patterns.md` | **retire** | Every one of its five anti-patterns survives in `writing-good-tests.md`. |

## The standing local delta

**Five table rows in `SKILL.md`'s "Common Rationalizations" keep their one-line cells** where
upstream now runs three or four lines each: *"I'll test after"*, *"Tests after achieve same goals"*,
*"Already manually tested"*, *"Deleting X hours is wasteful"*, *"TDD will slow me down"*.

That is the whole delta. It is bounded, deliberate, and recorded here so the next refresh does not
re-litigate it — re-adopting hunk 2 is a decision, not a sync.

**Plus one Odin-specific addition:** the Red Flags section carries a cross-reference to
`.claude/rules/common/testing.md` for the case where deleting the code is not viable (it already
landed, or a parallel session shipped it). The skill's only answer is "delete it and start over";
Odin's always-on rule prescribes mutation checks standing in for the unseen RED, declared in the PR.
Two always-available instructions disagreed, and the always-on authored rule wins — the skill now
points at it rather than restating it.

## Coverage check for the retirement

Verified line by line before deleting `testing-anti-patterns.md`. Every anti-pattern survives:

| Retired file's anti-pattern | Where it lives now |
|---|---|
| Testing mock behavior | Principle 2, "The mock earns no assertions" (same `sidebar-mock` example) |
| Test-only methods in production | Principle 2, "Production classes carry production methods only" |
| Mocking without understanding | Principle 2, "Mock at the right level" (same `ToolCatalog`/`MCPServerManager` example) |
| Incomplete mocks | Principle 2, "Mirror real data completely" |
| Integration tests as afterthought | "Tests Ship With the Implementation" |

Upstream additionally carries material the retired file had no equivalent of: **Principle 1, "Name
the Break"** (mirror assertions, change detectors, and the rule that asserting a script or config
*contains* an exact line proves only that the source is the source — which is the lesson behind
Odin's own guard-test discipline), **the Mutation Check**, and **11 Warning Signs**.

**Knowingly lost in the trade:** the retired file's worked before/after TypeScript samples for
"test-only methods in production" and "incomplete mocks" compress to prose lines upstream, and its
four Gate Functions become two. The *rules* survive verbatim in the surviving gates ("A method only
tests call lives in test utilities, not production"; "Mock responses mirror the complete real
structure"); only the illustrations go. Recorded here so this reads as a decision rather than as
drift to whoever refreshes next.

Adopting the file verbatim — rather than merging the samples back in — keeps `writing-good-tests.md`
on upstream's refresh path instead of creating a second permanently-forked file. That was the
deciding reason.

## Removal ledger

`testing-anti-patterns.md` (8,251 B) is recorded in the harness `CHANGELOG.md` as removed and by
what it was replaced.
