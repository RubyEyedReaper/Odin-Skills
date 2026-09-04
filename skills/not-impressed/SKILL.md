---
name: not-impressed
description: Use when reviewing code you did not write by hand — an agent-generated diff, a large pasted implementation, a PR that looks finished — and the question is whether it is overdeveloped. Assumes the code is machine-generated and untrusted until validated.
---

# not-impressed

## What this is not for

This skill owns exactly one verdict that nothing else in this repository owns: **is this code
overdeveloped?** Everything adjacent already has an owner. Route there instead.

| If the task is… | It belongs to | Not here because |
|---|---|---|
| Routine review after a change | `code-reviewer` agent | That is the default reviewer; this one starts from a hostile prior and costs more |
| Security-only review — injection, secrets, authz, OWASP | `security-reviewer` agent | It carries the triggers and the remediation ladder; this skill cites them |
| Critiquing a plan before code exists | `plan-adversary` agent | There is no diff to review. Severity tables and style checks do not apply |
| Interface polish — spacing, states, hierarchy | `impeccable` | Design judgment, not structural judgment |
| Removing dead code and duplication after the fact | `refactor-cleaner` agent | That is remediation. This skill reports; it never deletes |
| Asking what already solved this, before the code was written | `consistency` | That is the precondition, not the review. A diff reimplementing something the tree already has is overdevelopment this skill can only find afterwards |

Two of those are honest de-escalations. If the diff is small, human-written and uncontroversial,
`code-reviewer` is the correct answer and this skill is overkill — which is the same mistake this
skill exists to find, pointed at itself.

## The stance

**Assume the code is machine-generated and untrusted until validated.** Not malicious — plausible.
Machine-generated code fails in a specific direction: it is fluent, it is well-formatted, it names
things reasonably, and it is *too much*. It reaches for an abstraction before there are two callers,
adds a cache before there is a measurement, wraps a working call in an adapter, and pulls a
dependency for six lines of logic. None of that looks like a bug. All of it is cost the reader pays
forever.

So the default verdict is not "approve" and it is not "reject". It is **trim**, until the code shows
why each part earns its place. A finding is not an opinion about taste — it names what to delete and
asserts, in a sentence, that deleting it preserves the original behaviour.

Being unimpressed is the discipline. Fluent code reads as correct code, and the reviewer who is
impressed has stopped reviewing.

## The three references

Read them in this order. Each answers a different question.

- **[references/review-rubric.md](references/review-rubric.md)** — the eleven verification bullets
  and, for each, *what evidence discharges it*. Read first. It is the completeness check: a review
  that skipped a bullet is not finished. It cites the severity ladder rather than defining one.
- **[references/overdevelopment-catalog.md](references/overdevelopment-catalog.md)** — six patterns,
  each with its recognition signal, the simpler-alternative recipe, and the behaviour-preservation
  sentence that must be written before the finding counts. This is the part no other surface in this
  repository owns, and it is the reason this skill exists.
- **[references/report-template.md](references/report-template.md)** — the output shape. Five
  classes in a fixed order. Copy it; do not improvise a structure.

## Procedure

### 1. Dispatch — never review inline

Dispatch the `adversarial-reviewer` agent (`.claude/agents/adversarial-reviewer.md`). Do not read
the diff and form a verdict in the session that produced it.

Two independent reasons, either sufficient:

- **A reviewer sharing the author's context inherits the author's rationalisations.** The session
  that wrote the abstraction already believes the second caller is coming. A fresh context does not.
- **An invoked skill body never unwinds.** There is no call stack: invoke this skill inline from a
  build loop and its body plus three references stay resident for every remaining turn. A dispatched
  agent has a real context boundary and returns a real value.

Recorded as ADR-0101.

Give the agent the diff or the file list, the surrounding conventions it should measure against, and
nothing about why the code was written the way it was. Rationale is exactly what it must not have.

### 2. Verdict

The agent returns one of three, and the finding shape is defined in its own file:

| Verdict | Means |
|---|---|
| `ship` | Nothing to delete. Every part earns its place, and the reviewer names the part it tried hardest to cut. |
| `trim` | The code works and is too much. Findings name what to delete and why deleting it is behaviour-preserving. |
| `rebuild` | The structure is wrong, not excessive. Trimming produces a smaller wrong thing. |

`ship` requires the same evidence as the others. "Looks fine" is not a verdict — it is a review that
did not happen.

### 3. Disposition

Every finding is disposed of as **accepted**, **mitigated** or **deferred** by the session that
requested the review. A finding nobody can dispose of is an opinion. Remediation — actually deleting
the code — is `refactor-cleaner`'s act or the author's, never this skill's.

## Common mistakes

| Mistake | Why it fails |
|---|---|
| Reviewing in the authoring session because the diff is small | Diff size does not change the context boundary. The rationalisations are inherited either way. |
| Reporting "this is over-engineered" with no deletion named | Unfalsifiable. A finding that names no target cannot be accepted, mitigated or deferred. |
| Naming a deletion without the behaviour-preservation sentence | That is a proposal to change behaviour wearing a simplification's clothes. |
| Restating a severity ladder | One ladder, one owner: `.claude/rules/common/code-review.md`. A second copy drifts and becomes the defect. |
| Flagging every abstraction | An abstraction with two real callers earns its keep. The catalogue's signals exist so the finding is evidenced, not reflexive. |
| Padding the report to look thorough | The skill whose verdict is "too much" cannot produce too much. Five classes, findings only. |
