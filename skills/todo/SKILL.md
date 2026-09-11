---
name: todo
description: Use when a session needs a task list and the native TaskCreate/TaskUpdate tools are unavailable, failing, or not firing — "TaskCreate isn't working", "track these steps", "keep a todo list", "what's left in this session", "mark that one done", or the task gate refusing a write because nothing is tracking the work. Also when a coordinator, a work-loop, a gauntlet wave or a factory lap needs a checkable list of items that survives a context reset.
metadata:
  origin: Odin
artifact: .claude/skills/todo/scripts/todo.py
---

# todo — a facade over the one store, and deliberately not a second one

> **Voice (ADR-0011).** Prose to human stays Odin. The item text a caller writes is a
> **deliverable**: normal English, because a successor has to act on it.

## What this is not for

**This skill introduces no store.** That is the whole design, and everything below follows from it.

| The task | Its owner | Why not this skill |
|---|---|---|
| Tracking a task list at all, when the native tools work | `TaskCreate` / `TaskUpdate` | The cheaper route, and the one `odin-task-gate.sh` checks first. This skill is what you reach for when it is unavailable — never instead of it. |
| The cycle a list of items belongs to — its contract, its outcomes, its ledger | `work-loop` — `.claude/skills/work-loop/scripts/loop.py` | That engine owns the store. `scripts/todo.py` **invokes** it and holds no ledger logic of its own. |
| Which work exists across the repository, and in what order | `roadmap` | A durable backlog. A todo list is this session's, and dies with the contract that declared it. |
| Where the whole run is going | `goal` | A destination that outlives every item. |
| What a mid-run interruption displaced and when the return is owed | `off-topic` | A committed checkpoint, not a list. |
| What a campaign contains and whether it may close | `campaign` | A manifest across sessions. |

**The one thing this skill owns:** making the work-loop ledger usable as a todo list without
learning the twelve-field contract first, and without anything new being written to disk.

## The two routes, and why there is no third

`odin-task-gate.sh` accepts exactly two pieces of evidence that a session is tracking its work:

| Route | Evidence | Established by |
|---|---|---|
| Native | a marker under `.claude/.runtime/tasks/<session>` | the `TaskCreate`/`TaskUpdate` PostToolUse arm |
| Ledger | an **open** work-loop ledger at `.claude/.runtime/work-loop/<session>.json` whose own `session` field matches | `loop.py open` |

The ledger route exists because of M-0043 (harness:RM-0337) — a session doing tracked, bounded work
through `work-loop` was being refused by a gate demanding a `TaskCreate` it had no reason to call.

**A third route is refused by a gate, not by a paragraph.** Every additional thing the task gate
would accept moves it one step closer to a `touch`, and the gate's value is entirely that its
evidence is hard to fake. `.claude/scripts/todo-store-check.sh` asserts the count in both
directions, and separately asserts that `todo.py` opens no file for writing, creates no directory,
and still invokes `scripts.loop` — because a facade that calls nothing would pass every refusal by
doing nothing at all.

## Where the list actually lives

Two fields of the work-loop ledger, and nothing else:

| The list is | The ledger field |
|---|---|
| the items | the contract's `expected_outputs`, declared once when the ledger opens |
| which are done | `completed_actions`, which `loop.py` derives from the iteration records |

So an item's standing is **computed at read time**, never stored — the same rule as the campaign
manifest (ADR-0113) and the goal record, for the same reason: a stored answer is correct until the
next write and believed forever after.

The consequence worth planning around: **the item list is declared up front and does not grow.** A
new item arriving mid-run is either out of scope (`out-of-scope` scores it), or the contract was
wrong and the loop closes and reopens. That friction is deliberate — a list that grows faster than
it is drained is a loop that never terminates, and `loop.py`'s `iteration_limit` is what notices.

## Procedure

### 1. Ask which route is live — never assume

```sh
python3 .claude/skills/todo/scripts/todo.py route --root . --session "$CLAUDE_CODE_SESSION_ID"
```

Exit 0 means the gate is satisfied and there is nothing to do here. Exit 1 names both routes as
absent and prints the two commands below. It **reports** and never arms: a probe that established
the thing it probes is `ci-gate/fixture-reads-ambient-state` wearing a helper's clothes.

### 2. Declare the items, open the ledger

```sh
python3 .claude/skills/todo/scripts/todo.py contract --session "$SID" \
    --item "gate: write goal-check.sh" \
    --item "matrix: one BLOCK case per condition" \
    --item "register: four registries and the runbook counts" > /tmp/contract.json

cd .claude/skills/work-loop
python3 -m scripts.loop open --root "$REPO" --session "$SID" --contract /tmp/contract.json
```

**The text before the first colon is the item's stable id.** Declared rather than derived from
position, because a positional id renumbers when an item is inserted and every record written
before the insertion then names the wrong item.

The synthesised contract carries one rubric dimension, and it is a real one:

```
dimension        items-open
evidence_command python3 .claude/skills/todo/scripts/todo.py count-open --root . --session <SID>
baseline         the number of items declared        target 0        direction lower-is-better
```

A dimension whose evidence command cannot be run is a judgment wearing a dimension's clothes, and
`loop.py` refuses one. This one is runnable and its number is derived from the ledger.

### 3. Work, and record each item as it lands

```sh
python3 .claude/skills/todo/scripts/todo.py list  --root . --session "$SID"
python3 .claude/skills/todo/scripts/todo.py done  --root . --session "$SID" --item gate
```

`done` records a `continue` iteration naming that item, and passes the new open count as the
dimension's measure. **Record each item as it finishes** — batching the updates at the end means
a session that dies mid-run leaves a ledger claiming nothing was done.

An item nobody declared is refused by name. Recording it would put a second list inside the ledger,
which is the failure this skill exists to avoid, arrived at from the inside.

### 4. Close it

```sh
cd .claude/skills/work-loop
python3 -m scripts.loop close --root "$REPO" --session "$SID" --outcome complete
```

`complete` over a list with open items is `loop.py`'s call to refuse or accept, not this skill's.
The list surviving the close is what `handoff` carries forward.

## Red flags

| Thought | Reality |
|---|---|
| "TaskCreate is broken, so write a TODO.md" | That is a third store, and `todo-store-check.sh` refuses it by filename shape. The fallback already exists and the gate already accepts it. |
| "Add a `done: true` field so reading is cheaper" | A stored status is a second source of truth, correct until the next write (ADR-0113). `count-open` derives it. |
| "A new item came up — append it to the list" | The list is `expected_outputs`, declared once. Score it with `out-of-scope`, or close the contract and open a new one. |
| "Skip `route` and just open a ledger" | An open ledger over a session that already has the native marker is two answers to one question, and the second is the one nobody maintains. |
| "Record all five items done at the end" | A session that dies at item three leaves a ledger saying zero. Record each as it lands. |
| "The facade can cache the item list to save a read" | A cache is a store. `todo-store-check.sh` reports the first `open(..., "w")`. |
| "`loop.py` is heavy for four items" | That is exactly what `contract` is for. The weight is in typing the contract, and this writes it. |

## Quick reference

| Need | Where |
|---|---|
| Which route is live for this session | `todo.py route --root . --session <SID>` |
| Synthesise a contract from an item list | `todo.py contract --session <SID> --item 'id: text' …` |
| The list, open and done | `todo.py list --root . --session <SID>` (`--json` for a machine) |
| Record one item complete | `todo.py done --root . --session <SID> --item <id>` |
| The rubric's evidence command | `todo.py count-open --root . --session <SID>` |
| Open / close the ledger | `work-loop` — `loop.py open`, `loop.py close` |
| Why there is no third route | `M-0043`, harness:RM-0337, and `.claude/scripts/todo-store-check.sh` |
| What the gate refuses, and the near misses it must not | `.claude/tests/todo-store.test.sh` |
