# Handoff template — fleet assignment

Copy this whole file, fill every slot, delete nothing. A slot with no content is a decision the
worker makes for you.

Path: `.claude/.runtime/handoff/<ISO8601>-<worker>.md` (colons → `-` in the time portion). The
directory is gitignored, so **pass the absolute path** to `odin-relay.sh`.

The frontmatter's six fields are the `handoff` skill's; `project_id`, the `## Suggested skills`
section, and roadmap-id qualification are **refused** by `odin-relay.sh` when missing or malformed —
see ADR-0038, ADR-0050 (per-roadmap id counters), ADR-0056 (launch-directory harness check). Those
rules are stated once, there. This template adds only what is new: the six assignment elements and
the standing invariants.

---

```markdown
---
created_at: <ISO 8601 UTC>
project_id: <repo name, or projects/<slug>>
mem_class: <read .claude/.runtime/active-mem-class — do not guess>
active_branch: <the branch THIS worker owns>
plan_file: <path the worker will write its plan to, or null>
next_action: <one imperative line — the worker's first move>
---

# Successor brief — Workstream <id>: <one-line title>

<Campaign name and umbrella item, qualified: umbrella harness:RM-0054.>
Your item: <slug>:RM-####  (deps <slug>:RM-#### landed).
Coordinator monitors via `claude agents`; it integrates your branch — you never merge.

## Task and desired outcome
<What to build. Then what "done" looks like as an artifact on disk: files, their responsibilities,
the ledger entries, the docs. Enumerate content requirements as a numbered list — a worker drives
enumerated items to completion and infers prose.>

## Current context
<What already landed and where — commits, branches, PRs, by sha. Decisions already made and the
reason for each, so the worker does not reopen them. Constraints that are not negotiable.>

## Open questions, risks, dependencies
<What is unresolved and who resolves it. What blocks what. What a sibling worker is touching that
this one must not. Which external things can fail — a container, a credential, a rate limit.>

## Reserved ids
<Every ADR / DEC / RM number this worker may use, allocated by the coordinator. "Mint nothing else."
Parallel workers reading the same ledger allocate the same next number and both are right.>

## Authorization scope
Edit only: <explicit paths>. Everything else belongs to a sibling worker or the coordinator.
<Named prohibitions: never merge, never force-push, never open a PR, never close an issue,
never edit generated files.>

## Procedure
1. First action: `bash .claude/scripts/odin-autonomous.sh on`
2. <plan> 3. <build; atomic commits + Co-Authored-By trailer>
4. Gates: <exact commands>.  5. `git push -u origin <branch>`.
6. Final output: deliverable table + evidence + "READY FOR INTEGRATION". No merge, no PR.

## Standing invariants
- You run in your own independent session. You are not a subagent; you outlive the turn.
- You are monitored by the delegating session until you land or are stopped.
- You are autonomous: never AskUserQuestion, on any fork, scope included (ADR-0052). Decide,
  record the DEC/ADR, continue.
- Terse Odin voice (ADR-0011) — never lapses mid-skill; deliverable content stays normal.
- Task list is mandatory before the first edit (ADR-0031).
- Trust the repository over this brief; say where they disagree.

## Suggested skills
- <skill> (why) · <skill> (why)
- verification-before-completion (before claiming done)
```

---

## Checklist before launching

- [ ] All six frontmatter fields present, `null` only where the value genuinely does not exist
- [ ] Every roadmap id qualified (`harness:RM-0065`, never `RM-0065`) — the relay refuses otherwise
- [ ] `## Suggested skills` names real skills, resolvable from the launch directory
- [ ] Element 5 present: an explicit `Edit only:` line
- [ ] Standing invariants block present verbatim — a worker assumes none of them
- [ ] Reserved ids listed, or the section says "none needed"
- [ ] No pasted diffs or tool output; paths, shas and PR numbers instead
- [ ] `odin-relay.sh --dry-run` run against the finished file
