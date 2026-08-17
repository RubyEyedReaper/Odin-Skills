# Provenance

Every skill in this repository is either **authored for Odin** (no upstream exists) or a **fork**
(a real upstream exists and Odin's copy diverges from it). Nothing else ships here: the Odin harness
also vendors 82 third-party skills it has never modified, and redistributing those is not this
repository's job. (82 = the harness's 99 skill directories minus the 17 mirrored here; measured
2026-08-17, not inherited.)

`scripts/validate-skills.sh` cross-checks this table against `skills/` and
`.claude-plugin/plugin.json`, so a skill added without a row here fails CI.

## Odin-authored (7)

Prose CC-BY-SA-4.0, code MIT, `Copyright (c) 2026 RubyEyedReaper`.

| Skill | What it does |
|---|---|
| `decision-matrix` | Quantitative weighted-decision engine — weighted-sum / Pugh / TOPSIS / RICE, sensitivity analysis, recorded DEC decisions |
| `endless` | The continuous work loop — three defined checkpoints, and three continuations chosen by predicate: continue inline, fan out, or relay |
| `mistake-to-gate` | Turns a mistake into an always-on mechanical gate, with a matrix proving the gate fires |
| `oops` | Root-causes something that should not have happened, then hands off to `mistake-to-gate` for the guard |
| `roadmap` | Standing inventory + dependency graph; waves computed from the graph rather than stored |
| `successor` | Fleet-scale delegation to other Claude sessions — a six-element handoff bar, five ordered phases, and coordinator-owned integration |
| `superplan` | Multi-agent deep planning — planner + architect + adversarial reviewer in parallel, synthesized into one approved plan |

## Forks (10)

Each keeps its upstream license, shipped as `LICENSE` inside the skill directory, with the local
delta stated in that directory's `UPSTREAM.md`. One upstream published no LICENSE file at all
(`rules-distill`); that fork declares the absence in its `UPSTREAM.md` and ships a `NOTICE` instead —
see the decision below. Upstream HEADs are those audited on 2026-08-15
(`.claude/docs/skills-outdated.md` in the Odin harness repo).

| Skill | Upstream | License | Upstream HEAD | Local delta |
|---|---|---|---|---|
| `impeccable` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 | `7b646ba` | Hook cwd anchoring split into `envProjectDir()` / `resolveStateCwd()` so hook state stops following session drift; local `scripts/hook-lib.test.mjs`; four extra reference docs |
| `blueprint` | [affaan-m/ECC](https://github.com/affaan-m/ECC) (orig. antbotlab/blueprint) | MIT | `c9de8f5` | Rewritten as an operational procedure: 5-phase pipeline, `scripts/plancheck.py` + 20 tests, `references/step-brief.md`, phase-5 registration of steps as roadmap children |
| `grill-with-docs` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | `8b78b53` | Upstream is a 245-byte delegation stub the agent was forbidden to invoke; grown into a real body — dependency-load assertion, cite-or-flag verification pass with four verdict labels, ADR output pinned to `.claude/docs/adr/`, `disable-model-invocation` removed |
| `handoff` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | `8b78b53` | Rewritten around Odin session/memory internals — `active-mem-class`, `mem_class` vocabulary, memory-guard interaction, `project_id`/`plan_file` frontmatter |
| `using-superpowers` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | `b36e082` | Activation adapted to a vendored SessionStart hook; keeps `references/claude-code-tools.md` and `references/copilot-tools.md`, which upstream has since removed |
| `test-driven-development` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | `b36e082` | Merge resolved 2026-08-15: upstream's `writing-good-tests.md` adopted verbatim and `testing-anti-patterns.md` retired; five Common-Rationalizations rows keep their one-line cells where upstream expanded them; Red Flags cross-references the harness's own skipped-RED recovery rule |
| `verification-before-completion` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | `b36e082` | Adds a closing section distinguishing this gate mindset from the multi-phase `verification-loop` skill |
| `agent-browser` | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Apache-2.0 | `548b159` | Reduced to an offline stub that delegates live content to the `agent-browser` CLI, so the skill resolves without network |
| `rules-distill` | [affaan-m/ECC](https://github.com/affaan-m/ECC) | As published upstream — no LICENSE accompanied the vendored copy; the blanket ECC row in Odin's `FORKS.md` carries the provenance | not pinned (see the skill's `UPSTREAM.md`) | Non-functional as vendored: paths resolved against `~/.claude/`, and an empty scan exited 0 having examined nothing. Fork makes every path repo-relative, makes an empty scan non-zero, replaces the human-approval stop with a recorded decision plus a branch artifact, moves `results.json` into `.claude/.runtime/`, adds `MISTAKES.md` keys at the promotion threshold as a second evidence source, and requires an always-on-vs-`paths:` tier on every new-rule verdict |
| `decision-mapping` | [mattpocock/skills](https://github.com/mattpocock/skills) (upstream `wayfinder`) | MIT | `8b78b53` | Made invocable — upstream's `disable-model-invocation` dropped, real description and triggers added. Keeps a committed markdown map instead of upstream's issue-tracker map; ports Destination / Out-of-scope / Not-yet-specified, HITL-vs-AFK ticket typing, the `task` type, and claim-before-work (with the claim required to be committed) |

### Decision — `rules-distill` ships a NOTICE where no upstream LICENSE exists (2026-08-17)

No LICENSE file accompanied the vendored ECC copy of `rules-distill`, so the fork cannot satisfy the
ordinary rule that every fork ships its upstream license, and inventing one would assert a grant
nobody made. `scripts/validate-skills.sh` check 6 now accepts a **declared absence**: an `UPSTREAM.md`
containing the literal string `no LICENSE file accompanied`, plus a sibling `NOTICE` carrying the
provenance. Both artefacts are required — a declaration with no `NOTICE` fails, and a `NOTICE` with no
declaration still fails, so an ordinary fork cannot substitute one for the license it does have.
`scripts/sync-from-odin.sh` now treats `NOTICE` as this repository's packaging alongside `UPSTREAM.md`
and `LICENSE`; without that it would delete the file on the next sync and silently re-redden the gate.

Rejected: exempting the skill in this file's prose. That keys an exemption on text the check never
reads, so the ledger and the gate would go on disagreeing — which is the defect being fixed here, not
a fix for it. Harness item `harness:RM-0070`.

## Not included, and why

| Excluded | Reason |
|---|---|
| The 82 unmodified vendored skills | Not owned, not forked — redistributing them is a different repository with a different licensing story |
| Skills refreshed against upstream | This repository mirrors Odin's current local content; it is not where upstream refreshes happen |

## Source of truth

`.claude/skills/` **in the Odin harness repo** is authoritative. This repository is a published
mirror. `scripts/sync-from-odin.sh` copies one way only, and `--check` fails on drift so a stale
mirror is caught by CI rather than discovered by an installer.
