# Report template

Copy this shape. Five classes, **in this order**, always all five — an empty class is reported empty
rather than dropped, because a missing class reads as an oversight and an empty one is a result.

The order is not cosmetic. Critical issues come first because they block. Simplification sits in the
middle because it is this skill's own verdict and must not be buried under nitpicks. Strengths come
last because a reader who stops early should have stopped on the findings.

Severity labels are CRITICAL / HIGH / MEDIUM / LOW, defined in
[`.claude/rules/common/code-review.md`](../../../rules/common/code-review.md) § Review Severity
Levels. Do not redefine them here or in the report.

---

```markdown
## Verdict

`ship` | `trim` | `rebuild` — <one sentence, naming the deciding reason>

## 1. Critical issues

<CRITICAL and HIGH findings: correctness, data loss, security, a boundary that
accepts what it must reject. Each one:>

- **[CRITICAL] <one-line claim>** — `path/to/file.ts:88`
  - Evidence: <the line, the input, or the command output that shows it>
  - Failure: <concrete inputs or state → wrong output, crash, or exposure>
  - Fix: <the smallest change that closes it>

<If none: "None found." plus the classes checked — see the rubric's eleven bullets.>

## 2. High-priority improvements

<MEDIUM findings that are not simplifications: missing error handling, an untested
branch, a convention the surrounding code does not share, a log line that leaks.>

- **<one-line claim>** — `path/to/file.ts:120`
  - Evidence: <what shows it>
  - Why it matters: <the cost of leaving it>
  - Fix: <the change>

## 3. Simplification opportunities

<The overdevelopment findings. This is the section the skill exists for. Every entry
carries a deletion target and the behaviour-preservation sentence — an entry missing
either is not a finding and does not belong here.>

- **<pattern name from the catalogue> — <what to delete>** — `path/to/file.ts:12-64`
  - Signal: <the observable fact that put it on the table — the count, the search, the
    absent measurement>
  - Simpler: <the concrete alternative shape>
  - Preserves behaviour: <the sentence, including what would have to be true for it to
    be false and how that was checked>
  - Removes: <lines, files, dependencies>

## 4. Questions and assumptions

<Rubric rows that could not be discharged, and every assumption the review rests on.
Each is stated with the check that would settle it, so the author can settle it rather
than argue with it.>

- **<the question>** — assumed `<the reading taken>` because `<why>`. Settled by: `<the
  command, file or person that answers it>`.

## 5. Strengths

<What is genuinely right, specifically. Not encouragement — calibration: it tells the
author which parts survived the pass, so a later change does not undo them by accident.
On a `ship` verdict this section carries the part the review tried hardest to cut and
why it held.>

- **<the specific thing>** — `path/to/file.ts:40` — <why it is right>
```

---

## Rules for filling it in

- **Every finding cites `file:line`.** A finding without a location cannot be accepted, mitigated or
  deferred, which makes it an opinion.
- **Findings inside a class are ordered by cost of being wrong**, not by how clever the observation
  is. Unranked findings get dropped wholesale.
- **No preamble, no closing summary.** The verdict line is the summary. Prose framing the report is
  the same excess this skill reports on.
- **Never restate the diff.** The author has it. Cite lines; do not reproduce them beyond the
  fragment that carries the evidence.
- **The report never edits code.** Remediation is `refactor-cleaner`'s act or the author's. This
  output is a set of disposable findings, and each one is disposed of as accepted, mitigated or
  deferred by the session that asked.
