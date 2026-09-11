---
name: project-manager
description: Use when the question is about the portfolio rather than about one project — which projects exist, which are active and which have gone dormant, which carry unlanded branches, which are missing their own README, changelog, ADR set or roadmap, and where a campaign's next wave should go. Also on "what projects do we have", "is anything stalled", "which project needs attention", "portfolio status", "status across projects", and before a coordinator picks the slices for a fleet.
metadata:
  origin: Odin
artifact: .claude/skills/project-manager/scripts/project-status.sh
---

# project-manager — the layer above one project

> **Voice (ADR-0011).** Prose to human stays Odin. The probe's own output is a **deliverable**:
> normal English, because a coordinator acts on it without reading this file.

## What this is not for

`projects` owns **one** project. This skill owns the question one layer up, and owns nothing else.

| The task | Its owner | Why not this skill |
|---|---|---|
| Working inside one project — the routing table, the switch ritual, the artifact checklist | `projects` (ADR-0106) | That is the whole of one project's lifecycle. This skill never enters a project; it reports across all of them. |
| What to build next, in what order, within a project | `roadmap` | An ordering over items. This reports how many are open, and never which one is next. |
| What is left across the roadmap and the tracker at once, for a fleet | `gauntlet frontier` | A work frontier computed at read time. This is a *portfolio* reading and schedules nothing. |
| Who owns a delegated session, and whether a worker is stalled | `successor-manager` | Sessions and branches under a coordinator. This reports repositories. |
| Whether a delegated branch's work has landed | `bl_classify` — `.claude/scripts/lib/branch-landedness.sh` | The one implementation of landedness. The probe **calls** it; a second copy would have no way to disagree out loud. |
| Whether a project's docs are in the right place | `odin-project-doc-guard.sh` | A write-time guard and a CI scan. This reports which artifacts are absent; it never decides where one belongs. |
| Where a project's roadmap lives | `roadmap_candidates` — `.claude/scripts/lib/roadmap-discovery.sh` | Discovery has one owner. |

**The one thing this skill owns:** the **join** — five directories read as one portfolio, with each
dimension's unreadable case reported rather than folded into a verdict.

## The probe

```sh
bash .claude/skills/project-manager/scripts/project-status.sh . \
     [--json] [--dormant-days N] [--project SLUG]
```

| Exit | Means |
|---|---|
| 0 | every project reported, every dimension measured |
| 1 | at least one dimension is `undetermined` — an input the probe could not read |
| 2 | could not look — no root, no `projects/` directory, nothing under it, or a library it composes is missing |

It **changes nothing**: no fetch, no checkout, no write, no cleanup. A case in the matrix asserts
the file fingerprint, `HEAD` and the checked-out branch are all identical afterwards, because
read-only is a property of the effect and two recorded occurrences of
`ci-gate/fixture-reads-ambient-state` *consumed* the state they probed.

It also **never runs a project's gate.** A portfolio probe that spent an hour per project would be
run once and then avoided — and a project's gate is `projects`' business, per project.

## The dimensions, and what each refuses to guess

| Dimension | Answers | Refuses |
|---|---|---|
| presence | `populated` / `uninitialised` / `empty` | reporting an empty directory as a project missing files |
| activity | a **day count**, then `active` / `dormant` against `--dormant-days` | a verdict whose input the reader cannot see |
| artifacts | the missing ones **by name** | a count, which does not say what to write |
| roadmap | `<open>/<total>` from the canonical JSON | reading the generated `ROADMAP.md`, which is regenerated from it |
| branches | `N unlanded, N landed, N unmeasured` | counting an unmeasured branch as landed |
| skills mirror | `sp_mirror_state`'s four values | treating an unpopulated submodule as an empty mirror |

### Two defects the probe's own first run found, which is why it exists

Both produced confident, specific, wrong output, and both are now matrix cases.

**`git -C <dir>` walks up.** It succeeds for any path *inside* a repository, so a
`projects/<slug>/` that is a plain subdirectory answered every branch question with the **harness's**
branches. Four projects reported the identical `8 unlanded, 13 landed` — the harness's own branch
set, attributed to four repositories that do not have one. Four agreeing numbers is what made it
visible, exactly as in the incident `branch-landedness.sh`'s own header records. The fix is
`ps_is_repo_root`: the directory must *be* a repository root, not merely sit in one.

**An uninitialised submodule is an empty directory.** Two projects reported
`missing: README.md CHANGELOG.md docs/adr/ docs/roadmap/roadmap.json`. Both have all four; they were
simply not checked out in that worktree. A probe that reads an empty directory and reports four
missing artifacts has not found four gaps — it has failed to look, and said something false about a
project as a result. The fix is `ps_presence`, measured **before** every other dimension, which is
`sp_mirror_state`'s four-valued lesson applied one directory over.

The general rule both are instances of: **`undetermined` is not a verdict and is never folded into
one** (`cli/coding-style.md` § A Verdict Requires an Input You Actually Read). Four recorded
occurrences of that key are functions that composed a path, a probe or a join on an input they had
never established, and answered with a real word anyway.

## Procedure

1. **Read the portfolio.** `project-status.sh .` — start here, before choosing where work goes.
2. **Treat every `undetermined` as a question, never as a zero.** An uninitialised submodule is
   answered by initialising it; an unreadable roadmap is a finding about that project.
3. **Route each substantive finding to its owner.** A missing artifact is `projects`' checklist. An
   unlanded branch is `successor-manager`'s register, or `finishing-a-development-branch`. A stale
   roadmap is `roadmap reconcile`. This skill files nothing and fixes nothing.
4. **Say what the reading was taken against.** The day count and `--dormant-days` both appear in the
   output; quote them, because "dormant" alone is a word whose threshold the reader cannot see.

## Red flags

| Thought | Reality |
|---|---|
| "The project directory is empty, so it has no README" | It is an uninitialised submodule. You did not look. |
| "`git -C projects/x` worked, so x is a repository" | git walked up. You asked the harness. |
| "Zero open roadmap items — that project is done" | `undetermined` prints as `undetermined`, never as `0/0`. Check which you read. |
| "No branch came back unlanded, so nothing is outstanding" | Read the `unmeasured` count in the same line. Silence about a branch is not that branch being clean. |
| "It says dormant, so drop it" | Dormant is a reading of a day count against a flag you chose. The count is printed; look at it. |
| "Add a gate run per project so the report is complete" | An hour-long probe is a probe nobody runs. Gates belong to each project. |
| "Have it initialise the missing submodules while it is there" | It changes nothing, and a matrix case asserts that. Fixing is somebody's act, with its own authorisation. |

## Quick reference

| Need | Where |
|---|---|
| The whole portfolio | `bash .claude/skills/project-manager/scripts/project-status.sh .` |
| One project | `… --project <slug>` |
| Machine-readable | `… --json` (an unreadable dimension is `null`, never `0`) |
| A different dormancy reading | `… --dormant-days N` |
| Working inside one project | `projects` |
| What is left for a fleet | `gauntlet frontier` |
| Whether a worker is stalled | `successor-manager` |
| What the probe refuses, and the near misses it must not | `.claude/tests/project-manager-status.test.sh` |
