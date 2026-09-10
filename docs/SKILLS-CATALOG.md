# Odin Skills Catalog

A complete, per-skill reference for every skill **Odin owns or has forked**.

---

## About this document

### What it is for

This is the operator-facing description of the Odin skill corpus. It exists so that four questions
can be answered without opening code first:

1. **What is this skill, and what problem does it address?**
2. **What executable surface does it carry** — scripts, hooks, and the gates that can refuse it?
3. **What else breaks if it changes** — which skills does it hand off to, gate, or depend on?
4. **What does an operator need to know at 3am** — limitations, known debt, security posture,
   ownership.

It is written for engineers onboarding to the corpus, operators debugging a session that stopped
somewhere unexpected, and anyone doing impact analysis before changing or removing a skill.

### How to navigate it

One `## Skill:` section per skill, **alphabetical by identifier**, each with the same eight
subsections in the same order. Use the [index](#index) to jump; the identifier in the index is the
anchor slug and is also the string you pass to the `Skill` tool.

Within an entry, the enumerable sections — Scripts, Hooks, Gates, Integrations — are **derived from
the repository**, not recalled. The prose sections vary in length with what the skill's own body
says; a short Description means a small skill, not an unexamined one.

### Membership — what is in scope, and the command that decides it

Odin's harness carries **123 skills** on disk under `.claude/skills/`. Most are *vendored*:
third-party bodies carried unmodified, which `vendor-skills.sh --refresh` may overwrite at will.
Those are not Odin's, and they are not catalogued here.

The subject set of this document is the set Odin **owns or has forked**, and that set is
decidable — it is not a list anybody maintains by hand. The rule is
[`odin-skills:ADR-0003`](adr/0003-mirror-membership-rule.md): a skill belongs to Odin when it was
**authored here**, or **forked from upstream and substantially modified here**, and membership is
materialised as the directory listing of this repository's `skills/`.

Derive it, rather than trusting the numbers below:

```sh
# from the Odin harness root
ls -1 projects/Odin-Skills/skills                                        # the member set
bash projects/Odin-Skills/scripts/sync-from-odin.sh --check --odin "$PWD" # the mirror is faithful
bash .claude/scripts/skill-provenance-check.sh                            # every skill has a class
```

Measured at the sha this document was written against:

```
$ ls -1 projects/Odin-Skills/skills | wc -l
39

$ bash projects/Odin-Skills/scripts/sync-from-odin.sh --check --odin "$PWD"
OK: 39 skills in sync with <harness root>/.claude/skills

$ bash .claude/scripts/skill-provenance-check.sh
skill-provenance-check: OK — 123 skills, every one classified
```

**39 skills: 28 `authored`, 11 `forked`, 0 `undetermined`.** A count stated in this document is a
count that was measured; if a re-run disagrees with it, the disagreement is the finding and this
document is the stale party.

### Provenance classes

The class is not decorative. It decides **what a refresh may destroy**, and it is derived on every
run by `.claude/scripts/lib/skill-provenance.sh` from four inputs: the vend map, the `FROZEN` list,
the presence of an `UPSTREAM.md`, and mirror membership.

| Class | Means | May a refresh overwrite it | In this catalog |
|---|---|---|---|
| `authored` | written for Odin; no upstream exists | no | **yes** — 28 |
| `forked` | third-party, substantially modified here | no | **yes** — 11 |
| `vendored` | third-party, carried unmodified | **yes** — that is the point | no |
| `frozen` | vendored, but upstream is gone or unusable | no | no members at this sha |
| `undetermined` | nothing claims it and nothing declares it | refuses to answer | none at this sha |

`undetermined` is not folded into `authored`: a skill installed by a provisioner looks identical on
disk to one written here, and guessing either way protects or exposes the wrong thing. While any
skill is undetermined, `sp_protected_set` refuses to produce a protect list at all — a partial
protect list is the exact shape that overwrites the one skill nobody could classify.

**Fork evidence outranks the vend map.** A forked skill is usually still listed in the map;
`rules-distill` is vended from ECC *and* forked here.

### Where a fork's `UPSTREAM.md` lives — and why it matters that it is here

Nine of the eleven forks carry their `UPSTREAM.md` **only in this mirror repository**, not in the
harness's own `.claude/skills/<name>/`. That is deliberate and load-bearing: refresh protection is
*derived* from the mirror directory, so **deleting a skill's directory here re-exposes the fork to
`vendor-skills.sh --refresh`** and the next refresh silently reverts every local change. The two
exceptions — `factory` and `rules-distill` — carry the file in both places.

Each fork entry below names its upstream, the licence artefact that accompanies it, and the sha its
divergence was last audited against. Publishing a fork is a licensing act, not a copy:
`scripts/validate-skills.sh` check 6 refuses a fork that ships without a licence artefact.

### Status, and how deprecation is marked

**Status** in each entry's header is one of `active`, `deprecated`, or `experimental`.

No skill in the corpus declares a status in its frontmatter — the frontmatter keys in use across
the 39 are `name`, `description`, and optionally `origin`, `metadata`, `license`, `version`,
`allowed-tools`, `argument-hint`, `user-invocable`, `artifact*`, `forks`, `upstream`,
`requires_binary`, `engine`, `hidden`, `arguments`. Status is therefore **derived**, and this
document states the derivation rather than an opinion:

- `active` — the skill is a mirror member, is reachable from the routing surface
  (`CLAUDE.md`'s auto-use map, `.claude/docs/SKILL-ROUTING.md`, or the `odin-skill-gate` hook), and
  carries no deprecation notice in its body.
- `deprecated` — the body, an ADR, or `CHANGELOG.md` says so. **A deprecated skill still present in
  the tree is listed here and marked, never omitted.** At the sha this was written, no member is
  deprecated; the status column is not vestigial, it is currently uniform.
- `experimental` — declared as such in the body or by the ADR that introduced it.

A single deprecated *alias* exists inside an active skill (`impeccable`'s `teach` alias for `init`)
and is recorded in that skill's entry, not as a skill of its own.

### The Gates section — read this before you go looking for a feature-flag console

**Odin has no feature-flag system.** There is no flag service, no percentage rollout, no user
segmentation, and no flag console. A catalog that filled the requested "Gates" table with invented
flag names would be confidently wrong, and a catalog that answered "no gates" for all 39 would hide
the machinery that actually decides whether a skill's work is allowed to proceed.

What this repository has instead is **three kinds of conditional control**, and the Gates table in
each entry is filled with those, with the template's columns remapped honestly:

| Kind | What it is | "Default State" means | "Evaluation Logic" means |
|---|---|---|---|
| **CI gate** | a checker script under `.claude/scripts/` or a matrix under `.claude/tests/`, stepped by `.claude/scripts/ci-local.sh` and, for the fastest of them, by `.claude/scripts/pre-push` | always on; the question is *where* it runs — `pre-push`, `ci-local.sh`, or by hand | the predicate the script asserts, and its exit code |
| **Posture gate** | a hook whose severity depends on session posture: **warn** interactive, **block** unattended | the interactive default (`warn`), flipped by arming posture | `.claude/scripts/odin-autonomous.sh on` publishes a per-session ticket (ADR-0051); the hook reads it |
| **Env override** | an `ODIN_*` environment variable that forces a gate's severity or skips it | unset — the gate's own default applies | string comparison in the hook, documented at its use site |

CI runs **locally** (`bash .claude/scripts/ci-local.sh`); no workflow in the harness carries an
automatic trigger, and triggering one remotely is blocked always-on (ADR-0117). A gate's cost
matters: `PRE_PUSH_GATES` is a declared budget of 30000ms, and `pre-push-set.test.sh` refuses a set
that declares more than it.

**Corpus-wide gates are stated once, here, and not repeated in 39 entries.** Every member is
subject to: `skill-provenance-check.sh` (every skill has a class — also in `PRE_PUSH_GATES`),
`skill-provenance-guard.test.sh`, `mirror_drift` (this mirror matches the harness),
`scripts/validate-skills.sh` (this repository's own gate, including check 6 — a fork must ship a
licence artefact), `skill-routing-check.sh` and `skill-reachability-check.sh` (a skill nothing names
is a skill nothing fires), `skill-invocability-check.sh` (a routed skill must not carry
`disable-model-invocation`), `skill-registry-coverage.sh`, `skill-artifact-check.sh`,
`skill-delegate-check.sh`, `categories-coverage-test.sh`, and `doc-reference-check.sh` over every
path a body cites.

Each entry's Gates table therefore lists the gates **specific to that skill** — the checker it
names as its own enforcement, the posture that changes its behaviour, the env override it reads. A
skill with none of those still gets the prescribed sentence,
`This skill does not use any feature gates.`, and the corpus-wide list above still applies to it.

### The Hooks section — the six real events

Odin registers hooks in `.claude/settings.json` under exactly six events, and **no others**:
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostCompact`, `Stop`. There is no
`pre-deploy`, no `post-merge`, no `on-event`. Where an entry's Hooks table names a type, it is one
of those six.

A skill "has" a hook when a registered hook **names that skill** — routing to it, gating its
surface, or enforcing its record format. Most skills own no hook file of their own; the hook is
harness machinery that points at them. Two hooks reach nearly the whole corpus and are therefore
stated once here rather than repeated 39 times:

- **`odin-skill-gate.sh`** (`UserPromptSubmit`) reads *intent* from the prompt and names the skills
  that should fire. It names **all 39 members** — measured with
  `grep -qwF -- "$name" .claude/hooks/odin-skill-gate.sh` over the derived member list. Every member
  is therefore reachable from intent alone, which is what `skill-reachability-check.sh` and
  `skill-routing-check.sh` hold.
- **`odin-surface-router.sh`** (`PreToolUse` on `Write|Edit|NotebookEdit|Bash`) reads the *surface* —
  the file about to be written — and names skills and rule namespaces with no prompt involved. A
  loop submits one prompt and runs forty turns, so surface routing is the one that reaches turn
  thirty.

Per-entry Hooks tables list the hooks **specific** to that skill, and name `odin-skill-gate` only
where the routing is the notable fact about it.

### The Integrations section — what "integration" means here

Skills do not call each other's APIs; there is no service mesh. An integration in this corpus is one
of four relations, and each row says which:

- **invokes** — the body instructs the agent to fire the other skill as a step.
- **hands off to** — the other skill is this one's terminal successor; the chain is ordered and the
  order is a real constraint.
- **is gated by / gates** — one skill's record or check refuses until the other has done its part.
- **shares a record** — both write or read the same committed ledger (`MISTAKES.md`, `CAVEAT.md`,
  `MUTATIONS.md`, `.claude/docs/decisions/`, `.claude/docs/roadmap/roadmap.json`).

Sources, in precedence order: the "what this owns and must not restate" table most skill bodies
carry; the routing chains in the harness `CLAUDE.md` auto-use map and
`.claude/docs/SKILL-ROUTING.md`; and a name sweep across bodies whose hits are confirmed by reading
the sentence before they are written down. A skill that merely *mentions* another in a red-flags
table is not integrated with it and gets no row.

### Conventions

- Paths are relative to the **Odin harness root** unless they begin `skills/` or `docs/`, in which
  case they are relative to this mirror repository.
- `harness:RM-####` is a roadmap item id in the harness's `roadmap.json`; `ADR-####` is a harness
  architecture decision under `.claude/docs/adr/`; `odin-skills:ADR-000#` is one of this
  repository's own; `DEC-####` is a numbered decision in `.claude/docs/decisions/`.
- An empty section is written with its prescribed sentence, never dropped. **An omitted section is
  indistinguishable from an unexamined one**, which is the failure this document exists to prevent.
- Where something could not be established from the files, the entry says so in one line. An
  `undetermined` is a finding; a plausible invention is the failure mode.

### Ownership

The whole corpus is owned by the Odin harness maintainer; there is no per-skill team. Skill
lifecycle — classification, mirror membership, packaging, freshness, refresh, publication — is owned
by the `odin-skill-manager` skill and the rule half at `.claude/rules/skills/lifecycle.md`. Writing
a skill's body is `skill-creator` and `writing-skills`; whether a body's own instructions are being
followed is `skill-comply`. Per-entry "Ownership" lines name the *skill* that owns the surface, not
a person.

---

## Index

39 skills. `A` = authored by Odin, `F` = forked from upstream and maintained here.

| Skill | Class | In one line |
|---|---|---|
| [agent-browser](#skill-agent-browser) | F | Browser automation for an agent — navigate, fill, click, screenshot, extract; an offline stub here |
| [automate](#skill-automate) | A | Whether a repeated action is worth automating, at which level, and what rolls it back |
| [blueprint](#skill-blueprint) | F | Decompose an objective too big for one plan into cold-start-executable construction steps |
| [campaign](#skill-campaign) | A | Plan a multi-session campaign's waves, track what landed, close it out on evidence |
| [caveat](#skill-caveat) | A | Record a hazard with the condition under which it recurs, and land the safeguard |
| [consistency](#skill-consistency) | A | Name the incumbent implementation before writing a second one |
| [decision-mapping](#skill-decision-mapping) | F | Chart a committed decision map for a space whose route is not yet visible |
| [decision-matrix](#skill-decision-matrix) | A | Score options against weighted criteria and record a numbered DEC |
| [endless](#skill-endless) | A | Continue past the item in hand — checkpoints and the three continuations |
| [factory](#skill-factory) | F | Build a repository that ships its own code unattended |
| [gauntlet](#skill-gauntlet) | A | Drive every issue and roadmap item to done across many sessions, re-arming rather than ending |
| [grill-with-docs](#skill-grill-with-docs) | F | Stress-test a plan against actual documentation rather than opinion |
| [handoff](#skill-handoff) | F | Write the handoff, launch the successor session, then monitor it |
| [impeccable](#skill-impeccable) | F | Design, critique and polish a frontend interface; also a PostToolUse design check |
| [improve](#skill-improve) | A | Change a skill on a declared reason, reversibly, reverting on a red gate |
| [learn](#skill-learn) | A | The capture bar for durable knowledge, five confidence rungs, a re-verification command |
| [leek](#skill-leek) | A | Diagnose context, token, memory, cache and session leaks; files issues, never cleans up |
| [mistake-to-gate](#skill-mistake-to-gate) | A | Turn a mistake into an always-on mechanical gate with a matrix that proves it fires |
| [mutations](#skill-mutations) | A | Record a behaviour-altering change with its expected impact written before the observation |
| [not-impressed](#skill-not-impressed) | A | Review machine-generated code with a hostile prior; one verdict — trim |
| [odin-skill-manager](#skill-odin-skill-manager) | A | Classification, mirror membership, packaging, freshness, refresh, publication |
| [off-topic](#skill-off-topic) | A | Checkpoint work displaced mid-run, and the condition that resumes it |
| [oops](#skill-oops) | A | Root-cause something that should not have happened and build a mechanical guard |
| [out-of-scope](#skill-out-of-scope) | A | Fix it now or file it — six weighted dimensions and an auditable deferral |
| [projects](#skill-projects) | A | The project subtree routing table, switch ritual and artifact checklist |
| [revive](#skill-revive) | A | Bring a stopped fleet back unattended from a committed manifest |
| [roadmap](#skill-roadmap) | A | What to work on next; the living inventory and dependency graph |
| [rules-distill](#skill-rules-distill) | F | Distill recurring skill patterns and mistake-log keys into rule files |
| [s2s](#skill-s2s) | A | What one session says to another, and what it leaves in a terminal nobody reads |
| [status](#skill-status) | A | The four human-facing fleet controls: report, quiesce, timed resume, stop-for-handoff |
| [successor](#skill-successor) | A | Delegate work to sessions other than this one; coordinate a fleet |
| [successor-manager](#skill-successor-manager) | A | Who owns a delegated session, and is it stalled or dead |
| [superplan](#skill-superplan) | A | Multi-agent deep planning: planner + architect + adversary, synthesized into a plan doc |
| [test-driven-development](#skill-test-driven-development) | F | RED before GREEN, before any implementation code |
| [tidy](#skill-tidy) | A | A verdict per path on whether something that outlived its purpose may go |
| [using-superpowers](#skill-using-superpowers) | F | The skill-first discipline itself; injected at session start |
| [verification-before-completion](#skill-verification-before-completion) | F | Evidence before assertions — run the command before claiming it passes |
| [work-loop](#skill-work-loop) | A | The bounded work cycle contract, six iteration outcomes, a resumable ledger |
| [workflows](#skill-workflows) | A | Define, version, supersede and retire a reusable workflow chain |

---

## Skill: agent-browser

**Identifier:** `agent-browser`
**Repository:** `.claude/skills/agent-browser/` (harness) · `skills/agent-browser/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `vercel-labs/agent-browser`, Apache-2.0, upstream HEAD last audited `548b159` (2026-08-10)

---

### Description

Browser automation for an agent: navigate pages, fill forms, click, screenshot, extract data, drive
Electron desktop applications, and run exploratory QA. It is a CLI-backed capability — Chrome or
Chromium over CDP with accessibility-tree snapshots and compact `@eN` element references — not a
Playwright or Puppeteer wrapper.

**Forked from `vercel-labs/agent-browser` and reduced to an offline discovery stub.** That reduction
is the entire local change and it is deliberate: upstream authors the real workflow content to be
*served by the CLI itself*, so a vendored snapshot would go stale against whichever CLI version is
actually installed on the host. The stub keeps upstream's triggering `description` — the string that
decides whether the skill fires at all — and delegates every instruction to
`agent-browser skills get core` at invocation time. The result resolves with no network access and
can never contradict the installed tool.

The Apache-2.0 §4(b) modification statement lives in the mirror's
`skills/agent-browser/UPSTREAM.md`, beside the `LICENSE`.

### Purpose and Use Cases

Fired on any request to interact with a website programmatically: "open a site", "fill out this
form", "take a screenshot", "scrape this page", "test this web app", "log in", plus exploratory
testing, dogfooding and bug hunts. Specialised content is loaded on demand for Electron apps
(VS Code, Slack, Discord, Figma), Slack workspace automation, Vercel Sandbox microVMs, and AWS
Bedrock AgentCore cloud browsers.

**Constraints and assumptions, all of them operationally significant:**

- **`requires_binary: agent-browser`.** Without the CLI on `PATH` the stub resolves and then has
  nothing to delegate to. It fails as *silence*, not as an error — the most common live failure of
  this skill.
- Installation is attempted at session start by `.claude/scripts/setup.sh`, which logs
  `WARN: agent-browser install failed/blocked — its MCP tools will be unavailable this session` when
  `npm install -g agent-browser` is blocked or offline. **A session that logged that warning cannot
  use this skill**, and the MCP `agent_browser_*` tools will be absent.
- `hidden: true` in frontmatter; `allowed-tools` restricts it to `Bash(agent-browser:*)` and
  `Bash(npx agent-browser:*)`.
- The observability dashboard runs on port 4848, independent of browser sessions; agents stay on the
  dashboard origin because session traffic is proxied internally.

### Scripts

This skill does not define any scripts.

Its executable surface is the external `agent-browser` CLI, not files in this repository. The
harness script that provisions that CLI is `.claude/scripts/setup.sh` (§1), which is harness
machinery rather than a script the skill owns; it runs at `SessionStart` and needs network access
plus a working global `npm` prefix.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `setup.sh` §1 | `SessionStart` | every session start | Installs the CLI globally (120s timeout), then `agent-browser install` for Chrome (180s). Logs a `WARN` and continues on failure — never fails the session | `npm`, network, a writable global npm prefix |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches browser-automation intent | Names this skill in the routing hint | none |

### Gates

This skill does not use any feature gates.

Its only conditional behaviour is binary presence, which is not a gate: the CLI is either installed
or the skill is inert. The corpus-wide provenance and licence gates listed in the overview apply,
and its Apache-2.0 licence artefact is what `scripts/validate-skills.sh` check 6 asserts.

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `e2e-testing` | alternative | Both drive a browser; `e2e-testing` owns Playwright/Cypress suites, this owns interactive and exploratory driving | Not a dependency. Prefer this for one-off interaction, that for a committed suite |
| `impeccable` | invoked by | `impeccable`'s live browser iteration drives a real page while critiquing it | `impeccable` degrades to static critique when the CLI is absent |

The skill body instructs the agent to prefer `agent-browser` over any built-in browser automation or
web tool.

### Additional Relevant Information

- **Ownership:** the skill body is upstream's, held as a fork by `odin-skill-manager`; the install
  path is owned by `.claude/scripts/setup.sh`.
- **Related documentation:** `skills/agent-browser/UPSTREAM.md` (this mirror) — the §4(b) statement,
  the divergence, and the requirement; `FORKS.md` at the harness root.
- **Known limitations / technical debt:**
  - The stub carries **no usage content of its own**. A reader who does not run
    `agent-browser skills get core` learns nothing about how to drive the tool.
  - The one measured divergence from upstream (2026-08-15 audit) is the frontmatter `description`,
    tracked deliberately close to upstream because that string decides triggering.
  - MCP tool availability and skill availability are separate failures with the same symptom;
    `.claude/tests/mcp-target-table.test.sh` covers the MCP half.
- **Observability:** `setup.sh` log lines are the signal — `agent-browser already installed.`,
  `agent-browser installed.`, `agent-browser Chrome ready.`, or the `WARN`. The CLI's own dashboard
  is on port 4848.
- **Security / compliance:** the skill drives a real browser with real credentials; the CLI carries
  an authentication vault and persists session state. Treat any host running it as holding live
  session cookies. Apache-2.0 obligations are discharged by the `LICENSE` and `NOTICE` beside the
  skill in this mirror.
- **Versioning:** deliberately unversioned here — the stub delegates to whatever CLI version is
  installed, which is the point of the fork.

---

## Skill: automate

**Identifier:** `automate`
**Repository:** `.claude/skills/automate/` (harness) · `skills/automate/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Decides **whether** a repeated action should be automated, **at which of six levels** it may run,
and **whether an automation that already exists is still worth keeping**. Three questions in a fixed
order, and the first one is the one that gets skipped: *was the result already derivable from what
the session held?* If it was, the fix is to stop making the call, not to make it faster — automating
a redundant call makes the waste reliable.

The problem domain is agent self-modification. An agent that scripts everything it does twice
accumulates artifacts nobody approved, at reaches nobody agreed to, with no way to withdraw them.
This skill supplies the approval boundary and the mandatory rollback.

### Purpose and Use Cases

Fires on: doing something a third time; a call whose result was probably already known; being about
to write a script or wire a hook; and — the underused direction — an existing automation nobody can
justify keeping.

**Six verdicts, exactly one of which applies:** `eliminate` (the result was derivable — repair
retention instead), `keep-manual` (too rare or too variable to be worth an artifact), `assist`
(automate the evidence, never the conclusion), `automate` (mechanical end to end), `gate` (a
preventable failure a repository-state predicate detects — hand to `mistake-to-gate`), `retire` (an
existing automation's recorded retirement predicate has fired).

A candidate with no verdict is **not "pending"** — it is `keep-manual` until someone argues
otherwise.

**Six levels, ordered by reach**, each naming its approval boundary and a non-optional rollback:
`ad-hoc` (one command; the inverse must be named *before* the command runs), `scratch` (an
uncommitted script; teardown is the safety property), `committed` (`.claude/scripts/`, run by hand;
rollback is `git revert`), `routed` (a step in a skill or chain; rollback removes the step and bumps
the chain manifest), `gated` (in the suite's gate list — it can now fail the suite for everyone;
requires a matrix proving it fires *and* fails), `unattended` (runs with no human in the turn, via
the local nightly wrapper, against a written allowlist).

**Hooks, `settings.json`, and rule files are explicitly off the ladder, not at the top of it.** A
hook that fails to parse denies every subsequent tool call to the session that wrote it, which then
cannot repair itself — that has happened in this repository. `settings.json` decides whether the
guards run at all. A rule file with no `paths:` frontmatter costs context on every turn of every
session, forever. An automation needing one of these **proposes** it as a separate, deliberate
change from a fresh session, with the syntax validated before the write lands.

### Scripts

This skill does not define any scripts.

It is a decision procedure whose output is a record, not an artifact. The scripts it discusses are
the ones a *caller* is about to write.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches a repeated-action or script-authoring intent | Names this skill in the routing hint | none |

The skill's own frontmatter carries `artifact: .claude/scripts/*.sh .claude/hooks/*.sh` and
`artifact_pattern: ^#\s*record:` — a declaration that a script or hook this skill authorises carries
a `# record:` pointer line to the plan holding its automation record. That declaration is what
`skill-artifact-check.sh` asserts. The gate exists because of `harness:RM-0357`, measured
2026-09-01: four skills mandated an artifact and **three had zero instances anywhere in the tree**,
`automate`'s `# record:` line among them. `.claude/scripts/skill-artifact-check.sh` itself now
carries one.

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `skill-artifact-check.sh` | that this skill's mandated artifact exists **at least once in the tree**, rather than being a mandate nobody has read | always on | `ci-local.sh` step *Skill artifact (tree)*, plus the `skill-artifact.test.sh` matrix | at least one file under the declared `artifact` globs must contain `artifact_pattern` (a **Python** regex, `re.MULTILINE`). Alternative: `artifact_status: never-run` with a required non-empty `artifact_status_reason`, printed on every green run so an exemption stays a standing question. A floor against zero, not a coverage measure |
| the `gated` level's own bar | whether a proposed automation may enter the suite's gate list | refused without a matrix | delegated to `mistake-to-gate` §1–§9 | a matrix must prove the gate fires **and** fails; `pre-push-set.test.sh` separately refuses a `PRE_PUSH_GATES` set declaring more than its 30000ms budget |
| the `unattended` level's allowlist | what an unattended automation may touch | nothing, until the repository owner writes an allowlist | one explicit approval, recorded | the automation record's `touches` field; never hooks, settings or rule files |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | hands off to | The `gate` verdict is a handoff, not a decision this skill completes | A gateable predicate is never an automation decision. Ordering: verdict here, matrix there |
| `consistency` | is gated by | A verdict of `automate` over a job an existing script already does is a second implementation | Must run **before** any of the six verdicts is reached; this skill never asks the incumbent question itself |
| `workflows` | delegates to | A chain of skills is a workflow, not an automation | This skill decides whether a step should exist; `workflows` owns the chain's lifecycle and version |
| `leek` | complements | `leek` diagnoses waste that already exists; this is consulted before a new artifact exists | Opposite directions on the same axis |
| `skill-creator`, `writing-skills`, `rules-distill` | hands off to | They author the artifact once this skill has said which one, at which level | Ordering: level decided here, artifact written there |
| `work-loop`, `endless`, `roadmap`, `verification-loop` | explicitly excluded | Each owns a neighbouring question the body names and refuses | Cited so the boundary does not blur; no runtime coupling |

### Additional Relevant Information

- **Ownership:** the `automate` skill owns the automation record's ten fields; the gate list it
  routes into is owned by `ci-local.sh` and `pre-push`.
- **Related documentation:** `references/redundant-call-check.md` (the derivability question),
  `references/automation-record.md` (the ten fields, what breaks when each is absent, and a worked
  example). Both live beside the skill.
- **Known limitations / technical debt:**
  - The record lives **in the plan document of the change that introduces the automation**, with a
    pointer line in the artifact's header — deliberately *not* a repository-wide ledger, because an
    append-at-creation list nobody edits at retirement reads exactly like an accurate one. The cost
    is that finding every automation record requires reading plan docs.
  - Nothing mechanically enforces that a `retire` verdict is ever reached; the retirement predicate
    is recorded but nothing schedules the re-read.
- **Observability:** none of its own. The nightly wrapper's output
  (`bash .claude/scripts/local-nightly.sh`) is where an `unattended`-level automation surfaces.
- **Security / compliance:** the level table *is* the access-control model — each level names what
  the automation may touch and who must agree. The refusal to let a session write hooks or
  `settings.json` from inside itself is a security boundary, not a style preference.
- **Versioning:** unversioned; the six verdicts and six levels are the interface.

---

## Skill: blueprint

**Identifier:** `blueprint`
**Repository:** `.claude/skills/blueprint/` (harness) · `skills/blueprint/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `affaan-m/ECC`, originating with `antbotlab/blueprint`; MIT (Copyright (c) 2026 Affaan Mustafa); upstream HEAD last audited `c9de8f5` (2026-08-13)

---

### Description

Takes one objective too big for a single plan and produces a **construction plan**: numbered task
briefs plus a dependency graph, each brief executable by an agent that has read nothing but the
brief itself. The product is not prose — it is dispatchable work, and it is finished when
`plancheck` passes and every task exists as a roadmap child item.

**Forked and substantially rewritten.** Upstream described a slash command Odin does not ship and
made no claim a script could check. The rewrite added: a five-phase pipeline with concrete commands;
`scripts/plancheck.py`, a deterministic gate with 20 tests, that must pass before any step is
dispatched; a mandatory cold-start brief template; a plan-mutation protocol; and phase-5
registration of steps as roadmap children so execution waves stay *computed from the graph* rather
than stored (recorded as DEC-0001 in the harness). The 2026-08-15 audit measured +68 lines present
upstream and −149 present only here; the −149 is this rewrite, not upstream deletion.

### Purpose and Use Cases

Fires when **any** of these holds of a single roadmap item: more than about two days of work; more
than one deployable surface (schema + API + UI); not verifiable until several pieces land together;
`superplan` produced more than about twelve steps (a decomposition failure reported as a step list);
or the work will span sessions or agents.

**Not** for a single-PR change (`superplan`), for deciding *what* to build (`roadmap`), for choosing
between options (`decision-matrix`), or for a fork-analysis planning document.

The body draws a distinction an operator needs: Odin writes **two** artifacts called "plan". A
**decision plan** (`.claude/docs/plans/*.md`, written by `writing-plans` after grilling) carries
forks, alternatives and recommendations, and is gated by the plan-depth rubric (ADR-0027). A
**construction plan** (this skill) carries Task N briefs with Files / steps / verification / exit
criteria, and is gated by `plancheck` *and* the rubric. **Running `plancheck` against a decision
plan reports missing `Files:` blocks that a decision plan has no reason to carry** — that is the
tool pointed at the wrong artifact, not a defect in either.

Assumption worth stating: blueprinting an item with thin acceptance criteria produces briefs full of
guesses. `roadmap` Gate 1 owns that predicate, and the body says to stop and grill instead.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `plancheck` | `.claude/skills/blueprint/scripts/plancheck.py` | The construction-plan gate. Reports `no-goal`, `no-tasks`, `no-files`, `no-verification`, `no-exit-criteria`, `placeholder`, `forward-dependency`, `unknown-task` | Phase 4 of the pipeline, invoked by the skill body; also stepped in `ci-local.sh` as *Blueprint plancheck tests* (`py_tests blueprint`) | `python3 -m scripts.plancheck <path-to-plan.md>`, run from `.claude/skills/blueprint/`. `--json` for machine use. Exit 0 clean, 1 findings, 2 unreadable |
| `__init__.py` | `.claude/skills/blueprint/scripts/__init__.py` | Package marker so `python3 -m scripts.plancheck` resolves | import time | none |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-plan-gate.sh` | `PreToolUse` on `Write\|Edit\|NotebookEdit\|Bash` | a write is attempted | Searches the plan directories for an active plan; **warns** interactive, **blocks** unattended. Names `blueprint` as one of the skills that satisfies it | the plan directories it searches; `ODIN_PLAN_ENFORCE`; the posture ticket |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches multi-PR / too-big-for-one-plan intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `plancheck` | whether a construction plan may be dispatched | always on for construction plans; **not advisory** — fix findings and re-run until clean | invoked by the skill at phase 4; the engine's own tests are a `ci-local.sh` step | eight named finding codes over the plan's markdown; exit 0/1/2 |
| `odin-plan-gate.sh` | whether any write may proceed without a plan | **warn** interactive, **block** unattended | posture armed per session by `.claude/scripts/odin-autonomous.sh on` (ADR-0051) | plan, ADR and memory files are exempt; `ODIN_PLAN_ENFORCE` overrides the posture default |
| the plan-depth rubric | whether the plan is deep enough | always on; planner sends back below 4/5 | `.claude/docs/plan-depth-standard.md` | three preconditions: a named process skill, ≥3 genuine decision forks, a recorded scope decision |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `roadmap` | invokes, and is gated by | Phase 5 registers each task as a roadmap child (`roadmap add --parent`), and Gate 1 refuses an item with thin acceptance criteria | **Ordering is mandatory.** A construction plan not on the roadmap is invisible to `next` and will be re-planned by the next session. Dependencies are set as roadmap edges; the roadmap computes waves, so the plan never stores one (DEC-0001) |
| `superplan` | complements | `superplan` handles single-PR work; more than ~12 steps out of it is the trigger to come here | Not a call. The step count is the boundary |
| `subagent-driven-development`, `executing-plans` | hands off to | Blueprint plans, it does not execute | Terminal successors. The executing agent gets **one brief, verbatim**; a question the brief should have answered is a phase-3 defect to fix in the plan, not to answer in chat |
| `planner`, `architect` (agents, not skills) | dispatches | Phase 4's judgment half — "pick the task you would most likely fail to execute with only this brief" | Agents, dispatched after `plancheck` is clean |
| `grilling` | invokes | Sharpening an objective whose acceptance criteria are thin, before decomposing | Ordering: grill first, blueprint second |
| `decision-matrix` | explicitly excluded | Choosing between options is not decomposition | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** `odin-skill-manager` holds the fork; the roadmap edges it writes are owned by the
  `roadmap` engine.
- **Related documentation:** `references/step-brief.md` — the mandatory cold-start brief template,
  read before drafting; `skills/blueprint/UPSTREAM.md` in this mirror; harness DEC-0001 (waves are
  computed, never stored); ADR-0027 and `.claude/docs/plan-depth-standard.md`; ADR-0039 for the
  `roadmap` → `blueprint` → `superplan` chain.
- **Known limitations / technical debt:**
  - `plancheck` checks *shape*, not sense. A brief can be complete by every one of its eight codes
    and still be unexecutable; that is why phase 4 has a judgment half.
  - **Task numbers are identity, not order.** Never renumber — numbers are referenced by roadmap
    children, briefs and commit messages. Mutations append (`Task 7a/7b`) or insert at the highest
    number and add the edge.
  - The mutation protocol is prose; nothing mechanically detects a silently edited live plan.
- **Observability:** `plancheck --json`; the roadmap's own `waves --limit 3` for the layering.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror. No credential or data handling.
- **Versioning:** unversioned. Upstream divergence is tracked by sha in `UPSTREAM.md`, and a refresh
  means re-reading upstream for anything worth adopting, **not** restoring upstream's text.

---

## Skill: campaign

**Identifier:** `campaign`
**Repository:** `.claude/skills/campaign/` (harness) · `skills/campaign/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Owns two things about a unit of work larger than one session: **what a campaign contains and in what
order**, and **whether it may be declared finished.** A campaign is an objective, a set of roadmap
items, waves of delegated workers, and a close-out.

The design stance is one sentence: **the manifest stores the plan and never a status.** Waves,
per-worker scope, reserved identifiers and the objective are decisions someone made, and a file is
the right place for them. A status is a claim that was true when someone wrote it and goes stale
*silently* — the file reads identically whether it is current or six hours old. Measured cost in
this repository: in one backlog burn-down, **31 of 43** issues examined were already fixed on `main`
while the tracker still said otherwise. Status is therefore computed at read time, every time, and
`validate` **refuses** a manifest that carries one (ADR-0113).

### Purpose and Use Cases

Fires when several delegated sessions are one piece of work: planning the waves and per-worker
scope, tracking what has actually landed, or closing out. Also when a campaign *looks* finished and
that claim needs checking.

The record is one committed JSON manifest per campaign at
`.claude/docs/campaigns/<slug>.json`, holding `campaign`, `objective`, `base`, `remote`,
`close_out`, and `waves[].workers[]` with `worker`, `branch`, `item` (a qualified roadmap id),
`scope` globs and `reserved` identifiers.

**Status is computed from three channels, in this order**, and the order matters because the later
channels cannot report their own absence:

1. **Can the remote be consulted at all** — `git ls-remote --heads <remote> <branch>`. A roadmap
   read from a stale checkout and a landedness computed against an unfetched base both answer
   confidently and wrongly.
2. **The roadmap item** — `done` with a landed sha, or not.
3. **Landedness by content** — `bl_classify` from `.claude/scripts/lib/branch-landedness.sh`.
   **Never `git merge-base --is-ancestor`**: this repository lands by rebase merge, which rewrites
   every sha, and ancestry answered "not merged" for **56 of 110** branches that had in fact landed
   (ADR-0093).

A row is `landed`, `open`, or `undetermined`. A disagreement between roadmap and content is never
resolved in favour of either side — it is a finding for a human, not a tie to break.

**`close` has teeth.** It refuses while any item lacks a `done` status with a landed sha, and names
each blocker. **Undetermined outranks a named blocker**: a run that names three blockers *and*
failed to reach the remote has an incomplete blocker list, so it exits 2, not 1. On a clean close
the residue — worker branches, worktrees — is printed *for `tidy`*; this skill removes nothing.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `campaign` | `.claude/skills/campaign/scripts/campaign.py` | The engine. `validate` (manifest well-formed, and carries no status), `status` (compute from three channels), `close` (compute, print, refuse) | Invoked by the skill body from `.claude/skills/campaign/`; the engine's tests are the `ci-local.sh` step *Campaign engine tests* (`py_tests campaign`) | `python3 -m scripts.campaign <sub> --root <repo> --manifest <file>`, `--json`. **Nothing is written by any subcommand** |
| `__init__.py` | `.claude/skills/campaign/scripts/__init__.py` | Package marker | import time | none |

Exit codes are the interface, so a caller greps nothing: `0` validated/computed/**closeable**, `1`
refused (malformed, or a named item is not done), `2` **undetermined** (a channel could not be
read), `64` usage.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-completion-evidence.sh` | `Stop` | a turn ends claiming completion | Requires evidence behind a completion claim; names `campaign` among the skills whose records count | the campaign manifest, the roadmap |
| `odin-safety-guard.sh` | `PreToolUse` on `Bash\|Edit\|Write\|NotebookEdit` | a destructive or ambiguous command | Blocks always-on; names `campaign` in its guidance for campaign-owned paths | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches multi-session / wave / close-out intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `campaign-manifest-check.test.sh` | that a committed manifest is well-formed and carries no status field | always on | `ci-local.sh` step *Campaign manifest check matrix* | schema validation plus the no-status refusal (ADR-0113) |
| `campaign close` | whether a campaign may be declared finished | always on; refusal is the default | invoked at close-out | every item `done` with a landed sha, over three channels; undetermined outranks a named blocker |
| `py_tests campaign` | the engine's own correctness | always on | `ci-local.sh` step *Campaign engine tests* | the skill's `tests/` |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `successor` | invokes | `successor` owns provisioning, launching, integrating, tearing down, and the six-element handoff bar; a campaign decides *what* is delegated and in what order | **The bar is cited, never restated.** Two copies drift and the looser copy wins silently |
| `successor-manager` | invokes | What is true of one delegated session right now — the ownership register and a verdict from channels the session does not control | A campaign **asks** it and never re-derives it; nothing here opens a daemon socket |
| `roadmap` | shares a record | Campaign items **are** roadmap items | The manifest references qualified ids and copies no title, acceptance or status. The `harness:` half of `harness:RM-0302` is the roadmap's slug, and the identity rule is called, never copied |
| `tidy` | hands off to | Close-out prints residue as a list | This skill never deletes |
| `gauntlet` | is called by | A gauntlet re-arms across campaigns and calls `close` to ask whether this batch may end | Ordering: `gauntlet` computes the frontier, `campaign close` supplies the verdict |
| `s2s` | shares a record | What a worker sends back, and why a queued message is not a delivered one (ADR-0162) | Cited, not called |
| `work-loop`, `endless`, `/relay` | explicitly excluded | Neighbouring questions the body names and refuses | Cited so the boundary does not blur |

### Additional Relevant Information

- **Ownership:** the manifest schema and the close verdict are owned here; landedness is owned by
  `.claude/scripts/lib/branch-landedness.sh`; item status is owned by the roadmap engine.
- **Related documentation:** `references/campaign-record.md` (the manifest field by field, and what
  it deliberately omits); harness ADR-0113 (the manifest stores the plan, not the status);
  harness ADR-0093 (landedness is content, never ancestry); ADR-0162 (a queued message is not a
  delivered one).
- **Known limitations / technical debt:**
  - `status` and `close` are **read-only by construction**. Nothing updates the roadmap; a campaign
    that finishes leaves item status to whoever lands the work.
  - Landedness depends on reachable remotes. On a host that cannot fetch, every row is
    `undetermined` and `close` exits 2 — correct, and indistinguishable from a network outage
    without reading the reason line.
- **Observability:** `status --json` is the machine-readable state; exit codes are the interface.
- **Security / compliance:** the manifest is committed and contains branch names and scope globs, no
  credentials.
- **Versioning:** unversioned; the manifest schema is validated rather than versioned.

---

## Skill: caveat

**Identifier:** `caveat`
**Repository:** `.claude/skills/caveat/` (harness) · `skills/caveat/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Fires the moment something turns out to behave differently from how it reads — a sharp edge, a
surprising default, a command that succeeds while doing the wrong thing, a tool whose absence looks
like a pass. **A caveat is a hazard met once, and it is worth exactly one thing: the safeguard it
buys.**

The deliverable is **two artifacts, always both**: an entry in `CAVEAT.md` carrying the condition
under which the hazard recurs, and a **landed safeguard** — a hook, a validation check, a rule, or
stated guidance with a home. Recording without converting is the failure the skill exists to
prevent; a ledger of war stories teaches nobody and warns nobody.

### Purpose and Use Cases

Fires on the hazard itself, whether or not anybody asked for it to be written down: a discovered
exception ("this works, except when"), a hazard a later session would meet the same way, an oops
moment where the workflow pauses here before continuing, or a review that produced a
"careful, X does Y" with nothing behind it.

**The cycle is pause → record → remediate → continue**, and the work in hand stops at step 1. It
resumes after the *safeguard*, not after the entry — the details are never as sharp again as they
are now, and a hazard written down later is written down as a story.

Step 3 is the field that earns the file: **state the condition under which it recurs**, as the state
that reproduces it, never the retelling. "A promotion touches a key whose rows contain an escaped
pipe" — not "someone was careless". A reader must be able to ask whether that state is present and
get an answer.

Step 4 chooses the safeguard's kind, mechanical ones first: **hook** (refuse the action before it
happens), **check** (a predicate over repository state, built by `mistake-to-gate` §1–§9), **rule**
(competent people could disagree, so a gate would be disabled — rule text via `rules-distill` at a
`paths:`-scoped tier), **guidance** (the condition is judgment and no predicate exists). *Reaching
for `guidance` first is the tell that step 2 stopped too early.*

Step 5 is ordering with teeth: **land the safeguard, then write the entry**, so the entry cites
something that exists.

### Scripts

This skill does not define any scripts.

Its enforcement is `.claude/scripts/mistakes-check.sh`, which the body names as its gate but which
is owned by `mistake-to-gate`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-voice-lint.sh` | `Stop` | every turn end | Lints the turn's prose; `Caveat:` is one of the declared kinds a delegated session may speak | the declared-kind list |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches hazard / gotcha / "watch out for" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `mistakes-check.sh` | that a `CAVEAT.md` entry converts rather than merely records | always on | `ci-local.sh` step *Mistake-log gate*, **and** in `PRE_PUSH_GATES` (declared 214ms) | refuses an entry with no `Recurs when:` and an entry with no `Safeguard:` — the conversion step is a repository-state predicate, not a sentence in the skill |
| `caveat-routing-reach.test.sh` | that the hazard intent actually reaches this skill | always on | `ci-local.sh` step *Caveat routing-reach matrix* | routing-surface coverage for the caveat trigger set |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | shares a record, and hands off | One event can be both a caveat and a counted mistake. The **key** goes in `MISTAKES.md`; the recurrence condition, impact and safeguard come here | **Ordering:** append the counted occurrence first (`mistakes.py append --key …`), then write the caveat entry citing that id in `Related mistake:`. A caveat entry must carry **no** failure-mode key — a second file able to hold one would make every count an undercount, silently, and the promotion ladder would stop firing for any key split across the two while both files looked healthy (DEC-0092) |
| `oops` | complements | `oops` owns an incident that already went wrong and is counted; a caveat may be met with nothing yet gone wrong | Both can fire on one event. A caveat with no occurrence is normal — that is the case that makes this a separate ledger rather than a column |
| `rules-distill` | hands off to | Where the safeguard's kind is `rule` | The rule half; a caveat's guidance is one hazard's, not a distilled principle |
| `learn`, `improve`, `automate` | explicitly excluded | Neighbouring questions the body names and refuses | Cited so the boundary does not blur |

### Additional Relevant Information

- **Ownership:** `CAVEAT.md` at the harness root is the ledger; the gate over it is
  `mistakes-check.sh`, owned by `mistake-to-gate`.
- **Related documentation:** `CAVEAT.md` (the entry shape); DEC-0092 and the ADR recorded with it
  (why caveats are uncounted and mistakes are counted).
- **Known limitations / technical debt:**
  - The gate checks that `Recurs when:` and `Safeguard:` are **present**, not that the safeguard
    named actually exists or works. A `Safeguard:` pointing at landed-but-broken work passes.
  - The pause discipline (step 1) is unenforceable by any predicate — commit ordering does not
    survive a squash merge.
- **Observability:** `bash .claude/scripts/mistakes-check.sh` is the one command; it prints its
  refusals.
- **Security / compliance:** hazards recorded here frequently concern destructive commands. Entries
  quote those commands as documentation, which is why the safety guard reads command *words* with
  quoted spans stripped rather than raw payloads.
- **Versioning:** unversioned.

---

## Skill: consistency

**Identifier:** `consistency`
**Repository:** `.claude/skills/consistency/` (harness) · `skills/consistency/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Asks one question before anything new is written: **what already solves this, and if something does,
why is a new one better?** Both halves are required. Naming nothing and writing anyway is the
failure; naming something and differing anyway is fine — *provided the differing is recorded where
the next reader finds it.*

The stance: **a second implementation is a decision, and an undeclared decision is a defect.** Not
because variation is forbidden, but because two copies disagree and **the looser one wins silently.**
Recorded three times in this repository under one failure key — a hook carrying its own copy of an
engine's staleness policy at 14 days while the engine said 7; a gate list hand-copied into a handoff
and missing a row; two implementations of "has promotion happened" inside a single file, disagreeing
for as long as both existed.

### Purpose and Use Cases

Fires before the writing, on the reuse question, whether or not anybody asked: a new script, gate,
matrix, helper, config format, id scheme, error convention or file layout; "is there already one of
these"; "roll our own"; and when a review finds a new variation where a working solution exists.

**Three steps.** (1) **Name the incumbent by path** — not "we probably have something", a file.
Cheapest lookups first: `ls .claude/scripts/` and `.claude/scripts/lib/` for a script or gate; the
matrix of the closest existing gate for a matrix (copy its *shape*, not its content); an existing
`.conf`/`.tsv` beside its consumer for a format; the closest existing id scheme or exit-code
convention, reusing the spelling. (2) **If something solves it, the default is reuse** — a near-fit
adapted is cheaper than a parallel implementation, because the second one is the one nobody updates.
(3) **If differing is right, record it** in descending order of durability: the new file's own
header, a row in the governing registry, the commit body, a DEC when scorable, an ADR when it
constrains future work. *A reason that names what is different about this case is a record;
"cleaner" is not.*

If the answer is genuinely "nothing", say so in one line and write the new thing. **That is the
common case and it costs a sentence.**

The gap it fills, and the only reason it is a skill: `common/development-workflow.md` step 0 says
research *the world* before writing new code, and nothing said research *this tree*.

### Scripts

This skill does not define any scripts.

Its mechanical half is `.claude/scripts/one-implementation-check.sh`, a harness gate the body names
as its enforcement rather than a script the skill owns.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "is there already one of these" / "roll our own" / "another implementation" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `one-implementation-check.sh` | that a script, hook or matrix does not recompute a predicate one of the ownership-claiming `.claude/scripts/lib/` libraries owns | always on | `ci-local.sh` step *One-implementation registry*, with `one-implementation.test.sh` as its matrix | five findings — `UNSOURCED-CALL` (names an owned symbol without sourcing its owner), `RESTATED` (matches the library's declared signature), `UNREGISTERED-OWNER` (a library claims sole ownership and the registry has no row), `STALE-REGISTRY`, and `EXEMPT`/`UNCHECKED` **printed on passing runs too**, so "exempt by design" stays a standing question |

**What the gate does not catch, said plainly in the skill's own body:** two implementations inside
one file (the unit is a file against a library); a copy of something that is not a library predicate
— a gate list pasted into a handoff, a policy value pasted into a hook; and a restatement under
different names where no signature is declared. The gate prints `UNCHECKED` for each of those on
every run rather than letting silence read as coverage.

**Measured finding — the body's counts are stale.** The skill's own text says *"Ten libraries under
`.claude/scripts/lib/` exist so that a question has one answer, and eight declare it in their own
headers"*, and *"seven of the eight rows"* have no declared signature. Run against this sha:

```
$ ls .claude/scripts/lib | wc -l                                            # 28 entries
$ grep -rl 'sole owner\|one implementation\|single implementation' .claude/scripts/lib | wc -l
7
$ bash .claude/scripts/one-implementation-check.sh . | grep -c UNCHECKED
4
$ grep -vcE '^\s*#|^\s*$' .claude/scripts/one-implementation.conf                 # 14 registry rows
```

Seven claiming libraries and four `UNCHECKED`, not eight and seven. The gate is green and the
registry is current; it is the **prose in the skill body** that has drifted, which is a small
instance of exactly the failure this skill prosecutes. Recorded here rather than corrected — this
document does not edit skills.

What it rests on is stated too: a library header *claiming* sole ownership is a correlate of the real
property, and no script can read the real one. A machine-readable marker inside each library is the
recorded successor (DEC-0114, Fork 2).

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `automate` | gates | A verdict of `automate` over a job an existing script already does is a second implementation | **Ordering: this runs before any of the six verdicts is reached.** `automate` never asks the incumbent question itself |
| `codebase-design` | routes to | The scalability half — module seams and interface depth — is judgment with an existing owner | Explicitly not re-derived here. The one thing added: *before inventing a new module shape, name the module in this tree that already has the shape you want* |
| `not-impressed` | complements | That skill reviews code that exists; this is the precondition before it exists | Opposite sides of the same writing |
| `oops`, `mistake-to-gate` | complements | Those fire **after** a failure and count recurrence; this fires **before** the writing | No runtime coupling; cited as a boundary |
| `rules-distill` | hands off to | When the recorded difference is really a principle, the rule half belongs there | Ordering: record here, distil there |
| `find-skills` | invokes | Step 1's "anything at all" lookup | Followed by `.claude/docs/skill-decision-matrix.md` |
| `improve` | explicitly excluded | The declare-before / revert-after contract for a recurring friction | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the registry is `.claude/scripts/one-implementation.conf`; the gate over it is
  `one-implementation-check.sh`. The style rules this skill deliberately does not restate are owned
  per namespace under `.claude/rules/`.
- **Related documentation:** `references/one-implementation-registry.md` (adding a row, and what a
  reason must contain); `common/development-workflow.md` § Feature Implementation Workflow step 0;
  `common/coding-style.md` (the file- and function-size ceilings); DEC-0114.
- **Known limitations / technical debt:** the gate covers one slice — a file against a library — and
  the body enumerates exactly what falls outside it. The `UNCHECKED` output on seven of eight rows is
  the honest measure of that coverage, not a defect to be silenced.
- **Observability:** `bash .claude/scripts/one-implementation-check.sh .` prints `EXEMPT` and
  `UNCHECKED` rows on green runs by design.
- **Security / compliance:** none specific.
- **Versioning:** unversioned.

---

## Skill: decision-mapping

**Identifier:** `decision-mapping`
**Repository:** `.claude/skills/decision-mapping/` (harness) · `skills/decision-mapping/` (this mirror)
**Status:** `active` · declared `version: 1.0.0`, `license: MIT`, `user-invocable: true`
**Class:** `forked` — upstream `mattpocock/skills`, `skills/engineering/wayfinder` (renamed from `decision-mapping`); MIT (Copyright (c) 2026 Matt Pocock); upstream HEAD last audited `8b78b53` (2026-08-15)

---

### Description

Charts the way to a destination when a loose idea is too big for one agent session and the route is
not visible yet. The product is a **decision map**: one committed markdown file carrying a named
destination, explicit out-of-scope, typed decision tickets, blocking edges, and a fog frontier that
advances one resolved ticket at a time.

**Plan, don't do.** Each ticket resolves a decision; the map is finished when nothing is left to
decide before someone goes and builds. The pull to just do the work is the signal that the edge of
the map has been reached and it is time to hand off.

**Forked from `mattpocock/skills`.** Two divergences are load-bearing: upstream keeps
`disable-model-invocation: true` (adopting upstream's rename would not have fixed that), and
**upstream moved the map onto an issue tracker while this fork keeps it a committed markdown file** —
the committed tier is the reset-proof one (ADR-0009) and the tier a fresh session can read with no
credentials and no network. Ported *from* upstream: the named `## Destination`, `## Out of scope` as
a scoping act distinct from fog, and `## Not yet specified` with the sharpness test.

### Purpose and Use Cases

Fires on "where do I even start", "we need to figure out X before we can plan", or a space with
several open questions that hang on each other. **Not** for scoring options against criteria
(`decision-matrix`) or sequencing work already decided (`roadmap`, `blueprint`).

**Where the map lives:** `.claude/docs/plans/<YYYY-MM-DD>-<effort>-map.md` for harness work,
`<project>/docs/plans/…` for a project. The whole map is loaded as context every session, so **it
must stay compact — it is an index, not a store.** A decision lives in exactly one place, its ticket;
the map gists and links, never restates. Assets produced while resolving a ticket are linked, never
pasted in.

**Four ticket types, each HITL or AFK.** `research` (AFK; a subagent, in parallel with its siblings,
producing a linked note), `prototype` (HITL; raise the fidelity of the discussion with something
cheap and concrete), `grilling` (HITL; the default case), `task` (either — manual work that must
happen *before a decision can be made*; the one type that does rather than decides, and it earns its
place only by unblocking a decision).

**A HITL ticket only resolves through a live exchange with a human, and the agent never stands in for
the human's side of it.** A grilling ticket whose agent answered its own questions is not resolved.
In an unattended run this is explicitly **not a licence to stop**: take every AFK ticket the frontier
offers, leave the HITL ones unclaimed with the question sharpened, and report that as the real
advance it is.

**Fog of war.** The map is deliberately incomplete. The test for fog versus ticket is whether the
question can be *stated* precisely now — not whether it can be answered now. Do not pre-slice fog
into ticket-sized pieces: one patch may graduate into several tickets, or none.

**Out of scope never graduates.** It returns only if the destination is redrawn, and then as a fresh
effort, not a resumption.

**Claiming is a commit.** A session claims a ticket by writing its `Claimed by:` line and committing
that line *before doing anything else*.

### Scripts

This skill does not define any scripts.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-ask-gate.sh` | `PreToolUse` on `AskUserQuestion` | an `AskUserQuestion` call is attempted | Refuses the stop in an unattended run and names the skills that resolve a fork instead — `decision-mapping` among them (ADR-0052) | the posture ticket |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "where do I start" / open-questions intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `skill-artifact-check.sh` | that the mandated artifact (`.claude/docs/plans/*-map.md`) exists at least once | **exempt** — `artifact_status: never-run` | the exemption is printed on every green run, so it stays a standing question | the declared reason, verbatim in frontmatter: *no decision map has ever been committed — `.claude/docs/plans` holds no `*-map.md`, measured 2026-09-01. Writing one so this gate goes green would be manufacturing an instance to satisfy a detector, which is the detector working backwards. The exemption lifts the first time a real decision map is charted* |
| `odin-ask-gate.sh` | whether a HITL ticket may stop an unattended run | **warn** interactive, **block** unattended | posture armed per session | ADR-0052 — a question is not a pause, it ends the turn |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `writing-plans`, `superplan`, `blueprint` | hands off to | Terminal successors once the route is clear | The handoff point is defined by the pull to start building |
| `decision-matrix` | hands off to, and receives from | Fuzzy options are mapped here first, then scored there | Bidirectional: `decision-matrix`'s own hand-off table sends fuzzy criteria back here |
| `grilling` / `grill-with-docs`, `domain-modeling` | invokes | Resolves a `grilling` ticket | HITL — the agent does not answer its own grilling ticket |
| `prototype` | invokes | Resolves a `prototype` ticket and links the artifact | HITL |
| `roadmap` | explicitly excluded | Sequencing work already decided | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the map file belongs to the effort that charts it; the skill is held as a fork by
  `odin-skill-manager`.
- **Related documentation:** `skills/decision-mapping/UPSTREAM.md` in this mirror; ADR-0009 (the
  committed file tier is the reset-proof one); ADR-0052 (a question ends the turn).
- **Known limitations / technical debt:**
  - **Zero instances.** No decision map has ever been committed in this repository (measured
    2026-09-01). The skill is routed, documented and unexercised — which the artifact gate records
    rather than hides. That is the single most important operational fact about this entry.
  - HITL resolution is unavailable to an unattended fleet by construction, so an unattended run can
    only ever advance a map's AFK frontier.
- **Observability:** the map file itself; `skill-artifact-check.sh`'s printed exemption.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror.
- **Versioning:** declares `version: 1.0.0` in frontmatter — one of only three members that declare a
  version at all.

---

## Skill: decision-matrix

**Identifier:** `decision-matrix`
**Repository:** `.claude/skills/decision-matrix/` (harness) · `skills/decision-matrix/` (this mirror)
**Status:** `active` · declared `version: 0.2.0`, `license: Apache 2.0`, `user-invocable: true`
**Class:** `authored`
**Command form:** `/decide`

---

### Description

A quantitative weighted-decision engine. Turns a choice into a deterministic, **recorded** decision:
options scored against weighted criteria by multiple methods (weighted-sum, Pugh, TOPSIS/AHP, and the
product frameworks RICE/WSJF/ICE/Kano), with sensitivity analysis, method-disagreement detection,
hard-constraint vetoes, multi-scorer aggregation, and a numbered `DEC-####` written to a ledger.

The division of labour is strict: **the agent elicits and frames; the script does all the math.**
Never compute scores by hand — if the script errors, surface it and stop rather than guessing.

**Decide, do not ask.** A fork that reaches this skill is the agent's to resolve: score it, record the
DEC, report the winner and the deciding reason in one line, and keep working. Handing the user a menu
of options is the failure this skill exists to prevent
(`.claude/rules/common/decision-authority.md`).

### Purpose and Use Cases

Fires for **any** non-trivial multi-option choice or prioritization, including a mid-task internal
fork: "which library/framework/database/vendor", build-vs-buy, "rank these", RICE/WSJF.

**Seven-step workflow.** Frame the goal and its reversibility (`two-way` / `one-way` — a one-way door
with a non-low-confidence winner is promoted to an ADR); 2+ real alternatives, with "do nothing"
usually belonging in the set; criteria and weights 0–100, flagged when one criterion exceeds 60% of
the weight, each marked higher- or lower-is-better; **hard constraints captured *before* scoring**,
because a vetoed option is eliminated regardless of score — that is what makes a constraint different
from a heavy weight; scores 0–100 per option × criterion × scorer, elicited one at a time with a
recommended value and its reasoning, **reading the codebase instead of asking whenever the answer is
on disk**; run; present.

Four decision-spec templates ship with the skill (build-vs-buy, technical architecture, product
prioritization/RICE, candidate or vendor selection) — adapt one, never ship it unedited, and never
keep a criterion the decision does not actually turn on.

**Which ledger a DEC lands in is a decision the spec must declare.** A decision about a project is
recorded in that project's `docs/decisions/`; only harness decisions go to
`.claude/docs/decisions/`. Precedence is flag > spec key > harness ledger, and **relative paths
resolve against the repository root, not the working directory**, because the engine runs from the
skill's own directory. Recording a project's decision in the harness ledger inflates the harness DEC
sequence and hides the decision from the project that owns it, so when the workspace contains any
`projects/*/docs/decisions/` and the spec declares no `decisions_dir`, `--record` prints a warning
naming every candidate ledger before it writes (DEC-0023). *Declaring the key silences it — the
default is an assumption, the declaration is a statement.*

**The engine refuses an incomplete spec on purpose:** a missing score is a question nobody answered,
and filling it with a plausible number launders a guess as arithmetic.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `score` | `.claude/skills/decision-matrix/scripts/score.py` | The entry point. Runs every applicable method, compares them, and optionally records the DEC | `python3 -m scripts.score [--spec <path>] [--record]` from the skill directory (spec on stdin if `--spec` omitted); engine tests are the `ci-local.sh` step *Decision-matrix engine tests* | decision-spec JSON; `--decisions-dir`; result JSON to stdout, errors to stderr with exit 1 |
| `methods` | `scripts/methods.py` | Weighted-sum, Pugh, TOPSIS/AHP, RICE/WSJF/ICE/Kano | called by `score` | the spec's criteria and scores |
| `sensitivity` | `scripts/sensitivity.py` | Fragility of the ranking; `near_tie_pairs` | called by `score` | weights and scores |
| `aggregation` | `scripts/aggregation.py` | Multi-scorer combination; the `multi_scorer_analysis` block reporting conflicts and outliers | called by `score` when more than one scorer is present | per-scorer scores |
| `validate` | `scripts/validate.py` | Refuses an incomplete spec | called by `score` before any math | the spec schema |
| `ledger` / `ledgers` | `scripts/ledger.py`, `scripts/ledgers.py` | Writes `DEC-####-<slug>.md` and upserts the ledger index; resolves which ledger owns the decision | `--record` | `decisions_dir`, repository root |
| `recall` | `scripts/recall.py` | Reads back prior decisions | called by the skill body | the ledger |
| `visual` | `scripts/visual.mjs` | Self-contained HTML rendering of a result | `node scripts/visual.mjs <result.json>` → stdout | a result JSON; Node |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

`allowed-tools` deliberately pins the `cd`-prefixed invocation forms, because `-m scripts.score`
needs the skill directory on `sys.path` and a rule that does not match that prompts on the documented
happy path; `node` is permitted only for `scripts/visual.mjs`, since a bare `node *` would permit
`node -e` for the lifetime of the invocation.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-ask-gate.sh` | `PreToolUse` on `AskUserQuestion` | an `AskUserQuestion` call is attempted | Refuses the stop unattended and names `decision-matrix` as the resolver for a scorable fork | the posture ticket |
| `odin-safety-guard.sh` | `PreToolUse` on `Bash\|Edit\|Write\|NotebookEdit` | a write near the decision ledgers | Names `decision-matrix` in its guidance for ledger paths | none |
| `odin-surface-router.sh` | `PreToolUse` on `Write\|Edit\|NotebookEdit\|Bash` | the file being written is a decision record | Names this skill for the surface, with no prompt involved | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "decide" / "compare options" / "prioritize" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `decision-ledger.test.sh` | ledger format, index upsert, and the `Gaps` accounting | always on | `ci-local.sh` step *Decision-ledger matrix* | the ledger's own invariants |
| `id-allocation.test.sh` | that two sessions cannot mint the same `DEC-####` | always on | `ci-local.sh` step *Id-allocation matrix* | compare-and-swap over `refs/odin/ids/*` |
| `ledger-scope-default.test.sh` | that a project's decision is not silently recorded in the harness ledger | always on | `ci-local.sh` step *Ledger-scope default matrix* | DEC-0023 — the warning naming every candidate ledger when `decisions_dir` is undeclared |
| `py_tests decision-matrix` | the engine's own correctness | always on | `ci-local.sh` step *Decision-matrix engine tests* | the skill's `tests/` |
| the incomplete-spec refusal | whether math runs at all | always on | inside `validate.py` | a missing score is a refusal, never a default |
| hard constraints (`veto_reasons`) | whether an option is eligible regardless of score | per-spec; empty by default | declared in the spec before scoring | a vetoed option is eliminated; when all options are vetoed, the constraints **are** the decision and must be quoted, not silently relaxed |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `roadmap` | shares a record, bidirectionally | `roadmap prioritize --export` → score → `roadmap prioritize --from` round-trips RICE scores onto items | A DEC produced while prioritizing lands on each item as `priority.dec`, so `roadmap next`'s ordering carries the audit trail of why it is ordered that way |
| `architecture-decision-records` | hands off to | `promote_to_adr_hint` fires on a one-way door decided with confidence | Ordering: DEC first, ADR promoted from it |
| `decision-mapping` | receives from, and hands back to | Fuzzy options are framed there and scored here | Bidirectional |
| `grilling` / `grill-with-docs` | invokes | When criteria need an interview to pin down | Elicitation style is borrowed wholesale — one at a time, with a recommendation |
| `blueprint` | hands off to | When the chosen option is a multi-PR effort | Then `roadmap` registers its steps |
| `recursive-decision-ledger` | shares a convention | The numbered `DEC-####` ledger notion originates there | Not a call; a reused convention |
| every skill with a fork to resolve | invoked by | `automate`, `out-of-scope`, `tidy`, `improve` and others delegate their arithmetic here | This is the harness's single scoring engine |

### Additional Relevant Information

- **Ownership:** the engine and the ledger format are owned here; id allocation is owned by the
  harness's CAS allocator over `refs/odin/ids/*`.
- **Related documentation:** `references/decision-spec-schema.md`, `references/elicitation.md`,
  `references/multi-scorer.md`, `references/product-frameworks.md`, `references/pugh-matrix.md`,
  `references/sensitivity-analysis.md`, `references/topsis.md`;
  `.claude/rules/common/decision-authority.md`; DEC-0023.
- **Known limitations / technical debt:**
  - **Scoring to a predetermined winner** is the named failure mode: a rigged matrix is worse than an
    opinion because it looks like evidence.
  - The `redundant` criteria warning catches **labels, not synonyms** — three flavours of "developer
    experience" triple that concern's weight silently, and a human catches that.
  - A `near_tie` including the winner means the lead is inside the noise; the tiebreaker must be
    named rather than assumed.
  - A companion project, `projects/decision-matrix-web`, has its own gate stepped in `ci-local.sh`;
    it is a separate deliverable and not part of this skill's package.
- **Observability:** result JSON, the HTML artifact from `visual.mjs`, and the committed
  `DEC-####-<slug>.md` with its ledger index row.
- **Security / compliance:** `allowed-tools` is deliberately narrow — the `node` entry permits only
  the bundled renderer. Apache-2.0 declared in frontmatter.
- **Versioning:** declares `version: 0.2.0`.

---

## Skill: endless

**Identifier:** `endless`
**Repository:** `.claude/skills/endless/` (harness) · `skills/endless/` (this mirror)
**Status:** `active`
**Class:** `authored`
**Command form:** `/loop`, `/autoloop` (one iteration)

---

### Description

The continuous work loop. `roadmap` decides **what**, `successor` decides **who**, and this skill
decides **whether to keep going, hand off, or fan out** — at every checkpoint, from an observable
predicate rather than from whatever the context window still holds.

**Core principle: an iteration ends at a checkpoint, not at a task.** A finished task with nothing
decided after it is where autonomy dies quietly — the session idles, the branch sits unpushed, and
the next roadmap item waits for a human. Every checkpoint forces one of three named continuations.
There is no fourth, and *"stop" is not one of them unless a human is owed something.*

Declared a **rigid** skill: the checkpoint decision is not a judgment call.

### Purpose and Use Cases

Fires on an unattended or overnight run, a `/loop` or `/autoloop` iteration, a session told to keep
going until the roadmap is empty, a checkpoint reached with work still queued, or a run whose context
is filling before the work is done.

**Not for** a single task with a defined end, or a loop over work that shares mutable state —
parallel sessions on one checkout corrupt each other's index (ADR-0054).

**Ten phases:** arm posture → track → pick → gate → build → verify → land → capture → checkpoint →
continue. The phase-to-skill table is not restated in the skill — it lives in
`.claude/docs/autonomous-loop-standard.md`, and the commands live in `/autoloop`, because a third
copy of a table is a third thing to drift. Two phases carry facts an operator needs:

- **Phase 1** re-arms posture **every** iteration. The claim is TTL'd; skipping the renewal drops the
  gates back to `warn`, and *a warned gate in an unattended run is a gate that did nothing.*
- **Phase 2** creates the task list before any other tool. No task list → no completed task → no
  compaction boundary, ever (ADR-0031, ADR-0036).
- **Phase 8** has a second half only a loop has: an incident becomes a guard, through `oops`. A loop
  that captures features and drops its own mistakes re-makes them on a schedule.

**Three checkpoints, and only three:** `Landed` (on `main`, closed with the **landed** sha — a topic
branch sha does not survive the rebase that merged it); `Hard blocker` (an external dependency
refuses — missing credential, failing upstream, rate limit, or a decision that spends money or is
outward-facing); `Context` (past roughly half the ceiling → `/relay`).

**`blocked` is not a roadmap status**, and the skill says so against its own history: the engine's
statuses are `proposed`, `ready`, `in-progress`, `done`, `dropped`, so the command this row
prescribed for most of its life — `roadmap set … --status blocked` — *could not run at all*.
Blockedness is **computed**, from an unmet `deps` edge or from an `escalate` record in a `work-loop`
ledger. `gauntlet frontier` reports the two apart and never sums them: collapsing them is how a rate
limit gets reported as a dependency and waited on forever.

**Explicitly not checkpoints:** in-scope work left undone by choice; a plan written but not executed;
a branch green but unpushed; "this deserves its own session later".

### Scripts

This skill does not define any scripts.

It names three harness scripts as its machinery: `.claude/scripts/odin-autonomous.sh` (phase 1),
`.claude/scripts/ci-local.sh` (phase 6), and `.claude/scripts/session-burn.sh` (the first
continuation predicate).

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "keep going" / autonomous-loop intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `odin-autonomous.sh` (posture) | whether the plan gate and task gate **block** or merely **warn** | `warn` (interactive) | armed per session, TTL'd, re-armed **every** iteration; bound to the session's process tree so no other session can claim it (DEC-0020) | a published ticket claimed by the next gated tool call (ADR-0051) |
| `session-burn.sh` | whether the loop relays on **spend** rather than depth | always on; exit 3 is the trip | first predicate at every checkpoint, ahead of the context predicate | measured: 48 sessions — the top 1% — accounted for 69.5% of all successor cache-read over 29 days, and the heaviest ran 853 turns at ~239K prefix (~24% of a 1M ceiling, so the *context* row never fired once) for **$159.61**; the median successor session cost about a cent |
| `session-burn.test.sh`, `autonomous-posture.test.sh`, `loop-position-check.sh` | the loop's own machinery | always on | `ci-local.sh` steps *Session burn meter*, *Posture scope reporting*, *Loop position register* | each asserts its own predicate |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `roadmap` | invokes | Phase 3 picks the next unblocked item and sets it in-progress | **Never from `ROADMAP.md` prose, never from memory of the last iteration** |
| `successor` | invokes | The Delegate continuation — become a coordinator, all five phases, then integrate and resume at phase 1 | Fires when `roadmap waves` puts ≥2 items in one layer **and** their surfaces do not overlap |
| `handoff` / `/relay` | hands off to | The Relay continuation, on either the burn or the context predicate | This session stops only after confirming the branch is pushed |
| `oops`, `mistake-to-gate` | invokes | Phase 8's second half — an incident becomes a guard (ADR-0057) | Ordering: capture the feature findings *and* the mistakes |
| `work-loop` | shares a record | The `escalate` outcome with `--blocker`, `--evidence`, `--recommended-next` is how a hard blocker is recorded | A blocked item is not a stopped loop — the loop moves to the next item |
| `gauntlet` | complements | This decides whether to continue; `gauntlet` computes what is left and which of it goes in the next wave | `gauntlet frontier` reports dependency-blocked and externally-blocked apart |
| `out-of-scope` | invokes | A defect surfaced mid-iteration outside the item in hand | This skill never decides what happens to a finding inside an iteration |
| `off-topic` | complements | Its checkpoint is a committed debt; this skill's checkpoints decide whether to continue at all | Different senses of the same word, deliberately distinguished |
| `dynamic-workflow-mode` | complements | A task-local harness for one loop | Cited in the routing map |

### Additional Relevant Information

- **Ownership:** the phase table is owned by `.claude/docs/autonomous-loop-standard.md`; the commands
  by `.claude/commands/autoloop.md`; the continuation predicates here.
- **Related documentation:** `.claude/docs/autonomous-loop-standard.md` (phase → skill, rows 0–22);
  ADR-0031 and ADR-0036 (task list → compaction boundary); ADR-0051 (posture is per-session);
  ADR-0054 (parallel sessions on one checkout); ADR-0057 (incident → guard); ADR-0060 (checkpoints
  and the three continuations).
- **Known limitations / technical debt:**
  - The skill records its own historical defect — a prescribed command that could not run — rather
    than quietly correcting it. An operator reading an old loop transcript will see that command.
  - The burn thresholds are measured on one host over one window; they are a policy, not a law.
- **Observability:** `bash .claude/scripts/session-burn.sh` (exit 3 trips the relay);
  `roadmap waves`; the `work-loop` ledger for escalations.
- **Security / compliance:** phase 6 verifies **locally**; dispatching a workflow is blocked
  always-on and would test the pushed tree rather than the working one.
- **Versioning:** unversioned.

---

## Skill: factory

**Identifier:** `factory`
**Repository:** `.claude/skills/factory/` (harness) · `skills/factory/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `coleam00/skills`, `.claude/skills/build-dark-factory` at `ecef6ffd4caa0b23a8c79601c1215b1e2908ac72` (2026-08-25). Declared in frontmatter: `origin: fork`, `upstream: coleam00/skills — build-dark-factory @ ecef6ffd`, `forks: build-dark-factory`

---

### Description

Builds a **dark factory** into a repository: work goes in as an issue, validated code comes out,
nobody reads the diff. Five components in construction order — the guidance layer, the validation
harness, the workflow-driven repo, deployment, and the trigger that makes it autonomous.

Its stance is that it is **not a different way of coding with AI — it is the way the repo already
codes with AI, with the human checkpoints removed.** Whatever process runs today goes inside: Spec
Kit, BMAD, a PRP framework, or Odin's own roadmap → superplan → TDD → review chain. Steps stay,
skills stay, MCP servers, rule files, subagents and commands stay.

It requires a PRD as input and **deliberately does not write one**. It builds into the repo and
**does not hand over a design document** — every phase ends with files committed and something
demonstrably working.

**Forked from `coleam00/skills`' `build-dark-factory`.** This is a fork rather than a vendoring, and
it is excluded from `vendor-skills.sh` with the reason inline there, so no refresh fights it.

### Purpose and Use Cases

Fires on: a dark factory, an autonomous or self-driving repository, a software factory, an agent that
ships its own code, an unattended or overnight coding loop, autonomous PRs, lights-out coding, a repo
that maintains itself, or "how do we reach level 4 or 5 of AI coding autonomy". Also used to **audit,
arm, raise the dial on, or stop** a factory that already exists.

**Four Odin-specific divergences, each with an operational consequence:**

1. **No question rounds.** `AskUserQuestion` is never called, in any phase (ADR-0052). The interview
   still runs, still computes its questions, still carries one recommendation each — and then
   *adopts the recommendation and records it* as a numbered DEC or in the plan doc's decision-forks
   section. Upstream mandated the question tool in capitals with no fallback; a skill whose first
   phase is a three-round interview would stop an unattended run three times before writing a line.
2. **Plan before edits.** CLAUDE.md item 5's three preconditions apply, and the plan goes in
   `.claude/docs/plans/` — the only directory `odin-plan-gate.sh` searches.
3. **The governance files are protected mechanically, not by prompt.** Layer 1H of
   `.claude/hooks/odin-safety-guard.sh` refuses a write to `MISSION.md`, `FACTORY_RULES.md` or
   `FACTORY.md` in a factory repo. *A guard a node calls is a guard the node can skip.*
4. **One decider, many entry points (ADR-0170).** `factory/orchestrator.sh` decides what runs next;
   `workflows/factory-lap.yaml` runs one dispatcher tick as an Archon workflow so a lap is startable,
   watchable, resumable and cancellable through the same surface as everything else — **and it
   decides nothing.** An entry point may observe, refuse before spending, and report; it may not
   compute the refusal, and it may not carry its own copy of a value `factory/config.sh` owns. This
   was prose until the lap workflow's preflight drifted into its own stop-button test, and it is now
   checked by `.claude/tests/factory.test.sh`.

The skill also carries an explicit **output discipline** table, added because a user of the upstream
version reported it as *"incredibly frustrating and hard to process, overwhelming to say the least"*
— and that was the skill working, explaining itself at every step. Budget: nothing between decisions;
two lines at a phase end; a command's output never pasted, verdict and number only.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `factory_doctor` | `.claude/skills/factory/scripts/factory_doctor.py` | Audits an existing factory — what exists, what is armed, what is missing | invoked by the skill body when auditing or arming | the target repository path |
| `_runner` | `scripts/_runner.py` | Shared harness for the skill's own checks | called by the others | — |
| `_audit_runner` | `scripts/_audit_runner.py` | Drives the audit pass | called by `factory_doctor` | — |
| `_test_factory_doctor` / `_test_audit_runner` | `scripts/_test_factory_doctor.py`, `scripts/_test_audit_runner.py` | The skill's own tests | `ci-local.sh` step *Factory machinery* (`--timeout 900`) via `.claude/tests/factory.test.sh` | — |

The skill also names, in the repository it builds: `factory/orchestrator.sh` (the one decider) and
`factory/config.sh` (the single owner of configured values).

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-safety-guard.sh` Layer 1H | `PreToolUse` on `Bash\|Edit\|Write\|NotebookEdit` | a write targeting `MISSION.md`, `FACTORY_RULES.md` or `FACTORY.md` in a factory repo | **Refuses** it — the governance files are unamendable from inside the factory | none; blocked always-on |
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write with no active plan | warns interactive, blocks unattended | `.claude/docs/plans/` |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches dark-factory / lights-out intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `factory.test.sh` | the skill's machinery, including that an entry point does not compute its own refusal or carry its own copy of a `config.sh` value | always on | `ci-local.sh` step *Factory machinery*, `--timeout 900` — the longest single step in the suite | ADR-0170's one-decider invariant, now a predicate rather than prose |
| safety-guard Layer 1H | whether the governance files may be written from inside the factory | **blocked always-on**; no posture or permission grant lifts it | in `.claude/hooks/odin-safety-guard.sh` | path match on `MISSION.md` / `FACTORY_RULES.md` / `FACTORY.md` in a factory repo |
| the autonomy dial | how much the factory does without a human | raised **on evidence**, never by default | `.claude/rules/factory/patterns.md` | the rule namespace's own criteria |
| the Archon lap preflight | whether a lap spends anything | refuses before spending | `workflows/factory-lap.yaml`, checked by `archon-lap.test.sh` | observes and refuses; **never computes** the refusal |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `archon` | invokes | A factory lap runs as an Archon workflow, startable and cancellable through the same surface as everything else | The workflow decides nothing; `factory/orchestrator.sh` is the only decider (ADR-0170) |
| `decision-matrix` | invokes | Every discharged interview round is recorded as a numbered DEC instead of an `AskUserQuestion` | ADR-0052; `references/interview.md` states the discharge per round |
| `roadmap`, `superplan`, `test-driven-development` | composes | The factory encodes whatever process the repo already runs; in this repository that is Odin's own chain | Not replaced — wrapped |
| `agent-harness`, `agent-harness-construction` | complements | Making a repository agent-ready is the precondition; this removes the human checkpoints afterwards | Ordering: harness first |
| `oops` | invokes | The validation harness's failures become guards | Cited in the factory's own loop |

### Additional Relevant Information

- **Ownership:** the fork is held by `odin-skill-manager`; the rule half is
  `.claude/rules/factory/patterns.md`; the guard is Layer 1H of the safety guard.
- **Related documentation:** `references/setup.md`, `references/interview.md`,
  `references/guidance-layer.md`, `references/validation-harness.md`, `references/automation.md`,
  `references/deployment.md`; `.claude/skills/factory/UPSTREAM.md` **and** the mirror copy (one of
  only two forks carrying `UPSTREAM.md` in both places); ADR-0170; ADR-0052.
- **Known limitations / technical debt:**
  - `UPSTREAM.md` records three upstream defects that "would reach any Linux user of the upstream
    skill" and are worth reporting upstream; they are carried as local divergence rather than fixed
    at source.
  - The skill is heavy: `factory.test.sh` is the suite's longest step at a 900-second bound.
  - It requires a PRD it will not write, so an operator arriving without one is blocked at Phase 0
    by design.
- **Observability:** `factory_doctor` is the audit surface; the Archon run is watchable through
  `manage-run`.
- **Security / compliance:** this is the highest-reach skill in the corpus — it constructs a
  repository that merges its own code. The unamendable governance files and the always-on Layer 1H
  refusal are the security boundary, and they are mechanical precisely because a prompt-level rule
  can be skipped by the node it is addressed to.
- **Versioning:** unversioned here; upstream divergence pinned by sha in frontmatter and
  `UPSTREAM.md`.

---

## Skill: gauntlet

**Identifier:** `gauntlet`
**Repository:** `.claude/skills/gauntlet/` (harness) · `skills/gauntlet/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

The campaign that re-arms. **A gauntlet does not end when its list does — it ends a *batch*.**

The reasoning is measured, not asserted: over the 14 days ending 2026-09-02 this repository created
385 items and closed 252 — **1.53 created per completion, with no day below 1.0**. A loop instructed
to "run until zero open items" is therefore instructed to run forever without ever reaching a state
it can report, which is how a run goes silent for twelve hours with no verdict. *The skill tells its
reader to re-measure that ratio before quoting it; it is a fact about a period, not a constant.*

So the unit is a **batch**: an item set frozen at a pinned base, so `campaign close` can compute a
verdict over something that holds still, plus a **re-arm** that recomputes the frontier and rolls
into the next batch. The loop never stops; the batch always does.

Declared a **rigid** skill — the channel order, the refusals and the exit codes are not judgment
calls.

### Purpose and Use Cases

Fires on: an endless gauntlet; a campaign that re-arms instead of ending; "keep going until every
issue and roadmap item is done"; a batch that finished while new work kept arriving; a coordinator
asking what is left across roadmap *and* tracker at once; "re-arm", "next wave", "quick wins first";
and when a campaign looks finished and the loop must decide whether to start another.

**Eight-step cycle:** arm and reconcile → frontier → plan → assign → build → integrate → verify →
**re-arm**. Step 8 is the one nothing else has: *a closeable batch is not a finished gauntlet.*
Step 6 gates the **merged** result — a branch green before its rebase says nothing about what lands.

Step 8 also has a second half a single batch does not: **every finding becomes capturable work
before the re-arm** — a feature or defect to `roadmap`/`to-issues`, an incident to `oops` →
`mistake-to-gate`, a hazard to `caveat`, an unobserved effect to `mutations`, a recurring friction to
`improve`, a durable lesson to `learn`, a third repetition to `automate`. An uncaptured finding dies
with the batch, and findings are the next batch's fuel.

**Three terminal states, and nothing else:** *batch closed, loop continues* (re-arm — not an end);
*budget* (`session-burn.sh` exits 3, or a usage limit lands — recorded as a `revive` manifest with
the assignment and a not-before instant, so the fleet restarts without a human); and *every
remaining item externally blocked* — each open item carrying a `blocked-external` record with
blocker, evidence and recommended next action, via `work-loop iterate --outcome escalate`, three
fields each, **and then the loop ends having said why**.

**Nothing here writes state.** The frontier is a *status*, and a stored status reads identically
whether it is current or six hours old — measured in this repository at **31 of 43** issues already
fixed while the tracker said otherwise. The plan lives in the campaign manifest, the cycle in the
`work-loop` ledger, the restart in the `revive` manifest; this skill adds no store.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `gauntlet` | `.claude/skills/gauntlet/scripts/gauntlet.py` | `frontier` (read four channels; refuse to call an unread one empty), `rearm` (emit a wave, holding back colliding surfaces), `verify` (may the batch close, **and** what appeared since it was pinned) | `python3 -m scripts.gauntlet <sub> --root … [--explain] [--json] [--width N] [--manifest <file>]`, run from the skill directory | the roadmap, the tracker, the campaign manifest, the remote |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

Exit codes, per command: `frontier` — 0 empty **and every channel read**, 1 work remains (the
ordinary case), 2 a channel could not be read. `rearm` — 0 a wave was emitted, 2 a channel could not
be read, 3 nothing assignable. `verify` — 0 the batch may close **and** the frontier is empty, 1
refused (unlanded, or new work appeared), 2 undetermined.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "re-arm" / "next wave" / exhaustive-backlog intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `gauntlet-ledger-citation.test.sh` | that the ledger conformance mapping is cited rather than restated | always on | `ci-local.sh` step *Gauntlet ledger citation* | DEC-0118 — the field-by-field mapping against the source protocol's `gauntlet/state.json` / `gauntlet/ledger.jsonl` naming |
| the frontier's channel-read refusal | whether an unread channel may be reported as empty | refuses; exit 2 | inside `frontier` | four channels, each read or declared unread. **Empty enumeration with a clean exit is the shape being refused** |
| the surface-collision check at `rearm` | whether two items may be co-scheduled in one wave | holds colliding surfaces back | inside `rearm` | overlap between the items' declared surfaces. `endless` states this check in prose and **no code performed it** — closing that is the skill's stated reason to exist |
| `campaign close` | whether a batch may close | refuses while any item is unlanded | called by `verify` | delegated in full; never re-derived |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `campaign` | invokes | `verify` **calls** `campaign close` for the batch verdict | Landedness by content, the remote-first channel order and the no-status refusal (ADR-0113) are cited, never re-derived |
| `endless` | complements | This says what the frontier holds; `endless` decides what to do about it | The continuation predicates stay there |
| `work-loop` | shares a record | The cycle's contract, twelve fields, six outcomes, four stall predicates, quality rubric, critic packet and ledger | All of it belongs there. Field mapping in `references/ledger-conformance.md` (DEC-0118) |
| `successor`, `successor-manager` | invokes | Delegation and the truth about a live session | The five phases and the six-element bar are `successor`'s |
| `revive` | hands off to | The budget terminal state writes a revival manifest with a not-before instant | The fleet restarts with nobody at the keyboard |
| `roadmap` | invokes | `reconcile`, item identity, the slug rule, `next`/`waves` | Never re-derived |
| `triage`, `to-issues` | hands off to | **A tracker row is emitted as a finding, never placed in a wave** | A hard ordering constraint |
| `superplan`, `blueprint`, `writing-plans` | invokes | The plan-depth bar applies **per item, not per batch** | Ordering: plan each item before assigning it |
| `tidy` | hands off to | Close-out hands residue over as a list | Deletes nothing |
| `s2s` | cites | What a worker says back, and that a send reports on the send (ADR-0162) | Cited, not called |

### Additional Relevant Information

- **Ownership:** the composition order and the refusals are owned here; every capability it composes
  is owned elsewhere and cited by name.
- **Related documentation:** `references/rearm-cycle.md` (channels, blockedness, the ordering formula,
  every refusal); `references/ledger-conformance.md` (DEC-0118); ADR-0113.
- **Known limitations / technical debt:**
  - The 1.53-per-completion figure is period-bound and the skill says so; quoting it as a constant is
    the failure it warns against.
  - `frontier` reads a tracker, so it depends on network reachability; unread channels exit 2 rather
    than degrading to a partial answer, which is correct and indistinguishable from an outage without
    reading the reason line.
- **Observability:** `frontier --explain` and `--json`; the campaign manifest; the `work-loop` ledger.
- **Security / compliance:** no credentials of its own; tracker access inherits the session's.
- **Versioning:** unversioned.

---

## Skill: grill-with-docs

**Identifier:** `grill-with-docs`
**Repository:** `.claude/skills/grill-with-docs/` (harness) · `skills/grill-with-docs/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `mattpocock/skills` (`skills/engineering/grill-with-docs/`), MIT (Copyright (c) 2026 Matt Pocock)

---

### Description

A relentless interview that treats every claim as unverified until a source is cited. Ordinary
grilling sharpens what *you* think; this sharpens what is *true*, then writes it down.

**Core principle: an unsourced claim is an open question wearing a confident face.**

Two things separate it from `grilling` alone. Every claim under interview is checked against a
source — the documentation, the code, the spec, the API's real behaviour — before it settles a branch
of the design tree. And **the session produces artifacts**, not just agreement: decisions land as
ADRs, vocabulary lands in the glossary. *An interview that resolves five forks and records none of
them did not happen.*

**Forked from `mattpocock/skills`, and there is no line of upstream's stub left in the body.**
Upstream ships a stub; the fork's own `UPSTREAM.md` states the reason for the rewrite: a stub cannot
assert its dependencies loaded, and upstream's own documentation names partial loading as a hazard.
The fix for silent partial loading is a **loud first step**, which is what this fork opens with.

### Purpose and Use Cases

Fires when: a plan or design rests on claims about a library, API, protocol or spec nobody has read
end to end; "the docs say…" / "I think it works like…" — assertion without citation; a requirements
interview over a heavy document corpus; onboarding a domain whose vocabulary is not pinned down; or
before committing to an integration whose real behaviour is assumed.

**Not for** eliciting *preferences* (`grilling` — there is no source to check a preference against),
exploring intent from scratch (`brainstorming`), or a decision with scorable criteria and no factual
dispute (`decision-matrix`).

**Step 0 asserts the dependencies loaded, every time.** The skill composes two others, and loading
only one produces the worst outcome — a plausible interview with no paper trail, or a paper trail
with no rigour — and the failure is **silent**. The step makes it loud: invoke both, then confirm in
one line that you can state the **frontier** from `grilling` and the **ADR format** from
`domain-modeling`. Cannot state one? Stop and say which did not load.

**Four verdict labels, used exactly:** `supported` (source says this, and it was read this session —
settles, cite it in the ADR); `contradicted` (source says something else — **reopens the parent
decision, and this is the finding worth the session**); `gap` (no source found or none exists —
branch stays open, recorded as an explicit unknown, *never as a soft yes*); `weak` (indirect, stale
or inferential — settles only with the weakness named in the ADR). A contradicted claim pushes the
frontier **backwards**, and that is the point, not a setback.

Done when the frontier is empty **and** every settled branch cites a source.

**Unattended:** `grilling`'s wait-points are discharged per
`.claude/rules/common/decision-authority.md` — state each question with its `➡️` answer, adopt it,
continue. **The verification gate is not discharged.** Nothing about running unattended makes an
unsourced claim more true; if anything it removes the last human who might have said "wait, is that
right?" A `gap` stays a gap and the plan proceeds under a stated assumption; *it is never quietly
upgraded to `supported` because the run needed the branch closed.*

### Scripts

This skill does not define any scripts.

It ships an `agents/` directory beside `SKILL.md` rather than a `scripts/` one.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches doc-grounded interview / "the docs say" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| Step 0's dependency assertion | whether the interview runs at all on partial loading | stop-on-failure; not advisory | the skill's own first step | the agent must state the frontier and the ADR format from the two sub-skills |
| `elicitation-contract.test.sh` | that the elicitation contract this and `grilling` share holds | always on | `ci-local.sh` step *Elicitation-contract matrix* | the contract's own predicate |
| the unattended discharge | whether a wait-point may stop an unattended run | **warn** interactive, **discharged** unattended | `.claude/rules/common/decision-authority.md`, per-row | the wait-point is discharged; **the verification gate is not** |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `grilling` | **invokes — required** | The frontier/rounds interview mechanics | Ordering is absolute: assert it loaded before anything else. Partial loading fails silently, which is why step 0 exists |
| `domain-modeling` | **invokes — required** | The ADR and glossary formats | Same assertion. **The ADR path is `.claude/docs/adr/`, not `docs/adr/`** — `domain-modeling` names the latter, which in this repository would start a second ADR tree with its own numbering, colliding with the ranges `.claude/docs/adr/README.md` indexes. *When the two disagree, this skill's line wins* |
| `architecture-decision-records` | shares a record | Decisions the interview settles land as ADRs | Format is `domain-modeling`'s |
| `writing-plans` | shares a record | Findings — every gap, contradiction and weak source — go to the plan doc's decision-forks section, one row per finding with its verdict label | Ordering: interview, then plan |
| `brainstorming`, `decision-matrix` | explicitly excluded | Intent from scratch, and scorable criteria with no factual dispute | Cited as boundaries |

### Additional Relevant Information

- **Ownership:** held as a fork by `odin-skill-manager`; the ADR tree it writes into is owned by
  `.claude/docs/adr/README.md`.
- **Related documentation:** `skills/grill-with-docs/UPSTREAM.md` in this mirror;
  `.claude/rules/common/decision-authority.md` (the per-row discharge of `grilling`'s wait-points);
  `CONTEXT.md` (the glossary destination).
- **Known limitations / technical debt:**
  - The skill's correctness depends on an agent honestly reporting whether two sub-skills loaded.
    That is an assertion, not a predicate — nothing mechanical verifies it.
  - It carries a path override against a sub-skill it invokes (`docs/adr/` vs `.claude/docs/adr/`).
    Two documents disagree in plain text and the resolution lives in this one; a reader of
    `domain-modeling` alone gets the wrong answer.
- **Observability:** the ADRs and glossary entries it produces are the trace. An interview with no
  artifacts is the failure.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror. It reads external documentation, so it can pull untrusted text into context.
- **Versioning:** unversioned.

---

## Skill: handoff

**Identifier:** `handoff`
**Repository:** `.claude/skills/handoff/` (harness) · `skills/handoff/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `mattpocock/skills`, MIT (Copyright (c) 2026 Matt Pocock); upstream HEAD last audited `8b78b53` (2026-08-13)
**Command form:** `/relay`

---

### Description

Hands this session's work to a **separate successor session**. Three phases, in order: write the
document, launch the successor, then stay on as its monitor. A handoff **ends this session's
ownership of the work** — this session does not carry on building; it watches, integrates, and lands.

**Delegation is the default, not a follow-up step.** A handoff that stops at a written document
leaves the work in the context window it was written to escape, and the second step is the one nobody
takes.

**Forked and rewritten around the Odin harness's session and memory internals**, which upstream has
no equivalent of. Upstream has since added `agents/openai.yaml` (Codex metadata) to every skill,
which this fork does not carry.

### Purpose and Use Cases

Fires when a long-running session is out of context, when work must continue past this context
window, or when another agent should pick the work up. One successor is this skill; a coordinated
fleet — several workers, per-worker branches, waves — is `successor` (ADR-0059). **Both launch
through the same script and inherit its refusals; neither re-implements them.**

**Phase 1 — the document** goes to `.claude/.runtime/handoff/<ISO8601>.md`, with `-` in the time
portion because colons are not path-safe everywhere. `.claude/.runtime/` is git-ignored and is the
established home for harness-internal session state, so the handoff survives an OS temp sweep, stays
out of every commit, and **never reaches a remote**.

Six frontmatter fields are required (`created_at`, `project_id`, `mem_class`, `active_branch`,
`plan_file`, `next_action`); `worktree:` and `hop:` are optional. **No trailing comments on a
frontmatter line** — the relay's reader is shell builtins, not a YAML parser, so
`hop: 1  # first handoff` is a hop number that reads `1  # first handoff` and is refused.

Several conditions are **refused** by `.claude/scripts/odin-relay.sh` rather than warned about,
*because the session that would read a warning is the one about to be cleared*: a `project_id` that
does not name the project (ADR-0038); a `## Suggested skills` section that names no skills
(ADR-0056); an unqualified roadmap id — `harness:RM-0034`, never `RM-0034`, since ids are
per-roadmap counters and a successor has no memory of which roadmap was open (ADR-0050); a declared
worktree that is not the directory being launched in (`harness:RM-0566`); and a `hop:` at the chain
ceiling (`harness:RM-0434`). Ids inside fenced blocks are exempt.

**The launch directory is quiet when wrong.** A successor starts in the relay's working directory;
every `git` call in a generated brief carries `git -C <worktree>`, so commits and pushes land
correctly **while the session's own reads, its hooks, and `odin-plan-gate.sh`'s plan search all
follow the wrong tree.** Roster rows from earlier campaign batches show workers running in the
coordinator's checkout with briefs that named a worktree, and nothing said so.

**The chain has a ceiling.** `hop:` is how many relays produced this handoff; absent means hop 0.
The relay refuses at `ODIN_RELAY_HOP_MAX` (default 8), because a chain that long is usually a loop
that cannot finish rather than work nearly done — every hop pays a fresh context window to re-read
what the last one already knew. **The count only advances if each successor writes it**, and nothing
mechanically forces the increment: a parent cannot verify a document its child has not written yet,
so *an omitted `hop:` restarts the chain and its bound stops meaning anything.* A reader resolves its
predecessor by arithmetic — its own hop minus one — rather than by a path that may already have been
swept.

**What a handoff captures: ephemeral working state only.** It is not a memory tier. Durable facts
belong in `CONTEXT.md` and `.claude/docs/adr/`; curated recall belongs in claude-mem under the active
class. Nothing is promoted automatically — *a handoff is discardable by definition, and a fact that
matters beyond the next session does not belong only in one.*

**Phase 3 reads four channels, in order, because each alone lies:** `fleet-health.sh` **first** — the
other three cannot report their own absence. The registry is served by the daemon, and when the
daemon exits it keeps returning its last-known list, so **a dead session renders as `blocked`,
indistinguishable from working** (M-0014). The script reads the daemon's control socket from disk
instead, which the subject cannot fake once it is gone.

**This skill cannot clear or end the session.** No hook event returns a field that resets context and
`/clear` is a client command the agent cannot type (ADR-0038, ADR-0036). The relay makes clearing
cheap; the keystroke stays the user's. *Never claim to have cleared anything.*

### Scripts

This skill does not define any scripts of its own. It names two harness scripts as its machinery:

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `odin-relay.sh` | `.claude/scripts/odin-relay.sh` | Validates the handoff, then launches the successor as a separate OS-level session | invoked by the skill body; `--dry-run` first, which prints the command and launches nothing | `--handoff <path>` (absolute when the successor runs in another worktree), `--name`, `--cwd <worktree>`; `ODIN_RELAY_HOP_MAX` (default 8) |
| `fleet-health.sh` | `.claude/scripts/fleet-health.sh` | Reads the daemon's control socket from disk — the one channel a dead session cannot fake | phase 3, first of four | none |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-compact-boundary.sh` | `PostToolUse` on `TaskUpdate` | a task completes | Marks a compaction boundary; names `handoff` as the alternative when context is the constraint | a task list must exist at all (ADR-0031) |
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write is attempted | Names `handoff` among the skills whose documents are exempt from the plan requirement | the plan directories |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches out-of-context / hand-this-forward intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `odin-relay.sh`'s refusals | whether a handoff may launch at all | refuses, never warns | inside the relay, at launch | six conditions: unnamed `project_id`, empty `## Suggested skills`, unqualified roadmap id, declared-but-not-current worktree, `hop:` at ceiling, malformed frontmatter line |
| `ODIN_RELAY_HOP_MAX` | the chain ceiling | **8** | env override | integer comparison against `hop:`; the relay names the hop it stopped at |
| `relay.test.sh`, `relay-seed.test.sh`, `relay-handoff-test.sh`, `relay-launch-block-detection.test.sh`, `handoff-delegation.test.sh` | the relay's own behaviour, the seed's content, the launch directory, and that a blocked launch is detected | always on | five `ci-local.sh` steps | each asserts one refusal or one seed invariant |
| `supervision-channels.test.sh` | that the four monitoring channels are read in order | always on | `ci-local.sh` step *Supervision channels matrix* | health first; the registry is not liveness |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `successor` | shares a record, and defers to | The six-element quality bar the handoff body must clear — assigned task and desired outcome, current context, open questions and risks, authorization scope, suggested skills, standing invariants — **is `successor`'s, stated once there** | Read it before writing a handoff of any size. One successor is this skill; a fleet is that one (ADR-0059) |
| `successor-manager` | invokes | Phase 3's verdict about a live session | The registry is not liveness (M-0014) |
| `endless` | invoked by | The Relay continuation, on the burn or context predicate | This session stops only after confirming the branch is pushed |
| `off-topic` | shares a record | An open checkpoint under `.claude/docs/off-topic/` is in-flight state and must be named in the handoff | Otherwise the successor inherits the branch **without the debt attached to it** |
| `roadmap` | shares a record | Every roadmap id in a handoff is written qualified | ADR-0050; the relay refuses an unqualified id outside a fenced block |
| `revive` | complements | A fleet that must survive a shutdown writes a revival manifest rather than a handoff | Different failure mode, same destination |

### Additional Relevant Information

- **Ownership:** the document format is owned here; the six-element bar by `successor`; the launch
  and its refusals by `.claude/scripts/odin-relay.sh`.
- **Related documentation:** `skills/handoff/UPSTREAM.md` in this mirror; ADR-0077 (write, launch,
  monitor); ADR-0059 (one successor vs a fleet); ADR-0038 and ADR-0036 (the agent cannot clear its
  own context); ADR-0050 (qualified roadmap ids); ADR-0056 (suggested skills must name skills);
  `.claude/docs/odin-memory-standards.md` (the `mem_class` vocabulary — read the current value from
  `.claude/.runtime/active-mem-class` rather than guessing).
- **Known limitations / technical debt:**
  - **The hop count is unenforceable.** Nothing can force a successor to declare `hop: N`, and an
    omitted one silently restarts the chain. The ceiling is real only while every link cooperates.
  - Handoffs live under gitignored `.claude/.runtime/`, so a chain crossing worktrees cannot read its
    predecessors' documents at all — which is why a reader resolves by arithmetic rather than path.
  - The skill cannot complete its own stated purpose end to end: clearing the session is the user's
    keystroke.
- **Observability:** `claude agents --json`, `claude logs <id>`, `git ls-remote --heads origin
  '<class>/*'` — none of them first; `fleet-health.sh` is.
- **Security / compliance:** handoffs are gitignored and never pushed. The skill instructs redaction
  of anything sensitive and forbids pasting raw tool output.
- **Versioning:** unversioned; upstream divergence pinned by sha in `UPSTREAM.md`.

---

## Skill: impeccable

**Identifier:** `impeccable`
**Repository:** `.claude/skills/impeccable/` (harness) · `skills/impeccable/` (this mirror)
**Status:** `active` · declared `version: 3.7.1`, `license: Apache 2.0`, `user-invocable: true`
**Class:** `forked` — upstream `pbakaus/impeccable`, Apache-2.0, upstream HEAD last audited `7b646ba` (2026-08-14)

---

### Description

Designs and iterates production-grade frontend interfaces: real working code, committed design
choices, exceptional craft. It is by a wide margin the **largest** skill in the corpus — 35
scripts and 28 reference documents, measured at this sha — and the only member that registers a `PostToolUse` hook of its
own.

Covers websites, landing pages, dashboards, product UI, app shells, components, forms, settings,
onboarding and empty states, across UX review, visual hierarchy, information architecture, cognitive
load, accessibility, performance, responsive behaviour, theming, typography, spacing, layout, colour,
motion, micro-interactions, UX copy, error states, i18n and design systems.

**Forked from `pbakaus/impeccable`.** The Apache-2.0 §4(b) modification statement is in the mirror's
`UPSTREAM.md`. The recorded local changes: hook-local cache and config files are anchored to the
project directory rather than raw `process.cwd()`; four reference documents were added that upstream
has no equivalent of; and the harness integration upstream does not carry.

### Purpose and Use Cases

Invoked by sub-command — `craft`, `shape`, `audit`, `critique`, `animate`, `bolder`, `colorize`,
`delight`, `layout`, `overdrive`, `quieter`, `typeset`, `adapt`, `clarify`, `distill`, `harden`,
`onboard`, `optimize`, `polish`, `init`, `document`, `extract`, `live` — each with a required
reference document. **Not for backend-only or non-UI tasks.**

**A five-step setup runs before any design work, and steps 2 and 4 are marked non-optional:**

1. `node scripts/context.mjs` once per session (`--target <path>` inside a monorepo). It prints the
   project's `PRODUCT.md` (and `DESIGN.md` when present), or says it is missing. **`NO_PRODUCT_MD`
   stops the work** until `reference/init.md` has been followed.
2. A sub-command requires reading `reference/<command>.md`. *Without it you will skip steps the user
   expects.*
3. Read at least one project file — CSS, tokens, theme, a representative component.
4. Read the matching **register** reference: `reference/brand.md` when design *is* the product
   (marketing, landing, campaign, long-form, portfolio) or `reference/product.md` when design
   *serves* the product (app UI, admin, dashboard, tool). *Skipping this produces generic output.*
5. For a genuinely new project with no committed brand colours, `node scripts/palette.mjs` supplies
   a brand seed; otherwise identity preservation wins.

The design guidance is prescriptive and specific rather than general — contrast floors (4.5:1 body,
3:1 large, and the same 4.5:1 for placeholders), a 65–75ch measure, a display-heading ceiling of
6rem and a letter-spacing floor of −0.04em, `text-wrap: balance` on h1–h3, a semantic z-index scale
instead of 999, exponential ease-out with no bounce, a mandatory `prefers-reduced-motion`
alternative, and a named anti-pattern: **the cream/sand/beige body background as "the saturated AI
default of 2026"**, with the token names that are tells in themselves.

### Scripts

35 files under `.claude/skills/impeccable/scripts/`. The ones an operator needs by name:

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `context.mjs` | `scripts/context.mjs` | Prints `PRODUCT.md`/`DESIGN.md`, or `NO_PRODUCT_MD`; may emit an `UPDATE_AVAILABLE` directive that never blocks the task | setup step 1, once per session | `--target <path>` |
| `hook.mjs` | `scripts/hook.mjs` | The `PostToolUse` entry point — a thin stdin/stdout adapter that reads the hook event, runs the design detector against the touched file, and emits findings via `hookSpecificOutput.additionalContext` | registered in `.claude/settings.json` under `PostToolUse` for `Write\|Edit\|NotebookEdit` | the hook event on stdin; `envProjectDir` |
| `hook-lib.mjs` | `scripts/hook-lib.mjs` | Where the hook's logic actually lives, so it is unit-testable without a subprocess | imported by `hook.mjs` | — |
| `hook-lib.test.mjs` | `scripts/hook-lib.test.mjs` | The hook's tests, including cwd anchoring | `ci-local.sh` step *Impeccable hook cwd anchoring* — `node --test` | — |
| `hook-before-edit.mjs`, `hook-admin.mjs` | `scripts/` | Pre-edit variant and hook administration | invoked by the skill body | — |
| `detect.mjs`, `detect-csp.mjs`, `context-signals.mjs` | `scripts/` | The design detector and its signals | called by the hook | the touched file |
| `palette.mjs` | `scripts/palette.mjs` | Brand seed colour and composition guidance, OKLCH | setup step 5, new projects only | — |
| `critique-storage.mjs`, `pin.mjs` | `scripts/` | Persisting critiques and pinned targets | invoked by the sub-commands | — |
| `live*.mjs` (≈18 files) | `scripts/live*.mjs` | The live browser-iteration surface — server, session, DOM, inject, insert, poll, resume, status, target, wrap, accept, complete, manual-edit evidence and commit/discard | `live` sub-command | a running browser; `reference/live.md` |
| `modern-screenshot.umd.js` | `scripts/` | Bundled screenshot dependency | called by the live surface | — |
| `command-metadata.json` | `scripts/` | Sub-command metadata | read by the skill | — |

**The hook's contract is stated in its own header and is worth quoting:** *never break a turn, always
exit 0.* Clean files emit a small acknowledgement unless quiet mode is enabled.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `impeccable/scripts/hook.mjs` | `PostToolUse`, matcher `Write\|Edit\|NotebookEdit` | any file write | Runs the design detector against the touched file and emits a system reminder through `hookSpecificOutput.additionalContext` when findings exist. Writes an audit log. **Always exits 0** | Node; the detector; `envProjectDir` |
| `odin-surface-router.sh` | `PreToolUse` on writes | the surface being written is frontend | Names this skill for the file, with no prompt involved | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches design / UI / polish intent | Names this skill in the routing hint | none |

This is the **only** member skill that owns a registered hook file. Every other hook in the corpus is
harness machinery that points at skills.

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `NO_PRODUCT_MD` | whether design work may start | **stops** the work | setup step 1 | `context.mjs` cannot find a `PRODUCT.md`; the repair is `reference/init.md` |
| `node --test scripts/hook-lib.test.mjs` | that the hook anchors its cache and config to the project directory rather than `process.cwd()` | always on | `ci-local.sh` step *Impeccable hook cwd anchoring* | the fork's own recorded divergence from upstream |
| the hook's quiet mode | whether clean files emit an acknowledgement | acknowledgement on | per-invocation configuration | `hook-lib.mjs` |
| `UPDATE_AVAILABLE` | whether the user is asked about updating | asks once, then continues | printed by `context.mjs` | **never blocks the current task** |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `agent-browser` | invokes | The `live` sub-command drives a real page while critiquing it | Degrades to static critique when the CLI is absent |
| `frontend-design`, `interface-design`, `ui-ux-pro-max`, `frontend-design-direction` | complements | Neighbouring design skills in the routing map; `impeccable` is also the PostToolUse design check | Routing neighbours rather than callers |
| `accessibility` | complements | Contrast and reduced-motion floors overlap with WCAG work | This skill states the floors inline; `accessibility` owns the standard |
| `motion-foundations` and the motion family | complements | Motion guidance here is prescriptive; the motion skills own tokens and springs | Cited in the routing map |
| `teach` | **deprecated alias** | `teach` is a deprecated alias for `init`: if a user types it, load `reference/init.md` and proceed as if they ran `init` | The one deprecation in the corpus, and it is an alias inside an active skill, not a deprecated skill |

### Additional Relevant Information

- **Ownership:** held as a fork by `odin-skill-manager`; the registered hook entry in
  `.claude/settings.json` is harness configuration.
- **Related documentation:** 28 files under `.claude/skills/impeccable/reference/` — one per
  sub-command, plus `brand.md`, `product.md`, `hooks.md`, `interaction-design.md`, `codex.md`;
  `skills/impeccable/UPSTREAM.md` in this mirror.
- **Known limitations / technical debt:**
  - **Surface area.** 35 scripts and 28 references make this the hardest member to change
    safely, and the only one whose failure can add noise to every write in a session.
  - The hook's "never break a turn, always exit 0" contract means a broken detector fails **silently**
    — findings simply stop appearing.
  - `allowed-tools` permits `Bash(npx impeccable *)`, so the skill can reach a published package
    distinct from the vendored copy.
- **Observability:** the hook's audit log (`writeAuditLog`); the system reminder emitted into the
  turn; `hook-admin.mjs`.
- **Security / compliance:** Apache-2.0 §4(b) statement and `LICENSE` beside the skill in this
  mirror. The `live` surface runs a local server and drives a browser; treat it as a development-only
  capability.
- **Versioning:** declares `version: 3.7.1` — the only member with a patch-level version, and the one
  whose upstream releases most obviously matter.

---

## Skill: improve

**Identifier:** `improve`
**Repository:** `.claude/skills/improve/` (harness) · `skills/improve/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

**The rung the ladder does not have.** This harness turns failures into enforcement in three rungs,
all owned elsewhere; this skill takes the fourth — a **friction that recurs and that no script can
decide.** A body that routes badly, a reference nobody reads, a procedure with a step everybody
skips, a boundary table that omits the skill people actually reach for.

An improvement here is **a change declared before it is made and reversible after.**

### Purpose and Use Cases

Fires on a recurring friction in a skill, or when a skill change must declare its reason, its
falsifier, and what happens if it reddens a gate.

**The handover test runs before anything else**, and it is quoted from `mistake-to-gate` §2 in that
skill's own words rather than paraphrased:

> **Is there a predicate over repository state that is true exactly when the friction is present?**

**Yes** → it is a gate. Invoke `mistake-to-gate` and stop — one sentence, no analysis, no partial
work here first. **No** → it is this skill's. *The question is quoted rather than paraphrased on
purpose: two bodies that paraphrase a shared border drift into disagreeing about it, and nothing in
this harness detects two skills claiming one scenario.*

**The trigger is recurrence, read at run time.** One annoyance is a preference; recurrence is
evidence. The register is read with `mistakes.py report`, and the body carries an explicit
prohibition: **never write a count from that register into prose** — a number in a body is wrong by
the next occurrence, *and this repository has shipped that exact defect more than once.* A key
already at the promotion threshold is not this skill's; that is `mistake-to-gate` §11's, both halves.

**Five fields.** Declared *before* the change: **reason, expected benefit, affected skills,
validation criteria.** Written into whatever closes it: **outcome.**

Two carry the weight. **Validation criteria must name a falsifier** — a command or observation that
would show the improvement did *not* work; if one cannot be stated, the change is a preference, so
say so and land it as one, or not at all. **Outcome is what makes the other four cost something**: an
improvement whose outcome is never recorded is indistinguishable from one that was never made.

The fields live in the commit body — plus an ADR when a contract moves, plus `CHANGELOG.md` when
something is removed. **There is no improvement ledger and there will not be one**: a second store of
recurring problems diverges from `MISTAKES.md` within a week and nothing says which is right.

### Scripts

This skill does not define any scripts.

It reads `mistake-to-gate`'s register through
`python3 .claude/skills/mistake-to-gate/scripts/mistakes.py report .`, optionally `--key <key>`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches recurring-friction / skill-change intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `skill-artifact-check.sh` | that the five-field record has ever been written | **exempt** — `artifact_status: never-run` | the exemption prints on every green run | the declared reason, verbatim: *the record is five fields in the commit body, which no glob can match, and the mechanism has never run: **0 of the 30 commits touching `.claude/skills` since `improve` landed at `b5aaf902`** (2026-08-26) carry them, measured 2026-09-01. Retro-fitting them would mean rewriting published history, and a record written now from memory is a function of who remembered. The obligation binds forward from here* |
| the falsifier requirement | whether a change may be called an improvement at all | required | inside the skill's validation-criteria field | a command or observation that would show it did not work; absent one, it is a preference |
| the revert-on-red rule | what happens when the change reddens a gate | **revert**, not patch forward | ADR-0109 | the gate's own verdict |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | **gated by, and reads** | The handover test is that skill's §2 question, quoted; the recurrence register is `MISTAKES.md` | **This skill reads that register and never writes it.** A key at threshold belongs to §11, not here |
| `oops` | reads from | `oops` is the front door for an incident and appends the counted row | Ordering: incident there, recurring friction here |
| `rules-distill` | hands off to | A pattern now in two or more skills, or a key at threshold, is a rule at a declared tier with a row in `DISTILLATIONS.md` | Not this skill's output |
| `skill-creator`, `writing-skills` | complements | Ordinary authoring or restructuring | This fires on recurring friction, **not on every edit** |
| `not-impressed` | explicitly excluded | A verdict on a diff delivered by a fresh context | Different question entirely |
| `systematic-debugging`, `diagnosing-bugs` | explicitly excluded | A friction is not a defect | *Diagnose first — you cannot improve a mechanism you have not identified* |

### Additional Relevant Information

- **Ownership:** the five fields are owned here; the recurrence register and the promotion ladder by
  `mistake-to-gate`; the rule tier by `rules-distill`.
- **Related documentation:** `references/change-record.md`, `references/revert-protocol.md`;
  ADR-0109 (declared before, reversible after; reverts on a red gate rather than patching forward).
- **Known limitations / technical debt:**
  - **Zero instances**, declared in frontmatter and quoted above: 0 of 30 eligible commits carry the
    five fields. Like `decision-mapping`, this is a routed, documented, unexercised mechanism, and the
    exemption is the honest record of that rather than a hidden gap.
  - The record lives in commit bodies, which **no glob can match**, so no gate can ever check content
    — only that the mechanism has or has not run, by declaration.
- **Observability:** `mistakes.py report .` for the trigger; the commit body for the record.
- **Security / compliance:** none specific.
- **Versioning:** unversioned.

---
