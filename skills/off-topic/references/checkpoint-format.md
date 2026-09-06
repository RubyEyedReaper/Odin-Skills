# The checkpoint format

One JSON file per checkpoint, in `.claude/docs/off-topic/`, named `<id>.json` where the id is the
file's stem. Committed — a gitignored checkpoint yields one verdict in the authoring checkout and a
different one everywhere else, which is exactly the case a checkpoint exists for (DEC-0108).

```json
{
  "schema": 1,
  "created_at": "2026-09-03T19:55:00Z",
  "interrupted": {
    "roadmap_item": "harness:RM-0527",
    "plan": ".claude/docs/plans/2026-09-03-off-topic.md",
    "branch": "skills/off-topic"
  },
  "interrupting": {
    "summary": "capture the ungoverned session-to-session channel before it is forgotten",
    "roadmap_item": "harness:RM-0520"
  },
  "resume_when": { "kind": "roadmap", "ref": "harness:RM-0520" },
  "resume_to": "re-run the skill-gate arm proof, then wire the ci-local step",
  "parent": null
}
```

## Field by field

| Field | Required | Holds | Why this shape |
|---|---|---|---|
| `schema` | yes | `1` | A store with no version cannot be migrated without guessing which files predate a change |
| `created_at` | yes | UTC instant, `Z`-suffixed | The one absolute value here. Ordering nested checkpoints by mtime would reorder them on any checkout |
| `interrupted` | yes | At least one of `roadmap_item`, `plan`, `branch`, `work_loop_session` | **References only.** Each is owned elsewhere and updates itself. A checkpoint with none of them names nothing to return to |
| `interrupting` | yes | `summary` (one line), optionally `roadmap_item` or `issue` | The summary is for a reader; the references are what the resume condition resolves against |
| `resume_when` | yes | `{kind, ref}` — `kind` one of `roadmap`, `issue`, `manual` | A **closed vocabulary**, never a command. A checkpoint-supplied string run by the check would be a subprocess outside every always-on guard — the objection ADR-0143 records for `work-loop`'s rubric evidence commands |
| `resume_to` | yes | One line: the first action on returning | A *plan to return*, which is the one thing no other file holds |
| `parent` | yes, nullable | Another checkpoint's id, or `null` | Nesting. See **Nesting** below |

## What is refused, and what each refusal catches

| Refused | Catches |
|---|---|
| Any key not in the table above, at any depth | A store growing fields nobody validates |
| `status`, `state`, `progress`, `phase`, `done`, `complete`, at any depth | The failure `campaign` refuses (ADR-0113) and `revive` refuses at any depth: a status reads identically whether it is current or six hours old |
| `interrupted` with no reference at all | A checkpoint naming nothing to return to |
| A `roadmap_item` no roadmap item matches | A dangling reference — the one way a pointer store can lie, and the reason it is checked rather than trusted |
| A `plan` path that is not a file | Same, for the plan half |
| A `parent` naming a checkpoint the store does not hold | A closed parent with an open child — the LIFO violation |
| A `parent` chain that returns to itself | A cycle, which makes the stack unorderable |
| `resume_when.kind` outside the three words | A free-text condition nothing can resolve |
| An empty `resume_to` | An obligation with no instruction is a note, not a checkpoint |

## Choosing `resume_when`

| `kind` | `ref` | Resolves by |
|---|---|---|
| `roadmap` | An item id | The item's status in `.claude/docs/roadmap/roadmap.json`. Met when it is `done` |
| `issue` | An issue number | The tracker. Met when it is closed. Unreachable tracker is a finding, never a pass |
| `manual` | One line naming the condition | Nothing. Reported as unresolvable by design, and counted in the summary |

**Prefer `roadmap` or `issue`.** `manual` is honest — it says in the open that no channel can tell
you the return came due — and it is the weaker form for exactly that reason. A `manual` checkpoint is
still listed on every run, which is the whole of what it buys.

## Nesting

An interrupt during an interrupt stacks: the new checkpoint's `parent` is the id of the one already
open. Refusing to nest would be an instruction to write nothing, and overwriting would lose the first
displacement silently — the precise failure this skill exists to prevent.

Return is **LIFO**. A parent is not closed while a child is open, and because closing is deleting the
file, that is checkable from the tree alone: a checkpoint whose `parent` is absent from the store is
an orphaned child, and the check names it.
