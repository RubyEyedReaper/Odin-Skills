# Upstream: `blueprint`

| | |
|---|---|
| Upstream | https://github.com/affaan-m/ECC (originating with `antbotlab/blueprint`) |
| License | MIT — Copyright (c) 2026 Affaan Mustafa (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `c9de8f5` (2026-08-13) |
| Modified by Odin | **Yes — substantially rewritten** |

## Changes made by Odin

Upstream's text described a slash command Odin does not ship, and made no claim a script could check.
The rewrite turns it into an operational procedure with a mechanical gate:

1. **A 5-phase pipeline** with concrete commands, replacing the prose description.
2. **`scripts/plancheck.py`** — a deterministic gate that must pass before construction steps are
   dispatched, with 20 tests in `tests/test_plancheck.py`.
3. **`references/step-brief.md`** — a mandatory cold-start task-brief template, so a step is
   executable by an agent with no prior context.
4. **A plan-mutation protocol** for changing a blueprint mid-flight.
5. **Phase-5 registration** of construction steps as `roadmap` child items, so execution waves stay
   computed from the dependency graph rather than stored (recorded as DEC-0001 in the Odin harness).

## Divergence from current upstream

The 2026-08-15 audit measured +68 lines present upstream and −149 lines present only here. The −149
is this rewrite, not upstream deletions. Refreshing means re-reading upstream for anything worth
adopting, not restoring upstream's text.
