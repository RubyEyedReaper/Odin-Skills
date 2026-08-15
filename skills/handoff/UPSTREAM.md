# Upstream: `handoff`

| | |
|---|---|
| Upstream | https://github.com/mattpocock/skills |
| License | MIT — Copyright (c) 2026 Matt Pocock (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `8b78b53` (2026-08-13) |
| Modified by Odin | **Yes — substantially rewritten** |

## Changes made by Odin

The skill is rewritten around the Odin harness's session and memory internals, which upstream has no
concept of:

1. **Session-state integration** — the handoff reads the state written by
   `.claude/hooks/odin-project-context.sh`, including `active-mem-class`.
2. **Memory-class vocabulary** — `mem_class` uses the exact terms defined by the harness's memory
   standard, and cross-tier writes are fail-closed by `.claude/hooks/odin-memory-guard.sh`.
3. **Structured frontmatter** — a `project_id` / `plan_file` block identifying which project subtree
   and which plan document the handed-off work belongs to.
4. **Durable-tier routing** — facts that belong in the committed file tier are written there and
   referenced, rather than carried in the handoff body.

## Note on the harness fork ledger

This fork went undeclared for a period: the Odin harness's `FORKS.md` recorded the whole
`mattpocock/skills` upstream as carrying no local edits. The 2026-08-15 audit found this skill
rewritten, and the ledger was corrected in the same change that created this repository.

## Divergence from current upstream

Upstream has since added `agents/openai.yaml` (Codex metadata) to every skill, which this fork does
not carry. The audit measured +5 lines upstream and −54 lines here; the −54 is this rewrite.
