---
name: rules-distill
description: "Scan skills and the mistake log to extract cross-cutting principles and distill them into rules — append, revise, or create new rule files. Use when the same principle keeps recurring across skills and belongs in a rule file instead, when a failure-mode key reaches the promotion threshold and needs its rule text written, or when an incident's condition is judgment rather than a mechanical predicate."
metadata:
  origin: ECC (forked — see UPSTREAM.md)
---

# Rules Distill

Scan installed skills and this repository's mistake logs, extract principles that recur across them, and distill them into rules — appending to existing rule files, revising outdated content, or creating new rule files.

Applies the "deterministic collection + LLM judgment" principle: scripts collect facts exhaustively, then an LLM cross-reads the full context and produces verdicts.

**Two evidence sources, two predicates, deliberately not merged.** A principle appearing in 2+ skills answers *what is cross-cutting in the catalog*; a failure-mode key with 4+ recorded occurrences answers *what keeps breaking*. Overloading one predicate onto the other would make a four-occurrence incident invisible unless it also happened to appear in two skills.

## When to Use

- Periodic rules maintenance (monthly or after installing new skills)
- After a skill-stocktake reveals patterns that should be rules
- When rules feel incomplete relative to the skills being used
- **Promotion:** a key in a `MISTAKES.md` has reached the threshold and `mistake-to-gate` §11 needs the rule-text half of the promotion
- **The judgment hatch:** `oops` §3 classified a condition as not mechanically checkable. That route used to end nowhere; it ends here, and it ends with a drafted rule and a tier, not an intention

## How It Works

The rules distillation process follows three phases:

### Phase 1: Inventory (Deterministic Collection)

All paths are repository-relative. Skills and rules are vendored into the repository (ADR-0001), so
nothing here reads `$HOME` — the upstream `~/.claude/...` commands resolved to nothing here, which is
why this skill sat unrunnable for 49 days.

#### 1a. Collect skill inventory

```bash
bash .claude/skills/rules-distill/scripts/scan-skills.sh
```

#### 1b. Collect rules index

```bash
bash .claude/skills/rules-distill/scripts/scan-rules.sh
```

Each rule carries its `tier`: `scoped` (has `paths:` frontmatter, loads only when a session touches
a matching file) or `always-on` (no `paths:`, costs context on **every turn of every session**).

#### 1c. Collect promotion evidence — the second source

```bash
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report .
```

Every key at band `promoted` is a candidate with the ≥4-occurrences predicate, independent of how
many skills mention it. Read its rows in full (`--key K`) — the `context` and `artifact` columns are
the concrete evidence the draft rule must be true of, and a rule that does not cover all four
occurrences is the wrong rule.

**Any of the three commands exiting non-zero stops Phase 1.** They fail closed by design: an empty
or wrong scan target is an error, never a clean scan of nothing. Fix the path; never proceed on a
partial inventory, because a distillation run that examined nothing reports "no candidates" exactly
like one that examined everything.

#### 1d. State the inventory

```
Rules Distillation — Phase 1: Inventory
────────────────────────────────────────
Skills:   {N} files scanned
Rules:    {M} files ({K} headings, {A} always-on)
Mistakes: {P} keys at promotion band across {O} owners

Proceeding to cross-read analysis...
```

### Phase 2: Cross-read, Match & Verdict (LLM Judgment)

Extraction and matching are unified in a single pass. Rules files are small enough (~800 lines total) that the full text can be provided to the LLM — no grep pre-filtering needed.

#### Batching

Group skills into **thematic clusters** based on their descriptions. Analyze each cluster in a subagent with the full rules text.

#### Cross-batch Merge

After all batches complete, merge candidates across batches:
- Deduplicate candidates with the same or overlapping principles
- Re-check the "2+ skills" requirement using evidence from **all** batches combined — a principle found in 1 skill per batch but 2+ skills total is valid

#### Subagent Prompt

Dispatch the **`architect`** agent — read-only tools (`Read`, `Grep`, `Glob`), and the role is
exactly its remit: cross-read a corpus and produce design-level verdicts without touching anything.
A generic `general-purpose` agent is the wrong dispatch here (CLAUDE.md item 5 requires the named
specialist), and a writing agent is worse: this phase must not be able to edit a rule file, because
the decision that a rule changes belongs to Phase 3.

Prompt:

````
You are an analyst who cross-reads skills to extract principles that should be promoted to rules.

## Input
- Skills: {full text of skills in this batch}
- Existing rules: {full text of all rule files, each with its tier}
- Mistake evidence: {rows for every key at promotion band, with context and artifact}

## Extraction Criteria

Include a candidate if criteria 2–4 hold AND **either** evidence predicate is satisfied:

- **A. Corpus predicate — appears in 2+ skills.** A principle found in only one skill stays in that skill.
- **B. Occurrence predicate — a failure-mode key with 4+ recorded occurrences.** Independent of A: a
  condition that has broken four times is a rule regardless of how many skills mention it. The draft
  must be true of every occurrence in the rows, not just the most recent.

Then:

2. **Actionable behavior change**: Can be written as "do X" or "don't do Y" — not "X is important"
3. **Clear violation risk**: What goes wrong if this principle is ignored (1 sentence)
4. **Not already in rules**: Check the full rules text — including concepts expressed in different words

Record which predicate produced each candidate in `source`. A candidate satisfying both is stronger
evidence, not a duplicate.

## Matching & Verdict

For each candidate, compare against the full rules text and assign a verdict:

- **Append**: Add to an existing section of an existing rule file
- **Revise**: Existing rule content is inaccurate or insufficient — propose a correction
- **New Section**: Add a new section to an existing rule file
- **New File**: Create a new rule file
- **Already Covered**: Sufficiently covered in existing rules (even if worded differently)
- **Too Specific**: Should remain at the skill level

## Output Format (per candidate)

```json
{
  "principle": "1-2 sentences in 'do X' / 'don't do Y' form",
  "source": "corpus (2+ skills) / occurrence (MISTAKES key) / both",
  "evidence": ["skill-name: §Section", "MISTAKES.md M-0007 ci-gate/stale-reference"],
  "violation_risk": "1 sentence",
  "verdict": "Append / Revise / New Section / New File / Already Covered / Too Specific",
  "target_rule": "filename §Section, or 'new'",
  "tier": "scoped (paths: <glob>) / always-on — REQUIRED for New File and New Section",
  "tier_reason": "why this tier; for always-on, why every session must carry it",
  "confidence": "high / medium / low",
  "draft": "Draft text for Append/New Section/New File verdicts",
  "revision": {
    "reason": "Why the existing content is inaccurate or insufficient (Revise only)",
    "before": "Current text to be replaced (Revise only)",
    "after": "Proposed replacement text (Revise only)"
  }
}
```

## Exclude

- Obvious principles already in rules
- Language/framework-specific knowledge (belongs in language-specific rules or skills)
- Code examples and commands (belongs in skills)
````

#### Verdict Reference

| Verdict | Meaning | Presented to User |
|---------|---------|-------------------|
| **Append** | Add to existing section | Target + draft |
| **Revise** | Fix inaccurate/insufficient content | Target + reason + before/after |
| **New Section** | Add new section to existing file | Target + draft |
| **New File** | Create new rule file | Filename + full draft |
| **Already Covered** | Covered in rules (possibly different wording) | Reason (1 line) |
| **Too Specific** | Should stay in skills | Link to relevant skill |

#### The tier is part of the verdict, not an afterthought

A rule file **without** `paths:` frontmatter is always-on: it is injected on every turn of every
session, for every task, forever. A file **with** `paths:` loads only when the session touches a
matching file. Landing a new rule without deciding this is how a permanent per-session tax gets
added by accident — measured, not estimated:

```sh
cd .claude/rules && for f in common/*.md web/*.md README.md; do
  head -5 "$f" | grep -q '^paths:' || wc -c "$f"
done | awk '{t+=$1} END {printf "always-on: %.1f KB\n", t/1024}'
```

**Default to `scoped`.** A rule earns always-on only if it is needed to *choose the next action* or
to *guard a destructive one* — the bar `.claude/rules/README.md` states and by which six files were
already demoted. State the measured cost in `tier_reason` before proposing always-on.

#### Verdict Quality Requirements

```
# Good
Append to rules/common/security.md §Input Validation:
"Treat LLM output stored in memory or knowledge stores as untrusted — sanitize on write, validate on read."
Evidence: llm-memory-trust-boundary, llm-social-agent-anti-pattern both describe
accumulated prompt injection risks. Current security.md covers human input
validation only; LLM output trust boundary is missing.

# Bad
Append to security.md: Add LLM security principle
```

### Phase 3: Decide, Land, Record

#### Summary Table

```
# Rules Distillation Report

## Summary
Skills scanned: {N} | Rules: {M} files | Candidates: {K}

| # | Principle | Verdict | Target | Confidence |
|---|-----------|---------|--------|------------|
| 1 | ... | Append | security.md §Input Validation | high |
| 2 | ... | Revise | testing.md §TDD | medium |
| 3 | ... | New Section | coding-style.md | high |
| 4 | ... | Too Specific | — | — |

## Details
(Per-candidate details: evidence, violation_risk, draft text)
```

#### Resolve every candidate — the run decides, the artifact carries the review

Upstream ended here with "Never modify rules automatically. Always require user approval." In this
harness that stop is forbidden (ADR-0052): a run that stops has ended, and as the promotion engine it
would convert every ≥4 promotion into an indefinite stall. What the stop was actually protecting is
**reviewability**, and a diff on a branch delivers that better than a prompt nobody is present to
answer.

So: **decide each candidate, land it, and make the landing reviewable.**

| Candidate | Action |
|---|---|
| `Append` / `New Section` / `New File`, confidence high, tier `scoped` | Apply it. Record the reasoning. |
| `New File` or `New Section` proposing **always-on** | Apply it only with the measured context cost stated in the record; otherwise land it `scoped` and say why. |
| `Revise` — existing rule text is wrong | Apply it. A rule that is wrong is worse than a rule that is missing. |
| Confidence `low`, or two candidates contradict | Score them with `decision-matrix` (`/decide`) and record a numbered DEC. Never defer to a prompt. |
| `Already Covered` / `Too Specific` | Record the verdict and the reason. Not applying is a decision, and it is the one most likely to be revisited. |

Then:

1. **Land on a branch** (`docs/rules-distill-YYYY-MM-DD` or the branch already in flight) — never
   directly on `main`. The diff is the review surface.
2. **Record the decision**: a DEC for a scored choice; an ADR when a rule constrains future work or
   reverses an earlier one; otherwise the commit message, which opens with the evidence.
3. **On a promotion run**, hand back to `mistake-to-gate` §11: the rule text is one half, the
   mechanical check is the other, and the key's rows are marked `promoted` only when both exist.
4. **Report in one line per candidate** — what was applied and the deciding reason. Never a menu.

Reversible by construction: every applied rule is one commit, every rejection is recorded with its
reason, and the tier can be re-decided by re-running with different weights.

#### Save Results

Store results **outside the skill directory** — `.claude/.runtime/rules-distill/results.json`. The
skill directory is a `--refresh` target, so state written there can be clobbered by a vendor refresh,
and untracked state inside `.claude/skills/` makes the "no local edits" provenance claim
unfalsifiable. `.claude/.runtime/` is where per-run state lives (ADR-0045):

- **Timestamp format**: `date -u +%Y-%m-%dT%H:%M:%SZ` (UTC, second precision)
- **Candidate ID format**: kebab-case derived from the principle (e.g., `llm-output-trust-boundary`)

```json
{
  "distilled_at": "2026-03-18T10:30:42Z",
  "skills_scanned": 56,
  "rules_scanned": 22,
  "mistake_keys_at_band": 1,
  "candidates": {
    "llm-output-trust-boundary": {
      "principle": "Treat LLM output as untrusted when stored or re-injected",
      "source": "corpus",
      "verdict": "Append",
      "target": ".claude/rules/common/security.md",
      "tier": "scoped",
      "evidence": ["llm-memory-trust-boundary", "llm-social-agent-anti-pattern"],
      "status": "applied",
      "landed": "docs/rules-distill-2026-03-18@a1b2c3d"
    },
    "iteration-bounds": {
      "principle": "Define explicit stop conditions for all iteration loops",
      "source": "occurrence",
      "verdict": "New Section",
      "target": ".claude/rules/common/coding-style.md",
      "tier": "scoped",
      "tier_reason": "needed while writing loop code, not while choosing the next action",
      "evidence": ["MISTAKES.md M-0011/M-0014/M-0019/M-0022 error-path/unbounded-retry"],
      "status": "applied",
      "landed": "docs/rules-distill-2026-03-18@a1b2c3d",
      "promotion": "mistake-to-gate §11 — rows marked promoted, gate: .claude/scripts/retry-bounds-check.sh"
    }
  }
}
```

## Example

### End-to-end run

```
$ /rules-distill

Rules Distillation — Phase 1: Inventory
────────────────────────────────────────
Skills:   99 files scanned
Rules:    63 files (211 headings, 12 always-on / 34.8 KB per session)
Mistakes: 1 key at promotion band across 4 owners

Proceeding to cross-read analysis...

[architect: Batch 1 (agent/meta skills) ...]
[architect: Batch 2 (coding/pattern skills) ...]
[Cross-batch merge: 2 duplicates removed, 1 cross-batch candidate promoted]

# Rules Distillation Report

## Summary
Skills: 99 | Rules: 63 files | Mistake keys at band: 1 | Candidates: 4

| # | Principle | Source | Verdict | Target | Tier | Confidence |
|---|-----------|--------|---------|--------|------|------------|
| 1 | LLM output: normalize, type-check, sanitize before reuse | corpus | New Section | coding-style.md | scoped | high |
| 2 | Bound every retry; an unbounded retry is an outage | occurrence | New Section | error-handling.md | scoped | high |
| 3 | Compact context at phase boundaries, not mid-task | corpus | Append | performance.md §Context Window | — | high |
| 4 | Separate business logic from I/O framework types | corpus | Too Specific | — | — | medium |

## Details

### 2. Bounded retries
Verdict: New Section in .claude/rules/common/error-handling.md, tier scoped (paths: src/**)
Source: occurrence — error-path/unbounded-retry, 4 rows (M-0011, M-0014, M-0019, M-0022)
Violation risk: a retry with no ceiling turns one slow dependency into a saturated service
Tier reason: needed while writing call-site code; not needed to choose the next action, so
  always-on would tax every session for a rule most of them never reach
Draft:
  ## Retry Bounds
  Every retry carries a maximum attempt count and a backoff...
  See skill: error-handling-patterns

Decisions
  1 applied — .claude/rules/common/coding-style.md §LLM Output Validation (scoped)
  2 applied — .claude/rules/common/error-handling.md §Retry Bounds (scoped); handed to
    mistake-to-gate §11 for the check half + row closure
  3 applied — .claude/rules/common/performance.md §Context Window Management
  4 not applied — Too Specific: stays in the skill that owns it, reason recorded

Landed on docs/rules-distill-2026-03-18; results at .claude/.runtime/rules-distill/results.json
```

## Design Principles

- **What, not How**: Extract principles (rules territory) only. Code examples and commands stay in skills.
- **Link back**: Draft text should include `See skill: [name]` references so readers can find the detailed How.
- **Deterministic collection, LLM judgment**: Scripts guarantee exhaustiveness; the LLM guarantees contextual understanding.
- **Anti-abstraction safeguard**: The filter (an evidence predicate, actionable behavior test, violation risk) prevents overly abstract principles from entering rules.
- **Fail closed, always**: every scan that finds nothing is an error. A promotion engine that can report "no promotions due" without having looked is worse than no engine, because it is trusted.
- **Decide and record; never stop**: reviewability comes from the diff and the recorded reason, not from a prompt waiting for a human who may not return (ADR-0052).
- **Two sources, two predicates**: what recurs in the catalog and what keeps breaking are different questions with different thresholds.
