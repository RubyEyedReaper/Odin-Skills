# Contributing

## Where a change belongs

This repository is a **mirror**, not the source. `.claude/skills/` in the Odin harness is
authoritative. That harness is a private repository, so it is named here rather than linked.

| Change | Where |
|---|---|
| Skill content — `SKILL.md`, references, skill scripts | Odin first, then `scripts/sync-from-odin.sh` here |
| Packaging — manifests, licensing, validator, CI, docs | Here |
| Adding or removing a member skill | Both, in the same pair of PRs |

A skill edited directly here is overwritten by the next sync, silently. `scripts/sync-from-odin.sh --check`
in CI is what catches it, but only after the fact — so edit upstream.

## Membership bar

A skill belongs here only if Odin **authored** it (no upstream exists) or **forked** it (an upstream
exists and Odin's copy diverges). A vendored skill Odin has not modified does not qualify, however
useful it is.

Adding one means, in the same change:

1. the skill directory under `skills/`
2. a row in `docs/PROVENANCE.md`
3. its path in `.claude-plugin/plugin.json`
4. for a fork: upstream `LICENSE` copied into the skill directory, plus `UPSTREAM.md`
5. for a fork under Apache-2.0: the modification statement in `UPSTREAM.md` and a block in `NOTICE`

`scripts/validate-skills.sh` fails on any of 1–4 being missing. Item 5 is a legal obligation no
script checks — do not skip it.

## Changing a fork

When a fork's local delta changes, update its `UPSTREAM.md` in the same commit. That file is the
record of what Odin altered and, for the Apache-2.0 forks, the notice the license requires. A delta
that drifts from its description is a licensing defect, not a documentation nit.

## Before opening a PR

```sh
scripts/validate-skills.sh
scripts/tests/validate.test.sh
scripts/tests/doc-links.test.sh
scripts/sync-from-odin.sh --check   # only meaningful from inside an Odin checkout
```

All four must pass. `scripts/check-doc-links.sh` runs as check 10 of `validate-skills.sh`, so a
link added to a repository that is not on `scripts/public-repos.txt` is a red gate. This repository
is public; a link to one that is not is a 404 for every visitor. Adding a repository to that
allowlist is a reviewed claim that it is public — see the file's own header.

CI runs `validate-skills.sh` and `validate.test.sh`, so there is no CI-only logic to satisfy. The
doc-link matrix is local-only, for the reason `docs/PUBLISHING.md` gives for this workflow being
`workflow_dispatch`-only.

## Commits

Conventional type prefix (`feat|fix|docs|chore|refactor|test|ci`), one logical change per commit.

## PR checklist

- [ ] Skill content changes landed in the Odin harness first
- [ ] `docs/PROVENANCE.md` matches `skills/` and `.claude-plugin/plugin.json`
- [ ] Forked skills touched in this PR have an updated `UPSTREAM.md`
- [ ] `scripts/validate-skills.sh` passes
- [ ] `scripts/tests/validate.test.sh` passes
- [ ] `scripts/tests/doc-links.test.sh` passes, and no new link points at a non-public repository
- [ ] No skill directory contains a dangling symlink
