---
name: off-topic
description: Use when a new task arrives mid-run and displaces work already in flight — an interruption, a pivot, being sidetracked, parking what you were doing, or coming back to it afterwards. Also on "before I forget", "hold that thought", "where were we".
metadata:
  origin: Odin
---

# Off-topic — the work a mid-run task displaced

## The stance

A task introduced into a run in flight creates an **obligation to return**, and that obligation is
the only thing worth writing down. Everything else about the interrupted work is already recorded
somewhere with an owner — the item, the plan, the branch, the ledger. A checkpoint that copies them
becomes a second, staler opinion about facts it does not own.

So a checkpoint here is **a pointer plus a relation**: which work was displaced, what displaced it,
what condition means the displacement is over, and what to do first on returning. Nothing else.

**The return itself is held by the agent. Nothing can make a session resume.** What is mechanical is
that an *owed* return cannot stay invisible: the checkpoint is committed, so every checkout reaches
the same verdict about it, and `.claude/scripts/off-topic-check.sh` reports a return that has come
due. That is the honest limit of the automation, stated here rather than implied away.

Rigid skill. The trigger predicate, the schema and the refusals are not judgment calls.

## What this owns, and what it must not restate

This skill sits *across* other skills. A second copy of a rule drifts, and the looser copy wins
silently — so every row names an owner, and nothing in that column is re-derived here.

| The task | Its owner | Never re-derived here |
|---|---|---|
| One bounded cycle: the contract, the six outcomes, the stall predicates, the ledger | `work-loop` | All of it. `pause` is the adjacent outcome — see **Against `pause`** below — and this skill neither extends the vocabulary nor writes to that ledger |
| What work exists, its identity and its status | `roadmap` | Item ids, the slug rule, `next`/`waves`. A checkpoint *references* an item and never holds a second opinion about it |
| Whether to keep going at all, and the three continuations | `endless` | The continuation predicates. `endless`'s checkpoint is a decision point in a long run; this one is a debt |
| Handing a whole session forward | `handoff` | The six-element brief. A handoff written while a checkpoint is open names it; that is the whole interaction |
| What a campaign contains and whether it may close | `campaign` | Landedness by content, the channel order, the refusal to store a status (ADR-0113) |
| What residue may be deleted | `tidy` | An open checkpoint is not residue. Closing one is a return, never a sweep |
| Planning the displaced work, or the new one | `superplan`, `writing-plans`, `blueprint` | The plan-depth bar |
| Whether a defect found mid-run is fixed now or routed and left | `out-of-scope` | The six weighted dimensions and the deferral record. A `fix-now` verdict can *produce* a displacement, and then this skill fires on its own predicate — never because that one asked it to |

### Against `pause`

`work-loop`'s `pause` outcome describes this event well: state is checkpointed, the loop ends, and
`resume` re-enters exactly. Two reasons this is a separate skill rather than that outcome:

- **A `work-loop` ledger exists only where somebody opened a contract.** Displacement arrives most
  often in a session that never did — an integration part-done, a branch mid-review, a plan being
  executed without a loop around it.
- **`pause` ends the loop; a displacement does not.** The interrupting task runs *inside* the same
  run, and the return is owed while the loop is still live.

Where a loop *is* open, use both: record the checkpoint here, and record `pause` there if the loop
genuinely ends. They answer different questions — `pause` says this cycle stopped, a checkpoint says
a return is owed.

## When this fires

**Recurs when:** all three hold.

1. **Work is in flight** that a reader could not reconstruct from the tree alone — a claimed roadmap
   item, an open plan, an unpushed branch, an integration part-done.
2. **A new task arrives that is not that work**, and finishing the in-flight work would not finish it.
3. **The new task displaces rather than interleaves** — it needs an edit, a branch or a plan of its
   own.

The origin of the new task does not matter. A defect the agent finds mid-run displaces exactly as
hard as one a human introduces.

| Not a trigger | Why |
|---|---|
| A question | Answering displaces nothing. A question is not a task. |
| A defect fixed in the same breath, inside the same unit of work | Part of the work, not a displacement of it. |
| One skill routing to another | Skills route to each other constantly inside one unit of work. |
| Work picked up *after* the current unit lands | Nothing was displaced. That is `roadmap next`. |

## The procedure

1. **Write the checkpoint before starting the new task**, not after. A checkpoint written afterwards
   records what is remembered, which is the thing that fails.
2. **Fill every field from a reference**, never from a summary of state. Format, field by field, and
   what each refusal catches: [checkpoint-format.md](references/checkpoint-format.md).
3. **Commit it in the same change as the pivot.** It is shared state or it is nothing.
4. **Do the new task.**
5. **Return**: re-read `resume_to`, do that, then delete the checkpoint file in the commit that
   resumes. Deletion *is* the close — there is no `status` field to flip, because a status reads
   identically whether it is current or six hours old (`campaign`, ADR-0113).

Nested interrupts stack by `parent`. Return is **LIFO**: a parent is not closed while a child is
open, and the check catches a child whose parent is already gone.

## What is checked, and what is not

`bash .claude/scripts/off-topic-check.sh` — the findings, the exit codes, why a `manual` resume
condition is the honest-but-weaker form, and what no gate here claims:
[return-contract.md](references/return-contract.md).

The one-line summary: an owed return, a dangling reference, an orphaned child, a cycle, a forbidden
key and an unreachable channel are all findings. **Whether the return actually happened is not
checked** — only whether an unmet obligation is still sitting in the tree where anyone can see it.

## Quick reference

```sh
bash .claude/scripts/off-topic-check.sh          # report open checkpoints and owed returns
bash .claude/scripts/off-topic-check.sh --json   # the same, machine-readable
```

| Store | `.claude/docs/off-topic/` — committed, one JSON per checkpoint, `README.md` as the anchor |
|---|---|
| Steady state | Empty but for the README. A non-empty directory *is* the signal |
| Exit 0 | No checkpoint, or every open one still legitimately open |
| Exit 1 | A finding — most often a return that has come due |
| Exit 2 | The store could not be read. Never reported as clean |

## Common mistakes

| Mistake | What goes wrong |
|---|---|
| Copying the interrupted work's state into the checkpoint | A second source of truth, stale on the first push. Reference the branch and the plan; they update themselves |
| Writing a `status`, `state` or `progress` field | Refused by the check. A status cannot say whether it is current |
| Leaving the checkpoint behind after returning | The next reader sees an obligation that was already met, and stops believing the store |
| Reaching for `manual` by default | It is unresolvable by construction, so nothing can tell you the return came due. Use a roadmap item or an issue whenever one exists |
| Writing the checkpoint after the new task is underway | It then records memory rather than state, which is the failure this skill exists to prevent |
