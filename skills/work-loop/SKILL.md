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

Twelve fields, declared before the first iteration, refused if any is missing or empty:
purpose, owner, starting state, inputs, expected outputs, success criteria, failure
criteria, dependencies, iteration limit, timeout behaviour, escalation path, quality
rubric. Field by field, with what goes wrong when each is absent:
[loop-contract.md](references/loop-contract.md).

## The quality rubric

The twelfth field, and the one that makes "better" checkable rather than asserted. A weighted list
of dimensions, each naming the **command** that produces its number, plus its baseline, target,
weight, failure threshold, direction, and whether it is a hard gate.

`open` refuses a dimension with no evidence command — a dimension you cannot write a command for is
a judgment, and a judgment belongs in review rather than in a rubric. `score` takes one measurement
per dimension and returns the weighted total, the hard gates breached, and one verdict.

**A hard-gate failure outranks any weighted total, including one that went up.** `score` exits 6 in
that case — distinct from malformed (1) and from ok (0) — and still prints the improved total, because
a verdict that hid the improvement would be as unreadable as one that accepted it.

The engine **reads** the evidence commands and never runs one — executing a contract-supplied string
from inside the engine was vetoed, because a subprocess there is not a tool call and would sit
outside every always-on guard (DEC-0091, ADR-0143). `open` refuses a command that cannot parse, one
whose program resolves nowhere, and one carrying an unresolved placeholder; `--baseline-evidence
<dimension>=<path>` takes a transcript the **caller** produced, refuses it unless the declared
baseline appears in it, and records that dimension `measured` rather than `declared`. The eight keys,
the arithmetic, what a `measured` provenance does and does not prove, and this repository's default
dimension set (DEC-0090): [quality-rubric.md](references/quality-rubric.md).

## The iteration record

What a later reader has instead of the session that wrote it. The engine **derives** what it can and
**refuses** what it cannot check, because the alternative — more optional fields — is the defect
itself: one coordinator ledger held 29 iterations whose `note` and `recommended_next`, both already
optional, were null.

| Derived by the engine | From |
|---|---|
| `evaluation` | `score_rubric` over the contract's rubric and this iteration's `--measure` values |
| `baseline` | the previous **measured** iteration's readings, or the rubric's declared baselines when there is none |

An iteration recorded without `--measure` carries a null evaluation and **does not become the next
one's baseline** — a blank pass must not erase the last real reading.

| Refused, before anything is written | Exit |
|---|---|
| `--critic-verdict` with no `--evidence-path` | 1 |
| A verdict outside `PASS` `FAIL` `REVISE` `REVERT` `ESCALATE`, or a decision outside `retain` `revert` `revise` `escalate` | 1 |
| A measurement naming an undeclared dimension, or a declared dimension left unmeasured | 1 |
| **`--decision retain` over a breached hard gate** | **7** |

The obligation runs one way: evidence with no verdict is an ordinary iteration that collected
artifacts. And `retain` with **no** measurements is accepted — the engine refuses what it measured,
never what it did not look at.

Field by field, who writes each one, and the two recorded residues:
[iteration-record.md](references/iteration-record.md).

## The critic pass

A builder's report of its own work is not evidence. `loop brief` assembles the packet a critic
receives — the diff, the verification output, the contract's rubric, the baseline, the verdict
vocabulary and the asks — and records it as a **single-use** brief whose id is the hash of those
artifacts. `iterate --critic-verdict` then requires `--critic-brief <id>` naming that brief, and
spends it.

| Refused | Why |
|---|---|
| A verdict with no `--critic-brief` | A verdict written by the builder in the same breath as the work |
| A brief id the engine never emitted, or a brief when none is pending | Also how a spent brief is caught on second use — a verdict is about one change |
| A verdict with no `--critic-next` | The critic names the single most valuable next improvement |
| An unreadable **or empty** diff, verification file or change-scope transcript | Exit 8, naming the file. A packet with an empty diff has the critic judge a change it never saw |
| A diff that does not cover every path `--change-scope` declares | Exit 9. Readable and non-empty were the only tests, and a one-file excerpt of a nine-file commit passes both |

**What this proves and what it does not.** Mechanically: no verdict is recordable that is not bound
to a packet the engine assembled from the actual artifacts, and each packet buys one verdict. **The
binding's subject is the packet, never the change** — it says "this verdict is about this packet",
and how far the packet *is* the change is exactly what the `scope` block reports. Not mechanically —
and no gate here claims it — that a *different context* produced the verdict, nor that a declared
scope describes the change under review. Those halves are review criteria: dispatch
`adversarial-reviewer` with the packet. Which half is which:
[critic-pass.md](references/critic-pass.md).

The engine still runs no critic and dispatches nothing — and it derives no diff. It reads the scope
transcript the caller produced, the same way it reads a rubric's evidence command and never runs one
(ADR-0143, extended by DEC-0093). It packages, and it refuses.

## The six outcomes

Exactly one per iteration. Only `continue` permits another.

| Outcome | Means | Then |
|---|---|---|
| `continue` | The iteration made progress and the contract still holds | Another iteration |
| `complete` | The success criteria are met | Loop ends |
| `revise` | The approach is wrong; the contract needs changing | Loop ends; `open` a revised contract over the same ledger — the predecessor is kept, see **Contract epochs** |
| `escalate` | A blocker outside the loop's reach | Loop ends, **blocker + evidence + recommended next action written to the ledger** — all three enforced, see below |
| `pause` | State is checkpointed for a later session | Loop ends; `resume` re-enters exactly |
| `stop` | The limit is spent, or the work is abandoned | Loop ends |

**`escalate` and `pause` never wait for a human.** They are outcomes of the *iteration*,
never of the session: a run that stops has ended, and in an unattended session nothing
behind a question resumes until a human returns. `escalate` writes the blocker and its
next action down, captures a roadmap item, and ends the loop — the session then continues
with other work. `pause` checkpoints and ends. Neither may ask. ADR-0103 records why the
six-word vocabulary is kept and the blocking reading of two of those words is rejected.

## The escalate record

A hard external blocker is the only sanctioned reason to stop short of done (CLAUDE.md
item 3: a missing credential, a failing dependency, a rate limit). `escalate` is where one
gets written down, and the record carries **three** fields, each required:

| Field | Flag | Holds |
|---|---|---|
| blocker | `--blocker` | What stopped the loop, in one sentence |
| evidence | `--evidence` | What shows it — an exit code, a command's output, a path |
| recommended next action | `--recommended-next` | What the next session should do about it |

`iterate` and `close` both refuse an `escalate` missing any of them, and
`.claude/scripts/blocker-record-check.sh` reads every ledger and refuses the same shape,
catching records written before the engine enforced it and records written by anything
else. A **stall-promoted** escalate is written by the engine rather than by an author, so
the engine derives all three from the facts it holds — which predicate fired, and the
signature or dependency behind it.

**What is checked is that the stop recorded a blocker in a stated form — never whether the
blocker was genuine.** That is a judgment, and a gate that adjudicated it would be one
competent people disagree with, which is a gate that gets disabled. **A blocker record is
evidence, not permission**: it makes stopping harder to do silently, and no easier to do.

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

## Contract epochs

A `revise` says the approach is wrong, so the loop ends and a **revised contract is opened
over the same ledger**. `open` decides on the ledger's `status`, never on whether a file is
there: a closed ledger is re-opened, and its contract, terminal outcome, close record and
iteration numbers move into `epochs[]`. `iterations` and `completed_actions` carry forward,
so `resume` re-enters correctly and an action performed before the revision is still refused
after it.

**`--force` is not how you revise.** Its meaning is *discard* — for a corrupt ledger nobody
wants — and the history is the one thing a revise exists to keep. It stops being the only
way in.

| Key | Holds |
|---|---|
| `epoch` | which contract is live, counting from 1 |
| `epochs[]` | every contract that preceded it, with how each one ended |
| an iteration's `epoch` | which contract it ran under; `n` stays monotonic across a revise |

**The predicates read the current epoch only.** Read across a revision, `circular-state`
re-fires on the very state hash that produced the `revise` — forcing the first honest
iteration under the new contract straight back to `revise` — and `retries-exhausted` reports
a fresh contract's first iteration as its last, on the predecessor's spent limit.

A re-open clears any pending brief: a brief's id hashes the contract's rubric, so one that
outlived its contract names a packet the engine would no longer assemble.

**The knock-on worth knowing.** `.claude/hooks/odin-task-gate.sh` accepts a work-loop ledger
as a session's task-list route only at `status: open`. Before ADR-0140 a session whose
toolset carries no `TaskCreate` lost its `Write`/`Edit` route the moment it recorded a
`revise` — punished, mid-run, for using the vocabulary correctly. Re-opening restores the
state the gate asks about.

## Quick reference

```sh
cd .claude/skills/work-loop
python3 -m scripts.loop open --root ../../.. --session "$SID" --contract contract.json
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome continue \
        --action migrate-db --state "coverage=67" --error "$(tail -1 build.log)"
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome escalate \
        --blocker "the deploy credential the contract declares is absent" \
        --evidence "gh auth status exited 1: no token found" \
        --recommended-next "issue a scoped token, then re-open this contract unchanged"
python3 -m scripts.loop brief --root ../../.. --session "$SID" --json \
        --diff-file /tmp/change.diff --verification-file /tmp/suite.txt \
        --change-scope /tmp/scope.txt   # git show <sha> --stat, run by YOU
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome continue \
        --action tighten-guard --measure gate-integrity=0 \
        --evidence-path /tmp/ci-local.log --critic-brief "$BRIEF" \
        --critic-verdict PASS --critic-next "measure the suite wall clock" --decision retain
python3 -m scripts.loop score --root ../../.. --session "$SID" --json \
        --measure gate-integrity=0 --measure context-budget=37000
python3 -m scripts.loop resume --root ../../.. --session "$SID" --json
python3 -m scripts.loop status --root ../../.. --session "$SID"
python3 -m scripts.loop close  --root ../../.. --session "$SID" --outcome complete
```

| Exit | Means |
|---|---|
| 0 | success |
| 1 | the contract or the iteration's facts are malformed |
| 2 | usage error, or a ledger that cannot be read |
| 3 | refused: the ledger is not in a state this command acts on — `iterate`/`close` over a closed one, `open` over a live one |
| 4 | reported over a ledger with no iterations — nothing was examined |
| 5 | refused: the action is already recorded complete |
| 6 | scored, and a hard-gate dimension breached its failure threshold |
| 7 | refused: a change was to be retained over a breached hard gate |
| 8 | refused: an input the critic brief needs could not be read, or was empty |
| 9 | refused: the packet's diff does not cover the change its declared scope names |

`4` is separate from `0` on purpose. A caller that cannot distinguish "no stalls found"
from "no iterations examined" cannot detect a report that means nothing.

## What `status` reports about quality

The rubric, the record and the critic verdict are all in the ledger; `status` is the one command a
reader runs to ask about a loop, so it carries five quality keys alongside the counters:

| Key | Value |
|---|---|
| `rubric_verdict` | `pass` or `fail`, from that record's evaluation — `null` if that record was not scored |
| `weighted_total` | the weighted score, `0`–`100` — `null` on the same condition |
| `critic_verdict` | `PASS` `FAIL` `REVISE` `REVERT` `ESCALATE` |
| `decision` | `retain` `revert` `revise` `escalate` |
| `quality_from` | the `n` of the iteration all four came from |

**All five come from one record**, and `quality_from` names it. Resolved field by field they would
compose a snapshot that never existed: `iterate` refuses `--decision retain` while a hard gate is
breached (exit 7), so a reader taking the verdict from iteration 2 and the decision from iteration 1
prints exactly the pairing the engine refuses. The record is the last one that was **judged** —
scored, reviewed, or decided — because preferring a scored record over a later reviewed one drops
the loop's most recent judgment.

**Absent is not zero.** Every key is present and `null` when the reported record does not carry it
— including over an empty ledger, where the payload carries them beside its exit 4. A loop nobody
scored must not read as a loop that scored badly, and a printed `0.0` is indistinguishable from a
measured one.

**A `null` does not mean nobody scored.** It means the *reported* record — the newest judged one —
did not carry that field. A loop scored at iteration 1 and reviewed at iteration 2 reports
`rubric_verdict: null` with `quality_from: 2`, and the score is still in the ledger. Reading `null`
as "never scored" is the misreading this section exists to prevent, and it costs what the
composed-snapshot defect cost.

## Common mistakes

| Mistake | What happens |
|---|---|
| Treating `escalate` as "ask the user" | The contract violation this skill was written to prevent. It writes the blocker down and ends the loop. |
| Escalating with a next action and no blocker or evidence | Refused. A stop that names nothing is indistinguishable from giving up, and the reader has no session left to ask. |
| Reading the ledger to decide whether to keep going | That is `endless`'s decision, from its own predicates. The ledger says how *this* cycle ended. |
| Resuming by iteration number | An index survives nothing. Resume on the completed action ids. |
| Reaching for `--force` to re-open after a revise | `--force` discards. `open` re-opens a closed ledger on its own and keeps the predecessor in `epochs[]`; the history is what a revise exists to keep. |
| A contract with prose success criteria | Nothing can decide `complete`, so the loop runs to its limit and reports `stop`. |
| A rubric dimension whose evidence is "review says so" | Refused at `open`. Name it in the review checklist and leave it out of the rubric — the honest residue beats a dimension that looks measured. |
| A command carrying `--root R`, `<session-id>`, or a program that resolves nowhere | Refused at `open`. A command that cannot run as written was never run, and the baseline beside it is a guess wearing a measurement's clothes. |
| Reading a `declared` baseline as a failed measurement | It is an *unverified* one. Run the command yourself and pass `--baseline-evidence` to promote it; `status` reports how many of the epoch's baselines a transcript backed. |
| Reading a high weighted total as permission | The verdict is `fail` while any hard gate is breached, at any total. Exit 6 exists so a caller cannot miss it. |
| Recording a critic verdict the same context produced | Refused — a verdict needs a brief the engine emitted. The verdict belongs to a context that did not build the change. |
| Re-using one brief across two iterations | Refused. A brief is spent by the iteration that records its verdict; the alternative is change N's judgment on change N+1. |
| Handing `brief` an excerpt of the change and no `--change-scope` | Accepted, and the packet says `provenance: "unverified"` — which is the honest reading, not an endorsement. Declare the scope and a partial diff is refused instead. |
| Reading `provenance: "unverified"` as "the diff is complete" | It means nothing was established either way. Absent is not zero, here as everywhere else in this engine. |
| `--decision retain` after a breached gate | Refused, exit 7. Record `revert`, `revise` or `escalate` — the last carries a blocker and its evidence. |
| Naming an undeclared dependency at iterate time | Refused as a contract finding — declare it, or the predicate decides over invented state. |
| Re-running the predicates on read | One ledger, two verdicts, depending on when it was read. `status` reports; it never re-decides. |
| Reading a `status` quality field without `quality_from` | The four describe **one** iteration, not the loop. `quality_from` is which one. |

## Verifying a change to this skill

```sh
cd .claude/skills/work-loop && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5
```

Confirm the collected count is **non-zero**. `tests/__init__.py` is what makes it so;
without that file discovery collects nothing and the suite passes having examined nothing.
