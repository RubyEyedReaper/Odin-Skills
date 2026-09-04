---
name: automate
description: Use when a repeated action might be worth automating — something done a third time, a call whose result was probably already known, a script about to be written, a level to run it at, or an existing automation nobody can justify keeping.
artifact: .claude/scripts/*.sh .claude/hooks/*.sh
artifact_pattern: ^#\s*record:
---

# Automate — what to automate, at which level, and whether it is still worth having

Three questions, in this order. Skipping the first is how a session automates its own waste.

1. **Was the result already derivable** from what the session held? Then the fix is to stop making
   the call, not to make it faster. [redundant-call-check.md](references/redundant-call-check.md).
2. **At which of six levels** may it run — what may it touch, who must agree, how is it withdrawn?
3. **Is an automation that already exists still worth having?** Answered by the retirement predicate
   recorded when it was created, in [automation-record.md](references/automation-record.md).

## What this is not for

| The task | Its owner | Why not this skill |
|---|---|---|
| A preventable failure that a repository-state predicate detects | `mistake-to-gate` | A gateable predicate is never an automation decision. If a script can decide it and the answer can be wrong, it is a gate with a matrix, not an automation with a record. |
| A reusable chain of skills and its lifecycle | `workflows` | A chain is a sequence agents follow. This skill decides whether a step should exist at all. |
| A bounded work cycle and its ledger | `work-loop` | That is one cycle's contract and outcomes. Automation is about what recurs across cycles. |
| Whether to keep going after this item lands | `endless` | Continuation doctrine. This skill never decides what happens next. |
| What to work on | `roadmap` | An automation is never a roadmap item's substitute. |
| Retrying a command until it goes green | `verification-loop` | A retry loop needs no record and no approval. |
| Finding waste already present — context, caches, orphaned sessions | `leek` | Diagnosis of an existing leak. This skill is consulted before a new artifact exists. |
| Writing the skill, script or rule the automation turns out to need | `skill-creator`, `writing-skills`, `rules-distill` | Those author the artifact once this skill has said which one, at which level. |
| Whether something in this tree already does it, before any of the six verdicts are reached | `consistency` | A verdict of *automate* over a job an existing script already does is a second implementation, and this skill never asks that question. |

## The six verdicts

Exactly one applies to a candidate. `eliminate` and `retire` are why this skill exists; reaching for
`automate` first is the failure mode it is written against.

| Verdict | Means | What follows |
|---|---|---|
| `eliminate` | The result was already derivable from material the session held | Do not automate. Stop making the call; if it recurs because the earlier result was lost, repair retention — the handoff, the plan, the ledger |
| `keep-manual` | Real, but too rare or too variable to be worth an artifact | Nothing is built. Record the verdict so the third person to ask does not re-litigate it |
| `assist` | The gathering is mechanical; the decision is not | Automate the evidence, never the conclusion. The artifact prints; an agent decides |
| `automate` | Mechanical end to end, and the same every time | Pick a level below, fill the record, build it |
| `gate` | Preventable failure, detectable from repository state | Hand to `mistake-to-gate`. A gate needs a matrix proving it fires and fails, which an automation record does not carry |
| `retire` | An existing automation's retirement predicate has fired | Run its recorded rollback. Say in the change that it was retired and which predicate fired |

A candidate with no verdict is not "pending" — it is `keep-manual` until someone argues otherwise.

## The six levels

Ordered by **reach**: what the automation can touch, and how many future sessions it binds. Every
level names its approval boundary and its rollback, and **rollback is never optional** — an
automation you cannot withdraw is a permanent change wearing a temporary one's clothes.

| Level | What it is | Approval boundary | May touch | Rollback |
|---|---|---|---|---|
| `ad-hoc` | One command composed in the session, nothing persisted | The acting agent, within the task's existing authorization | Only what the task already authorizes | The inverse command, **named before the command runs**. No inverse means this is not an `ad-hoc` candidate |
| `scratch` | An uncommitted script in the session's scratch directory | The acting agent | The scratch directory, plus what the task authorizes | Delete the file. Session teardown does it anyway; that is the level's whole safety property |
| `committed` | A script in `.claude/scripts/` (or the project's), run by hand | The reviewer of the commit that adds it | Only the paths named in its own header | `git revert` of the commit that added it — safe because nothing yet calls it |
| `routed` | The script becomes a step in a skill or a workflow chain | The owner of that skill or chain; in this repository, the coordinator who owns the routing surfaces | Whatever the calling step's session already authorizes | Remove the step and bump the chain's manifest version. The script survives at `committed` |
| `gated` | Wired into the verification suite's gate list — it can now fail the suite for everyone | The owner of the gate list, and only with a matrix proving the gate fires **and** fails (`mistake-to-gate`) | The tree read-only; it reports, it does not repair | Delete its step line from the gate list. The script stays runnable by hand |
| `unattended` | Runs with no human in the turn, via the local nightly wrapper | The repository owner, explicitly and once, against a written allowlist | Only the allowlist in its record. Never hooks, settings or rule files | Remove the gate from the one list the wrapper reads. An automation with its own entry outside that list deletes that line — **never** by editing a workflow |

### The `unattended` level routes to the local nightly script

`nightly-audit.sh` is a wrapper over the single gate list in `ci-local.sh`: a gate added there is
picked up nightly with no second edit. That is the whole mechanism, and it is why an automation
proposing its own schedule is adding a second registration for something already registered.

**Never propose a workflow schedule trigger, and never dispatch a run remotely.** `gh workflow run`
and `gh run rerun` are blocked always-on (`common/security.md`, safety-guard Layer 1D) because a
remote dispatch tests the pushed tree rather than the one being edited — a green result describing
code that no longer exists locally. Reading a run a push already started is unrestricted and is how
the remote suite is meant to be consulted.

The pull at this level is real: the sentence "and then just run it nightly" arrives already formed.
Reach `unattended` only by adding to the list the wrapper already reads.

## Not levels — hooks, settings and rule files

**Never write a hook, a settings file, or a rule file from inside the session doing the automating.**
These are not the top of the ladder. They are off it, because their reach is every future session's
ability to work at all.

- **A hook that fails to parse denies every subsequent tool call to the session that wrote it**,
  which then cannot repair itself. That has happened in this repository.
- **`.claude/settings.json` decides whether the guards run at all**, for every future session. A
  change there is not an automation; it is a change to what automation is permitted to be.
- **A rule file with no `paths:` frontmatter is always-on** and costs context on every turn of every
  session, forever.

An automation that needs one of these **proposes** it: a separate, deliberate change, made from a
fresh session, with the syntax validated before the write lands. Proposing is not the same as
deferring — name the file, the change and the validation command in the record, and hand it on.

## The record

An automation declares ten fields **before it exists**: name, trigger, verdict, level, derivability,
approval, touches, rollback, retirement predicate, owner. None is optional, `rollback` least of all.
Field by field, with what goes wrong when each is absent, and a worked example:
[automation-record.md](references/automation-record.md).

The record lives in the plan document of the change that introduces the automation, with a pointer
line in the artifact's own header. Not a repository-wide ledger: an append-at-creation list nobody
edits at retirement reads exactly like an accurate one.

## Red flags

| Thought | Reality |
|---|---|
| "I've done this three times, script it" | Three times is the trigger to run the derivability check, not the answer to it |
| "It's cheap to just re-run the command" | Cheap per call is how a redundant call survives review. The cost is the context it spends and the answer it displaces |
| "Automating it makes it reliable" | Automating a derivable call makes the waste reliable |
| "I'll add the rollback later" | There is no later. A record without a rollback is a permanent change |
| "It's obviously safe, so the level doesn't matter" | The level is the approval boundary. Skipping it means nobody agreed |
| "A hook would be so much cleaner" | And it denies every tool call in this session if it does not parse. Propose it; do not write it |
| "Then we run it nightly on a schedule" | The nightly wrapper already runs the gate list. Add to the list |
| "Nobody uses it, but it's harmless to leave" | That is `retire` with the predicate already fired |
