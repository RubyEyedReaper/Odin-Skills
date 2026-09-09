---
name: s2s
description: Use when a session must say something to another session rather than to a person — reporting back to a coordinator, messaging a peer or worker, deciding what a delegated session should put in its terminal versus in its report, or asking who is actually reading this output. Also on "tell the coordinator", "report back", "send it to the other session", "cross-session message", "the worker is too chatty", "cut the chatter", "nobody is reading this terminal", and when a message was sent and the reader never acted on it.
metadata:
  origin: Odin
---

# s2s — the channel between two running sessions

The decision, its rejected alternatives, and what this design costs:
[ADR-0162](../../docs/adr/0162-the-session-to-session-channel-has-an-owner.md). Where the bound lives
and why it warns: DEC-0106, DEC-0107.

## The stance

**A send reports on the send.**

That sentence is the whole skill, and it is not a caution — it is a measurement. `MISTAKES.md`
M-0125: a monitor brief named cross-session `SendMessage` to its coordinator as its only reporting
path. Every send is held for the recipient user's approval. Two expired undelivered. Each returned
`success:true`. The role produced correct findings and delivered none of them, and nothing anywhere
said so.

So the channel is real and the channel is not a delivery guarantee, and a session that treats it as
one loses its work silently. Three things follow, and they are the three this skill owns:

1. **The deliverable is a durable path.** Something committed and pushed, that the reader can pull
   whether or not any message arrives. The message is a **pointer** to it, plus an ask.
2. **A delegated session's terminal is a log, not a report.** Nobody is sitting in front of it. It is
   read, if at all, through `claude logs` — a channel measured at ten escape sequences per hundred
   bytes, redrawn by cursor moves, whose word spacing does not survive the transport. Writing a long
   report there is writing to a lossy channel with no reader.
3. **Those are different audiences with different budgets**, and a session that has not decided which
   one it is addressing writes for neither.

Rigid on the message bar and the report contract. The rest is judgment.

## What this owns, and what it must not restate

`s2s` governs a message and a report **in flight**. `successor` governs a session's **lifecycle**.
`handoff` governs the **document** that starts one. That sentence is the seam, and it is testable:
if the question is about a session that exists or is about to, it is not this skill's.

| The task | Its owner | Never re-derived here |
|---|---|---|
| The handoff document, its six-element bar, its frontmatter | `successor` | The bar and the template. `odin-relay.sh` already refuses on three of them; the refusals are cited, never restated |
| Provision, launch, integrate, tear down | `successor` | The five phases |
| Whether a session that exists is alive, and who owns it | `successor-manager` | The five verdicts, the health gate, the ownership register. Its red flag "a send reports on the send" is where this skill's stance comes from — cited, not copied |
| Which **inbound** supervision channel establishes what | `handoff` §3 | That table. This skill added one row to it — the outbound direction — and owns nothing else in it |
| Writing one brief, launching one successor, monitoring it | `handoff` | All of it |
| What a campaign contains and when it may close | `campaign` | The manifest, landedness by content |
| Whether to keep going at all | `endless`, `work-loop` | The continuation predicates, the six outcomes |
| Whether a cited path resolves from the reader's position | `.claude/rules/common/agents.md` § A Cited Path Is a Claim About the Reader's Position | Every word of it. A message is that same claim in a different envelope; read the rule there |
| The **shape** of prose to a human — fragments, no greeting, no first person as subject | ADR-0011, `voice_lint.py` | Every voice class. This skill adds volume and touches no existing class |

**The gap this fills**, and the only reason it is a skill: measured at `55bb7609`,
`grep -rn 'SendMessage' .claude/rules/ .claude/docs/*.md` returned **0**. Every campaign in this
workspace runs on that channel, and no rule, no skill and no gate said anything about it. Re-measure
before quoting the number; it is a fact about a commit.

## Two audiences

| | A human | Another session |
|---|---|---|
| Reading it | now, in the terminal, and can say "shorter" | later, cold, with none of your context |
| Channel | the turn's prose | a durable path, plus a message pointing at it |
| Budget | as much as the decision needs | four label lines, and structure after that |
| Failure | too little context to decide | a claim the reader cannot resolve or act on |

**An orphan has no human column.** A delegated session — launched by `odin-relay.sh`, running
unattended in its own worktree — has no reader in its terminal at all. Everything it types there is
a log for a post-mortem nobody may run. That is not a reason to type nothing; it is a reason to type
the things a post-mortem needs and stop.

## What a message must carry

Four fields. Each prevents a failure that has happened.

| Field | Prevents |
|---|---|
| **The recipient, by name from `ListAgents`** | a send into a slot that is gone. The registry outlives the daemon that served it, so a name you remember is not a name that resolves |
| **The durable path**, resolvable from the *reader's* position | M-0125 verbatim. The path is the deliverable; the message only points at it |
| **The ask, in one imperative** | a message that reports and requests nothing, which the reader files rather than acts on |
| **What you will do if no reply arrives** | a sender that blocks forever on a channel that drops, and a reader who did not know they were the blocker |

On the second field, the reachability question is **not** this skill's to answer:
`.claude/rules/common/agents.md` § A Cited Path Is a Claim About the Reader's Position owns it, and a
message is the same claim in a different envelope. Read it there. A path is reachable from where the
reader stands, on the branch that checkout holds — never from where you stand.

Two things a message is never for, both settled elsewhere: asking a peer to perform an action your
own session was refused (that launders a permission decision), and carrying a fact that should have
been committed.

## The report contract

The relay seed asks for the opening turn in **labels** — `Item:`, `Branch:`, `Evidence:`, `Next:`,
and nothing else — rather than in four lines of prose. That is the same instruction it always
carried, in the form that costs nothing: a prose restatement contradicted the silence instruction
nine lines below it in the same string, and labels do not.

A delegated session's turn — every turn, not only the last, because nothing marks a turn as last —
is bounded on **narration**: lines that are neither markdown furniture, nor a label line, nor inside
a fence.

**Structure is free.** `Verdict:` / `Next action:` lines, tables and fenced command output cost
nothing against this bound however long they run. Continuous prose costs its full length.

That is the point of bounding narration rather than volume, and the reason is **not** that narration
tells the two audiences apart — measured, it separates their medians better than volume does and both
distributions still overlap. The reason is that a narration bound is *satisfiable without losing
information*: the cheapest way to comply is to keep the evidence and drop the prose around it. Under
a volume cap the cheapest way to comply is to delete evidence, which is how a check meant to improve
reports ends up degrading them.

Write the report as:

```report-shape
Item:      <qualified id>
Branch:    <branch> at <sha>, pushed
Verdict:   <landed | blocked | escalated>, and the one deciding fact
Evidence:  <the command that proves it, and its result>
Next:      <the imperative, or none>
Blocker:   <what is in the way, or none>
Durable:   <the path the reader can pull>
```

Not a template to fill in mechanically — a shape. Anything that does not fit one of those lines is
probably a restatement of work the reader can read for themselves.

### The eight kinds — what a delegated session may say at all

The bound above asks *how much* an orphan narrates. A second, stricter question sits beside it: an
orphan should narrate **nothing**. It has no reader in its terminal, so it speaks only to declare one
of eight things, as a label at the start of a line:

| Kind | Say it when | Route to |
|---|---|---|
| `Mistake:` | something went wrong that a check could have caught | `oops` |
| `Caveat:` | a hazard with a condition under which it recurs | `caveat` |
| `Memory:` | something durable about this workspace a later session needs | `learn` |
| `Learning:` (or `Learned:`) | a finding that outlives the run | `learn` |
| `S2S:` | a message to another session, and the durable path it points at | this skill |
| `Ready for integration` | the branch is pushed and the coordinator may take it | `successor` |
| `Mutation:` | a change whose actual effect nobody has checked yet | `mutations` |
| `Issue:` | work discovered that belongs on the tracker | `roadmap`, `to-issues` |

**Silence is compliant, and is the ordinary case.** These are exception conditions — "say something
if there is a mistake" — not a checklist to fill in. A turn with nothing to declare declares nothing.

The report shape's own labels (`Item:`, `Branch:`, `Verdict:`, `Evidence:`, `Next:`, `Blocker:`,
`Durable:`) are declarations too, so a compliant structured hand-back passes both legs. Evidence
**under** a declaration is free until a blank line closes the block, which is what stops one `Issue:`
line laundering a page of narration after it.

### Its detector, and the limits of it

`.claude/scripts/lib/s2s_report.py`, called from a leg in `.claude/hooks/odin-voice-lint.sh`, with
its matrix at `.claude/tests/s2s.test.sh`.

| Property | Value | Why |
|---|---|---|
| Caps | 4 narration lines, 60 narration words | The relay seed's own opening instruction, with no headroom. It was 8/120 — that instruction plus room for a verdict, a blocker and one spare — until 2026-09-09, when the owner asked for less. The headroom was the part being spent, and the spare invited a fifth line. **Not** calibrated to the measured population, in either direction: calibrating a bound to what motivated it enshrines the defect |
| Override | `ODIN_S2S_MAX_LINES`, `ODIN_S2S_MAX_WORDS` | One place, the hook's default |
| Posture | unattended only | An attended human is who the volume is *for*, and holds a working control. An orphan has neither |
| Severity | **warn**, never block | A `Stop` block cannot un-print a report already emitted, spends a second turn, and — decisively — the `stop_hook_active` guard is shared across every `Stop` hook, so blocking here makes the next `Stop` self-disable `odin-unfinished-work.sh` and `odin-completion-evidence.sh` |
| Off switch | `ODIN_S2S_REPORT_ENFORCE=off` | |

Measured against the **previous** caps of 8/120, 93 of 154 delegated final turns exceeded the line
cap and 110 of 154 the word cap. The current pair is stricter, so the fire rate is higher again;
re-derive it rather than assuming either number.
**That is the gap being reported, not evidence the caps are wrong** —
and it is a second reason the class warns rather than blocks, since a class that refuses six turns in
ten on the day it lands is a class that gets switched off, taking the eight voice classes in the same
hook with it.

Re-derive all of it rather than trusting this paragraph:

```sh
python3 .claude/skills/s2s/scripts/report-volume.py
```

**Promotion to `block` has a stated condition, and the comment does not satisfy it**: the shared
`Stop` re-entrancy guard must become per-hook, *and* a measured run must show the fire rate near
zero. Either alone is insufficient.

## What is checked, and what is not

`.claude/rules/ci/rule-enforcement.md` § A Normative Statement Names Its Detector is binding, and an
unenforced rule is indistinguishable from an enforced one unless it says so. So:

| Statement | Detector |
|---|---|
| A delegated session's turn stays within the narration bound | `.claude/scripts/lib/s2s_report.py` via `odin-voice-lint.sh`; matrix `.claude/tests/s2s.test.sh` |
| A delegated session's turn declares a kind or says nothing | `.claude/scripts/lib/s2s_kinds.py` via the same hook; matrix `.claude/tests/s2s-kinds.test.sh`. Warn, unattended only, off switch `ODIN_S2S_KINDS_ENFORCE=off`, vocabulary override `ODIN_S2S_KINDS` |
| A brief naming a send as a reporting channel names a durable path and the send-is-not-receipt note | `.claude/scripts/s2s-brief-check.sh`; same matrix |
| The doctrine states what the outbound channel does **not** establish | `.claude/tests/supervision-channels.test.sh`, which asserts that cell of every row |
| A cited path resolves from the reader's position | `odin-relay.sh` for handoffs, `doc-reference-check.sh` for repository docs — both owned elsewhere |

**Unchecked, named in the open rather than left to be assumed:**

- **Nothing observes a send.** `SendMessage` is a harness tool with no repository-state footprint —
  no script under `.claude/` can see a send, a delivery, or a refusal. Every detector above has a
  **document** as its subject for exactly that reason. A wrapper script every send routed through
  would look enforced and assert nothing, because the tool can still be called directly.
- **The four-field message bar is held by a reader**, not by a gate. Only its durable-path half is
  checked, and only where a *brief* names the channel.
- **`s2s-brief-check.sh` is not wired into `odin-relay.sh`.** That is where it belongs, as one clause
  beside the relay's existing content refusals. Until then it runs from the matrix over the committed
  corpus. Scope, not design.
- **A session that never armed its posture is outside the bound's reach.** Narrow rather than absent
  — such a session is already stopped earlier by `odin-plan-gate` on its first gated write — but it
  is a gap.

## Red flags

| Thought | Reality |
|---|---|
| "The send returned success, so it arrived" | It reports on the send. Two returned `success:true` and expired undelivered (M-0125) |
| "I'll put the findings in the message" | Then the findings exist in exactly one place, and it is a channel that drops. Commit them, push, point at them |
| "A human will read this terminal if something goes wrong" | Through `claude logs`, which loses word spacing. Put what a post-mortem needs in the commit and the branch |
| "The report should be thorough because the run was complicated" | Thorough is structure, not prose. Add a table and a fenced transcript; do not add paragraphs |
| "Nothing went wrong, so there is nothing to report" | Correct — say nothing. Silence is the compliant default for an orphan, and a turn of tidy prose about what you did is the failure the kind bound reports |
| "It's only a warning, so it doesn't matter" | It is a warning because blocking would suspend two sibling gates, not because the bound is optional |
| "This is about which session is alive" | That is `successor-manager`. This skill is about what a session says |
| "I'll ask the coordinator which option to take" | Never. `.claude/rules/common/decision-authority.md` — decide, record, continue. A message that asks a question is a stop with extra steps |

## Quick reference

| Situation | Do |
|---|---|
| Reporting to a coordinator | Commit and push first. Then message the path, plus one imperative |
| Nothing landed yet | Say so, name the blocker, name what you will do next. A blocked report is still a report |
| The terminal is filling with prose | Cut to the seven lines of the report shape. Structure is free |
| A message got no reply | Do what you said you would do without one. Never block on the channel |
| Asked what a delegated session should say | The report shape above, and the four-field message bar |
| Asked whether a worker is alive | `successor-manager` |
| Asked how to launch or integrate one | `successor`, or `handoff` for a single one |
