# Roadmap schema reference

Canonical state is `roadmap.json`. Everything else is generated. Stdlib-only Python
engine; no dependencies to install.

## Document

```json
{
  "schema": 1,
  "scope": "task:ServerPartPicker",
  "updated": "2026-07-29",
  "last_reconcile": "2026-07-29",
  "items": []
}
```

| Field | Meaning |
|---|---|
| `schema` | Format version. Currently `1`; a mismatch fails `validate`. |
| `scope` | Memory-class style label, e.g. `task:<slug>` or `operational`. **Not an identity** — two roadmaps may share one. |
| `slug` | Optional. The roadmap's *identity*, used to qualify its item ids as `<slug>:RM-####`. Absent is valid: it derives from the layout — `harness` for a harness roadmap, the project root's basename for a project one. Declared wins. Must be unique across the roadmaps in a tree; `roadmap-check.sh` fails on a clash (ADR-0050). |

**`id` is only unique within its own roadmap.** `RM-####` comes from a per-file counter, so the same
id names different work in every roadmap that exists. Cite one in any document that will be read
elsewhere — a handoff above all — in the qualified form the engine prints: `harness:RM-0034`.
`odin-relay.sh` refuses a handoff that does not.
| `updated` | Last mutation date (ISO). Stamped automatically. |
| `last_reconcile` | Last drift check. `null` means never — `reconcile` is due. |
| `surface_roots` | Optional. Directories the reconcile surface sweep walks, repo-relative. Absent means the conventional source roots that exist. |

## Item

```json
{
  "id": "RM-0007",
  "title": "Build-comparison page",
  "kind": "page",
  "status": "ready",
  "tier": "next",
  "deps": ["RM-0003"],
  "parent": null,
  "phase": "Phase 4",
  "priority": {"method": "RICE", "reach": 8, "impact": 2,
               "confidence": 0.8, "effort": 3, "score": 4.27},
  "owner_skill": "interface-design",
  "acceptance": ["Two builds render side by side"],
  "links": {"prd": "#61", "plan": null, "adr": null,
            "issues": [], "files": ["apps/web/src/app/compare/**"]},
  "created": "2026-07-29",
  "updated": "2026-07-29",
  "completed": null,
  "evidence": null,
  "notes": ""
}
```

### `id`

`RM-` plus four digits. Allocated as `max + 1`, never `count + 1`, so deleting an
item never re-issues its id. Ids are per-file, so two projects both having `RM-0001`
is correct and intentional (ADR-0026 project isolation).

### `kind`

`feature` · `page` · `function` · `integration` · `infra` · `data` · `ops` · `docs`
· `research`

Pick the narrowest that fits. `page` is a user-visible route; `function` is a
discrete capability behind one; `integration` is anything crossing a system
boundary; `infra` and `ops` are non-user-facing platform work.

### `status`

`proposed` → `ready` → `in-progress` → `done`, plus `dropped`.

- `proposed` — captured, not yet specified enough to start
- `ready` — acceptance criteria exist; could be picked up
- `in-progress` — claimed; a plan doc should be linked
- `done` — shipped, with `evidence`
- `dropped` — deliberately not doing it; still satisfies dependents

**There is no `blocked` status.** Blocking is computed from unmet `deps` every time
it is asked for. A stored flag goes stale the moment a dependency finishes, and
that is the single most common way a roadmap starts lying. `validate` rejects it.

### `tier`

`now` · `next` · `later` · `someday` — the human bucket. Ordering *within* a tier
comes from `priority.score`.

### `deps` and `parent`

`deps` are hard blockers: an item is unblocked when every dep is `done` or
`dropped`. `parent` is containment, not blocking — it links tracer-bullet slices to
the feature they decompose, and renders as a dashed cluster in the graph.

Cycles in either are detected by a three-colour DFS and reported as a closed path.
`validate` exits 1 on any cycle.

### `priority`

Produced by `decision-matrix` (RICE/WSJF/ICE), never hand-computed. Only `score` is
read by the engine; the other fields are provenance. An item with no score sorts
*after* every scored item in the same tier — so scoring is how you pull something
forward.

### `links`

| Key | Holds |
|---|---|
| `prd` | Issue ref for the PRD produced by `to-prd`, e.g. `"#61"` |
| `plan` | Path to the plan doc from `superplan` |
| `adr` | ADR ref if a hard-to-reverse decision landed |
| `issues` | Tracer-bullet issue refs from `to-issues` |
| `files` | Globs identifying the item's code — used by `reconcile` |

`files` is what makes drift detection work. An item with no `files` cannot be
checked against git or disk.

### Dates and evidence

`created` / `updated` are stamped automatically. `completed` is set when status
becomes `done` and cleared if it moves away. `evidence` should be a commit sha or
PR number — the answer to "how do we know this shipped?"

## Generated artifacts

| File | Notes |
|---|---|
| `ROADMAP.md` | Opens with a banner carrying the source `sha256`. Never hand-edit. |
| `graph.dot` | Graphviz source; status-coloured nodes, blocked items outlined red. |
| `graph.svg` | Rendered via `dot -Tsvg`. Absent graphviz degrades quietly. |

Freshness is checked by re-rendering and comparing the whole file, so a hand-edited
`ROADMAP.md` is detected even when the banner hash still matches.

## Validation

`validate` reports, and exits 1 on: unsupported schema version, malformed or
duplicate ids, unknown `kind`/`status`/`tier`, a stored `blocked` status, unknown or
self `deps`, unknown or self `parent`, an item marked `done` whose dep is not,
unknown link fields, dependency cycles, parent cycles, and a stale or hand-edited
`ROADMAP.md`.
