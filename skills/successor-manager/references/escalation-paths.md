# Escalation paths

One section per verdict from `scripts/successor-status.sh`. Read the verdict first; the probe's
exit code tells you whether a verdict was claimed at all.

| Probe exit | Meaning | Do |
|---|---|---|
| `0` | every row `live` or `landed` | nothing |
| `1` | findings | the sections below |
| `2` | daemon down | § The daemon is gone — before anything else |
| `3` | a register could not be read | § No verdict was claimed |
| `64` | usage error | the message names the flag that would have answered it |

---

## The daemon is gone — before anything else

Exit `2`. Every session is dead, whatever the registry says, and every row reads `failed` because
no kinder verdict is available. **Do not relaunch anything yet.**

A whole fleet going silent at once is one shared dependency dying, not N agents failing
independently. Name the host cause before spending a launch on it:

```sh
journalctl -k | grep -i oom-killer | tail
docker ps -a                       # a database or service container the fleet all depended on
bash .claude/scripts/fleet-health.sh   # its host report names memory headroom and orphaned MCP servers
```

Then relaunch through `successor`'s Phase 2, from **amended** handoffs, and rewrite each register
row — the new sessions have new ids, and a row pointing at a dead id classifies forever as `failed`.

## No verdict was claimed

Exit `3`. Either the session registry could not be read, or the ownership register could not be.
The message names which.

Nothing here is a verdict, and nothing may be reported as one. Fix the instrument:

- **Session registry unreadable** — `fleet-health.sh` is the owner of that diagnosis; run it alone
  and read its output.
- **Ownership register missing or empty** — an empty register is not a clean fleet. Either nobody
  recorded rows at launch (fix the launch procedure — see
  [ownership-register.md](ownership-register.md) § Writing a row), or `--register` is pointed at the
  wrong directory. A worker's worktree has its own `.claude/.runtime/`, nearly empty; the register
  lives in the checkout the coordinator launches from.

## live

Leave it alone. A `live` verdict means unlanded work on a branch that moved inside the staleness
window, in a session the daemon still knows. There is nothing to do and nothing to report.

Widen `--stale-after` rather than intervening if a worker's natural cadence between pushes is longer
than the default half-hour — a long gate suite is the usual reason. Do not narrow it to catch a
stall sooner; that converts a healthy worker into a false finding and the finding into noise.

## stalled

Unlanded, still in the registry, and its branch has been quiet past the window.

1. **Read before acting.** `claude logs <id>`. A worker waiting on a prompt nobody is there to
   answer, a worker looping, and a worker running a fifteen-minute suite look identical from
   outside and need three different responses.
2. **A missing `settings.local.json` is the most common cause** of the first of those — it is
   gitignored, holds this machine's permissions, and a worktree provisioned without it stalls on
   approvals. Copy it in and the same handoff will work.
3. **Amend the handoff, then relaunch.** The same handoff produces the same stall; that is what
   made it stall. Amend the element that was missing — most often the authorization scope or a
   dependency the worker could not discover — then `claude stop <id>` and relaunch through
   `successor`'s Phase 2.
4. **Rewrite the register row** with the new session id. Reuse the branch, the worktree and the
   reserved ids; only the session id and `launched_at` change.

Before step 3, read § The resume guarantee. A relaunch is a resume, and a resume that re-runs
landed work is worse than the stall.

## failed

Gone from a registry the health gate has just proved current, with nothing landed.

The branch is the deliverable, and it survives the session. Do not delete the worktree yet — an
unfinished branch in a removed worktree is work with no checkout to resume in.

1. `bash .claude/skills/successor-manager/scripts/successor-status.sh --session <id> --json` and
   record the `landedness` field. `unlanded` and `unfetched` are different situations: the second
   means the branch is published but this checkout has never read it.
2. Decide between **resume** and **reassign**. Resume when the branch holds substantial work and the
   handoff was sound; reassign when the handoff was the problem. Either way, § The resume guarantee
   binds what the new session may re-do.
3. Keep the row until the branch lands or is deliberately abandoned. Retiring it deletes the
   evidence for the finding.

## landed

`bl_classify` says the content is in the base. This verdict is independent of the session: a worker
that pushed and died still landed its work, and a worker still running on a branch that has landed
has nothing left to do.

Confirm the roadmap item carries its `evidence` sha — recorded from the **landed** sha, never the
topic-branch sha, because a rebase merge rewrites every one of those. Then teardown, which belongs
to `successor`'s Phase 5: remove the worktree, delete the branch, stop the session, retire the row.

## undetermined

The channels disagreed, or one of them could not be read. **This is not a soft `stalled`, and it is
never resolved by picking the more likely verdict.**

The `landedness` field names which case:

| `landedness` | What it means | Next |
|---|---|---|
| `undetermined` | some commits paired, some did not — `bl_classify` withholds the verdict for the whole ref | A human reads `git range-diff` on the branch. A partly-landed branch is exactly the case where re-running duplicates work. |
| `evidence-unavailable` | `bl_classify` could not look — missing base ref, a git call that errored | Fix the instrument. A missing `origin/main` in the checkout is the usual cause. |
| `unfetched` | published, but no local ref, and this probe does not fetch | Fetch it deliberately in a checkout you own, then re-run the probe. |
| `remote-unreadable` | `git ls-remote` failed | Network or credentials. Nothing about the work is known. |
| `no-branch-recorded` | the register row has no `branch` | Fix the row. The verdict is uncomputable without it. |

**Never resume under an `undetermined` verdict.** The resume guarantee below cannot hold when
landedness is unknown, and re-running a step that already landed is the silent double-application
the guarantee exists to prevent.

---

## The resume guarantee

**Resuming a successor performs zero actions its branch or its roadmap claim already records as
complete.**

Keyed on evidence that survives a rebase merge, because that is how this repository lands:

| Key on | Not on | Because |
|---|---|---|
| the roadmap item's `status` and `evidence` sha | a topic-branch sha recorded at launch | A rebase merge rewrites every sha. The recorded one resolves to nothing, or to something else. `evidence` is recorded from the landed sha (see the roadmap skill). |
| `bl_classify`'s verdict on the branch | `git merge-base --is-ancestor` | Ancestry is a question about shas, landedness about content. Measured: 56 of 110 branches reported "not merged" while fully landed (ADR-0093). |
| both of the above | the session transcript | A transcript records what was *attempted*. A relaunched session has none at all. |

The procedure, before a resumed session does anything:

1. `successor-status.sh --session <id> --json`. If the verdict is `undetermined`, **stop** — see
   above.
2. If `landed`, there is nothing to resume. Retire and move on.
3. If `unlanded`, read the roadmap item. An item whose status is closed with an `evidence` sha is
   done regardless of what the branch looks like; do not re-run it.
4. Write the amended handoff to say **explicitly** which enumerated steps are already complete and
   on what evidence. A successor knows only what its handoff says; a step it is not told is done is
   a step it will do again, confidently.

## The seam: burning without progressing

`stalled` is not the only pathology. A session that is spending steadily and landing nothing is a
different failure with the same appearance from the register's side — its branch is quiet, its
session is live, and this probe classifies it `stalled` on the strength of the quiet branch.

The predicate that distinguishes them is **cumulative spend**, and it is not implemented here.
ADR-0097 establishes it, measured over 29 days and 14,804 transcripts: successor sessions were 41.1%
of all spend, and the cost concentrated in roughly 48 runaway loops rather than in thousands of
expensive sessions — a heaviest-to-median ratio near 9,500×. The context-fullness predicate
`endless` already carries could not fire on any of them, because they sat at about a quarter of the
context ceiling for hundreds of turns, re-reading the same depth.

**That ADR, its `--model` flag and its `session-burn.sh` live on `origin/harness/successor-burn-audit`
(PR #487), and nothing in this skill duplicates them** — a second copy of that meter would conflict
at integration and drift afterwards. What this skill contributes to it is the `model` field in the
register row: a launch tier nobody records is a tier nobody notices reverting, which is exactly how
the measured $0.00 Sonnet share went unnoticed.

When that branch lands, the burn check belongs in this file as a sixth section, and `stalled`
acquires a sibling. Until then, a `stalled` row on a session that is visibly consuming is read by a
human, not by the probe.
