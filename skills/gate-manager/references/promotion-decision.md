# The promotion decision — three outcomes, six dimensions, and what disqualifies an option

Read when a finding must become something durable. The arithmetic is `decision-matrix`'s; what this
file supplies is the option set, the dimensions, and the disqualifiers that settle most cases before
any scoring happens.

## The seven sources

Each already has a skill that produces the record. This decision starts *after* one exists — a
finding with no record is `oops`'s work, not this one's.

| Source | Record | Produced by |
|---|---|---|
| a shipped bug, wrong assumption, unsafe action | a `MISTAKES.md` row, keyed | `oops` |
| something that behaves differently from how it reads | a `CAVEAT.md` row with its recurrence condition | `caveat` |
| a change whose real effect nobody checked | a `MUTATIONS.md` row, `pending` until observed | `mutations` |
| retained context, waste, orphaned sessions, unused skills | a filed issue | `leek` |
| a recurring friction no script can decide | a declared, reversible change | `improve` |
| something learned that should outlive the session | a record with a `verified_by` command | `learn` |
| a tracker issue or an audit finding | `#NNN`, or a row in `.claude/docs/audits/` | `issues` / audit |

## The three outcomes

Exactly three. A proposal that fits none of them is not ready to be decided.

### 1. Gate

A command decides it against the repository as it stands, with no judgment. What lands: a checker, a
matrix **seen red once**, a step line in `ci-local.sh`, and a provenance the registry can derive.

### 2. Review criterion

Decidable, but only by a reader. What lands: a normative statement in the owning rule file that
**names that it has no detector**. `ci/rule-enforcement.md` § Three Honest Outcomes is the authority;
an unmarked normative statement is the defect that section exists to catch.

### 3. Recorded residue

Real, and neither of the above reaches it. What lands: a stated residue in the nearest gate's header
or rule, saying **what was measured and when** — never a bare "unenforceable", which is a claim
about the world rather than about an attempt.

**There is no fourth.** "Gate it later" is the finding evaporating with the context that held it.

## The disqualifiers — check these before scoring

Most proposals are settled here, and scoring one that a disqualifier has already answered wastes the
round and produces a number that looks like agreement.

| Disqualifier | Consequence |
|---|---|
| **Keys on a correlate, not the thing** (`mistake-to-gate` §3) | Not a gate. A file count is not coverage; a comment mention is not wiring; a config key is not the behaviour (`ci/testing.md` § Assert Outcomes, Not Intent). → review criterion |
| **The predicate needs a judgment** — "is this the *right* tier", "is this abstraction earned" | Not a gate, at any strength. → review criterion |
| **It is a second copy of an existing policy** | Refused outright. Four such proposals are on record (M-0065, M-0091, M-0105, M-0110), all as `ci-gate/policy-copied-into-a-second-place`. Extend the incumbent, named by path. |
| **A harness gate about one project** | Refused mechanically by `gate-registry-check.sh`. The project declares its vocabulary; the harness reads it. |
| **Hit rate not measured** | Not ready. A check that fires on everything is a false positive; one that can never fire is decoration. Measure over the real population first, and record both numbers. |
| **The predicate reads ambient state** | Not a gate yet. A verdict that turns on the machine running it is `ci-gate/fixture-reads-ambient-state`, and most recorded occurrences were wrongly **green**. |
| **Nothing could ever fail it** | Not a gate. A gate with no reachable red is a green tick over an empty set. |

## The dimensions, when scoring is still needed

Six, scored per option through `decision-matrix`. Weights are the caller's to set and to record.

| Dimension | Asks | Higher is better |
|---|---|---|
| **decidability** | can a command answer it against the tree, alone? | yes |
| **hit rate** | over the real population, how many true findings vs false ones? | measured, neither 0 nor 100% |
| **cost at the gate** | wall-clock in the pre-push set and in `ci-local.sh` | lower |
| **blast radius when wrong** | what a false positive blocks, and who it blocks | lower |
| **durability** | does it survive a rename, a refresh, a version bump? | yes |
| **who reads the failure** | does its message name what to do, to someone positioned to do it? | yes |

**Cost is a real dimension, not a formality.** The pre-push set carries a declared budget and it is
nearly spent; a gate that fits today and forces the next four into exemption has spent a shared
resource that nobody re-measured. Read the budget before proposing, not after.

**Durability decides more than it looks.** A detector keyed on a filename, a line number, or a
first-match ordering goes quiet the first time something is inserted above it — silently, which is
the worst direction. Prefer a predicate keyed on the property.

## What a landed gate owes

Every one of these, or it is not finished:

1. **A matrix with one BLOCK case per condition it claims to refuse**, ALLOW cases for the near
   misses, and each case asserting the **message** rather than the exit code alone — neighbouring
   rules share exit codes, and an exit-code-only matrix keeps a broken gate green.
2. **Seen red once.** Where implementation preceded the test, `common/testing.md`'s recovery
   applies: mutate the checker one change at a time, prove a case goes red per mutation, **anchor
   every mutation and assert it applied**, and say in the commit that RED was skipped.
3. **A distinguishable "could not look."** An empty input set is an error, not a clean result.
4. **A provenance in its own header** — the record's id, where the next reader of the gate sees it,
   so `gate-registry-check.sh` derives it and no registry row is needed.
5. **A classification**: in the pre-push set with a measured cost, or in
   `.claude/docs/pre-push-exempt.manifest` with a stated reason.
6. **A step line in `ci-local.sh`.** A gate nothing runs is not a gate — two matrices sat unwired in
   this repository with 33 assertions between them, all passing, all running nowhere.

## What this decision never decides

Stated so a recorded DEC is not read as more than it is:

- **Whether the finding is true.** That is the record's job, and the record's premise may be stale
  (`common/development-workflow.md` § The Report May Be Stale — measured at 31 of 43).
- **Whether an existing gate should be removed.** `leek` finds one nobody can justify; `tidy` gives
  a verdict per path. This decision is about what a *new* finding becomes.
- **Whether the gate is well written.** A gate can be precisely, checkably wrong. That is review's.
