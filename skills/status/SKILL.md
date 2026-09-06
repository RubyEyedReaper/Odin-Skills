---
name: status
description: Use when a human addresses the fleet itself rather than the work — asking what is running, for a status report, to pause or halt everything, to stop and wait a while before resuming, or to stop so they can start a fresh session. Also on "what's running", "how's it going", "hold everything", "freeze the fleet", "pause the workers", "resume in an hour", "wait 20 minutes then continue", "stop so I can pick this up in a new session".
metadata:
  origin: Odin
---

# status — the four words a human says to a fleet

## The stance

A status is **computed at read time, every time, and stored nowhere**. A status written to a file
reads identically whether it is current or six hours old — which is why `campaign` refuses a stored
status (ADR-0113), why `revive`'s manifest refuses one at any depth, and why nothing this skill
touches has a `state:` field.

The other three controls are not new capability. They are the **order the existing machinery runs
in** when a human says a word, plus the one thing no engine can supply: what the answer costs. A
pause that is not accompanied by what it fails to preserve is a promise the mechanism does not make.

Rigid skill. The bound, the channel order, the verdict vocabulary and the refusals are not judgment
calls.

## What this owns, and what it must not restate

| The task | Its owner | Never re-derived here |
|---|---|---|
| Handing this session forward, once, with a structured brief | `handoff` (`/relay`) | The six-element bar, the frontmatter, the relay's refusals. Control 4 **is** that skill — this one routes to it and adds nothing |
| Restarting an absent fleet unattended from a not-before instant | `revive` | The manifest, the five preconditions, the cron shape. A timed resume writes `not_before` into *that* manifest |
| What is true of one delegated session right now | `successor-manager` | The health gate, the five verdicts, the ownership register |
| Launching, integrating, tearing down a worker | `successor` | The five phases. An absent worker is a finding here, never a relaunch |
| Whether to keep going at all | `endless` | Continuation doctrine |
| Whether a batch may close, and what re-arms | `campaign`, `gauntlet` | Landedness by content, the frontier |
| One bounded cycle and its six outcomes, `pause` among them | `work-loop` | Its ledger and its vocabulary. **`work-loop`'s `pause` ends a cycle; this one stops a session acting.** Neither writes to the other's record |
| What a mid-run interruption owes on return | `off-topic` | The checkpoint format. A pause that needs a checkpoint writes **that** one — there is no second format |
| What a session says to another session | `s2s` | The message contract. A pause request travels that channel and inherits its rule: a send reports on the send |
| Whether the daemon is even there | `fleet-health.sh` | Its exits. They are forwarded, never re-interpreted |

The gap none of them fills, and the only reason this is a skill: **what the four words mean when a
human says them, in what order the machinery runs, and what the answer costs to read.**

## The four controls

| The human says | Verb | What runs | What it costs |
|---|---|---|---|
| "status", "what's running" | `status` | `status-report.sh` — one line, ≤300 codepoints, computed now | Detail is elided, severity-ordered; the counts never are |
| "pause", "hold everything" | `pause` | quiesce the reachable sessions; report the rest | Nothing is preserved by contract — see below |
| "stop and wait an hour" | `resume-at` | checkpoint, stop cleanly, write `not_before` into `revive`'s manifest | The context window. What comes back reads committed state |
| "stop so I can start fresh" | `handoff` | `handoff` / `/relay`, unchanged | Nothing — this is the control that preserves things, by writing them down first |

```sh
bash .claude/scripts/status-report.sh          # the line
bash .claude/scripts/status-report.sh --json   # the same, machine-readable and unbounded
```

## The report

`odin · daemon up · sessions 18 (5 live, 8 idle, 3 blocked, 2 absent) · tasks 29 · agents ? · …`

Everything about it — what the 300 is measured over, why elision is severity-ordered, why `unknown`
is never `0`, the exit codes — is [report-contract.md](references/report-contract.md). Three rules
are load-bearing enough to repeat here:

1. **Liveness is never read from the subject.** `fleet-health.sh` runs first, and a roster row is
   believed only when that row's *own* socket exists. A wedged session reports `running`; a dead one
   reports whatever the registry last knew, because the registry outlives the daemon (ADR-0072).
2. **A count that could not be obtained renders `?`.** An invented `0` reads as a finished fleet.
   `agents ?` is the steady state — no channel enumerates a session's in-context subagents.
3. **An elision announces itself, and never drops the failing worker.** Blocked and absent rows sort
   ahead of live; the tail is what goes. If the counts alone will not fit, nothing is cut and the
   report exits 5.

## Pause, and what it does not preserve

**`SIGSTOP` is not a pause, and this skill will not issue one.** Measured on this host: through a
4m32s freeze every channel — the roster, `fleet-health`, both sockets — reported the session as
present and working while its whole process tree sat in state `T`; through a 14-minute freeze every
upstream connection dropped to zero and the supervisor **killed and respawned the session**, so what
came back was a new process with a new context window wearing the same id. Recorded as **DEC-0115**.

What a pause preserves, what it does not, which sessions it can reach, what happens to one that does
not answer, and why "in sync" means ordered rather than simultaneous:
[pause-contract.md](references/pause-contract.md). The one-line version, which belongs in the
answer given to the user rather than in a footnote:

> Quiesce stops the session acting and preserves nothing by contract. The context window survives by
> luck. Everything durable must already be on disk before the pause is requested.

## Common mistakes

| Mistake | What goes wrong |
|---|---|
| Reporting a pause as done because the message was delivered | A send reports on the send. A peer can refuse, and one did during the measurement |
| Rendering an unobtainable count as `0` | Reads as a finished fleet — the exact failure ADR-0072 exists over |
| Storing the report so it can be read later | A stored status is indistinguishable from a current one. Re-run the command |
| Resuming eight sessions at once | A launch burst; it has already left registered sessions with no task (harness:RM-0518) |
| Treating an orphan like a child | There is no channel to it. `unreachable` is a verdict, not a failure to try harder |
| Shortening the report by cutting the tail | Only safe *because* it is severity-ordered. Cutting an unordered line drops the failing worker |
