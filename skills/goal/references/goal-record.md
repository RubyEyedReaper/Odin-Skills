# The goal record — required shape, and the bar each field must clear

Read by `.claude/scripts/goal-check.sh`. Every rule here is one that checker enforces, except where
it says otherwise in the open.

## Location

| Scope | Path |
|---|---|
| The harness | `.claude/docs/goals/<slug>.md` |
| A project subtree | `projects/<slug>/docs/goals/<goal-slug>.md` |

The slug is the filename stem and must equal the frontmatter `goal:` value. Two names for one record
is how a downstream reference resolves to nothing.

## Frontmatter

```yaml
---
goal: <slug>          # equals the filename stem
owner: <who>          # a session id, a role, or a person — never "the team"
scope: harness        # or the project slug this goal belongs to
---
```

**Refused as frontmatter keys:** `status`, `progress`, `done`, `complete`, `percent`. The standing of
a goal is computed by running `Done when`; a stored answer is a second source of truth that is
correct until the next commit and believed forever after (ADR-0113).

## The six required sections

### 1. The title line

`# <one sentence, present tense>` — a state of the world, not a list of actions.

| Weak | Strong |
|---|---|
| Fix the open issues | Every open issue carries a command that reproduces its premise |
| Improve skill routing | No skill is reachable only through its own description |
| Make the harness faster | The pre-push set completes inside its declared budget |

The test: could a reader disagree about whether it is currently true? If not, it is not a destination.

### 2. `## Objective`

What must become true, and why that is the destination rather than a step toward one. Two or three
sentences. This is the only section written as argument rather than as specification.

### 3. `## Done when`

A fenced `sh` block holding **a command**, followed by what its output or exit code must be.

```sh
bash .claude/scripts/goal-check.sh . && test "$(gh issue list -R <owner>/<repo> --state open --limit 500 --json number --jq 'length')" -eq 0
```

Rules the checker enforces:

- The block is fenced and tagged `sh`.
- Its first non-comment word resolves — on `PATH`, or as a file under the repository root. A command
  naming a program nothing can run is the same defect as an `observed_rc` nobody executed.
- The block is followed by prose saying what counts as reached. A command with no stated expectation
  is half a predicate.

**More than one command is allowed and often correct.** A destination with two independent halves
gets two blocks, each with its own expectation. What is not allowed is a block that is really prose
with a `#` in front of it.

### 4. `## Out of scope`

A bullet list. Each line names something a reasonable reader would otherwise assume is included, and
gives the reason it is not.

An empty list fails the checker. Not because every goal excludes something in principle, but because
an unbounded destination makes every item arguably on the way to it — which is the drift this record
exists to prevent, restated as a document.

### 5. `## Verified by`

A fenced `sh` block holding the command that re-establishes **this record's own premises** — not
whether the goal is reached (that is `Done when`), but whether the things it assumes are still true.

A goal that assumes 122 open issues, written against a tracker that now holds 40, is not wrong about
its destination and is wrong about its arithmetic. `Verified by` is what notices.

Never a date. `learn`'s rule: a record's freshness is a command, because a date tells you when
somebody last believed something and nothing about whether it holds now.

### 6. Reader references — implicit, and checked from the other side

The record does not list its readers; the readers name the slug. `goal-check.sh` reports a record
that **no committed file references by slug** as `unreferenced` — a goal nothing consults is a goal
nothing can drift from, and it exits non-zero rather than passing quietly.

## Exit codes

`goal-check.sh` follows the CLI convention the rest of the harness uses:

| Code | Means |
|---|---|
| 0 | every record clean |
| 1 | at least one record is malformed, or unreferenced |
| 2 | could not look — no such root, no goals directory, or a goals directory holding no records |

**An empty goals directory is exit 2, never 0.** "I looked and found nothing" and "there is nothing
to look at" are different answers, and a harness with no goal at all should say so rather than report
a clean sweep of the empty set.

## What this checker deliberately does not decide

Stated here so a reader does not mistake a green run for more than it is:

- **Whether the goal is worth pursuing.** That is judgment, and no predicate here pretends to it.
- **Whether `Done when` is the *right* command.** It checks the command resolves and carries an
  expectation, not that it measures the destination. A goal can be precisely, checkably wrong.
- **Whether the goal has been reached.** Run `Done when`. The checker never runs it — a checker that
  executed every goal's completion command on every push would be running arbitrary committed
  commands as a side effect of a gate, which is a much worse property than the one it would buy.

That third one is the residue worth remembering: this gate asserts a record is *well-formed*, and a
well-formed goal nobody is moving toward still reads green.
