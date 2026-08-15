# Upstream: `test-driven-development`

| | |
|---|---|
| Upstream | https://github.com/obra/superpowers |
| License | MIT — Copyright (c) 2025 Jesse Vincent (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `b36e082` (2026-08-12) |
| Modified by Odin | **Yes** |

## Changes made by Odin

**`testing-anti-patterns.md` is retained locally.** It is referenced from `SKILL.md` and covers the
failure modes Odin sees most: tests asserting on mock behaviour, test-only code leaking into
production classes, and mocking a dependency without understanding its side effects.

## Divergence from current upstream

Upstream has since replaced roughly 60 lines of "Why Order Matters" prose in `SKILL.md` with a
pointer to a **new** file of its own, `writing-good-tests.md`. That file is *not* the same as this
fork's `testing-anti-patterns.md`.

Refreshing is therefore a real decision, not a copy: adopt upstream's `writing-good-tests.md`, keep
`testing-anti-patterns.md`, or merge the two. Overwriting blindly loses the local file and leaves
`SKILL.md` pointing at nothing.
