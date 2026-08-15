# Odin-Skills

The skills the [Odin](https://github.com/RubyEyedReaper/Odin) harness **owns** — five authored from
scratch, eight forked from upstream projects and modified — packaged as one installable Claude Code
plugin.

Odin vendors 98 skills in total. The other 85 are third-party work it has never touched, and they
are not redistributed here. This repository is only the part Odin is actually the author or the
maintainer of.

## What's in it

**Authored here (5)** — `decision-matrix` · `mistake-to-gate` · `oops` · `roadmap` · `superplan`

**Forked and modified (8)** — `impeccable` · `blueprint` · `handoff` · `using-superpowers` ·
`test-driven-development` · `verification-before-completion` · `agent-browser` · `decision-mapping`

Origins, upstream licenses, and the exact local delta for every fork: [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

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

Most are pure prose and work anywhere. Three want something present:

| Skill | Needs |
|---|---|
| `decision-matrix` | `python3` (stdlib only) for the scoring engine |
| `blueprint` | `python3` (stdlib only) for `plancheck.py` |
| `impeccable` | `node` for its hook scripts |
| `agent-browser` | the `agent-browser` CLI — this skill is a deliberate offline stub that delegates to it |

## Licensing

Deliberately not one license, because it cannot honestly be one.

| What | License |
|---|---|
| Skill prose authored here (`odin-authored` rows in PROVENANCE) | CC-BY-SA-4.0 |
| Scripts, workflows, manifests | MIT |
| `impeccable`, `agent-browser` | Apache-2.0 (upstream) |
| `blueprint`, `handoff`, `using-superpowers`, `test-driven-development`, `verification-before-completion` | MIT (upstream) |

Each forked skill ships its upstream `LICENSE` in its own directory and an `UPSTREAM.md` stating what
changed — which is also how Apache-2.0 §4(b) is satisfied for the two Apache works. Attribution for
every upstream: [`NOTICE`](NOTICE).

## Source of truth

`.claude/skills/` in the Odin harness repo is authoritative; this repository is a published mirror of
it. Odin commits its skills so they survive container resets, so it cannot depend on an external repo
to supply them.

Sync is one-way and mechanical:

```sh
scripts/sync-from-odin.sh --check   # fail if the mirror has drifted
scripts/sync-from-odin.sh           # copy .claude/skills/ -> skills/
```

CI runs `--check`, so a stale mirror fails the build instead of reaching an installer.

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

## Related

- [Odin](https://github.com/RubyEyedReaper/Odin) — the harness these skills were built for
