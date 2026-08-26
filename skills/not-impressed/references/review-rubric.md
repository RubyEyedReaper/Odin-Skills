# Review rubric — the eleven bullets and what discharges each

**One table, not eleven files.** Progressive disclosure pays when a reader needs one branch and not
the others; a completeness rubric is read whole on every review, so splitting it would cost eleven
reads and buy nothing. (Fork A of the workstream plan.)

**Severity is not defined here.** The four levels — CRITICAL, HIGH, MEDIUM, LOW — and the
block / warn / info / note actions they imply live in
[`.claude/rules/common/code-review.md`](../../../rules/common/code-review.md) § Review Severity
Levels. That file is the single owner. A second ladder in this file would be a contradiction, and
this repository treats a contradiction between docs as a defect until resolved.

## How to use this table

Each row is a question the review must answer, and a statement of **what evidence discharges it**.
Evidence means a citation, a command with its output, or a named line — never an impression. A row
you cannot discharge is itself a finding: report it under *questions and assumptions* with the
check that would settle it.

A review that skipped a row is not finished. A review that discharged every row with "looks fine"
has discharged nothing.

| # | Bullet | What discharges it |
|---|---|---|
| 1 | **Correctness** — does it do what it claims? | The claim restated in one sentence from the code alone, plus a named case where the code and the claim would diverge and the line that prevents it. `file:line` for both. Absent that, the divergent input, run. |
| 2 | **Invalid input and boundary handling** | For each entry point, the behaviour on empty, null, zero, negative, maximum, malformed and duplicate input — read off the code, not assumed. Each is either handled at a cited line or is an unhandled case named as a finding. A validator at the boundary discharges the whole class for that entry point; a validator one layer in does not. |
| 3 | **Structure and naming** | Every exported name read as a stranger would: does the name predict the behaviour? Cite the pair where it does not. For structure, the file's responsibilities enumerated — more than one cohesive responsibility is a finding with the proposed seam named. See `.claude/rules/common/coding-style.md` for the size and nesting floors. |
| 4 | **Duplication, dead code, hard-coded values** | Duplication: the two or more `file:line` spans, plus whether they change together or merely look alike — only the former is duplication. Dead code: the symbol and the search that found no caller, including dynamic and string-keyed callers. Hard-coded values: the literal, its meaning, and the named constant or config key it should be. |
| 5 | **Validation, error handling, logging, test coverage** | Validation: bullet 2's boundary evidence. Errors: every `catch`, `except` or ignored return located, and for each, what it does with the failure — a swallowed error is a finding by itself. Logging: whether a failure is diagnosable from the log alone, and whether any log line carries a secret or PII. Coverage: the command run and its number against the 80% floor in `.claude/rules/common/testing.md`, plus whether the new tests were ever seen red. |
| 6 | **Sensitive-data protection** | Every place a credential, token, key or personal field is read, written, logged, serialized or put in a URL, enumerated with `file:line`. Findings here cite `.claude/rules/common/security.md` and escalate to the `security-reviewer` agent — this skill reports the surface, it does not own the remediation ladder. |
| 7 | **Efficiency under realistic load** | The realistic input size **stated as a number, with where it came from** — a config value, a table's row count, a measured request rate. Then the cost at that size: allocations per item, round trips, whether a loop body does I/O. A claim of "slow" with no number is an assumption, not a finding, and belongs under questions. |
| 8 | **Scalability** | What breaks first when bullet 7's number grows 10× and 100× — memory, a connection pool, a per-item query, a lock. Name the specific limit and the line that hits it. "It should scale" is not evidence; neither is "this won't scale" without the limit named. |
| 9 | **Bottlenecks** | The single most expensive operation on the hot path, identified from the code and, where a measurement is possible, from a profile or timing run rather than intuition. Named as `file:line` with what it costs and what it is called by. If the hot path cannot be identified, say so — a guessed bottleneck sends the fix to the wrong place. |
| 10 | **Integration with existing conventions** | Three sibling files in the same directory or layer read, and this code compared against them: error style, naming, test placement, module boundaries, dependency direction. A deviation is a finding only when the siblings actually agree with each other; where they disagree, that is a finding about the codebase, reported under questions. Cite the rule namespace under `.claude/rules/` that governs the surface. |
| 11 | **Simplifiability** | The whole of [`overdevelopment-catalog.md`](overdevelopment-catalog.md), one pass per pattern. Discharged by: for each pattern, either the recognition signal is absent, or a finding exists carrying the simpler-alternative recipe **and** the behaviour-preservation sentence. This is the bullet the skill exists for; it is never discharged by "seems reasonable". |

## Two ways this table is misused

- **Discharging a row by asserting the property.** "Input is validated" is a claim. "`parse()` at
  `api/ingest.ts:41` rejects empty and non-UTF-8; nothing rejects a 400 MB body" is evidence.
- **Treating an undischarged row as a pass.** A row nobody could answer is reported, not skipped.
  The report's *questions and assumptions* class exists for exactly this, and a review that never
  uses it is either perfect or incomplete.
