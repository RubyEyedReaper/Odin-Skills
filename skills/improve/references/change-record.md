# The change record — five fields

Every improvement declares five things. Four are written **before** the change is made; the fifth is
written into whatever closes it.

They are not a form. Each one below is stated with **what goes wrong when it is missing**, because a
field with no failure mode gets filled in without being read.

## Where the record lives

**Nowhere new.** There is no improvement ledger and there will not be one — a second store of "things
that keep going wrong" diverges from `MISTAKES.md` within a week and nothing says which is right.

| The change | Its record |
|---|---|
| Any improvement | The **commit body**, five fields, one line each |
| An improvement that alters a contract — a boundary, an obligation, a routing rule | Additionally an **ADR** |
| An improvement that removes something | Additionally a row in `CHANGELOG.md`, the canonical removal ledger |

The record travels with the diff. `git log -- <path>` is how a later reader finds why a body says
what it says.

## 1. Reason

**States:** the friction, concretely, and the evidence it recurred. Name the failure-mode key when
the register carries one — read it, do not remember it:

```sh
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report .
python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report . --key <key>
```

**Missing:** the change is indistinguishable from drift. A later reader cannot tell an improvement
from a preference, so the next session with a different preference reverses it, and neither edit
knows about the other.

**Worked line:** `Reason: the boundary table does not name roadmap, so three sessions reached for
this skill to pick what to work on next.`

## 2. Expected benefit

**States:** what becomes true that is not true now — a behaviour, not a quality. "Clearer" is not a
benefit; "an agent asking what to work on next is routed away in the first table" is.

**Missing:** nothing anchors the change's size. An edit with no stated benefit grows to whatever felt
worth writing, and the review has no question to ask except whether the prose reads well.

**Worked line:** `Expected benefit: the first table an agent reads names roadmap, so the wrong-skill
invocation is refused before the body is read.`

## 3. Affected skills

**States:** every skill body, reference or router row the change touches, **and the origin of each**.

The origin is not optional and is not a formality — a vendored body edited in place deletes itself
silently at the next `vendor-skills.sh --refresh`. The precondition, its two commands and the owning
records are in [revert-protocol.md](revert-protocol.md).

**Missing:** the blast radius is discovered after the fact. A change to one body that contradicts a
neighbour's boundary table produces two skills claiming one scenario, and nothing detects that.

**Worked line:** `Affected skills: improve (Odin-authored, mirrored — protected); no vendored body
touched.`

## 4. Validation criteria

**States:** a **falsifier** — a command to run or an observation to make that would show the
improvement did **not** work. Not evidence it did.

| Shape | Example |
|---|---|
| A command | `bash .claude/scripts/skill-routing-check.sh` exits non-zero |
| An observation with a population | the next three sessions hitting this friction still reach for the wrong skill |
| A register reading | a new row appears under the same key after the change landed |

**Missing:** the field is decoration and the improvement is unfalsifiable. Every subsequent state of
the world confirms it, including the state where it changed nothing.

If no falsifier can be stated, that is the finding: the change is a preference, and it is landed as
one or not at all.

**Worked line:** `Validation criteria: a new occurrence under the key after this lands — the routing
table was not the cause.`

## 5. Outcome

**States:** what actually happened, measured against field 4. Written into whatever **closes** the
change — the follow-up commit, an ADR amendment, or the revert.

It cannot be written at declaration time, and that is the point: the four fields above are a
prediction, and an outcome is what makes a prediction cost something.

**Missing:** the improvement is indistinguishable from one that was never made. The body carries an
edit nobody can evaluate, and the next reader inherits a change with a rationale and no result.

Three outcomes, and only one of them is a revert:

| Outcome | What follows |
|---|---|
| The falsifier did not fire | Record it. Done. |
| The falsifier fired — the change did not deliver | Record it, then **decide**: another approach, a reversal, or accept and move on. Not an automatic revert |
| A gate went red | **Revert.** Mandatory, and not a judgment — see [revert-protocol.md](revert-protocol.md) |

**Worked line:** `Outcome: no new occurrence under the key in the following two weeks; falsifier did
not fire.`

## Checklist

- [ ] Reason names the friction and its recurrence, with the register read at run time
- [ ] Expected benefit is a behaviour, not a quality
- [ ] Affected skills lists every body **and its origin**
- [ ] Validation criteria names a falsifier — something that would show failure
- [ ] The five fields are in the commit body; an ADR too, if a contract moved
- [ ] Outcome written into the commit, amendment or revert that closes the change
