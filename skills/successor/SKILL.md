---
name: successor
description: Use when work must be delegated to sessions other than this one — spawning a successor session, running a fleet of parallel sessions, coordinating several agents across separate branches or worktrees, handing a campaign to workers, or when a single context window cannot hold the work left. Also use when a delegated session has gone silent, stalled, or produced a branch that must be integrated.
---

# Successor sessions

## Overview

A successor is a **separate OS-level Claude session** — its own context window, its own harness, its
own lifetime — launched by `.claude/scripts/odin-relay.sh` and reachable through `claude agents`.
Not a subagent. A subagent shares the parent's lifetime, returns text, and dies with the turn; a
successor outlives the session that spawned it, pushes commits, and is integrated by branch.

**Core principle: a successor knows only what its handoff says.** Everything else it must rediscover
at its own cost, or guess at yours. The handoff bar below is therefore the whole skill; the rest is
procedure around it.

Rigid skill. The phases run in order; the bar has no optional elements.

## When to use

| Situation | Fire |
|---|---|
| Hand THIS session's work forward, one successor | `/relay` — already does it, has its own gates |
| Two or more independent workers, coordinated | **this skill** |
| A campaign with waves, per-worker branches | **this skill** |
| Parallel work inside one context window | `dispatching-parallel-agents` (subagents, not sessions) |
| A delegated session stalled or wedged | **this skill** → Phase 3 |
| A worker's branch is ready to land | **this skill** → Phase 4 |

One successor = `/relay`. A coordinated fleet = this skill.

Not for: work that fits one session (just do it), or work whose steps share mutable state — parallel
sessions on one checkout corrupt each other's index (ADR-0054).

## The handoff quality bar

Every handoff carries all six. A missing element is not a gap the worker fills in — it is a wrong
turn the worker takes confidently.

1. **Relevant skill set** — a `## Suggested skills` section naming the skills that own the work.
2. **Assigned task and desired outcome** — what to build, and what "done" looks like as an artifact.
3. **Current context** — progress so far, decisions already made and their reasons, constraints.
4. **Open questions, risks, dependencies, next actions** — what is unresolved and what blocks what.
5. **Authorization scope** — an explicit `edit only: <paths>` line. What the worker may touch, and
   what belongs to a sibling worker or the coordinator.
6. **Standing invariants** — restated, not assumed (see below).

Plus the frontmatter: six fields, `## Suggested skills`, qualified roadmap ids. Those three are
already **refused** by `odin-relay.sh` (ADR-0038, ADR-0050, ADR-0056) — cite them, do not restate
their rules, and never re-implement the checks.

Template: `references/handoff-template.md`.

### Standing invariants — in every handoff, in these words

- The successor runs in **its own independent session**, not as anyone's subagent.
- The successor is **monitored** by the delegating session until it lands or is stopped.
- The successor is **autonomous** — never `AskUserQuestion`, on any fork, including scope
  (ADR-0052, `.claude/rules/common/decision-authority.md`). It decides, records, continues.
- The successor speaks **terse Odin voice** (ADR-0011), which never lapses mid-skill.
- The successor **arms its own posture** as its first action: `bash .claude/scripts/odin-autonomous.sh on`.
  A coordinator cannot arm a child — the claim ticket is stamped by the claiming session's own next
  hook (ADR-0051).

## The five phases

Run in order. Each has commands in `references/fleet-runbook.md`.

### 1. Provision

One git worktree per worker, cut from `main`, named by change class. Copy
`.claude/settings.local.json` into each — gitignored, holds this machine's permissions, and a worker
without it stalls on prompts nobody is there to answer. The launch directory must carry `CLAUDE.md`
and a non-empty `.claude/skills/`, or the relay refuses (ADR-0056).

**Reserve every id up front** — ADR, DEC, and roadmap numbers — and write each worker's ids into its
handoff. Ids are allocated by reading a ledger; parallel workers reading the same ledger all win, and
the collision surfaces at integration when it is most expensive.

### 2. Launch

`odin-relay.sh --handoff <absolute path> --name <worker>`, once per worker, **`--dry-run` first**.
Handoffs live under gitignored `.claude/.runtime/handoff/`, so a worker in another worktree cannot
see a relative path — pass an absolute one.

### 3. Monitor

Two signals, because either alone lies: session `state` from `claude agents --json`, and branch
movement from `git ls-remote`. A wedged session reports `running`; a finished worker may idle with
its branch already pushed.

```
idle, no branch movement    →  claude logs <id>
wedged / looping            →  claude stop <id>, amend the handoff, relaunch
all workers silent at once  →  a shared dependency died, not twelve dead agents — check it first
```

Relaunch from an **amended** handoff. The same handoff produces the same stall.

### 4. Integrate — coordinator only

Workers never merge. For each branch, in a fixed order:

1. **Scope-diff** the branch against its declared authorization. A file outside `edit only:` is a
   finding, not a merge.
2. Rebase onto `main`, resolve in the worktree, re-run the gates on the **merged result**.
3. Land by fast-forward. `main` stays linear (CLAUDE.md item 7).
4. **Recompute** shared counts and registries — inventory numbers, category lists — rather than
   textually merging two workers' edits to the same line.

### 5. Teardown

Remove the worktree, delete the branch, stop any session still attached. A spent worktree left
registered keeps Layer 1F's concurrency guard armed against the main checkout (ADR-0054).

## Red flags

| Thought | Reality |
|---|---|
| "The worker can figure out the scope" | It will pick one, and it will be wider than yours. Write element 5. |
| "I'll arm autonomous mode for them" | Impossible. Posture is claimed by the session's own hook (ADR-0051). |
| "Same handoff, just relaunch it" | The handoff caused the stall. Amend first. |
| "All the agents died" | One shared dependency died. Check it before relaunching anything. |
| "I'll let workers mint their own ADR numbers" | Both pick the same one. Reserve up front. |
| "Just this once, a subagent will do" | A subagent cannot push a branch or outlive the turn. |
| "The branch was green before the rebase" | It said nothing about what lands. Gate the merged result. |
| "I'll merge and let the worker keep going" | Integration is serialized and coordinator-owned. |

## Quick reference

| Need | Where |
|---|---|
| Copyable handoff | `references/handoff-template.md` |
| Commands per phase | `references/fleet-runbook.md` |
| Operational facts learned the hard way | `references/fleet-runbook.md` § Pinned facts |
| Why sessions and not subagents | `.claude/docs/adr/0059-successor-skill.md` |
| One successor, no fleet | `/relay`, `.claude/commands/relay.md` |
