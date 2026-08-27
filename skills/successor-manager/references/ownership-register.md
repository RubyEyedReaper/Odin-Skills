# The ownership register

One delegated session, one file:

```
.claude/.runtime/successor-register/<session-id>
```

`key<TAB>value` lines, one per field, order-immaterial, `#` comments and blank lines ignored. The
directory is gitignored — the register is runtime state, not a committed artifact.

**Why a file per session rather than one table.** One writer per file, by construction. A single
appended table is written by a coordinator at every launch and read by anything at any time, and two
coordinators launching into one campaign is the ordinary case, not the exotic one. The `key<TAB>value`
shape rather than fixed columns for the same reason a schema outlives its first version: a field
added later must not renumber the fields already there.

## The row

| Field | Records | Why it is here |
|---|---|---|
| `session_id` | the id `claude agents` knows the session by | The join key. Membership of the registry's id set is one of the three signals, and without this there is nothing to look up. Defaults to the filename if omitted. |
| `worker` | the human-readable name passed at launch | What a report calls it. An id is not something a person can hold in their head across a fleet. |
| `branch` | the topic branch the worker pushes to | The other two signals are both questions about this branch. A row without it can only ever be `undetermined`, and the probe says so rather than guessing. |
| `worktree` | absolute path to the worker's checkout | Where to look when a verdict needs a human. Also what teardown removes — a spent worktree left registered keeps the concurrency guard armed against the main checkout (ADR-0054). |
| `scope` | the declared `edit only:` paths, verbatim from the handoff | Integration scope-diffs the branch against this. A file outside it is a finding, not a merge. Recording it here means the check does not depend on the handoff file still existing. |
| `reserved_ids` | ADR, DEC and roadmap ids allocated to this worker | Ids are allocated by reading a ledger, so parallel workers reading one ledger all win and the collision surfaces at integration, where it is most expensive. Written down at launch, the overlap is visible before it is paid for. |
| `handoff` | absolute path to the brief it was launched from | A stalled session is relaunched from an **amended** handoff — the same one produces the same stall. This is what gets amended. Absolute, because a worker in another worktree cannot resolve a relative path. |
| `integrator` | who lands this branch | Workers never merge, and integration is serialized. A row whose integrator is nobody is a branch that will sit green and unlanded. |
| `model` | the tier the session was launched on | A measured $0.00 Sonnet share across 4,915 successor sessions was an absent flag, not a preference, and absent flags fail silently and forever (ADR-0097, landed in PR #487). A launch tier nobody records is one nobody notices reverting. |
| `launched_at` | unix seconds at launch | The staleness fallback when a branch has no commits yet, so a worker in its first minutes is not read as stalled. |
| `launch_sha` | the base sha the branch was cut from | Branch **movement** is this sha against the published one. Without it, "has this worker done anything" has no answer that does not involve trusting the worker. |

## Retirement — an explicit act, never an age sweep

A row is removed when its work is done: the branch is `landed`, the worktree is removed, and the
session is stopped. That is teardown, and teardown belongs to `successor`.

**No retention class is declared for this directory, and declaring one would be wrong.**
`runtime-retention.sh` sweeps its session-keyed classes by deleting a file whose session id is no
longer in the fleet registry — which is precisely the moment a `failed` verdict becomes readable.
A session gone from a healthy registry with nothing landed *is* the finding; a sweep keyed on its
disappearance would delete the evidence at the instant it was earned. So the register is a
**deliverable**, like `handoff/`, not a counter, and the sweeper's existing behaviour — an
unrecognised directory is left alone, which it has a gate case asserting — is the correct one here.

The cost, stated because a design's residue belongs in the open: rows accumulate if nobody retires
them. The probe makes that visible rather than tidy — a long-retired worker still holding a row
shows up on every run, which is a nag, and a nag is the intended pressure.

## Writing a row

```sh
reg=.claude/.runtime/successor-register
mkdir -p "$reg"
{
  printf 'session_id\t%s\n'  "$sid"
  printf 'worker\t%s\n'      "$name"
  printf 'branch\t%s\n'      "$branch"
  printf 'worktree\t%s\n'    "$wt"
  printf 'scope\t%s\n'       "$scope"
  printf 'reserved_ids\t%s\n' "$ids"
  printf 'handoff\t%s\n'     "$handoff"
  printf 'integrator\t%s\n'  "$integrator"
  printf 'model\t%s\n'       "$model"
  printf 'launched_at\t%s\n' "$(date +%s)"
  printf 'launch_sha\t%s\n'  "$(git -C "$wt" rev-parse origin/main)"
} > "$reg/$sid"
```

Written at launch, in the same breath as the launch. A row recorded afterwards is a row that is
missing for exactly as long as it takes something to go wrong.

Reading the rows back, and what each verdict obliges you to do, is
[escalation-paths.md](escalation-paths.md).
