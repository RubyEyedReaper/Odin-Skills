---
name: consistency
description: Use when something new is about to be written and something in the tree may already solve it — a new script, gate, matrix, helper, config format, id scheme, error convention or file layout. Also on "is there already one of these", "what do we already use for this", "follow the existing pattern", "another implementation", "a second copy", "reinvent", "roll our own", "write our own version", "make this consistent with", and when a review finds a new variation where a working solution already exists. Fires before the writing, on the reuse question, whether or not anybody asked.
metadata:
  origin: Odin
---

# Consistency — name what already solves it, then record the decision to differ

## The stance

**A second implementation is a decision, and an undeclared decision is a defect.** Not because
variation is forbidden — because the two copies will disagree, and the looser one wins silently.
This repository has recorded that three times under one failure key: a hook carrying its own copy of
an engine's staleness policy at 14 days while the engine said 7; a gate list hand-copied into a
handoff and missing one row; two implementations of "has promotion happened" inside a single file,
disagreeing for as long as both existed.

So the discipline is one question asked before the writing, not a review afterwards:

> **What already solves this, and if the answer is "something does", why is a new one better?**

Both halves are required. Naming nothing and writing anyway is the failure. Naming something and
differing anyway is fine — **provided the differing is recorded where the next reader finds it.**

## What this owns, and what it must not restate

This skill is a composition layer over rules and skills that already exist. It **cites** them; a
second copy of a rule drifts, which is the thing being prosecuted here.

| The task | Its owner | Never re-derived here |
|---|---|---|
| Searching outward before writing new code — GitHub, vendor docs, package registries | [`common/development-workflow.md`](../../rules/common/development-workflow.md) § Feature Implementation Workflow step 0 | The search order and the tools. That rule is outward-facing; this skill is the inward half of the same question |
| The style rules themselves — naming, file layout, error handling, documentation style, testing floor | `.claude/rules/`, per namespace | All of it. A skill restating a rule creates the looser copy |
| Where a module's seams go, and how deep an interface should be | `codebase-design` | Module boundaries and testability. The scalability half of this skill's brief routes there |
| The size at which a file must be split | [`common/coding-style.md`](../../rules/common/coding-style.md) | The 200–400 / 800-line ceiling and the function ceiling |
| Turning an incident into a gate, and counting recurrence | `oops`, `mistake-to-gate` | The failure keys, the promotion threshold, the matrix bar. Those fire **after** a failure; this fires **before** the writing |
| Rule text drawn from several skills, and which loading tier it goes in | `rules-distill` | The tier decision and the distillation ledger |
| Whether a repeated action is worth automating at all | `automate` | The six verdicts and the six levels |
| Whether code that already exists is overdeveloped | `not-impressed` | The hostile prior and its one verdict — that is a review, this is a precondition |
| Whether a friction that keeps recurring is worth changing | `improve` | The declare-before / revert-after contract |

**The gap this fills**, and the only reason it is a skill: the rule above says research *the world*
before writing new code, and nothing says research *this tree*. Nothing owns the moment where a
working solution exists twenty files away and the cheapest path is a second one.

## The procedure

Three steps, at the moment something new is about to be written.

**1. Name the incumbent.** State what already solves this, by path. Not "we probably have
something" — a file. Where to look, cheapest first:

| The new thing | Ask |
|---|---|
| a script or gate | `ls .claude/scripts/`, and `.claude/scripts/lib/` for the predicate it needs |
| a matrix | the matrix of the closest existing gate — copy its shape, not its content |
| a config or registry format | an existing `.conf`/`.tsv` beside its consumer |
| an id scheme, a status vocabulary, an exit-code convention | the closest existing one, and reuse the spelling |
| anything at all | `find-skills`, then `.claude/docs/skill-decision-matrix.md` |

If the answer is genuinely "nothing", say so in one line and write the new thing. That is the
common case and it costs a sentence.

**2. If something does solve it, choose — and the default is reuse.** Source the library, follow the
format, take the same exit codes. A near-fit adapted is cheaper than a parallel implementation,
because the second one is the one nobody updates.

**3. If differing is right, record it where the next reader will be.** In descending order of
durability:

- the new file's own header — one paragraph naming the incumbent and the reason
- a row in the registry that governs the thing (for a library predicate,
  `.claude/scripts/one-implementation.conf`)
- the commit body
- a DEC when the choice is scorable, an ADR when it constrains future work

A reason that names *what is different about this case* is a record. "Cleaner" is not.

## The mechanical half

One slice of this is checkable, and it is checked:
[`one-implementation-check.sh`](../../scripts/one-implementation-check.sh), stepped in `ci-local.sh`
alongside its matrix.

**The predicate.** Ten libraries under `.claude/scripts/lib/` exist so that a question has one
answer, and eight declare it in their own headers. A script, hook or matrix that recomputes one of
those predicates — by calling an owned symbol without sourcing its owner, or by restating a declared
signature — is a second answer, and is reported unless the registry records an exemption.

| Finding | Means |
|---|---|
| `UNSOURCED-CALL <file> <symbol> <lib>` | the file names an owned symbol and does not source the library that owns it |
| `RESTATED <file> <lib>` | the file matches the library's declared signature — the predicate written a second time under other names |
| `UNREGISTERED-OWNER <lib>` | a library claims sole ownership and the registry has no row: the registry has fallen behind the tree |
| `STALE-REGISTRY …` | a row names a library that is gone, one whose header no longer claims, or an exemption with no reason or a path that has moved |
| `EXEMPT` / `UNCHECKED` | printed on passing runs too, so "exempt by design" stays a standing question |

Adding a row, and what a reason must contain:
[`references/one-implementation-registry.md`](references/one-implementation-registry.md).

**What it does not catch, said plainly.** Two implementations inside one file (the unit is a file
against a library). A copy of something that is not a library predicate — a gate list copied into a
handoff, a policy value pasted into a hook. A restatement under different names where no signature
is declared, which is seven of the eight rows, and the gate prints `UNCHECKED` for each of them on
every run rather than letting silence read as coverage.

**What it rests on.** A library's header *claiming* sole ownership is a correlate of the real
property — that two consumers would otherwise compute the question differently — and no script can
read the real one. A machine-readable marker inside each library removes the correlate and is the
recorded successor (DEC-0114, Fork 2).

## The scalability half, routed rather than restated

The brief that produced this skill also asked for scalable, modular, well-documented design from the
outset. That is judgment, it already has owners, and a paragraph of advice here would be filler:
seams and module depth are `codebase-design`'s, the file-size ceiling is
[`common/coding-style.md`](../../rules/common/coding-style.md)'s, and neither is re-derived here.
The one thing this skill adds to it is the same question pointed at structure: **before inventing a
new module shape, name the module in this tree that already has the shape you want.**

## Red flags

| Thought | Reality |
|---|---|
| "Nothing quite fits" | Name the closest thing and say what does not fit. If you cannot, you have not looked |
| "Adapting the existing one is more work" | It is more work once. Two implementations are more work every time either changes |
| "This is a special case" | Then the special part is the record. Write the paragraph |
| "It's only a small helper" | M-0003 was a number in a hook. M-0106 was one function |
| "I'll unify them later" | Nothing in this repository's history has been unified later. The registry row is the cheap version of later |
| "The gate is green, so there is no second copy" | Seven of eight rows have no signature declared, and the gate says so on every run. Green means *what is checked* is clean |
| "This is a review question" | A review sees the code that exists. This is the question before it exists — `not-impressed` owns the other one |
