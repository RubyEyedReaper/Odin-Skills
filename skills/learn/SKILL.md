---
name: learn
description: Use when durable knowledge is being built, validated or retired — whether a finding is worth a record at all, how confident that record is, which command re-verifies it, and when it has stopped being true.
---

# Learn — what is worth remembering, how sure we are, and when it stops being true

A record earns its place by clearing a **capture bar**, states its confidence as a **rung on a
ladder** rather than a feeling, and carries the **command that would re-check it** — so a later
session can re-run the evidence instead of taking the record's word for it.

This skill adds **no store.** The memory tiers already exist and are described in
[`.claude/docs/odin-memory-standards.md`](../../docs/odin-memory-standards.md). What it adds to a
record in one of them is two fields and a discipline for moving them.

## What this is not for

| The task | Its owner | Why not this skill |
|---|---|---|
| Where a record physically lives, and which class it belongs to | `odin-memory-standards.md` + `odin-memory-guard.sh` | The tiers, the operational/task split and the write guard are settled. This skill is a reader of them. |
| Recording a decision and the reasoning behind it | `architecture-decision-records` | An ADR is a decision record. This is about knowledge that was discovered, not chosen. |
| Domain vocabulary and its definitions | `domain-modeling` | `CONTEXT.md` is the glossary. A term is not a finding. |
| A mistake that needs a mechanical guard | `oops`, then `mistake-to-gate` | Those turn an incident into a check. This one decides whether the *knowledge* is worth keeping. |
| A principle recurring across skills, headed for a rule file | `rules-distill` | A rule is always-on text. A record is recalled on demand. |
| Context bloat, cache buildup, memory surfacing from the wrong project | `leek` | Those are hygiene failures in the environment, not questions about a record's truth. |
| What to work on next | `roadmap` | Knowledge is not a backlog. |

**Bridges to:** `rules-distill` — the disclaimer above is half the story. The other half is
[The enforced handoff](#the-enforced-handoff): a record that reaches `enforced` is not itself a
rule, but it is exactly the shape of evidence `rules-distill`'s third source reads.

## The two fields

Added to a record in a tier that already exists:

```yaml
confidence: gated
verified_by: bash .claude/tests/safety-guard.test.sh
verified_on: 2026-08-27
```

**`verified_by` names a command, not a person and not a date.** A date says somebody looked. A
command says what would have to be re-run to look again — the difference between a record that can
be re-checked and one that can only be trusted.

The always-loaded memory index has a **300-character-per-line ceiling** (`memory-index-check.sh`,
DEC-0053) because it is read whole into every session in its scope. So the index line carries the
short half only — `· gated 2026-08-27` — and the command lives on the record it links to, which is
unbounded on purpose. The engine renders that marker; it is never hand-assembled.

## The six outcomes

Exactly one per pass over a candidate or a record.

| Outcome | Means |
|---|---|
| `record` | The candidate cleared the bar; write it into the tier it belongs to |
| `merge` | An existing record already covers it; fold the new evidence into that one |
| `promote` | New evidence lifts an existing record a rung |
| `refresh` | The verifying command still passes; the rung holds, the date moves |
| `demote` | The evidence for the current rung no longer holds; the record falls one rung |
| `retire` | The premise is gone; remove the record and say why |

`retire` deletes knowledge on purpose. A record kept past its truth is worse than no record — it is
read with the same confidence as one that is still correct, and nothing about it says otherwise.

## The five confidence tiers

`asserted` → `observed` → `reproduced` → `gated` → `enforced`. Every rung states the evidence that
**promotes** a record into it and the trigger that **demotes** it out; a ladder whose every rung is
a feeling is a vocabulary, not a mechanism. Rung by rung, with the promotion evidence each one
demands and the mistake each rung invites:
[confidence-tiers.md](references/confidence-tiers.md).

The three rungs from `reproduced` up **require** `verified_by`. A record claiming one without a
command is malformed, not merely unverified.

## The enforced handoff

`enforced` is the top rung, and the top rung is not this skill's terminal state — it is
`rules-distill`'s **third** evidence source (harness:RM-0617). That skill already carries two,
deliberately unmerged: a principle in 2+ skills, or a `MISTAKES.md` key at the promotion threshold.
An `enforced` record is neither — it is a fact already proven to hold by a gate that fails when the
fact stops being true — so without this handoff it had no route into a rule at all.

The handoff needs no new tooling: `verify` already reports a record's rung.

```sh
cd .claude/skills/learn && python3 -m scripts.capture_bar verify --record <path-to-enforced-record>
```

`rules-distill`'s Phase 1 runs this per candidate found at `· enforced` in the memory index, exactly
as it already runs `mistakes.py report` for its occurrence predicate. A record still reporting
`enforced` is evidence source C; one that has demoted is not — the same "the command decides, not
the calendar" rule this skill applies everywhere else.

## The capture bar

Five refusal classes, evaluated highest-harm first, **each with its own exit code** so a caller can
tell them apart — five refusals sharing one non-zero code report "no" and nothing else, and the
remedy for a secret is not the remedy for a duplicate.

| # | Class | Exit | Refused because |
|---|---|---|---|
| 1 | credential | 3 | Secret material — matched by key name, or by value shape |
| 2 | personal | 4 | Personal data — an address, an identifier, a phone number |
| 3 | chatter | 5 | True only inside the conversation that produced it |
| 4 | duplicate | 6 | An existing record already covers it → `merge` |
| 5 | derivable | 7 | A restatement of a line the repository already carries |

**A refusal never prints the matched credential.** Not in the message, not in a verbose mode, not in
a fixture's expected output. The caller is told the *key name* or the *pattern name* — what they
need in order to remove it — and nothing more. A refusal that echoes the secret has published it to
every log the caller writes, which is worse than the record it prevented. Masking is not a
substitute: a masked secret is still a secret in every one of those logs.

What each class is keyed on, what it deliberately does not catch, and the false-positive it was
tuned against: [capture-bar.md](references/capture-bar.md).

## The staleness pass

`verify` re-reads a record and decides its rung from the command, not from the calendar. **Age
flags; the command decides.** A record past its max age is marked stale — which means "re-check
this", never "this is wrong".

**Reading a record never executes the command inside it.** Execution is opt-in via `--run`; the
default reports what would run and changes nothing. How a demotion is chosen, why an unresolvable
command falls to `observed` rather than to nothing, and when a pass ends in `retire`:
[staleness-pass.md](references/staleness-pass.md).

## Quick reference

```sh
cd .claude/skills/learn
python3 -m scripts.capture_bar check  --candidate cand.json --root ../../.. --corpus <dir>
python3 -m scripts.capture_bar verify --record rec.json                 # reports; runs nothing
python3 -m scripts.capture_bar verify --record rec.json --run --cwd ../../..
python3 -m scripts.capture_bar tiers
```

| Exit | Means |
|---|---|
| 0 | accepted, or a pass that held the tier |
| 1 | malformed record |
| 2 | usage error |
| 3–7 | refused: credential · personal · chatter · duplicate · derivable |
| 8 | the pass demoted the record one rung |
| 9 | the pass retired the record |

`--corpus` and `--root` are optional, and a class without its input is reported `"skipped"` on
stdout **and** announced on stderr. A check that quietly passes when its subject is missing is
indistinguishable from one that agrees with every input.

## Common mistakes

| Mistake | What happens |
|---|---|
| A `verified_on` with no `verified_by` | The record can be aged but never re-checked. Nothing can ever demote it, so it stays at its rung forever. |
| Claiming `gated` because a check exists | `gated` requires that the check **fails** when the fact stops being true — proved by breaking the fact and watching it red. An unmutated gate is an `observed`. |
| Masking a secret instead of withholding it | Still a secret, now in every log. Report the key name. |
| Refusing every finding as "derivable" | The class is keyed on restatement of one line, not on inference. A fact assembled from three files is a finding. |
| Reading a record with `--run` by habit | Reading a record then executes text stored in it. Default to the reporting pass. |
| Treating a stale flag as a demotion | Age says re-check. Only the command decides the rung. |
| Keeping a record whose premise is gone | It is read with the confidence of a true one. `retire` it and record the reason. |

## Verifying a change to this skill

```sh
cd .claude/skills/learn && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5
```

Confirm the collected count is **non-zero**. `tests/__init__.py` is what makes it so; without that
file discovery collects nothing and the suite passes having examined nothing.
