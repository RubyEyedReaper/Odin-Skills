# The operating model — phases, owners, and what each project owes

## How to read this file

Each row names the phase, the skill that owns it, and **what that owner decides**. No row explains
*how* the phase is done — that is the owner's text, and a second copy of it drifts silently.

**The test:** if a reader could follow a phase from this file without ever invoking the skill it
names, that row has restated instead of routed, and is a defect.

## The lifecycle

| Phase | Owner | What the owner decides |
|---|---|---|
| First session in an unfamiliar tree | `codebase-onboarding`, `repo-scan` | What the codebase is, its entry points and conventions |
| What to build, what is left, what is next | `roadmap` | Item identity, status, dependencies, and which item is unblocked |
| One item too big for a single plan | `blueprint` | The decomposition into construction steps and their graph |
| Planning before source is edited | `superplan`, `writing-plans` | The decision forks, the recommendation for each, and the recorded scope |
| Execution | `executing-plans`, `subagent-driven-development` | Which step runs next and who runs it |
| Vocabulary | `domain-modeling` | The project's terms, recorded in the project's own `CONTEXT.md` |
| Decisions | `architecture-decision-records`, `decision-matrix` | Whether a fork is scored or argued, and what the record says |
| Something that should not have happened | `oops`, `mistake-to-gate` | Root cause, and whether a mechanical gate is possible |
| Handoff to another session | `/relay`, `successor` | What the successor needs and how it is launched |
| Completion | `verification-before-completion`, `finishing-a-development-branch` | Whether the evidence supports the claim, and how the branch is integrated |

Two phases in that list are the reason this file exists at all — they route to *nobody*, because
nobody else owns them: the project-switch ritual in the skill body, and the checklist below.

## The per-project artifact checklist

A project subtree is self-contained. These are what it owes, each with the command that says
whether it exists. Run them from the repository root, with `P=projects/<slug>`.

| Artifact | Path | Check |
|---|---|---|
| README | `$P/README.md` | `test -f "$P/README.md"` |
| Changelog | `$P/CHANGELOG.md` | `test -f "$P/CHANGELOG.md"` |
| Its own ADR set | `$P/docs/adr/` | `ls "$P"/docs/adr/*.md` |
| Its own decision ledger | `$P/docs/decisions/` | `ls "$P"/docs/decisions/*.md` |
| Its own roadmap, if more than one unit of work remains | `$P/docs/roadmap/roadmap.json` | `test -f "$P/docs/roadmap/roadmap.json"` |
| Its own mistake log | `$P/MISTAKES.md` | `test -f "$P/MISTAKES.md"` |
| Data-provenance manifest, if it has a domain catalog | `$P/docs/data-provenance.json` | `test -f "$P/docs/data-provenance.json"` |
| Its own gate | whatever the project's docs name | run it and read the exit code |

None of these is a harness file. The harness's own inventory counts ignore everything under
`projects/`, and a project's ids are its own sequence — a project's decision recorded into the
harness ledger inflates a sequence that project cannot see.

## Silence is not clean

**A project-scoped guard with nothing configured produces no findings, which reads exactly like a
project with nothing to find.** The data-provenance manifest is the clearest case: a guard that
walks up from a source file looking for `docs/data-provenance.json` and does not find one has no
vocabulary to check against, so it says nothing. The output of "not configured" and the output of
"clean" are the same output.

So a new project's guard is proved with a **positive control**, never with an absence:

1. Write the manifest.
2. Introduce a deliberate violation of the kind the guard exists to catch.
3. Run the guard and confirm it **flags** that violation.
4. Remove the violation and confirm the guard goes quiet.

Step 3 is the one that carries the information. Without it, step 4's silence means nothing, because
silence was already the answer before the manifest existed.

The same reasoning applies to any project-scoped check: **before reporting a clean run, establish
that the check can fail.**
