# The re-arm cycle — the frontier, the wave, and the two questions a close-out never asks

The skill body states the cycle; this file states what each step reads, what it refuses, and what it
deliberately leaves undetermined.

## The channels, in a fixed order

A frontier is the union of open work across channels **the session does not control**. Each is read
in this order, and each can fail to be read — which is `undetermined` (exit 2), never an empty
contribution.

| # | Channel | Read from | Failure is |
|---|---|---|---|
| 1 | roadmap | `.claude/docs/roadmap/roadmap.json`, items whose status is `proposed`, `ready` or `in-progress` | `undetermined` — a missing or unparsable roadmap is not an empty backlog |
| 2 | work-loop | `escalate` records under `.claude/.runtime/work-loop/` | an **absent** directory is not undetermined; an unreadable ledger **is** — see below |
| 3 | campaigns | every `.claude/docs/campaigns/*.json`, for the item ids already claimed | a missing directory is an empty claim set; a manifest that exists and will not parse is `undetermined` |
| 4 | tracker | `gh issue list --state open --json number,title,labels,updatedAt` | `undetermined` — this is the channel most likely to fail quietly |

**Why the tracker's failure is the sharpest.** An unauthenticated `gh` and a tracker with nothing
open produce the same empty list in every format `gh` prints. Reading the first as the second is a
gauntlet reporting that it is finished because it could not look. `--no-tracker` is available and
honest: the frontier then records the channel as `skipped`, never as `read`.

**One row per unit of work.** An open issue already named by an open roadmap item's `links.issues`
is *joined*, not counted twice. An open issue with no roadmap item is its own row, `provenance:
"untriaged"` — which is a finding: route it through `triage`, and it is never placed in a wave.

### The one channel allowed to be absent

The work-loop directory is runtime state under a declared retention class, so it may legitimately not
exist — a fresh checkout has run no loops. Treating that as a channel failure would make every fresh
checkout permanently undetermined. What it costs, stated rather than hidden: **an external blocker
recorded nowhere else is invisible to this reading.** Record it where the reading can see it —
`loop iterate --outcome escalate` with all three of `--blocker`, `--evidence`, `--recommended-next`.

**Absent is the exemption; unreadable is not.** A ledger that exists and will not parse raises
`Undetermined`, exactly as an unparsable campaign manifest does. It used to be skipped, and a
truncated ledger therefore dropped an externally-blocked item back into the assignable set while the
channel still reported `read` — two channels in one file holding opposite policies, the looser one
silently under-reporting blockers.

**Which fields name the blocked item, and when the record expires.** Only `blocker` and `evidence`
are scanned: those describe *what stopped*, while `recommended_next` describes what to do instead,
so an id there names the successor rather than the casualty — a record reading "do RM-1 next
instead" marked RM-1 blocked and left the item the escalation was about assignable. And because
`escalate` is terminal in `work-loop`'s six outcomes, an iteration recorded **after** one means the
loop was re-opened and the record is history; without that rule a blocker never expires and the item
stays blocked until somebody deletes the file.

## Blockedness is derived, and its two senses stay apart

The roadmap engine's statuses are `proposed`, `ready`, `in-progress`, `done`, `dropped`. There is no
`blocked`, deliberately: a stored status can contradict the computed one, which is ADR-0113's
refusal wearing a different hat. So blockedness is computed, from two different channels that mean
two different things:

| Reported as | Read from | Means |
|---|---|---|
| `blocked-by-dep:<id>` | an unmet `deps` edge in the roadmap | the graph's own arithmetic — a sibling item has to land first |
| `blocked-external:…` | a `work-loop` `escalate` record naming the item | a hard external blocker — a missing credential, a failing upstream, a rate limit |

**They are counted apart and never summed.** Collapsing them is how a rate limit gets reported as a
dependency and waited on forever. A blocked item stays *on* the frontier — `endless` is explicit
that a blocked item is not a stopped loop — and is never placed *in* a wave.

## The ordering — quick-win first, every factor naming its field

```
quickwin = gain × reversibility ÷ cost         (confidence is a gate, below)
```

| Factor | Read from | Value |
|---|---|---|
| `gain` | `priority.score` when present, else `tier` | `score ÷ 25`; or `now` 3.0, `next` 2.0, `later` 1.0, `someday` 0.5 |
| `reversibility` | `kind` | `docs`/`ops`/`research` 1.0, `infra` 0.75, `feature`/`page`/`function`/`integration` 0.5, `data` 0.25 |
| `cost` | `acceptance` + `deps` | `1 + len(acceptance) + len(deps)` |
| `confidence` | `acceptance` | **a gate**, not a multiplier — see below |

A **recorded DEC beats a heuristic**: `priority.score` overrides the tier proxy wherever it exists,
and the output says which one it used (`provenance: scored` against `provenance: tier`). Everything
`--explain` prints names the field it read, so an ordering can be argued with rather than trusted.

### Why confidence is a gate rather than a discount

It began as a multiplier — 1.0 with acceptance criteria, 0.4 without. Run against this repository's
own 149 open items it ranked an item with **nothing declared first**: no acceptance also collapsed
`cost` to its floor of 1, so `3.0 × 0.4 ÷ 1` beat a fully-declared item's `3.0 × 1.0 ÷ 3`.
Undeclared work sorted to the top of a quick-win ordering, which is the exact opposite of the
intent.

An item with no checkable definition of done does not have a *cheap* estimate. It has **no**
estimate. So it is emitted `provenance: "underdeclared"`, unscored, sorted last — the honest residue
rather than a number with a haircut. The matrix case is
`QuickwinTest.test_no_acceptance_is_unscored_not_discounted`.

### Declaration coverage is printed on every run

The two proxies are only as good as the fields they read, and both were thin when this was written:
**11 of 149 items declared a surface, 1 of 149 carried a recorded score** (measured 2026-09-03 at
`9054ccad`). Those are not footnotes in a plan doc — `frontier` prints numerator, denominator and
percent on every run, so a reader watches the coverage move without being told what it used to be.
`--metric surface-coverage` and `--metric score-coverage` print the percent alone, which is what
lets a `work-loop` rubric dimension name a command that really produces its number.

**Read the fraction, not the percent.** Appending items that each declare a surface raises the
percentage without any standing item gaining a declaration — measured once at 7.38% → 9.8% where
all four new declarations were on four newly appended rows. Numerator and denominator are both
printed for exactly this reason.

## The wave — the check `endless` states in prose and nothing implemented

`endless` says "diff the surfaces before fanning out — two sessions on one checkout is ADR-0054's
failure". Nothing did. `rearm` does, under two rules:

1. **An item with a declared surface is placed only if that surface intersects nothing already
   placed.** Intersection is deliberately generous — a path-prefix relationship counts, and either
   side's glob is matched against the other's literal. A false *collide* costs one wave of
   parallelism; a false *disjoint* costs a conflicted merge and the serial run the fan-out was
   supposed to replace.
2. **At most one item with an unknown surface per wave.** Two undeclared surfaces cannot be shown
   disjoint, so they are not assumed to be. `surface_of` returns `None` for an item that declares
   nothing, never `[]` — an unknown surface read as an empty one is
   `error-path/unreadable-input-returned-a-substantive-verdict`, and it would clear 138 of 149 items
   nobody looked at.

Also never placed: a blocked item, an item already claimed by a committed campaign manifest, and an
untriaged tracker row.

**The breakdown sums to `deferred`.** The width check runs before the surface checks, so most rows
in a large frontier are held as `wave-full` and never surface-checked at all — which means
`collision=0` is **not** evidence the collision rule fired. Every bucket is reported, including
`held_wave_full` and `held_claimed`, because a breakdown that does not add up reads as a measurement
and is not one: on the real corpus it once accounted for 24 of 149 deferrals and printed
`surface-unknown=4` beside a frontier holding 138 unknown surfaces.

**Why the check reads declared paths rather than prose.** A cheaper predicate exists — do two items
*mention* the same file? — and it is wrong in both directions. Two items whose titles both say
`ci-local.sh` may edit the script and the matrix that tests it, which is disjoint and should be
co-scheduled; two items whose titles share no word at all may both land in `.claude/docs/`. Both
controls are in the matrix (`SurfaceTest.test_negative_control_the_title_predicate_would_fail` and
its converse), and they are what proves this predicate does work the obvious one does not.

The emitted rows are **campaign-shaped**: `worker`, `branch`, `item` (qualified `<roadmap>:<id>`),
`scope`. They carry no key `campaign validate` would refuse — no status, no state, no copied title
or acceptance — because the next thing that happens to them is being copied into a manifest.

## Verify — two questions, deliberately separate

| Question | Answered by | Never re-decided here |
|---|---|---|
| May this batch close? | `campaign close`, **called as a subprocess** | landedness by content, `bl_classify`, the remote-reachability ordering — all `campaign`'s, and a second copy would drift |
| What has appeared since the batch was pinned? | this engine's own frontier | — |

The exit code is the conjunction, and the ordinary result is the interesting one: **a batch can be
legitimately closeable while the frontier has grown.** Run against this repository on 2026-09-03,
`verify` reported the `2026-09-01-gauntlet-controller` campaign closeable *and* 151 items open, and
exited 1. That is the whole thesis in one command — closing a batch is not finishing the gauntlet.

## Exit codes

| Command | 0 | 1 | 2 | 3 | 64 |
|---|---|---|---|---|---|
| `frontier` | the frontier is empty **and** every channel was read | work remains (the ordinary case — a finding, not a failure) | a channel could not be read | — | usage |
| `rearm` | a wave was emitted | — | a channel could not be read | nothing assignable | usage |
| `verify` | the batch may close **and** the frontier is empty | refused — items unlanded, or new work has appeared | a channel could not be read, or `campaign close` returned 2 **or anything outside its own set** | — | usage |

`campaign`'s own set is `0` `1` `2` `64`, and the subprocess runner manufactures `124` for a
timeout and `127` for a missing program. Anything outside `{0, 1, 2}` is **this engine failing to
ask the question**, so it is `undetermined` and names the code. Mapping it to 1 told a caller that
greps nothing that a broken invocation was unlanded work.

`rearm`'s "nothing to assign" is **3 rather than 1** on purpose: it is neither a refusal nor an
error, and a caller that cannot tell it from "a wave was emitted" cannot drive the loop.

## The commands

```sh
cd .claude/skills/gauntlet
python3 -m scripts.gauntlet frontier --root "$PWD/../../.." --explain
python3 -m scripts.gauntlet frontier --root "$PWD/../../.." --no-tracker --metric surface-coverage
python3 -m scripts.gauntlet rearm    --root "$PWD/../../.." --width 4 --json
python3 -m scripts.gauntlet verify   --root "$PWD/../../.." --manifest <manifest> --json
```

`--root` is required and never defaults to the cwd, for the reason `git -C ""` is refused elsewhere
in this harness: an engine handed an empty root does not fail, it silently answers about whatever
tree the process happens to be in. It is resolved to an absolute path once, at the argument
boundary, because `verify` hands it to a subprocess with a different working directory.

## Verifying a change to this skill

```sh
cd .claude/skills/gauntlet && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5
```

Confirm the collected count is **non-zero**. `tests/__init__.py` is what makes discovery work;
without it the suite passes having examined nothing.

## Which roadmap, and which tracker

The frontier is computed for **one** repository's work. When a campaign's work lives somewhere other
than the repository holding its manifest — `projects/<slug>`, its own git repository — the manifest
says so with `project`, and `frontier`, `rearm` and `verify` all follow it:

```sh
python3 -m scripts.gauntlet frontier --root <harness> --manifest <campaign manifest>
python3 -m scripts.gauntlet frontier --root <harness> --roadmap <path>   # the flag wins
```

Two channels follow `project` and two deliberately do not. The **roadmap** and the **tracker** are
the project's; `.claude/docs/campaigns` and the work-loop ledger are the harness's and stay on
`--root`. That split is not cosmetic: reading the roadmap from one repository and the tracker from
another produces a frontier that mixes two backlogs and looks entirely plausible — measured once at
165 project items beside 96 issues from the wrong tracker.

Every failure resolving `project` is `undetermined`, never a fall back to the default. Reporting on
the harness roadmap while the caller believes it read the project's is a confident wrong answer, and
this engine's whole discipline is that "I looked and found nothing" and "I could not look" are
different answers. The one exception is `verify` with an unreadable `--manifest`: it already asks
`campaign close` about that manifest and reports its exit, so raising a second time would shadow the
answer that names the problem.
