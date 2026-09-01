---
name: projects
description: Use when starting or switching to a project subtree, when a project's own README, changelog, ADR set, decision ledger, roadmap or data-provenance manifest may be missing, or when deciding whether a project is initialized, active, dormant or completed.
artifact: projects/*/README.md
---

# Projects — one operating model, from onboarding to completion

Almost every phase of a project's life already has an owner. This skill is the **routing table**
over those owners, plus the two things that have no owner today: the **project-switch ritual** and
the **per-project artifact checklist**.

There is no engine here, and no state anybody sets by hand. A project's state is *read* from its
tree — see [state-transitions.md](references/state-transitions.md).

## What this is not for

| The task | Its owner | Why not this skill |
|---|---|---|
| Which item to work on next, what is left to build | `roadmap` | A project's remaining work is items in that project's own roadmap. This skill never ranks or picks. |
| Understanding an unfamiliar codebase | `codebase-onboarding`, `repo-scan` | Those own *how* to read a codebase. This skill only says that phase comes first and names them. |
| Planning before source is edited | `superplan`, `blueprint` | Plan depth is a shipped standard with its own gate. Nothing here relaxes or restates it. |
| Handing work to another session | `/relay`, `successor` | A handoff is a session-level act. A project switch inside one session is not a handoff. |
| The project's vocabulary | `domain-modeling` | Terms live in the project's own `CONTEXT.md`, written by that skill. |
| Continuing past the item in hand | `endless` | Continuation is about the loop, not about the project. |
| Applying this model to a specific project subtree | that project's own docs | This skill describes the model; it never writes into anybody's project. |

## The project-switch ritual

Run this on **starting** a project and on **switching** to one, before any other action. The failure
it prevents is silent: nothing errors when the previous project's scope is carried into a new one —
the work is simply aimed at the wrong target, and reads as correct all the way to the commit.

Each step is an assertion about *this* project. State the answer; do not assume it carried over.

1. **Name the subtree.** `projects/<slug>/`, and whether it is a nested repository of its own — the
   harness enumerates such a project, skips it, and says so on every run. Its git state is not the
   harness's git state.
2. **Read the project's own goal and scope**, in its own words, from its init card or README. The
   previous project's goal is not evidence about this one.
3. **Assert the memory namespace** — `task:<slug>`. Operational records are read-only context
   inside a project and are never merged into project memory.
4. **Assert the id sequences are the project's own.** Roadmap ids and decision ids are per-file
   counters, so the same number names different work in every project. Outside the project, cite
   them qualified: `<slug>:RM-0007`.
5. **Assert the project's own gate** — the command that is *this* project's CI — and run it once
   before changing anything, so a later red is attributable to your change.
6. **Walk the artifact checklist** in [operating-model.md](references/operating-model.md), and read
   its warning about silence.

## Red flags

| Thought | What it means |
|---|---|
| "Same repo, I already know the setup" | A subtree is not the harness. Step 1 has not been answered. |
| "The tests were passing earlier" | Earlier, in a different project's gate. Step 5 has not been run. |
| "I'll record this decision in the ADR set" | Which ADR set? A project's decisions never enter the harness sequence. |
| "The guard found nothing, so it is clean" | Or it is not configured. Read the checklist's warning. |
| "This project has no roadmap, so I'll just start" | A project with more than one unit of remaining work owes one. Absence is a finding. |

## Reference

- [operating-model.md](references/operating-model.md) — every lifecycle phase and the skill that
  owns it; the per-project artifact checklist.
- [state-transitions.md](references/state-transitions.md) — the four states, and the evidence each
  transition requires.
