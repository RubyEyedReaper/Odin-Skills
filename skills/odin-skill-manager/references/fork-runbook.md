# Fork runbook — turning a vendored skill into one Odin maintains

A fork is a commitment: upstream fixes stop arriving and must be ported by hand, and Odin now
republishes someone else's work under its own monorepo. Take it only when the alternatives lose.

## First, decide against the alternatives

| Option | When it wins |
|---|---|
| **Fix upstream** | the defect is theirs and they take patches. No local cost at all. |
| **Freeze** — add the name to `FROZEN` | the local change is small, or upstream is gone. Says "stop re-pulling this" with no provenance question and no second copy. |
| **Fork** | Odin genuinely maintains it now — the body diverges substantially and is meant to. |
| Hand-edit the vendored body | never. The next refresh reverts it silently. |

Fork and freeze cost the same in ported fixes. The difference is licensing: a fork is published,
a freeze is not.

## The order matters — the edit is last

### 1. Record the fork before touching the body

`.claude/skills/<name>/UPSTREAM.md`:

- the upstream repository and URL;
- **the sha forked from** — without it, no future porter can produce a meaningful diff;
- what changed here and why;
- what a porter must read first.

Written first because an `UPSTREAM.md` is what flips the class. A body edited before the record
exists is a `vendored` skill with local modifications — precisely the state a refresh destroys.

### 2. Verify the class flipped

```sh
. .claude/scripts/lib/skill-provenance.sh
sp_class "$PWD" <name>                          # must print: forked
sp_protected_set "$PWD" | grep -x '<name>'      # must match
```

Fork evidence outranks the vend map, so the skill stays in `--print-map` and is protected anyway.
That precedence is the point; do not remove the vend line to "make it a fork".

### 3. Now edit the body

### 4. Publish it

Forks are mirror members. [membership-runbook.md](membership-runbook.md), plus the artefacts
`validate-skills.sh` requires:

- the upstream `LICENSE` beside the `UPSTREAM.md`, or a literal declaration that upstream
  published none plus a `NOTICE`;
- a `docs/PROVENANCE.md` row naming the upstream, its licence, and the fork sha;
- the upstream in `scripts/public-repos.txt`.

### 5. Verify end to end

```sh
bash .claude/scripts/skill-provenance-check.sh --membership
bash projects/Odin-Skills/scripts/validate-skills.sh
bash .claude/scripts/skill-freshness.sh --deep --only <name>   # must report: protected
```

A fork differs from upstream by construction, so the freshness reporter prints it as `protected`
and never as behind. That is not cosmetic filtering: a report where eleven forks read `behind`
trains its reader to ignore it.

## Un-forking

Rare, and it is a deletion of local work. Remove the `UPSTREAM.md`, confirm `sp_class` reports
`vendored`, refresh, and check the resulting body is one anybody still wants. Record it in
`CHANGELOG.md` — a fork that quietly became vendored again is a set of local fixes nobody knows
were dropped.
