---
name: grill-with-docs
description: Use when a plan, design, claim or requirement must be stress-tested against actual documentation and source material rather than against opinion — a requirements interview over a heavy doc or spec corpus, an unfamiliar API or library whose real behaviour is not yet established, a claim that "the docs say" something nobody has read, or a design whose evidence is asserted but not cited. Also use when an interview must leave a paper trail — ADRs and glossary entries — instead of ending in the conversation.
---

# Grill With Docs

## Overview

A relentless interview that treats every claim as unverified until a source is cited. Ordinary
grilling sharpens what *you* think; this sharpens what is *true*, then writes it down.

**Core principle:** an unsourced claim is an open question wearing a confident face.

Two things distinguish this from `grilling` alone:

1. **Every claim under interview is checked against a source** — the documentation, the code, the
   spec, the API's real behaviour — before it is allowed to settle a branch of the design tree.
2. **The session produces artifacts**, not just agreement: decisions land as ADRs, vocabulary lands
   in the glossary. An interview that resolves five forks and records none of them did not happen.

## When to Use

- A plan or design rests on claims about a library, API, protocol, or spec nobody has read end to end
- "The docs say…" / "I think it works like…" / "it should support…" — assertion without citation
- A requirements interview over a heavy document or spec corpus
- Onboarding a domain where the vocabulary is not yet pinned down
- Before committing to an integration whose real behaviour is assumed rather than established

**Not for:** eliciting *preferences* (use `grilling` — there is no source to check a preference
against); exploring intent from scratch (use `brainstorming`); a decision with scorable criteria and
no factual dispute (use `decision-matrix`).

## Step 0: Assert the dependencies loaded — do this first, every time

This skill composes two others. Loading only one produces the worst possible outcome: a plausible
interview with no paper trail, or a paper trail with no rigour. The failure is **silent** — this
step is what makes it loud.

```
REQUIRED SUB-SKILL: grilling         — the frontier/rounds interview mechanics
REQUIRED SUB-SKILL: domain-modeling  — the ADR and glossary formats
```

Invoke both with the Skill tool now. Then confirm, in one line, that you can state from each:

- from `grilling` — what the **frontier** is and why a question can belong to a later round
- from `domain-modeling` — the **ADR format** and what earns a glossary entry

**Cannot state one of them?** Stop and say which skill did not load. Do not proceed on partial
loading — an interview conducted without `domain-modeling` looks exactly like a successful one until
someone goes looking for the decisions.

## The Loop

Run `grilling`'s design tree and rounds, with a verification gate on every answer.

For each frontier question:

1. **Ask it in `grilling`'s format**, with the `➡️` recommended answer.
2. **Cite or flag.** Every factual claim in the question *or* the recommended answer carries a
   source: a file and line, a doc URL and section, or an observed command output. A claim with no
   source is not settled — it is recorded as a **gap** and the branch stays open.
3. **Read the source; do not recall it.** Fetch the doc, open the file, run the command. Facts are
   never the user's job (`grilling` already says this) and they are never memory's job either.
4. **Record the verdict** for each claim, using exactly these four labels:

| Verdict | Meaning | What happens to the branch |
|---|---|---|
| **supported** | source says this, and it was read this session | settles; cite it in the ADR |
| **contradicted** | source says something else | reopens the parent decision — this is the finding worth the session |
| **gap** | no source found or none exists | branch stays open; recorded as an explicit unknown, never as a soft yes |
| **weak** | source is indirect, stale, or inferential (a blog post, an old version, an analogy) | settles only with the weakness named in the ADR |

5. **Recompute the frontier** and go again. A contradicted claim pushes the frontier *backwards* —
   that is the point, not a setback.

Done when the frontier is empty **and** every settled branch cites a source.

## Artifacts — where output goes

| Output | Destination | Format |
|---|---|---|
| A decision the interview settled | `.claude/docs/adr/` | `domain-modeling`'s ADR format |
| Vocabulary the interview pinned down | `CONTEXT.md` at the repo root | `domain-modeling`'s glossary format |
| Findings — every gap, contradiction, and weak source | the plan doc's decision-forks section | one row per finding, with the verdict label |

**The ADR path is `.claude/docs/adr/`, not `docs/adr/`.** `domain-modeling` names the latter, which
in this repository would start a second ADR tree with its own numbering, colliding with the ranges
`.claude/docs/adr/README.md` indexes. When the two disagree, this line wins.

## Unattended sessions

With autonomous posture armed, `grilling`'s wait-points are discharged per
`.claude/rules/common/decision-authority.md` — state each question with its `➡️` answer, adopt it,
and continue. **The verification gate is not discharged.** Nothing about running unattended makes an
unsourced claim more true; if anything, it removes the last human who might have said "wait, is that
right?"

Unattended, a **gap** verdict is recorded as a gap and the plan proceeds under a stated assumption.
It is never quietly upgraded to *supported* because the run needed the branch closed.

## Quick Reference

| When you… | Do |
|---|---|
| Start the skill | Load both dependencies, state one fact from each |
| Hear "the docs say" | Ask which doc, which section; then read it |
| Recall an API's behaviour | Read it or run it — recall is a `weak` source at best |
| Find the source disagrees | Verdict `contradicted`, reopen the parent decision |
| Find no source at all | Verdict `gap`. Not a soft yes |
| Settle a decision | Write the ADR before moving on, to `.claude/docs/adr/` |
| Meet a new domain term | Glossary entry in root `CONTEXT.md` |
| Finish | Frontier empty **and** every settled branch cites something |

## Common Mistakes

- **Citing the plan as evidence for the plan.** The document under interview is not a source for its
  own claims. Neither is an earlier answer in this same session.
- **Treating "the docs don't say otherwise" as support.** Absence of contradiction is a `gap`.
- **Recording only the decisions.** The gaps and contradictions are the higher-value half of the
  output — they are what the next session cannot re-derive.
- **Loading `grilling` and skipping `domain-modeling`** because the interview "is going fine". It
  will go fine right up to the point where nothing was written down.
- **Verifying the easy claims.** The claim nobody wants to check is the one carrying the risk.

## Red Flags

- A branch settled on "I'm fairly confident that…"
- An ADR written with no citation in it
- A `gap` that became `supported` between rounds with no new source read
- The session ended in the conversation, with no file changed
- Only one of the two dependencies was ever loaded
