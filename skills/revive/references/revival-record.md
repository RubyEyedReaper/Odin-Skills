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
| `worktree` | An absolute path. Cron has no working directory of yours, and a relative path resolves against whatever `/` cron hands the job. |
| `brief` | Which brief shape the handoff generator uses. |
| `items` | Qualified roadmap ids (`slug:RM-####`). Ids are per-file counters, so a bare one names different work in every roadmap (ADR-0050). |
| `model` | Optional. Omitted means Sonnet. `opus` only where the role's own work is the deep-reasoning kind — a coordinator resolving forks, not a worker executing a plan somebody else wrote. |

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
