# Changelog

All notable changes to this repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Skill *content* changes originate in the [Odin](https://github.com/RubyEyedReaper/Odin) harness and
arrive here by sync; entries below record what changed in this distribution.

## [Unreleased]

### Fixed

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
