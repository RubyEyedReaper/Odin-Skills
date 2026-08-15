## What changed

<!-- One or two sentences. What does this PR do, and why? -->

## Change class

- [ ] Packaging — manifests, licensing, validator, CI, docs
- [ ] Membership — adding or removing a skill
- [ ] Sync — pulling skill content down from the Odin harness

<!-- Skill *content* edits do not belong here; they land in the Odin harness first
     and arrive by sync. See CONTRIBUTING.md. -->

## Checklist

- [ ] Skill content changes (if any) landed in the Odin harness first
- [ ] `docs/PROVENANCE.md` matches `skills/` and `.claude-plugin/plugin.json`
- [ ] Forked skills touched here have an updated `UPSTREAM.md`
- [ ] `scripts/validate-skills.sh` passes
- [ ] `scripts/tests/validate.test.sh` passes
- [ ] No skill directory contains a dangling symlink

## Licensing

- [ ] No skill's upstream `LICENSE` was removed or replaced
- [ ] Apache-2.0 forks (`impeccable`, `agent-browser`) still state their modifications in `UPSTREAM.md`
- [ ] N/A — this PR touches no skill directory
