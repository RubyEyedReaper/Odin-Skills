# Publishing

This repository is **published**. It exists in two public shapes, both one-way mirrors of
`.claude/skills/` in the Odin harness, which stays authoritative (harness ADR-0001, harness
ADR-0061, and [`adr/0001-distribution-monorepo-and-per-skill-repos.md`](adr/0001-distribution-monorepo-and-per-skill-repos.md)):

| Shape | Where | Published |
|---|---|---|
| The distribution monorepo — this tree, installable as one Claude Code plugin | <https://github.com/RubyEyedReaper/Odin-Skills> | 2026-08-17, first push `aa75b29e9c05b7e0be83c9e6155396644d4c3fb8`, 21 commits on `main` |
| One repository per skill, `skill-<name>`, for taking a single skill without the bundle | `https://github.com/RubyEyedReaper/skill-<name>` — 17 of them | 2026-08-17, all public, one per directory under `skills/` |

Development is coordinated in the Odin harness under `projects/Odin-Skills/`. **Nothing published is
ever edited in place**: a published repository is corrected by re-running the publishing script, and
a pull request opened against one is not merged. Two publish targets must not become two development
targets.

This document is the operating runbook: how the mirrors are produced, how to publish an eighteenth
skill, and how to push a subsequent update.

## Why a subtree split rather than a fresh `git init`

`git subtree split` carries the commit history of a directory into a standalone branch, so a
published repository opens with the real record of how it was built. A fresh `git init` throws that
away and starts at one squashed commit — which also breaks the audit trail the fork `UPSTREAM.md`
files depend on: they cite upstream and local commits that exist only in that history.

Both shapes are produced this way, and both are split from the harness's `origin/main` rather than
from a working tree, so a published mirror can only ever contain merged work.

## Why the harness keeps this subtree

Extraction did not remove `projects/Odin-Skills/` from the harness, and will not. The harness's
`.claude/scripts/vendor-skills.sh` derives its refresh-protection list from `skills/` in this
directory — the directory listing *is* the definition of "a skill Odin authored or forked", and a
vendor refresh consults it to know what it must not overwrite. Delete the mirror and the next
`--refresh` silently clobbers every fork. The cost is a few megabytes of duplication in the harness;
the alternative is a silent data-loss path.

## Publishing one skill

```sh
scripts/publish-skill.sh <skill-name> [--owner OWNER] [--root DIR] [--dry-run] [--verify]
```

Flags follow the skill name. `--owner` defaults to `RubyEyedReaper`. Exit `0` on success or when
there is nothing to do, `1` when the script refused or a step failed, `2` on a usage error.

**Mode is chosen, not assumed.** `gh repo view <owner>/skill-<name>` decides between two paths:

- **create** — split `projects/Odin-Skills/skills/<name>` out of the harness, clone the split branch,
  write the landing page and licence artefacts, create the public repository, push `main`.
  The split runs *before* the repository is created, so a failed split leaves no empty public
  repository behind.
- **update** — clone the published repository, replace its tracked content from `skills/<name>`,
  rewrite the landing page and artefacts, and push only if something actually changed
  (`already matches skills/<name> — nothing to push`). A second `subtree split` cannot fast-forward
  the first push, and force-pushing is forbidden, so a rerun must take this path.

**The subtree prefix is repository-root-relative**, computed rather than hardcoded: `git subtree`
runs `cd_to_toplevel` before reading `-P`, so a prefix relative to this directory splits nothing.
Inside the harness the prefix is `projects/Odin-Skills/skills/<name>`; in a standalone clone of the
monorepo it is `skills/<name>`. Both are real, which is why neither is written down in the script.

**Licence artefacts are selected by skill class, and the selection fails closed** — the alternative
to an unsatisfied class is publishing someone else's work under Odin's terms:

| Class | Detected by | Carried into the published repository |
|---|---|---|
| Odin's own | no `UPSTREAM.md` and no `LICENSE` | `LICENSE-MIT` + `LICENSE-CC-BY-SA-4.0` |
| A fork with an upstream licence | `skills/<name>/LICENSE` | that `LICENSE` + the root `NOTICE` |
| A fork whose upstream published none | `UPSTREAM.md` + `skills/<name>/NOTICE` | that `NOTICE`, concatenated with the root `NOTICE` under the one filename |
| A fork that declares neither | `UPSTREAM.md` alone | **refused, before any network call** |

The root `NOTICE` travels with every fork because it carries the Apache-2.0 §4(d) notice text, which
exists nowhere else in the tree. Of the 17 published skills, 7 are Odin's own, 9 are forks carrying
an upstream `LICENSE`, and `rules-distill` is the declared-absence case.

`--dry-run` prints every `git` and `gh` command for both modes and touches no network — useful
before the first publish of a new skill. `--verify` clones the published repository and diffs it
against `skills/<name>`, ignoring only the files the script itself writes (`README.md` and the
licence artefacts); it is the live check that a published repository still matches its source, and
it is preferred over a table of shas that goes stale the next time anything is pushed.

The generated landing page opens with a read-only banner naming
[RubyEyedReaper/Odin-Skills](https://github.com/RubyEyedReaper/Odin-Skills) as the place development
happens. It deliberately does **not** name the harness repository: that repository is private, so a
link to it is a 404 for every visitor and points issues at a tracker nobody outside the account can
reach. `scripts/tests/publish-skill.test.sh` walks every GitHub link the generated page contains and
fails on any repository that is not itself a publish target.

## Publishing an eighteenth skill

Skill content is authored in the harness, never here.

1. Land the skill in the harness `.claude/skills/<name>/`, and — if it is a fork — its `UPSTREAM.md`
   and the upstream `LICENSE` (or a `NOTICE` declaring the absence) in `skills/<name>/` here.
2. `scripts/sync-from-odin.sh` — copy `.claude/skills/` → `skills/`. `UPSTREAM.md`, `LICENSE` and
   `NOTICE` are this repository's own packaging and are preserved across the sync.
3. Add the skill to `.claude-plugin/marketplace.json`, `docs/PROVENANCE.md`, the licensing table in
   `README.md`, and the harness `FORKS.md` if it is a fork. `scripts/validate-skills.sh` checks
   manifest parity and provenance, so a missed entry is a red gate, not a silent omission.
4. `bash scripts/validate-skills.sh` and `bash scripts/tests/validate.test.sh` — green before
   anything goes out.
5. `bash scripts/publish-skill.sh <name> --dry-run`, read the plan, then run it without the flag.
6. `bash scripts/publish-skill.sh <name> --verify`.

## Pushing a subsequent update to the monorepo

Run from the root of the Odin harness checkout, after the change has landed on the harness's `main`:

```sh
git fetch origin
git subtree split -P projects/Odin-Skills -b odin-skills-extract origin/main
git -C <clone-of-Odin-Skills> fetch <harness-checkout> odin-skills-extract:refs/heads/incoming
git -C <clone-of-Odin-Skills> checkout main
git -C <clone-of-Odin-Skills> merge --ff-only incoming
git -C <clone-of-Odin-Skills> push origin main
```

A refused fast-forward means the published `main` and the split have diverged — something was
pushed to the publish target that the harness does not contain. Report it and reconcile; never force.

Releases are tagged on the published repository, annotated, from the same clone:

```sh
git -C <clone-of-Odin-Skills> tag -a v0.1.0 -m "First published release of the Odin-Skills distribution"
git -C <clone-of-Odin-Skills> push origin v0.1.0
```

`v0.1.0` marks the first release whose documentation describes the published state. The first push
was deliberately left untagged: the tree still carried text calling this project unpublished, and
tagging then would have made that text the content of the release.

Updating the per-skill repositories after a sync is the same `publish-skill.sh <name>` run — the
update path — one per changed skill.

## Verifying a published tree stands alone

From a standalone clone of the monorepo:

```sh
bash scripts/tests/validate.test.sh   # 19/19
bash scripts/validate-skills.sh       # OK: 17 skills validated
```

`scripts/sync-from-odin.sh --check` needs a harness checkout at `../..` and refuses without one.
From a standalone clone, point it at one explicitly:

```sh
bash scripts/sync-from-odin.sh --check --odin /path/to/Odin
```

`scripts/tests/publish-skill.test.sh` (32 cases) covers every decision the publisher makes before it
touches the network, with `git` and `gh` stubbed earlier on `PATH` — a case that reached GitHub would
fail rather than create a public repository.

## CI in the published repository

`.github/workflows/validate.yml` triggers on `workflow_dispatch` **only**, and must stay that way
while this directory lives inside the Odin harness. An automatic trigger here fires on GitHub's
runners the moment a push lands, which is exactly what Layer 1D of
`.claude/hooks/odin-safety-guard.sh` closes — scoped to `projects/*/.github/workflows/` because the
harness's own root workflows are branch-protection status checks and must keep triggering. With
`push:` or `pull_request:` declared here, that guard refuses **every `git add`, `commit` and `push`
in the whole harness monorepo**, with no opt-out short of editing the hook.

The workflow is a thin wrapper around the same scripts run above, so a green local run means what a
green CI run would. Automatic triggers become correct only if this directory ever stops being a
harness subtree — and it does not, for the reason given above.
