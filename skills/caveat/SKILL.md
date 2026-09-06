---
name: caveat
description: Use the moment something turns out to behave differently from how it reads — a sharp edge, a gotcha, an exception, a footgun, a caveat, a surprising default, a command that succeeds while doing the wrong thing, a tool whose absence looks like a pass. Also use on "watch out for", "careful, X does Y", "that's a trap", "note that this only works when", "we should write that down", "make sure nobody hits this again", and on any oops or mistake moment where the workflow must pause, record the hazard with the condition under which it recurs, and land the safeguard before continuing. Fires on the hazard itself, whether or not anybody asked for it to be written down.
---

# Caveat

A caveat is a hazard met once. It is worth exactly one thing: the safeguard it buys.

**The deliverable is two artifacts, always both.** An entry in `CAVEAT.md` carrying the condition
under which the hazard recurs, and a landed safeguard — a hook, a validation check, a workflow rule,
or stated preventative guidance with a home. Recording without converting is the failure this skill
exists to prevent; a ledger of war stories teaches nobody and warns nobody.

## When this fires

- something behaved differently from how it reads — a command that succeeds while doing the wrong
  thing, a flag whose absence is a decision, a default nobody chose
- an exception was discovered: this works, except when
- a hazard was met that a later session would meet the same way
- an oops or mistake moment, where the workflow pauses here before continuing
- a review, audit or postmortem produced a "careful, X does Y" with nothing behind it

## What this is not

| Skill | Its subject | Why it is not this one |
|---|---|---|
| `oops` | one incident that already went wrong | its deliverable is a check plus a counted row in `MISTAKES.md`. A caveat may be met without anything going wrong yet. Both can fire on one event — see the cycle below |
| `mistake-to-gate` | recurrence, and promotion at the fourth occurrence | it counts. This converts at the first, so nothing here is counted |
| `learn` | something that should outlive the session, on a confidence rung | a caveat is not a finding about the world, it is a hazard in this tree with a condition |
| `improve` | a friction no script can decide | a caveat's safeguard is usually mechanical; where it cannot be, say so in the entry |
| `automate` | whether a repeated action is worth automating | that is a decision about effort. This is a decision about a hazard |
| `rules-distill` | rule text drawn from several skills or a threshold key | the rule half of a promotion. A caveat's guidance is one hazard's, not a distilled principle |

## The cycle — pause, record, remediate, continue

At an oops or mistake condition, the work in hand stops. It resumes after the safeguard, not after
the entry.

1. **Pause.** Do not finish the step that surfaced the hazard. The details are never as sharp again
   as they are now, and a hazard written down later is written down as a story.

2. **Name the hazard with its artifact.** The command, the path, the output. "The gate was wrong" is
   not a hazard; "`prisma migrate diff --shadow-database-url "$DATABASE_URL"` drops the database it
   is printing a diff of" is.

3. **State the condition under which it recurs.** This is the field that earns the file. Write the
   *state that reproduces it*, not the story: "a promotion touches a key whose rows contain an
   escaped pipe", never "someone was careless". A reader must be able to ask whether that state is
   present, and get an answer.

4. **Decide the safeguard's kind** — and prefer the mechanical ones, in this order:

   | Kind | Use when | Lands as |
   |---|---|---|
   | hook | the hazard is an action to refuse before it happens | a matcher in `.claude/hooks/`, with its case in the guard's matrix |
   | check | the hazard is a state a predicate can see | a gate in the owner's gate list, built by `mistake-to-gate` §1–§9 |
   | rule | competent people could disagree about a finding, so a gate would be disabled | rule text via `rules-distill`, at a `paths:`-scoped tier |
   | guidance | the condition is judgment and no predicate exists | the entry itself, plus the document whose reader meets the hazard |

   Reaching for `guidance` first is the tell that step 2 stopped too early. Try to state the
   predicate; only when it cannot be stated is guidance the honest kind.

5. **Land the safeguard, then write the entry.** In that order, so the entry cites something that
   exists. A `Safeguard:` naming work not yet done is the thing the gate refuses.

6. **Append the entry** with the shape `CAVEAT.md` documents, and run the gate:

   ```sh
   bash .claude/scripts/mistakes-check.sh
   ```

   It refuses an entry with no `Recurs when:` and an entry with no `Safeguard:`, so the conversion
   step is a repository-state predicate rather than a sentence in this file. A skill whose only
   enforcement is prose gets skipped.

7. **Continue** the work that was paused, and say in the commit that it was.

## Interoperating with `oops` and `mistake-to-gate`

One event can be both a caveat and a mistake. They are recorded in different files for a mechanical
reason, and the boundary is not a matter of taste:

- **`MISTAKES.md` is counted.** A row carries a failure-mode key, and `mistakes.py` derives
  recurrence from those keys to decide when a mistake has happened often enough to become a rule.
- **`CAVEAT.md` is not.** No entry here carries a key. A second file able to hold one would make
  every count an undercount, silently — the ladder would stop firing for any key split across the
  two, and both files would look healthy (DEC-0092, and the ADR recorded with it).

So when an event is both, do both, in this order:

```sh
# the counted occurrence, which returns the M-id
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py append . \
  --key '<class>/<predicate-slug>' --context '…' --artifact '…' --fix '…'
```

then write the caveat entry and cite that id in `Related mistake:`. The key stays in one file; the
recurrence condition, the impact and the safeguard live here. When the key reaches its threshold,
`mistake-to-gate` §11 owns the promotion — this skill does not.

**A caveat with no occurrence is normal.** A hazard met while reading, or met and avoided, has
nothing to count and no `Related mistake:` line. That is the case that makes this a separate ledger
rather than a column.

## Failure modes

| Thought | Reality |
|---|---|
| "Write it down now, convert it later" | Later is a ledger of war stories. The gate refuses the entry, and it is right to |
| "The recurrence condition is obvious" | Then it is one sentence. An unwritten condition is one nobody can test for |
| "This is a mistake, so it goes in `MISTAKES.md`" | It may be both. The key goes there; the condition and the safeguard come here |
| "Give the caveat a key so it can be counted" | That is the split the gate refuses. Append the occurrence to `MISTAKES.md` instead |
| "Guidance is fine, this one is judgment" | Sometimes true. Try to state the predicate first — most hazards that feel like judgment are a state nobody tried to name |
| "Finish the step first, it is nearly done" | The details are sharpest now. A hazard recorded after the step is recorded as a story about the step |

## Checklist

- [ ] The work that surfaced the hazard is paused, not finished
- [ ] The hazard is named with its command, path or output — not as a category
- [ ] `Recurs when:` states a condition a reader can test for, not a retelling
- [ ] The safeguard's kind was chosen from the table, mechanical kinds tried first
- [ ] The safeguard is landed, and the entry cites it by path
- [ ] The entry carries every field `CAVEAT.md` documents, and no failure-mode key
- [ ] `bash .claude/scripts/mistakes-check.sh` is green
- [ ] Where the event was also an occurrence, `MISTAKES.md` holds the keyed row and the entry cites
      its id
- [ ] The paused work is finished, and the commit says the pause happened
