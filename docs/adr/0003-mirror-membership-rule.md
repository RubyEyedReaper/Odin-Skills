# ADR-0003: Membership of the mirror is a rule, never a count

## Status

Accepted — 2026-09-01 (records a decision in force since the repository was assembled)

## Context

The Odin harness vendors far more skills than it owns. This repository publishes a subset, and which
subset has been described three different ways in three places, all of them by number:

| Where | What it says | Measured 2026-09-01 |
|---|---|---|
| [ADR-0001](0001-distribution-monorepo-and-per-skill-repos.md) context | "authored 7 … substantially modified 10 more … Those 17" | — |
| `INIT.md` § Purpose | "seven skills authored here and ten forked" | — |
| `docs/PROVENANCE.md` § headings | "Odin-authored (9)", "Forks (10)" | 17 authored rows, 10 fork rows |
| `skills/` on disk | — | **27 directories**, `validate-skills.sh` exits 0 |

Every one of those numbers was true when it was written. None of them is the membership rule, and a
count restated in four documents is four documents that go stale on the day a skill is authored —
which has now happened repeatedly, silently, while the validator stayed green, because the validator
checks the table against the directory and never checks a prose heading against either.

The membership rule itself is not in doubt and is enforced mechanically today: the harness's
`.claude/scripts/vendor-skills.sh` derives its fork-protection set from the listing of
`projects/Odin-Skills/skills/` — the directory listing **is** the operative definition of "a skill
Odin authored or forked" (ADR-0001, constraint 2). What was missing is the record that this is the
rule, so that the next reader updates a number rather than inventing a fourth one.

## Decision Drivers

- The harness's fork protection reads this directory listing. Membership therefore has to be
  decidable from the repository, not from a document.
- A skill authored in the harness this week must be able to join the mirror without an ADR being
  amended.
- Third-party skills the harness has never modified must stay out: redistributing them is a
  different repository with a different licensing story ([ADR-0002](0002-split-licensing-authored-and-forked.md)).
- Whatever the rule is, `scripts/validate-skills.sh` has to be able to enforce it per skill.

## Considered Options

### Option 1: A fixed enumeration in an ADR

Name the member skills in the record; amend the ADR to add one.

- **Pros**: Unambiguous on the day it is written; the set is auditable against one document.
- **Cons**: Immutable-decision discipline says an Accepted ADR is superseded rather than rewritten,
  so every new skill needs a new record. Guaranteed to be stale between edits, which is the state
  this repository is already in four times over.

### Option 2: A count, maintained in prose

Keep saying "17 skills" (or 27, or whatever it is next month) in the README, INIT and ADR context.

- **Pros**: Reads well; gives a reader a sense of scale.
- **Cons**: This is the status quo, and it is what produced the table above. A count is a derived
  fact restated by hand in four places, with nothing deriving it. `ci-gate/report-overclaims-its-scope`
  is the harness's name for exactly this failure.

### Option 3: A predicate, with the directory as its materialisation

Membership is: **a skill the Odin harness authored, or forked from an upstream and substantially
modified.** The materialisation of that predicate is `skills/` in this repository, cross-checked
per skill by `scripts/validate-skills.sh` against `docs/PROVENANCE.md`.

- **Pros**: A skill joins by being synced and given a provenance row — no document amendment. The
  set is derivable at any moment (`ls skills/`), so any count in prose is a measurement with a date
  rather than a claim. Matches what the harness's fork protection already reads.
- **Cons**: "Substantially modified" is a judgement, made once per skill when it is added, and this
  record does not mechanise it. A reader who wants a number must measure one.

## Decision

**Option 3.** Membership of the mirror is the predicate — authored by Odin, or forked and
substantially modified — and `skills/` is where that predicate is materialised. Consequently:

- **No document states the size of the set as a standing fact.** Where a number is genuinely useful,
  it is written as a measurement with the date it was taken, in the way `docs/PROVENANCE.md`'s
  "measured 2026-08-26, not inherited" note already does.
- **Adding a member is: sync the skill, add its `docs/PROVENANCE.md` row, and let
  `scripts/validate-skills.sh` pass.** No ADR is amended, and this one is not superseded.
- **Removing a member is deliberate and rare**, because the harness's `vendor-skills.sh` reads this
  directory for fork protection: a skill dropped from `skills/` stops being protected against the
  next vendor refresh (ADR-0001, constraint 2).
- The counts currently standing in `ADR-0001`'s context, `INIT.md` and `docs/PROVENANCE.md`'s
  section headings are **historical or stale**. An Accepted ADR's context is a snapshot and stays as
  written; the two living documents are corrected as maintenance, and keeping them correct is a
  separate piece of work from this decision.

## Consequences

**Positive**

- The question "is this skill in the mirror?" has one answer, in the repository, and the same answer
  the harness's fork protection uses.
- A newly authored skill joins without an ADR amendment, so the record stops being a bottleneck that
  gets skipped.
- Any future count is a measurement, which makes staleness visible instead of authoritative.

**Negative**

- "Substantially modified" stays a judgement. Two people could disagree about a lightly-patched
  vendored skill, and nothing here resolves it beyond the provenance row being written and reviewed.
- Removing the standing counts costs a reader the at-a-glance sense of scale that a number gave.

**Mitigations**

- `docs/PROVENANCE.md`'s per-skill table is the enumeration, and the validator keeps it aligned with
  the directory in both directions.
- Where scale is wanted, `ls skills/ | wc -l` is one command and cannot be stale.

## Related

- [ADR-0001](0001-distribution-monorepo-and-per-skill-repos.md) — the distribution shape, and the
  constraint that the harness reads this directory for fork protection.
- [ADR-0002](0002-split-licensing-authored-and-forked.md) — the licensing that follows from which
  half of the set a skill is in.
- [`../PROVENANCE.md`](../PROVENANCE.md) — the per-skill enumeration and its source-of-truth note.
- [`../../INIT.md`](../../INIT.md) — the project's invariants, including the one-way mirror rule.
