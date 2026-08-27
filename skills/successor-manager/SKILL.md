---
name: successor-manager
description: Use when delegated sessions already exist and the question is who owns one or what is actually true of it — a worker that may be stalled, a fleet whose state nobody trusts, a branch to resume without re-running landed work.
---

# successor-manager — ownership, and the verdict

## What this is not for

This skill owns two things nothing else owns: **who is responsible for a delegated session**, and
**how that session's state is decided from evidence rather than from its own report of itself.**
Delegation itself already has an owner. Route there instead.

| The task | Its owner | Why not this skill |
|---|---|---|
| Provisioning, launching, integrating, tearing down; the six-element handoff bar | `successor` | It owns the five phases. This skill starts once a session exists and asks what is true of it. Its bar is cited here, never restated — two copies of a bar drift, and the looser copy wins silently. |
| Handing **this** session forward, once | `/relay` | One-off delegation with its own gates. One successor is `/relay`; a fleet is `successor`; this skill is what you consult about either afterwards. |
| Planning a multi-successor campaign, waves, campaign closure | `campaign` — harness:RM-0302, **not yet built** | Waves are a different item. The seam is named, not filled: this skill classifies the sessions a campaign launched; it does not decide what a campaign contains or when it is finished. |
| Parallel work inside one context window | `dispatching-parallel-agents` | Subagents. They share the parent's lifetime, return text, and die with the turn — there is no register row and no verdict to compute. |
| Whether to keep going at all | `endless` | Continuation doctrine. This skill says what happened; it never says whether to carry on. |
| Cost of a session that is progressing but expensive | ADR-0097's branch | The burn predicate and `session-burn.sh` live on `origin/harness/successor-burn-audit`. Named as a seam in [escalation-paths.md](references/escalation-paths.md); nothing here duplicates them. |

## The stance

**A session's own report of itself is never sufficient evidence.**

A wedged session reports that it is running. A dead session reports whatever the registry last knew,
because the registry outlives the daemon that served it — on 2026-08-19 five sessions died together
and went on rendering as ordinary for eight hours (M-0014, ADR-0072). Both are the subject
describing itself, and neither can report its own absence.

So the verdict is computed from channels the subject does not control, in a fixed order, and the
order is the point.

## The three signals, in order

```dot
digraph verdict {
  rankdir=LR;
  health   [label="1. fleet-health.sh", shape=box];
  down     [label="exit 2\nevery session dead", shape=box, style=filled, fillcolor="#ffcccc"];
  blind    [label="exit 3\nno verdict for anything", shape=box, style=filled, fillcolor="#ffe0b2"];
  movement [label="2. branch movement", shape=box];
  content  [label="3. landedness by content", shape=box];
  verdict  [label="one of five verdicts", shape=doublecircle];

  health -> down     [label="2"];
  health -> blind    [label="3"];
  health -> movement [label="0"];
  movement -> content;
  content -> verdict;
}
```

1. **`bash .claude/scripts/fleet-health.sh` first**, because the other two channels cannot report
   their own absence. Its exit code **gates** everything after it: `2` means the daemon is gone and
   every session is dead regardless of what the registry says; `3` means the registry is unreadable
   and **no verdict may be claimed for anything**.
2. **Branch movement** — `git ls-remote --heads origin <branch>` for the published sha, and the
   tip's own commit date against a staleness window.
3. **Landedness by content** — `bl_classify` from `.claude/scripts/lib/branch-landedness.sh`.
   **Never `git merge-base --is-ancestor`**: this repository lands by rebase merge, which rewrites
   every sha, and ancestry answered "not merged" for 56 of 110 branches that had in fact landed
   (ADR-0093).

The registry's **id set** is consulted, and nothing else from it. Membership is the daemon's account
of who exists, and step 1 has just proved that account current; the per-session field describing how
a session feels is the subject talking.

## Five verdicts, one of them mandatory

| Verdict | What the evidence said | Escalation |
|---|---|---|
| `live` | unlanded, in the registry, branch moved inside the window | none — leave it alone |
| `stalled` | unlanded, in the registry, branch quiet past the window | [escalation-paths.md](references/escalation-paths.md) § Stalled |
| `failed` | unlanded, gone from a registry the health gate proved current | § Failed |
| `landed` | `bl_classify` says the content is in the base | § Landed — retire the row |
| `undetermined` | the channels disagreed, or one could not be read | § Undetermined |

**`undetermined` is mandatory, not a fallback for laziness.** It is the honest answer when a
channel could not look, and a classifier without it invents a verdict silently — which is the
failure the whole ordering exists to prevent.

## The probe

```sh
bash .claude/skills/successor-manager/scripts/successor-status.sh          # the live register
bash .claude/skills/successor-manager/scripts/successor-status.sh --json   # one document
bash .claude/skills/successor-manager/scripts/successor-status.sh --session <id>
```

Exit codes are the interface, so a caller greps nothing: `0` every row live or landed, `1` findings,
`2` daemon down, `3` a register could not be read, `64` usage. `2` and `3` are forwarded from
`fleet-health.sh` unchanged, so a caller that already handles the fleet monitor handles this too.

**It reads only.** No fetch, no write, and it never consumes the state it inspects. Its matrix is
`.claude/tests/successor-status.test.sh`.

## The register

One `key<TAB>value` file per delegated session under `.claude/.runtime/successor-register/`, written
at launch by whoever launched it. What a row records and why each field is there is
[ownership-register.md](references/ownership-register.md). A row is **retired by an explicit act**,
never by an age sweep — the reasoning is in that file, and it is the reason no new retention class
is declared.

## Red flags

| Thought | Reality |
|---|---|
| "`claude agents` says it is running" | That is the subject reporting on itself. Run the health gate first, then read movement. |
| "The branch is not an ancestor of main, so it never landed" | Ancestry is a question about shas; landedness is a question about content. 56 of 110 (ADR-0093). |
| "All the workers show the same state, so the fleet is fine" | Every session reading identically is the signature of a dead daemon, not of agreement. |
| "I could not read the registry, so nothing is wrong" | "I looked and found nothing" and "I could not look" are different answers. That is exit 3. |
| "It is stalled, so relaunch it" | The same handoff produces the same stall. Amend it — and read § Stalled before re-running anything. |
| "Resume from where the transcript stops" | A transcript records what was attempted, not what landed, and a relaunched session has none. |
| "The row can go, the session is gone" | A gone session with an unlanded branch is the `failed` finding. Retiring the row deletes the evidence for it. |
| "It is expensive, so it is stuck" | Burning without progressing is its own pathology, and it is not `stalled`. See the burn seam. |
