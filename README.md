# Odin-Skills

The skills the Odin harness **owns** — authored here, or forked from an upstream and modified —
packaged as one installable Claude Code plugin. The split is derived rather than restated: run
`ls skills/*/UPSTREAM.md | wc -l` for the forks and `ls -d skills/*/ | wc -l` for the whole set. The harness itself is a
private repository, so it is named here rather than linked.

Odin vendors far more than it owns; the rest is third-party work it has never modified, and that
is not redistributed here. This repository is only the part Odin is actually the author or the
maintainer of.

## What's in it

Every skill Odin **authored** or **forked and maintains**. Membership is a rule, not a list
([`adr/0003`](docs/adr/0003-mirror-membership-rule.md)) — so neither the names nor the count are
typed here, because both drifted the moment a skill landed and nobody hand-edited this paragraph.
Read them from disk:

```sh
ls -d skills/*/ | wc -l                                  # members
sed -n '/^| `/p' docs/PROVENANCE.md | wc -l              # rows that account for them
```

The table naming every member, its class, its upstream, its licence and the exact local delta for
each fork is [`docs/PROVENANCE.md`](docs/PROVENANCE.md) — one place, checked by
`scripts/validate-skills.sh` against `skills/` and `.claude-plugin/plugin.json` in both directions.

## Install

**As a marketplace plugin**

```
/plugin marketplace add RubyEyedReaper/Odin-Skills
/plugin install odin-skills
```

**Manually** — copy any skill directory into `~/.claude/skills/`:

```sh
git clone https://github.com/RubyEyedReaper/Odin-Skills
cp -R Odin-Skills/skills/decision-matrix ~/.claude/skills/
```

Skills are self-contained: each directory holds its own `SKILL.md`, references, and scripts.

## Skills with a runtime dependency

Most are pure prose and work anywhere. Six want something present:

| Skill | Needs |
|---|---|
| `decision-matrix` | `python3` (stdlib only) for the scoring engine |
| `roadmap` | `python3` (stdlib only) for the roadmap engine |
| `blueprint` | `python3` (stdlib only) for `plancheck.py` |
| `mistake-to-gate` | `python3` (stdlib only) for `mistakes.py` |
| `impeccable` | `node` for its hook scripts |
| `agent-browser` | the `agent-browser` CLI — this skill is a deliberate offline stub that delegates to it |

## Licensing

Deliberately not one license, because it cannot honestly be one.

| What | License |
|---|---|
| Skill prose authored here (`odin-authored` rows in PROVENANCE) | CC-BY-SA-4.0 |
| Scripts, workflows, manifests | MIT |
| `impeccable`, `agent-browser` | Apache-2.0 (upstream) |
| `blueprint`, `decision-mapping`, `grill-with-docs`, `handoff`, `using-superpowers`, `test-driven-development`, `verification-before-completion` | MIT (upstream) |
| `rules-distill` | as published by upstream — no `LICENSE` accompanied the vendored copy |

Each forked skill ships an `UPSTREAM.md` stating what changed, and its upstream `LICENSE` in its own
directory — which is also how Apache-2.0 §4(b) is satisfied for the two Apache works. `rules-distill`
is the one exception: its upstream shipped no license file, so its `UPSTREAM.md` declares that
absence and a `NOTICE` beside it carries the attribution. Attribution for every upstream:
[`NOTICE`](NOTICE); origins and the exact local delta: [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## Source of truth

`.claude/skills/` in the Odin harness repo is authoritative; this repository is a published mirror of
it. Odin commits its skills so they survive container resets, so it cannot depend on an external repo
to supply them.

Sync is one-way and mechanical:

```sh
scripts/sync-from-odin.sh --check   # fail if the mirror has drifted
scripts/sync-from-odin.sh           # copy .claude/skills/ -> skills/
```

`--check` is a local gate, also runnable in CI by manual `workflow_dispatch` — and only from inside
an Odin harness checkout, since a standalone clone has nothing to compare against. It is deliberately
not an automatic trigger: while this subtree lives inside the Odin monorepo, a workflow under
`projects/*/.github/workflows/` that fires on push would trip the harness safety guard's Layer 1D and
block every git write in the whole repository. The workflow's own comment carries the reasoning.

## Validating

```sh
scripts/validate-skills.sh      # frontmatter, manifest parity, licensing, provenance, symlinks
scripts/tests/validate.test.sh  # the matrix proving each of those checks actually fires
```

`.github/workflows/validate.yml` is a thin wrapper around exactly those commands — the same script
runs locally and in CI, so a green local run means something.

## Security

See [`SECURITY.md`](SECURITY.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Changes to a forked skill need a matching `UPSTREAM.md`
update; changes to a skill's content should land in the Odin harness first, then sync here.
