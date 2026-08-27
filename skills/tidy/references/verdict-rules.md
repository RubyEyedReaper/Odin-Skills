# Verdict rules

The four verdicts `tidy-verdict.sh` emits, the evidence each one requires, and the direction they
fail. Read this before overriding a verdict by hand.

## The verdicts

| Verdict | Exit | Emitted when | What it authorizes |
|---|---|---|---|
| `remove` | 0 | A removal ledger records the path's basename | A deliberate removal, dry-run first |
| `retain` | 10 | No ledger records it | Nothing. Keep the material. |
| `refuse` | 11 | The argument is a branch | Nothing, permanently |
| `unresolved` | 12 | The path resolved to neither a file nor a branch, or no ledger was readable | Nothing. Report the gap. |
| — | 2 | Usage: no argument, a directory, an empty or missing `--root` | Nothing |

**Every verdict other than `remove` keeps the material.** That direction is the design, not an
accident of implementation: a wrong `retain` costs disk, and a wrong `remove` costs the content.
When you are unsure which way an unusual input should fall, it falls toward keeping.

## What counts as evidence for `remove`

Two ledgers, both committed files, so a verdict is reproducible from a clean checkout:

1. **`CHANGELOG.md`** — the contract's canonical removal ledger (CLAUDE.md item 8: a plan is spent
   once its work is in living docs or code *and recorded in the changelog*).
2. **A decision record** under `.claude/docs/decisions/*.md` — a numbered decision that names the
   path is removal-grade evidence too. A plan whose substance was absorbed into a recorded decision
   is spent even when the changelog never mentioned it.

What is deliberately **not** evidence:

- **A mention in git history.** A commit message naming a file is usually the commit that *created*
  it. Accepting history would make the evidence test nearly vacuous.
- **The path looking obsolete.** An old timestamp, a stale-sounding name, a directory nobody has
  touched — none of these say the content survived anywhere. They are the input to a `leek` finding,
  not evidence for a removal.
- **A record naming a branch.** See `refuse` below; no evidence unlocks that case.

### How the basename is matched

Boundary-anchored, literal, case-sensitive. Not a plain substring, and not `grep -w`.

`grep -w` treats `.` and `-` as word separators, and those are exactly the characters that join
these names — so under `-w`, a changelog line naming `live.md.bak` would "record" `live.md`, and a
line naming `old-live.md` would record `live.md`. Both are false positives, and a false positive
here authorizes a deletion. The pattern therefore rejects a neighbouring `.`, `-`, `_`, `/` or
alphanumeric on either side of the match.

## `refuse` — branches, permanently

A branch never receives a `remove` verdict. Not an unlanded one, not a fully landed one, and not one
the changelog names.

The reason is [ADR-0093](../../../docs/adr/0093-branch-landedness-is-a-question-about-content.md):
the error is asymmetric and force-push is blocked, so a wrongly deleted branch has no reflex that
restores it. Landedness *is* computable — `branch-landedness.sh` computes it, and
`successor-manager` consumes it — and a verdict *about* a branch is useful. But "we can tell" is not
"we may delete", and turning the first into the second is the tempting mistake this rule exists to
refuse.

## `unresolved` — a check that could not look

Two causes, both reported rather than swallowed:

- The argument names neither a path on disk nor a branch in the repository.
- Neither ledger is readable, so no removal could be justified from evidence.

A blind check must not be indistinguishable from a measured keep. That collapse is what let 76 of 77
open issues go uncaptured in this repository ([ADR-0069]), and the same defect pointed at deletion
costs more. `unresolved` is a finding: report it, fix what could not be read, and re-run.

[ADR-0069]: ../../../docs/adr/0069-evidence-that-could-not-be-gathered-is-not-evidence-of-none.md

## The paired recipe

A `remove` verdict is followed by two command lines:

```
dry-run: git -C <root> rm -r --dry-run -- <path>
apply: git -C <root> rm -r --force -- <path>
```

or, for an untracked path, the `git clean -d` pair. Both are built from **one template with a single
flag slot**, so they differ at exactly one token position. That is what makes "dry-run first, on the
same code path as the apply" a property a test can check rather than a promise in prose — a
`--dry-run` that runs different code from the apply proves nothing about the apply.

`tidy-verdict.sh` runs neither line. Running the dry-run, reading what it names, and then running the
apply is a separate deliberate act with a human-visible diff.

## Overriding a verdict

Sometimes the right answer disagrees with the script — material whose content survived somewhere no
ledger records, most often. The repair is to **write the record, then re-run**, not to skip the
verdict. The ledger entry is the durable half; the removal is the disposable half. A removal
performed without one leaves nothing behind saying where the content went, which is precisely the
state the ledger exists to prevent.
