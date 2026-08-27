# The campaign record

One JSON manifest per campaign, committed under `.claude/docs/campaigns/<slug>.json`. It holds the
**plan** — the decisions someone made about what this campaign contains and in what order — and
nothing that describes the present.

JSON rather than Markdown with frontmatter for a mechanical reason: there is no YAML parser in the
standard library, and a hand-rolled one is a second thing that can be wrong about a file whose
entire job is to be unambiguous. The prose half of a campaign already has a home — the per-worker
handoff, whose quality bar `successor` owns.

Committed rather than written under `.claude/.runtime/` for two: a record of decisions belongs in
the file tier that survives a container reset (ADR-0009), and every runtime class must be declared
in the retention script or it is a retention gap that reads as green. The engine takes the manifest
path as an argument, so a scratch campaign passes a scratch path.

## Fields

| Field | Holds | Why it is here |
|---|---|---|
| `campaign` | a slug | Names the unit of work in reports and in the close-out. |
| `objective` | one sentence | What the campaign is for. A campaign whose objective cannot be stated in a sentence is two campaigns. |
| `base` | comparison ref, default `origin/main` | Landedness is a question about content *in a base*. Naming it makes the question answerable and the answer reproducible. |
| `remote` | default `origin` | The channel consulted first, because the others cannot report their own absence. |
| `close_out` | the criteria, as strings | Written when the campaign is planned, not when it is closed. Criteria authored at the end are criteria fitted to the result. |
| `waves[].wave` | an ordinal | Waves **order** the work. They do not scope it — a worker's scope is its own field. |
| `waves[].workers[].worker` | the worktree / session name | The handle a coordinator uses to find the session and its worktree. |
| `waves[].workers[].branch` | the topic branch | The ref whose content landedness is computed from. |
| `waves[].workers[].item` | a **qualified** roadmap id, `<roadmap>:<id>` | The single reference to what the work is. Qualified because a bare `RM-0302` is ambiguous across roadmaps, and an id that resolves in the wrong one is worse than one that does not resolve at all. |
| `waves[].workers[].scope` | path globs | The `edit only:` line from the handoff, in machine-readable form, so a scope diff at integration is a computation rather than a memory. |
| `waves[].workers[].reserved` | ids allocated up front | Parallel workers that allocate their own ids all win, and the collision surfaces at integration when it is most expensive. |

## What it deliberately does not hold

**No status, anywhere.** Not on the campaign, not on a worker row. `validate` refuses `status`,
`state`, `progress`, `completed`, `complete`, `evidence`, `landed`, `done` and `verdict` wherever
they appear.

A stored status is a claim that was true when it was written. It goes stale silently — the file
reads identically whether it is current or six hours old — and this repository has measured what
that costs: 31 of 43 issues in one burn-down were already fixed on `main` while the tracker still
said otherwise. Status is computed from the roadmap plus branch landedness every time it is asked
(ADR-0113).

`evidence` is in the refused set for a slightly different reason: the landed sha exists, but it is
the **roadmap's** to hold. Copied into the manifest it becomes a second source of truth, and the two
diverge the moment a branch is re-landed.

**No roadmap content.** `title` and `acceptance` are refused. The manifest references an item by id
and reads the rest from the roadmap, because a copied title drifts from its original and nothing
detects it.

**No session state.** Whether a worker is live, stalled, failed or gone is `successor-manager`'s
verdict, computed from channels that session does not control. A field here recording it would be
the subject's account of itself, written down and then trusted after it stopped being true.

**No handoff.** The six-element bar belongs to `successor`. A copy of the bar in a second file drifts
from the original, and the looser copy is the one that wins.

## The half before the colon

`harness:RM-0302` names the **roadmap**, not the memory class. The two are different fields and
were conflated once already: the live harness roadmap's `scope` is `operational` while every id it
prints reads `harness:RM-…`, so a prefix compared against `scope` reads every real id as foreign
and reports the whole campaign undeterminable.

The identity rule belongs to the roadmap engine — a document's declared `slug` wins, and otherwise
the slug is derived from the document's own path, deliberately blind to which checkout or worktree
it is read from. This engine **calls** that rule rather than copying it, for the same reason it
calls `bl_classify` rather than reimplementing landedness.

An id naming another roadmap is `undetermined`, never resolved locally: answering it here would
answer a question about the wrong roadmap.

## What a reader should do with a refusal

| Refusal | What it means | Next |
|---|---|---|
| `manifest stores 'status'` | Someone cached a computed value. | Delete the field. Run `status` to get the current answer. |
| `item ... is unqualified` | A bare roadmap id. | Qualify it: `<roadmap>:<id>`. |
| `campaign declares no workers` | The manifest would examine nothing. | A green from an instrument that looked at nothing is the failure this refuses; add the workers. |
| `worker ...: copies the roadmap's 'title'` | A second source of truth. | Remove it; the id already names the item. |
| `item ... is claimed by more than one worker` | Two workers, one item. | Split the item or merge the workers — parallel sessions on one item collide at integration. |
