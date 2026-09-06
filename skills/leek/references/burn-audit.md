# Burn audit — the method behind Leek's `tokens` and `sessions` families

**Origin: the `ecc-tools-cost-audit` skill** (`.claude/skills/ecc-tools-cost-audit/SKILL.md`,
vendored from ECC). That skill is the prose statement of this method, scoped to one
repository's webhook → queue → worker → billing path, and it remains the right entry point
for that repository. This file generalises the same discipline to a Claude Code
environment: trace ingress before theorizing, rank by burn, and prove containment with the
narrowest step that can prove it.

## The discipline, in four rules

1. **Evidence first, theory second.** Do not begin from a hypothesis about where the burn
   is. Read the transcript, the process table and the cache sizes, then form a hypothesis
   the evidence already supports. Broad wandering is what makes a cost audit expensive.
2. **Trace ingress before the expensive step.** Find every path that reaches the costly
   operation before proposing a fix for one of them. A fix on one enqueue path is worthless
   when three converge on the same worker.
3. **Rank by burn, never by code neatness.** The finding that is easiest to fix is almost
   never the one costing the most. Order the work by what is being spent.
4. **Separate three things explicitly** — the mechanism causing the burn, the user-visible
   impact, and the product or configuration gap that permitted it. Conflating them produces
   an issue nobody can close.

## High-signal burn patterns

Each is a shape, not a specific defect. The first four are what Leek's `tokens` family
detects mechanically; the rest need a human reading the trace.

### 1. The same output returned repeatedly

One tool result, identical bytes, entering context several times in a session. Almost
always a re-read of content that did not change: a file read at the top of every loop
iteration, a status command polled without a state change, a config re-fetched because
nothing held the first answer.

The cost is linear in the repeat count and invisible per call, which is why it survives.
*Detected as* `tokens/repeated-tool-output` above `DUP_TOOL_RESULT` repeats.

### 2. Retry on a deterministic failure

The same tool, the same input, over and over. A transient failure retried is correct; a
deterministic one retried is spend with no progress, and the loop usually ends by
exhausting a budget rather than by succeeding.

The fix is never a better retry policy — it is a check on the precondition that is failing.
*Detected as* `tokens/retry-loop` above `RETRY_LOOP` identical invocations.

### 3. Unbounded tool output

A tool returning more than the task needed: a whole file when a range would do, a full
directory listing when a count would do, a complete log when the last twenty lines would
do. Bound the output at the call site. *Detected as* `tokens/oversized-tool-result`.

### 4. Work that outlives its session

A process still running after the task that started it finished or failed. On a
systemd-user host this is the pattern that starves the machine: orphaned MCP servers
accumulate at hundreds of megabytes each, and enough of them takes the session daemon down
— at which point every session in the fleet reports a state it is no longer in.

**`ppid == 1` finds none of them.** User services are reparented to the user manager, not
to init, so the predicate must be "no live session anywhere in my ancestry", walked up the
parent chain. *Detected as* `sessions/orphaned-mcp-server`.

### 5. Expensive work before persistence safety

Tokens spent, then the write fails — a branch collision, a full disk, a rejected push.
The spend happened and nothing shipped. Order the cheap failure checks before the expensive
step, not after it.

### 6. One expensive path shared by every trigger

Several entry points converging on the same costly operation, so any of them can spend it.
The audit question is not "is this path expensive" but "how many ways are there in".

### 7. Output-producing work that re-enters its own input

Anything whose output is watched by the thing that produced it: an agent whose commits
trigger the analysis that made them, a loop whose findings become its next iteration's
input without a termination predicate. Treat every such path as a priority-0 recursion risk
until proved otherwise, because the cost is unbounded rather than merely high.

## Fix in burn order

When findings are recorded and the work is planned, this is the order:

1. Stop anything recursive or unbounded — the cost has no ceiling
2. Stop work that outlives its session and holds resources
3. Stop repeated identical work — retries and re-reads
4. Bound output at the call sites that are oversized
5. Reduce the fixed per-session cost (that is `context`'s half — see
   [context-inventory.md](context-inventory.md))

Anything below the highest-burn open item is deferred, however tempting it is to fix first.

## Prove containment with the narrowest step

State the status exactly, in these terms and no vaguer:

- **found** — the evidence exists and the mechanism is named
- **recorded** — the issue is open with that evidence in it
- **contained** — a change landed and the narrow proving step was re-run
- **still open** — none of the above, and say which

Re-run the one family the finding came from, not the whole scan: `leek-scan.sh --check
tokens` is the proving step for a `tokens` finding. A full pass re-reports everything and
buries the answer to the question that was actually asked.

## Pitfalls

- Beginning with a broad sweep instead of settling the ingress path first
- Mixing inferred impact with code-backed mechanism in one claim
- Fixing a cheaper, tidier finding before the highest-burn one is contained
- Calling burn contained without re-running the narrow proving step
- Acting on any of it during the audit — Leek records; the fix is planned work
  (ADR-0088)
