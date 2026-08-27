# The staleness pass

```sh
python3 -m scripts.capture_bar verify --record rec.json                       # reports; runs nothing
python3 -m scripts.capture_bar verify --record rec.json --run --cwd ../../..  # executes and decides
```

The record is a JSON object carrying `confidence`, and — at `reproduced` and above — `verified_by`
and `verified_on`. A rung above `observed` without those two fields is **malformed**, not merely
unverified: it claims evidence it never named.

## Reading a record never runs it

`verified_by` holds a shell command taken from a record. Executing it as a side effect of *reading*
would mean that opening a corpus to survey it runs every command in it. So execution is opt-in:

- **Default** — reports `would_run`, the age, and whether the record is stale. `outcome` is `null`,
  exit 0. Nothing is executed and nothing is decided.
- **`--run`** — executes `verified_by` in `--cwd` and returns one of `refresh`, `demote`, `retire`.

The suite proves the default is honest by giving a record a command that would leave a file behind,
and asserting the file does not exist. A guarantee about non-execution asserted by reading the
source would only assert the author's intention.

## What the pass decides

| Command | Outcome | Exit | Rung |
|---|---|---|---|
| exits 0 | `refresh` | 0 | held; `verified_on` moves to today |
| exits non-zero | `demote` | 8 | falls **one** rung |
| exits 127 (unresolvable) | `demote`, reason `unresolvable` | 8 | falls to `observed` |
| exits non-zero at `asserted` | `retire` | 9 | the record is removed, with the reason |

**Why 127 falls to `observed` rather than one rung.** A command that cannot be resolved has not
disproved anything — the fact may be perfectly true. What is gone is the *ability to re-check it*,
which is exactly what the three command-bearing rungs assert. So the record drops to the highest
rung that requires no command, keeping what was actually established.

**Why demotion is one rung and not to the floor.** A `gated` record whose check now fails has lost
its gate, not its reproduction. Dropping it to `asserted` would discard evidence the failure never
touched, and a ladder that collapses on the first failure is a boolean wearing five labels.

**Why `retire` exists.** Demotion at the floor has nowhere to go. A record whose only evidence no
longer holds is not a weak record — it is a false one, and it is read with exactly the confidence of
a true one. Removing it is the outcome, and the reason is recorded with the removal.

## Age flags; the command decides

`--max-age-days` (default 180) marks a record `stale`. Staleness **never** changes the rung — a
record verified in January whose command still passes today is stale and `enforced`, and the pass
says both. The flag means *re-check this*, never *this is wrong*.

The inverse matters more: a record verified yesterday whose command now fails is demoted, freshness
notwithstanding. A date is evidence that somebody looked, and nothing else.

## The index marker

The pass renders `index_marker` — `· gated 2026-08-27` — for the always-loaded memory index, and
**deliberately leaves the command out of it**. The index is read whole into every session in its
scope and holds a 300-character-per-line ceiling (`memory-index-check.sh`, DEC-0053); the record it
links to has no ceiling at all. The expensive half of the pair goes where loading it is free.

Do not hand-assemble the marker. It is rendered so that its shape moves in one place.

## What the pass never does

- It never writes into a memory tier. It reports an outcome; applying it is a separate, visible act.
- It never asks anything. There is no `input(`, no stdin read, and no path that waits — asserted at
  the source level in the suite, because absence of a stop cannot be observed by running the
  program: the case that would prove it is the one that hangs. ADR-0103 settled the same question
  the same way for the loop engine.
- It never re-decides on read. One record, one pass, one outcome; a second reader of the same
  payload gets the same verdict.
