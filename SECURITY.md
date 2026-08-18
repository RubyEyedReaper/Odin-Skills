# Security

## Reporting

Report a vulnerability through GitHub's private advisory form on this repository
(**Security → Report a vulnerability**). Do not open a public issue for anything exploitable.

Include what the skill does when the issue triggers, the harness and OS you saw it on, and a minimal
reproduction if you have one.

## What the threat model is here

These are agent skills: Markdown instructions an AI agent reads and acts on, plus a few scripts it
runs. That makes two things security-relevant in a way ordinary documentation is not.

**Instructions are executed, not just read.** A skill that tells an agent to run a command gets that
command run, often without a human looking closely. Treat prose that directs destructive or
credential-touching actions as you would treat the code doing it. Skills here must never instruct an
agent to disable a safety guard, weaken TLS verification, write to `~/.ssh`, `~/.gnupg`, `~/.aws`,
shell init files, or the agent's own settings, or to exfiltrate environment variables.

**Scripts run with the agent's privileges.** `decision-matrix` and `blueprint` ship Python (stdlib
only); `impeccable` ships Node hook scripts. They inherit whatever the invoking agent can do.

## What is in scope

- A skill's instructions steering an agent into a destructive or credential-exposing action
- Command injection or path traversal in a shipped script
- A skill script writing outside its intended target
- Secrets committed to this repository

## What is not

- An agent choosing to do something unsafe that no skill here instructed
- Vulnerabilities in the upstream projects the forks derive from — report those upstream
  (see `NOTICE`), though telling us too is welcome so the fork can be patched
- Missing hardening in the Odin harness itself. The harness is a private repository with no tracker
  you can reach, so send it through the advisory form above and it will be relayed — do not sit on it

## Verifying what you install

Every skill is plain text. Read `SKILL.md` before installing, and read any `scripts/` it ships.
`docs/PROVENANCE.md` states where each skill came from and, for forks, exactly what was changed
relative to upstream — so a fork's diff against its stated upstream HEAD is auditable.
