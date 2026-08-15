# Changelog

All notable changes to this repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Skill *content* changes originate in the [Odin](https://github.com/RubyEyedReaper/Odin) harness and
arrive here by sync; entries below record what changed in this distribution.

## [Unreleased]

### Added

- `grill-with-docs` joins as the eighth fork (thirteenth member). Upstream ships a 245-byte
  delegation stub carrying `disable-model-invocation: true`; Odin's contract named it in seven
  places while the Skill tool refused to invoke it. Grown into a real doc-verification interview —
  dependency-load assertion, cite-or-flag pass with four verdict labels, ADR output pinned to the
  harness's own tree. See its `UPSTREAM.md`.
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
