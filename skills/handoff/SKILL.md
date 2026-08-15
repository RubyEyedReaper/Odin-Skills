---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work.

## Where it goes

`.claude/.runtime/handoff/<ISO8601>.md` — e.g. `.claude/.runtime/handoff/2026-07-09T13-04-22Z.md`
(colons are not path-safe on every filesystem; use `-` in the time portion).

`.claude/.runtime/` is git-ignored (`.gitignore:29`) and is the established home for harness-internal
session state — `.claude/hooks/odin-project-context.sh` already writes `active-mem-class` there. The
handoff therefore survives an OS temp sweep, stays out of every commit, and never reaches a remote.

Create the `handoff/` directory if absent. Do not write to the OS temp directory, and do not write
anywhere else in the workspace.

## Required frontmatter

Every handoff document opens with this YAML block. All six fields are required; write `null` only
where the value genuinely does not exist (e.g. no plan file yet).

```yaml
---
created_at: 2026-07-09T13:04:22Z   # ISO 8601, UTC
project_id: odin                    # repo or projects/<slug> this work belongs to
mem_class: operational              # `operational` or `task:<slug>` — must match .claude/.runtime/active-mem-class
active_branch: feat/agent-token-discipline
plan_file: .claude/docs/plans/<name>.md   # or null
next_action: Run harness-audit, then open the PR   # one line, imperative
---
```

`mem_class` uses the exact vocabulary of `.claude/docs/odin-memory-standards.md`. Read the current
value from `.claude/.runtime/active-mem-class` rather than guessing it.

## Body

Free-form prose after the frontmatter. Include a `## Suggested skills` section naming the skills the
next agent should invoke.

## What a handoff captures

**Ephemeral working state only** — where the work stopped, what was in flight, what to do next.

It is not a memory tier and must not be treated as one:

- **Durable facts** (a decision and its reasoning, a non-obvious root cause, a shipped capability)
  belong in the file tier — `CONTEXT.md`, `.claude/docs/adr/`. Write them there, then reference them.
- **Curated recall** belongs in claude-mem under the active class. The write boundary is enforced
  fail-closed by `.claude/hooks/odin-memory-guard.sh`.
- Nothing in a handoff is promoted to either tier automatically. A handoff is discardable by
  definition; if a fact matters beyond the next session, it does not belong only here.

## Rules

- Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits,
  diffs). Reference them by path or URL instead.
- Do not paste raw tool output, diffs, or file contents. Reference the path.
- Redact any sensitive information, such as API keys, passwords, or personally identifiable
  information.
- If the user passed arguments, treat them as a description of what the next session will focus on
  and tailor the doc accordingly.
