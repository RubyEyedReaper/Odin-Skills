---
name: gauntlet
description: Use when work must be driven to exhaustion across many delegated sessions rather than one at a time — an endless gauntlet, a campaign that re-arms instead of ending, "keep going until every issue and roadmap item is done", a batch that finished while new work kept arriving, or a coordinator asking what is left across the roadmap and the tracker at once. Also on "re-arm", "rearm", "next wave", "quick wins first", and when a campaign looks finished and the loop must decide whether to start another.
metadata:
  origin: Odin
---

# Gauntlet — the campaign that re-arms

## The stance

**A gauntlet does not end when its list does.** It ends a *batch*.

Item creation outruns completion: measured over the 14 days ending 2026-09-02, this repository
created 385 items and closed 252 — 1.53 created per completion, with no day below 1.0. A loop
instructed to "run until zero open items" is therefore instructed to run forever without ever
reaching a state it can report, which is how a run goes silent for twelve hours with no verdict.
Re-measure that ratio before quoting it; it is a fact about a period, not a constant.

So the unit is a **batch**: an item set frozen at a pinned base, so `campaign close` can compute a
verdict over something that holds still, and a **re-arm** that recomputes the frontier and rolls the
loop into the next batch. The loop never stops. The batch always does.

Rigid skill. The channel order, the refusals and the exit codes are not judgment calls.

## What this owns, and what it must not restate

Seven of the eight capabilities an endless improvement loop needs already ship. This skill is the
composition layer over them, and it **cites** them — a second copy of a rule drifts, and the looser
copy wins silently.

| The task | Its owner | Never re-derived here |
|---|---|---|
| Whether to keep going, and the three continuations at a checkpoint | `endless` | The continuation predicates. This skill says what the frontier holds; `endless` decides what to do about it |
| One bounded cycle: contract, twelve fields, six outcomes, four stall predicates, the quality rubric, the critic packet, the ledger | `work-loop` | All of it. The rubric, the hard gates (`score` exit 6, `iterate --decision retain` exit 7) and the single-use `brief` are that skill's. Field-by-field mapping against the source protocol's `gauntlet/state.json`/`gauntlet/ledger.jsonl` naming: [references/ledger-conformance.md](references/ledger-conformance.md) (DEC-0118) |
| What a campaign contains, and whether it may close | `campaign` | Landedness by content, the remote-first channel order, the refusal to store a status (ADR-0113). `verify` **calls** `campaign close` |
| Provisioning, launching, integrating, tearing down a delegated session | `successor` | The five phases and the six-element handoff bar |
| What is true of a session that already exists | `successor-manager` | The health gate, the five verdicts, the ownership register |
| Restarting a stopped fleet with nobody at the keyboard | `revive` | The manifest, the not-before instant, the five preconditions |
| What work exists, and its graph | `roadmap` | Item identity, the slug rule, `next`/`waves`/`reconcile` |
| Planning one item before it is built | `superplan`, `blueprint` (multi-PR), `writing-plans` | The plan-depth bar |
| Turning an untriaged issue into work | `triage`, `to-issues` | A tracker row is emitted as a finding, never placed in a wave |
| What residue may be deleted at the end | `tidy` | Close-out hands it over as a list, and deletes nothing |
| What a worker says back, and what its terminal carries rather than its report | `s2s` | The message bar, the narration bound, and that a send reports on the send (ADR-0162) |

**The gap this fills**, and the only reason it is a skill: nothing else names the chain's fixed
order, nothing re-measures the item set mid-campaign, and nothing checks a surface collision before
fanning out — `endless` states that check in prose and no code performed it.

## The cycle

```
reconcile → frontier → plan → assign → build → integrate → verify → RE-ARM
    ↑                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

| # | Step | Fire | The one thing that makes it load-bearing |
|---|---|---|---|
| 1 | **Arm and reconcile** | `endless` phase 1–2, `roadmap reconcile` | Posture is TTL'd; a warned gate in an unattended run is a gate that did nothing |
| 2 | **Frontier** | `gauntlet frontier` | Reads four channels and refuses to call an unread one empty |
| 3 | **Plan** | `superplan`, or `blueprint` when one item spans PRs | The plan-depth bar applies per item, not per batch |
| 4 | **Assign** | `gauntlet rearm` → the manifest, then `successor` | Emits campaign-shaped rows with colliding surfaces held back |
| 5 | **Build** | the worker's own chain — `test-driven-development`, surface routing | Routing arrives per edit with no prompt involved, which is what still fires at turn thirty |
| 6 | **Integrate** | `successor` phase 5, `ci-local.sh` locally | Gate the **merged** result; a branch green before its rebase says nothing about what lands |
| 7 | **Verify** | `gauntlet verify --manifest` | Two questions: may the batch close, **and** what appeared since it was pinned |
| 8 | **Re-arm** | `gauntlet rearm`, then step 2 | The step nothing else has. A closeable batch is not a finished gauntlet |

Step 8 has a second half a batch does not: **every finding becomes capturable work before the
re-arm.** A feature or defect goes to `roadmap`/`to-issues`; an incident to `oops` → `mistake-to-gate`;
a hazard to `caveat`; an unobserved effect to `mutations`; a recurring friction to `improve`; a
durable lesson to `learn`; a third repetition to `automate`. An uncaptured finding dies with the
batch, and findings are the next batch's fuel.

## The three commands

```sh
cd .claude/skills/gauntlet
python3 -m scripts.gauntlet frontier --root "$PWD/../../.." --explain
python3 -m scripts.gauntlet rearm    --root "$PWD/../../.." --width 4 --json
python3 -m scripts.gauntlet verify   --root "$PWD/../../.." --manifest <file> --json
```

| Command | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `frontier` | empty **and** every channel read | work remains — the ordinary case | a channel could not be read | — |
| `rearm` | a wave was emitted | — | a channel could not be read | nothing assignable |
| `verify` | the batch may close **and** the frontier is empty | refused — unlanded, or new work appeared | undetermined | — |

Nothing here writes state. The frontier is a **status**, and a stored status reads identically
whether it is current or six hours old — measured in this repository at 31 of 43 issues already
fixed while the tracker said otherwise. The plan lives in the campaign manifest, the cycle in the
`work-loop` ledger, the restart in the `revive` manifest; this skill adds no store.

Channels, blockedness, the ordering formula and every refusal:
[rearm-cycle.md](references/rearm-cycle.md).

## Terminal states — the only three

A gauntlet stops for one of these, and for nothing else. Each is recorded, not felt.

| Terminal state | Reached when | Recorded as |
|---|---|---|
| **Batch closed, loop continues** | `verify` says the batch may close | `campaign close`'s residue to `tidy`, then **re-arm** — this is not an end |
| **Budget** | `session-burn.sh` exits 3, or a usage limit lands | a `revive` manifest with the assignment and a not-before instant, so the fleet restarts without a human |
| **Every remaining item externally blocked** | each open item carries a `blocked-external` record with blocker, evidence and recommended next action | `work-loop iterate --outcome escalate`, three fields each, then the loop ends having said why |

**Not terminal.** An empty frontier — that is a *finding to verify*, because a frontier reads empty
when a channel could not be read. Everything else that is not a stop is `endless`'s "Not
checkpoints" list, which this skill's ownership table assigns to `endless` and therefore **cites
rather than copies**: the copy that stood here had already drifted, dropping one of its rows. Read
it there.

## Red flags

| Thought | Reality |
|---|---|
| "The campaign closed, so the gauntlet is done" | `close` asks whether the pinned items landed. It never asks what arrived. Re-arm. |
| "The frontier is empty, so there is nothing left" | Check which channels were read. An unauthenticated `gh` and a clean tracker print the same empty list. |
| "No open issues came back, so the tracker is clear" | That is exit 2's whole reason to exist. "I looked and found nothing" and "I could not look" are different answers. |
| "Two items in the layer — fan out" | Not until their surfaces are diffed. Two undeclared surfaces are not disjoint, they are unknown. |
| "It has no acceptance criteria, so it is small" | It has no *estimate*. Unscored and last, never discounted into the front of the queue. |
| "This item is blocked, so the loop stops" | A blocked item is not a stopped loop. It stays on the frontier and out of the wave; the loop takes the next one. |
| "Run until zero open items" | Unreachable at the measured creation rate. Freeze a batch, close it, re-arm. |
| "I will store the frontier so the next session need not recompute it" | That is the stale-tracker failure, recreated by hand. It is computed every time. |
| "I'll ask which batch matters more" | A question in an unattended run is not a pause, it is the end of the turn (ADR-0052). Score it, record the DEC, continue. |
| "Green before the rebase, so it lands green" | Gate the merged result. |

## Quick reference

| Need | Where |
|---|---|
| The channels, the ordering formula, every refusal | [rearm-cycle.md](references/rearm-cycle.md) |
| Whether to continue, relay or fan out at a checkpoint | `endless` |
| The cycle contract, the rubric, the critic packet, the ledger | `work-loop` |
| What a campaign contains and whether it may close | `campaign` |
| Launching and integrating one worker | `successor`; one alone is `/relay` |
| Is that worker stalled, dead or landed | `successor-manager` |
| Restarting the fleet after a shutdown or a limit | `revive` |
| What work exists, and its graph | `roadmap` |
| Verify a change to this skill | `cd .claude/skills/gauntlet && python3 -m unittest discover -s tests -t . -v` — confirm a **non-zero** collected count |
