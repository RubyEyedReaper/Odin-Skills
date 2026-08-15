# Upstream: `verification-before-completion`

| | |
|---|---|
| Upstream | https://github.com/obra/superpowers |
| License | MIT — Copyright (c) 2025 Jesse Vincent (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `b36e082` (2026-08-12) |
| Modified by Odin | **Yes — one added section** |

## Changes made by Odin

A closing **"Relationship to other skills"** section distinguishes this skill from `verification-loop`:
this one is a *gate mindset* — never claim work is done without running a command first — while
`verification-loop` is a structured multi-phase build/type/lint/test/security/diff workflow producing
a formal report. Without the distinction the two skills read as duplicates and the wrong one gets
invoked.

## Divergence from current upstream

Upstream has trimmed the skill: the "Why This Matters" failure-memory list and "The Bottom Line"
section are gone (−25 lines relative to this fork, with no upstream additions).

The overwhelming majority of what looks like local divergence is upstream *deletion*, so a refresh is
nearly a straight adoption — except for the added section above, which a blind copy silently drops.
