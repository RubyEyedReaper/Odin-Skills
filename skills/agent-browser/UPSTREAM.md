# Upstream: `agent-browser`

| | |
|---|---|
| Upstream | https://github.com/vercel-labs/agent-browser |
| License | Apache License 2.0 (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `548b159` (2026-08-10) |
| Modified by Odin | **Yes** |

## Changes made by Odin

This statement satisfies Apache License 2.0 §4(b).

The skill is reduced to an **offline stub**. Upstream's full skill content is authored to be served
by the `agent-browser` CLI itself; vendoring a snapshot of it would go stale against whichever CLI
version is actually installed. The stub keeps the triggering description and delegates the live
content to the CLI at invocation time, so the skill resolves without network access and never
contradicts the installed tool.

## Requirement

The `agent-browser` CLI must be installed for this skill to do anything useful. Without it the stub
resolves and then has nothing to delegate to.

## Divergence from current upstream

The 2026-08-15 audit found a one-line difference against upstream — the frontmatter `description`.
The stub deliberately tracks upstream's description closely, since that string is what decides
whether the skill triggers at all.
