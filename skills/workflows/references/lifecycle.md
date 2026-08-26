# Lifecycle transitions and the evidence each one requires

The states are `draft`, `active`, `retired`. Every transition is recorded **in the manifest**, which
is what makes the chain's history readable a year later without a git archaeology session.

## draft → active

A chain is `draft` while it is still being written and `active` once it is the recommended way to do
that class of work.

**Evidence:** `validate` exits 0 for that id. Nothing else gates the promotion — a chain is
recommended because a human decided it is, and no script can assert that.

Flip `status` by hand and re-validate. There is no `promote` subcommand: a one-word edit does not
need a verb, and a verb would imply a check that does not exist.

## active → active (revise)

Edit the manifest, move the version per the table in
[manifest-schema.md](manifest-schema.md), re-validate.

**Evidence:** the version moved. A revision that leaves the version alone is indistinguishable from
the previous revision to anyone who read it earlier — which is the whole reason the field is there.

## active → retired, with a reason

```sh
python3 -m scripts.workflow retire <id> --reason "the gate it fed was deleted" --root <root>
```

**Evidence required:** the reason text, stored at `retired.reason` with a timestamp. The minor
version is bumped, because a lifecycle transition is a change to the interface.

Use this branch when the work the chain describes is no longer done at all — the tool went away, the
subsystem was deleted, the practice was abandoned.

## active → retired, superseded

```sh
python3 -m scripts.workflow retire <old> --superseded-by <new> --root <root>
```

**Evidence required, and checked:**

1. `<new>` exists as a manifest.
2. `<new>` is not itself retired — a supersede must point at something runnable. A chain of
   retirements ending nowhere is how a reader is sent in a circle.

Stored at `retired.superseded_by`. Set `supersedes: "<old>"` on the successor in the same change, so
the link is readable from either end; validation does not require it, because a successor authored
before the retirement legitimately does not know it yet.

## Why retire and supersede share one verb

Two verbs would let a manifest carry both kinds of evidence, or neither. One verb with mutually
exclusive **required** evidence makes "abandoned" and "replaced" distinguishable in the artifact and
impossible to conflate — while keeping the CLI to five subcommands.

Retiring an already-retired workflow is refused (exit 3) rather than overwriting the first reason.
The first retirement is the one that happened.

## retired → run: the refusal

```
$ python3 -m scripts.workflow run retired-chain --root <root>
retired-chain is retired (new-chain) — refusing to run
$ echo $?
3
```

This is the point of the lifecycle. A `status` field nothing enforces is a comment, and a comment
does not stop the next agent from following a chain everyone agreed to stop using.

Three properties, each asserted by the matrix in `tests/test_retire.py`:

- The refusal has **its own exit code**, so a caller branches on it without parsing text.
- `--dry-run` does **not** bypass it. A dry run of a retired workflow is still refused.
- A retired manifest still **validates**. Retirement is a lifecycle state, not corruption; conflating
  the two would make `validate` red forever on a healthy repository.

## There is no un-retire

Reviving a retired chain means writing a new manifest with a new `id` and `supersedes` pointing at
the retired one. Flipping `status` back would erase the retirement evidence, and the reason a chain
was stopped is exactly what the person reviving it needs to read.

## The empty set is not a finding

`validate` over a directory with no manifests exits **4**, not 0 and not 1.

Kept apart from findings deliberately: a caller that cannot distinguish "every manifest is clean"
from "there were no manifests" cannot detect the failure where a path is wrong, a directory is
missing, or a glob matched nothing — and that failure reports itself as success. Exit 4 also covers
a manifest directory that does not exist at all, for the same reason: nothing was examined.

## Where run records go

`run` opens `.claude/.runtime/workflow-run/<session-id>/<timestamp>-<id>.json`; `record` closes the
most recent open one with `ok` or `failed` and an optional note. A closed record is not reopened —
a second `record` for the same workflow is a usage error, because a run that already reported an
outcome is over.

These are **in-flight state**, session-keyed like the other runtime classes. Durable outcomes belong
in the ledgers that already exist — `CHANGELOG.md`, `roadmap.json`, `MISTAKES.md`. A new committed
store would split the counts those ledgers already carry.
