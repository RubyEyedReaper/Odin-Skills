---
name: leek
description: Diagnose leaks and hygiene failures in a Claude Code environment — context that stays loaded, wasted tokens, memory that outlives its scope, cache buildup, orphaned or runaway sessions, cross-session and cross-project contamination, stale working state, and misconfigured agents, hooks, MCP servers or skills. Use when a session fills its context too fast, burn or cost looks wrong, memories surface from the wrong project, caches or processes accumulate, a session went silent or will not stop, secrets may be sitting in a shared store, or a skill has never been used. Reports and files issues; never cleans up.
metadata:
  origin: Odin
  forks: context-budget, ecc-tools-cost-audit
---

# Leek

> "Leek", as in leak — the vegetable. A diagnostic and hygiene pass over a Claude Code
> environment: what is being wasted, what is being retained past its scope, what is
> reachable from where it should not be, and what is still running after its work ended.

**Leek diagnoses. Leek never remediates.** Its outputs are a report document, one GitHub
issue per distinct concern, and a hand-off to `mistake-to-gate` where a finding has a
repo-state predicate. It runs no cleanup, terminates no process, expires no memory and
clears no cache — those are separate, deliberate acts by something else, and the reason is
[ADR-0088](../../docs/adr/0088-leek-diagnoses-never-remediates.md): the scanner's own
evidence says the environment is in an unexpected state, which is the worst possible moment
to exercise judgment about what is safe to destroy.

## When to use

- Context fills too fast; output quality degrades over a session; a session is "heavy"
- Burn, spend or token usage looks disproportionate to the work done
- A memory surfaced that belongs to another project, or a memory that should have expired
- Caches, job workspaces, transcripts or embeddings are accumulating on disk
- A session went silent, a fleet reports `blocked`, or a process will not stop
- Secrets or credentials may have reached a memory store, a cache or a config file
- Before adding agents, skills or MCP servers — is there room?
- "Which skills have never been used?"
- Periodically, as hygiene, before a campaign or after one

Not for: fixing what it finds (open the issue, then plan that work like any other);
choosing what to build next (`roadmap`); auditing a plan (`plan-adversary`); diagnosing one
concrete bug (`systematic-debugging`).

## Run the scanner first

Everything below is triage of the scanner's output. Do not hand-audit what it measures.

```sh
bash .claude/skills/leek/scripts/leek-scan.sh                       # every family, text
bash .claude/skills/leek/scripts/leek-scan.sh --json                # same, machine-readable
bash .claude/skills/leek/scripts/leek-scan.sh --check memory,isolation
bash .claude/skills/leek/scripts/leek-scan.sh --check skills-unused
bash .claude/skills/leek/scripts/leek-scan.sh --min-severity high   # critical + high only
```

Exit codes are the interface: `0` no findings, `1` findings, `2` usage error. A full pass
over a live host takes about ten seconds.

**Exit 0 is a measured clean, not a silence.** An evidence channel that could not be read
produces an `evidence-unavailable` finding, so a blind channel exits 1. Read the *Evidence
channels* block at the top of every report before the findings — `no findings` from an
instrument that could not look is the failure mode that let 76 of 77 open issues go
uncaptured (ADR-0069).

### The eight families

| Family | What it looks for |
|---|---|
| `context` | Always-on rule bytes, oversized instruction files, bloated agent descriptions, heavy agent and skill bodies, byte-identical skill bodies, MCP over-subscription |
| `tokens` | Oversized transcripts, the same tool output returned repeatedly, retry loops on identical input, tool results larger than the budget |
| `memory` | Unscoped records, records relabelled across projects, duplicates, records past retention, provenance gaps, credential shapes, file-tier index drift |
| `cache` | Oversized and stale cache roots under the state dir and the memory service |
| `sessions` | Daemon liveness (via `fleet-health.sh`), MCP servers with no live session in their ancestry, and long-lived processes split by CPU fraction — burning CPU is a runaway, near-idle is a memory hold. Each report names the owner and the project |
| `isolation` | Workspace-wide permission grants, memory files naming several projects, credential shapes in caches every session can read |
| `state` | Spent plan docs, runtime residue, expired posture claim tickets, abandoned worktrees, a large uncommitted diff |
| `components` | Duplicate agent names, unbounded agent tool grants, unregistered and missing hooks, hook hygiene (size, unbounded output, discarded failures, `eval` or a download piped to a shell, an environment dump, no `set -u`), MCP filesystem breadth and inline credentials, settings conflicts, skills never invoked, stub skills |

`skills-unused` is a selector for the never-invoked half of `components` on its own.

### Three things the scanner will not tell you

- **A hook-hygiene finding is a shape, not a proven defect.** The checks read normalized
  source — comments and quoted spans blanked — because a guard that *matches* `eval` in
  order to block it reads identically to one that runs it. Even normalized, a hook that
  deliberately silences one command looks like one that swallows every failure. Only the
  author can tell them apart; the finding says which line to look at.

- **The transcript window bounds every usage answer.** "Never invoked" means "not in the
  retained transcripts", and the report states the window it scanned. A skill added last
  week and a skill nobody has ever wanted look identical over a 24-day window; read the
  finding against the skill's age before concluding anything.
- **A credential-shape match is reported by class, never by text.** The scanner prints the
  record id, the project and the match class. It does not quote the match, because a
  finding that quotes a secret has copied it into a report and then into an issue.

## Triage

Rank by the cost of being wrong, not by how easy each is to close — the burn-order
discipline in [references/burn-audit.md](references/burn-audit.md).

| Severity | Meaning | Act by |
|---|---|---|
| `critical` | Immediate privacy, security or cost risk | Issue today, labelled `security`; rotate anything exposed |
| `high` | Significant wasted usage or unstable behaviour | Issue this pass |
| `medium` | Inefficient, stale or poorly scoped state | Issue, or fold into an existing roadmap item |
| `low` | Cleanup or optimization opportunity | Batch into one hygiene issue rather than twenty |

Two questions decide whether a finding is real:

1. **Is the premise still true?** A finding is a claim about the tree and the host at scan
   time. Re-run the one family before planning anything from a report older than a session
   — the scanner is cheap and a stale premise is what makes a fix conflict with itself.
2. **Is it intended?** Several checks flag configuration that is sometimes correct: a
   read-only permission granted workspace-wide, a large plugin cache on a machine that
   uses those plugins, several projects sharing one memory store where every read is
   scoped. Say so in the issue and close it as intended, rather than leaving it to
   resurface every pass.

## Record — the only actions Leek takes

### 1. The report document

Write `.claude/docs/audits/leek-YYYY-MM-DD.md`. It carries the command that produced it,
the evidence-channel block verbatim, the finding counts, and one section per severity. A
report without its channel block is unfalsifiable — the next reader cannot tell a clean
host from a blind scan.

### 2. One issue per distinct concern

Never one issue for "leek findings". Use `to-issues` when there are many, or:

```sh
gh issue create -R <owner>/<repo> --title "<family>/<code>: <one-line summary>" \
  --label tech-debt --body-file <file>
```

Each issue body carries the finding's component, evidence, impact and remediation from the
JSON, plus the scan date. Label `security` for `critical`, `tech-debt` otherwise; add
`audit` so a later pass can find them.

### 3. Hand mechanical predicates to `mistake-to-gate`

A finding whose condition is a repo-state predicate — a hook registered against a missing
script, a duplicate agent name, an always-on rule over budget — is a gate waiting to be
written, not a cleanup task. Invoke `mistake-to-gate` for it. A finding whose condition is
judgment goes to `rules-distill` instead.

### 4. Capture the work

Anything worth doing is a roadmap item (`roadmap add`), planned like any other work. Leek's
pass ends when the findings are recorded, not when they are fixed.

## Forked method

Two skills supply the method for two families and remain independently usable — Leek's copy
is the executable one, theirs is the origin:

- [references/context-inventory.md](references/context-inventory.md) — the component
  inventory, token estimation and always-needed/sometimes/rarely classification, from
  `context-budget`.
- [references/burn-audit.md](references/burn-audit.md) — evidence-first burn tracing,
  the high-signal burn patterns, and fix-in-burn-order, from `ecc-tools-cost-audit`.

## Common mistakes

- Reading the findings without reading the evidence-channel block above them
- Treating `exit 0` as proof of health when a channel said `unavailable`
- Cleaning up during the audit — every cleanup is a second, deliberate act (ADR-0088)
- Terminating a process by command-line pattern; `pkill -f` matches the harness's own
  wrapper shells, including the shell running the kill. Confirm with `pgrep -af`, then act
  on the PID
- One issue for the whole report, which nobody can close
- Quoting a credential match into a report or an issue
- Re-running the scanner instead of re-running the one family the finding came from
- Concluding a skill is dead from a transcript window shorter than the skill's age
