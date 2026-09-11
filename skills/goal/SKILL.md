---
name: goal
description: Use when a run needs a destination that outlives the item in hand — setting an end goal for an unattended or endless loop, asking what a campaign is actually for, checking whether a goal has been reached, or noticing that a loop is still working but no longer on task. Also on "set a goal", "what are we aiming at", "when are we done", "stay on task", "the end goal", "goal drift", and when a session is about to be handed to a successor that will not remember why the work started.
metadata:
  origin: Odin
artifact: .claude/docs/goals/*.md
---

# goal — a destination a loop can still read after a context reset

> **Voice (ADR-0011).** Prose to human stays Odin. A goal record is a **deliverable**: it is written
> in normal English, because a successor three context windows from now has to act on it.

## What this is not for

A goal is the **standing destination** — the thing that is still true after the current item lands,
the current campaign closes, and the session that set it is gone. Four neighbours already own
shorter-lived objectives, and this skill is not a fifth copy of any of them.

| The task | Its owner | Why not this skill |
|---|---|---|
| What a *campaign* is for, and when it may close | `campaign` — the `objective` key in `.claude/skills/campaign/scripts/campaign.py` | A campaign is bounded by its own item set. A goal outlives the campaign and usually spans several. |
| What a *plan* builds, and how you know it worked | `blueprint` / `superplan` — the `**Goal:**` line `.claude/skills/blueprint/scripts/plancheck.py` refuses a plan without | One plan, one PR-sized objective. Deleting a plan deletes its goal; this record survives that. |
| What *one iteration* must achieve | `work-loop` — `success_criteria` in the twelve-field contract at `.claude/skills/work-loop/scripts/loop.py` | Per-iteration, and discarded when the loop closes. A goal is what the loop was opened *for*. |
| What to build next, and in what order | `roadmap` | An ordering over items. A goal says which orderings count as progress — it never picks the item. |
| Whether to keep going at all | `endless` | Continuation doctrine. This skill says what "done" means; that one decides whether to take another step toward it. |
| Whether the batch may close | `gauntlet` / `campaign close` | Those ask whether the *pinned items* landed. This asks whether the thing they were pinned for has happened. |

**The one thing this skill owns:** a committed, falsifiable statement of where a run is going, that a
session which has never seen this conversation can read and act on.

## Why a file and not a sentence in a brief

A goal stated only in a prompt dies with the context window that held it. The measured failure it
prevents is not forgetting the goal — it is **continuing to work without one**, which looks exactly
like working. A loop with no destination still picks items, still lands them, still reports progress,
and drifts, because every individual step is defensible.

So the record is committed (a successor in a fresh worktree can resolve it), carries no status (the
standing of a goal is computed at read time, never stored — ADR-0113), and is referenced by **slug**
downstream rather than copied, for the reason `campaign.py`'s `FORBIDDEN_COPY_KEYS` already gives:
two copies of a destination disagree, and the looser one wins silently.

## The record

One file per goal, at `.claude/docs/goals/<slug>.md`. A project subtree's goals go in that project's
own `docs/goals/`. Six fields, all required; the shape and each field's bar are in
[references/goal-record.md](references/goal-record.md).

```markdown
---
goal: <slug>
owner: <the session, role or human accountable>
scope: <harness | the project slug this goal belongs to>
---

# <one sentence: the destination, in the present tense>

## Objective

<what must become true. Not what will be done — what will be the case when it has been.>

## Done when

```sh
<a command>
```

<what its output or exit code must be.>

## Out of scope

- <something a reasonable reader would otherwise assume is included, and why it is not>

## Verified by

```sh
<the command that re-checks this record's own premises>
```
```

### `Done when` is a command, and that is the whole design

A goal whose completion is prose cannot be falsified, and an unfalsifiable destination is
indistinguishable from no destination at all — which is the failure this skill exists to prevent.
The rule is borrowed rather than invented: `work-loop`'s rubric already holds that a dimension you
cannot write an evidence command for is a judgment, not a dimension.

If the command cannot be written, the goal is not yet a goal. That is a finding about the goal, not
a reason to relax the field. Split it until each part has one, or record what could not be made
checkable **in the record itself** — `ci/rule-enforcement.md` § Three Honest Outcomes applies here
exactly as it does to a gate.

### There is no `status` field, and adding one is the defect

Whether a goal has been reached is computed by running `Done when`. Storing the answer creates a
second source of truth that is correct only until the next commit, and every reader afterwards
believes the stored one. Same rule, same reason, as the campaign manifest's refusal to store a
status (ADR-0113). `goal-check.sh` refuses a record carrying `status`, `progress`, `done` or
`complete` as a frontmatter key.

### `Verified by` is not a date

A record's premises expire. The field holds the command that re-establishes them, not the day
somebody last believed them — `learn`'s rule, applied to a destination. A goal whose `Verified by`
no longer exits 0 is not wrong; it is **unverified**, which is a different finding and gets said out
loud rather than assumed either way.

## Procedure

1. **Check for an incumbent.** `ls .claude/docs/goals/` and read what is there. Two live goals with
   overlapping destinations is the same defect as two implementations of one predicate — name the
   incumbent, and either extend it or record why this one differs (`consistency`).
2. **Write the destination in the present tense.** "Every open issue carries a reproducing command"
   — a state of the world, not a list of actions. If it reads as a to-do list, it belongs in
   `roadmap`.
3. **Write `Done when` as a command before anything else.** If step 2's sentence resists this, it
   was a wish. Rewrite it until a command decides it.
4. **Write `Out of scope` with a reason per line.** The entries that earn their place are the ones a
   reasonable reader would otherwise assume are included. An empty list is almost always a goal that
   has not been thought about yet.
5. **Land it**, then run `bash .claude/scripts/goal-check.sh .`
6. **Point the consumers at the slug**, never at a copy of the text.

## Who reads a goal, and what each one does with it

A goal is only worth writing if something consults it. Each of these names the record by slug:

| Reader | What it does with the goal |
|---|---|
| `endless` | At a checkpoint, asks whether the next step is toward the goal before asking which item is next |
| `work-loop` | An iteration whose outcome moves nothing toward the goal is a `revise`, not a `complete` |
| `gauntlet` | Orders the frontier by contribution to the goal; a batch that cannot move it is a finding, not a wave |
| `campaign` | A campaign's objective names the goal it serves; a campaign serving no goal is asked why it exists |
| `successor` / `handoff` | The goal slug travels in the handoff, so a fresh session inherits the destination and not just the next task |
| `factory` | A factory's `MISSION.md` cites the goal rather than restating it — the mission is unamendable by the agent, and a copied destination inside it cannot be corrected |
| `roadmap` | Unchanged: it still orders items. The goal says which orderings count as progress |

## Red flags

| Thought | Reality |
|---|---|
| "The goal is obvious from the plan" | A plan is deleted when it is spent. The goal is what outlives it. |
| "`Done when`: the work is complete" | Not a command, and not falsifiable. Nothing can disagree with it, including a run that achieved nothing. |
| "I'll record progress in the goal so the next session knows" | That is a status field wearing a different name. Progress is computed by running `Done when`. |
| "Out of scope: nothing" | Then the destination is unbounded, and every item is arguably on the way to it. |
| "The campaign objective already says this" | A campaign closes. If the destination survives the close, it is not the campaign's. |
| "The goal was reached, so delete the record" | Run `Done when` first. A goal reached is recorded as reached with the output that showed it, then tidied under CLAUDE.md item 8 like any spent artifact. |
| "Two goals, but they're related" | Related destinations are one goal with two `Done when` commands, or two goals with an `Out of scope` line each pointing at the other. |

## Quick reference

| Need | Where |
|---|---|
| The record's required shape and each field's bar | [references/goal-record.md](references/goal-record.md) |
| Check every committed record | `bash .claude/scripts/goal-check.sh .` |
| What the checker refuses, and the near misses it must not | `.claude/tests/goal-record.test.sh` |
| Whether to take another step | `endless` |
| What is left across every channel | `gauntlet frontier` |
| Why no status field | ADR-0113, and `campaign.py`'s `FORBIDDEN_STATE_KEYS` |
