# The pause contract — what it does, and what it does not preserve

A user who is told their sessions are frozen, and later finds one gone, has been given a worse tool
than one who was told what the pause costs. This file is that telling.

## The measurement

Run 2026-09-03 on this host against session `5cd92413` (`pause-lab`), a throwaway successor launched
into its own worktree for the experiment. Method: `SIGSTOP` to the session's whole process tree,
sampled every ~20s, then `SIGCONT`. The subject emitted a heartbeat line per model turn, so
"frozen" and "dead" could be told apart from outside.

### Round 1 — a 4m32s freeze

| Channel | Before | During | After |
|---|---|---|---|
| Heartbeat (model turns) | `iter=21` at 23:35:18 | **stopped** | `iter=22` at 23:39:50 — resumed at the next iteration |
| `claude agents --json` | `state=working status=busy` | **`state=working status=busy`** | unchanged |
| `fleet-health.sh` | daemon UP, 18 registered | **daemon UP, 18 registered** | unchanged |
| Control + rendezvous sockets | present | **present** | present |
| Process states | `S` | `T` (all 13, MCP children included) | `S` |
| Upstream connections (ESTAB) | 17 | 17 → 16 → **7** | 7 |

The turn loop resumed. **Every channel a coordinator reads reported the frozen session as present
and working**, for four and a half minutes, while it did nothing at all. That is the M-0014
signature — five dead sessions rendering as ordinary for eight hours — manufactured on purpose.

### Round 2 — a 14-minute freeze

| Channel | Before | During | After |
|---|---|---|---|
| Upstream connections (ESTAB) | 5 (idle session) | **0**, from ~2 minutes in | 0 |
| The process tree | `S`, pids 1527513/1527543 | `T` | **gone** |
| Roster row | `attempt: 1` | unchanged | **`attempt: 2`, new pids** |

The supervisor killed the frozen session and respawned it. What came back was a **new process with
a new context window**, wearing the same session id and the same name. Nothing in any channel said a
pause had happened, and nothing said the context was gone.

## What follows, and is the decision

`SIGSTOP` is **not** a pause. Past some window the supervisor treats a frozen session as dead and
replaces it, and before that window every channel misreports it as working. Recorded as **DEC-0115**
(the option was vetoed on a measured constraint, not on taste), with the condition that would lift
the veto written into the record: a channel that reports a stopped process as stopped.

So this skill's `pause` means one of two things, and says which:

| Verb | What it does | When |
|---|---|---|
| **quiesce** | Stop the session *acting*, at its next tool boundary. The process stays alive and legible | A live session that will be resumed within minutes, by a human who is present |
| **checkpoint + stop + resume-at** | Write the checkpoint, stop cleanly, and let `revive` relaunch from a not-before instant | Anything that must survive a shutdown, a limit, or a gap longer than a coffee break |

## What a pause does not preserve — state this, do not imply it

| Lost the moment the pause takes effect | Lost as soon as the process does not survive |
|---|---|
| The in-flight upstream response | The context window — a reboot, an OOM, the daemon dying, or a long enough freeze each take it |
| Any subagent mid-turn | The `TaskCreate` list: runtime, per-session |
| Background jobs the session started | `claude logs` scrollback |
| The model's unwritten plan, its reading of the last tool result, and every intention not committed to a file | Uncommitted working-tree edits — present on disk, with no record of why |

**Everything durable must already be on disk before the pause is requested.** That is the whole
sentence, and it is what makes this control different from `handoff`, which writes the durable thing
as its first act.

## Reach — an orphan is not addressable the way a child is

| Class | Evidence | What pause means | If it does not answer |
|---|---|---|---|
| Rostered, live socket | a roster row **and** its own socket | the request is delivered over the message channel | `unconfirmed` — never `paused` |
| Rostered, no socket | a roster row alone | nothing; it is already gone | `absent` |
| Known but unrostered (orphan) | a register row, a manifest role, a worktree, a branch | **unreachable** — no channel exists to reach it through | `unreachable`, with its own exit code |

Two consequences, neither negotiable:

- **A send reports on the send.** A delivered pause request is not a paused session. Confirmation is
  a *second* measurement, never the delivery's exit code.
- **A peer may refuse.** Measured in the same experiment: a session sent an instruction by another
  session declined it as permission laundering, and was right to. Cross-session control is a request,
  not a command, and a control surface that assumes otherwise reports compliance it never had.

Cross-worktree reach is `claude stop` and the message channel only. A runtime ticket written in one
checkout's `.claude/.runtime/` reaches nothing in another's, and committing it would make a pause
into shared state with a lifetime — a status in a hat, which ADR-0113 refuses.

## Resume — "in sync" means ordered and barriered, never simultaneous

Relaunching N sessions at once is a launch burst, and a launch burst has already collided with a
flapping session-init hook and left registered sessions with no task (harness:RM-0518). The same
failure appeared unprompted while measuring this skill: the experiment's own successor was launched,
registered, reported `state=working` — and had been blocked at `UserPromptSubmit` by the claude-mem
hook, with no task at all.

So a resume relaunches **the coordinator, alone** (ADR-0121's rule, unchanged), confirms its first
prompt was *accepted* rather than that a session exists, and leaves the rest as findings for that
coordinator to act on. An absent worker is reported, never re-launched from here: two actors
provisioning the same worktrees is the collision `successor` Phase 1 exists to prevent.

## What no mechanism here can do

**Nothing can make a session resume.** A timed resume starts a *new* session that reads committed
state; it does not continue the old one's turn. The honest form of "resume exactly where it left
off" is: the branch, the plan, the roadmap claim, the campaign manifest and the checkpoint are all
on disk, and a fresh session reads them. Everything else was in a context window that no longer
exists.
