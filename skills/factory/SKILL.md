---
name: factory
description: Build a dark factory into a repository — work goes in as an issue, validated code comes out, nobody reads the diff. Five components in construction order: the guidance layer, the validation harness, the workflow-driven repo, deployment, and the trigger that makes it autonomous. Encodes the AI coding process the repo already runs rather than replacing it. Requires a PRD as input and deliberately does not write one. Use when the user wants a dark factory, an autonomous or self-driving repository, a software factory, an agent that ships its own code, an unattended or overnight coding loop, autonomous PRs, lights-out coding, a repo that maintains itself, or asks how to reach level 4 or 5 of AI coding autonomy. Also use to audit, arm, raise the dial on, or stop a factory that already exists.
argument-hint: "[path/to/product.prd.md] [optional: path/to/repo]"
arguments: [prd, repo]
metadata:
  origin: fork
  upstream: coleam00/skills — build-dark-factory @ ecef6ffd
  forks: build-dark-factory
---

# Factory

> **Voice (ADR-0011).** Prose to human stays Odin: fragments, no first person, no greeting, no
> closer. Applies inside every phase below, including the ones whose upstream text is written as
> conversation. Code, paths, commands, config, templates and every written deliverable stay
> normal — a `MISSION.md` this skill produces is a deliverable, not speech.

**What the user typed:** $ARGUMENTS

> Work out the PRD path and the repo path from that line. Do not print a parse nobody checked —
> the split is on whitespace, so a sentence yields the first two *words* as the two paths. Read the
> line, find the thing that looks like a `.md` PRD and the thing that looks like a directory,
> confirm both in one sentence, then Phase 0. One given: infer which from its extension, take the
> repo as the current one. PRD path absent from disk: say so, stop.

A dark factory: work in one end, shipped code out the other, nobody in between. Work arrives as an
issue. Workflows plan, build, validate, merge. Deployment carries it to users. Nobody reads the
diff.

That last sentence is the whole difficulty. Rest is plumbing.

**Build it into the repo. Do not hand over a design document.** Every phase ends with files
committed and something demonstrably working.

---

## Odin-specific, before anything else

Four things this fork changes about how the upstream skill behaves. `UPSTREAM.md` carries the
reasoning; these are the operational consequences.

1. **No question rounds.** `AskUserQuestion` is never called, in any phase (ADR-0052). The interview
   still runs, still computes its questions, still carries one recommendation each — and then
   **adopts the recommendation and records it**, as a numbered DEC or in the plan doc's
   decision-forks section. `references/interview.md` states the discharge per round.
2. **Plan before edits.** The three preconditions in CLAUDE.md item 5 apply to this skill like any
   other: a named process skill, a plan doc with ≥3 resolved decision forks, a recorded scope
   decision. Plan goes in `.claude/docs/plans/` — the only directory `odin-plan-gate.sh` searches.
3. **The governance files are protected mechanically, not by prompt.** Layer 1H of
   `.claude/hooks/odin-safety-guard.sh` refuses a write to `MISSION.md`, `FACTORY_RULES.md` or
   `FACTORY.md` in a factory repo. A guard a node calls is a guard the node can skip.
4. **One decider, many entry points (ADR-0170).** `factory/orchestrator.sh` decides what runs next.
   `workflows/factory-lap.yaml` runs one dispatcher tick as an Archon workflow, so a lap is
   startable, watchable, resumable and cancellable through the same surface as everything else — and
   it decides nothing. An entry point may observe, refuse before spending, and report; it may not
   compute the refusal, and it may not carry its own copy of a value `factory/config.sh` owns. This
   was prose here until the lap workflow's preflight drifted into its own stop-button test, and it
   is now checked by `.claude/tests/factory.test.sh`. The rule half is
   `.claude/rules/factory/patterns.md`.

---

## Output discipline

Long document; short speech. A user who ran the upstream version reported it as *"incredibly
frustrating and hard to process, overwhelming to say the least"* — and that was the skill working,
explaining itself at every step. Reasoning that belongs in a file is noise in a chat window.

| Moment | Budget |
|---|---|
| Between one decision and the next | nothing |
| Finishing a phase | two lines: what exists now, next action |
| Explaining a concept | only on request, short version first |
| Reporting a file written | one line: path, and what decides its content |
| A command's output | never pasted; verdict and number only |

Never: announce a phase before doing it; restate a decision as a paragraph; explain why the skill
works this way (that is in `references/`, for the agent); print a table of what is about to be
built; summarise at the end of a phase what was said at its start; paste a file just written.

Test before any message: *would this still be true if deleted?* If a file on disk carries the fact,
delete it.

---

## What this is

**Not a different way of coding with AI. The way the repo already codes with AI, with the human
checkpoints removed.**

Whatever process runs today is what goes inside. Spec Kit, BMAD, a PRP framework, Odin's own
roadmap → superplan → TDD → review chain. Steps stay. Skills stay. MCP servers, rules files,
subagents, commands: same.

One thing changes. Nobody approves the plan, nobody reads the diff before it ships.

So: write down the process that exists, then build the parts that make walking away safe. Read
`CLAUDE.md`, `AGENTS.md`, `.claude/` and `.cursor/` for it rather than imposing the example.

**This skill does not write the PRD.** Deliberate. `to-prd` writes one; come back with a file.

## Two facts that shape every decision below

- **Cached reads dominate cost over output, by orders of magnitude.** Context size drives the bill
  far more than how much gets written — which is why the premium model belongs in the planning slot
  and a cheaper one everywhere else.
- **Refusing is cheap; building is not.** Borderline Phase 0 → refuse. The wrong factory is
  discovered in month two and no prompt patches it.

Offer to stop after the guidance layer for a smaller first commitment. Useful even with no cron
ever turned on.

## Three harnesses, named once

| Harness | What | Who builds it |
|---|---|---|
| **Agent harness** | Claude Code, Codex, Pi — prompt to edits | vendor; not your problem |
| **Factory harness** | how work is planned, implemented, reviewed, gated, merged | `templates/runner/`, mostly copied |
| **Validation harness** | the tools the agent uses to check its own work as a user would | **you**, and it is most of the work |

Factory harness decides what runs. Validation harness decides whether what ran was worth keeping.
Confusing them is how an impressive DAG ships broken software on schedule.

> **The factory harness is templatable. The validation harness is not.**

---

## Construction order

Numbered in anatomy order; built in this one.

| Build | Component | Why here |
|---|---|---|
| 0th | *(the PRD)* | the input, not a component |
| 1st | **Guidance layer** (#4) | markdown; everything else reads it; cheapest, highest leverage |
| 1.5th | *(walking skeleton)* | greenfield only, after the guidance layer. Thinnest slice yielding one assertable behaviour. Phase 0c |
| 2nd | **Validation harness** (#5) | the long pole; start before you need it, you will be wrong about it twice |
| 3rd | **Workflow-driven repo** (#1) | now the workflows have rules to obey and checks to pass |
| 4th | **Deployment** (#3) | close the loop to real users before making it unattended |
| **Last** | **The trigger** (#2) | the switch. On only when 1–4 are proven |

**Trigger last, deliberately.** Turning on a scheduler is the moment the repo becomes autonomous.
Everything before it runs by hand and gets inspected. A factory whose dispatcher came first is an
unsupervised code generator nobody has ever checked.

State this before starting. Reframes the project from "wire up an agent" to "earn the right to walk
away".

---

## Phase 0 — the input, the refusals, greenfield

### 0a. There has to be a PRD

Input is a PRD: what is being built and why, at the level a product manager writes. Problem, users,
scope, and above all **non-goals**. Spec, brief, product doc, epic — name does not matter.

It does **not** contain the tech stack, architecture, data model or file layout. Engineering
decisions, decided later or already settled by the existing codebase.

**When it contains one anyway — and it usually will — treat it as SETTLED, not as scope, and say
so.** Someone who is not an engineer writes down the stack because it is the part they are confident
about. Arguing costs the room and buys nothing. Take it as decided, keep it out of `MISSION.md` (not
scope; the factory must not defend it), flag it in one line. Check **reachability** out loud: a
stack exercisable only through a rendered page needs its logic split out behind something an E2E can
call. See 0c.

Read the PRD in full before the first question. Then map it:

| PRD gives | Factory builds |
|---|---|
| the problem, why it matters | the framing at the top of `MISSION.md` |
| who the users are | the person the E2E path is acted out as |
| MVP scope, capability areas | what triage may accept |
| **non-goals** | **`MISSION.md` out-of-scope-forever — the most load-bearing list in the build** |
| success metrics | what the validation harness ultimately argues about |
| open questions, TBDs | a decision to **propose**, not a wall. Pick a defensible value, record it, hold the merge for a human. Escalate only for `FACTORY_RULES.md` §7.2. "Open" means "not yet decided", never "you may not propose" |

What the PRD does not give — and what the interview exists to produce: the E2E happy path narrated
as observable steps; the protected list; the two gates that must be code; the target autonomy level;
the stop button; how work arrives and where the factory runs.

**Refuse with no PRD.** Say why: without written scope `MISSION.md` has no out-of-scope list, and
without that list every plausible request is arguably in scope. The factory builds all of them.
Single most common way an autonomous repo goes wrong; no prompt patches it later. Point at `to-prd`
and stop.

### 0b. The repo has to be observable

Inspect before asking. A test command that runs, a way to start the app, existing CI, whether the
tracker CLI is authenticated, whether the repo is public, and **whatever AI coding setup already
exists** (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.cursor/`, skills, commands, MCP config). That last
one is the process to encode, and it is usually already sitting there.

**Decide which repo this is by LOOKING. Do not ask.** The refusals below are written for one and
misfire on the other:

- **Brownfield** — source files that are not scaffolding. Refusals apply as written.
- **Greenfield** — a PRD, a `.gitignore`, `.claude/`, a README, nothing that runs. Both refusals are
  then trivially true and carry no signal. Go to 0c; do not refuse.

Say which, in one line, so it can be corrected: *"no source outside docs/ and .claude/ — greenfield."*

**Refuse, and say why, when:**

- **Nothing can observe the software working** — nothing to start, invoke, or import. Component 5
  has nothing to stand on. This is about software that cannot be observed, not software that does
  not exist yet; greenfield trips it by definition, see 0c. **A library is not this case** — the
  harness ships three drivers (`http`, `cli`, `library`), and `APP_STARTED driver=library` means the
  import succeeded, the same claim a server answering makes. Read
  `templates/harness/appproc.py` before calling something unobservable.
- **No CI and no test command at all.** Start with a test suite. A dark factory on zero checks is a
  machine for merging plausible code.
- **The agent would touch auth, payments, or a blast radius nobody can absorb.** Protected list, not
  factory.

Saying no here is cheaper than saying it in month two. Offer the smaller version: guidance layer and
harness now, stop before autonomy.

### 0c. Greenfield — the walking skeleton, and it is SMALL

**The common case.** Most people want a factory at the start of a project, which is also the best
time: the guidance layer is cheapest to write when nothing contradicts it, and the sim/presentation
split below is free before there is code.

**The skeleton is the thinnest vertical slice, NOT the MVP.** This is where greenfield goes wrong,
in the same direction every time: build the core so the harness has something to test, and now the
interesting risky work has been done by hand and the factory gets the leftovers. Inverts the point.

Build the smallest slice producing one observable, assertable behaviour end to end. A game: one
enemy, one hit, one damage number, persisted across restart. A service: one endpoint that writes one
row and reads it back. A CLI: one command, one flag, one changed line of output.

Test is not "is this useful" — **"can an E2E assert something a user would notice?"** Yes → stop
building, start building the factory. Everything else in the MVP is issues.

State the size and what is deliberately left out, before starting.

**The reachability constraint, decided now.** The harness reaches software exactly three ways:
`http`, `cli`, `library`. A rendered window, a game loop, a canvas, a native UI is none of them. So
on greenfield: **the logic must live behind a headless, scriptable surface an E2E can drive.**
Simulation separate from rendering; domain separate from view. Nearly free now, a rewrite later.

**The factory's scope is strictly smaller than the MVP.** Some items are not machine-validatable and
never will be — *"combat feels good"*, *"a first-time player understands it"*. Name them, write them
into `MISSION.md` and `FACTORY_RULES.md` as **permanently human**, and be clear the factory owns the
simulation layer rather than the product.

Then, in order: Phase 1 (interview, unchanged on greenfield) → Phase 2 (guidance layer) → the
skeleton, named and sized against the journey from R1.1 → Phase 3 onwards.

**The skeleton fork is resolved, not asked** (ADR-0052). Default: build the thin skeleton now, then
the factory on it — naming the slice and naming what is left out, so "recommended" cannot be read as
"I will build your MVP". Take *guidance layer and scaffolds only* when the repo already has an owner
building the skeleton; take *stop, architecture first* when the PRD defers the thing 0c's
reachability constraint depends on. Record the choice and its reason as a DEC either way.

## Phase 1 — interview

Read `references/interview.md` and work through it. It is the skill in question form: what each
question is for, what a good answer sounds like, which vague answers to push back on.

**Three rounds, not a questionnaire.** Round 1 is three questions that decide the project. Round 2
is six only the user could answer — each about something that has **already happened to them**.
Round 3 is every remaining setting with its default filled in.

**Every round resolves without waiting** (Odin fork). Compute the questions, derive the options from
their PRD and their repo and cite the source, mark exactly one `(Recommended)` with the reason —
then adopt it and record it. Where a recommendation would be dishonest, say *that* rather than
inventing confidence, and record the coin-flip as a coin-flip with what would break the tie.

**Propose defaults; do not interrogate.** Protected paths, poll interval, concurrency, stop button,
PR cap, model routing, holdout location all have working defaults in `config.sh`. *"Protecting these
five paths plus the CI config"* beats *"which files must the agent never touch?"*, which cannot be
answered by someone who has never built one of these.

**The PRD has already answered part of this.** Never re-ask what it answers. Read the scope and
non-goals back as a proposal and spend the time on what it left open.

Round 1, three questions that decide the project:

1. **The single most useful thing someone does with this, first click to the thing they end up
   looking at.** That sequence becomes the main path checked on every change. Undescribable →
   nothing can check it.
2. **How a feature gets built with AI here today.** Take what is there and read `CLAUDE.md`,
   `AGENTS.md`, `.claude/`, `.cursor/` for the rest. The workflows should be recognisably that
   process with the approvals taken out.
3. **Whether code may reach users with nobody reading it first.** Then the dial. **Default 3.**

### The autonomy dial

| Level | Automatic | Still human |
|---|---|---|
| 0 | workflows exist | run them by hand |
| 1 | labelled issue → PR opens | review and merge everything |
| 2 | + validator runs and posts a verdict | merge everything |
| 3 | + validator **auto-merges** when every structural gate is green | write the issues, cut releases |
| 4 | + triages its own issues; a scheduled test files its own bugs | write the important issues |
| 5 | + writes its own issues from the mission | nothing |

**Level 3 is the default. Build for it.** First level where code merges without a human reading it,
and the whole point: a factory that stops at 2 is a code generator with a queue and the person is
still the bottleneck. Everything difficult here exists to earn 3.

0–2 are stages on the way, not destinations. Ship in order, prove a lap at each, keep going. The
dial is enforced in `orchestrator.sh`, and `factory_doctor` blocks 3 outright until a holdout
exists — so "build for 3" cannot become "switch on 3" before the evidence.

Stop below 3 only for a specific recorded reason: an unmovable review requirement, an unabsorbable
blast radius, a harness not yet trusted. Above 3 is a different question, not a further step: 4
hands over what gets built, 5 hands over what to build.

## Phase 2 — the guidance layer (component 4)

Read `references/guidance-layer.md`. Three files from `templates/`:

- `MISSION.md` — what is being built, and what is **out of scope forever**
- `FACTORY_RULES.md` — how the agent behaves unsupervised, and the protected list
- `CLAUDE.md` / `AGENTS.md` — the conventions any project has, factory or not

**`MISSION.md` is a compression of the PRD, not a new document.** Draft from the PRD directly. Its
non-goals become the out-of-scope list almost verbatim; anything the interview added is marked as
such, so later it is obvious which constraints came from the product and which from making it
unattended.

If a conventions file exists, **keep it and pull the factory-only rules out** rather than writing a
new one over the top. Usually the single most useful edit this phase makes.

Placement test, per rule:

> Would you write this with a human doing the work? → conventions file.
> Does it exist only because nobody is watching? → `FACTORY_RULES.md`.
> Is it about what the product is and is not? → `MISSION.md`.

**The one property that matters: the agent cannot amend the rules it is judged by.** All three on
the protected list; a PR touching them is auto-rejected before anything else is evaluated. In this
repository that is Layer 1H of `odin-safety-guard.sh` as well as `factory/guard.py` — enforced in
code twice, because the version a node calls is the version a node can skip.

Run `python3 scripts/factory_doctor.py --repo <path>` now. It fails loudly, which is correct — it is
a checklist and this is the start of working through it.

## Phase 3 — the validation harness (component 5)

Read `references/validation-harness.md` in full before writing anything. Longest reference because
this is where factories fail. **Its opening section is the contract the runner expects** — the
entrypoint, the markers, the append rule, the `--quick` subset. Getting the append rule wrong breaks
every marker assertion for a reason that looks like your code.

**Start from the scaffold, then delete its assertions.**

```sh
cp -r templates/harness <repo>/harness
```

`templates/harness/` is the plumbing and only the plumbing. Not Python-only, not web-only: every
command lives in `harness.config.json`, driver is `http`, `cli` or `library`. Proven on a Python
HTTP service, a Node CLI (five config values changed) and a Python library.

**Every assertion in `e2e.py` is a worked example and all of it should be deleted.** Same for
`.factory/holdout/run.py` and `harness/mutations/defects.json`. Each carries a marker line to delete
when the content becomes yours, and `factory_doctor` **blocks at level 2+** until you do — a gate
that is green about the template's sample product is worse than no gate.

The interview produces all three: **R1.1** the journey, **R2.5a** the composed scenarios the builder
cannot read, **R2.5b** the defects that must be caught.

Short version, not a substitute for reading it:

- **Climb the ladder:** static → unit → integration → **E2E as the real user** → visual judging →
  holdout scenarios → deterministic gate.
- **Draw the independence line after integration.** Everything below it is inside the agent's
  optimization loop; given time it satisfies what was measured rather than what was meant. More
  tests below the line is not the fix.
- **At least two gates must be code the model cannot talk past.** The merge itself, and a positive
  assertion that the app actually started. Elsewhere a "gate" is a prompt instruction, which is a
  suggestion with good manners.
- **Empty is not pass.** Assert how many checks *ran*, not only how many failed. A skipped check
  returns nothing, and nothing is not a failure.
- **The validator never learns how the code was written.** Only what was asked and what the code
  does now.

Deliverable: a `validate` entrypoint a workflow can call, emitting explicit markers, and a merge
gate in bash that greps for them. In this repository `FACTORY_VALIDATE_CMD` points at
`.claude/scripts/ci-local.sh`.

## Phase 4 — the workflow-driven repo (component 1)

Read `references/automation.md` for each agent's headless contract and what is in the runner.

**Copy the runner; do not write one.** `templates/runner/factory/` is a working execution layer —
dispatcher, runner, structural gate, protected-path guard, merge, deploy, state machine, seven node
prompts. Its `README.md` is the install order.

```sh
cp -r templates/runner/factory <repo>/factory
mkdir -p <repo>/.factory/locks <repo>/.factory/holdout <repo>/.factory/runs
```

Then three edits, and the third is the real work:

1. **`factory/config.sh`** — the agent, the models, `FACTORY_VALIDATE_CMD` pointing at Phase 3's
   harness, and `FACTORY_PYTHON` if the host's interpreter is not `python3`. Every project-specific
   value lives here; editing another script to change a path is a bug in `config.sh`.
2. **`factory/guard.py`** — the protected list. Seed it; do not just accept what the interview
   returned.
3. **`factory/prompts/*.md`** — **rewrite as the repo's own process.** Where R1.2's answer lands.
   Plan with one skill and implement with another → two nodes. A rules file or MCP server loaded at
   a particular step today → load it at that step here.

A factory is interesting because it runs unattended, not because it works differently. Someone who
recognises their own workflow in these prompts maintains it; someone learning a new pipeline does
not. **The prompts are the personalisation; the plumbing is not.**

## Phase 5 — deployment (component 3)

Read `references/deployment.md`. Short, and it contains the trap that silently kills more factories
than anything else: **GitHub does not trigger workflows on commits made with the default
`GITHUB_TOKEN`.** The agent commits, the deploy never fires, nothing errors, nothing tells you.

If the loop does not end at real users, what was built is a PR generator.

## Phase 6 — the trigger (component 2)

Only now. Read `references/setup.md` in full and the automation reference's dispatcher section.
`references/setup.md` is the unglamorous half nobody writes down: prerequisites, cron and systemd and
Task Scheduler, the `.gitattributes` line-ending pin, `core.longpaths`, `PYTHONIOENCODING`, the
`git check-ignore` pre-flight, credential expiry, and testing the stop button on purpose. Every item
on it broke a real factory.

**Say this out loud, because almost everyone arrives with the wrong model: nothing pushes.** Filing
an issue does not trigger a run. No webhook, and not meant to be one — a scheduler wakes on a timer,
reads state, dispatches at most one thing. An issue filed at 09:01 waits for the next tick. A push
trigger that breaks fails *silently* and looks exactly like a factory with nothing to do; a poll
that breaks is a poll you can see not running.

**Install it after the first lap, not here.** `install-trigger.sh` refuses below dial 1, and the
dial does not leave 0 until Phase 7 has proven a lap by hand. Build the trigger's configuration now;
run the installer at Phase 7 step 3.

```sh
bash factory/install-trigger.sh --status
bash factory/install-trigger.sh --install
bash factory/install-trigger.sh --remove
```

**The dispatcher must be the dumbest, most deterministic thing in the system.** Not an LLM deciding
what to run — that hallucinates dispatches for work that does not exist. Bash, a fixed priority
order, shared state in something boring.

Fixed priority, load-bearing:

1. fix a PR that needs fixing
2. validate a PR waiting for review
3. implement the highest-priority accepted issue
4. triage untriaged issues

**Finish in-flight work before starting new work.** Backwards, and the factory triages forever while
its own PRs rot.

## Phase 7 — prove it, then reach level 3

**Target is 3. Not finished until the dial is there.** These steps are the evidence that earns it.

1. Run the walking skeleton by hand: one real issue, all the way to a PR merged by a human. Do not
   proceed on a factory that has never completed a lap.
2. `python3 scripts/factory_doctor.py --repo <path> --audit` until clean. It refuses level 3 while
   there is no holdout — the check that decides whether the rest of this was real.
3. `bash .claude/tests/factory.test.sh`, and `python3 scripts/_test_runner.py --repo <path>`. The
   doctor checks the repo is set up correctly; these check the machinery under it still works. Free,
   about two minutes, and a factory that fails them fails *silently* — parking work nobody is told
   about, or re-running a workflow that can only die. Re-run after any hand-edit under `factory/`,
   and before re-arming a factory that has been idle: the runner is copied and never linked, so a
   fix upstream has not reached yours.
4. Raise the dial to 1, then 2, watching a full cycle at each — then **3**. Stopping at 2 leaves a
   person merging every PR, which is the bottleneck the build was for. Stopping below 3 gets written
   into `FACTORY.md` as what would have to be true to go further.
5. Write `FACTORY.md` from the template — what was built, which level it runs at, what has to be true
   before the next notch. **Link the PRD it was built from**: when the product changes the mission
   must change with it, and the factory will keep faithfully building the old scope until someone
   notices.

---

## Operating facts — not a speech

**Do not recite this section.** Each belongs at the single moment it becomes actionable, one line.

- **The PRD is a live document now, not a kickoff artifact.** Nobody compensates for staleness here:
  the factory builds the scope it was given until the scope is edited. Changing what the product is
  means editing `MISSION.md`, in a human commit, on purpose.
- **Instrument tokens on day one**, before the first unattended run — as a measurement you will want
  and cannot reconstruct later. One "fix an issue" run is far more agent sessions than it looks like.
- **One premium model in the planning slot, cheaper everywhere else.** Premium in one of the two
  slots that matter buys most of the quality of premium in both. Premium in zero is what costs you.
- **Leash every editing node to its own diff.** A node that can edit without a file scope grows a
  six-file PR into eleven and introduces a bug on the way through.
- **Run `git check-ignore -v` on every config file before the first workflow that commits.** A
  `git add -A` inside a PR-create step publishes whatever was not ignored, and public means public.
- **The agent is the interchangeable part; the plumbing is not.** Credential expiry, cost cliffs, no
  default session timeout and sandbox egress are the same problems in every agent.

## Resources

- `UPSTREAM.md` — provenance, the four defects this fork repaired, and what a porter reads first.
- `OPERATIONS.md` — arming, reading state, stopping, and what a failed lap looks like.
- `references/interview.md` — three rounds, every question with its recommendation and its
  **discharge**. Read in Phase 1.
- `references/guidance-layer.md` — the three-file split, the placement test, protected files, and
  writing an out-of-scope list that does real work. Phase 2.
- `references/validation-harness.md` — the ladder, the independence line, holdout design, structural
  vs prompted gates, failure modes. Phase 3, before writing any check.
- `references/automation.md` — headless contracts for eight coding agents, orchestrator options,
  dispatcher rules. Phases 4 and 6.
- `references/deployment.md` — deploy strategies, the `GITHUB_TOKEN` trap, GitHub scheduling
  gotchas. Phase 5.
- `references/setup.md` — prerequisites, the platform tax, scheduling, turning it on. Skim in 0b to
  refuse early; read in full in Phase 6.
- `templates/` — `MISSION.md`, `FACTORY_RULES.md`, `FACTORY.md`, `CLAUDE.md`. Copy and fill; never
  ship a template's placeholder text.
- `templates/runner/` — the working execution layer, copied in Phase 4. Its comments record real
  incidents; a factory rebuilt from the design alone rediscovers every one of them, unattended, in
  production.
- `templates/harness/` — the validation harness's *plumbing*, copied in Phase 3. Runs out of the
  box; every assertion in it is an example to delete.
- `workflows/factory-lap.yaml` — one dispatcher tick as an Archon workflow. The observable front
  door; the dispatcher is still the only thing that decides what runs next (ADR-0170). Archon is
  optional for a built factory: without it, the runner still runs from cron.
- `scripts/factory_doctor.py` — deterministic audit of a factory repo: protected files, holdout
  leaks, gate-is-code, empty-is-not-pass, ignored secrets, autonomy level. Phases 2 and 7. Never
  read its source into context; only its output. Exit 2 means it could not look; exit 1 means it
  looked and found problems.
- `scripts/_test_factory_doctor.py` — the doctor's own tests. Builds a healthy factory, breaks one
  thing at a time, requires the doctor to notice.
- `scripts/_test_runner.py` — the runner's behaviour suite. Builds a real git repo with the real
  `factory/` in it, stubs the agent and the validator so a lap is free and deterministic, then
  drives the actual shell scripts. Every test named after the defect it locks.
  `--repo <path>` runs it against a factory somebody BUILT — the one to remember, because the runner
  is copied and never linked. `--mutate` restores each historical defect and requires the suite to
  go RED; a test whose defect can be put back while everything stays green is decoration.
- `scripts/_audit_runner.py` — the structural invariants no behaviour test can express: a knob read
  by a child process that `config.sh` never exported, a prompt placeholder the renderer does not
  substitute, a state nothing dispatches on, an unguarded command that dies before the escalate on
  the next line. Where `factory_doctor` audits YOUR repo, this audits the MACHINERY.
