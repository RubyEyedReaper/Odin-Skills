# Upstream: `using-superpowers`

| | |
|---|---|
| Upstream | https://github.com/obra/superpowers |
| License | MIT — Copyright (c) 2025 Jesse Vincent (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `b36e082` (2026-08-12) |
| Modified by Odin | **Yes** |

## Changes made by Odin

1. **Activation adapted to a vendored SessionStart hook.** Upstream assumes its own installer wires
   activation; Odin injects this skill's text at session start from
   `.claude/hooks/superpowers-session-start.sh`. The skill body is otherwise upstream's.

2. **Two platform reference files retained** that upstream has since **removed**:
   `references/claude-code-tools.md` and `references/copilot-tools.md`. Both are reachable from the
   injected session-start text, so dropping them breaks the injection rather than merely losing a
   document.

## Divergence from current upstream

Upstream added `references/hermes-tools.md`, which this fork does not carry, and the 2026-08-15 audit
measured +88 lines upstream against −195 lines here across four shared files.

Refreshing needs care in both directions: adopt upstream's edits, but do **not** let the refresh
delete the two retained reference files.
