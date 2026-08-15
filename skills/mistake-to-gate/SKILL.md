---
name: mistake-to-gate
description: Turn a mistake that just happened into an always-on mechanical gate with a matrix that proves it fires. Use this whenever something slipped through and the response is "that shouldn't happen again" — a wrong file edited, a stale or guessed reference, a broken link, an id from the wrong namespace, a hand-edit of a generated file, a guard that silently passed, a convention nobody enforced. Also use it when asked to "add a check", "make sure this can't regress", "enforce this always", "prevent this in future", or when a review, audit or postmortem produces a rule with nothing behind it. Fires even when the user only describes the mistake and never asks for a check.
---

# Mistake to Gate

A rule nobody checks is a rule that is wrong by the second change. This skill turns one concrete
incident into a check that runs on every push, plus the matrix that proves the check would have
caught it.

The output is three things, and the work is not finished until all three exist:

1. a checker that exits non-zero on the mistake,
2. a matrix asserting **exit codes** — a BLOCK case per real mistake, and ALLOW cases for the near
   misses,
3. a line in the repository's single gate list.

This skill also owns the **mistake log engine** — `scripts/mistakes.py`, which counts recurrence by
failure-mode key and tells this repository when a mistake has happened often enough to stop being a
mistake (ADR-0057). `oops` appends to the log; §11 below is what happens when a key reaches the
threshold.

## When this fires

Any of these, whether or not a check was requested:

- something was edited, cited or named wrongly and a human caught it
- a convention lives in prose ("always qualify the id", "never hand-edit that file") with no
  enforcement behind it
- a review, audit or postmortem produced a "we should always…" statement
- a guard was found to pass when it should have failed
- **a failure-mode key reached the promotion threshold** — `mistakes-check.sh` fails with
  "promotion due", or `oops` announced the promotion band. At that point the incident is not a
  mistake any more, it is a missing rule, and §11 below is the procedure

## The procedure

### 1. Name the incident in one sentence, with its artifact

Write what actually happened and the exact string, path or diff that shows it. "Links were wrong" is
not an incident. "`0027-plan-depth-standard.md` was linked from three files; the file on disk is
`0027-skill-utilization-and-plan-depth.md`" is.

The artifact matters because it becomes the first BLOCK case. A gate built from a remembered
*category* of mistake tends to check the category you imagined rather than the one that happened.

### 2. Decide whether it is mechanically checkable

Ask: **is there a predicate over repository state that is true exactly when the mistake is present?**

| Checkable | Not checkable — do something else |
|---|---|
| a reference resolves; a count matches; a generated file matches its source; an id is namespaced; a required section exists | "the plan was shallow"; "this name is confusing"; "the abstraction is wrong" |

If it is not checkable, this is a rule or a review criterion, not a gate — reach for `rules-distill`
and say so, rather than building a check that approximates judgment. A gate encoding taste produces
false positives, and a gate people disagree with gets disabled, taking its true positives with it.

### 3. Key the check on the consumer, not on a correlate

Check the thing that actually breaks. A sweep keyed on something that merely *correlates* with the
real predicate stops asserting the moment the correlation drifts — silently, because it still passes.

To check that a cited document exists, resolve the citation to a **file**. Do not check that its
number appears in an index: the index is a correlate, the file is the consumer.

### 4. Scope it to what this repository owns

A gate reaching outside its boundary produces failures its owners cannot fix. Where a workspace holds
nested repositories, each keeps its own numbering and conventions; checking a subtree's ids against
the parent's set is not thoroughness, it is the exact confusion the gate exists to prevent. State the
boundary in a comment, so the next reader does not "improve" the gate by widening it.

### 5. Write the checker so it can be tested

Two properties separate a gate from a script that happens to run in CI:

- **It takes a root argument** — `check.sh [ROOT]`, defaulting to the repository. Without it the
  matrix has nothing to point at but the real tree, which is passing, so every case is an ALLOW case
  and nothing demonstrates the gate can fail.
- **It reports what failed, where, and what to do**, collecting findings and exiting non-zero once at
  the end. A run that aborts on the first failure hides every later one.

Follow whatever CLI conventions the repository already carries: diagnostics to stderr, data to
stdout, meaningful exit codes.

### 6. Do not let the gate disable itself

This is the failure mode that matters most, because it is invisible: **a check depending on a tool
that may be absent, which treats absence as "nothing found".**

A real instance: a scan written in `awk`, inside a script specified to run with nothing on `PATH`.
Where `awk` was missing it produced empty output and **passed** — it had been agreeing with every
input for as long as it existed.

Prefer shell builtins, or the language the repository already requires. Where an external tool is
genuinely needed, **fail closed**: detect its absence and exit non-zero naming it. A guard that
disables itself when a dependency is missing is indistinguishable from a guard that agrees with you.

### 7. Falsify it before trusting it

The matrix is the deliverable, not a formality.

- **One BLOCK case per recorded occurrence** — each one reconstructed in a fixture from the artifact
  in its `MISTAKES.md` row, not a plausible variant. Where a single incident is being gated, that is
  one case; where a key reached the promotion threshold, it is four, and they are strictly better
  evidence than any variant you could invent — four independent reconstructions of the same
  condition are what tell you whether the predicate you wrote is the predicate that keeps failing.
- **ALLOW cases for the near misses**: the legitimate forms that resemble the mistake. A guard that
  blocks everything gets disabled, and then it protects nothing.
- **Assert behaviour, never source.** Run the checker and read its exit code and output; never grep
  the checker for the string it is supposed to emit. A source-grep stays green through a rename of
  the very thing it checks.

Then prove the matrix can fail: break the checker deliberately, watch a case go red, restore it. A
matrix never seen red has never been tested.

### 8. Wire it into the one gate list — the owner's, never the parent's

Add it where the other gates live, so it runs by the command contributors already run. Where one list
is wrapped by several runners, add it to the **list**, never to a runner — a gate added to one wrapper
runs in one place while creating the impression of coverage everywhere.

**Which list is decided by who owns the code the gate checks**, and getting this wrong is the
boundary error §4 warns about, made at the last step:

| The mistake happened in… | The list | Named from |
|---|---|---|
| the harness itself — `.claude/`, root docs, harness scripts | `.claude/scripts/ci-local.sh`, beside the other `step "…"` lines | this repository's `CLAUDE.md` item 7 |
| a project under `projects/<slug>/` | **that project's own** gate list | that project's `README`/`CONTRIBUTING`/`docs` — read them; never assume it is `ci-local.sh` |
| a `projects/<slug>/` that is its own git repository | that repository's list, committed there | its own docs; the harness cannot commit into it |

A harness gate that checks project code fails on code the harness does not own, and its owners
cannot clear it — which is how a gate gets commented out. When the project has no gate list yet,
creating one *is* the work; adding the check upward is not a shortcut, it is a different check.

Then run the whole suite, not just the new gate. A new check often fails older fixtures that predate
its requirement. That is the gate working; those fixtures are updated in the same change.

### 9. Move whatever the repository asserts about itself

Adding a script, skill or test frequently moves a number some other gate checks — inventory counts,
enumerations, a documented total. Move them in the same change. A count that drifts is the next
incident.

### 10. Record it where it changes a contract

If the gate enforces a **new** obligation, that is a decision and it earns an ADR. If it enforces
something already agreed, the commit message carrying the incident is enough.

### 11. Promotion — when the same key reaches the threshold

Four recorded occurrences of one failure-mode key is not four mistakes; it is one missing rule that
has been paid for four times. Promotion is what closes it, and it has three parts — **all three, or
the key keeps re-triggering the gate until somebody deletes the gate**.

1. **Read every row for the key first.**

   ```sh
   python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report . --key ci-gate/stale-reference
   ```

   Each row carries an artifact. Those artifacts are the BLOCK cases (§7): reconstruct all of them,
   and let the predicate be the one that catches every one. A predicate that catches three of four
   is the wrong predicate — the fourth row is telling you where the real condition is.

2. **Land both halves.** A rule with no check is wrong by the second change; a check with no rule is
   a failure whose reason nobody can read.
   - the **check**, built by §1–§9 above, in the owner's gate list per §8;
   - the **rule text**, in the owning `CLAUDE.md` — the harness's for a harness key, that project's
     for a project key — or in a `.claude/rules/` file when it is a rule the harness carries. Route
     the rule-text half through the forked `rules-distill`, which drafts it, decides its tier
     (`paths:`-scoped by default; always-on costs context on every turn of every session) and
     records the reasoning.

3. **Close the loop on the rows.** The originating occurrences are what the gate reads, so a
   promotion that does not mark them leaves the gate failing forever:

   ```sh
   python3 .claude/skills/mistake-to-gate/scripts/mistakes.py promote . \
     --key ci-gate/stale-reference --fix 'gate: .claude/scripts/doc-reference-check.sh; rule: CLAUDE.md item 8'
   ```

   Then run `bash .claude/scripts/mistakes-check.sh` and watch it go green. That transition **is**
   the proof the promotion is complete — the same "assert behaviour, never source" rule applied to
   your own closing step.

Later occurrences of a promoted key are still logged. A row arriving after promotion means the rule
exists and the check missed it, which is a new incident about the check — the most valuable kind.

## Commit shape

One commit: checker, matrix, gate-list line, and any counts that moved. The message opens with **the
incident** — concretely — and then what now refuses it. Months later that message is the only
surviving explanation of why the check exists, and a gate whose reason is lost is a gate somebody
deletes.

## What this is not

- **Not a linter.** One gate, one predicate, one incident.
- **Not a substitute for review.** Gates catch the mechanical class; the rest is judgment, and
  pretending otherwise is how a green pipeline comes to mean nothing.
- **Not a place for taste.** If competent people could disagree about a finding, it belongs in
  review.

## Checklist

- [ ] Incident named concretely, with the artifact that shows it
- [ ] Predicate is mechanical, not judgment
- [ ] Keyed on the consumer, not on a correlate
- [ ] Boundary stated — what is owned, and what is deliberately not checked
- [ ] Checker takes a root argument, reports every finding, exits non-zero once
- [ ] No dependency whose absence becomes a pass; missing tools fail closed
- [ ] BLOCK case per real mistake; ALLOW cases for the near misses
- [ ] Matrix asserts exit codes and output, never the checker's source
- [ ] Matrix seen red at least once, deliberately
- [ ] Added to the single gate list; full suite re-run; older fixtures fixed
- [ ] Counts and enumerations the repository asserts have been moved
- [ ] Commit message opens with the incident
- [ ] **On a promotion:** every row for the key marked `promoted` with the gate path in `fix`, rule
      text landed in the owning `CLAUDE.md` (or a tiered `.claude/rules/` file), and
      `mistakes-check.sh` watched going from red to green
