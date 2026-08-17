---
name: endless
description: Use when work must continue past the item in hand rather than stop with it — an unattended or overnight run, a /loop or /autoloop iteration, a session told to keep going until the roadmap is empty, a checkpoint reached with work still queued, or a run whose context is filling before the work is done. Also use when the next thing to do must be chosen and started without a human in the turn.
metadata:
  origin: Odin
---

# Endless — the continuous work loop

## Overview

A loop that never has to be told what to do next. `roadmap` decides **what**, `successor` decides
**who**, and this skill decides **whether to keep going, hand off, or fan out** — at every
checkpoint, from an observable predicate rather than from whatever the context window still holds.

**Core principle: an iteration ends at a checkpoint, not at a task.** A finished task with nothing
decided after it is where autonomy dies quietly — the session idles, the branch sits unpushed, and
the next roadmap item waits for a human. Every checkpoint in this skill forces one of three named
continuations. There is no fourth, and "stop" is not one of them unless a human is owed something.

Rigid skill. The checkpoint decision is not a judgment call; the predicates below are.

## When to use

| Situation | Fire |
|---|---|
| Keep working until the roadmap is empty | **this skill** |
| One unattended iteration, right now | `/autoloop` — the command; this skill is its doctrine |
| Which skill owns loop phase N | `.claude/docs/autonomous-loop-standard.md` — the phase table |
| What to work on next, once | `roadmap` alone. A single pick is not a loop |
| Hand this session forward, one worker | `/relay` |
| Two or more independent workers | `successor` |

Not for: a single task with a defined end (do it), or a loop over work that shares mutable state —
parallel sessions on one checkout corrupt each other's index (ADR-0054).

## The loop

Ten phases. The **skill** for each is in the phase table
([`autonomous-loop-standard.md`](../../docs/autonomous-loop-standard.md) § Phase → skill, rows 0–22);
the **commands** are in [`/autoloop`](../../commands/autoloop.md). Neither is restated here — a third
copy of a table is a third thing to drift, which is what audit F6/F7 found.

```
arm posture → track → pick → gate → build → verify → land → capture → CHECKPOINT → continue
     ↑                                                                                  │
     └──────────────────────────────────────────────────────────────────────────────────┘
```

| # | Phase | The one thing that makes it load-bearing |
|---|---|---|
| 1 | **Arm posture** | `odin-autonomous.sh on`, **every** iteration. The claim is TTL'd; skipping the renewal drops the gates back to `warn`, and a warned gate in an unattended run is a gate that did nothing. |
| 2 | **Track** | `TaskCreate` before any other tool. No task list → no completed task → no compaction boundary, ever (ADR-0031, ADR-0036). |
| 3 | **Pick** | `roadmap next`, unblocked only, then `set --status in-progress`. Never from `ROADMAP.md` prose, never from memory of last iteration. |
| 4 | **Gate** | Sharpen / score / decompose / plan. Forks found inside a gate are **yours** — decide, record the DEC or ADR, continue (`common/decision-authority.md`). |
| 5 | **Build** | Surface routing arrives per edit with no prompt involved. Invoke what it names; it fires because the *file* demands it, which stays true at turn thirty. |
| 6 | **Verify** | `bash .claude/scripts/ci-local.sh`. Locally, on the working tree. Dispatching a workflow is blocked always-on and would test the pushed tree, not this one. |
| 7 | **Land** | Rebase onto `main`, fast-forward, push, delete the branch. Close with the **landed** sha — a topic-branch sha does not survive the rebase that merged it. |
| 8 | **Capture** | Every finding becomes a roadmap item, an issue, or an ADR. An uncaptured finding dies with this context, and findings are the next iteration's fuel. |
| 9 | **Checkpoint** | Below. |
| 10 | **Continue** | One of exactly three continuations. Below. |

Phase 8 has a second half that only a loop has: **an incident becomes a guard.** Anything in the
iteration that should not have happened goes through `oops` — root cause, a mechanical guard, one
row in `MISTAKES.md`; a repo-state predicate hands off to `mistake-to-gate` (ADR-0057). A loop that
captures features and drops its own mistakes re-makes them on a schedule.

## Checkpoint semantics

A checkpoint is a **defined state**, not a feeling of being finished. Exactly three reach one:

| Checkpoint | Reached when | Recorded as |
|---|---|---|
| **Landed** | The item is on `main` and closed with the landed sha | `roadmap set RM-XXXX --status done --evidence <sha>` |
| **Hard blocker** | An external dependency refuses: missing credential, failing upstream, rate limit, a decision that spends money or is outward-facing | `roadmap set RM-XXXX --status blocked` + the blocker in one line, and the loop moves to the next item — a blocked item is not a stopped loop |
| **Context** | Context past roughly half the ceiling | `/relay` — the successor continues from the handoff |

**Not checkpoints.** In-scope work left undone by choice; a plan written but not executed; a branch
green but unpushed; "this deserves its own session later". Each of those is the loop handing work
back, which CLAUDE.md item 3 forbids in the same words whether a human is watching or not.

## The continuation decision

At a checkpoint, run the predicates in order and take the first that fires.

| Predicate — observable, in this order | Continuation |
|---|---|
| Context past ~half the ceiling | **Relay.** `/relay` writes the handoff and launches the successor; this session stops after confirming the branch is pushed. A successor with a good handoff beats an iteration spent re-reading what this one already established. |
| `roadmap waves` puts **≥2 items in the same layer**, and their surfaces do not overlap | **Delegate.** Become a coordinator: `successor`, all five phases. Then integrate, then resume the loop at phase 1. |
| Anything else — one item, or a colliding pair | **Continue inline.** Next iteration, same session, phase 1. |

**Layer width alone is not the predicate.** Two items in one layer that touch the same files are one
worker's work, not two: the graph knows about dependencies, not about collisions. Diff the surfaces
before fanning out — two sessions on one checkout is ADR-0054's failure, and a fan-out that lands
conflicts costs more than the serial run it replaced.

**Coordinator duties are not optional.** Fanning out converts this session from a builder into an
integrator: reserve every ADR/DEC/RM id up front, monitor two signals (session state *and* branch
movement), scope-diff each branch against its declared authorization, gate the **merged** result,
and tear the worktrees down. `successor` owns all five; skipping teardown leaves Layer 1F's
concurrency guard armed against the main checkout.

## Pacing, when the loop self-schedules

The harness re-invokes on completion of the work it tracks, so **polling is waste**. Schedule a long
fallback (1200 s+) that only fires if the tracked work hangs or never notifies. Poll on a short
interval only for state the harness cannot see — a remote queue, an external run — and then match
the interval to how fast that state actually changes.

## Red flags

| Thought | Reality |
|---|---|
| "The task list is bookkeeping, the work is real" | No completed task means no compaction boundary and no re-armed routing. The list *is* mechanism. |
| "I armed the posture last iteration" | The claim is TTL'd. Arm it every iteration or run interactive by accident. |
| "Nothing left in the roadmap, so the loop is done" | An empty graph means unreconciled or uncaptured, not finished. `reconcile`, then capture the last iteration's findings. |
| "Two items in the layer — fan out" | Not until you have diffed their surfaces. |
| "I'll note this finding in the report" | The report is context. Capture it as an item, an issue, or an ADR. |
| "This next part is big; it deserves its own session" | Big work is planned first, then **started** here. Splitting it off is deferral wearing a schedule. |
| "Context is fine, I'll relay when it bites" | By then the handoff is written by a session too full to write a good one. Relay at the predicate. |
| "I'll ask which item matters more" | A question in an unattended run is not a pause, it is the end of the turn (ADR-0052). Score it, record the DEC, continue. |
| "Green before the rebase, so it lands green" | Gate the merged result. |

## Quick reference

| Need | Where |
|---|---|
| Run one iteration now | `/autoloop` |
| Which skill owns phase N | `.claude/docs/autonomous-loop-standard.md` |
| Arm / read / release posture | `bash .claude/scripts/odin-autonomous.sh on\|status\|off` |
| What to work on, and parallel layers | `roadmap` — `next`, `waves`, `reconcile` |
| Fan out and integrate | `successor` |
| Hand this session forward | `/relay` |
| An incident from the iteration | `oops` → `mistake-to-gate` |
| Why a native loop skill, not the vendored catalog | `.claude/docs/adr/0060-endless-skill.md` |
| Why routing had to become surface-shaped | `.claude/docs/adr/0051-turn-triggered-skill-routing.md` |
