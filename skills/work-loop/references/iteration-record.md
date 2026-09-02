# The iteration record — what a later reader has instead of the session

An iteration's record is read by somebody who was not there. Every field is there because a reader
without it has to guess, and the guesses are what this page exists to remove.

The measured failure: one coordinator ledger held **29 iterations**, and every one of them carried
exactly `actions`, `dependency_missing`, `error_signature`, `n`, `note`, `outcome`,
`recommended_next`, `reported_outcome`, `stall`, `state_hash`. The last record had `note` and
`recommended_next` both null. Nothing in it distinguishes an iteration that improved something from
one that merely ran.

**The fix is not more optional fields** — optional fields are precisely what was null 29 times. It is
that the engine **derives** everything it can, and **refuses** what it cannot check.

## Who writes each field

| Field | Written by | Holds |
|---|---|---|
| `n`, `outcome`, `reported_outcome`, `stall` | engine | The iteration's number and how it ended, including a stall-promoted outcome |
| `error_signature`, `state_hash` | engine | Normalised inputs to the stall predicates |
| `actions` | author (`--action`) | Stable ids for work performed. **Resume keys on these**, never on `n` |
| `measurements` | author (`--measure`) | One number per declared rubric dimension |
| `evaluation` | **engine** | `score_rubric`'s own output over those measurements — per-dimension scores, weighted total, hard gates breached, verdict |
| `baseline` | **engine** | The previous *measured* iteration's readings, or the rubric's declared baselines when there is none |
| `files_changed` | author (`--files-changed`) | What the iteration touched |
| `commands_run` | author (`--command-run`) | What it ran, verbatim |
| `evidence_paths` | author (`--evidence-path`) | Where the evidence lives |
| `critic_verdict` | author (`--critic-verdict`) | One of `PASS` `FAIL` `REVISE` `REVERT` `ESCALATE`, from a context that did not build the change |
| `critic_next` | author (`--critic-next`) | The single most valuable next improvement |
| `decision` | author (`--decision`) | One of `retain` `revert` `revise` `escalate` |
| `blocker`, `evidence`, `recommended_next` | author, or engine on a stall | The escalate record — all three required, see SKILL.md |
| `note` | author (`--note`) | Free text. Deliberately still optional, and deliberately not load-bearing |

## What the engine derives, and why

**The evaluation is computed, never accepted.** Passing a JSON evaluation blob would let a record
claim a verdict the rubric would not produce — the self-assessment this whole design removes. The
author supplies numbers; the engine supplies conclusions.

**The baseline is the previous iteration's own measurements.** That gives before-versus-after for
free and makes it impossible for the stored baseline to disagree with what was actually measured.
Two consequences worth stating:

- At iteration 1 there is no previous reading, so the baseline is the rubric's **declared**
  baselines — the numbers the contract was opened with.
- An iteration recorded **without** `--measure` carries a null `measurements` and a null
  `evaluation`, and **does not become the next iteration's baseline**. A blank pass must not erase
  the last real reading, or a later before-versus-after compares an after against nothing.

## What the engine refuses, before anything is written

Every check runs above the first write. A refusal that still records is not one, and a half-claimed
action makes the next resume skip work nobody did.

| Refused | Exit | Why |
|---|---|---|
| `--critic-verdict` with no `--evidence-path` | 1 | A verdict with nothing behind it is the self-assessment a critic pass exists to replace |
| A verdict outside the five words | 1 | A verdict nobody can compare with another iteration's is not a verdict |
| A decision outside the four words | 1 | Same |
| A measurement naming an undeclared dimension, or a declared dimension left unmeasured | 1 | A total over a subset is a score about a smaller rubric |
| `--decision retain` over a breached hard gate | **7** | Regression protection — see below |

The vocabularies are validated in the command rather than by argparse `choices`, so a bad word
returns **1 (malformed)** rather than **2 (usage)**. A caller that cannot tell those apart will treat
one as the other.

## `retain` is refused over a breached hard gate

"Net improvement" is never an excuse for silently breaking core behaviour. When the evaluation's
verdict is `fail`, `--decision retain` is **refused** with exit 7, naming the breached dimensions and
the weighted total that does not buy them.

Refused rather than warned: a warning in an unattended run is a line nobody reads. Refused rather
than silently rewritten to `revert`: the engine would then be inventing a decision nobody made, in
the one field whose entire purpose is to record what was chosen.

An author with a genuine approved trade-off records `escalate` — which is the correct record for it,
and carries a blocker, its evidence and a recommended next action.

**With no measurements there is no breached gate to protect against**, and `retain` is accepted. The
engine refuses what it *measured*, never what it did not look at; inventing a refusal there would be
a check that could not run passing itself off as a check that ran and found nothing.

## Two vocabularies, kept apart

`critic_verdict` and the loop's six `outcome` values answer different questions and are deliberately
disjoint — a test asserts the sets do not intersect.

| | Judges | Values |
|---|---|---|
| `outcome` | how this **iteration** ended | `continue` `complete` `revise` `escalate` `pause` `stop` |
| `critic_verdict` | the **change** the iteration made | `PASS` `FAIL` `REVISE` `REVERT` `ESCALATE` |

`continue` is meaningless as a critic verdict, which is the shortest argument against merging them.

## Stated residue

**An evidence path is checked for presence, not for existence.** Requiring the file to exist at
iterate time would make the ledger unwritable from a different checkout and would refuse a verdict
about a CI artifact that legitimately lives elsewhere — a verdict that depends on the host rather
than on the tree. The cost is real and is stated here rather than pretended away: a path can be
wrong, and only a reader will find out.

**The ledger is append-only in behaviour, not in format.** `iterations` is only ever extended and
`iterate` refuses a completed action, so nothing rewrites an existing record. A separate append-only
`.jsonl` would be a second on-disk format to keep in sync for a property the engine already holds.
If anything ever does rewrite an existing iteration, that changes and the format question re-opens.

## Quick reference

```sh
cd .claude/skills/work-loop
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome continue \
        --action tighten-guard \
        --measure gate-integrity=0 --measure regression-matrix-strength=94 \
        --measure record-integrity=0 --measure context-budget=37000 \
        --files-changed .claude/scripts/some-check.sh \
        --command-run "bash .claude/scripts/ci-local.sh --fast" \
        --evidence-path /tmp/ci-fast.log \
        --critic-brief "$BRIEF" \
        --critic-verdict PASS \
        --critic-next "measure the suite's wall clock before adding another gate" \
        --decision retain
```

`--critic-brief` is not optional here. Wave 3 bound the verdict to a packet the engine assembled
(`references/critic-pass.md`), and this command is refused without it — the form above without that
flag was documented for one commit and would never have run.

## Reading it back

`status` surfaces the record's quality: `rubric_verdict`, `weighted_total`, `critic_verdict`,
`decision`, and `quality_from`.

**All five come from one iteration**, and `quality_from` is its `n`. The alternative — resolving each
field from the last record that carried it — composes a snapshot that never existed: `iterate`
refuses `--decision retain` while a hard gate is breached, so a reader taking the rubric verdict from
iteration 2 and the decision from iteration 1 prints exactly the pairing the writer refuses. The read
path contradicting the write path is a worse defect than a blank field, because it is not blank.

The record chosen is the last one that was **judged** — scored, reviewed, or decided. Preferring a
scored record over a later reviewed one would drop the loop's most recent judgment: a reader would
see `rubric pass … (iteration 1)` and conclude nobody reviewed the loop, while iteration 2 carried a
REVISE. With no judged record at all, five `null`s — including over an empty ledger, where the payload
carries them beside its exit 4, so a consumer written against the documented shape does not raise on
the one path this command exists to keep distinguishable.
