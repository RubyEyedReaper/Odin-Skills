# Stall detection — four predicates a script decides

A stall is not a feeling that progress has slowed. It is one of exactly four conditions
over the ledger's own history, each decidable without reading the work. All four run
inside `iterate`, at the moment the iteration is recorded — there is no separate command
to invoke, because a predicate that must be invoked is one that will not be, at turn
thirty of an unattended run.

Each predicate turns a reported `continue` into a **named non-continue outcome**. None of
them relabels an outcome the caller already reported as terminal: the predicates
contradict a `continue`, they do not overrule a decision.

| # | Predicate | Fires when | Outcome | The break it prevents |
|---|---|---|---|---|
| 1 | Repeated error | This iteration's error signature has now been seen `--stall-threshold` times (default 3) | `escalate` | Thirty runs of one failure recorded as thirty ordinary iterations |
| 2 | Circular state | This iteration's state hash equals one already in the ledger | `revise` | A loop oscillating between two states forever, each step locally plausible |
| 3 | Retries exhausted | The iteration count reaches the contract's `iteration_limit` | `stop` | A declared limit that never binds |
| 4 | Dependency unavailable | The iteration reports a **declared** dependency it could not reach | `escalate` | Iterating against something that is simply gone |

Order matters and is fixed: a missing dependency is reported before the repetition that
is its symptom, so the ledger names the cause rather than the echo.

## Why the error signature is normalised

A predicate keyed on raw error text never fires. One failure renders differently on every
run — a changing absolute path, pid, hex address, timestamp, or quoted value — so two
occurrences of the same failure hash differently and the count never reaches two. The
predicate reads as strict and is in practice dead code.

Normalisation, in order, before hashing:

| Step | Replaced with | Why |
|---|---|---|
| Lowercase | — | `ConnectionError` and `connectionerror` are one failure |
| Quoted spans (`"…"`, `'…'`) | `<q>` | The quoted part is usually the varying value |
| `0x…` | `<hex>` | Addresses differ every run |
| Absolute paths | `<path>` | A checkout directory, a temp dir, a build id |
| ISO timestamps | `<ts>` | Always different |
| Digits | `<n>` | Line numbers, pids, ports, durations |
| Runs of whitespace | one space | Wrapping differs by terminal |

The result is hashed to sixteen hex characters. Two renderings of one failure share a
signature; two genuinely different failures do not. Both directions are asserted in
`tests/test_stall.py` — a normaliser tested in only one direction collapses everything
to one signature and turns predicate 1 into a hair trigger.

## Why the dependency must be declared

`iterate --dependency-missing NAME` is refused when the contract's `dependencies` never
declared `NAME`. Without that check, any caller could end any loop by naming a dependency
it invented at iteration time, and predicate 4 would decide over caller-supplied state
rather than declared state. The refusal is a contract finding, not a stall: the defect is
in the contract, and it is repaired by declaring the dependency.

## What is not a stall

| Situation | Why not | What owns it |
|---|---|---|
| The work is hard and slow | Slowness is not repetition | The contract's `timeout_behaviour` |
| The context window is filling | Nothing about the loop's own history | `endless`'s context checkpoint, then `/relay` |
| A gate is red for a new reason each time | Different signatures — the loop is making progress | Nothing; keep iterating |
| The next roadmap item is unclear | Not this loop's history at all | `roadmap` |

## Reading the verdict later

`status` reports the standing verdict; it never re-decides it. Re-running the predicates
on read would let one ledger yield two verdicts depending on when it was read, which is
the class of defect a ledger exists to remove.
