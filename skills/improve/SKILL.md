---
name: improve
description: Use when a friction keeps recurring in a skill and no script can decide it — a body that routes badly, a reference nobody reads, a step everybody skips — or when a skill change must declare its reason, its falsifier, and what happens if it reddens a gate.
artifact_status: never-run
artifact_status_reason: >-
  the record is five fields in the commit body, which no glob can match, and the mechanism has
  never run: 0 of the 30 commits touching .claude/skills since improve landed at b5aaf902
  (2026-08-26) carry them, measured 2026-09-01. Retro-fitting them would mean rewriting published
  history, and a record written now from memory is a function of who remembered. The obligation
  binds forward from here. ADR-0109 names this exact silence and accepts it on purpose ("Silence is
  not a signal... measured by leek, not here") — this exemption is that acceptance, not an oversight
  an audit should re-flag.
---

# Improve — the rung the ladder does not have

This harness turns failures into enforcement in three rungs, and they are all owned. This skill takes
the fourth: a **friction that recurs and that no script can decide**.

An improvement here is a change **declared before it is made and reversible after**.

This skill's own frontmatter has carried `artifact_status: never-run` since it landed, and an audit
pass (harness:RM-0615, issue #1247) read that as an unenforced procedure. It is not one: ADR-0109's
own Consequences section names this exact state and accepts it — *"silence is not a signal... if
this skill turns out to be unused, that shows up in `leek`'s never-used-skill sweep, not here."*
Read ADR-0109 before treating a long-running `never-run` exemption here as a defect.

## What this is not for

| The task | Its owner | Why not this skill |
|---|---|---|
| Something happened that should not have | `oops` | That is the front door. It root-causes the incident and appends a row to the owner's `MISTAKES.md`. This skill reads that register; it never writes it |
| A condition a script can decide about the repository | `mistake-to-gate` | A predicate gets a gate and a matrix, not prose. Hand it over — see the handover test below |
| A pattern now in two or more skills, or a key at the promotion threshold | `rules-distill` | That is a rule, at a declared tier, with a row in `DISTILLATIONS.md` |
| Authoring or restructuring a skill | `skill-creator`, `writing-skills` | Ordinary authoring. This skill fires on **recurring friction**, not on every edit |
| Whether machine-generated code is overdeveloped | `not-impressed` | A verdict on a diff, delivered by a fresh context. Different question entirely |
| What to work on next | `roadmap` | This skill never picks work |
| A bug, a failure, something slow | `systematic-debugging`, `diagnosing-bugs` | A friction is not a defect. Diagnose first; you cannot improve a mechanism you have not identified |

## The handover test

Before anything else, ask `mistake-to-gate` §2's own question, in its own words:

> **Is there a predicate over repository state that is true exactly when the friction is present?**

**Yes** → it is a gate. Invoke `mistake-to-gate` and stop. One sentence, no analysis, no partial
work here first.

**No** → it is yours. A body that routes badly, a reference nobody reads, a procedure with a step
everybody skips, a boundary table that omits the skill people actually reach for.

The question is quoted rather than paraphrased on purpose. Two bodies that paraphrase a shared border
drift into disagreeing about it, and nothing in this harness detects two skills claiming one
scenario.

## The trigger — recurrence, read at run time

One annoyance is a preference. Recurrence is evidence.

```sh
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report .
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report . --key <key>
```

**Never write a count from that register into prose** — a number in a body is wrong by the next
occurrence, and this repository has shipped that exact defect more than once. Read it when you need
it.

A key found **already at the promotion threshold** is not this skill's. That is a promotion, and
`mistake-to-gate` §11 owns it — both halves, the check and the rule text, the latter through the
forked `rules-distill`.

## The five fields

Declared **before** the change: **reason, expected benefit, affected skills, validation criteria**.
Written into whatever closes it: **outcome**.

They live in the commit body — an ADR too when a contract moves, `CHANGELOG.md` too when something is
removed. There is **no improvement ledger** and there will not be one: a second store of recurring
problems diverges from `MISTAKES.md` within a week and nothing says which is right.

Two of the five carry the weight:

- **Validation criteria** must name a **falsifier** — a command or an observation that would show the
  improvement did *not* work. If you cannot state one, the change is a preference; say so and land it
  as one, or not at all.
- **Outcome** is what makes the other four cost something. An improvement whose outcome is never
  recorded is indistinguishable from one that was never made.

Each field, with what goes wrong when it is missing, and where the record lives:
[change-record.md](references/change-record.md).

## Before any skill edit — check the origin

`vendor-skills.sh --refresh` runs a delete-then-copy over every skill outside its protected set, so an
edit to a vendored, unprotected body **deletes itself silently** at the next refresh. Two commands
answer it — is it vendored, and is it protected — and the third case has only two honest resolutions:
take the body out of the refresh path (a fork, with its own record) or do not make the edit.

Both commands, the three cases, and the citation to the records that own fork policy:
[revert-protocol.md](references/revert-protocol.md).

## When it goes wrong

| What happened | Response |
|---|---|
| A gate went red | **Revert, not patch.** Mandatory. Patching forward means the next failure cannot be attributed — the improvement is entangled with its own repair |
| Every gate green, the falsifier fired | Record the outcome, then **decide**. Not an automatic revert |
| Every gate green, the falsifier did not fire | Record it. Done |

The full protocol, including the three moves that feel reasonable and are the same mistake:
[revert-protocol.md](references/revert-protocol.md).

## Red flags

| Thought | Reality |
|---|---|
| "A script could check this, but prose is faster" | Then it is `mistake-to-gate`'s. Hand it over |
| "This has only happened once, but it will recur" | Then wait for the second one. One occurrence is a preference with a forecast attached |
| "I'll note the count so the next reader has context" | The count is wrong at the next occurrence. Cite the command instead |
| "A small file tracking improvements would help" | That is `MISTAKES.md`, and this record is per *change*, not per *occurrence* |
| "The gate is red but it's clearly unrelated" | Revert. If the gate is genuinely wrong, that is a separate change, landed first, on its own |
| "The benefit is obvious, a falsifier is ceremony" | An unfalsifiable improvement is confirmed by every future state of the world, including the one where it changed nothing |

## Checklist

- [ ] Handover test asked; a gateable predicate handed to `mistake-to-gate` and stopped
- [ ] Recurrence established; register read at run time, no count written down
- [ ] Key not already at the promotion threshold — if it is, it is a promotion
- [ ] Origin checked before touching any skill body
- [ ] Four fields declared in the commit body before the change; a falsifier among them
- [ ] Outcome written into the commit, amendment or revert that closes it
- [ ] Red gate reverted, never patched forward
