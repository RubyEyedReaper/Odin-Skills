---
name: superplan
description: "Multi-agent deep planning workflow: fan out to planner + architect + adversarial reviewer in parallel, synthesize into an approved plan doc. Use before any non-trivial implementation. (Formerly named ultraplan.)"
---

> Ship signal, not noise. Parallel perspectives, one coherent plan, human gate before a line of code.

# Superplan Skill

## When to use

- Any implementation task where the scope, architecture, or approach is non-obvious
- Before writing code for a feature that touches multiple files or systems
- When a written plan doc is required for human approval

## Phase 1 — Fan-out (parallel agents)

Announce: "Running superplan — dispatching planner, architect, and adversarial reviewer in parallel."

Dispatch all three agents **simultaneously** using the Agent tool:

### Agent 1 — Planner
```
subagent_type: planner
prompt: |
  Create a detailed implementation plan for the following task.
  Output: ordered task list with file-level changes, test strategy, commit checkpoints.
  Assume zero codebase context — enumerate every file to touch.

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

### Agent 3 — Adversarial Reviewer
```
subagent_type: code-reviewer
prompt: |
  You are the adversarial reviewer in a planning process. Your job is NOT
  to create a plan — it is to challenge the proposed approach and expose
  what could go wrong.

  For the task below, identify:
  1. Hidden assumptions that may be wrong
  2. Missing edge cases and failure modes
  3. Security or correctness risks in obvious approaches
  4. Scope creep risks — what's being pulled in that wasn't asked for
  5. Simpler alternatives that accomplish the same goal
  6. Gaps in the task description that will cause rework

  Do not propose a full plan. Return a numbered critique list only.

  Task: <TASK>

  Codebase root: <REPO_ROOT>
  Relevant files already identified: <CONTEXT>
```

## Phase 2 — Synthesis

After all three agents return:

1. Merge the planner's task list with the architect's design constraints
2. Resolve any conflicts between planner and architect (architect wins on structural matters)
3. Apply the adversarial critique: remove scope creep, add missing edge cases, note risks inline
4. Produce a single coherent plan document

## Phase 3 — Write plan doc

Save to `.claude/docs/plans/<slug>.md` — the directory `odin-plan-gate.sh` searches. A plan the
gate cannot see does not unblock the work it was written for; a bare `docs/plans/` creates an
untracked directory at the repo root and a plan nothing reads. A project subtree's plans go in
that project's own `docs/plans/`, which the gate also searches.

Use this structure:

```markdown
# Superplan: <Task Title>
Date: YYYY-MM-DD
Status: PENDING APPROVAL

## Task

<one-paragraph description of what is being built and why>

## Architectural notes

<key design decisions from the architect agent — interfaces, coupling, approach chosen>

## Risks & open questions

<numbered list from adversarial reviewer, with dispositions: accepted / mitigated / deferred>

## File map

| File | Change | Notes |
|------|--------|-------|
| path/to/file.ts | create / modify / delete | what changes and why |

## Task list

- [ ] **Task 1**: <title>
  - Files: ...
  - Test: ...
  - Commit: `type: description`

- [ ] **Task 2**: ...

## Done criteria

<measurable conditions that confirm the work is complete>
```

## Phase 4 — Human approval gate

After writing the doc:

1. Print the plan path and a short summary (≤5 bullet points)
2. Ask: "Approve this plan and begin implementation, or request changes?"
3. Do not touch any implementation files until approval is granted
4. On approval: invoke `executing-plans` or `subagent-driven-development` to execute

## Constraints

- Never start implementation before explicit human approval
- Adversarial critique must be addressed (accepted, mitigated, or deferred with reason) — never silently dropped
- Plan doc is the contract: implementation must not deviate without updating the doc first
