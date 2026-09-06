# The return contract — what is mechanical and what is not

## What no hook can do

No hook resumes a session. A `Stop` handler can print; a `PreToolUse` handler can refuse; neither can
make the next turn continue the work the last one left. Anything claiming otherwise is describing a
reminder and calling it a mechanism.

So the automation here is narrower and stated plainly: **the return is held by the agent, and an owed
return cannot stay invisible.** The checkpoint is committed, so every checkout reaches the same
verdict about it; `.claude/scripts/off-topic-check.sh` reports the moment the obligation comes due.

Three shapes were available and the reasons the other two lost:

| Shape | Verdict |
|---|---|
| A `Stop`-time reminder | Session-local, unreadable by anyone else, silent on a session that died. Not the primary. |
| A gate that reds whenever a checkpoint exists | Reds on the normal case — a checkpoint is legitimately open for the whole duration of the new task — and a gate that reds on the normal case gets disabled. |
| A gate that reds when the checkpoint is open **and its interrupting task has finished** | Chosen. That is the moment the return becomes owed, and finishedness is read from a channel the checkpoint does not own. |

## The findings

`off-topic-check.sh` reads every `*.json` in `.claude/docs/off-topic/` and reports:

| Finding | Means |
|---|---|
| `owed-return` | `resume_when` is met and the checkpoint is still there. The return is due |
| `dangling-reference` | An `interrupted` or `interrupting` reference resolves to nothing |
| `orphaned-child` | A `parent` the store does not hold — a parent closed before its child, against LIFO |
| `parent-cycle` | A `parent` chain that returns to itself |
| `forbidden-key` | A `status`-shaped key, or a key outside the schema, at any depth |
| `malformed` | Unparseable JSON, a missing required field, or a `resume_when.kind` outside the three words |
| `channel-unreachable` | A resume condition that *should* resolve and could not — an unreadable roadmap, a tracker that could not be reached |

## The exit codes

| Exit | Means |
|---|---|
| 0 | No checkpoint, or every open one still legitimately open |
| 1 | One or more findings |
| 2 | The store could not be read at all — directory or `README.md` missing, or unreadable |

**Zero checkpoints is the steady state and exits 0.** That is the one place a `count: 0` is honest
here, and it is only honest because exit 2 covers the case it would otherwise hide: a check pointed
at a path that does not exist would also select none. The `README.md` in the store is the existence
anchor that separates the two — an empty enumeration from a directory that is *there* means nothing
is owed; an empty enumeration from a directory that is not is a broken check reporting clean.

## `channel-unreachable` is a finding, not a silence

A resume condition resolved through a channel that could not be reached is reported
`channel-unreachable` and **never** `met` — ADR-0069's discipline, which exists because `no drift`
from an instrument that could not look is how 76 of 77 open issues went uncaptured.

`manual` is the exception, and deliberately not a finding: it declares up front that no channel
exists, so reporting it as an unreachable one would be noise on every run. It is counted and listed
instead, which is the whole of what a `manual` condition buys.

## What this does not claim

- **Not** that the return happened. Only that an unmet obligation is visible in the tree.
- **Not** that the checkpoint describes the interrupted work correctly. Two references are resolved
  — `roadmap_item` against the roadmap and `plan` against the filesystem — and existence is all that
  is proved: the right id for the wrong work resolves exactly as well.
- **Not** anything about `branch` or `work_loop_session`. They are labels, deliberately unresolved: a
  branch is *supposed* to be gone once the work lands, so checking it would red on the normal case,
  and a gate that reds on the normal case gets disabled.
- **Not** that a missing checkpoint means nothing was displaced. Nothing detects a displacement that
  was never written down; that clause is held by the trigger predicate in `SKILL.md`, by an agent.
