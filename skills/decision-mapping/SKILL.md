---
name: decision-mapping
description: >-
  Use when a loose idea is too big for one agent session and the way to the finish line is not
  visible yet — "where do I even start", "we need to figure out X before we can plan", a space with
  several open questions that hang on each other. Charts a committed markdown decision map: a named
  destination, explicit out-of-scope, typed tickets (research / prototype / grilling / task, each
  HITL or AFK), blocking edges, and a fog frontier that advances one resolved ticket at a time.
  Produces decisions, not deliverables. Not for scoring options against criteria (`decision-matrix`)
  or for sequencing work already decided (`roadmap`, `blueprint`).
version: 1.0.0
user-invocable: true
argument-hint: "[the loose idea, or a path to an existing map + optional ticket name]"
license: MIT
metadata:
  origin: Odin — fork of mattpocock/skills `wayfinder` (formerly `decision-mapping`)
---

# Decision Mapping — chart the way before planning it

A loose idea has arrived: too big for one agent session, and wrapped in fog. The way from here to the
**destination** is not visible yet. This skill charts that way as a **decision map** — a single
committed markdown file — then works its **decision tickets** one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting: a spec to hand off, a
decision to lock before planning starts, or a change made in place. The map is domain-agnostic.

**Plan, don't do.** Each ticket resolves a decision; the map is done when nothing is left to decide
before someone goes and builds. The pull to just do the work is the signal you have reached the edge
of the map and it is time to hand off — to `writing-plans`, `superplan`, or `blueprint`. An effort
can override this in its `## Notes`; absent that, produce decisions, not deliverables.

**Refer by name.** Tickets have names — their headings. In everything a human reads, use the name,
never a bare number. A wall of `#3, #4, #7` is illegible; names read at a glance. The numbers exist
so blocking edges can point at something stable, and they ride inside the name, never instead of it.

## Where the map lives

One markdown file per effort, **committed** alongside the work it plans:

| Effort | Path |
|---|---|
| Harness | `.claude/docs/plans/<YYYY-MM-DD>-<effort>-map.md` |
| Project | `<project>/docs/plans/<YYYY-MM-DD>-<effort>-map.md` |

A file, not an issue tracker: the committed file tier is the reset-proof one (ADR-0009), and it is
the tier a fresh session can read with no credentials and no network. The whole map is loaded as
context every session, so **it must stay compact** — it is an index, not a store. A decision lives in
exactly one place, its ticket; the map gists and links, never restates.

Assets created while resolving a ticket (a research note, a prototype, a spec) are **linked** from
the ticket, never pasted into it.

## Map structure

```markdown
# Decision map — <effort name>

## Destination

<what reaching the end of this map looks like. One or two lines; every session orients to it
before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index — one line per resolved ticket, enough to judge relevance, then open the
     ticket for the detail -->
- **[#3 Relational or non-relational?](#3-relational-or-non-relational)** — Postgres; the
  access patterns are relational and the ops burden is already carried.

## Not yet specified

<!-- in-scope fog: suspected questions not yet sharp enough to ticket -->

## Out of scope

<!-- work consciously ruled beyond the destination; never graduates -->

---

## #1: <Ticket name>

Type: research | prototype | grilling | task   ·   HITL | AFK
Blocked by: #<n>, #<n>
Claimed by: <session/agent id> <ISO-8601>   ← absent means unclaimed
Status: open | resolved | out-of-scope

### Question

<the decision or investigation this ticket resolves>

### Answer

<written on resolution; the ticket is the one place the detail lives>
```

Each ticket is sized to **one agent session**. A ticket that cannot be resolved in one session is two
tickets, or it is a `blueprint` step wearing a ticket's clothes.

## Ticket types

Every ticket is either **HITL** — worked *with* a human who speaks for themselves — or **AFK**, driven
by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in
for the human's side of it. *A grilling ticket whose agent answered its own questions is not resolved.*

| Type | Mode | Use when | Resolved by |
|---|---|---|---|
| **Research** | AFK | The answer is knowledge outside this working directory — docs, a third-party API, a knowledge base | A subagent, in parallel with its siblings; produces a linked markdown note |
| **Prototype** | HITL | "How should it look / behave" is the question — raise the fidelity of the discussion with something cheap and concrete to react to | `prototype`; links the artifact |
| **Grilling** | HITL | Conversation. The default case | `grilling` / `grill-with-docs` + `domain-modeling` |
| **Task** | either | Manual work that must happen before a *decision* can be made — provisioning access, moving data so its shape can be seen | The agent alone where it can; otherwise a precise checklist for the human. The answer records what was done and any facts later tickets depend on (paths, URLs, counts) |

`task` is the one type that *does* rather than decides, and it earns its place only by unblocking a
decision — never by delivering a piece of the destination.

**HITL in an unattended run.** A HITL ticket cannot be resolved by an agent running alone, and
inventing the human's half is the failure this typing exists to prevent. It is also not a licence to
stop: take every AFK ticket the frontier offers, and leave the HITL ones claimed by nobody with the
question sharpened. That is a real advance, and it is reported as one.

## Fog of war

The map is *deliberately* incomplete. Beyond the live tickets lies fog: decisions you can tell are
coming but cannot yet pin down, because they hang on questions still open. Resolving a ticket clears
the fog ahead of it, graduating whatever is now specifiable into fresh tickets — one at a time, until
the way to the destination is clear and no tickets remain.

**Fog or ticket?** The test is whether you can state the question precisely *now* — not whether you
can answer it now.

- **Ticket** when the question is already sharp, even if it is blocked and you cannot act on it yet.
- **Not yet specified** when you cannot phrase it that sharply. Do not pre-slice fog into
  ticket-sized pieces: one patch may graduate into several tickets, or none.

`## Not yet specified` excludes what is already decided, what is already a live ticket, and what is
out of scope.

## Out of scope

Fog gathers only *toward* the destination. The destination fixes the scope, so work beyond it is
**out of scope** — not fog, and not a candidate for `## Not yet specified`.

Ruling something out of scope is a scoping act, not a step on the route. When an existing ticket turns
out to sit past the destination — mis-scoped while charting, or exposed by a resolution — mark it
`Status: out-of-scope` and leave one line in `## Out of scope`: the gist, why it is out, and a link.
It stays out of `## Decisions so far`, which records the route actually walked.

Out-of-scope work never graduates. It returns only if the destination is redrawn, and then as a fresh
effort, not a resumption.

## Claiming — before any work, in one commit

A session **claims** a ticket by writing its `Claimed by:` line **and committing that line before
doing anything else**. An open ticket with no `Claimed by:` is unclaimed and takeable.

The claim and its commit are one act. A claim that lives only in a working tree is invisible to the
concurrent session about to take the same ticket, which is precisely the collision the claim exists
to prevent. Release a claim you are abandoning by deleting the line — a stale claim is worse than
none, because it silently removes a ticket from the frontier.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session** — research tickets excepted,
since they run as parallel subagents and cost this session nothing but the dispatch.

### Chart the map

Invoked with a loose idea.

1. **Name the destination.** `grilling` + `domain-modeling` to pin down what this map is finding its
   way to. The destination fixes the scope, so it is settled first.
2. **Map the frontier.** Grill again, **breadth-first** — fan out across the space rather than deep on
   one thread, surfacing the open decisions and the first steps takeable now.
   **If this surfaces no fog, you do not need a map.** The way is already clear; say so and hand off
   to `writing-plans` (or `to-prd` for a multi-session build) instead of charting an empty one.
3. **Write the map file** — Destination and Notes filled in, `## Decisions so far` empty, the fog
   sketched into `## Not yet specified`.
4. **Write the tickets you can specify now**, then wire `Blocked by:` edges in a **second pass** —
   tickets need numbers before they can reference each other. Wiring sorts them into the frontier
   (open, unblocked, unclaimed) and the blocked.
5. **Fire the research subagents** — one per `research` ticket, in parallel, each returning a linked
   note. They are AFK by construction; nothing waits on a human.
6. **Stop.** Charting is one session's work and hand-resolves nothing. Commit the map.

### Work through the map

Invoked with a map path, optionally a ticket name. Without one, **you** pick the next ticket, not the
user.

1. Load the **whole map** — it is written to be loaded whole.
2. Choose the ticket: the one named, else the first frontier ticket in order. **Claim it and commit
   the claim** before any work.
3. Resolve it. Open related or resolved tickets on demand; invoke the skills `## Notes` names. In
   doubt: `grilling` + `domain-modeling`.
4. Record the resolution in the ticket's `### Answer`, set `Status: resolved`, and append the one-line
   gist to `## Decisions so far`.
5. Add newly-surfaced tickets (write, then wire); graduate any fog the answer sharpened, **clearing
   each graduated patch from `## Not yet specified`** so it lives in exactly one place. If the answer
   reveals a ticket sits beyond the destination, rule it out of scope rather than resolving it. If it
   invalidates other tickets, update or delete them.
6. Commit. Expect concurrent sessions to be editing the same file.

## Hand-offs

| Situation | Next |
|---|---|
| A ticket is really "which of these options" with scorable criteria | `decision-matrix` (`/decide`) — score it, record the DEC, paste the gist into the ticket |
| The fog is gone and the route is clear | `writing-plans`, or `superplan` for a single non-trivial PR |
| The cleared route is multi-PR | `blueprint`, then register its steps as `roadmap` children |
| The effort produced a durable constraint | `architecture-decision-records` |
| A ticket surfaced new vocabulary | `domain-modeling` — land it in `CONTEXT.md` as you go |

## Failure modes

- **Charting a map that has no fog.** If the grilling surfaces nothing undecided, the map is
  ceremony. Hand off to planning and say why.
- **Resolving three tickets in one session.** The later ones are answered from the momentum of the
  first, not from the evidence. One per session.
- **Restating a decision on the map.** The map gists and links; the ticket holds the detail. Two
  copies means one of them is about to be wrong.
- **An agent resolving a HITL ticket alone.** That is not a resolution; it is a guess with a heading.
- **Pre-slicing the fog.** Fog written as five neat tickets is five guesses about questions you cannot
  yet state.
- **Claiming without committing.** The concurrent session cannot see your working tree.
