# Membership runbook — publishing an owned skill to the mirror

`projects/Odin-Skills/` is a **one-way publication** of `.claude/skills/`. The harness is
authoritative; a change made in the mirror is destroyed by the next sync.

Membership is a rule, not a list (`odin-skills:ADR-0003`): every `authored` or `forked` skill is
a member. `skill-provenance-check.sh --membership` is that rule's predicate, and it is why
eleven owned skills that nothing was publishing became visible at once.

## The steps

### 1. Copy the skill into the mirror

```sh
bash projects/Odin-Skills/scripts/sync-from-odin.sh          # copies; harness wins
bash projects/Odin-Skills/scripts/sync-from-odin.sh --check  # reports drift, changes nothing (rc 1 on drift)
```

The sync deliberately **excludes** `UPSTREAM.md`, `LICENSE` and `NOTICE`. Those are the
publication's own artefacts, not the skill's — which is also why the mirror is one of the four
inputs the classifier reads.

### 2. List it in the plugin manifest

`projects/Odin-Skills/.claude-plugin/plugin.json` — every directory on disk must be listed, and
every listed name must exist on disk. `validate-skills.sh` checks both directions.

The manifest `description` carries **no count**. A standing number in prose is wrong the moment
the next skill lands, and `validate-skills.sh` refuses a `docs/PROVENANCE.md` heading that
carries one.

### 3. Document provenance

`projects/Odin-Skills/docs/PROVENANCE.md` needs a row naming the skill in backticks. For a
**fork**, that row also carries the upstream, its licence, and the sha forked from.

### 4. Licence artefacts, for forks only

`validate-skills.sh` refuses:

- an upstream `LICENSE` with no `UPSTREAM.md` stating the local changes;
- an `UPSTREAM.md` with no upstream `LICENSE`;
- an `UPSTREAM.md` declaring no upstream licence and shipping no `NOTICE`.

Where upstream published no licence at all, the `UPSTREAM.md` says so literally and a `NOTICE`
ships beside it. The repository root carries `LICENSE-MIT` and `LICENSE-CC-BY-SA-4.0`; a bare
root `LICENSE` is refused, because one file cannot describe split licensing.

A fork's upstream must also be in `projects/Odin-Skills/scripts/public-repos.txt` — publishing
someone's work under Odin's monorepo is a licensing act, and the allowlist is where that act is
authorised rather than assumed.

### 5. Validate

```sh
bash projects/Odin-Skills/scripts/validate-skills.sh
bash projects/Odin-Skills/scripts/check-doc-links.sh
bash .claude/scripts/skill-provenance-check.sh --membership
```

### 6. Record it

`projects/Odin-Skills/CHANGELOG.md`. Then delete the skill's declared row from
`.claude/docs/skill-provenance.tsv` if it had one — the row was a debt against publication, and
publication is what discharges it.

## What membership does not mean

It does **not** define ownership. That inversion is what harness:RM-0473 removed: a skill is in
the mirror *because* it is owned, and reading it the other way left `factory` — a documented
fork with an `UPSTREAM.md` — protected by nothing but the absence of a vend line.

It is also why `sp_mirror_state` is four-valued. An unpopulated submodule directory in a fresh
clone is not an empty mirror, and a guard that cannot tell those apart protects nothing at
exactly the moment it looks fine.
