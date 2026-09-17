# The revival manifest — field by field

One JSON document per campaign, committed at `.claude/docs/revival/<slug>.json`. Validated by
`.claude/scripts/revival-manifest-check.sh`, which is in the gate list, so a malformed manifest fails
the suite rather than failing silently at 21:00 on a Monday.

```json
{
  "revival": "2026-08-28-harness-remediation",
  "campaign": "2026-08-28-harness-remediation",
  "not_before": "2026-08-31T21:00:00-04:00",
  "tick_minutes": 20,
  "roles": [
    {
      "role": "audit fixer coordinator",
      "kind": "coordinator",
      "branch": "harness/remediation-coord-r3",
      "worktree": "/home/dell/Documents/Repos/odin-wt-fix-coord",
      "brief": "coordinator",
      "model": "opus",
      "model_reason": "A campaign coordinator integrates several workers' branches and resolves conflicts across them",
      "items": ["harness:RM-0262", "harness:RM-0349"]
    }
  ]
}
```

## Top level

| Field | Why it is here |
|---|---|
| `revival` | The manifest's own name. Distinct from `campaign` because one campaign could one day be armed twice with different windows, and a file that cannot name itself cannot be reported on. |
| `campaign` | The slug of a manifest under `.claude/docs/campaigns/`. **Referenced, never copied.** The engine asks that manifest's engine what is open; a copied item list drifts and nothing detects it. |
| `not_before` | An ISO-8601 instant **with an explicit UTC offset**. This is the whole scheduling decision, and it lives here rather than in the crontab so it can be read, reviewed and changed without touching a schedule. |
| `tick_minutes` | How often the schedule looks. Not how often anything happens — the preconditions decide that. |
| `roles` | One row per session the campaign runs. |

### Why the offset is mandatory

`2026-08-31T21:00:00` names a different instant on every host that reads it, and the host that reads
this one is a cron job with no `TZ` in its environment. The validator refuses a bare local time
rather than guessing, because the guess is invisible and wrong by hours.

## A role

| Field | Why it is here |
|---|---|
| `role` | The display name the session was launched with. This is what the engine matches against the daemon roster's `name`, so it must be exactly the string passed to `odin-relay.sh --name`. |
| `kind` | `coordinator`, `monitor` or `worker`. Exactly one `coordinator` per manifest — two would provision the same worktrees. |
| `branch` | The branch this role owns. Written into the generated handoff's `active_branch` and its authorization scope. |
| `worktree` | An absolute path. Cron has no working directory of yours, and a relative path resolves against whatever `/` cron hands the job. The revived session is launched **in** it (`odin-relay.sh --cwd`), and the generated handoff declares it as `worktree:` so the relay refuses a launch anywhere else (#1471). A coordinator's `worktree` also decides which copy of this manifest the schedule trusts — see below. |
| `brief` | Which brief shape the handoff generator uses. |
| `items` | Qualified roadmap ids (`slug:RM-####`). Ids are per-file counters, so a bare one names different work in every roadmap (ADR-0050). |
| `model` | Optional. Omitted means Sonnet. `opus` only where the role's own work is the deep-reasoning kind — a coordinator resolving forks, not a worker executing a plan somebody else wrote. One of `sonnet`, `opus`, `haiku`. |
| `model_reason` | **Required when `model` is anything but `sonnet`.** What about this role's own work needs that tier. The engine writes it into the generated handoff, because `odin-relay.sh` refuses a non-default tier that does not say why — and before this field existed that refusal ended every opus revival: 567 ticks, zero launches (#1307). The validator and the engine both refuse its absence, so the failure names the manifest rather than a generated file. |

## Where the schedule finds a manifest

Not in one checkout. Cron runs `revival-tick.sh` from whatever checkout the crontab names, and that
checkout holds whatever branch it last held — measured 527 commits behind `main` on the day this
was written, blind to a manifest landed on `main` and to one committed on a campaign branch (#1442).
So the tick enumerates **every registered worktree** (`git worktree list`) and reads each one's
`.claude/docs/revival/*.json` (DEC-0184). `revival-tick.sh --list` prints what it found, and
`revival-cron.sh status` reads that same list.

Copies of one manifest are keyed on `revival`, and worktrees cut at different moments hold different
revisions of it, so which copy counts is a rule rather than a race:

1. A copy inside the worktree **its own coordinator role names** is authoritative.
2. Identical copies are one manifest.
3. Differing copies resolve to the one whose **last commit descends from every other variant's** —
   the later revision of one file. A coordinator that moved worktrees leaves exactly this shape.
4. Anything else — an uncommitted copy, revisions on divergent branches — is **refused**, every path
   named, exit 1. Never "the first one found".

The engine runs with the chosen copy's tree as its root, so the campaign manifest and the handoff it
generates come from the same tree. A worktree listing git cannot produce exits 3 and launches nothing.

**Which code runs is still the crontab's checkout.** Discovery fixes what the schedule can see, not
which revision of the tick executes; `revival-cron.sh status` prints that checkout and how far behind
`origin/main` it sits.

## What the manifest must never hold

**A status, under any of its names.** `status`, `state`, `progress`, `last_seen`, `session_id` are
refused **at any depth** — not merely at the top level, because the field somebody actually adds is a
note inside a role row: *"progress": "wave 2 done"*.

The reason is not tidiness. A status is a claim that was true when it was typed, and it goes stale in
silence: the file reads identically whether it is current or six hours old. This repository has the
measurement — in one backlog burn-down, 31 of 43 issues examined were already fixed on `main` while
the tracker still said otherwise. `campaign` refuses a stored status for exactly this reason
(ADR-0113), and a second file that could carry one needs the same refusal or the rule erodes at the
first convenient moment.

Every transient fact is therefore measured at fire time:

| The question | Answered by, at fire time |
|---|---|
| Is the bridge up? | `~/.claude/daemon.lock` pid + `procStart`, and a control socket on disk |
| Is the daemon alive? | `.claude/scripts/fleet-health.sh` |
| Which sessions exist? | `~/.claude/daemon/roster.json` |
| What is still open? | the `campaign` engine's `status` |
| Where are the branches? | `git ls-remote` |
| Which worktrees exist? | `git worktree list` |

### Which tree each channel reads

Discovery (above) hands `fleet-revive.sh` the manifest's own tree as its positional `ROOT` in the
scheduled path. But `ROOT` is also the engine's **own** checkout when the script is invoked
directly — its documented CLI form, and the shape a bug reproduction takes (#1474). Two different
questions get asked of two different trees, and conflating them is the defect this row exists to
name:

| Channel | Resolves against |
|---|---|
| Bridge lock, daemon roster, session listing | host-global paths (`ODIN_REVIVAL_LOCK` / `ODIN_REVIVAL_ROSTER` / the agents command) — not tree-scoped at all |
| The manifest's `not_before`, `roles`, `model`/`model_reason` | the manifest file itself, wherever discovery found it |
| Campaign open-item count | the manifest's **own repository** — `$ROOT` when the manifest already resolves inside it, else `git -C <manifest's directory> rev-parse --show-toplevel` (#1474) — never `$ROOT` unconditionally |
| Remote branch tips, `git worktree list`, the relay, the generated handoff's directory | the engine's own `$ROOT` — these are about the engine's checkout, not the campaign's data |

A revival manifest discovered in a campaign worktree names a campaign whose manifest and roadmap
items are committed on that worktree's own branch, and are not necessarily on the engine's. Reading
the open-item count from `$ROOT` in that case reads a tree that has never heard of the campaign —
"campaign undetermined", forever, because the same tick runs again with the same wrong root next
time. The fix is unconditional: it holds whether the engine was invoked through `revival-tick.sh`'s
discovery (which already, in the common case, hands it the right tree) or directly, naming a
manifest that lives somewhere else entirely.

## What a role claim adds, and why the roster is not enough

`.claude/hooks/odin-role-claim.sh` writes `.claude/.runtime/revival/<session-id>.tsv` at
`SessionStart` — session id, role name, cwd, branch, head, instant.

The roster already holds most of that, and the roster is the right channel for **liveness** because
it is outside the subject's control. It is also transient: it lives under `/tmp` and `~/.claude`, and
it does not survive every daemon restart. A revival happening after one is looking at a roster with
no memory of what was running, which is exactly the moment identity matters. The roster answers *who
is alive*; the claim answers *who was here*.

Both are runtime state under `.claude/.runtime/`, gitignored and swept with their retention class.
Neither is committed, and neither is authoritative about the plan — that is this manifest's job.
