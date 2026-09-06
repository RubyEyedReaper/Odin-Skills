# Context inventory — the method behind Leek's `context` family

**Origin: the `context-budget` skill** (`.claude/skills/context-budget/SKILL.md`, vendored
from ECC). That skill is the prose statement of this method and remains independently
invocable — it is the right entry point when the question is "how much headroom do I have
and what should I drop". This file is the *executable* statement: what
`scripts/leek.py`'s `check_context` measures, why each threshold is where it is, and what
the numbers mean. Where the two disagree, the scanner is what ran.

## What is actually paid, and when

Four different loading behaviours, and confusing them is how a context audit reaches the
wrong conclusion:

| Component | Paid when | Consequence |
|---|---|---|
| Rule file with no `paths:` frontmatter | Every turn of every session | The only true always-on tax. A file demoted to `paths:` costs nothing until a matching file is touched |
| Project instruction file (`CLAUDE.md`, `AGENTS.md`) | Every turn of every session | Same tax, and usually the largest single one |
| Agent `description` frontmatter | Every dispatch context, for **every** agent in the roster | An agent nobody invokes still costs its description on each fan-out |
| Agent body, skill body | Only when that agent spawns or that skill is invoked | Progressive disclosure works here — weight is real but conditional |
| MCP tool schema | Every turn, per tool | The largest lever on most hosts: a 30-tool server can outweigh every skill combined |

The `@`-imports in `CLAUDE.md` are **not** the loading mechanism for rules — auto-discovery
is, and `paths:` frontmatter is what makes a rule conditional (ADR-0041). An audit that
reads the import list and stops has measured intent rather than cost.

## Estimation

- Prose: `words × 1.3`
- Code-heavy files: `chars / 4`
- MCP: `~500 tokens per tool schema`

Deliberately not a tokenizer. The number exists to rank findings, not to bill anything —
and a scanner that shells out to a tokenizer buys three significant figures of precision it
then spends on a decision that only needed an order of magnitude.

## Thresholds and why

Constants at the top of `scripts/leek.py`, not a config file. Each is set where the cost
starts to matter rather than where it becomes fatal, because a threshold nobody crosses
never fires and a threshold everybody crosses is ignored.

| Constant | Value | Reasoning |
|---|---|---|
| `ALWAYS_ON_RULE_BYTES` | 45 KB | The documented always-on budget for the whole rule set; `.claude/rules/README.md` states the measured figure and the command that re-measures it |
| `RULE_FILE_BYTES` | 8 KB | One rule file large enough that demoting it alone is worth doing |
| `CLAUDE_MD_BYTES` | 32 KB | An instruction file past this is carrying reference material a pointer index should hold |
| `AGENT_DESC_WORDS` | 30 | ECC's measured figure; beyond it the description is documenting rather than triggering |
| `AGENT_FILE_LINES` | 200 | Where an agent definition starts inflating every spawn |
| `SKILL_BODY_LINES` | 400 | Where a skill should be moving detail into `references/` |
| `MCP_SERVER_MAX` | 10 | Above this, schema overhead dominates every other component combined |

## Classification — the three buckets

Every flagged component sorts into one of three, and the bucket is what decides the
remediation:

| Bucket | Test | Action |
|---|---|---|
| **Always needed** | Named in the project instructions, backs an active command, or is required to choose the next action or guard a destructive one | Keep. Its weight is the cost of the harness working |
| **Sometimes needed** | Domain- or language-specific; useful on some sessions | Give it `paths:` frontmatter, or move it behind a skill so progressive disclosure applies |
| **Rarely needed** | No route, overlapping content, or no match to what this repository is | Retire it. Cross-check against `components/skill-never-invoked` before deciding |

The always-on bar, stated once and worth restating here because it is the whole test: a
file earns always-on status only if it is needed **to choose the next action or to guard a
destructive one.** Everything else is conditional.

## Issue patterns this family detects

- **Bloated agent descriptions** — paid on every dispatch regardless of use
- **Heavy agent and skill bodies** — real but conditional; only worth acting on for
  components that actually spawn often
- **Byte-identical skill bodies** — two names, one procedure; route one to the other
- **MCP over-subscription** — especially servers wrapping a CLI already on PATH
- **Always-on rule creep** — the tax that compounds silently, because adding one more file
  never feels like the one that broke the budget

## Cross-checks worth running together

- `context` plus `components/skill-never-invoked`: a heavy skill body with no recorded
  invocation is a retirement candidate, where either finding alone is only a suggestion.
- `context` plus `tokens`: high always-on weight *and* repeated tool output means the
  session is paying twice — once for the fixed cost and again for re-sent history.
- Before adding components: run `--check context`, add the estimated cost of what you plan
  to add, and decide against the total rather than against the delta.
