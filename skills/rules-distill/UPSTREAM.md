# Upstream: `rules-distill`

| | |
|---|---|
| Upstream | https://github.com/affaan-m/ECC |
| License | As published by the upstream repository; no LICENSE file accompanied the vendored copy, and the blanket ECC row in [`FORKS.md`](../../../FORKS.md) carries the provenance |
| Vendored via | `.claude/scripts/vendor-skills.sh` (ECC skill set) |
| Modified by Odin | **Yes — forked 2026-08-15** (`skills/mistake-system`, harness:RM-0063) |

Refresh protection is **derived** from `projects/Odin-Skills/skills/rules-distill/`, not from a
hand-typed list, so the mirror directory is what keeps `vendor-skills.sh --refresh` from
overwriting these changes. Deleting the mirror re-exposes the fork.

## Why it was forked

The 2026-08-15 mistake-pipeline audit (`.claude/docs/audits/2026-08-15-mistake-system.md`, F9–F16)
found the vendored skill **non-functional in this harness**, which explains why
`.claude/docs/adr/AUDIT-2026-06-27.md:99` recorded "No record of last distill pass" and the finding
stayed open for 49 days: the skill's first documented command could not succeed here.

## Changes made by Odin

1. **Repo-relative paths (F9).** Phase 1 invoked `~/.claude/skills/rules-distill/scripts/*.sh` and
   `scan-rules.sh` defaulted `RULES_DIR` to `$HOME/.claude/rules`. Odin vendors skills and rules
   into the repository (ADR-0001), so both resolved to nothing. Scripts now derive the repository
   root from their own location and default to `.claude/skills` and `.claude/rules`; output paths
   are repo-relative rather than `~/`-prefixed.

2. **Fail-closed scans (F10).** `scan-skills.sh` returned `{"found":true,"count":0}` with exit 0 for
   an empty or wrong directory, and swallowed `find` errors — a distillation run could report
   success having examined nothing. Both scanners now exit non-zero naming the path when the target
   is missing **or** empty, and both fail closed when `jq` is absent instead of treating the absence
   as "nothing found".

3. **The approval stop is replaced (F11).** Upstream ended with "Never modify rules automatically.
   Always require user approval." ADR-0052 forbids that stop in this harness — as the promotion
   engine it would convert every threshold promotion into an indefinite stall. Phase 3 now decides
   each candidate, lands it on a branch, and records the reasoning (DEC/ADR/commit). Reviewability
   comes from the diff, which is what the stop was protecting.

4. **State moved out of the skill directory (F12).** `results.json` was written into
   `.claude/skills/rules-distill/`, a `--refresh` target; it now lives at
   `.claude/.runtime/rules-distill/results.json` (ADR-0045).

5. **A second evidence source (F13).** Upstream's only predicate was corpus frequency ("appears in
   2+ skills"), which answers *what is cross-cutting*, not *what keeps breaking*. Failure-mode keys
   at the promotion threshold in a `MISTAKES.md` now enter as candidates under their own predicate,
   and each candidate records which source produced it. The two are deliberately not merged.

6. **Every new rule carries a tier (F14).** A rule file without `paths:` frontmatter is always-on
   and costs context on every turn of every session. `New File` / `New Section` verdicts now carry
   a required `tier` + `tier_reason`, defaulting to `scoped`, with the measured cost stated before
   always-on is proposed. `scan-rules.sh` reports each existing rule's tier so the decision is made
   against real numbers.

7. **The analyst agent is named (F15).** Upstream dispatched a `general-purpose` agent; the phase
   now dispatches `architect` — read-only tools, design-level verdicts, and unable to edit a rule
   file, which keeps the decision to change one inside Phase 3.

8. **Provenance (F16).** This file, a dedicated `FORKS.md` row, and the mirror at
   `projects/Odin-Skills/skills/rules-distill/`.

9. **A pass leaves committed evidence (ADR-0067, DEC-0008).** Upstream stored `results.json` in the
   skill directory and recorded a pass nowhere else. The fork moved that file to
   `.claude/.runtime/`, which fixed the clobber risk and left a second problem: that directory is
   gitignored, so a pass could run and still leave nothing a later session could find — exactly the
   state `AUDIT-2026-06-27.md:99` recorded for 49 days. §Save Results now appends one row per pass
   to `DISTILLATIONS.md` at the repository root, **including a pass that found nothing**, and adds
   `handed-off` to the verdict vocabulary for a candidate whose target file this run cannot write.

10. **Argument outranks environment in both scanners.** `${RULES_DISTILL_DIR:-${1:-…}}` read the
    environment first, so an exported variable silently retargeted a scan that named its target
    explicitly — the inverse of `.claude/rules/cli/patterns.md`, and the shape of the
    `ci-gate/fixture-reads-ambient-state` key already logged twice in `MISTAKES.md`.

11. **The Phase 2 corpus claim is measured, not inherited.** Upstream said "~800 lines total" and
    told the analyst to carry the full rules text into every batch. This corpus measures 4,905
    lines across 63 files, so the instruction now passes the scanner's rules index and lets each
    analyst read what it needs.

12. **A regression matrix (`.claude/tests/rules-distill-scan.test.sh`).** The fork landed with none,
    so every behaviour above was one edit from reverting silently. Layered per ADR-0068: the cited
    Phase-1 commands are executed rather than grepped for, scan assertions read emitted values and
    distinguish exit 1 from exit 2, and the ledger's shape is asserted.
