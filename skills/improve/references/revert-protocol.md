# Revert protocol

Two things can go wrong with an improvement, and they are answered differently. One is mandatory and
not a judgment. The other is a decision.

| What happened | Response |
|---|---|
| A gate went red | **Revert.** Not patch, not fix forward, not "the gate is wrong" |
| Every gate passed, the falsifier fired anyway | Record the outcome, then decide. Not an automatic revert |

## A change that reddens a gate is reverted, not patched

```sh
git -C <repo> revert <sha>
```

Then re-approach with the gate's output in hand.

**Why, and it is not tidiness.** Patching forward from a red gate entangles the improvement with its
own repair. The next failure cannot be attributed: it may come from the change, from the patch, or
from their interaction, and nothing in the tree separates them. The revert restores a state where
exactly one thing is known to be true — the gate was green — and the re-approach then has a single
variable.

Three moves that are the same mistake, named because each one feels reasonable at the time:

| The move | Why not |
|---|---|
| "The gate is wrong, I'll adjust the gate" | Then the improvement's evidence is a gate the improvement edited. If the gate really is wrong, that is a separate change with its own record, landed first, on its own |
| "It's a one-line fix, faster than reverting" | Speed is not the cost being paid. The cost is that the next red run has two candidate causes |
| "I'll revert if the patch doesn't work" | The patch working is the outcome that hides the problem, not the one that resolves it |

**The revert is the outcome.** Field 5 of [change-record.md](change-record.md) records the revert,
its sha, and what the gate said. A reverted improvement is a completed record, not a failed one.

## A missed benefit is not a revert trigger

The falsifier fired, every gate is green. That is the `outcome` field doing exactly its job — the
prediction was wrong, and this is how you found out.

Decide, and record the decision: re-approach with what the falsifier showed, reverse the change, or
accept it and move on. What is refused is leaving it undecided, because an improvement with a fired
falsifier and no decision reads to the next session as one that worked.

Reversing here is a normal change with its own five fields. It is not this protocol.

## The precondition — check the origin before any skill edit

**Run this before touching a skill body, including your own.** It is a precondition, not a review
step: by the time a refresh has run, the evidence that the edit ever existed is gone from the tree.

`vendor-skills.sh --refresh` performs a **delete-then-copy** over every skill outside its protected
set. An improvement written into an unprotected vendored body survives until the next refresh and
then vanishes — silently, with no failure, no diff and no mention.

Two questions, one command each:

```sh
# 1. Is it vendored?
grep -n "vend .* <name>" .claude/scripts/vendor-skills.sh

# 2. Is it protected from a refresh?
ls -d projects/Odin-Skills/skills/<name>          # the mirror — protected
grep -n -A20 '^FROZEN=' .claude/scripts/vendor-skills.sh | grep -w '<name>'
```

| Answer | What the edit means |
|---|---|
| Not in the vend list | Odin-authored. Edit it |
| Vendored **and** protected (mirrored or `FROZEN`) | Already a fork. Edit it, and port upstream fixes by hand |
| Vendored and **not** protected | **The edit deletes itself.** Take the body out of the refresh path first — which is a fork, with its own record — or do not make the edit |

The third row is a decision with consequences beyond this change: a fork means upstream fixes stop
arriving on their own. `FORKS.md` and
[ADR-0092](../../../docs/adr/0092-editing-a-vendored-skill-body-is-a-fork.md) own that policy and
carry the per-skill ledger. Read them; this file does not restate them, because a policy copied into
a second place is a failure mode this repository's own register already carries.

## Checklist

- [ ] Origin checked with both commands **before** the edit, not after
- [ ] A vendored, unprotected body is either taken out of the refresh path or left alone
- [ ] Red gate → revert, with the sha and the gate output recorded as the outcome
- [ ] No forward patch, no gate adjustment, no "revert if the patch fails"
- [ ] Fired falsifier with green gates → a recorded decision, never silence
