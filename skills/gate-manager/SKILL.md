---
name: gate-manager
description: Use when a finding must become something durable and the question is what — a mechanical gate, a review criterion, or a recorded residue. Fires on "should this be a gate", "turn this into a check", "promote this mistake", "what enforces this", "which gate owns that", "where did this gate come from", "do we have too many gates", and when a Leek, Caveat, Issue, Oops, Mistake, Learn or Mutation record is being converted into enforcement. Also when a gate is suspected of being about one project rather than about the harness.
metadata:
  origin: Odin
artifact: .claude/docs/gate-registry.tsv
---

# gate-manager — what a finding becomes, and where every gate came from

> **Voice (ADR-0011).** Prose to human stays Odin. A registry row and a DEC record are
> **deliverables**: normal English, because a reader three months from now acts on them.

## What this is not for

Two things sit either side of this skill, and it owns neither.

| The task | Its owner | Why not this skill |
|---|---|---|
| Root-causing an incident and writing the `MISTAKES.md` row | `oops` | The incident half. This skill starts once a record exists. |
| The mistake → gate **procedure**: threshold 4, the repo-state predicate, the promotion ritual | `mistake-to-gate` §11 | Fully owned there, and re-implementing it is out of scope by the plan's own recorded decision. This skill decides *whether* a finding is gate-shaped at all; that one performs the promotion once it is. |
| Is every matrix in `.claude/tests/` actually stepped | `gate-wiring.test.sh` | A wiring question. |
| Is every stepped gate owned by a matrix, and every arm driven | `matrix-coverage-check.sh` | A coverage question. |
| Does a rule's normative statement name a detector | `ci/rule-enforcement.md` | The rule half. |
| Distilling accumulated patterns into rule text | `rules-distill` | The other half of a promotion, and forked. |

**The two things this skill owns:**

1. **The decision** — a finding becomes a **gate**, a **review criterion**, or a **recorded
   residue**. Exactly three, never a fourth.
2. **The inventory** — every gate this repository runs can say where it came from, and no harness
   gate is about one project.

## The inventory

```sh
bash .claude/scripts/gate-registry-check.sh .
```

| Exit | Means |
|---|---|
| 0 | every stepped gate answers for itself |
| 1 | a gate with no provenance, a redundant row, an orphan row, or project bias |
| 2 | could not look — no gate list, no registry, or a gate list naming no gate |

**Derived, not typed — which is the only reason an aggregate gate is legitimate here.**
`one-implementation-check.sh:12-19` records four prior aggregate-gate proposals (M-0065, M-0091,
M-0105, M-0110), every one refused as `ci-gate/policy-copied-into-a-second-place`, and names the
single condition under which an aggregate is allowed: **a declared vocabulary, not an inferred one.**

So what is declared in `.claude/docs/gate-registry.tsv` is the **source vocabulary** — the evidence
channels a gate may have come from. The **gate list is never declared**: it is read from
`ci-local.sh`'s own `step ` lines, because a second copy of that list would agree with the real one
right up until they diverged, which is the moment the check was for.

A gate's source is derived from its own **leading comment block**. A row exists only where
derivation returns nothing, and the checker **refuses a row whose source it could have derived** —
which is what stops the file growing into the hand-kept list it exists to avoid. Same rule, same
sentence, as `skill-provenance.tsv`: a row is a debt, not a record.

### Where provenance lives, and the two ways a scanner gets it wrong

Both happened while this gate was being built, and each is now a matrix case.

**Reading too little.** The header scan first ended at the first non-comment line, so the
`# shellcheck` directive and `. lib/git-env.sh` source that open many gates truncated the block —
and eight gates citing their evidence in full were reported as citing nothing. Confident, specific,
and about the scanner.

**Reading too much.** Scanning the whole file would derive `roadmap-command-doc-test.sh` from a
`harness:RM-0102` at line 189, inside a case's explanation of what a *later* check covers. That is
not provenance. The block boundary costs one registry row and is worth it; the fix for that row is
to move the citation into the header, not to widen the scan.

### Non-project bias is mechanical

No `harness` gate may declare a `projects/<slug>` boundary, and the checker refuses one. A gate that
*lives* in a project may declare that project — a project owns its own gate list (ADR-0026); the
rule is about the harness reaching in, not about a project owning its own.

When the harness genuinely needs to know a project's vocabulary, the shipped pattern is
`odin-hardcode-guard.sh`'s: the project declares its own nouns in its own manifest and the harness
reads them. A clean scan with no manifest reads *unconfigured*, never *clean*.

## The decision

Seven evidence channels feed this, and the arithmetic is `decision-matrix`'s — this skill contributes
the dimensions and the three outcomes, never a scoring engine of its own. Full form, with the
dimensions and what disqualifies an option outright:
[references/promotion-decision.md](references/promotion-decision.md).

| Outcome | When | What lands |
|---|---|---|
| **Gate** | the finding is a **repository-state predicate** — a command can decide it against the tree, with no judgment | a checker, a matrix seen red once, a step line, a registry answer |
| **Review criterion** | it is decidable but only by a reader | a normative statement in the owning rule file, naming that it has no detector (`ci/rule-enforcement.md` § Three Honest Outcomes) |
| **Recorded residue** | it is real and neither of the above reaches it | a stated residue in the nearest gate's header or rule, saying what was measured and when |

**There is no fourth outcome, and "we'll gate it later" is not one of them.** A deferral with no
record is the finding evaporating; if it is worth deferring it is worth a residue that says so.

### The disqualifier that catches most proposals

**A gate must key on the thing, never on a correlate** (`mistake-to-gate` §3). A count of files is
not a statement that the suite covers them; a mention in a comment is not a wiring; a config key is
not the behaviour it configures (`ci/testing.md` § Assert Outcomes, Not Intent). A proposal that
keys on a correlate is not a gate that needs tightening — it is a **review criterion** wearing a
gate's clothes, and routing it as one is the whole point of having three outcomes.

### Measure the hit rate before writing the detector

A check that fires on everything is a false positive, and one that can never fire is decoration.
Run the candidate predicate over the real population **before** building it, and record both
numbers. Two examples from this campaign, both kept and both reported honestly:

- the rival-store filename arm of `todo-store-check.sh` matched **zero** files, and says so on a
  passing run rather than implying it checked something;
- the stale-claim detector that produced finding D had a **10%** hit rate over the population that
  could carry it — one contradicted claim in ten skills citing a roadmap id — which is a detector,
  not noise.

## Procedure

1. **Name the record.** `M-`, `C-`, `RM-`, `ADR-`, `DEC-`, `#NNN`, or a `leek` / `learn` / `improve`
   / `mutations` finding. A finding with no record is `oops`'s or `caveat`'s work first — this skill
   does not open the ledger, it reads it.
2. **Ask whether a command can decide it** against the repository as it stands. If the answer needs
   a reader, stop: it is a review criterion, and saying so is the deliverable.
3. **Measure the hit rate** over the real population before writing anything.
4. **Score it** — `decision-matrix` (`/decide`), dimensions in the reference, recorded DEC.
5. **Land what the outcome names**, and put the record's id in the **gate's own header** so the
   registry derives it and no row is needed.
6. **Run the inventory.** `gate-registry-check.sh .` — a new gate with no provenance is this skill's
   own failure mode.

## Red flags

| Thought | Reality |
|---|---|
| "Every finding should become a gate" | Three outcomes exist because most findings are not repository-state predicates. A gate over a judgment is a gate people disable, taking its true positives with it. |
| "Add a row to the registry for the new gate" | Cite the record in the gate's **header**. The checker refuses a row it could have derived, and the header is where the next reader of the gate looks. |
| "One aggregate gate would replace six" | Four such proposals are on record, all refused. The one legal form is a declared vocabulary, and the gate list is not it. |
| "This gate is about KinNest but it lives here" | Project bias, refused mechanically. Let the project declare its vocabulary and read it. |
| "The detector greps the config, which is close enough" | A correlate. `ci/testing.md`: assert the outcome, not the intent. |
| "Zero hits, so the gate works" | Zero hits means unexercised. Say so on the passing run, or the green tick is about nothing. |
| "The origin is obvious from the filename" | Then writing it in the header costs one line. `undetermined` across a corpus is how nobody can tell a deliberate gate from an accreted one. |
| "Deleting the gate is out of scope" | It is an outcome of this decision like any other, and `tidy` gives a verdict per path. A gate nobody can justify is `leek`'s finding first. |

## Quick reference

| Need | Where |
|---|---|
| Every gate's provenance, both directions | `bash .claude/scripts/gate-registry-check.sh .` |
| The source vocabulary and the declared residue | `.claude/docs/gate-registry.tsv` |
| The dimensions, and what disqualifies an option | [references/promotion-decision.md](references/promotion-decision.md) |
| Performing a promotion once it is decided | `mistake-to-gate` §11 |
| Writing the rule half | `rules-distill` (forked) |
| Recording the incident in the first place | `oops`, `caveat`, `mutations` |
| Is a gate still worth having | `leek` (finds it), `tidy` (a verdict per path) |
| What the registry refuses, and the near misses it must not | `.claude/tests/gate-registry.test.sh` |
