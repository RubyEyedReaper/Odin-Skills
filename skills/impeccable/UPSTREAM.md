# Upstream: `impeccable`

| | |
|---|---|
| Upstream | https://github.com/pbakaus/impeccable |
| License | Apache License 2.0 (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `7b646ba` (2026-08-14) |
| Modified by Odin | **Yes** |

## Changes made by Odin

This statement satisfies Apache License 2.0 §4(b), which requires modified files to carry prominent
notice that they were changed.

1. **Hook working-directory anchoring.** `envProjectDir()` was patched to consult
   `CLAUDE_PROJECT_DIR` before `CURSOR_PROJECT_DIR`, and `hook.mjs` / `hook-admin.mjs` route through
   it instead of raw `process.cwd()`. Upstream's behaviour let hook-local cache and config files
   (`.impeccable/hook.cache.json`) anchor to whatever directory a prior shell command had left the
   session in, rather than to the real project root.

2. **State cwd split from target cwd.** The same leak recurred because `runHook()` re-derived its
   root from `event.cwd`. State resolution is now a separate `resolveStateCwd()`, distinct from the
   resolution of *what was edited*. Files touched: `scripts/hook-lib.mjs`,
   `scripts/hook-before-edit.mjs`.

3. **Added `scripts/hook-lib.test.mjs`** — a regression test covering the two-root behaviour above,
   which upstream has no equivalent of.

4. **Added four reference documents** not present upstream: `reference/brand.md`,
   `reference/codex.md`, `reference/interaction-design.md`, `reference/product.md`.

5. **Script paths adjusted** for the Odin harness layout, and the skill wired as a PostToolUse hook.

## Divergence from current upstream

As of the 2026-08-15 audit this fork is **behind** upstream by roughly 17,000 lines across 74 shared
files, and upstream has added 57 files this fork does not carry — native/iOS/Android adaptation
references, a `degraded/` agent set, `doctor.md`, `craft-floor.md`, and live-setup documentation.

Refreshing this fork is a **merge**, not a copy: the four changes above must be re-applied and
`scripts/hook-lib.test.mjs` must stay green. A blind overwrite reintroduces the cwd-anchoring bug
that took two separate fixes to close.
