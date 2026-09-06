# Provenance

Every skill in this repository is either **authored for Odin** (no upstream exists) or a **fork**
(a real upstream exists and Odin's copy diverges from it). Nothing else ships here: the Odin harness
also vendors third-party skills it has never modified, and redistributing those is not this
repository's job. (84 = the harness's 122 skill directories minus the 38 mirrored here; measured
2026-09-06, not inherited — a count here is a dated measurement, never a standing fact; see
[`adr/0003`](adr/0003-mirror-membership-rule.md).)

`scripts/validate-skills.sh` cross-checks this table against `skills/` and
`.claude-plugin/plugin.json`, so a skill added without a row here fails CI.

## Odin-authored

Prose CC-BY-SA-4.0, code MIT, `Copyright (c) 2026 RubyEyedReaper`.

| Skill | What it does |
|---|---|
| `decision-matrix` | Quantitative weighted-decision engine — weighted-sum / Pugh / TOPSIS / RICE, sensitivity analysis, recorded DEC decisions |
| `endless` | The continuous work loop — three defined checkpoints, and three continuations chosen by predicate: continue inline, fan out, or relay |
| `mistake-to-gate` | Turns a mistake into an always-on mechanical gate, with a matrix proving the gate fires |
| `automate` | What to automate, at which level, and whether an existing automation still earns its keep — six verdicts, six levels, every level naming its approval boundary and a rollback that is never an optional field |
| `campaign` | Several delegated sessions as one unit of work — the manifest holds the plan and never a status, and `close` refuses while any item is unlanded, with a distinct refusal for landedness that could not be determined |
| `improve` | The rung below a gate — a recurring friction no script can decide, changed only with a declared reason and falsifier, and reverted rather than patched when it reddens a gate |
| `learn` | The capture bar for durable knowledge — five confidence rungs, six outcomes, and a `verified_by` command on every record so a later session re-runs the evidence instead of trusting the record |
| `oops` | Root-causes something that should not have happened, then hands off to `mistake-to-gate` for the guard |
| `not-impressed` | Hostile-prior review of machine-generated code — the one verdict it owns is whether the implementation is overdeveloped, and every finding names what to delete |
| `roadmap` | Standing inventory + dependency graph; waves computed from the graph rather than stored |
| `projects` | One operating model for a project subtree — a routing table over the skills that already own each phase, plus the switch ritual and the per-project artifact checklist that nothing owned |
| `workflows` | Lifecycle of a reusable workflow — define, version, supersede, retire; the runner refuses a retired manifest and an empty set |
| `work-loop` | The cycle contract and its resumable ledger — eleven declared fields, six outcomes that describe the iteration and never the session, four mechanical stall predicates |
| `successor` | Fleet-scale delegation to other Claude sessions — a six-element handoff bar, five ordered phases, and coordinator-owned integration |
| `successor-manager` | Ownership of a delegated session and a verdict computed from channels it does not control — daemon health first, then branch movement, then landedness by content |
| `superplan` | Multi-agent deep planning — planner + architect + adversarial reviewer in parallel, synthesized into one approved plan |
| `tidy` | A verdict per path over spent material — it decides and never acts, performs no discovery of its own, and permanently refuses to give a delete verdict for a branch |
| `caveat` | Records a sharp edge the moment it is found — the condition under which it recurs, not the incident, and the safeguard lands before work continues |
| `consistency` | Names the incumbent by path before a variation is written, and records the decision to differ where the next reader will look |
| `gauntlet` | An endless campaign that re-arms instead of ending — a frozen batch so a verdict can be computed, and a frontier recomputed at read time |
| `leek` | Leak and hygiene diagnosis across context, tokens, memory, cache, sessions and isolation — it files findings and never cleans up |
| `mutations` | Records a change whose real effect nobody has checked, with the expected impact written BEFORE the observation and `pending` until one exists |
| `odin-skill-manager` | Where a skill came from and what may be done to it — a class derived on every run from four inputs, mirror membership, upstream freshness and publication; an undetermined answer refuses rather than guessing |
| `off-topic` | A committed checkpoint for work displaced mid-run — the displacement edge and the resume condition, never a copy of state another file owns |
| `out-of-scope` | Fix it now or file it — six weighted dimensions through the decision-matrix engine, where a near-tie defers and a deferral carries its own score |
| `revive` | Brings a stopped fleet back with no human present — a committed manifest holding the assignment and a not-before instant, five preconditions checked in order |
| `s2s` | Session-to-session reporting — the deliverable is a durable path, the message is a pointer to it, and an orphan's terminal is bounded on narration |
| `status` | The four controls a human has over a running fleet — a report computed at read time, quiesce rather than freeze, a timed resume, and stop-for-handoff |

## Forks

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
| `factory` | [coleam00/skills](https://github.com/coleam00/skills) | MIT | `ecef6ff` | Upstream's mandatory `AskUserQuestion` interview replaced by computed rounds that adopt their own recommendation and record it (ADR-0052), plus four portability repairs — an absolute path to the author's workstation, two bare `python` invocations, and a fixture inheriting the host's `init.defaultBranch`; the runner suite went 20/56 to 56/56 and the audit suite from crash to 12/12 |

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
