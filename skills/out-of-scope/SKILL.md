---
name: out-of-scope
description: Use when work found mid-run is genuinely outside the current scope and the question is whether to fix it now anyway — a defect noticed in passing, a landmine the next session would trip over, "that's out of scope but", "should we fix this now or file it", "not my scope, but it'll bite someone", "is this worth fixing now", "file it or fix it". Also when a deferral needs to be auditable rather than remembered.
metadata:
  origin: Odin
---

# Out-of-scope — fix it now, or hand the next session a landmine

## The stance

Two contract items point in opposite directions across one case, and neither is wrong.

- **CLAUDE.md item 8** — on audit, review or structural work, file one issue per distinct concern
  rather than fixing out-of-scope items in the same pass.
- **CLAUDE.md item 3** — never close a turn reporting in-scope work as deferred-by-choice.

Item 3 governs work *inside* the scope. Item 8 governs work *outside* it. Between them sits work
that is genuinely out of scope **and** whose deferral costs the next session more than fixing it
costs this one — and that case had no rule, so it was settled by whoever held the keyboard.

This skill makes it decidable. The call is scored by the `decision-matrix` engine against six
weighted dimensions, the winner is taken, and a **deferral** is written into a committed store
carrying the spec that produced it. That last part is half the value: a deferral today is invisible
tomorrow unless the reasoning travels with it. The tracker is where this repository has watched
findings go to be re-discovered late — one burn-down found 31 of 43 examined issues already fixed on
`main`, each re-established from context by somebody who did not have it.

Rigid skill. The trigger predicate, the six criteria, the tie-break and the refusals are not
judgment calls. The scores are. The whole resolution is recorded in ADR-0168, with the two forks
it turns on in DEC-0112 (where the record lives) and DEC-0113 (the six dimensions).

## What this owns, and what it must not restate

A second copy of a rule drifts, and the looser copy wins silently. Every row names an owner, and
nothing in that column is re-derived here.

| The task | Its owner | Never re-derived here |
|---|---|---|
| Scoring options against weighted criteria, sensitivity, vetoes, the DEC record | [`decision-matrix`](../decision-matrix/SKILL.md) | All the math. This skill supplies a spec and reads the winner; it never computes a score by hand |
| Turning a finding into a tracker row | [`to-issues`](../to-issues/SKILL.md), [`triage`](../triage/SKILL.md) | Issue shape, labels, the triage state machine |
| Capturing work as an item with acceptance criteria | [`roadmap`](../roadmap/SKILL.md) | Item identity, the id allocator, status, `next`, `waves`. A record here *references* an item and holds no second opinion about it |
| Turning an incident into a mechanical guard | [`oops`](../oops/SKILL.md), [`mistake-to-gate`](../mistake-to-gate/SKILL.md) | The failure-mode key, the four-occurrence ladder, the gate matrix |
| A hazard met once, and the safeguard that now refuses it | [`caveat`](../caveat/SKILL.md) | `CAVEAT.md`'s entry shape and its recurrence condition |
| A change whose actual effect nobody has observed | [`mutations`](../mutations/SKILL.md) | The open/closed contract of `MUTATIONS.md` |
| A **new task** arriving mid-run, and the return to what it displaced | [`off-topic`](../off-topic/SKILL.md) | The checkpoint, the displacement edge, the resume condition. See **Against `off-topic`** below |
| Whether a batch may close, and what re-arms it | [`campaign`](../campaign/SKILL.md), [`gauntlet`](../gauntlet/SKILL.md) | Landedness by content, the refusal to store a status |
| Planning the fix, once `fix-now` wins and it is big | [`superplan`](../superplan/SKILL.md), [`writing-plans`](../writing-plans/SKILL.md) | The plan-depth bar |

### Against `off-topic`

They meet, and the boundary is one word: **who brought the work**.

| | `off-topic` | `out-of-scope` |
|---|---|---|
| Subject | A new task introduced into a run in flight | A defect discovered inside a run |
| Question | How does the displaced work get resumed | Should this be fixed now, or routed and left |
| Artifact | A checkpoint, deleted on return | A deferral record, kept for the audit |
| Nesting | Stacks by `parent`, closes LIFO | Never nests — see **Recursion** |

A `fix-now` verdict can *produce* a displacement, and then `off-topic` fires — but only on its own
predicate, unchanged: when the fix needs its own branch, plan or unit of work. A defect fixed in the
same breath, inside the same unit of work, is explicitly **not** an `off-topic` trigger, and this
skill does not make it one.

## When this fires

**Recurs when:** all three hold.

1. **A finding surfaced mid-run** — a defect, a stale value, a guard that passes without asserting,
   a wrong assumption — that nobody was looking for.
2. **It is genuinely outside the declared scope** of the work in hand. Test it against the recorded
   scope decision in the plan, not against a feeling.
3. **Deferring it is not obviously free.** Somebody downstream might hit it.

| Not a trigger | Why |
|---|---|
| **Work that is in scope** | It never reaches this skill. Item 3 already settled it: finish it. This is the misuse the skill is most likely to be reached for, and the one it refuses. |
| A finding whose fix is part of the work in hand | Not out of scope. Fix it and say so in the commit. |
| Choosing what to work on next | `roadmap`. Nothing was found mid-run. |
| A new task a human introduced | `off-topic`. |
| A hazard that behaves differently from how it reads | `caveat` — that ladder converts at first occurrence and is not a deferral question. |
| A finding met **while applying this skill** | Recursion is refused. See below. |
| A feature request a maintainer decided not to build | `triage`, whose `.out-of-scope/` knowledge base holds **rejected requests** in a project. Same two words, unrelated subject: that directory records what will not be built at all, this skill records when a known defect gets fixed |

## The procedure

1. **Confirm the trigger.** All three, in words, before scoring anything.
2. **Copy the template** — [`assets/decision-spec-template.json`](assets/decision-spec-template.json) —
   and fill the goal, the two option descriptions, and the twelve scores against the anchors below.
3. **Declare the authorization constraint honestly.** If this session may not edit the files the fix
   would touch, `fix-now` carries `constraint_results.authorized-to-fix: false` and the constraint
   carries the event that lifts it. A veto without its lifting condition is not re-runnable.
4. **Run the engine. Never do the arithmetic by hand.**

   ```sh
   cd .claude/skills/decision-matrix && python3 -m scripts.score --spec <path-to-spec>
   ```

5. **Take the winner**, with one rule on top of it: a **near-tie is a `defer`**. Within the engine's
   tie threshold the evidence does not distinguish the options, and item 8 is the standing default —
   a tie is not grounds to override it.
6. **Act.**
   - `fix-now` → fix it **in this run**, and name the finding and the score in the commit body. No
     record file: the fix is in the history, and a second copy of a fact git owns is the thing that
     goes stale.
   - `defer` → route the work through its own owner (`roadmap` to capture an item, `to-issues` for a
     tracker row), then write the record.
7. **Write the deferral record** into `.claude/docs/out-of-scope/`, embedding the spec that produced
   the verdict, and **commit it in the same change as the deferral**. Field by field, and what each
   refusal catches: [references/record-schema.md](references/record-schema.md).
8. **Do not recurse.**

## The scoring anchors

The engine scores 0–100. Two agents scoring the same finding must land near the same numbers, so
each dimension has anchors. Score the **option**, not the finding.

| Criterion | Weight | 0 | 50 | 100 |
|---|---|---|---|---|
| **next-session cost** (lower better) | 25 | Nobody meets it again | Met by anyone touching the same subsystem | Met by default on every run, with the context that found it gone |
| **silence** (lower better) | 20 | Fails loudly, with the cause in the message | Visible in output nobody reads | Returns a clean verdict it cannot support — indistinguishable from a real pass |
| **contamination** (lower better) | 20 | Nothing depends on it | Later work in the same subsystem is sized or shaped by it | Every later change lands on it and inherits the fault |
| **this-session cost** (lower better) | 15 | No edit | A new matrix case and a file not yet read | Its own campaign |
| **scope integrity** (higher better) | 12 | The option redefines what this run is | Adjacent, and stated in one line of the same change | The declared scope stands exactly as written |
| **reversibility** (higher better) | 8 | One-way — data, a published artifact, rewritten history | Revertible with a follow-up and a re-review | One commit reverted, nothing depending on it |

**Silence is the dimension that most often decides it.** A defect that crashes is expensive once; a
defect that returns a clean verdict it cannot support is expensive every time somebody trusts it,
and it is invisible in exactly the runs it corrupts.

The weights are recorded in DEC-0113 and the record home in DEC-0112. Both are re-runnable: change
the weights in a copy of the template, re-score, and record what changed.

## Recursion — depth zero, and mechanically so

A defect found **while applying this skill** is not scored. Record it through its own owner —
`roadmap` or `to-issues` — and continue with the decision in hand.

Any depth limit above zero is a number nobody can justify, and each level costs an engine run to
decide something whose cost is already bounded by the deferral above it. So the store schema
**forbids** `parent` and `depth` keys at any depth, and the check refuses a record carrying one.
This is the deliberate inverse of `off-topic`, whose checkpoints stack by `parent` and close LIFO.

## What is checked, and what is not

```sh
bash .claude/scripts/out-of-scope-check.sh          # verify every deferral record
bash .claude/scripts/out-of-scope-check.sh --json   # the same, machine-readable
```

The predicate that matters, in one sentence: **a deferral is either supported by its own score, or
it names the bar that made fixing unavailable.** The check re-runs each record's embedded spec
through the engine and reads two things from the result: the weighted-sum winner, and whether
`fix-now` was vetoed by a constraint. A record whose recomputed winner is `fix-now` is a finding; a
record whose `fix-now` was vetoed must carry `blocked_by` naming that constraint and the event that
lifts it. The five cases are tabulated in [references/record-schema.md](references/record-schema.md).

| Exit | Meaning |
|---|---|
| 0 | Every record is well-formed and supported by its own score. An empty store is clean — it is the steady state |
| 1 | A finding: a malformed record, a forbidden key, a deferral the score does not support, a `resolved_by` naming no commit |
| 2 | The store or the engine could not be read. Never reported as clean |

**The residue, stated rather than implied away.** Nothing detects a deferral that was never
recorded — a defect nobody wrote down leaves no trace in the tree, and no predicate can find it.
Nothing checks that the routed work was actually done; that is `roadmap`'s and the tracker's. This
check proves that the decisions on record are internally honest, never that the record is complete.

## Worked example — a real finding, scored end to end

`pre-push` declares its budget a hard constraint, computes the elapsed time, prints both, and
compares nothing. Scored: **fix-now 81.8, defer 49.1**, not fragile under sensitivity. The full
spec, the engine output, and what the repository actually did with it:
[references/worked-example.md](references/worked-example.md).

## Who cites this, and who deliberately does not

Integration is by citation, never by restatement — one line where a skill genuinely meets this
situation, and nothing where it does not.

| Cites this | Because |
|---|---|
| `off-topic` | The nearest neighbour. A `fix-now` verdict can produce a displacement, and the boundary has to read the same from both sides |
| `endless` | An unattended loop meets findings constantly, and the continuation doctrine is not the same question as what happens to one |
| `work-loop` | An iteration turns up work outside its own contract, and a deferral is not a seventh outcome |
| `oops` | An incident outside the work in hand still needs its guard; only the timing is decided here |
| `roadmap` | Capturing a finding is its job; whether capturing is the right answer at all is this one's |
| `triage` | The issue this skill's deferral produces is the issue that skill then triages |

**No line, with the reason.** `superplan`, `writing-plans` and `blueprint` own the plan whose scope
decision is this skill's *input* — the dependency runs one way, and a line there would invite a
planner to score a fork it should be resolving. `campaign` and `gauntlet` re-arm from a frontier
computed over the roadmap and the tracker, so a deferral routed to either is picked up without
either skill knowing this one exists. `successor`, `successor-manager`, `handoff` and `revive` are
about sessions, not findings. `caveat`, `mutations`, `mistake-to-gate`, `learn`, `automate`,
`improve`, `tidy`, `projects`, `workflows` and `test-driven-development` each own a different
artifact, and each is reached through `oops` or through the tracker rather than from here — a line
in all of them would be a second copy of a routing table `SKILL-ROUTING.md` already owns.

## Red flags

| Thought | Reality |
|---|---|
| "This is in scope, but it's big — score it and defer it" | In-scope work never reaches this skill. Item 3 is not negotiable and this is not the exemption. |
| "The scope decision doesn't mention it, so it's out of scope" | Silence in a scope decision is not exclusion. Read what the work covers, not what it failed to enumerate. |
| "It's small, just fix it" | Then it is in the work, and it belongs in the commit with a line naming it. No score, no record, no ceremony. |
| "Filing an issue is the safe default" | It is the *standing* default, which is not the same thing. The tracker is where a landmine waits for somebody without the context. |
| "I'll score it after I decide" | Then the score is a justification, not a decision. Fill the spec before choosing. |
| "Both options look about equal" | That is the near-tie rule, and it resolves to `defer`. Take it and move on. |
| "I can't edit that file, so it's a defer" | It is a veto, and it needs the event that lifts it recorded. Otherwise the record says the fix was *wrong*, when it was merely unavailable. |

## Common mistakes

| Mistake | What goes wrong |
|---|---|
| Scoring the finding instead of the options | The engine ranks options. Traits of the finding produce a spec that validates and means nothing. |
| Writing a record for a `fix-now` | A second copy of what the commit already says, stale on the first amend. |
| A record with no `routed_to` | The deferral names no owner, so the work exists only in a file nobody reads. The check refuses it. |
| Copying the deferred work's state into the record | The item and the branch update themselves; a copy does not. Reference them. |
| A `status:` field | Reads identically whether it is current or six hours old (`campaign`, ADR-0113). Closure here is a sha the tree can verify. |
| Re-scoring the same finding in a later session to reverse it | Allowed, and it is the point — but record the new score alongside the old, so the reversal is visible as a reversal. |
