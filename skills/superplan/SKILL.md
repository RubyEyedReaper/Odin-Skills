---
name: superplan
description: "Multi-agent deep planning workflow: fan out to planner + architect + adversarial reviewer in parallel, synthesize into an approved plan doc. Use before any non-trivial implementation. (Formerly named ultraplan.)"
---

> Ship signal, not noise. Parallel perspectives, one coherent plan, an approval gate that matches
> the posture — human when a human is driving, self-served and recorded when none is.

# Superplan Skill

## When to use

- Any implementation task where the scope, architecture, or approach is non-obvious
- Before writing code for a feature that touches multiple files or systems
- When a written plan doc is required for human approval

## Phase 1 — Fan-out (parallel agents)

Announce, as a fragment: `superplan — fan-out: planner, architect, adversary`. Odin voice does not
lapse inside a skill (ADR-0011); a quotable first-person sentence in skill text is the shape that
causes the lapse.

Dispatch all three agents **simultaneously** using the Agent tool.

**Fill `<CONTEXT>` with ≤10 paths, one line each, path + role — never file contents.** Each agent
starts its own session, so `<CONTEXT>` is paid three times, on top of the ~52 KB of `CLAUDE.md` and
always-on rules each session loads before it reads a word of the task. Every agent has its own Read
and Grep; what it needs from you is where to start looking, not the material itself.

```
src/auth/session.ts — where tokens are minted today
.claude/docs/adr/0031-*.md — the decision this must not reverse
```

### Agent 1 — Planner
```
subagent_type: planner
prompt: |
  Create a detailed implementation plan for the following task.
  Output: ordered task list with file-level changes, test strategy, commit checkpoints.
  Assume zero codebase context — read what you need with your own tools, and
  enumerate every file to touch.

  Task: <TASK>

  Codebase root: <REPO_ROOT>
  Relevant files already identified: <CONTEXT>
```

### Agent 2 — Architect
```
subagent_type: architect
prompt: |
  Review the following task for architectural and structural concerns.
  Output: system design implications, coupling risks, interface contracts,
  alternative approaches worth considering, and any design decisions that
  should be locked in before implementation starts.

  Task: <TASK>

  Codebase root: <REPO_ROOT>
  Relevant files already identified: <CONTEXT>
```

### Agent 3 — Adversary
```
subagent_type: plan-adversary
prompt: |
  Challenge the approach below and expose what could go wrong.
  Rank by cost of being wrong. Numbered critique list only — no plan.

  Task: <TASK>

  Codebase root: <REPO_ROOT>
  Relevant files already identified: <CONTEXT>
```

The prompt is short because the critique discipline lives in
[`.claude/agents/plan-adversary.md`](../../agents/plan-adversary.md) — the six attack directions,
the disposability rule, the output format, and what the role is *not*. This role used to dispatch
`code-reviewer` (13,618 B of post-implementation review checklists) and then spend the prompt
telling it not to review, which meant the largest definition in the fan-out was being overridden by
its own prompt and the behaviour could not be told apart from a review run (DEC-0004).

## Phase 2 — Synthesis

After all three agents return:

1. Merge the planner's task list with the architect's design constraints
2. Resolve any conflicts between planner and architect (architect wins on structural matters)
3. Apply the adversarial critique: remove scope creep, add missing edge cases, note risks inline
4. Produce a single coherent plan document

**Each agent's output feeds named sections — route it, do not paste it:**

| Agent output | Plan section it becomes |
|---|---|
| planner — ordered tasks, file-level changes, test strategy | *File map*, *Task list* |
| architect — alternative approaches, decisions to lock in | **Decision forks** (its alternatives are the raw fork material), *Architectural notes* |
| adversary — hidden assumptions, simpler alternatives, scope creep | *Risks & open questions*; any item offering a real alternative becomes a **Decision fork**; scope-creep items become the "deliberately out" half of the **scope decision** |

An architect alternative or an adversary simpler-alternative left sitting in prose is a fork that
was found and then discarded. Shape it into a fork with a recommendation, or say why it is not one.

## Phase 3 — Write plan doc

Save to `.claude/docs/plans/YYYY-MM-DD-<slug>.md` — the directory `odin-plan-gate.sh` searches. A
plan the gate cannot see does not unblock the work it was written for; a bare `docs/plans/` creates
an untracked directory at the repo root and a plan nothing reads. A project subtree's plans go in
that project's own `docs/plans/`, which the gate also searches. The date prefix is what makes a
directory of plans prunable — CLAUDE.md item 8 requires spent plans to be deleted.

The plan must satisfy all four criteria in
[`.claude/docs/plan-depth-standard.md`](../../docs/plan-depth-standard.md). The three **REQUIRED**
sections below are those criteria made structural: the `planner` agent scores the result against
the same rubric and **sends back anything below 4/5** before execution. Superplan is the harness's
mandatory pre-source planning step (CLAUDE.md item 5, roadmap Gate 4) — a plan it produces that
fails the standard fails at the one place the standard is supposed to bind.

Use this structure. Every section is required; a section with nothing to say says so and why.

```markdown
# Superplan: <Task Title>
Date: YYYY-MM-DD
Status: PENDING APPROVAL
Spec: <path to the brief, audit, issue or roadmap item this plan implements>
Roadmap item: <qualified id, e.g. harness:RM-0060 | none>

**Goal:** <one sentence: what this builds and how you will know it works>

## Task

<one-paragraph description of what is being built and why>

## Process skills fired

<the skill that produced the intent (brainstorming / grilling / grill-with-docs / roadmap) and the
one that produced this plan (superplan, and writing-plans or blueprint if either ran). Name them —
"no skill" is not an option for non-trivial work.>

## Recorded scope decision

- **In scope:** <what this work covers>
- **Deliberately out:** <what it leaves out, one reason each>
- **The reading chosen:** <where the objective admits more than one reading — the reading taken, the
  evidence for it (the item's notes, an ADR, the code), and that it is reversible>

Recorded, never asked. `AskUserQuestion` does not satisfy this section (ADR-0052).

## Decision forks

<≥3 (target 3–5). A fork is a place where a competent engineer could reasonably choose differently
— not a restatement of the task. Each one:>

### Fork N — <the choice, as a question>

| Option | Trade-off |
|---|---|
| **(a) <recommended>** | <what it buys, what it costs> |
| (b) <real alternative, not a strawman> | <what it buys, what it costs> |

**Recommendation: (x)** — <the deciding reason>. <If the fork is scorable, run `decision-matrix`
(`/decide`) and cite the DEC instead of arguing it here.>

## Architectural notes

<key design decisions from the architect agent — interfaces, coupling, approach chosen>

## Risks & open questions

<numbered list from the adversary, with dispositions: accepted / mitigated / deferred. "Open
question" means an unknown to be resolved by the work, never a question waiting on a human.>

## File map

| File | Change | Notes |
|------|--------|-------|
| path/to/file.ts | create / modify / delete | what changes and why |

## Task list

### Task 1 — <title>

**Files:**
- Create / Modify / Delete: `exact/path/to/file.ext`

**Depends on:** none | Task N <— a lower number only; a plan cannot depend on its own future>

Run: `<the command that proves this task landed>`
Expected: <the output or state that means it passed>

**Exit criteria:** <what is observably true when this task is done>
Commit: `type: description`

### Task 2 — <title>

<same five blocks; repeat per task — never "similar to Task 1", a cold executor may read them out
of order>

## Done criteria

| # | Condition | Check |
|---|---|---|
| 1 | <what must be true> | <the exact command or test that proves it, and its expected result> |

Every row names a command, test or audit that can be run. "Measurable conditions" with nothing to
run is the criterion this table replaced.
```

**Self-check before Phase 3.5** — the rubric the `planner` agent applies:

- [ ] Process skills named.
- [ ] ≥3 genuine forks, each with alternatives + a recommendation.
- [ ] Scope decision recorded — in, out, the reading chosen and its evidence. Not asked.
- [ ] Every task names exact file paths and why.
- [ ] Each task is deliverable and verifiable on its own.
- [ ] Done criteria name a concrete check per row.

**Write the plan link back to the roadmap.** If this plan serves a roadmap item:

```sh
cd .claude/skills/roadmap
python3 -m scripts.roadmap set <id> --plan <path-to-plan> --status in-progress
```

Roadmap Gate 4 refuses to start work with no plan, and its one exception is a `links.plan` naming a
plan doc touched in the last 8 hours. Without this call that exception is unreachable, and a resumed
session re-plans work this plan already covers. Never hand-edit `roadmap.json`.

## Phase 3.5 — `plancheck` (mechanical gate)

The rubric above is judgment; this is the half a script can check — every task names its files,
carries a command that verifies it, states when it is finished, contains no placeholder, and depends
only on tasks that run before it.

```sh
cd .claude/skills/blueprint
python3 -m scripts.plancheck <path-to-plan>       # exit 0 = clean; 1 = findings; 2 = unreadable
```

Fix and re-run until it exits 0 — this gate is not advisory, and it is the same one
`roadmap/SKILL.md` (*Executing a wave*, step 3) already tells wave executors to run. It is also what
makes the plan safe to hand to `subagent-driven-development`: a dispatched executor sees only its own
task, so a forward dependency the gate would have caught becomes an agent blocking on work that does
not exist yet.

The task shape above is what `plancheck` parses — `### Task N`, `**Files:**`, `Run:`/`Expected:`,
`**Exit criteria:**`, and a `**Goal:**` line in the header. A checkbox-bullet task list parses as
no tasks at all, which the gate reports as `no-tasks`.

## Phase 4 — Approval, conditional on posture

Read the posture first — do not assume one:

```sh
bash .claude/scripts/odin-autonomous.sh is-active "$CLAUDE_CODE_SESSION_ID"   # exit 0 = unattended
```

That script owns the predicate (ADR-0051); `odin-plan-gate.sh` and `odin-task-gate.sh` source the
same function rather than each testing for the marker themselves. Do not hand-roll a check for
`.claude/.runtime/autonomous/` — the claim ticket has a stamping step and a TTL, and a private copy
of the test goes wrong the first time either changes.

**Pass the session id.** A claim belongs to a session, not to the checkout — that is the whole point
of ADR-0051, and it is why the bare `is-active` (no id) reports interactive for everyone: a caller
that cannot name itself cannot hold a claim. `CLAUDE_CODE_SESSION_ID` is the same id the hooks are
handed. If it is unset, the check reports interactive and the human gate stands — the safe direction
to fail.

**Unattended (exit 0) — self-serve, no stop:**

1. Stamp the doc: `Status: APPROVED (self-served per ADR-0052)`, with the deciding reason in one line
2. Print the plan path and the ≤5-bullet summary
3. Proceed directly to `executing-plans` or `subagent-driven-development`

**Interactive (non-zero) — human gate, unchanged:**

1. Print the plan path and a short summary (≤5 bullet points)
2. Ask: "Approve this plan and begin implementation, or request changes?"
3. Do not touch any implementation files until approval is granted
4. On approval: invoke `executing-plans` or `subagent-driven-development` to execute

**Why this is conditional and not a rule with an exemption.** A run that stops has ended: the work
behind the question does not resume until a human returns (ADR-0052,
[`common/decision-authority.md`](../../rules/common/decision-authority.md)). Every unattended path
in the harness — `/autoloop`, `/loop`, a dispatched successor, a background job — routes through
this skill by contract, so an unconditional stop here instructs those sessions to end their turn at
exactly the point the work becomes executable. Settled; do not re-litigate.

## Constraints

- Under an armed autonomous claim, approval is self-served and recorded — never asked. With no
  claim, never start implementation before explicit human approval.
- Adversarial critique must be addressed (accepted, mitigated, or deferred with reason) — never silently dropped
- Plan doc is the contract: implementation must not deviate without updating the doc first
