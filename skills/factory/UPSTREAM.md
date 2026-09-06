# `factory` — upstream provenance and the divergences

**Forked from** `coleam00/skills`, `.claude/skills/build-dark-factory`, at
`ecef6ffd4caa0b23a8c79601c1215b1e2908ac72` (2026-08-25).

**This is a fork, not a vendoring.** It is excluded from `.claude/scripts/vendor-skills.sh`, with
the reason inline there, so no refresh fights it. Upstream fixes are ported by hand; the table
below is what a porter has to read first.

---

## 1. The blocking interview is gone, and it is replaced rather than deleted

Upstream mandates the question tool, in capitals, with no fallback:

> **EVERY QUESTION GOES THROUGH THE QUESTION TOOL.** `AskUserQuestion` in Claude Code, or the
> equivalent elsewhere. Every one, including the open-ended ones. No exceptions, and no prose
> fallback.

Odin forbids exactly that (ADR-0052, `.claude/rules/common/decision-authority.md`). A question is
not a pause: it ends the turn, and nothing behind it resumes until a human comes back. A skill whose
first phase is a three-round interview would stop an unattended run three times before writing a
line.

**The rewrite keeps every artifact and drops only the waiting.** Each round still computes its
questions, still carries exactly one recommendation, and still derives its options from the user's
own PRD and repository. What changed is the last step: the recommended answer is **adopted and
recorded** — into the plan doc's decision-forks section, or as a numbered DEC — instead of being
offered. `references/interview.md` states this per round.

This is the same discharge the `grilling` row of `decision-authority.md` already describes, applied
inside a forked body rather than as an overlay. Both, deliberately: the overlay covers a reader who
has the rule without the skill loaded, and the body covers the moment the stop would happen, which
is where an explicit in-skill instruction has beaten a general rule before.

## 2. Four defects fixed, each of which made the shipped suites unrunnable here

None of these are Odin preferences. Every one is a portability bug that reports itself as something
else, which is why they survived: the failure text names a defect in the factory rather than the
cause.

| Where | Defect | Symptom it produced | Fix |
|---|---|---|---|
| `scripts/_test_audit_runner.py` | `SK` was an absolute path to the author's own workstation (`C:\Users\...`) | `FileNotFoundError` on every machine but one — a suite that had never run anywhere else | resolved from `__file__` |
| `templates/harness/ci.py` | `resolve()` handled Windows `.cmd` shims but not a host with `python3` and no `python` | `GATE_FAILED: static`, which reads as "your code does not compile" | falls back to `python3` then `sys.executable`, in the same function and for the same reason |
| `templates/runner/factory/*.sh` | the literal word `python`, in five scripts and seventy places | `rc=127`, surfacing as `ILLEGAL_TRANSITION`, a gate that refuses everything, and a dispatcher answering `idle` forever | one `FACTORY_PYTHON` knob in `config.sh`, exported by name like every other |
| `scripts/_test_runner.py` | fixtures built with `git init` and then addressed as `main` | `fatal: invalid reference: main`, swallowed by a `2>&1` and re-reported as `ESCALATE: could not create worktree` | `git init -b main` — the fixture establishes the input its verdict turns on |

Measured before: `_test_runner.py` **20 of 56**, `_test_audit_runner.py` **crashed on import**.
After: **56/56** and **12/12 FIRED, 0 MISSED**. `_test_factory_doctor.py` was **22/22** throughout.

The first three would reach any Linux user of the upstream skill. They are worth reporting upstream.

## 3. Two runner scripts were dropped, then restored — and why the reversal is recorded

The plan for this fork (`DF-3`) chose to re-express the runner as Archon workflow YAML, on the
argument that shipping a second definition of the pipeline is the failure upstream's own
`automation.md` warns about: *the one nobody runs is the one that drifts.*

**Attempted, measured, reversed.** `orchestrator.sh` and `run-workflow.sh` are named in about
twenty places across `factory_doctor.py` (1,312 lines) and `_audit_runner.py` (599) — the audit
suite's entire premise is that those two files exist and can be read. Removing them left the
1,900-line audit machinery with no subject, which is a worse outcome than the one DF-3 was avoiding:
not two definitions, but one definition and a gate that silently checks nothing.

**What ships instead.** The runner stays whole and remains the armed unattended loop. Archon is the
**on-demand and observable** front door — `workflows/factory-lap.yaml` runs one dispatcher tick as a
workflow, so a lap can be started, watched, resumed and cancelled through the same surface as every
other Odin workflow, without a second copy of the pipeline existing anywhere. The seam is
`config.sh`, which is where upstream says project-specific values belong.

The dispatcher is still the only thing that decides what runs next. That property is what DF-3 was
protecting, and it is intact.

## 4. Odin's harness owns four things the skill used to own alone

| Concern | Upstream | Here |
|---|---|---|
| Protected governance files | `factory/guard.py`, called by a node | **also** an always-on PreToolUse layer in `.claude/hooks/odin-safety-guard.sh` — a guard a node calls is a guard the node can skip |
| Verification command | `harness/ci.py` | `FACTORY_VALIDATE_CMD` points at the project's own gate; in this repository that is `.claude/scripts/ci-local.sh` |
| Where the plan goes | a design doc in the conversation | `.claude/docs/plans/`, because that is the only directory `odin-plan-gate.sh` searches |
| Suite wiring | run by hand | `.claude/tests/factory.test.sh`, stepped by `ci-local.sh` |

## 5. Voice

The upstream body is warm second-person prose throughout. Odin's ADR-0011 voice never turns off
mid-skill, so `SKILL.md` was rewritten in Odin fragments. **The references were not** — they are
agent-read reference material rather than speech to a human, and rewriting 2,200 lines of careful
prose would have cost the reasoning that makes them worth having. Where a reference tells the agent
to *say* something, the Odin overlay at its head restates the instruction in the harness's terms.

## 6. What was deliberately not brought across

- `dark-factory-diagram.png` — a human-facing image, and upstream's own comment says it is not for
  the agent. A binary in a skill directory that nothing reads is context nobody spends well.
- Nothing else. Every reference, template, script and runner file is present.

## Porting an upstream change

1. Diff upstream against `ecef6ffd4caa0b23a8c79601c1215b1e2908ac72`.
2. Anything touching `references/interview.md`'s question rounds, the two dropped-then-restored
   runner scripts, or a bare `python` invocation lands on top of a divergence above — read the row
   before applying.
3. Re-run all three suites. They are the fork's evidence that a port did not break it:

   ```sh
   bash .claude/tests/factory.test.sh
   ```
