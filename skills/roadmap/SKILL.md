---
name: roadmap
description: Use when the user asks what to work on next, wants to start the next thing, adds or tracks a feature, page, function or integration, initializes a project, asks what is left to build, wants work batched into parallel waves or phases, wants competing items prioritized or ranked, or the roadmap needs reconciling against reality.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Skill
---

# Roadmap

## Overview

Standing inventory of everything a project still needs — features, pages, functions,
integrations, infra — plus the dependency graph between them.

`roadmap.json` is canonical; `ROADMAP.md` and `graph.{dot,svg}` are generated.
A script computes the graph; **never compute "what's next" yourself.**

This skill also **owns the hand-offs**: it decides when to grill, when to score, when
one item needs a multi-PR blueprint, and how a wave of items gets executed. Those are
gates with observable predicates below, not suggestions.

## When to use

- "What should I work on next?" / "start the next thing"
- A new feature, page, function or integration is mentioned — record it *first*
- Project initialization, or an existing project with no roadmap
- "What can run in parallel?" / batching work into waves
- More than ~8 items competing for the same slot
- An item finishes, or nothing reconciled in `RECONCILE_AFTER_DAYS` (7) days — ask `due`, never restate it

**Not** for: how to build one item (`superplan`; `blueprint` for multi-PR), phase
narrative (`PLAN.md`), or vocabulary (`CONTEXT.md`, owned by `domain-modeling`).

## Storage

| Scope | Canonical | Generated |
|---|---|---|
| Project | `<root>/docs/roadmap/roadmap.json` | `<root>/ROADMAP.md`, `docs/roadmap/graph.{dot,svg}` |
| Harness | `.claude/docs/roadmap/roadmap.json` | alongside it |

## Engine

Run from this skill's directory: `python3 -m scripts.roadmap <command>`

| Command | Use |
|---|---|
| `next --limit 3` | unblocked set, ordered — the only sanctioned answer |
| `waves --limit 3` | parallel execution layers; wave 0 == `next` |
| `add --title T --kind K` | capture an item |
| `set RM-0007 --status in-progress` | mutate; reports newly-unblocked items |
| `prioritize --export --out spec.json` | RICE decision spec for `decision-matrix` |
| `prioritize --from result.json` | write DEC scores back onto items |
| `validate` | schema, cycles, freshness (exit 1 on error) |
| `render` | regenerate markdown + graph |
| `reconcile` | drift report |
| `due` | is a reconcile overdue? — silent when not, so a caller needs no comparison |
| `bootstrap --from INIT.md --surface-sweep` | seed a new roadmap from project docs + starter surfaces |
| `init --scope task:<slug>` | create an empty roadmap for a scope |

**Never hand-edit `roadmap.json` or `ROADMAP.md`** — hand edits are detected and fail
`validate`. `blocked` is not a status; it is computed from unmet deps.

**Generated files self-heal.** `next`, `waves`, `prioritize` and `reconcile` re-render
`ROADMAP.md` and the graph whenever they no longer match `roadmap.json`, so a project
never reads a stale rendering — including after an out-of-band edit. `validate` still
*reports* staleness instead of hiding it (it is the CI gate), and `--no-render` opts
out for read-only checkouts. Never quote `ROADMAP.md` back to the user without having
run one of the refreshing commands in the same turn.

Entry chains and handoff text: [references/workflows.md](references/workflows.md).
Field reference: [references/roadmap-schema.md](references/roadmap-schema.md).

## The four gates

Between picking an item and merging it, four skills fire on observable predicates.
Nothing here is a matter of taste — check the predicate, invoke the skill.

| Gate | Fires when | Skill |
|---|---|---|
| **Sharpen** | acceptance is thin | `grilling` / `grill-with-docs` |
| **Score** | >8 items compete, or two look equally next | `decision-matrix` (`/decide`) |
| **Decompose** | one item exceeds one PR | `blueprint` |
| **Plan** | always, before source | `superplan` |

### Gate 1 — Sharpen: grill before planning

**Predicate — grill when any holds:** fewer than 2 `acceptance` entries; acceptance
contains an unmeasurable word (*fast, better, nice, robust, seamless, etc.*); no
`links.prd` on a product-facing item; or the item's title is the only description of it.

Use `grill-with-docs` instead of `grilling` when the item introduces a noun that is not
yet in `CONTEXT.md` — the interview then lands the glossary entry and any ADR as it goes.

Write the result back before planning: `set RM-XXXX --acceptance "..." --acceptance "..."`.
An item that survives a grill with unchanged acceptance was already sharp; that is a
pass, not a wasted step. **Planning an item whose acceptance nobody can test is how a
plan gets approved and then rebuilt.**

### Gate 2 — Score: prioritize with the engine, not by feel

**Predicate:** more than ~8 pickable items in the same tier, or the top two entries of
`next` are indistinguishable to you.

```
python3 -m scripts.roadmap prioritize --export --tier now --out /tmp/spec.json
# fill in every null score — the engine refuses an unscored spec on purpose
cd ../decision-matrix && python3 -m scripts.score --spec /tmp/spec.json --record
cd ../roadmap && python3 -m scripts.roadmap prioritize --from /tmp/result.json
```

Scores land in `priority.score` with the `DEC-####` that produced them, so the ordering
in `next` carries its own audit trail. Re-run with different weights to revisit it.

### Gate 3 — Decompose: blueprint when one item is not one PR

**Predicate — blueprint when any holds:** the item's acceptance needs more than ~2 days;
it touches more than one deployable surface (schema + API + UI); it cannot be verified
until several pieces land together; or `superplan` produced more than ~12 steps.

`blueprint` returns numbered construction steps. Register them as children, then work
the children — the parent stays open as the umbrella:

```
python3 -m scripts.roadmap add --title "<step title>" --kind feature \
  --parent RM-XXXX --deps RM-YYYY --plan docs/plans/<blueprint>.md
```

The parent goes `done` only when every child does. **Do not execute a blueprint's steps
without registering them** — unregistered steps are invisible to `next`, `waves`, and to
whoever picks this up after a context reset.

### Gate 4 — Plan: superplan before building, no exceptions

| Rationalization | Reality |
|---|---|
| "This item is tiny" | Tiny items with unexamined deps are how scope leaks |
| "We're behind, skip it" | The plan is what stops a rebuild |
| "A plan already exists" | Only counts if the predicate below holds |
| "User said just do it" | They asked for the item, not for skipping the gate |

**The one exception, as an observable predicate:** `links.plan` names a plan doc
modified in the last 8 hours whose Done criteria cover this item's `acceptance`.
Then go straight to `executing-plans`. Otherwise: `superplan`.

Red flags: editing source with no item `in-progress`; an item that jumped
`proposed` → `done`; a plan doc covering work beyond the item's scope.

## Executing a wave

`waves` groups the pickable set into layers that can run in parallel. A wave is a batch,
and the batch is the unit of planning and verification — not the individual item.

1. **Read the wave.** `waves --limit 2`. Wave 0 is startable now; anything listed under
   *waiting on in-flight work* is not, and no amount of planning changes that.
2. **Plan the whole wave before starting any of it.** Two items in the same wave that
   both touch one file are not parallel — that only shows up when both are planned.
3. **Gate the plan mechanically.** `python3 -m scripts.plancheck <plan.md>` from the
   `blueprint` skill directory: it fails on steps with no files, no verification command,
   no exit criteria, on placeholder tokens, and on a step depending on a later one.
   Fix and re-run until it exits 0. Judgment still comes from the plan-depth rubric —
   the script only catches what a script can.
4. **Execute.** `executing-plans` for one item; `subagent-driven-development` when the
   wave has genuinely independent items and the plans prove they do not collide.
5. **Verify, then close.** `verification-before-completion`, then
   `set RM-XXXX --status done --evidence <sha>` per item.
6. **Gap closure.** Where verification fails, do not reopen the plan wholesale: capture
   each gap as its own child item, plan those, re-run step 3. A gap is a scope discovery,
   and scope discoveries belong in the roadmap.

**Do not start wave N+1 while wave N has an unclosed item.** The wave boundary is where
the dependency graph is actually true; crossing it early is how two agents edit the same
file with two different plans.

## Resuming — no separate state file

The resumable state is already in the roadmap: `status: in-progress` says what was
claimed, `links.plan` says what to read, and `waves` says what came next. On a fresh
session, run `waves`, open the linked plan, continue. Use `/relay` to hand a session off.
Nothing else needs persisting, and a fourth state file is one more thing that can lie.

## Bootstrapping must add starter surfaces

Project docs omit what the author wasn't thinking about. `--surface-sweep [PROFILE]` adds a
profile's starter surfaces as `someday` so they are visible and droppable rather than silently
missing, and names the profile in the summary line.

| Profile | Covers | Use for |
|---|---|---|
| `web` (default; bare `--surface-sweep`) | login, signup, profiles, FAQ, help, blog, news, legal, search, error pages, analytics, admin | a product with a UI |
| `library` | README, API reference, examples, CHANGELOG, versioning and deprecation policy, release process, CONTRIBUTING, CI | a library, plugin or skills repository |

Pick the profile from what the repository *is*, not from what it might grow into — the `web` list
on a plugin repository is thirty-five items for pages it will never have, and each one costs a
reviewer a decision. Flag any item that contradicts an existing ADR rather than silently adding or
skipping it; where no human is watching, record the call in the plan and move on.

Adding a profile is adding a key to `STARTER_SURFACES` in `scripts/roadmap.py`.

## This is a living doc, not a plan

CLAUDE.md item 8 deletes spent plans. **It does not apply here.** Roadmap files are
permanent — when work completes, update status; never delete.

## Maintenance

`reconcile` gathers evidence from git, the tracker, disk, `CHANGELOG.md` and the
render hash. Auto-apply only re-rendering and adding untracked items as `proposed`.
**Promoting to `done` or demoting from it always needs user confirmation** —
silent status rewrites destroy trust in the roadmap.

## Common mistakes

- Answering "what's next" from `PLAN.md` prose instead of `next`
- Quoting `ROADMAP.md` without a refreshing command in the same turn
- Building before recording the item
- Planning an item whose acceptance nobody could test — grill it first
- Executing blueprint steps that were never registered as child items
- Starting wave N+1 with wave N unclosed
- Filing issues at capture time — `to-issues` runs *after* the plan
- Inventing priority scores instead of running the engine
- Citing `RM-####` outside its own roadmap without the slug — ids are per-file counters, so the
  same one names different work in every roadmap. Write `harness:RM-0034` (ADR-0050)
