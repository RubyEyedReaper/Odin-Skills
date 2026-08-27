# The five confidence tiers

`asserted` → `observed` → `reproduced` → `gated` → `enforced`.

A tier is not a mood. Each rung below states the **evidence that promotes a record into it** and the
**trigger that demotes it out**, because a ladder whose rungs are feelings sorts nothing: everyone
puts their own findings one rung higher than the last person would have, and the ordering carries no
information a reader can act on.

The engine holds the same ladder in `scripts/capture_bar.py` (`LADDER`), printed by
`python3 -m scripts.capture_bar tiers`. Prose and code are one ladder; if they disagree, the code is
what `verify` obeys and the disagreement is a defect.

---

## 1. `asserted` — the floor

Somebody stated it, and the source is named.

| | |
|---|---|
| **Promoted by** | A claim with an attributable source: a person, a document, an upstream issue |
| **Demoted by** | Nothing below this rung. A failing pass here **retires** the record |
| **`verified_by`** | Optional |

An `asserted` record is worth keeping when the source is worth citing and re-deriving the fact is
expensive. It is not worth keeping as a hunch with a name attached.

**The mistake this rung invites:** treating "an experienced person said so" as evidence about the
tree. It is evidence about the person. The fact still has never been checked.

## 2. `observed` — seen once

An artifact exists: a log line, a command's output, a transcript, a screenshot.

| | |
|---|---|
| **Promoted by** | An artifact a reader can open, plus the command or context that produced it |
| **Demoted by** | The artifact can no longer be resolved |
| **`verified_by`** | Optional — often a command that *resolves the artifact* rather than one that reproduces the result |

**The mistake this rung invites:** recording the conclusion and discarding the artifact. A year
later the conclusion is unfalsifiable, which reads exactly like being right.

## 3. `reproduced` — it happens again

A named command re-runs and produces the same result, twice, independently.

| | |
|---|---|
| **Promoted by** | A second run from a different starting state — a clean checkout, another host, another session |
| **Demoted by** | The command no longer produces that result → falls to `observed` |
| **`verified_by`** | **Required** |

"Independently" is the load-bearing word. Two runs in one session, from one working tree, share
every piece of ambient state that could be the actual cause. A wall-clock number measured twice on
one busy host is one measurement.

**The mistake this rung invites:** a command that reproduces the *symptom* rather than the *claim* —
a suite that reds for any of nine reasons is not evidence for the tenth.

## 4. `gated` — a check fails when it stops being true

A check in the repository reds when the fact stops holding.

| | |
|---|---|
| **Promoted by** | **Mutation.** Break the fact; watch the check go red; restore it; watch it go green |
| **Demoted by** | The check is removed, or mutation shows it cannot fail → falls to `reproduced` |
| **`verified_by`** | **Required** — the command that runs the check |

Mutation is the whole rung. A check that has never been seen red asserts nothing, and a check
written against finished behaviour usually asserts what the code does rather than what it should.
The same reasoning that makes a skipped RED recoverable only by mutation applies here
([`common/testing.md`](../../../rules/common/testing.md)).

**The mistake this rung invites:** promoting on the existence of a gate. A gate whose predicate can
never fire is an `observed` record with a shell script stapled to it — and it is worse than none,
because it reports success having examined nothing.

## 5. `enforced` — nothing can land while it is false

That check runs unconditionally on the path a change must take.

| | |
|---|---|
| **Promoted by** | The check is in the always-run path — `ci-local.sh`, a required status check, an always-on hook |
| **Demoted by** | The check leaves that path and becomes optional or manual → falls to `gated` |
| **`verified_by`** | **Required** — the command that runs the always-run path |

The distance between `gated` and `enforced` is exactly the distance between a check that exists and
a check nobody can skip. It is a real rung: a gate reachable only by remembering to run it holds for
as long as people remember.

**The mistake this rung invites:** counting a check as enforced because it is *in CI* when the job
is conditional — a path filter, a `continue-on-error`, a matrix leg that skips. Enforcement is a
property of the path, not of the file the check lives in.

---

## Promotion is deliberate; demotion is mechanical

Promotion needs a person to produce new evidence and say which rung it buys. Demotion needs nobody:
`verify --run` executes `verified_by` and drops the rung when it fails. That asymmetry is the point
— knowledge decays whether or not anyone is watching, and a ladder that only moves upward is a
ratchet on confidence rather than a measure of it.

Demotion moves **exactly one rung**. A `gated` record whose check now fails becomes `reproduced`,
not `asserted`: what the failure proved is that the gate no longer holds, not that the underlying
result was never reproduced. The exception is an unresolvable command, which falls to `observed` —
see [staleness-pass.md](staleness-pass.md).
