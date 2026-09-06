---
name: mutations
description: Use the moment a change alters expected behaviour, data, logic, workflow, configuration or output — a new implementation, a rule change, a refactor, a config or dependency update, a schema or interface change, and equally a regression, a side effect, a corrupted value, an altered result or a mutation someone else's change produced. Also use on "did anyone check what that did", "this used to work", "the output changed", "that broke something downstream", "we changed the default", "is this safe to accept", "should we revert this", and whenever a change is proposed whose effect on behaviour, data integrity, security, dependencies or interfaces is predicted rather than observed. Fires on the change itself, whether or not anybody asked for it to be recorded.
---

# Mutations

A mutation is a change to expected behaviour, data, logic, workflow, configuration or output. It is
worth exactly one thing: **the observation that says what it actually did.**

**The deliverable is an entry in `MUTATIONS.md` that is OPEN until that observation exists**, and
then closed with a disposition and a citation of wherever the outcome was recorded. A change whose
effect nobody looked at is otherwise indistinguishable from one that was checked and behaved — that
indistinguishability is the whole subject of this skill, and `MU-0001` is it, measured.

## When this fires

Three gates. Any one of them fires this skill, and the work in hand pauses until the mutation is
assessed.

| Gate | Fires when |
|---|---|
| **Mutation** | a change is proposed or detected that affects behaviour, data integrity, configuration, security, dependencies, interfaces or expected outputs |
| **Oops** | a mutation produces an unexpected result, side effect or regression |
| **Mistake** | a mutation stems from an incorrect assumption, invalid action, missed requirement or preventable process failure |

The Oops and Mistake gates are **hand-offs, not duplicates**: they fire this skill to record the
mutation and its observation, and they fire `oops` / `mistake-to-gate` to record the occurrence and
build the guard. One event, two records, joined by a citation — see the boundary below.

### Which gate is mechanical

The Mutation gate. `mistakes-check.sh` refuses an entry whose `Actual observed impact:` reads
`pending` while its `Disposition:` claims anything but `needs review`:

```sh
bash .claude/scripts/mistakes-check.sh
```

That is "the workflow pauses until the mutation is assessed" as a repository-state predicate rather
than a sentence in this file. It also refuses any line in `MUTATIONS.md` parsing as a keyed
occurrence, and any entry missing a required field. A skill whose only enforcement is prose gets
skipped.

**The Oops and Mistake gates are deliberately not mechanical, and the residue is stated rather than
hidden** (ADR-0146). A tool-level matcher over "edits that touch behaviour, config or interfaces"
would fire on nearly every edit in this repository, and a detector with a ~100% hit rate carries no
information. Routing for those two is intent-level, in `.claude/hooks/odin-skill-gate.sh`.

## The cycle — pause, record, observe, dispose, continue

1. **Pause.** Do not finish the step that produced or surfaced the mutation. A prediction written
   after the result is known is not a prediction.

2. **Name the change with its artifact.** The command, the commit, the path, the config key. "The
   behaviour changed" is not a mutation; "landing by rebase rewrites shas, so `merge-base
   --is-ancestor` reports a landed branch as unmerged" is.

3. **Write `Expected impact:` now, before observing anything.** This is the field the pair turns
   on. It is never edited afterwards — a prediction revised once the answer is known destroys the
   only thing the ledger measures. No gate can see that; it is held by the author, exactly as
   test-first-ness is.

4. **Open the entry with `Actual observed impact: pending` and `Disposition: needs review`.**
   Any other disposition at this point is refused by the gate, and correctly: a verdict over an
   unobserved effect is a prediction wearing a verdict's label.

5. **Observe.** Run the command that would show the mutation's effect, on the surface it reaches —
   the consumers listed in `Location:`, not the change itself. An observation is a measurement with
   its command or artifact, never a reading of the diff.

   | The mutation touches | Observe with |
   |---|---|
   | behaviour | the test or command that exercises the changed path, before and after |
   | data | a query over the affected rows, counted |
   | configuration or a default | the consumer that reads it, run |
   | an interface or dependency | the callers, built or type-checked |
   | output | a diff of the produced artifact, not of the producer |

6. **Dispose.** One of five, and each names what happens next:

   | Disposition | Means | Next |
   |---|---|---|
   | `accepted` | the observed impact is acceptable, whether or not it was expected | cite where the outcome landed |
   | `corrected` | the mutation stays, its effect was repaired | cite the correcting change |
   | `reverted` | the mutation was undone | cite the revert |
   | `escalated` | the decision is not this session's to make | cite the issue or ADR carrying it |
   | `needs review` | no observation yet — the open state | keep observing |

7. **Convert, when the mutation is recurring or risky.** The conversion goes wherever it belongs,
   not into this ledger: a pre-change check or post-change validation (`mistake-to-gate`), a test
   case (`test-driven-development`), a rollback procedure or approval requirement in the owning
   doc, a workflow rule (`rules-distill`). This ledger records that it happened and where it went.

8. **Continue** the work that was paused, and say in the commit that it was.

## The boundary — four files, four questions

This repository has four places a record can go, so an author must never guess. Ask in order; the
first yes names the file.

| # | Question | File | Why only this one |
|---|---|---|---|
| 1 | Has the change's actual effect been observed yet? **No** → | `MUTATIONS.md` | The other three are all written *after* their subject is settled. None can hold "made, not yet checked" |
| 2 | Did something go wrong, and is it an occurrence of a failure mode worth counting? | `MISTAKES.md` | It counts, and drives promotion at the fourth occurrence. Nothing else counts |
| 3 | Is there a hazard that recurs under a statable condition and needs a safeguard now? | `CAVEAT.md` | It converts at the first occurrence and is closed by a landed safeguard |
| 4 | Is it a durable outcome that landed? | `CHANGELOG.md` | The canonical change ledger (CLAUDE.md item 8) |

**What this does that `CHANGELOG.md` does not**, stated plainly because #886 asked for it said
rather than assumed: a `CHANGELOG.md` entry is a statement that something landed, written once,
never revisited, and **an unintended mutation has no entry there by construction** — nobody writes
a changelog line for a regression they have not noticed. This ledger holds the *question*, from the
moment the change is made until someone answers it, and holds the answer next to the prediction it
is being compared against.

One event can produce records in several files. A mutation entry **cites** the others as it closes;
it does not compete with them.

| Skill | Its subject | Why it is not this one |
|---|---|---|
| `oops` | one incident that already went wrong | its deliverable is a guard plus a counted row. A mutation may be entirely benign, and most are |
| `mistake-to-gate` | recurrence, and promotion at the fourth occurrence | it counts. Nothing here is counted, and no entry here carries a key |
| `caveat` | a hazard with a recurrence condition, closed by a safeguard | a caveat is about a *sharp edge*; a mutation is about a *change*. A benign approved config update has no hazard and no safeguard, and forcing those fields would make them meaningless |
| `learn` | something that should outlive the session, on a confidence rung | a finding about the world. A mutation is a change to this tree with a predicted and an observed effect |
| `systematic-debugging` | finding the cause of a failure | it runs *before* this when the mutation was detected rather than proposed — you cannot state a cause you have not found |
| `verification-before-completion` | evidence before a claim of done | it verifies the change did what it says; this records what it did to everything else |

## Failure modes

| Thought | Reality |
|---|---|
| "The expected impact is obvious, write it after" | Then it is one sentence, written now. A prediction recorded after the result is a description |
| "It's a small config change" | A default nobody chose is the most-cited shape in `CAVEAT.md`. Size predicts nothing about reach |
| "The tests pass, so it's observed" | The tests observe the change. `Location:` names the consumers; observe those |
| "It's clearly fine, mark it accepted" | Then the observation takes one command. The gate refuses `accepted` over `pending`, and it is right to |
| "This went wrong, so it belongs in MISTAKES.md" | It may be both. The keyed row goes there; the prediction, the observation and the disposition come here |
| "Nothing observable changed, so there is nothing to record" | An observation that found no change **is** the observation. Write it — that is the state `pending` is not |
| "Record it now, observe it later" | That is what the open entry is for, and it is legitimate. What is refused is claiming a verdict while it is open |

## Checklist

- [ ] The work that produced or surfaced the mutation is paused
- [ ] The change is named with its command, commit, path or config key — not as a category
- [ ] `Expected impact:` was written before anything was observed, and has not been edited since
- [ ] `Location:` names the consumers the mutation reaches, not only the file that changed
- [ ] The entry opened at `Actual observed impact: pending` / `Disposition: needs review`
- [ ] The observation is a measurement with its command or artifact, over the consumers
- [ ] The disposition is one of the five, and names what happened next
- [ ] `Outcome recorded in:` cites the CHANGELOG entry, `M-NNNN`, `C-NNNN` or revert sha
- [ ] Where the event was also an occurrence, `oops` ran and the entry cites the `M-NNNN`
- [ ] Where the mutation is recurring or risky, the check, test or rule landed in its own home
- [ ] `bash .claude/scripts/mistakes-check.sh` is green
- [ ] The paused work is finished, and the commit says the pause happened
