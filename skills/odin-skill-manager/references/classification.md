# Classification — what each class licenses, and how it is derived

The class of a skill is not metadata about its content. It is the answer to one operational
question: **may `vendor-skills.sh --refresh` delete this directory and replace it?**

## Derived every run, from four inputs

`.claude/scripts/lib/skill-provenance.sh` is the one implementation. It reads:

| Input | Where from | What it establishes |
|---|---|---|
| the vend map | `vendor-skills.sh --print-map` (no network, no writes) | an upstream exists and is re-pullable |
| the `FROZEN` list | `vendor-skills.sh` | an upstream existed and is deliberately no longer pulled |
| an `UPSTREAM.md` | the harness copy, **or** the published mirror's copy | the skill was taken from someone and changed here |
| mirror membership | `projects/Odin-Skills/skills/` | Odin publishes it as its own |

Nothing else. There is no second copy of this logic — a script that re-derives a class by
listing a directory is the bug harness:RM-0473 removed, and it left `factory` (a documented
fork) protected by nothing but the absence of a vend line.

## Precedence

```
1. a declared row in .claude/docs/skill-provenance.tsv (with a reason)
2. frozen    — named in FROZEN
3. forked    — an UPSTREAM.md in the harness copy or the mirror copy
4. authored  — a mirror member with no upstream record anywhere
5. vendored  — named in the vend map
6. undetermined
```

**Fork evidence outranks the vend map, and that ordering is the load-bearing line.** A forked
skill is normally still in the map — `rules-distill` is vended from ECC *and* forked here. Put
the map first and the refresh the protect list exists to stop proceeds.

**The mirror is read as evidence, having been demoted from being the definition.** Nine of the
eleven fork records exist only in the mirror's packaging, because `sync-from-odin.sh` excludes
`UPSTREAM.md`, `LICENSE` and `NOTICE` from the sync deliberately — those are the publication's
own artefacts, not the skill's. When the mirror is not populated (a submodule in a fresh clone)
those nine fall through to the declared rows and to rule 5.

## Why `undetermined` exists and is never folded into `authored`

`archon` and `manage-run` arrive through `archon skill install`. On disk they are
indistinguishable from something written here: no upstream claims them, no artefact records
them. Guessing `authored` protects a third-party skill from refresh forever and hides that
nothing knows where it came from. Guessing `vendored` offers it up for overwrite. Neither is a
fact, so the library reports `undetermined` and rc 3 hands the decision to the caller.

`sp_protected_set` **refuses entirely** while any skill is undetermined, rather than returning
a shorter list. A partial protect list is the shape that overwrites exactly the skill nobody
could classify, and it does so with an exit status of 0.

## The declared rows are debts, not records

`.claude/docs/skill-provenance.tsv` holds only what derivation cannot reach:

```
name<TAB>class<TAB>reason[<TAB>unpublished]
```

Every row is a statement that the four inputs were insufficient. A row for an Odin-authored
skill means it has not been published yet — the fix is publication, after which the row is
deleted. Ten such rows existed and were removed the moment their skills became mirror members;
the two that remain are the provisioner-installed pair, which no derivation can reach.

A file that is mostly empty is the intended end state. If it grows, derivation is losing.

## The API

```sh
. .claude/scripts/lib/skill-provenance.sh

sp_class      "$ROOT" <name>     # one class on stdout; rc 3 for undetermined
_sp_class_var "$ROOT" <name>     # same, into $_SP_CLASS — no subshell, for loops over 122 skills
sp_list       "$ROOT"            # name<TAB>class<TAB>origin<TAB>mirrored, every skill
sp_protected_set "$ROOT"         # names a refresh must not touch; refuses on any undetermined
sp_mirror_state  "$ROOT"         # populated | uninitialised | unconfigured | absent
```

`sp_mirror_state` is four-valued and never boolean. "The directory is empty" has three distinct
causes once the mirror is a submodule, and only one of them means the mirror is genuinely gone.

`ODIN_VEND_MAP`, `ODIN_FROZEN`, `ODIN_SP_IGNORE_DECL` and `ODIN_SP_IGNORE_ALL_DECL` exist for
fixtures. A test that shells out to the real script changes meaning the day someone vendors an
unrelated skill.

## The gate

```sh
bash .claude/scripts/skill-provenance-check.sh              # 4 checks, ~386ms, offline
bash .claude/scripts/skill-provenance-check.sh --membership # + every owned skill is published
```

`--membership` is separated because it reads `projects/Odin-Skills/`, which a fresh clone has
not initialised. In `ci-local.sh` both halves run; on `pre-push` only the first, inside a 30s
budget it declares against.
