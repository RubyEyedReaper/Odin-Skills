---
name: work-loop
description: Use when a bounded work cycle needs a contract and a resumable ledger — declaring what one iteration is, recording which of six outcomes ended it, detecting a stalled loop mechanically, or resuming a loop a dead session left half-done.
---

# Work-loop — the cycle contract and its resumable ledger

A Loop is bounded work with a declared contract, iterations that each end in exactly one
of six outcomes, and a ledger a fresh session can resume from without repeating a single
completed action.

## What this is not for

| The task | Its owner | Why not this skill |
|---|---|---|
| Whether to keep going at all, and what to do next | `endless` | That is the continuation doctrine and its three checkpoints. This skill describes one cycle; it never decides whether another should start. |
| Polling until a command goes green | `verification-loop` | A retry until an exit code flips needs no contract and no ledger. |
| Executing a written implementation plan | `executing-plans` | The plan is the sequence. A Loop is a cycle with a limit. |
| Recurring wall-clock scheduling | Not this skill, at all | Nothing here schedules, triggers, or wakes anything. |
| What to work on next | `roadmap` | A Loop is *how* a bounded piece of work is run, never *which* work is next. |
| A reusable chain of skills and its lifecycle | `workflows` | A chain is emitted once, in order. A Loop iterates. |

## The contract

Eleven fields, declared before the first iteration, refused if any is missing or empty:
purpose, owner, starting state, inputs, expected outputs, success criteria, failure
criteria, dependencies, iteration limit, timeout behaviour, escalation path. Field by
field, with what goes wrong when each is absent: [loop-contract.md](references/loop-contract.md).

## The six outcomes

Exactly one per iteration. Only `continue` permits another.

| Outcome | Means | Then |
|---|---|---|
| `continue` | The iteration made progress and the contract still holds | Another iteration |
| `complete` | The success criteria are met | Loop ends |
| `revise` | The approach is wrong; the contract needs changing | Loop ends; re-open a revised one |
| `escalate` | A blocker outside the loop's reach | Loop ends, **blocker + evidence + recommended next action written to the ledger** |
| `pause` | State is checkpointed for a later session | Loop ends; `resume` re-enters exactly |
| `stop` | The limit is spent, or the work is abandoned | Loop ends |

**`escalate` and `pause` never wait for a human.** They are outcomes of the *iteration*,
never of the session: a run that stops has ended, and in an unattended session nothing
behind a question resumes until a human returns. `escalate` writes the blocker and its
next action down, captures a roadmap item, and ends the loop — the session then continues
with other work. `pause` checkpoints and ends. Neither may ask. ADR-0103 records why the
six-word vocabulary is kept and the blocking reading of two of those words is rejected.

## The four stall predicates

Mechanical, run inside `iterate` over the ledger's own history, each turning a reported
`continue` into a named non-continue outcome.

| Predicate | Outcome |
|---|---|
| N identical failures by normalised error signature | `escalate` |
| A state hash the ledger already holds | `revise` |
| The contract's iteration limit reached | `stop` |
| A declared dependency the iteration could not reach | `escalate` |

Why the signature is normalised, and what is deliberately *not* a stall:
[stall-detection.md](references/stall-detection.md).

## The ledger

`.claude/.runtime/work-loop/<session-id>.json` — in-flight state under a declared
retention class, swept with the rest of that class. Durable outcomes go to the ledgers
that already exist (`roadmap.json`, `CHANGELOG.md`, `MISTAKES.md`); this skill adds no
committed store.

Resume is keyed on **stable action ids**, never on an index. A ledger written by a session
that died mid-iteration has a counter that is either one too high or one too low with
nothing to say which; a recorded set of completed ids has no such ambiguity. `iterate`
refuses an action already recorded complete, and refuses the whole batch containing one —
a partial record is a repeat by another name.

## Quick reference

```sh
cd .claude/skills/work-loop
python3 -m scripts.loop open --root ../../.. --session "$SID" --contract contract.json
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome continue \
        --action migrate-db --state "coverage=67" --error "$(tail -1 build.log)"
python3 -m scripts.loop resume --root ../../.. --session "$SID" --json
python3 -m scripts.loop status --root ../../.. --session "$SID"
python3 -m scripts.loop close  --root ../../.. --session "$SID" --outcome complete
```

| Exit | Means |
|---|---|
| 0 | success |
| 1 | the contract or the iteration's facts are malformed |
| 2 | usage error, or a ledger that cannot be read |
| 3 | refused: this loop has ended |
| 4 | reported over a ledger with no iterations — nothing was examined |
| 5 | refused: the action is already recorded complete |

`4` is separate from `0` on purpose. A caller that cannot distinguish "no stalls found"
from "no iterations examined" cannot detect a report that means nothing.

## Common mistakes

| Mistake | What happens |
|---|---|
| Treating `escalate` as "ask the user" | The contract violation this skill was written to prevent. It writes the blocker down and ends the loop. |
| Reading the ledger to decide whether to keep going | That is `endless`'s decision, from its own predicates. The ledger says how *this* cycle ended. |
| Resuming by iteration number | An index survives nothing. Resume on the completed action ids. |
| A contract with prose success criteria | Nothing can decide `complete`, so the loop runs to its limit and reports `stop`. |
| Naming an undeclared dependency at iterate time | Refused as a contract finding — declare it, or the predicate decides over invented state. |
| Re-running the predicates on read | One ledger, two verdicts, depending on when it was read. `status` reports; it never re-decides. |

## Verifying a change to this skill

```sh
cd .claude/skills/work-loop && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5
```

Confirm the collected count is **non-zero**. `tests/__init__.py` is what makes it so;
without that file discovery collects nothing and the suite passes having examined nothing.
