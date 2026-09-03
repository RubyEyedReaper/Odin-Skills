---
name: handoff
description: Hand this session's work to a separate successor session — write the handoff document, launch the successor, then monitor it. Use when a long-running session is out of context, when work must continue past this context window, or when another agent should pick the work up.
argument-hint: "What will the next session be used for?"
---

# Handoff — write it, delegate it, monitor it

A handoff **ends this session's ownership of the work**. Three phases, in order: write the
document, launch a successor session that continues the work in its own context window, then stay
on as its monitor. This session does not carry on building — it watches, integrates, and lands.

**Delegation is the default, not a follow-up step.** A handoff that stops at a written document
leaves the work in the context window it was written to escape, and the second step (`/relay`) is
the one nobody takes. The single documented exception is [Document only](#document-only) below.

One successor is this skill. A coordinated fleet — several workers, per-worker branches, waves —
is the `successor` skill (ADR-0059). Both launch through the same script and inherit its refusals;
neither re-implements them.

---

## 1. Write the document

`.claude/.runtime/handoff/<ISO8601>.md` — e.g. `.claude/.runtime/handoff/2026-07-09T13-04-22Z.md`
(colons are not path-safe on every filesystem; use `-` in the time portion).

`.claude/.runtime/` is git-ignored and is the established home for harness-internal session state,
so the handoff survives an OS temp sweep, stays out of every commit, and never reaches a remote.
Create the `handoff/` directory if absent. Do not write to the OS temp directory, and do not write
anywhere else in the workspace.

Copy this skeleton and fill it in:

```handoff-skeleton
---
created_at: 2026-07-09T13:04:22Z
project_id: odin
mem_class: operational
active_branch: harness/agent-token-discipline
plan_file: .claude/docs/plans/<name>.md
next_action: Run harness-audit, then open the PR
---

## Where the work stopped

One paragraph: what was being built, and the last thing that landed.

## In flight

Uncommitted edits, an open PR, a running gate — with paths, not contents.

An open checkpoint under `.claude/docs/off-topic/` is in flight too — name it and its resume
condition here (`off-topic`), or the successor inherits the branch without the debt attached to it.

## Next actions

1. The imperative first move, the same one as `next_action`.
2. What follows it.

## Open questions, risks, dependencies

What is unresolved, and what blocks what. Decide, record, continue — never stop to ask
(`.claude/rules/common/decision-authority.md`).

## Authorization scope

edit only: <paths this successor owns>

## Suggested skills

`roadmap` · `test-driven-development` · the skills that own this work.
```

All six frontmatter fields are required; write `null` only where the value genuinely does not
exist. `mem_class` uses the vocabulary of `.claude/docs/odin-memory-standards.md` — read the
current value from `.claude/.runtime/active-mem-class` rather than guessing it.

Three of these are **refused** by `.claude/scripts/odin-relay.sh` rather than warned about, because
the session that would read a warning is the one about to be cleared: a `project_id` that names the
project (ADR-0038), a `## Suggested skills` section that names skills (ADR-0056), and every roadmap
id written qualified — `harness:RM-0034`, never `RM-0034`, since ids are per-roadmap counters and a
successor has no memory of which roadmap was open (ADR-0050). Ids inside fenced blocks are exempt.

The six-element quality bar the body must clear — assigned task and desired outcome, current
context, open questions and risks, authorization scope, suggested skills, standing invariants — is
the `successor` skill's, stated once there. Read it before writing a handoff for work of any size.

If the caller passed arguments, treat them as what the successor should focus on, and shape
`next_action` and the body around them.

### What a handoff captures

**Ephemeral working state only** — where the work stopped, what was in flight, what to do next. It
is not a memory tier:

- **Durable facts** (a decision and its reasoning, a non-obvious root cause, a shipped capability)
  belong in the file tier — `CONTEXT.md`, `.claude/docs/adr/`. Write them there, then reference them.
- **Curated recall** belongs in claude-mem under the active class, guarded fail-closed by
  `.claude/hooks/odin-memory-guard.sh`.
- Nothing here is promoted to either tier automatically. A handoff is discardable by definition; a
  fact that matters beyond the next session does not belong only in one.

Do not duplicate PRDs, plans, ADRs, issues, commits or diffs — reference them by path or URL. Do
not paste raw tool output. Redact anything sensitive.

---

## 2. Launch the successor

```sh
bash .claude/scripts/odin-relay.sh --handoff <path> --name "<short title>" --dry-run
bash .claude/scripts/odin-relay.sh --handoff <path> --name "<short title>"
```

Dry-run first — it prints the command and launches nothing, and it is where a refused handoff
surfaces while there is still a session to fix it in.

The successor is a **separate OS-level session**: its own context window, its own harness, its own
lifetime, reachable through `claude agents` / `attach` / `logs` / `stop`. Not a subagent — a
subagent dies with the turn and cannot push a branch. It starts in the current working directory
with this repo's settings, hooks and guards, and connects to claude.ai on its own; passing
`--remote-control` would be cargo cult.

Pass an **absolute** handoff path when the successor will run in another worktree — handoffs live
under gitignored `.claude/.runtime/`, which a relative path cannot reach from there.

Then report, in this order: the successor's id, `claude attach <id>`, and the one-line next action
it picked up.

**This skill cannot clear or end this session.** No hook event returns a field that resets context
and `/clear` is a client command the agent cannot type (ADR-0038, ADR-0036). The relay makes
clearing cheap; the keystroke stays the user's. Never claim to have cleared anything.

---

## 3. Monitor — this session's remaining job

After the launch, this session is the **successor manager**: it watches, and it does not continue
the delegated work. Building on in parallel is how two sessions edit the same branch and lose each
other's commits.

Four channels, in this order, because each alone lies:

```sh
bash .claude/scripts/fleet-health.sh        # FIRST — is the daemon there at all
claude agents --json                        # id, state, cwd — a registry, not liveness
claude logs <id>                            # what the successor is actually doing
git ls-remote --heads origin '<class>/*'    # branch movement
```

`fleet-health.sh` comes first because the other three cannot report their own absence. The registry
is served by the daemon: when the daemon exits it keeps returning its last-known list, so a dead
session renders as `blocked` — indistinguishable from working. The script reads the daemon's
control socket from disk instead, which the subject cannot fake once it is gone (M-0014). It
**exits 2** when sessions are registered and no live socket exists — every background session is
dead, relaunch from amended handoffs — and **exits 3** when the registry could not be read at all,
where the honest conclusion is none.

**Each channel establishes less than it appears to.** Read the third column before acting on any
one of them — a channel answering is not the same as the question being answered.

| Channel | What it establishes | Does not establish |
|---|---|---|
| `bash .claude/scripts/fleet-health.sh` | whether the daemon serving every other channel is alive | anything about one session's progress. It is the precondition for reading the other three, never a verdict about any one worker. |
| `claude agents --json` | the id set the daemon currently holds, and each session's cwd | liveness. The registry outlives the daemon that served it, so a dead session goes on rendering as `blocked` (M-0014). |
| `claude logs <id>` | what the successor's screen showed, once the escapes are stripped | that anything readable was returned at all — this channel exits 0 whatever it emits — and never what landed. |
| `git ls-remote --heads origin '<class>/*'` | that a branch exists at some sha, and when its tip last moved | that the work landed. Movement and ancestry are questions about shas; landedness is a question about content, and ancestry answered wrong for 56 of 110 branches (ADR-0093). |

`claude logs` is the channel that reports success while delivering nothing readable. Measured
2026-09-01 against session `ccf3304f`: `rc=0`, 65627 bytes, **6568 escape sequences** — cursor
addressing, 24-bit colour, absolute line positioning, ten sequences per hundred bytes. A screen
recording, not a log. Read it through the filter:

```log-filter
claude logs <id> 2>&1 | sed -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/\x1b[()][A-Za-z]//g' | tr '\r' '\n' | grep -v '^$' | tail -40
```

The `tr` matters as much as the `sed`: the source is a redrawn screen, so its lines are separated by
carriage returns and overwritten in place. Spacing is lossy — words the terminal placed with cursor
moves arrive run together — and that is this channel's honest ceiling. **`rc=0` from `claude logs`
does not mean the output was readable.** That is the general lesson, and it is why this table has a
third column: read what a command returns, never only what it exits.

| Observation | Read it as | Do |
|---|---|---|
| `running`, no branch push, quiet | working, or wedged — undecided | read the last turn through the filter above, never the raw channel |
| logs repeating one tool call | wedged | `claude stop <id>`, amend the handoff, relaunch |
| branch pushed, session idle | finished | integrate |
| every session silent at once | a shared dependency died | `fleet-health.sh` names it; check it first |
| gone from `agents --json` | exited or evicted | read its branch — the work may be pushed |

A relaunch always uses an **amended** handoff. The same document reproduces the same stall.

When the successor's branch is ready, integration is this session's: scope-diff the branch against
its declared `edit only:`, rebase onto `main`, re-run the gates on the **merged result**, land by
fast-forward, then remove the worktree and delete the branch. The procedure and its commands live
in `.claude/skills/successor/references/fleet-runbook.md` §4–5.

`successor-manager` owns this role as a skill (ADR-0105), with the ownership register and supervision
across whole fleets. Consult it for the verdict; the procedure above is what this session does.

---

## Document only

The one case that skips phase 2: the reader is **a human or another tool**, not a session — a
written summary requested for review, an artifact for a ticket. Say so explicitly in the report and
record the reason in the document's body, so the next reader can tell a deliberate exception from a
forgotten launch.

"The work is nearly done" is not that case. Neither is "the successor would only have to do a
little" — a handoff written at all means the context holding the work is spent.

---

## Red flags

| Thought | Reality |
|---|---|
| "I'll write the handoff and keep going for now" | The document was written because this context is spent. Launch, then monitor. |
| "I'll launch it after I finish this one last thing" | That is the failure this skill exists to fix — the last thing is never the last thing. |
| "A subagent can carry this" | A subagent dies with the turn and cannot push a branch. A successor outlives the session that spawned it. |
| "It says `blocked`, so it is waiting" | A dead session reads `blocked` too. `fleet-health.sh` first, always. |
| "Same handoff, just relaunch it" | The handoff caused the stall. Amend it first. |
| "I'll let the successor merge its own branch" | Integration is the monitor's, serialized. |
| "I'll arm autonomous posture for it" | Impossible — posture is claimed by the session's own hook (ADR-0051). The handoff tells it to arm its own. |
| "I cleared the session for them" | Nothing can. The keystroke is the user's. |

## Quick reference

| Need | Where |
|---|---|
| The command form of this skill | `/relay`, `.claude/commands/relay.md` |
| A fleet, not one successor | `successor` skill (ADR-0059) |
| Handoff quality bar, six elements | `.claude/skills/successor/SKILL.md` |
| Monitor / integrate / teardown commands | `.claude/skills/successor/references/fleet-runbook.md` |
| Why delegation is the default | `.claude/docs/adr/0077-a-handoff-delegates-and-the-delegator-monitors.md` |
