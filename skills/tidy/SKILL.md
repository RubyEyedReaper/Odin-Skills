---
name: tidy
description: Use when deciding whether something that has outlived its purpose may go — a spent plan, a retired workflow, inactive project material, a cache, a completed session, a branch. Also on "can this be deleted", "is this still needed", "clean this up".
metadata:
  origin: Odin
---

# Tidy

> The deliberate act, never the sweep. A path arrives; a verdict comes out. Nothing here searches
> for candidates, and nothing here removes anything.

## What this is not for

| The task | Its owner | Why not here |
|---|---|---|
| **Finding** what is stale, leaked or accumulating | `leek` | It diagnoses and never remediates ([ADR-0088](../../docs/adr/0088-leek-diagnoses-never-remediates.md)). This skill performs no discovery: a directory argument is a usage error, not a candidate list. |
| Deleting a branch | **nobody, permanently** | [ADR-0093](../../docs/adr/0093-branch-landedness-is-a-question-about-content.md) — the error is asymmetric and force-push is blocked, so a wrongly deleted branch has no reflex that restores it. A branch is always `refuse`. |
| Retiring a workflow | `workflows` | Retirement is a lifecycle transition on a manifest, with its own enforced refusal — not a filesystem removal. |
| Deciding a plan is spent | the contract | CLAUDE.md item 8: a plan is spent once its work is in living docs or code **and recorded in `CHANGELOG.md`**. This skill reads that record; it does not form the judgement. |
| Sweeping session-keyed runtime state | `runtime-retention.sh` | Those classes are swept mechanically on a schedule. A class nobody declared is swept by nothing — a declaration bug, not a tidy decision. |
| Deciding what to work on next | `roadmap` | Removing spent material is not planning. |
| An open checkpoint under `.claude/docs/off-topic/` | `off-topic` | It looks like residue and is an outstanding obligation. Closing one is a *return* — the file is deleted by the commit that resumes the work, never by a sweep. Always `refuse`. |

## When to use

- A plan doc, report, brief or scratch file looks finished and something must say whether it may go
- A `leek` finding named a path and the next question is what to do about it
- Before deleting anything in this repository, when the answer is not already obvious
- "Can this be deleted?" / "Is this still needed?" / "Clean this up"
- A branch is being considered for deletion — ask, and get told no, with the reason

## Get the verdict

```sh
bash .claude/skills/tidy/scripts/tidy-verdict.sh <path>
bash .claude/skills/tidy/scripts/tidy-verdict.sh --root <dir> <path>
bash .claude/skills/tidy/scripts/tidy-verdict.sh <branch-name>
```

One path per run. Exit codes are the interface: `0` remove, `10` retain, `11` refuse, `12`
unresolved, `2` usage.

## The four verdicts

| Verdict | Means | Do |
|---|---|---|
| `remove` | A removal ledger records the basename — its content survived somewhere | Run the printed **dry-run** line, read what it names, then run the **apply** line. Two commands, in that order, both read before either runs. |
| `retain` | No ledger names it, so this copy may be the only one | Keep it. If it really is spent, **write the ledger record first**, then re-run — the record is the durable half, the file is the disposable one. |
| `refuse` | The argument is a branch | Nothing. Not now and not with better evidence. Report it and move on. |
| `unresolved` | The path resolved to nothing, or no ledger was readable | Report the gap and fix what could not be read. A check that could not look is a finding, never a silence. |

**Every verdict other than `remove` keeps the material**, and that is the whole shape: a wrong
retain costs disk, a wrong removal costs the content. The full rules — what counts as evidence, how
the basename is matched, why history and appearance are not evidence, and how to override a verdict
honestly — are in [`references/verdict-rules.md`](references/verdict-rules.md).

## The removal is yours, not the script's

`tidy-verdict.sh` prints commands and runs none of them. The dry-run and apply lines come from one
template with a single flag slot, so they differ at exactly one token — which is what makes
"dry-run first, on the same code path as the apply" checkable instead of promised.

Read the dry-run's output before running the apply. A dry-run whose output nobody read is a
ceremony, and the apply is the step with no reflex behind it.

## Red flags

| Thought | Reality |
|---|---|
| "Let me scan the plans directory for stale ones" | That is discovery. Run `leek`, then bring it one path at a time. |
| "The branch is fully landed, so it can go" | Landedness is computable and is not authorization. `refuse` is permanent. |
| "No record, but it is obviously spent" | Then write the record. The verdict is not the obstacle; the missing ledger entry is. |
| "The script could not resolve it, so there is nothing there" | It could not look. That is a finding to report, not an absence to act on. |
| "I will delete it and note it in the changelog after" | The record is what survives. Write it first, or the removal leaves nothing saying where the content went. |
| "`--dry-run` printed something, close enough" | Read it. That is the entire point of the pair. |
