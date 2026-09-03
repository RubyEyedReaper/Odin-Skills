# The quality rubric — what "better" means, before the first iteration

A loop that cannot say what better means will report that it got better. The rubric is the twelfth
contract field, and it is what makes that claim checkable: a weighted set of dimensions, each naming
the **command** that produces its number.

`open` refuses a rubric that cannot decide anything. `score` takes one measurement per dimension and
returns a weighted total, the hard gates breached, and one verdict — in which **a hard-gate failure
outranks any total, including one that went up**.

## A dimension — eight keys, no more and no fewer

```json
{
  "dimension": "gate-integrity",
  "evidence_command": "bash .claude/scripts/ci-local.sh",
  "baseline": 2,
  "target": 0,
  "weight": 40,
  "failure_threshold": 0,
  "direction": "lower-is-better",
  "hard_gate": true
}
```

| Key | Well-formed when | What goes wrong without it |
|---|---|---|
| `dimension` | A name unique within the rubric | Two dimensions with one name make the total depend on which was read last |
| `evidence_command` | Non-empty, and it really produces the number | "Better" is a judgment again, and the loop is back where it started |
| `baseline` | The number measured **before** the change | Nothing to compare an after against, which is half of what a critic needs |
| `target` | The number that would score 100, and not equal to `baseline` unless `must_not_regress` is declared | A dimension that cannot move scores nothing and measures nothing |
| `weight` | A positive number | A zero-weight dimension is declared, counts for nothing, and reads as coverage it does not provide |
| `failure_threshold` | The value on the wrong side of which this dimension fails | The dimension reports and never refuses |
| `direction` | `higher-is-better` or `lower-is-better`, agreeing with `baseline` → `target` | See below — this is the one key that could have been derived, and deliberately is not |
| `hard_gate` | `true` or `false` — a boolean, not a truthy string | A truthy string would make every dimension a hard gate, silently |

### The ninth key, which is optional: `must_not_regress`

A dimension whose job is to **not move** — `suite-failures` at 0, `record-integrity` at 0 — sits at
its target already. The `target != baseline` rule above is right for an optimisation objective and
wrong for a hard gate, so those two honest dimensions were unwritable, and the workaround reached
for first was a fractional target (`0` → `0.0001`) invented to satisfy the validator
(harness:RM-0473). That is a lie written into the contract.

```json
{
  "dimension": "suite-failures",
  "evidence_command": "bash .claude/tests/run-all.sh",
  "baseline": 0,
  "target": 0,
  "weight": 30,
  "failure_threshold": 0,
  "direction": "lower-is-better",
  "hard_gate": true,
  "must_not_regress": true
}
```

| Declared `true` | Effect |
|---|---|
| `target` | must **equal** `baseline` — a dimension cannot both hold a line and be asked to move to a different one, and the disagreement is refused rather than silently resolved |
| `direction` | not cross-checked against `baseline` → `target`; for a line being held those are equal whichever direction is better, so the comparison decides nothing. It still decides which side of `failure_threshold` fails |
| score | `100` while the line holds, `0` once it breaks — there is nothing to interpolate between two ends that are the same number, which is exactly why the old refusal existed |

It is the one key a dimension may omit; absent means `false`, which is what every rubric written
before it already meant. Declared, never inferred from `baseline`, `target` and `failure_threshold`
coinciding — for the same reason `direction` is declared, immediately below.

**Why `direction` is declared rather than derived.** The ordering of `baseline` and `target` already
implies it, so deriving it would cost one key fewer. It is declared because a swapped pair reads
perfectly correct on the page and *inverts which side of `failure_threshold` fails*. `open`
cross-checks the two and refuses a disagreement, which turns a silent inversion into a refusal.

## The arithmetic, stated once

```
score            = 100 if not gate_failed else 0            (must_not_regress)
                 | clamp(0, 100, (measured − baseline) ÷ (target − baseline) × 100)
weighted_total   = Σ(weight × score) ÷ Σ(weight)
gate_failed      = measured > failure_threshold   (lower-is-better)
                 | measured < failure_threshold   (higher-is-better)
verdict          = fail  if any dimension has hard_gate and gate_failed
                 | pass  otherwise
```

The formula is direction-agnostic, which is why `direction` earns its place on the *threshold* test
rather than on the score. Overshooting a target does not score above 100 — a dimension cannot bank
credit against another one's failure.

**Scoring well and passing the gate are separate questions.** A dimension can score 50 and still be
over its threshold; folding the two together is exactly how a good total comes to buy a broken gate.

## Hard gates outrank the weighted total

The property the whole rubric exists to protect, and the reason `score` has its own exit code:

| Exit | Means |
|---|---|
| 0 | scored, and no hard gate was breached |
| 1 | the rubric or the measurements are malformed |
| 2 | there is no ledger for that session |
| 6 | **scored, and a hard gate was breached** — the total is still printed, and does not buy it |

Distinguishing 6 from 1 is not fussiness. A caller that cannot tell "measured and failed a gate"
from "malformed rubric" will eventually treat one as the other, and the one it treats as harmless
is the one that matters. The matrix case that fixes this in place scores one rubric twice: 28.0
passing, then **90.0 failing** — a strictly higher total with one hard gate breached.

## A measurement that could not be read is a finding, never a zero

`score` refuses a non-numeric measurement rather than coercing it. A rubric that silently scored an
unreadable channel as its worst value would report a regression nobody caused; as its best, it would
hide a real one. Both are worse than refusing.

For the same reason `score` refuses a dimension left unmeasured: a total over a subset is a score
about a **smaller rubric**, reported as though it were this one.

## The engine reads the evidence commands; it never runs one

Running arbitrary shell out of a JSON file was scored and **vetoed** (DEC-0091, ADR-0143): a
subprocess spawned from inside `loop.py` is not a tool call, so it would run outside
`odin-safety-guard.sh`'s always-on layers entirely — outside the database-wipe guard, the
credential-file guard and the look-before-you-destroy guard. Routing arbitrary contract-supplied
strings around the guards is a worse defect than the one it would fix. What lifts the veto is
recorded in the ADR.

**What `open` checks statically**, and refuses as a contract finding:

| Refused | Why |
|---|---|
| A command that does not parse as a shell command | An unbalanced quote is a finding now rather than a surprise at measurement time |
| A program that resolves neither on `PATH` nor as a file under `--root` | A command that cannot start produced no number. Every segment of a pipeline or `&&` chain is checked; an `LC_ALL=C` prefix is not read as the program |
| An unresolved placeholder | A long flag whose value is a bare one- or two-character uppercase token, an angle-bracket `<placeholder>`, or a literal `TBD`/`FIXME`/`XXX` |

The placeholder pattern reads the **raw command text**, not the argv: the defect it was written for
carried `'--root','R','--session','S'` inside a quoted `python3 -c` program, where no tokeniser would
have seen it. It is deliberately narrow — `--format JSON` and `--component always-on` do not match,
and every evidence command committed in this repository produces zero findings, pinned as a
negative-control case. A detector that fires on the real population is a false positive, not a gate.

**What is deliberately not checked:** the argument an interpreter is handed. `bash does-not-exist.sh`
passes, because `bash` resolves. `--root` is a ledger root and frequently not a checkout at all —
`sample-contract-check.sh` opens every committed sample against an empty temporary directory — so a
path-existence check there would refuse every honest command in a fixture.

## A baseline says how it was obtained

```sh
# run the command yourself — a real tool call, so every always-on guard applies
bash .claude/scripts/ci-local.sh > /tmp/gate.txt 2>&1
python3 -m scripts.loop open --root ../../.. --session "$SID" --contract contract.json \
        --baseline-evidence gate-integrity=/tmp/gate.txt
```

`--baseline-evidence <dimension>=<path>` is repeatable. The declared baseline must appear in the
transcript as a standalone number — `2` is not evidenced by a file whose only number is `20` — or
the `open` is refused. An unreadable or empty transcript exits **8**, the code `brief` already spends
on that shape. Every dimension with no transcript is recorded `declared`, never silently treated as
measured, and `status` reports `baselines_measured` / `baselines_total`.

**What `measured` proves:** a transcript carrying that number was supplied at open time — an omitted
measurement becomes a forged one. **What it does not prove:** that the number came from that command.
No non-executing engine could, and this page says so rather than overclaiming.

A `revise` resets every dimension to `declared`: the predecessor's transcript is not evidence for a
successor's baselines, which may not even be the same numbers.

## The default dimension set for this repository — DEC-0090

Odin ships **no application source**, so most of the dimensions a general quality rubric reaches for
have no subject here. Claiming them would be a totality claim, not coverage. Four dimensions
survived the constraint that every one names a command returning a number or an exit code:

| Dimension | Evidence command | Direction | Weight | Hard gate |
|---|---|---|---|---|
| `gate-integrity` | `bash .claude/scripts/ci-local.sh` (its exit code) | lower-is-better | 40 | yes |
| `regression-matrix-strength` | `ls .claude/tests/*.test.sh \| wc -l` | higher-is-better | 15 | yes |
| `record-integrity` | `bash .claude/scripts/doc-reference-check.sh` (its exit code) | lower-is-better | 25 | yes |
| `context-budget` | `bash .claude/scripts/context-budget.sh bytes --component always-on` | lower-is-better | 20 | no |

**Baseline and target are measured at `open` time, not copied from this page.** A number written
here would be a second copy of a count this repository already derives, and it would be stale by the
next change that moved it — see `.claude/rules/ci/inventory-claims.md`. Measure, then declare.

`context-budget` is the one optimisation objective: it reports when it is over its threshold and
does not veto, because a rule file legitimately growing is not a broken gate.

**Three sets were vetoed before scoring**, so this one beat a smaller field — recorded in DEC-0090
with what would lift each veto. A general eleven-dimension menu and a two-dimension set both failed
the every-dimension-names-a-command constraint; a per-loop ad-hoc set failed the recorded-on-disk
constraint, because a rubric re-invented each iteration has no *before* for a critic to compare an
*after* against.

## What the rubric deliberately does not cover

**A dimension you cannot write a command for belongs in review, and this page says so rather than
pretending.** A rubric encoding taste produces false positives; a gate people disagree with gets
disabled, and takes its true positives with it. When a quality that matters has no command, name it
in the review checklist and leave it out of the rubric — the honest residue is worth more than a
dimension that looks measured and is not.

## Quick reference

```sh
cd .claude/skills/work-loop
python3 -m scripts.loop open --root ../../.. --session "$SID" --contract contract.json \
        --baseline-evidence gate-integrity=/tmp/gate.txt
python3 -m scripts.loop score --root ../../.. --session "$SID" \
        --measure gate-integrity=0 \
        --measure regression-matrix-strength=94 \
        --measure record-integrity=0 \
        --measure context-budget=37000 --json
```
