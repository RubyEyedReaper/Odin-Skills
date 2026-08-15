---
name: blueprint
description: Use when one roadmap item is too big for a single plan — a feature spanning multiple PRs, sessions or agents. Decomposes an objective into cold-start-executable construction steps with a dependency graph, registers them as roadmap children, and gates the result on a mechanical check. Not for single-PR work (superplan) or for choosing what to build (roadmap).
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Skill
metadata:
  origin: community (antbotlab/blueprint, via ECC) — rewritten as an Odin procedure
---

# Blueprint

## Overview

One objective in, a **construction plan** out: numbered tasks, each executable by an
agent that has read nothing but the task itself.

Blueprint's product is not prose. It is a set of task briefs plus a dependency graph,
and it is finished when `plancheck` passes and every task exists as a roadmap child
item. A plan nobody can dispatch cold is not a plan.

## When to use

Fire when **any** of these is true of a single item:

| Predicate | Why blueprint and not superplan |
|---|---|
| more than ~2 days of work | one plan doc stops being holdable in context |
| more than one deployable surface (schema + API + UI) | each surface wants its own review and its own PR |
| not verifiable until several pieces land together | the verification story has to be designed, not assumed |
| superplan produced more than ~12 steps | that is a decomposition failure reported as a step list |
| work will span sessions or agents | context loss between sessions is the thing briefs prevent |

**Not** for: a single-PR change (`superplan`), deciding *what* to build (`roadmap`),
choosing between options (`decision-matrix`), or a fork-analysis planning document —
see *Two kinds of plan* below.

## Two kinds of plan

Odin writes two artifacts both called "plan", and they have different shapes:

| Artifact | Written by | Shape | Gated by |
|---|---|---|---|
| **Decision plan** (`.claude/docs/plans/*.md`) | `writing-plans` after `grilling` | forks, alternatives, recommendations, a Done section | plan-depth rubric (ADR-0027) |
| **Construction plan** (this skill) | `blueprint` | Task N briefs with Files / steps / verification / exit criteria | `plancheck` **and** the rubric |

`plancheck` checks construction plans. Running it against a decision plan reports
missing `Files:` blocks that a decision plan has no reason to carry — that is the tool
being pointed at the wrong artifact, not a defect in either.

## The pipeline

Five phases. Do not skip 4.

### 1. Research

Establish what exists before decomposing it.

```sh
git -C . rev-parse --abbrev-ref HEAD          # branch you will cut from
git -C . log --oneline -15                    # what landed recently
```

Read, in this order: the roadmap item (`roadmap.json` entry, `links.prd`, acceptance),
`CONTEXT.md` for the vocabulary, the relevant ADRs, and the files the item names.
If the item's acceptance criteria are thin, **stop and grill** — `roadmap` Gate 1 owns
that predicate, and blueprinting an unsharpened objective produces briefs full of
guesses.

Pre-flight the workflow mode: with `git` + `gh` available, tasks get branch/PR/CI
steps; without them, tasks edit in place and verification is local commands only.

### 2. Design

Decompose into **one-PR-sized tasks**, 3–12 typical. Each task:

- produces something independently reviewable — a reviewer could reject task 4 and
  still merge tasks 1–3;
- owns a coherent slice of the system, not a technical layer sliced across features;
- folds its own setup, config, fixtures and docs into itself rather than leaving them
  to a "wiring" task at the end.

Then assign, per task: **dependencies** (task numbers only), **files touched**,
**verification command**, and **rollback** (revert the PR, or the explicit undo when
the change is not revertible — a migration, a published artifact).

Two tasks may run in parallel when they share no files and neither consumes the
other's output. Express this as dependency edges and let the layering fall out;
do not hand-assign "wave 2".

### 3. Draft

Write the plan to `.claude/docs/plans/<slug>.md` (harness) or `<root>/docs/plans/<slug>.md`
(project). Every task follows the brief template in
[`references/step-brief.md`](references/step-brief.md) — read it before drafting.

The one rule that makes briefs work: **a brief is self-contained.** The executing agent
sees its own task and nothing else. "Similar to Task 2" is a plan failure; repeat the
content. So are `TBD`, `TODO`, "add appropriate error handling", "handle edge cases",
and any reference to a type or function no task defines.

### 4. Review — the gate

Mechanical first:

```sh
cd .claude/skills/blueprint && python3 -m scripts.plancheck <path-to-plan.md>
```

Exit 0 clean, 1 with findings, 2 unreadable. `--json` for machine use. It reports:

| Code | Means |
|---|---|
| `no-goal` | no `**Goal:**` — the plan cannot be checked against its own outcome |
| `no-tasks` | no `### Task N …` sections — nothing dispatchable |
| `no-files` | a task names no files — the executor cannot know what to touch |
| `no-verification` | no `Run:`/`Expected:`/`Verify:`/shell block — "done" would be a claim |
| `no-exit-criteria` | no `**Exit criteria:**` — the task ends when the executor gets bored |
| `placeholder` | `TBD`, `TODO`, "similar to Task N", "as needed" — unresolvable cold |
| `forward-dependency` | a task depends on one that runs later |
| `unknown-task` | a task refers to a task the plan does not define |

**This gate is not advisory.** Fix findings and re-run until clean.

Then judgment, which no script supplies: dispatch a reviewer agent (`planner` or
`architect`) against the plan with the question *"pick the task you would most likely
fail to execute with only this brief in front of you, and say what is missing."*
Fix every critical finding before phase 5.

### 5. Register

A construction plan that is not on the roadmap is invisible to `next` and will be
re-planned by the next session.

```sh
cd .claude/skills/roadmap
python3 -m scripts.roadmap add --title "<task 1 title>" --kind feature --parent RM-00NN
python3 -m scripts.roadmap set RM-00NN --link plan=<path-to-plan.md>
python3 -m scripts.roadmap set RM-00XX --deps RM-00YY      # the plan's edges
python3 -m scripts.roadmap waves --limit 3                 # confirm the layering
```

The parent item stays as the objective; the children are the tasks. Dependencies come
straight from phase 2 — the roadmap then computes the waves, so the plan never stores
a wave number that a later edge change would contradict (DEC-0001).

Report: task count, the wave layering, and the first wave's items. Nothing else.

## Executing a blueprint

Blueprint plans, it does not execute. Hand off to `subagent-driven-development`
(fresh agent per task, review between) or `executing-plans` (inline, batched).

The executing agent is given **one task brief**, verbatim. If it asks a question the
brief should have answered, that is a phase-3 defect: fix the brief in the plan, then
re-dispatch. Do not answer it in chat — the next session will ask again.

Mark progress on the roadmap, not in the plan's checkboxes alone:

```sh
python3 -m scripts.roadmap set RM-00XX --status done
```

## Mutation protocol

Plans meet reality. Every change to a live plan is a recorded edit, never a silent one.

| Situation | Do |
|---|---|
| a task is bigger than believed | **split** it: replace with N tasks, renumber nothing — append `Task 7a/7b`, keep the edges |
| a missing prerequisite appears | **insert** it as a new task with the highest number, and add the edge; numbering is identity, not order |
| a task turns out unnecessary | **skip**: strike the heading, keep the section with one line saying why, remove its edges |
| the objective itself changed | **abandon** the plan, record why in `CHANGELOG.md`, re-blueprint |

Never renumber tasks — task numbers are referenced by roadmap children, briefs, and
commit messages. Re-run `plancheck` after any mutation; edges are the thing mutations
break.

## Common mistakes

| Mistake | What happens |
|---|---|
| slicing by technical layer ("all the schema", "all the UI") | no task is independently reviewable; nothing merges until everything does |
| a "wiring it together" final task | the integration risk is concentrated where it is discovered last |
| briefs that reference earlier tasks | the plan only works read front-to-back, which is not how it is executed |
| storing a wave number in the plan | contradicts the graph after the first dependency change |
| skipping `plancheck` because the plan "looks fine" | the findings are exactly the things that look fine and read cold as ambiguous |
| blueprinting an item with thin acceptance criteria | briefs full of guesses; grill first (`roadmap` Gate 1) |
| leaving the tasks off the roadmap | `next` cannot see them; the work is re-planned next session |
