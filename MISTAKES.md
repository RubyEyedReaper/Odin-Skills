# Mistakes — Odin-Skills evidence log

Rows are appended by [`oops`](../../.claude/skills/oops/SKILL.md), one per occurrence, at the
moment the incident is worked. Recurrence is counted by `key`, never stored:

```sh
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report projects/Odin-Skills
```

**The ladder** (ADR-0057): 1 = logged · 2–3 = attention, with a look-back over the prior rows ·
**≥4 = a missing rule** — [`mistake-to-gate`](../../.claude/skills/mistake-to-gate/SKILL.md) lands a
mechanical check in **this project's** gate list and rule text in **this project's** `CLAUDE.md`,
never the harness's, then marks every row for the key `promoted`.

`key` is `<class>/<predicate-slug>`; the class comes from the closed set in `oops` §3
(`input` · `precondition` · `postcondition` · `error-path` · `ci-gate` · `judgment`) and the slug
names the condition, not the symptom. Ids are this project's own sequence. Never hand-edit a
`promoted` row.

| id | date | key | class | context | artifact | fix | status |
|---|---|---|---|---|---|---|---|
