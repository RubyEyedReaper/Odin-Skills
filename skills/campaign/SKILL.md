---
name: campaign
description: Use when several delegated sessions are one piece of work — planning a campaign's waves and per-worker scope, tracking what has actually landed across it, or closing it out. Also when a campaign looks finished and that claim needs checking.
---

# campaign — the plan, and the refusal to close early

## What this is not for

A campaign is a unit of work larger than one session: an objective, a set of roadmap items, waves of
delegated workers, and a close-out. This skill owns two things — **what a campaign contains and in
what order**, and **whether it may be declared finished.** Everything else already has an owner.

| The task | Its owner | Why not this skill |
|---|---|---|
| Provisioning, launching, integrating, tearing down; the six-element handoff bar | `successor` | It owns the five phases. A campaign decides *what* is delegated and in what order; `successor` performs each delegation. Its bar is cited here, never restated — two copies drift, and the looser copy wins silently. |
| What is true of one delegated session right now | `successor-manager` | It owns the ownership register and the verdict computed from channels the session does not control. A campaign asks it; it never re-derives it, and nothing here opens a daemon socket. |
| Handing **this** session forward, once | `/relay` | One successor with its own gates. Not a campaign. |
| What work exists and what is left | `roadmap` | Campaign items **are** roadmap items. The manifest references qualified ids; it copies no title, no acceptance and no status. |
| One bounded cycle and its ledger | `work-loop` | A campaign's unit is an item, not an iteration. A loop asks whether to run again; a campaign asks whether it is done. |
| Deciding what residue to delete at the end | `tidy` | Close-out hands residue over as a list. It never deletes. |
| Whether to keep going at all | `endless` | Continuation doctrine. This skill says whether a campaign may close, never whether to start another. |

## The stance

**The manifest stores the plan. It never stores a status.**

Waves, per-worker scope, reserved identifiers, the objective — those are decisions someone made, and
a file is the right place for them. A status is different: it is a claim that was true at the moment
someone wrote it, and it goes stale **silently**. The file reads identically whether it is current
or six hours old.

Measured cost in this repository: in one backlog burn-down, 31 of 43 issues examined were already
fixed on `main` while the tracker still said otherwise. A `status: in-progress` field in a campaign
manifest is that same failure in miniature. So status is **computed at read time**, every time, from
the roadmap plus branch landedness — and `validate` refuses a manifest that carries one, because a
rule with nothing behind it erodes at the first convenient moment (ADR-0113).

## The record

One JSON manifest per campaign, committed under `.claude/docs/campaigns/<slug>.json`. What it holds,
what it deliberately does not, and why each field is there:
[campaign-record.md](references/campaign-record.md).

```json
{
  "campaign": "ten-skill-formalization",
  "objective": "formalize ten harness capabilities as skill packages",
  "base": "origin/main",
  "remote": "origin",
  "close_out": ["every item landed", "residue handed to tidy"],
  "waves": [
    {"wave": 1, "workers": [
      {"worker": "campaign-skill", "branch": "skills/campaign", "item": "harness:RM-0302",
       "scope": [".claude/skills/campaign/**"], "reserved": {"adr": ["ADR-0113"]}}
    ]}
  ]
}
```

## The engine

```sh
python3 -m scripts.campaign validate --root <repo> --manifest <file>
python3 -m scripts.campaign status   --root <repo> --manifest <file> --json
python3 -m scripts.campaign close     --root <repo> --manifest <file>
```

Run from `.claude/skills/campaign/`. Exit codes are the interface, so a caller greps nothing:

| Code | Means |
|---|---|
| `0` | validated / computed / **closeable** |
| `1` | refused — the manifest is malformed, or a named item is not done |
| `2` | **undetermined** — a channel could not be read |
| `64` | usage |

Nothing is written by any subcommand. `status` computes and prints; `close` computes, prints, and
refuses.

## Status, computed from three channels in order

1. **The remote can be consulted at all** — `git ls-remote --heads <remote> <branch>`. First,
   because the channels after it cannot report their own absence: a roadmap read from a stale
   checkout and a landedness computed against a base nobody fetched both answer confidently.
2. **The roadmap item** — `done` with a landed sha, or not. The half of `harness:RM-0302` before
   the colon is the roadmap's **slug**, not its `scope` field, which is the memory class; the
   identity rule belongs to the roadmap engine and is called, never copied.
3. **Landedness by content** — `bl_classify` from `.claude/scripts/lib/branch-landedness.sh`.
   **Never `git merge-base --is-ancestor`**: this repository lands by rebase merge, which rewrites
   every sha, and ancestry answered "not merged" for 56 of 110 branches that had in fact landed
   (ADR-0093).

| Row verdict | What the channels said |
|---|---|
| `landed` | roadmap `done` with a sha, and the content is in the base |
| `open` | the item is not `done`, or is `done` with no landed sha |
| `undetermined` | a channel could not be read, or the roadmap and the content **disagree** |

A disagreement is never resolved in favour of either side. The roadmap claiming `done` over content
that is not in the base is a finding for a human, not a tie to break.

## Close — the part with teeth

`close` **refuses** while any campaign item lacks a `done` status with a landed sha, and it names
each blocker. Not a warning, not a summary with a caveat.

**Undetermined outranks a named blocker.** A run that names three blockers *and* failed to reach the
remote has an **incomplete** blocker list, so it exits 2, not 1. "I could not reach origin"
collapsing into "nothing is blocking" is the exact shape of a campaign declared complete with work
still open.

On a clean close the residue — worker branches, worktrees — is printed **for `tidy`**. This skill
removes nothing.

## Red flags

| Thought | Reality |
|---|---|
| "I just computed the status, I'll cache it in the manifest" | That is the stale-tracker failure, re-created by hand. `validate` refuses it. |
| "The branch is not an ancestor of main, so it never landed" | Ancestry is a question about shas; landedness is about content. 56 of 110 (ADR-0093). |
| "I could not reach the remote, so nothing is blocking" | Those are different sentences. Exit 2. |
| "Every worker session reports done" | A session's own report of itself is not evidence — that is `successor-manager`'s whole stance. |
| "The roadmap says done, so it is done" | Then the content is in the base and the engine says `landed`. If it does not, the channels disagree and a human reads it. |
| "One item is still open, but it is nearly there" | `close` has one job and this is it. |
| "Close it, then let the last worker land onto main" | The campaign's own items are what close-out asserts. Land first. |
| "The manifest can hold the titles too, for readability" | A copied title drifts from the roadmap and nothing detects it. Reference the id. |

## Quick reference

| Need | Where |
|---|---|
| What the manifest holds, field by field | [campaign-record.md](references/campaign-record.md) |
| Delegating one worker, and integrating it | `successor` |
| Is that worker stalled, dead, or landed | `successor-manager` |
| Why status is computed and never stored | `.claude/docs/adr/0113-a-campaign-manifest-stores-the-plan-not-the-status.md` |
| Why landedness is content, never ancestry | `.claude/docs/adr/0093-branch-landedness-is-a-question-about-content.md` |
