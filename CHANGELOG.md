# Changelog

All notable changes to this repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Skill *content* changes originate in the [Odin](https://github.com/RubyEyedReaper/Odin) harness and
arrive here by sync; entries below record what changed in this distribution.

## [Unreleased]

### Changed — first publish of the monorepo

- **This repository is published at <https://github.com/RubyEyedReaper/Odin-Skills>**
  (`harness:RM-0073`), public, first-push sha `aa75b29e9c05b7e0be83c9e6155396644d4c3fb8`, 21 commits
  on `main`. The history was carried by `git subtree split -P projects/Odin-Skills` taken from the
  harness's `origin/main`, not by a fresh `git init` and a squash: the fork `UPSTREAM.md` files cite
  commits that only exist in that history, and splitting from `origin/main` guarantees the published
  tree contains only merged work.
- **The subtree stays in the Odin harness.** `docs/PUBLISHING.md` lists removing
  `projects/Odin-Skills/` after the first push as an optional step; it was deliberately not taken,
  because the harness's `.claude/scripts/vendor-skills.sh` derives its refresh-protection list from
  `projects/Odin-Skills/skills/`, and deleting the mirror would re-expose every fork to `--refresh`.
  Sync direction remains one-way, Odin → Odin-Skills.
- **No tag was pushed.** `v0.1.0` is deferred on purpose: the published tree still contains
  documentation describing this project as unpublished, and tagging now would make that text the
  content of the release. The tag belongs to the change that corrects those docs.

### Added — `scripts/publish-skill.sh`

- **`scripts/publish-skill.sh`** — publishes one skill as its own repository,
  `<owner>/skill-<name>`, so a user can take a single skill without the bundle. A `git subtree
  split` rather than a fresh `git init`, so the published repository carries the real history the
  fork `UPSTREAM.md` files depend on. Three things it refuses to guess: the subtree prefix is
  computed **repository-root-relative** (`git subtree` runs `cd_to_toplevel` before reading `-P`, so
  a `$ROOT`-relative prefix splits nothing and pushes an empty repository); the licence artefacts
  are selected by skill class and a fork with neither an upstream `LICENSE` nor a declared-absence
  `NOTICE` is **refused before any network call**; and a rerun clones the existing repository and
  pushes only a real change, because a second `subtree split` cannot fast-forward the first push and
  force-pushing is forbidden. `--dry-run` prints every git and gh command and touches no network;
  `--verify` diffs the published tree against the local skill directory, ignoring only the files the
  script itself writes.
- **`scripts/tests/publish-skill.test.sh`** — 31 cases over every decision made before the network:
  name validation, the repo-root-relative prefix, the landing page, licence selection for all four
  classes, create-versus-update mode, and the dry run's inertness. `git` and `gh` are stubbed earlier
  on `PATH` for the whole suite — the `gh` stub only logs, the `git` stub passes read-only
  subcommands through and refuses clone/push/subtree — so a case that reached GitHub would fail
  rather than create a public repository.

### Fixed

- **The publishing gate rejected the one fork whose upstream published no license**
  (`harness:RM-0070`). `scripts/validate-skills.sh` check 6 required every skill carrying an
  `UPSTREAM.md` to also ship an upstream `LICENSE`, which `rules-distill` cannot — no LICENSE
  accompanied the vendored ECC copy, as `docs/PROVENANCE.md` already recorded. The check and the
  ledger disagreed, and the check gates publication. A fork may now declare the absence in its
  `UPSTREAM.md` (the literal string `no LICENSE file accompanied`) and substantiate it with a sibling
  `NOTICE`; an ordinary fork still must ship its license, and a `NOTICE` without the declaration is
  still a failure. `scripts/sync-from-odin.sh` learns `NOTICE` as this repository's packaging
  alongside `UPSTREAM.md` and `LICENSE` — without that the next sync deletes the file and silently
  re-reddens the gate. Adds `skills/rules-distill/NOTICE`, the three upstream rows the root `NOTICE`
  lacked (`grill-with-docs`, `decision-mapping`, `rules-distill`), and replaces the inherited "86
  unmodified vendored skills" figure with the measured 82. Suite 16 → 19 cases.
- **`README.md` was false in six places** (`harness:RM-0071`), and this tree is about to be
  published, so each one was about to become public. The counts predated four skills: it described 5
  authored and 8 forked inside a harness vendoring 98 with 85 untouched. Measured from disk, the
  figures are **17 owned (7 authored, 10 forked), 99 vendored in the harness, 82 untouched** — the
  commands agreed with the expected values, and `harness-audit.sh` independently reports 99 skills.
  Corrected: the opening paragraph, the "Odin vendors …" sentence, and both "What's in it" lists,
  which omitted `endless`, `successor`, `grill-with-docs` and `rules-distill`.
- **The licensing table omitted three forks** — `grill-with-docs`, `decision-mapping` and
  `rules-distill`. The first two are MIT upstream; `rules-distill` is the one fork whose upstream
  shipped no `LICENSE`, which the table and the paragraph beneath it now state, rather than implying
  every fork ships one.
- **The runtime-dependency table said "Three want something present" above four rows**, and was also
  missing two: `roadmap` and `mistake-to-gate` both ship `python3` scripts. Now six rows and a
  matching count.
- **`README.md:77` claimed "CI runs `--check`, so a stale mirror fails the build"** — it does not.
  `.github/workflows/validate.yml` is `workflow_dispatch`-only and must stay that way: an automatic
  trigger under `projects/*/.github/workflows/` trips Layer 1D of the harness safety guard and
  blocks every git write in the whole monorepo. Replaced with what is actually true, including that
  the drift check is only meaningful from inside a harness checkout.
- **`blueprint`'s `plancheck` accepts a fenced shell block as verification** (synced from the
  harness, `harness:RM-0037`). The hint pattern for an opening `bash` fence was matched against the
  fence-stripped task body, so it could never fire: a plan whose every task carried a runnable shell
  block was reported as having no verification, and the workaround was a prose `Verify:` line — the
  weak form the gate exists to discourage. Now its own `SHELL_FENCE_RE`, matched against the task's
  raw lines; the other three checks keep reading the stripped body, so a placeholder inside an
  illustrative code block is still not a finding. Suite 20 → 22 tests.
- **`docs/PROVENANCE.md`'s fork count was one low** — the heading said `Forks (9)` over ten rows,
  since `decision-mapping` was forked. `plugin.json` and the skill count were already right, so
  nothing was missing; only the heading disagreed with the table beneath it.
- **Unresolved merge-conflict markers in `.claude-plugin/plugin.json` and this file**, landed by
  `59893194` (the `decision-mapping` fork) and present on `main` since. The manifest was therefore
  not valid JSON, which is why `scripts/validate-skills.sh` reported *every* skill as "on disk but
  not listed in plugin.json" — the parse yielded nothing, so nothing matched. Both hunks were
  additive; both sides are kept.

### Changed

- **`roadmap` and `superplan` synced from the harness refinement pass** (2026-08-15). `superplan`'s
  plan template now satisfies all four criteria of Odin's plan-depth standard (process skills
  named, recorded scope decision, ≥3 decision forks, done criteria naming a runnable check), its
  task list carries dependencies and is gated by `plancheck`, its approval step is conditional on
  autonomous posture rather than an unconditional human stop, and its adversarial role dispatches a
  purpose-built `plan-adversary` agent instead of overriding `code-reviewer`. `roadmap` accepts
  `prioritize --export`, resolves `bootstrap --from` against `--root` and fails when no source is
  readable, takes a starter-surface profile (`web` default, `library` added), documents `init`, and
  distinguishes an empty roadmap from a fully blocked one. Engine suite 201 → 218 tests.
  **Note for standalone users:** `superplan` references `plan-adversary`, which lives in the Odin
  harness's `.claude/agents/` and is not part of this plugin — substitute your own critique agent.

### Added

- **This project now satisfies the `projects/` isolation contract** (`harness:RM-0071`). It had a
  CHANGELOG and docs but no `INIT.md`, no ADR sequence and no roadmap, which the harness audit
  flagged as F11/R16. Added:
  - **`INIT.md`** — purpose, scope (in: packaging, licensing, provenance, the validator, the sync
    and publish scripts; out: authoring skill content, which happens in the harness's
    `.claude/skills/` and arrives here only through `scripts/sync-from-odin.sh`), five invariants,
    a layout table, and the gate commands.
  - **`docs/adr/0001-distribution-monorepo-and-per-skill-repos.md`** plus its index — the
    distribution model recorded as this project's own ADR-0001: the monorepo is the coordination
    point, per-skill repositories are read-only publish targets derived from it by `git subtree
    split`, and the harness keeps this subtree rather than removing it after extraction because
    `.claude/scripts/vendor-skills.sh:57` derives its fork-protection set from
    `projects/Odin-Skills/skills/`. Ids here are this project's own sequence, never the harness's
    (harness ADR-0050).
  - **`docs/roadmap/roadmap.json` and the rendered `ROADMAP.md`**, scope `odin-skills`, seeded with
    three items: publish the v0.1.0 tag, give the published repo automatic CI without tripping the
    safety guard's Layer 1D, and decide whether a per-skill repo carries the plugin manifest or the
    bare skill directory. Generated by the roadmap engine and never hand-written. `--surface-sweep`
    was deliberately not passed: the `web` profile's login/signup/FAQ surfaces do not exist in a
    skills distribution repository, and the `library` profile's items are already covered by
    `README.md`, this file, `CONTRIBUTING.md` and the validator.

- **`endless` joins as the seventh authored skill (seventeenth member).** The continuous work loop:
  three defined checkpoints — item landed, hard external blocker recorded, or context past ~half the
  ceiling — and exactly three continuations, chosen by predicates in a fixed order rather than by
  judgment at turn thirty: relay on context, fan out when the dependency graph puts two or more items
  in one layer *and* their surfaces do not collide, otherwise continue inline. What it rules out
  matters as much: in-scope work left by choice, a plan written but unexecuted, and a branch green but
  unpushed are not checkpoints. Replaces the vendored ECC `autonomous-loops` skill, which described
  external-process loop shapes (`claude -p` pipelines, RFC-driven DAG orchestration) rather than the
  single-session loop this one governs.
  **Note for standalone users:** the skill cites harness-internal surfaces —
  `.claude/docs/autonomous-loop-standard.md` for phase → skill, the `/autoloop` command,
  `scripts/odin-autonomous.sh` for unattended posture, and the `roadmap`, `successor` and `oops`
  skills. The checkpoint and continuation semantics stand alone; the phase pointers assume Odin's
  layout.
- **`successor` joins as the sixth authored skill (sixteenth member).** Fleet-scale delegation to
  other Claude sessions: a six-element handoff bar (skill set, task and desired outcome, current
  context, open questions and dependencies, an explicit `edit only:` authorization scope, and the
  standing invariants restated verbatim), five ordered phases — provision, launch, monitor,
  integrate, teardown — and a copyable handoff template. Workers never merge; integration is
  serialized and coordinator-owned, gated on the **merged** result rather than the branch. Rationale
  and the failure modes it encodes: Odin's ADR-0059.
  **Note for standalone users:** the skill's launch and monitor phases call the Odin harness's
  `.claude/scripts/odin-relay.sh` and the `claude agents` session commands; the handoff bar and the
  phase discipline apply anywhere, the exact commands do not.
- `rules-distill` recorded as the ninth fork. It has shipped here since the 2026-08-15 mistake-system
  fork (the mirror directory is what protects it from `vendor-skills.sh --refresh`) but never had a
  manifest entry or a `PROVENANCE.md` row.
- `grill-with-docs` joins as a fork (thirteenth member at the time). Upstream ships a 245-byte
  delegation stub carrying `disable-model-invocation: true`; Odin's contract named it in seven
  places while the Skill tool refused to invoke it. Grown into a real doc-verification interview —
  dependency-load assertion, cite-or-flag pass with four verdict labels, ADR output pinned to the
  harness's own tree. See its `UPSTREAM.md`.
- `decision-mapping` joins as a fork (upstream `mattpocock/skills`, renamed `wayfinder`
  there). Odin forked it because the vendored copy carried `disable-model-invocation: true` while
  five harness routers pointed at it — routed by everything, invocable by nothing — and upstream
  keeps that flag. Odin's copy drops it and ports upstream's Destination / Out-of-scope /
  Not-yet-specified sections, HITL-vs-AFK ticket typing and claim-before-work onto a committed
  markdown map rather than an issue tracker.
- Initial repository: the 12 skills Odin authored (5) or forked (7), packaged as a single
  Claude Code plugin with a marketplace manifest.
- Split licensing — CC-BY-SA-4.0 for authored prose, MIT for code, upstream licenses preserved
  in-place for the seven forks, with `NOTICE` and per-fork `UPSTREAM.md` attribution. Apache-2.0
  §4(b) modification statements for `impeccable` and `agent-browser`.
- `scripts/validate-skills.sh` — frontmatter validity, `name`-to-directory match, manifest parity in
  both directions, licensing presence, provenance coverage, dangling symlinks, orphaned references.
- `scripts/tests/validate.test.sh` — one fixture per check, each proving the check actually fires.
- `scripts/sync-from-odin.sh` — one-way mirror from `.claude/skills/`, with `--check` drift mode.
- `.github/workflows/validate.yml` — thin wrapper around the two scripts.
- `docs/PROVENANCE.md`, `docs/PUBLISHING.md`.
