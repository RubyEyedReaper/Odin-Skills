# Ledger conformance — the source protocol's fields, mapped to `work-loop`'s

The source protocol this skill was built against asks for a `gauntlet/state.json` and an
append-only `gauntlet/ledger.jsonl`, each with the fields named in the left column below. `gauntlet`
writes no state (SKILL.md, "Nothing here writes state") — the ledger it names as owner is
`work-loop`'s. This table is the field-by-field citation
`.claude/scripts/gauntlet-ledger-citation-check.sh` verifies against `work-loop`'s live schema, so a
rename on either side is caught rather than silently rotting the mapping. Full reasoning and the
decision that produced it: `DEC-0118`.

The source request itself was a plan doc, and plan docs are deleted once their work lands
(CLAUDE.md item 8) — so the fields are reproduced here rather than cited, which is what keeps this
table readable after that deletion.

**How the check reads this table.** Every row below whose *work-loop equivalent* column names a
backtick-quoted identifier is checked against `CONTRACT_FIELDS` and the `record = {...}` keys read
directly out of `.claude/skills/work-loop/scripts/loop.py`. A row whose equivalent is `—` is a
decline, and carries its reason in prose — the checker does not touch declined rows.

| Source field | work-loop equivalent | Note |
|---|---|---|
| `run_id` | `session` | ledger top level |
| `iteration_number` | `n` | per record |
| `current_goal` | `purpose` | contract field |
| `quality_rubric` | `quality_rubric` | contract field, same name |
| `acceptance_tests` | `success_criteria` | contract field |
| `hard_constraints` | `failure_criteria` | contract field, plus per-dimension `hard_gate` |
| `budget_limits` | — | declined — owned by `endless` / `session-burn.sh` / `revive` |
| `current_baseline_metrics` | `baseline` | per record; "current" is the latest record |
| `best_known_metrics` | — | declined — derivable by scanning `evaluation.weighted_total`, not stored twice |
| `current_score` | `evaluation` | per record; weighted total inside it |
| `best_score` | — | declined — same reasoning as `best_known_metrics` |
| `active_hypothesis` | — | declined — superseded by the `state_hash`/`error_signature` stall predicates; `note` for prose |
| `selected_task` | `actions` | per record, action ids rather than prose |
| `change_summary` | `files_changed` | per record |
| `change_summary` | `commands_run` | per record — split across two fields |
| `verification_results` | `measurements` | per record |
| `verification_results` | `evidence_paths` | per record — split across two fields |
| `critic_verdict` | `critic_verdict` | same name |
| `regressions_detected` | `evaluation` | `hard_gate_failures` nested inside it |
| `unresolved_risks` | — | declined — owned by `roadmap capture` |
| `failed_approaches` | `stall` | per record, mechanical; `note` for prose |
| `lessons_learned` | — | declined — owned by `learn` / `oops` / `MISTAKES.md` |
| `next_candidate_tasks` | — | declined — owned by `roadmap next` / `gauntlet frontier` |
| `timestamp` | `opened_at` | ledger top level, written once at `open` |
| `timestamp` | `timestamp` | per record — the `ledger.jsonl` per-entry counterpart |

## Declined groups, by reason

- **Owned elsewhere** (`budget_limits`, `unresolved_risks`, `lessons_learned`,
  `next_candidate_tasks`): each has an existing owner in this repository's own harness. Recording a
  second copy inside `work-loop`'s ledger is the exact drift risk this comparison exists to prevent,
  one layer down from the cite-vs-second-store fork itself.
- **Derivable, not duplicated** (`best_known_metrics`, `best_score`): `work-loop`'s ledger is
  append-only, so "best so far" is a read-time query over `iterations[].evaluation.weighted_total`,
  never a second mutable field a writer must keep in sync with history that already holds the truth.
- **Superseded by a mechanical equivalent** (`active_hypothesis`, `failed_approaches`'s narrative
  half): the source's own purpose for these fields is anti-stagnation detection. `work-loop`'s
  `circular-state` and `repeated-error-signature` stall predicates do this without depending on a
  human having written a hypothesis down, which is strictly stronger than a narrative field that can
  be left blank.
- **"Queued for human review"** (one of three source decision values, alongside "retained" /
  "reverted"): declined — superseded by `escalate`, per ADR-0052/ADR-0103. An unattended session
  never synchronously queues for a human; `escalate` writes a structured, gate-checked blocker record
  and ends the loop instead.
