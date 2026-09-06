---
name: odin-skill-manager
description: Use when a skill enters, changes, or leaves this harness — creating one and registering it, forking a vendored skill, refreshing vendored skills from upstream, publishing an owned skill to the Odin-Skills mirror, retiring one, or answering "is this skill ours". Also on "vendored skill", "upstream skill", "fork a skill", "refresh skills", "skill provenance", "mirror membership", "publish a skill", "is this skill up to date". Owns classification, membership, packaging and freshness; routes authoring to skill-creator and writing-skills.
---

# odin-skill-manager

> A skill's provenance is not a fact about its content. It is a fact about what may be done to it —
> and the only place that fact can live is somewhere a gate can read.

## What this owns, and what it does not

Four skills already own parts of skill work. This one owns what none of them does: **where a skill
came from, whether it may be overwritten, whether it is published, and how far it has drifted.**

| The task | Its owner |
|---|---|
| Writing a new skill's body, frontmatter, references | `skill-creator`, then `writing-skills` |
| Whether a skill's own instructions are being followed | `skill-comply` |
| Finding a skill that already does the thing | `find-skills`, `skill-repo` |
| Whether a new thing duplicates an existing one | `consistency` |
| Distilling recurring skill patterns into rules | `rules-distill` |
| **Classification, mirror membership, packaging, freshness, refresh, publication** | **here** |

Creating a skill is therefore always two steps: `skill-creator` writes it, and this registers it.
A skill that exists but is not registered is invisible to the gate that decides what a refresh may
destroy.

## The four classes

The class is derived on every run by `.claude/scripts/lib/skill-provenance.sh` from four inputs —
the vend map, the `FROZEN` list, an `UPSTREAM.md`, and mirror membership.

| Class | Means | A refresh may overwrite it |
|---|---|---|
| `vendored` | third-party, unmodified here | **yes** — that is the point |
| `forked` | third-party, modified here | no — data loss with no upstream copy |
| `authored` | written here, no upstream exists | no |
| `frozen` | vendored, but upstream is gone or unusable | no — there is nothing to refresh from |

A fifth answer exists and is not a class: **`undetermined`**, rc 3. Nothing claims the skill and
nothing declares it. It is never folded into `authored`, because a skill installed by a provisioner
looks identical on disk to one written here, and guessing either way protects or exposes the wrong
thing. `sp_protected_set` refuses entirely while any skill is undetermined — a partial protect list
is the shape that overwrites exactly the skill nobody could classify.

Precedence, and the one line of it that matters: **fork evidence outranks the vend map**, because a
forked skill is usually still in the map. `rules-distill` is vended from ECC *and* forked here.

## The commands

```sh
bash .claude/scripts/skill-provenance-check.sh                # every skill has a class
bash .claude/scripts/skill-provenance-check.sh --membership   # every owned skill is published
bash .claude/scripts/skill-freshness.sh --quick               # did any upstream move (17 ls-remote)
bash .claude/scripts/skill-freshness.sh --deep                # which skills differ, and by how much
bash .claude/scripts/skill-freshness.sh --deep --only <name>  # one skill
bash .claude/scripts/vendor-skills.sh --print-map             # the upstream map, TSV, no network
bash .claude/scripts/vendor-skills.sh --refresh               # replace vendored skills only
bash projects/Odin-Skills/scripts/sync-from-odin.sh --check   # mirror drift
bash projects/Odin-Skills/scripts/validate-skills.sh          # the mirror's own gate
```

Exit codes are the interface. `skill-freshness` separates **1** (a vendored skill is behind) from
**3** (an upstream could not be read) on purpose: "it moved" and "nobody could tell" are different
sentences, and only one of them is a finding about a skill.

## The five operations

### 1. A new skill

1. `skill-creator` writes it. This skill does not author bodies.
2. Register it: `skill-provenance-check.sh` must pass. An Odin-authored skill classifies as
   `authored` **only once it is a mirror member** — until then it is `undetermined` and needs a
   declared row, which is a debt, not a record.
3. Publish it: [references/membership-runbook.md](references/membership-runbook.md).
4. Route it. A skill nothing names is a skill nothing fires — `skill-registry-coverage.sh` and
   `skill-routing-check.sh` hold that.

### 2. Forking a vendored skill

Full procedure: [references/fork-runbook.md](references/fork-runbook.md). The short form — the
edit is the *last* step, never the first:

1. Decide fork vs freeze. A freeze says "stop re-pulling this"; a fork says "Odin maintains this
   now and republishes it". Publishing someone else's skill has a licensing story; freezing does not.
2. Write `UPSTREAM.md` **before** editing the body: upstream, the sha forked from, and what a porter
   must read first.
3. Verify the class flipped: `sp_class` must report `forked`, and the protect list must contain it.
4. Publish, with the upstream `LICENSE` beside the `UPSTREAM.md` — or, where upstream published
   none, the literal declaration `no LICENSE file accompanied` plus a `NOTICE`.

### 3. Refreshing vendored skills

[references/refresh-runbook.md](references/refresh-runbook.md). Never hand-edit a vendored body:
the next refresh reverts it, silently, and the finding closes while the cost comes back. Two edits
are applied mechanically by `vend()` for exactly that reason — the frontmatter `name:` rewrite, and
stripping `disable-model-invocation: true`.

### 4. Publishing to the mirror

`projects/Odin-Skills/` is a one-way publication of `.claude/skills/`; the harness is
authoritative. A change made in the mirror is destroyed by the next sync. Membership is a rule, not
a list (`odin-skills:ADR-0003`), and `--membership` is its predicate.

### 5. Retiring a skill

Deletion is not enough. Remove it from the vend list **with the reason inline**, or the next run
re-vendors it — `grill-me` was re-created on every run for weeks after being retired. Then: mirror
member removed, registries updated, `CHANGELOG.md` records it.

## Red flags

| Thought | Reality |
|---|---|
| "I'll just patch the vendored skill" | The next refresh reverts it. Fork it, or freeze it, or fix it upstream. |
| "It's ours because it's in the mirror" | Backwards. It is in the mirror because it is ours. That circularity is what harness:RM-0473 removed. |
| "The refresh was clean, nothing broke" | Run `skill-invocability-check.sh`. A refresh reintroduced `disable-model-invocation` on four routed skills in one command. |
| "No diff means up to date" | Only if the comparison used the upstream's own directory name. Guessing by target name misses every renamed skill. |
| "The freshness doc says…" | A document cannot notice that upstream moved. Run `--deep`. |
| "I'll add the provenance row later" | The row is what stops a refresh destroying it. Later is after the refresh. |
| "Publishing is just a copy" | It is a licensing act. `validate-skills.sh` check 6 refuses a fork with no licence artefact, and it is right to. |

## Reference

| Need | Where |
|---|---|
| What each class licenses, and how it is derived | [references/classification.md](references/classification.md) |
| Refreshing without destroying local work | [references/refresh-runbook.md](references/refresh-runbook.md) |
| Adding a member to the published mirror | [references/membership-runbook.md](references/membership-runbook.md) |
| Turning a vendored skill into a fork | [references/fork-runbook.md](references/fork-runbook.md) |
| Declared rows, and why most of them are debts | `.claude/docs/skill-provenance.tsv` |
| The rule half | `.claude/rules/skills/lifecycle.md` |
