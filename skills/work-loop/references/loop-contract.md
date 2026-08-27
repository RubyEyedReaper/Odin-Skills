# The loop contract — eleven fields, declared before the first iteration

A loop with no contract cannot end well: it has no statement of what done looks like, no
limit, and no way for a later session to tell an unfinished loop from an abandoned one.
`open` refuses a contract missing any field, and refuses one whose field is declared
empty — an empty declaration is an undeclared field wearing a key.

| # | Field | Well-formed when | What goes wrong without it |
|---|---|---|---|
| 1 | `purpose` | One sentence naming the change in the world, not the activity | "improve the tests" never terminates; "coverage above 80%" does |
| 2 | `owner` | The session, agent or person accountable for the outcome | An escalated blocker lands in a ledger nobody reads |
| 3 | `starting_state` | The observable state at iteration zero — a branch, a number, a failing command | Progress is unmeasurable, so the circular-state predicate has no first point |
| 4 | `inputs` | Non-empty list of what the loop consumes | An iteration invents its inputs and two iterations disagree about what they ran on |
| 5 | `expected_outputs` | Non-empty list of artifacts the loop produces | `complete` becomes a feeling rather than a check |
| 6 | `success_criteria` | Non-empty list, each decidable by a command or an inspection | Nothing distinguishes `complete` from `stop` |
| 7 | `failure_criteria` | Non-empty list, each decidable the same way | The loop grinds through failures it should have escalated |
| 8 | `dependencies` | Non-empty list of the external things it needs by name | The dependency-unavailable predicate has nothing to check against, and any name at iteration time could end the loop |
| 9 | `iteration_limit` | A positive integer | The retries predicate cannot fire, and a loop with no ceiling is the thing this skill exists to prevent |
| 10 | `timeout_behaviour` | What happens when an iteration exceeds its budget | A hung iteration is indistinguishable from a slow one |
| 11 | `escalation_path` | Where a blocker goes — a roadmap item, an issue, an ADR | `escalate` degenerates into "ask a human", which ADR-0103 rejects |

## The shape on disk

```json
{
  "purpose": "drive the coverage gate to 80%",
  "owner": "harness",
  "starting_state": "coverage at 61% on branch harness/coverage",
  "inputs": ["the failing coverage report"],
  "expected_outputs": ["a committed test module per uncovered file"],
  "success_criteria": ["ci-local.sh reports coverage >= 80"],
  "failure_criteria": ["the same suite fails three times with one signature"],
  "dependencies": ["postgres"],
  "iteration_limit": 5,
  "timeout_behaviour": "checkpoint and pause after 20 minutes without progress",
  "escalation_path": "capture a roadmap item and end the loop"
}
```

A field the eleven do not name is refused too. The contract is an interface, and an
interface that silently accepts unknown keys cannot tell a typo from an extension.

## Criteria are decidable, or they are prose

`success_criteria` and `failure_criteria` earn their place only if an iteration can
decide them without a judgment call. "The code is clean" decides nothing. "`ruff check`
exits 0" decides. A criterion that needs a human to read it has already made the loop
depend on a human returning, which is the failure mode ADR-0103 was written against.

## The limit is a limit

`iteration_limit` is read from the contract on every iteration, never from a constant in
the engine. Reaching it fires the retries-exhausted predicate and ends the loop with
`stop` — the loop does not get a courtesy extra pass. A limit that is negotiable at the
moment it binds is a suggestion, and it will be renegotiated at turn thirty of an
unattended run, by a context that has forgotten why the number was chosen.

## Declaring is not planning

This contract states the *cycle*. What to build, and in what order, belongs to a plan
(`writing-plans`, `blueprint`) and to `roadmap`. A contract whose `purpose` reads like a
task list is a plan in the wrong file: name the outcome, and let the plan hold the steps.
