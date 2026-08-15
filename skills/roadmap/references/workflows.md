# Roadmap workflows

Four entry paths plus the wave loop. Each names the skills to invoke and the exact
handoff text.

---

## (a) Project initialization

```
brainstorming (only if intent is fuzzy)
  -> INIT.md written (goal / in scope / out of scope / stack locked)
  -> roadmap bootstrap --from INIT.md --from PLAN.md --surface-sweep
  -> review every derived item with the user
  -> decision-matrix (RICE) when more than ~8 items compete
  -> roadmap validate && roadmap render
  -> superplan on the top `tier: now` item
```

`bootstrap` mines markdown bullets and maps headings to tiers ("out of scope" and
"deferred" become `someday`; "phase 1" / "current" become `now`).

**`--from` paths resolve against the roadmap's root**, not the working directory — so the command
above works unchanged from inside the skill directory, which is where every documented invocation
runs it. An absolute path is taken as given. If **every** named source is unreadable the command
exits 1 and writes nothing: a bootstrap that read no source is a failed bootstrap, not an empty
success, and `--surface-sweep` does not excuse a mistyped path.

**`--surface-sweep` is not optional for a product.** Project docs describe what the
author was thinking about; they systematically omit the surfaces every web product
eventually needs — login, signup, password reset, profiles, account settings, FAQ,
help, blog, news, about, pricing, contact, terms, privacy, cookie consent, search,
error pages, transactional email, analytics, error monitoring, rate limiting, admin,
audit log. The flag adds them as `someday` / `proposed` so they are *visible and
droppable* rather than silently missing.

**It takes a profile**, because that list is wrong for a repository that ships no UI:

```
roadmap bootstrap --from INIT.md --surface-sweep            # web (the default)
roadmap bootstrap --from README.md --surface-sweep library  # docs, release, contribution, CI
```

The profile appears in the summary line and in each item's `notes`, so a wrong one is visible at a
glance rather than after thirty-five items land. An unknown profile is refused, listing what exists.

Starter-surface items are explicitly marked "confirm or drop" in `notes`. Walk them with the
user. Dropping one is a decision; never omitting it is the point.

**Watch for collisions with existing ADRs.** If a project decided something the
sweep contradicts — anonymous-first access versus a login page, say — do not
silently add or silently skip. Surface it: "ADR-000N chose X; these sweep items
assume accounts. Keep as `someday`, or drop?"

For an **existing** project, bootstrap in reconcile mode: mine `PLAN.md` phases,
`INIT.md`, `docs/adr/`, `CHANGELOG.md` (shipped work seeds `done` items) and open
issues, then present the derived set for confirmation before writing.

---

## (b) Start working on the next thing

```
hook injects <roadmap> next-up
  -> roadmap next --limit 3          (re-renders ROADMAP.md if it drifted)
  -> present each with dep evidence + links
  -> more than ~8 competing?     -> GATE 2: roadmap prioritize  (see (e))
  -> AskUserQuestion to choose  (skip only if exactly one unblocked item exists)
  -> roadmap set RM-XXXX --status in-progress
  -> acceptance thin?           -> GATE 1: grilling / grill-with-docs
                                   -> roadmap set RM-XXXX --acceptance ... --acceptance ...
  -> bigger than one PR?        -> GATE 3: blueprint -> register children (see (c))
  -> superplan                     GATE 4 (MANDATORY — see the gate in SKILL.md)
  -> roadmap set RM-XXXX --plan <path>
  -> plancheck the plan            (blueprint/scripts/plancheck.py, exit 0 required)
  -> human approval
  -> executing-plans  /  subagent-driven-development
```

### Handoff brief to `grilling` / `grill-with-docs`

```
Stress-test roadmap item RM-XXXX (<kind>): <title>.
Current acceptance: <acceptance[]>  — treat every unmeasurable word as unresolved.
Deps already satisfied: RM-YYYY (<their titles>).
Out of bounds: sibling roadmap items, and anything an existing ADR already decided.
Goal of this interview: acceptance criteria a reviewer could test without asking me
anything, plus any glossary term this item introduces.
```

### Handoff brief to `superplan`

```
Roadmap item RM-XXXX (<kind>): <title>.
Deps satisfied: RM-YYYY (<their titles>).
Acceptance: <acceptance[]>.
Links: PRD <prd>, ADR <adr>, files <links.files>.
Project root: <root>.
Do not exceed this item's scope — sibling roadmap items are out of bounds.
```

### Handoff brief to `blueprint`

```
Roadmap item RM-XXXX (<kind>): <title> — too large for one PR because <reason>.
Acceptance the whole effort must satisfy: <acceptance[]>.
Already built and off limits: <done items this depends on>.
Produce one-PR steps with dependency edges; each step must be executable cold.
Every step comes back as a child roadmap item (--parent RM-XXXX) before any of it runs.
```

---

## (c) A new thing is mentioned mid-project

```
roadmap add --title "<T>" --kind <K>          <- FIRST, always, one line
  -> product-facing and non-trivial?  -> to-prd  -> roadmap set --prd #NN --status ready
  -> intent fuzzy?                    -> brainstorming -> back to roadmap set
  -> when picked up                   -> path (b)
  -> plan too big for one PR?         -> to-issues on the PLAN, not the item
                                          slices become child items (--parent RM-XXXX)
                                          -> roadmap set --issues "#12,#13"
  -> item too big for one superplan?  -> blueprint for that ONE item
                                          its steps register as child items:
                                          roadmap add --title "<step>" --kind feature \
                                            --parent RM-XXXX --deps RM-YYYY \
                                            --plan docs/plans/<blueprint>.md
                                          parent goes done only when every child does
```

Capture costs one command. Do it before discussing feasibility — an idea that is
not recorded is an idea that gets rebuilt from scratch in three weeks.

**`to-issues` runs after the plan, never at capture time.** Bulk pre-filing floods
the tracker and creates exactly the duplicates that `to-issues`' own dedupe step
exists to prevent.

---

## (d) An item completes

```
verification-before-completion
  -> roadmap set RM-XXXX --status done --evidence <sha|PR#>
  -> architecture-decision-records if a hard-to-reverse decision landed
                                    -> roadmap set --adr ADR-00NN
  -> project CHANGELOG.md entry     (CHANGELOG stays the canonical change ledger)
  -> roadmap render
  -> roadmap reconcile
  -> report newly-unblocked items to the user
```

`set --status done` already prints what became unblocked. Pass that on — it is the
natural place to offer the next item.

---

## (e) Prioritising a crowded tier

```
roadmap prioritize --export --tier now --out /tmp/spec.json
  -> fill in every null score          (the engine rejects an unscored spec)
  -> decision-matrix: python3 -m scripts.score --spec /tmp/spec.json --record > result.json
  -> roadmap prioritize --from result.json
  -> roadmap next                      (ordering now carries its DEC reference)
```

Scores are elicited the way `grilling` elicits anything: one criterion at a time, with a
recommended value, and by reading the codebase rather than asking when the answer is on
disk. Never fill the nulls with numbers that "look about right" — an invented score is
worse than no prioritisation, because it launders a guess as arithmetic.

The DEC id lands in each item's `priority.dec`, so the ordering can be re-derived,
re-weighted, or challenged later. Re-running with different weights is a normal act, not
an admission that the first run was wrong.

---

## (f) Executing a wave

```
roadmap waves --limit 2
  -> wave 0 is startable now; "waiting on in-flight work" is not
  -> plan EVERY item in the wave before starting any of it
  -> plancheck each plan (blueprint/scripts/plancheck.py) until exit 0
  -> two plans touching one file are not parallel — resequence into separate waves
  -> execute: executing-plans (one item) / subagent-driven-development (proven-independent)
  -> verification-before-completion per item
  -> roadmap set RM-XXXX --status done --evidence <sha>
  -> verification gaps become CHILD items, planned and re-checked — never an
     informal "fix it up" pass on the closed plan
  -> only when the wave is empty: roadmap waves again
```

**The wave boundary is where the dependency graph is actually true.** Starting wave N+1
early is how two agents edit one file from two plans that never saw each other.

---

## Boundaries with neighbouring skills

| Skill | Owns | Roadmap does not |
|---|---|---|
| `superplan` | How one item gets built, this session | plan implementations |
| `blueprint` | A bounded multi-PR construction plan for one effort | sequence PRs |
| `writing-plans` | Spec → step plan | write plans |
| `grilling` / `grill-with-docs` | Interrogating an item until its acceptance is testable | interview |
| `to-prd` | Product requirements as a tracker issue | define requirements |
| `to-issues` | Tracer-bullet slices in the tracker | file issues at capture |
| `decision-matrix` | Weighted scoring of options | invent scores |
| `executing-plans` / `subagent-driven-development` | Running a plan | execute |
| `domain-modeling` | `CONTEXT.md` glossary | define vocabulary |
| `PLAN.md` | Narrative of the current phase | narrate |

`roadmap` owns the *sequencing* — which items exist, which are unblocked, which wave they
fall in, and which gate fires next. Every other skill in that table owns one step and
hands control back. Waves and blocked/unblocked state are computed here and nowhere else;
a skill that re-derives them from prose has already gone wrong.

`roadmap` owns *what exists to be built, across every session*. `blueprint` owns
*how one multi-PR effort gets built*. When a roadmap item is too large for a single
`superplan`, it delegates to `blueprint`, and blueprint's steps come back as child
roadmap items.

---

## Reconciliation

Triggers: the skill is invoked and `last_reconcile` is 7+ days old; immediately
after an item goes `done`; at bootstrap; or on demand. **Never per turn.**

The 7 is `reconcile.RECONCILE_AFTER_DAYS`, and it is the engine's to state. Consumers ask
`roadmap due`, which prints the notice or nothing at all; none of them carry a copy of the
threshold or the date arithmetic (ADR-0048 — a bash copy at 14 once shadowed this line, so
the documented trigger never fired).

Evidence sources — git commits intersected with `links.files`; issue tracker state;
a **surface sweep** (below); `CHANGELOG.md` entries with no `RM-####` reference; the
render hash.

The sweep answers "what exists on disk that no item claims?" — the mirror of the
`false-done` check. It enumerates with `git ls-files --cached --others
--exclude-standard`, so `.gitignore` is honoured by the tool that defines it and a
**nested repository is one entry, never walked into**. Paths fold to a directory two
levels under each configured root, are filtered through the same `claims()` predicate
`analyze` uses, sorted, and capped at 10 per run — the remainder reported as a count
rather than dropped in silence.

Roots come from `--surface-root`, else `surface_roots` in the doc, else the conventional
source directories (`src app apps packages lib services`) that actually exist. A repo
with none of them sweeps nothing, which is why a harness roadmap is quiet by default.
`--no-git` disables the sweep: there is deliberately no filesystem fallback, because a
hand-written ignore list reports a different set of paths than git — and under
`--apply-auto` that difference becomes items.

| Finding | Auto-applies? |
|---|---|
| `md-stale` — regenerate | yes |
| `untracked-issue` / `untracked-surface` — add as `proposed` | yes |
| `issue-closed` — propose `done` | **no, confirm** |
| `false-done` — files vanished | **no, confirm** |
| `stale-item` — in-progress 14+ days, no commits | **no, confirm** |
| `unrecorded-change` — CHANGELOG entry with no item | **no, confirm** |

"Auto-applies" means **under `--apply-auto`** — a bare `reconcile` reports and
re-renders, and never adds an item. `md-stale` is applied by the re-render, which
happens on every run. The other two add a `proposed` item whose `notes` name
reconcile as its source and whose `links` carry the evidence that made the finding
fire, so a second run sees the drift as tracked instead of adding a duplicate.
`--no-render` (read-only checkouts, CI) applies nothing at all.

An added item is still an item nobody chose: it lands `proposed`, to be confirmed,
reassigned to an existing item, or dropped.

Anything that promotes to `done` or demotes away from it needs a human. Silent
status rewrites are how a roadmap loses the user's trust permanently.
