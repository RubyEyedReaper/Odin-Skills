# Refresh runbook — replacing vendored skills without destroying local work

`vendor-skills.sh --refresh` is `rm -rf` followed by `cp -R`, per skill. For anything Odin
authored or forked that is data loss with no upstream copy to recover from. The protect list is
therefore the whole safety story, and it is derived — never typed.

## Before

```sh
bash .claude/scripts/skill-provenance-check.sh    # must exit 0
bash .claude/scripts/skill-freshness.sh --deep    # which skills actually differ, and by how many files
```

A refresh run without the deep pass is a refresh whose result cannot be checked: `--refresh`
reports what it replaced, not what changed, and 58 of 76 replacements are routinely byte-identical.

If the provenance gate does not exit 0, **stop.** `sp_protected_set` refuses while any skill is
undetermined, so the refresh either aborts or — worse, in an older shape — proceeds with a
shorter list.

## The run

```sh
bash .claude/scripts/vendor-skills.sh --refresh
```

It replaces `vendored` skills only. `forked`, `authored` and `frozen` are protected by class.

Two edits are applied mechanically by `vend()` on every vend, and both exist because a
hand-patch is what a refresh silently reverts:

| Edit | Without it |
|---|---|
| rewrite frontmatter `name:` to the directory name | the skill registers under upstream's name and every route to it misses |
| strip `disable-model-invocation: true` | the `Skill` tool refuses to invoke it — routed by four registries, invocable by none |

Both are reapplied every time, so the differences they create are **permanent**.
`skill-freshness.sh` normalises those two lines away before declaring staleness; otherwise six
skills read `behind(1)` forever, and a row that can never be cleared is a row a reader learns to
skip.

## After — the checks that catch what the diff does not

```sh
bash .claude/scripts/skill-invocability-check.sh    # nothing carries disable-model-invocation
bash .claude/scripts/skill-registry-coverage.sh     # every skill is still reachable
bash .claude/scripts/skill-routing-check.sh
bash .claude/scripts/skill-provenance-check.sh
bash .claude/scripts/skill-freshness.sh --deep      # nothing left behind
bash projects/Odin-Skills/scripts/sync-from-odin.sh --check
bash .claude/scripts/harness-audit.sh
```

Invocability is not optional. One refresh reintroduced `disable-model-invocation: true` on four
live routes at once (`setup-matt-pocock-skills`, `improve-codebase-architecture`, `teach`,
`triage`) — upstream added it, the diff looked ordinary, and the skills went silently unusable.

## The two checks a diff does not give you

A refresh replaces a skill wholesale, so **anything Odin added or repaired inside a vendored skill
disappears without a conflict**. Two commands find that, and both are cheap. Run them against the
refresh commit before anything else looks green:

```sh
R=<the refresh commit>

# 1. What it DELETED. An added file leaves no trace in a diff you read top-down.
git diff --diff-filter=D --name-only "$R^" "$R" -- .claude/skills

# 2. What it OVERWROTE. Odin's edits carry markers — an issue id, an ADR, a DEC — so a file whose
#    marker count DROPPED is a file whose local repairs went with the replacement.
for f in $(git diff --diff-filter=M --name-only "$R^" "$R" -- .claude/skills); do
  b=$(git show "$R^:$f" | grep -cE 'harness:RM-|ADR-0|DEC-0')
  a=$(git show "$R:$f"  | grep -cE 'harness:RM-|ADR-0|DEC-0')
  [ "$b" -gt "$a" ] && echo "$f  markers $b -> $a"
done
```

Measured on the 2026-09-06 refresh: two deletions (`skill-comply/tests/__init__.py` and its
`.gitignore`, which broke `py_tests` discovery) and two overwritten files (seven pipefail repairs in
`skill-repo` and one in `automated-assessment`). The marker scan and the gates found the same two
files independently, which is what makes the scan worth running: it names the loss *before* a gate
has to.

The repair is never "re-apply and move on" — re-applying restores the code and leaves the next
refresh free to revert it again. **Freeze the skill in the same change**, so the declaration exists
where the refresh reads it.

Check for dangling symlinks too. `ui-ux-pro-max` previously shipped `data/` and `scripts/` as
broken links; a skill whose scripts do not resolve fails at the moment someone needs it.

## Never hand-edit a vendored body

The next refresh reverts it, with no error and no conflict. The finding closes and the cost comes
back. Three legitimate routes:

1. **Fix it upstream** and re-vend. Best when the defect is theirs.
2. **Fork it** — [fork-runbook.md](fork-runbook.md). Odin maintains it from then on.
3. **Freeze it** — add the name to `FROZEN` in `vendor-skills.sh`, with the reason inline. Says
   "stop re-pulling this" without the provenance question or the duplicate copy that publishing
   someone else's skill creates.

The cost of a freeze is that upstream fixes stop arriving and must be ported by hand. Fork and
freeze both cost that; only the licensing story differs.

## Retiring a vendored skill

Deleting the directory is not enough. Remove the vend line **with the reason inline**, or the
next run re-creates it — `grill-me` was re-vendored on every run for weeks after being retired.
Then: mirror member removed if it had one, registries updated, `CHANGELOG.md` records it.

## Periodic

`local-nightly.sh` runs `skill-freshness.sh --quick` — 17 `ls-remote` calls, seconds, no clone.
It answers "did any upstream move", never "which skills differ". Neither tier belongs in a gate:
both read the network, and a suite whose verdict depends on the network is
`ci/testing.md` § *a case's verdict must not depend on state it did not establish*.
