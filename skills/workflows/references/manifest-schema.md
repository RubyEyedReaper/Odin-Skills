# Manifest schema

A manifest is a markdown document at `.claude/docs/workflows/<id>.workflow.md` carrying **exactly
one** fenced ` ```json ` block. The prose around the block is for the human reading it beside the
chain it describes; the block is what `scripts/workflow.py` acts on.

Why this shape rather than raw JSON or YAML frontmatter: `json.loads` is a real parser, so what the
engine reads is what a reader reads. A hand-rolled frontmatter parser asserts what its author
assumed, and no YAML parser ships in the stdlib — every engine under `.claude/skills/*/scripts/` is
stdlib-only.

## The ten lifecycle fields

| Field | Type | Rule |
|---|---|---|
| `id` | string | Must equal the filename stem. `run <id>` resolves by filename, so a mismatch makes the manifest unaddressable. |
| `version` | string | Three numeric parts, `MAJOR.MINOR.PATCH`. The manifest is an interface; a revision moves it. |
| `status` | string | One of `draft`, `active`, `retired`. |
| `owner` | string | Who is accountable for the chain being correct. A workflow nobody owns is the gap this skill exists to close. |
| `supersedes` | string or null | The workflow id this one replaced, or `null`. Present-and-null, never absent — an absent field cannot be told apart from an unanswered question. |
| `inputs` | list | What must exist before the chain starts. Non-empty. |
| `outputs` | list | What exists when it finishes. Non-empty. |
| `dependencies` | list | Other workflow ids this chain assumes. **The one list allowed to be empty:** a chain that depends on nothing is ordinary; one that produces nothing is a finding. |
| `decision_points` | list of objects | `{"at": <step number>, "question": <text>}`. `at` must name a step that exists. |
| `failure_handling` | list of objects | `{"when": <condition>, "action": <what to do>}`. Non-empty — a chain with no stated failure path has one anyway, undocumented. |
| `completion_criteria` | list | How the chain is known to be finished. Non-empty. |

All eleven rows above are required. `supersedes` accepts `null` as a value, not as an absence.

## The structural field

| Field | Type | Rule |
|---|---|---|
| `steps` | list of objects | `{"step": <n>, "skill": <name>, "gates": <what it gates>}`, numbered from 1 with no gaps. Non-empty. |

`steps` is the body the lifecycle fields describe, which is why it is listed apart — but it is
equally required, because `run` has nothing to emit without it.

## The retirement block

Present **only** when `status` is `retired`, and then required:

```json
"retired": { "reason": "the gate it fed was deleted", "at": "2026-08-26T19:44:02.117Z" }
```

or

```json
"retired": { "superseded_by": "new-chain", "at": "2026-08-26T19:44:02.117Z" }
```

A retired manifest without this block is a validation finding. `retire` writes it; hand-writing it
is allowed but skips the successor-exists check.

## Worked example

````markdown
# Bug investigation

Prose a human reads, beside the chain document this manifest governs.

```json
{
  "id": "bug-investigation",
  "version": "1.0.0",
  "status": "active",
  "owner": "harness",
  "supersedes": null,
  "inputs": ["a reproducible failure"],
  "outputs": ["a committed reproduction test", "a minimal fix"],
  "dependencies": [],
  "decision_points": [{"at": 2, "question": "is the root cause confirmed?"}],
  "failure_handling": [{"when": "the reproduction passes", "action": "return to step 1"}],
  "completion_criteria": ["the reproduction test fails before the fix and passes after"],
  "steps": [
    {"step": 1, "skill": "systematic-debugging", "gates": "diagnosis before fixes"},
    {"step": 2, "skill": "diagnosing-bugs", "gates": "root cause confirmed"}
  ]
}
```
````

## Versioning the interface

A manifest is consumed by whoever follows the chain, so it versions like any other interface.

| Change | Move |
|---|---|
| Wording, an added failure-handling row, a clarified completion criterion | patch |
| A new step, a new decision point, a lifecycle transition | minor — `retire` bumps the minor itself |
| A removed or renumbered step, a removed output, a changed `id` | major, and usually a supersede rather than an edit |

Renaming a workflow is **not** a version bump: the `id` is the address. Retire the old one with
`--superseded-by` and set `supersedes` on the new one, so both halves of the rename are recorded.

## What validation refuses

Every rule that fails is reported, not the first — one pass should list the whole repair.

- A missing required field, by name.
- An `id` that does not match the filename stem.
- A `version` that is not three numeric parts.
- A `status` outside the three.
- A list field that is empty, `dependencies` excepted.
- A step out of sequence, or missing `skill` or `gates`.
- A `decision_points` entry naming a step that does not exist.
- A `failure_handling` entry missing `when` or `action`.
- A retired manifest with no `retired` block.
- Zero, or two or more, fenced JSON blocks — the ambiguity is refused, never resolved by taking the
  first block.
- Unparseable JSON, reported as a finding against the named file rather than as a traceback.

An empty manifest **set** is not a finding but its own refusal, exit 4. See
[lifecycle.md](lifecycle.md) for why the two are kept apart.
