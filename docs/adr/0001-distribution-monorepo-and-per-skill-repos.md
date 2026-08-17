# ADR-0001: Distribution monorepo plus per-skill repositories

## Status

Accepted — 2026-08-17

## Context

The Odin harness vendors 99 skills; it authored 7 of them and substantially modified 10 more. Those
17 are the only ones it can honestly redistribute, and they need to reach users who are not running
Odin.

Two distribution shapes were already in play and had never been reconciled in writing:

- This subtree, `projects/Odin-Skills/`, packages all 17 as one Claude Code plugin — a marketplace
  entry in `.claude-plugin/marketplace.json` and a bundle a user installs with two commands.
- Harness [ADR-0061](../../../../.claude/docs/adr/0061-per-skill-repositories.md) covers publishing
  each skill as its own small public repository (`RubyEyedReaper/skill-<name>`), so a user can take
  one skill without the bundle. `docs/PUBLISHING.md` already describes the `git subtree split`
  mechanics for both.

Three constraints bound any answer:

1. **`.claude/skills/` in the harness is authoritative** (harness
   [ADR-0001](../../../../.claude/docs/adr/0001-vendor-skills-into-repo.md)). Odin commits its skills
   so they survive container resets, so it cannot depend on an external repository to supply them.
   Anything published is therefore downstream of the harness by construction.
2. **The harness cannot drop this subtree after extraction.**
   `.claude/scripts/vendor-skills.sh:57` derives its `protected_set` from
   `projects/Odin-Skills/skills/` — the directory listing *is* the definition of "a skill Odin
   authored or forked", and a vendor refresh consults it to know what not to overwrite. Delete the
   subtree and the next refresh silently clobbers every fork.
3. **Two publish targets must not become two development targets.** A skill that can be edited in
   three places has no source of truth, and the sync script is one-way by design.

## Decision Drivers

- A user must be able to install one skill without taking a 17-skill bundle, and vice versa.
- There must be exactly one place a skill's content is edited.
- Whatever is published must be checkable before it is published, by a script that also runs locally.
- The harness's fork protection must keep working after any extraction.
- Licensing and attribution must survive redistribution in both shapes.

## Considered Options

### Option 1: Monorepo only

Publish `Odin-Skills` as a single repository and plugin; no per-skill repositories.

- **Pros**: One target to publish, validate and license. Simplest possible sync story.
- **Cons**: A user wanting one skill clones seventeen. No per-skill install path, no per-skill issue
  tracker, and no way to point at a single skill as a citable artefact.

### Option 2: Per-skill repositories only

Publish each skill as its own repository; no bundle.

- **Pros**: Maximum granularity; each skill stands alone with its own license and history.
- **Cons**: Loses the plugin/marketplace entry entirely — the primary install path. Seventeen
  repositories to keep in step with no single place that proves they agree. Cross-skill invariants
  (manifest parity, the shared licensing tables, `NOTICE`) have no home.

### Option 3: Monorepo as source, per-skill repositories as read-only publish targets

Keep this subtree as the coordination point; derive each per-skill repository from it by
`git subtree split`, and treat those repositories as outputs.

- **Pros**: Both install paths exist. One place to validate cross-skill invariants before anything
  is published. `git subtree split` carries real commit history into each target, so the published
  repositories are not history-less dumps. Per-skill repositories are cheap to regenerate.
- **Cons**: A contributor who opens a PR against a per-skill repository is in the wrong place, and
  the repository must say so. Publishing is a scripted step someone has to run.

## Decision

**Option 3.** `projects/Odin-Skills/` is the distribution monorepo and the coordination point;
per-skill repositories are **read-only publish targets** derived from it.

Concretely:

- Development of skill *content* happens in the harness's `.claude/skills/` and flows here through
  `scripts/sync-from-odin.sh` only. Development of *packaging* — manifests, licensing, provenance,
  the validator, the publish scripts — is coordinated in `RubyEyedReaper/Odin` under
  `projects/Odin-Skills/`.
- Each per-skill repository is produced by `git subtree split` from this directory. It accepts no
  contributions; its README points back to the harness.
- **The harness keeps this subtree** rather than removing it after extraction, because
  `vendor-skills.sh` derives fork protection from it. Removal is a rejected alternative in harness
  ADR-0061, not a deferred step. The ~3.4 MB of duplication is the price of that guarantee.
- `scripts/validate-skills.sh` gates every publish and must exit 0 first.

## Consequences

**Positive**

- Both install paths work: the bundle via `/plugin install odin-skills`, a single skill via its own
  repository or a directory copy.
- One gate covers everything published, in both shapes, and runs identically locally and in CI.
- The harness's fork protection is unaffected by publishing, because the directory it reads never
  leaves.
- Per-skill repositories are regenerable — a bad publish is re-split, not repaired.

**Negative**

- Three places hold a copy of each skill (harness, this subtree, its per-skill repository), and only
  the first is writable. Anyone editing the wrong one loses the work at the next sync.
- Publishing is manual: `git subtree split` and push, per target, run by a human or a script.
- The duplication is permanent while the subtree stays in the harness.

**Mitigations**

- `scripts/sync-from-odin.sh --check` fails when the mirror has drifted, so a stale copy is loud.
- `INIT.md` states the one-way rule as invariant 1, and `CONTRIBUTING.md` routes changes to the
  harness.
- Each per-skill repository is marked read-only in its own README at publish time.
- `scripts/publish-skill.sh` makes the split reproducible and idempotent rather than hand-run.

## Related

- Harness [ADR-0061](../../../../.claude/docs/adr/0061-per-skill-repositories.md) — the harness-side
  record of per-skill repositories.
- Harness [ADR-0001](../../../../.claude/docs/adr/0001-vendor-skills-into-repo.md) — why
  `.claude/skills/` is authoritative and committed.
- Harness [ADR-0026](../../../../.claude/docs/adr/0026-project-isolation-policy.md) and
  `projects/README.md` — the isolation contract this project satisfies.
- [`../PUBLISHING.md`](../PUBLISHING.md) — the procedure.
- [`../PROVENANCE.md`](../PROVENANCE.md) — per-skill origin, license and local delta.
