# Publishing

This repository currently lives as a subtree inside the Odin harness at `projects/Odin-Skills/`.
It is complete and self-contained — manifests, licensing, validator, CI — but it has no remote of its
own yet.

Publishing was **deliberately not performed** by the session that built it: creating a GitHub
repository is externally visible and irreversible, and that session's GitHub access was scoped to
`rubyeyedreaper/odin` alone. Everything below is the exact sequence to finish it.

## Why a subtree split rather than a fresh `git init`

`git subtree split` carries the commit history of `projects/Odin-Skills/` into a standalone branch, so
the published repository opens with the real record of how it was built. A fresh `git init` throws that
away and starts at one squashed commit — which also breaks the audit trail the fork `UPSTREAM.md`
files depend on.

## Steps

Run from the root of the Odin harness checkout.

**1. Split the subtree into its own branch**

```sh
git subtree split -P projects/Odin-Skills -b odin-skills-extract
```

**2. Package it, history preserved**

```sh
git bundle create /tmp/odin-skills.bundle odin-skills-extract
```

**3. Create the remote**

Create `RubyEyedReaper/Odin-Skills` on GitHub — empty, no README, no `.gitignore`, no licence. Any
initial commit GitHub adds has to be reconciled away afterwards.

Suggested repository description (≤160 chars, no generic filler):

> Skills the Odin agent harness owns — decision scoring, roadmap planning, blueprint decomposition, mistake-to-gate hardening, interface polish.

Suggested topics: `agent-skill`, `claude-code`, `claude-skills`, `ai-agents`, `planning`,
`decision-making`.

**4. Seed the new repository from the bundle**

```sh
git clone /tmp/odin-skills.bundle Odin-Skills
cd Odin-Skills
git checkout odin-skills-extract
git branch -M main
git remote remove origin
git remote add origin https://github.com/RubyEyedReaper/Odin-Skills.git
git push -u origin main
```

**5. Verify the published tree stands alone**

```sh
bash scripts/tests/validate.test.sh   # 16/16
bash scripts/validate-skills.sh       # OK: 12 skills validated
```

`scripts/sync-from-odin.sh --check` will refuse here — there is no harness checkout at `../..`. From a
standalone clone, point it at one explicitly:

```sh
bash scripts/sync-from-odin.sh --check --odin /path/to/Odin
```

**6. Decide what the harness keeps**

Per `projects/README.md`, an extracted project leaves behind a pointer or nothing. Two defensible
options:

| Option | Consequence |
|---|---|
| **Keep the subtree** (recommended initially) | The mirror stays trivially syncable and CI can run the drift check. Costs ~3.4 MB of duplication in the harness. |
| `git rm -r projects/Odin-Skills`, leave a pointer row in `projects/README.md` | Harness stays lean; syncing then needs a clone of the published repo, and the drift check becomes a two-repo operation. |

Either way the harness's own `.claude/skills/` stays authoritative — nothing about publishing changes
that, and ADR-0001 requires it.

## After publishing

- Tag `v0.1.0` once the first push is green.
- The marketplace path advertised in `README.md`
  (`/plugin marketplace add RubyEyedReaper/Odin-Skills`) only resolves once the repository is public.
- Add the repository to the Odin harness session's GitHub scope if a future session should maintain it.
