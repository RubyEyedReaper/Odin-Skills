# Upstream: `decision-mapping`

| | |
|---|---|
| Upstream | https://github.com/mattpocock/skills — `skills/engineering/wayfinder` (renamed from `decision-mapping`) |
| License | MIT — Copyright (c) 2026 Matt Pocock (see `LICENSE` in this directory) |
| Upstream HEAD last audited | `8b78b53` (2026-08-15) |
| Modified by Odin | **Yes — substantially rewritten** |

## Why this is a fork and not a frozen vendor copy

The vendored copy carried `disable-model-invocation: true`, which makes the Skill tool refuse it —
while five Odin routers sent the agent there (`CLAUDE.md`, `rules/common/decision-authority.md`,
`hooks/odin-skill-gate.sh`, `docs/SKILL-ROUTING.md`, `docs/skill-decision-matrix.md`) and Odin's
decision-authority rule forbids the one escape the refusal message names, namely stopping to ask a
human to run it. The skill was a dead capability: routed by everything, invocable by nothing.

Adopting upstream's rename would not have fixed it — upstream keeps `disable-model-invocation: true`
— so the disposition was scored with the `decision-matrix` engine (fork 71.16, keep-frozen 43.44,
adopt-the-rename vetoed by the freeze's own no-ADR-rewrite constraint) and recorded in the
2026-08-15 decision-suite audit.

## Changes made by Odin

1. **Invocable.** `disable-model-invocation` dropped; `user-invocable: true`, a real `description`
   with trigger phrases, `argument-hint`, and a version added. The frozen copy's description was 109
   bytes and named no trigger.
2. **The map stays a committed markdown file.** Upstream moved the map onto an issue tracker with
   child issues, native blocking edges, and assignment-based claims. Odin has no per-effort tracker
   convention, and the committed file tier is the reset-proof one (ADR-0009), so the file is kept and
   the tracker's semantics are ported onto it: a `Claimed by:` line that must be **committed** before
   work (a claim in a working tree is invisible to the session about to collide with it), explicit
   `Blocked by:` edges, and a `Status:` field that makes an out-of-scope ticket unambiguous.
3. **Ported from upstream:** the named `## Destination`, `## Out of scope` as a scoping act distinct
   from fog, `## Not yet specified` with the sharpness test ("can you state the question now", not
   "can you answer it"), the HITL-vs-AFK distinction on every ticket, the fourth `task` ticket type,
   "refer by name, never a bare id", "plan, don't do", and the map-as-index rule.
4. **Odin-specific additions:** a table of where the map file lives for harness vs project efforts;
   a hand-off table routing scorable tickets to `decision-matrix` and a cleared route to
   `writing-plans` / `superplan` / `blueprint` / `roadmap`; a failure-modes section; and an explicit
   rule for what an unattended run does with a HITL ticket — take the AFK frontier, sharpen the HITL
   question, never invent the human's half.

## Divergence from current upstream

Upstream's tracker-native map is a genuinely different artifact, not a newer version of this one.
Refreshing means re-reading `wayfinder` for ideas worth porting onto the file-based map — as this
fork did in 2026-08 — never restoring upstream's text.
