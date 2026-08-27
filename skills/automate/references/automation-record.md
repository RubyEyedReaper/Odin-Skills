# The automation record — ten fields, declared before it exists

An automation with no record is a change nobody agreed to and nobody can withdraw. The record is
written **before** the artifact, in the plan document of the change that introduces it, with a
pointer line in the artifact's own header (`# record: <plan file>`).

**No field is optional.** `rollback` least of all: "delete the file" is a complete value; a blank is
not. A field you cannot fill is a finding — the automation is not ready, and usually the missing
field is `approval` or `retirement predicate`.

## The fields

| # | Field | What it holds | Absent means |
|---|---|---|---|
| 1 | `name` | What the artifact is called, matching the file it becomes | Nobody can find it from the record or the record from it |
| 2 | `trigger` | The recurring action, how often it was actually observed, and where | The automation is justified by an impression. Most `keep-manual` candidates die here |
| 3 | `verdict` | One of `eliminate`, `keep-manual`, `assist`, `automate`, `gate`, `retire` | The derivability question was skipped, which is the one this skill exists to ask |
| 4 | `level` | One of `ad-hoc`, `scratch`, `committed`, `routed`, `gated`, `unattended` | The reach is unstated, so the approval boundary is unstated, so nobody agreed |
| 5 | `derivability` | The redundant-call check's answer **and the named prior artifact** it points at | "I checked" with nothing to check against. See [redundant-call-check.md](redundant-call-check.md) |
| 6 | `approval` | Who agreed, and the evidence — a commit, a review, a plan line | The boundary was named and then not satisfied, which is worse than not naming it |
| 7 | `touches` | The paths and resources it may affect, enumerated | An automation whose reach is "whatever it needs" grows without a second review |
| 8 | `rollback` | The exact command or edit that withdraws it | A permanent change wearing a temporary one's clothes |
| 9 | `retirement predicate` | The observable condition under which the verdict becomes `retire` | It is kept forever, because the reasons to keep it were never written down and the reasons to drop it cannot be recognised |
| 10 | `owner` | Who answers for it when it fires wrongly | It is nobody's, and a failing automation nobody owns gets disabled rather than fixed |

## Rollback by level

The value depends on the level, and every level has one:

| Level | The rollback value looks like |
|---|---|
| `ad-hoc` | The inverse command, written down before the command runs |
| `scratch` | `rm <path>` — and teardown does it anyway |
| `committed` | `git revert <sha>` of the commit that added the script |
| `routed` | Remove the step from the skill or chain; bump the chain's manifest version. The script survives one level down |
| `gated` | Delete its step line from the gate list. The script stays runnable by hand |
| `unattended` | Remove the gate from the one list the nightly wrapper reads. Never by editing a workflow |

## A worked example

```
name:                  changed-rule-namespaces
trigger:               Before every rules edit, three sessions in a row ran the same four
                       greps to find which namespaces a path loads. Observed 2026-08-20,
                       -22, -25; each cost four tool calls and produced identical output.
verdict:               automate
level:                 committed
derivability:          Not derivable. The answer depends on the `paths:` frontmatter in the
                       tree at the moment of the call, and rule files changed between all
                       three observations — staleness beats derivability. Checked against
                       the 2026-08-22 session's own transcript, which held the 08-20 answer
                       and was wrong by one namespace.
approval:              Reviewer of the commit that adds the script (branch review).
touches:               Reads `.claude/rules/**` only. Writes nothing. Prints to stdout.
rollback:              `git revert` of the commit that adds
                       `.claude/scripts/rule-namespaces.sh`. Nothing calls it yet.
retirement predicate:  Retire when rule loading stops being decided by `paths:` frontmatter
                       — the script's whole premise — or when a routing surface starts
                       printing the same answer, whichever comes first.
owner:                 Harness maintainer.
```

Note what the example does **not** do: it does not route the script into a skill, wire it into the
gate list, or run it nightly. Each of those is a further level with a further approval, taken later
if the artifact earns it. Starting at `committed` is the ordinary case; starting higher is the thing
to justify.

## Retiring one

A `retire` verdict is recorded the same way — it names the automation, the predicate that fired, the
evidence that it fired, and the rollback that was run. A retirement with no evidence is an opinion
about an artifact somebody else is still relying on.
