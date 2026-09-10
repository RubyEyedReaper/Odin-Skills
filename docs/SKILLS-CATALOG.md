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

## Skill: learn

**Identifier:** `learn`
**Repository:** `.claude/skills/learn/` (harness) · `skills/learn/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Decides what is worth remembering, how sure the record is, and when it has stopped being true. A
record earns its place by clearing a **capture bar**, states its confidence as a **rung on a ladder**
rather than a feeling, and carries **the command that would re-check it** — so a later session can
re-run the evidence instead of taking the record's word for it.

**This skill adds no store.** The memory tiers already exist and are described in
`.claude/docs/odin-memory-standards.md`; what this adds to a record in one of them is two fields and
a discipline for moving them.

### Purpose and Use Cases

Fires when durable knowledge is being built, validated or retired: whether a finding is worth a
record at all, how confident that record is, which command re-verifies it, and when its premise has
expired.

**The two fields:**

```yaml
confidence: gated
verified_by: bash .claude/tests/safety-guard.test.sh
verified_on: 2026-08-27
```

**`verified_by` names a command, not a person and not a date.** A date says somebody looked; a
command says what would have to be re-run to look again — *the difference between a record that can
be re-checked and one that can only be trusted.*

The always-loaded memory index has a **300-character-per-line ceiling** (`memory-index-check.sh`,
DEC-0053), because it is read whole into every session in its scope. The index line therefore carries
the short half only — `· gated 2026-08-27` — and the command lives on the record it links to, which
is unbounded on purpose. *The engine renders that marker; it is never hand-assembled.*

**Six outcomes, exactly one per pass:** `record`, `merge`, `promote`, `refresh` (the verifying
command still passes — the rung holds, the date moves), `demote`, `retire`. **`retire` deletes
knowledge on purpose:** a record kept past its truth is worse than no record, because it is read with
the same confidence as one that is still correct and nothing about it says otherwise.

**Five confidence tiers:** `asserted` → `observed` → `reproduced` → `gated` → `enforced`. Every rung
states the evidence that promotes into it and the trigger that demotes out of it — *a ladder whose
every rung is a feeling is a vocabulary, not a mechanism.* **The three rungs from `reproduced` up
require `verified_by`**; a record claiming one without a command is **malformed**, not merely
unverified.

**The capture bar is five refusal classes, evaluated highest-harm first, each with its own exit
code** so a caller can tell them apart — *five refusals sharing one non-zero code report "no" and
nothing else, and the remedy for a secret is not the remedy for a duplicate*: credential (exit 3,
matched by key name or value shape), personal data (4), chatter — true only inside the conversation
that produced it (5), duplicate (6, → `merge`), and **derivable** (7) — a restatement of a line the repository already
carries.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `capture_bar` | `.claude/skills/learn/scripts/capture_bar.py` | Evaluates a candidate against the five refusal classes and returns the class-specific exit code | invoked by the skill body; tested by the `ci-local.sh` step *Learn capture-bar tests* (`py_tests learn`) | the candidate record; exits 3/4/5/6 per class |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-ask-gate.sh` | `PreToolUse` on `AskUserQuestion` | an `AskUserQuestion` call is attempted | Names `learn` among the skills that resolve rather than ask | the posture ticket |
| `odin-completion-evidence.sh` | `Stop` | a turn ends claiming completion | Names `learn` among the records that count as evidence | — |
| `odin-safety-guard.sh` | `PreToolUse` | a write near memory or credential surfaces | Names `learn` in its guidance | — |
| `odin-task-gate.sh` | `PostToolUse` on `TaskCreate\|TaskUpdate`, `PreToolUse` on writes | task-list bookkeeping | Names `learn` in its guidance | — |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches durable-knowledge / staleness intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `memory-index-check.sh` | the 300-character-per-line ceiling on the always-loaded index | always on | `ci-local.sh` step *Memory-index ceiling*, `--machine` | DEC-0053; the index is read whole into every session in its scope |
| `memory-index.test.sh` | the ceiling's own matrix | always on | `ci-local.sh` step *Memory-index matrix* | — |
| `memory-store-declaration-check.sh` | that a record declares which store it lives in | always on | `ci-local.sh` steps *Store declaration (tree)* and *Store-declaration matrix* | the declaration's presence |
| `odin-memory-guard.sh` | cross-tier writes | **fail-closed** | `PreToolUse` on memory MCP tools; matrix at `claude-mem-guard.test.sh` | the active memory class (ADR-0025) |
| the `verified_by` requirement | whether a record may claim `reproduced` or higher | required from `reproduced` up | inside the skill's own tiers | a rung claimed without a command is **malformed** |
| `py_tests learn` | the capture bar's own correctness | always on | `ci-local.sh` step *Learn capture-bar tests* | the five classes and their distinct exit codes |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `.claude/docs/odin-memory-standards.md` + `odin-memory-guard.sh` | reads from | Where a record physically lives, and which class it belongs to | **Settled elsewhere; this skill is a reader of them** and adds no store |
| `architecture-decision-records` | complements | An ADR is a *decision* record; this is knowledge that was **discovered**, not chosen | Cited as a boundary |
| `domain-modeling` | complements | `CONTEXT.md` is the glossary — *a term is not a finding* | Cited as a boundary |
| `oops`, `mistake-to-gate` | complements | Those turn an incident into a check; this decides whether the **knowledge** is worth keeping | Different questions on one event |
| `rules-distill` | complements | A rule is always-on text; a record is recalled on demand | The tier distinction is the boundary |
| `leek` | complements | Hygiene failures in the environment, not questions about a record's truth | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the confidence ladder and capture bar are owned here; the tiers, classes and write
  guard by `.claude/docs/odin-memory-standards.md` and `odin-memory-guard.sh`.
- **Related documentation:** `references/capture-bar.md`, `references/confidence-tiers.md` (rung by
  rung, with the promotion evidence each demands and the mistake each invites),
  `references/staleness-pass.md`; ADR-0112; DEC-0053; ADR-0025.
- **Known limitations / technical debt:** the index ceiling means the *useful* half of a record —
  the verifying command — is never visible in the always-loaded index, so a stale record looks
  identical to a fresh one until its file is opened.
- **Observability:** `verified_by` re-run; `memory-index-check.sh --machine`.
- **Security / compliance:** the capture bar's first two refusal classes are credential and personal
  data, with distinct exit codes so the remedy is distinguishable. `odin-memory-guard.sh` is
  fail-closed.
- **Versioning:** unversioned.

---

## Skill: leek

**Identifier:** `leek`
**Repository:** `.claude/skills/leek/` (harness) · `skills/leek/` (this mirror)
**Status:** `active`
**Class:** `authored` · frontmatter declares `forks: context-budget, ecc-tools-cost-audit`

---

### Description

> "Leek", as in leak — the vegetable.

A diagnostic and hygiene pass over a Claude Code environment: what is being wasted, what is retained
past its scope, what is reachable from where it should not be, and what is still running after its
work ended.

**Leek diagnoses. Leek never remediates.** Its outputs are a report document, **one GitHub issue per
distinct concern**, and a hand-off to `mistake-to-gate` where a finding has a repo-state predicate.
It runs no cleanup, terminates no process, expires no memory and clears no cache. The reason is
ADR-0088 and it is worth stating in full: *the scanner's own evidence says the environment is in an
unexpected state, which is the worst possible moment to exercise judgment about what is safe to
destroy.*

### Purpose and Use Cases

Fires when: context fills too fast or a session feels "heavy"; burn or spend looks disproportionate;
a memory surfaced from another project or one that should have expired; caches, job workspaces,
transcripts or embeddings accumulate; a session went silent, a fleet reports `blocked`, or a process
will not stop; secrets may have reached a memory store, cache or config file; before adding agents,
skills or MCP servers ("is there room?"); "which skills have never been used?"; and periodically as
hygiene, before or after a campaign.

**Not for** fixing what it finds (open the issue, then plan that work like any other), choosing what
to build (`roadmap`), auditing a plan (`plan-adversary`), or diagnosing one concrete bug
(`systematic-debugging`).

**Everything in the body is triage of the scanner's output — do not hand-audit what it measures.**

**Eight families:** `context` (always-on rule bytes, oversized instruction files, bloated agent
descriptions, heavy bodies, byte-identical skill bodies, MCP over-subscription), `tokens` (oversized
transcripts, repeated identical tool output, retry loops, over-budget tool results), `memory`
(unscoped records, records relabelled across projects, duplicates, past-retention records, provenance
gaps, credential shapes, file-tier index drift), `cache`, `sessions` (daemon liveness via
`fleet-health.sh`, MCP servers with no live session in their ancestry, and long-lived processes split
by CPU fraction — *burning CPU is a runaway, near-idle is a memory hold*), `isolation`
(workspace-wide permission grants, memory files naming several projects, credential shapes in caches
every session can read), `state` (spent plans, runtime residue, expired posture tickets, abandoned
worktrees, a large uncommitted diff), and `components` (duplicate agent names, unbounded tool grants,
unregistered and missing hooks, hook hygiene, MCP filesystem breadth and inline credentials, settings
conflicts, never-invoked skills, stub skills).

**Exit 0 is a measured clean, not a silence.** An evidence channel that could not be read produces an
`evidence-unavailable` finding, so a blind channel exits 1. The *Evidence channels* block at the top
of every report is read **before** the findings — *"no findings" from an instrument that could not
look is the failure mode that let 76 of 77 open issues go uncaptured* (ADR-0069).

**Three things the scanner will not tell you**, stated in the skill rather than left for a reader to
discover: a hook-hygiene finding is a **shape, not a proven defect** (the checks read normalized
source, because a guard that *matches* `eval` in order to block it reads identically to one that runs
it — only the author can tell them apart); **the transcript window bounds every usage answer**, so
"never invoked" means "not in the retained transcripts" and a skill added last week looks identical
to one nobody has ever wanted; and **a credential-shape match is reported by
class, never by text** — the scanner prints the record id, the project and the match class, and does
not quote the match, *because a finding that quotes a secret has copied it into a report and then
into an issue.*

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `leek-scan.sh` | `.claude/skills/leek/scripts/leek-scan.sh` | The scanner. Runs every family, or a selection | run by hand, or as a hygiene pass; a full pass over a live host takes about **ten seconds** | `--json`, `--check <families>` (e.g. `memory,isolation`, `skills-unused`), `--min-severity high`. Exit `0` no findings, `1` findings, `2` usage error |
| `leek.py` | `scripts/leek.py` | The scan engine behind the shell entry point | called by `leek-scan.sh`; matrix at `.claude/tests/leek.test.sh` | — |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches leak / hygiene / "never used" intent | Names this skill in the routing hint | none |

The skill **audits** hooks as part of its `components` family; it registers none of its own.

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `leek.test.sh` | the scanner's own families and exit codes | always on | `ci-local.sh` step *Leek scanner matrix* | per-family assertions |
| `--min-severity` | which findings are reported | all severities | per-invocation | `critical`/`high` filtering |
| the `evidence-unavailable` finding | whether an unread channel may be reported as clean | **refuses** — a blind channel exits 1 | inside the scanner | ADR-0069 |
| the never-remediate rule | whether the skill may act on what it finds | **never**; not a posture, an absolute | ADR-0088 | no cleanup path exists in the scanner |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | hands off to | A finding with a repo-state predicate becomes a gate | The hand-off is the skill's only remediation path, and it is someone else's |
| `to-issues`, `triage` | hands off to | One GitHub issue per distinct concern | Never fixes; files |
| `tidy` | complements | `tidy` supplies a verdict per path on what may go; `leek` reports what is accumulating | **Neither deletes.** Two skills, both non-destructive, deliberately |
| `handoff`, `successor-manager` | shares a channel | The `sessions` family calls `fleet-health.sh` — the same first channel those skills read | The registry is not liveness |
| `context-budget`, `ecc-tools-cost-audit` | **forked from** | Declared in frontmatter as `forks:` — this skill absorbed both | Both still exist as separate vendored skills; this is the composed successor |
| `roadmap`, `plan-adversary`, `systematic-debugging` | explicitly excluded | Choosing work, auditing a plan, diagnosing one bug | Cited as boundaries |

### Additional Relevant Information

- **Ownership:** the eight families and the scanner are owned here; `fleet-health.sh` by the fleet
  tooling; the issues it files by whoever triages them.
- **Related documentation:** `references/burn-audit.md`, `references/context-inventory.md`;
  ADR-0088 (diagnoses, never remediates); ADR-0069 (an instrument that could not look).
- **Known limitations / technical debt:**
  - Every usage answer is **bounded by the transcript retention window**, and the report states the
    window it scanned. This is the single most misread output of the skill.
  - Hook-hygiene findings are shapes; a normalized-source check cannot distinguish a guard that
    blocks `eval` from one that runs it.
  - The `forks:` frontmatter names two skills this one absorbed, but both remain present in the
    harness as separate vendored skills, so a reader can still route to the superseded ones.
- **Observability:** `leek-scan.sh --json`; the *Evidence channels* block; exit codes 0/1/2.
- **Security / compliance:** the `memory` and `isolation` families exist to find credential shapes in
  shared stores and workspace-wide permission grants. Findings may themselves quote sensitive
  material, so a report is handled with the care its subject warrants.
- **Versioning:** unversioned.

---

## Skill: mistake-to-gate

**Identifier:** `mistake-to-gate`
**Repository:** `.claude/skills/mistake-to-gate/` (harness) · `skills/mistake-to-gate/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Turns one concrete incident into a check that runs on every push, plus the matrix that proves the
check would have caught it. **A rule nobody checks is a rule that is wrong by the second change.**

**The output is three things, and the work is not finished until all three exist:** a checker that
exits non-zero on the mistake; a matrix asserting **exit codes** — a BLOCK case per real mistake and
ALLOW cases for the near misses; and a line in the repository's single gate list.

It also owns the **mistake log engine**, `scripts/mistakes.py`, which counts recurrence by
failure-mode key and tells the repository when a mistake has happened often enough to stop being a
mistake (ADR-0057). `oops` appends to the log; §11 is what happens when a key reaches the threshold.

### Purpose and Use Cases

Fires whether or not a check was requested: something was edited, cited or named wrongly and a human
caught it; a convention lives in prose with no enforcement; a review or postmortem produced a "we
should always…"; a guard was found to pass when it should have failed; or **a failure-mode key
reached the promotion threshold** — `mistakes-check.sh` fails with "promotion due", or `oops`
announced the promotion band. *At that point the incident is not a mistake any more, it is a missing
rule.*

**The procedure's early steps are where gates go wrong, and each is a rule with a stated failure:**

1. **Name the incident with its artifact.** "Links were wrong" is not an incident;
   "`0027-plan-depth-standard.md` was linked from three files; the file on disk is
   `0027-skill-utilization-and-plan-depth.md`" is. The artifact becomes the first BLOCK case — *a
   gate built from a remembered category tends to check the category you imagined rather than the one
   that happened.*
2. **Decide whether it is mechanically checkable**: is there a predicate over repository state true
   exactly when the mistake is present? Checkable — a reference resolves, a count matches, a
   generated file matches its source, an id is namespaced, a required section exists. Not checkable —
   "the plan was shallow", "this name is confusing", "the abstraction is wrong". *A gate encoding
   taste produces false positives, and a gate people disagree with gets disabled, taking its true
   positives with it.*
3. **Key the check on the consumer, not on a correlate.** To check that a cited document exists,
   resolve the citation to a **file**; do not check that its number appears in an index. *A sweep
   keyed on something that merely correlates stops asserting the moment the correlation drifts —
   silently, because it still passes.*
4. **Scope it to what this repository owns.** Where a workspace holds nested repositories, each keeps
   its own numbering and conventions; checking a subtree's ids against the parent's set *is not
   thoroughness, it is the exact confusion the gate exists to prevent.* State the boundary in a
   comment so the next reader does not "improve" the gate by widening it.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `mistakes.py` | `.claude/skills/mistake-to-gate/scripts/mistakes.py` | The mistake-log engine: `append` (returns the M-id), `report` (recurrence by failure-mode key), and the promotion-threshold arithmetic (ADR-0057) | invoked by `oops`, `caveat`, `improve` and this skill; tested by `ci-local.sh` step *Mistake-log engine tests* (`py_tests mistake-to-gate`) | `append . --key '<class>/<predicate-slug>' --context --artifact --fix`; `report .` / `report . --key <key>` |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

The harness gates it owns: `.claude/scripts/mistakes-check.sh`,
`.claude/scripts/mistakes-monotonic-check.sh`, `.claude/scripts/mistake-citations-check.sh`, and
`.claude/scripts/doc-reference-check.sh`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-completion-evidence.sh` | `Stop` | a turn ends claiming completion | Names `mistake-to-gate` among the records that count as evidence | the log |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "add a check" / "can't regress" / "enforce this always" intent | Names this skill in the routing hint | none |

### Gates

This skill owns more of the repository's gate surface than any other. The ones it is the direct owner
of:

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `mistakes-check.sh` | the log's own shape, the `CAVEAT.md` conversion fields, the `MUTATIONS.md` disposition refusal, **and** the "promotion due" signal | always on | `ci-local.sh` step *Mistake-log gate* **and** `PRE_PUSH_GATES` (declared 214ms) | required fields per entry; refuses a caveat with no `Recurs when:`/`Safeguard:`; refuses a mutation whose `Actual observed impact:` is `pending` while its `Disposition:` claims anything but `needs review`; fails when a key reaches the promotion threshold |
| `mistakes-monotonic-check.sh` | that the log only grows | always on | `ci-local.sh` step *Mistake-monotonicity gate* **and** `PRE_PUSH_GATES` (2315ms) | monotonicity over M-ids |
| `mistake-citations-check.sh` | that every citation in the log resolves | always on | `ci-local.sh` step *Mistake-citation gate* **and** `PRE_PUSH_GATES` (2618ms) | resolve each citation to a **file** — the consumer, not a correlate |
| `mistakes-dup-order.test.sh`, `mistakes-log.test.sh`, `mistake-promotion-provenance.test.sh` | duplicate ordering, log format, and that a promotion cites its evidence | always on | three `ci-local.sh` steps | — |
| `doc-reference-check.sh` | that every path a document cites exists | always on | `ci-local.sh` step *Doc reference resolution*, clean-clone | the citation resolves to a file; **fails on a reserved-but-unminted `ADR-` token even inside a sentence saying it stays unminted** |
| the promotion threshold | when a key stops being a mistake and becomes a rule | fires at the fourth occurrence | §11 | recurrence count per failure-mode key (ADR-0057) |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `oops` | receives from | `oops` is the incident front door and appends the counted row; a repo-state predicate is handed here | ADR-0057. **Ordering: root-cause there, gate here** |
| `caveat` | shares a record | `mistakes-check.sh` enforces `CAVEAT.md`'s conversion fields; a caveat entry carries **no** failure-mode key | DEC-0092 — a second file able to hold a key would make every count an undercount, silently |
| `mutations` | shares a record | The same gate refuses a `MUTATIONS.md` disposition claimed over an unobserved effect | ADR-0146 |
| `rules-distill` | hands off to, and is called by | §11 promotion writes the rule half through the forked `rules-distill`; and an unmechanisable finding is routed there instead of a gate | **Both halves of a promotion: the check here, the rule text there** |
| `improve` | read by | `improve` reads the recurrence register through `mistakes.py report` and **never writes it** | A key at threshold is §11's, not `improve`'s |
| `automate` | receives from | `automate`'s `gate` verdict hands over here | A gateable predicate is never an automation decision |
| `leek` | receives from | A leek finding with a repo-state predicate becomes a gate | Leek's only remediation path |

### Additional Relevant Information

- **Ownership:** `MISTAKES.md`, the log engine, and the four checker scripts above.
- **Related documentation:** ADR-0057 (incident → guard, and the promotion ladder); DEC-0092 (why
  caveats are uncounted); ADR-0146 (the mutation disposition refusal); `MISTAKES.md` itself.
- **Known limitations / technical debt:**
  - The promotion threshold is a count over **keys an author chose**. A mistake logged under two
    spellings of one key never reaches threshold, and nothing detects that.
  - `doc-reference-check.sh` failing on an unminted `ADR-` token *inside prose saying it is unminted*
    is a known sharp edge, and it constrains how plan documents may discuss future ADRs.
- **Observability:** `mistakes.py report .`; the four gates' own output; "promotion due".
- **Security / compliance:** the log is committed and quotes commands and paths from real incidents,
  several of them destructive; it is written to be read, not replayed.
- **Versioning:** unversioned.

---

## Skill: mutations

**Identifier:** `mutations`
**Repository:** `.claude/skills/mutations/` (harness) · `skills/mutations/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

A mutation is a change to expected behaviour, data, logic, workflow, configuration or output. **It is
worth exactly one thing: the observation that says what it actually did.**

The deliverable is an entry in `MUTATIONS.md` that stays **OPEN until that observation exists**, then
closes with a disposition and a citation of wherever the outcome was recorded. *A change whose effect
nobody looked at is otherwise indistinguishable from one that was checked and behaved* — and that
indistinguishability is the whole subject of the skill. `MU-0001` is that case, measured.

### Purpose and Use Cases

Fires on the change itself, whether or not anybody asked: a new implementation, a rule change, a
refactor, a config or dependency update, a schema or interface change — and equally a regression, a
side effect, a corrupted value, or a mutation someone else's change produced. Also on "did anyone
check what that did", "this used to work", "the output changed", "we changed the default", "is this
safe to accept", "should we revert this".

**Three gates fire it**, and the work in hand pauses until the mutation is assessed: **Mutation** (a
change affecting behaviour, data integrity, configuration, security, dependencies, interfaces or
outputs), **Oops** (a mutation produced an unexpected result), **Mistake** (a mutation stems from an
incorrect assumption or preventable process failure). The Oops and Mistake gates are **hand-offs, not
duplicates**: one event, two records, joined by a citation.

**Only the Mutation gate is mechanical, and the residue is stated rather than hidden** (ADR-0146). A
tool-level matcher over "edits that touch behaviour, config or interfaces" would fire on nearly every
edit in this repository, and *a detector with a ~100% hit rate carries no information.* Routing for
the other two is intent-level, in `odin-skill-gate.sh`.

**The cycle — pause, record, observe, dispose, continue:**

1. **Pause.** Do not finish the step that produced the mutation. *A prediction written after the
   result is known is not a prediction.*
2. **Name the change with its artifact.** "The behaviour changed" is not a mutation; "landing by
   rebase rewrites shas, so `merge-base --is-ancestor` reports a landed branch as unmerged" is.
3. **Write `Expected impact:` now, before observing anything.** This is the field the pair turns on,
   and **it is never edited afterwards** — a prediction revised once the answer is known destroys the
   only thing the ledger measures. *No gate can see that; it is held by the author, exactly as
   test-first-ness is.*
4. **Open with `Actual observed impact: pending` and `Disposition: needs review`.** Any other
   disposition at this point is refused, and correctly: *a verdict over an unobserved effect is a
   prediction wearing a verdict's label.*
5. **Observe** — run the command that would show the effect **on the surface it reaches**, the
   consumers listed in `Location:`, not the change itself. *An observation is a measurement with its
   command or artifact, never a reading of the diff.*

### Scripts

This skill does not define any scripts.

Its enforcement is `.claude/scripts/mistakes-check.sh`, owned by `mistake-to-gate`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "did anyone check what that did" / "the output changed" / behaviour-altering intent | Names this skill in the routing hint. **This is the routing for the Oops and Mistake gates, which are deliberately intent-level rather than tool-level** | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `mistakes-check.sh` (the mutation clause) | that a disposition is not claimed over an unobserved effect | always on | `ci-local.sh` step *Mistake-log gate* and `PRE_PUSH_GATES` | refuses an entry whose `Actual observed impact:` reads `pending` while `Disposition:` claims anything but `needs review`; refuses any line in `MUTATIONS.md` parsing as a **keyed occurrence**; refuses an entry missing a required field |
| the Oops and Mistake gates | whether those two fire mechanically | **deliberately not mechanical** | intent-level routing only | ADR-0146 — a matcher over behaviour-touching edits would fire on nearly every edit, and a ~100% hit rate carries no information |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `oops` | hands off to | The Oops gate records the occurrence and builds the guard while this records the mutation and its observation | **One event, two records, joined by a citation** |
| `mistake-to-gate` | is gated by | `mistakes-check.sh` enforces this ledger's fields and refusals | The gate is that skill's; the ledger is this one's |
| `caveat` | complements | A hazard met once versus a change whose effect is unobserved | Both refuse to let the work in hand finish first |
| `test-driven-development` | shares a discipline | The unedited `Expected impact:` is the same unenforceable property as test-first-ness | Named explicitly as such |

### Additional Relevant Information

- **Ownership:** `MUTATIONS.md` at the harness root; the gate is `mistake-to-gate`'s.
- **Related documentation:** ADR-0146 (the disposition refusal, and why two of three gates are not
  mechanical); `MUTATIONS.md` (the entry shape and `MU-0001`).
- **Known limitations / technical debt:** the two properties that matter most — that the prediction
  was written first and never revised — are **unenforceable by any predicate**, and the skill says
  so rather than implying coverage it does not have.
- **Observability:** `bash .claude/scripts/mistakes-check.sh`; the ledger's own `pending` entries are
  the open-work list.
- **Security / compliance:** the ledger records configuration and dependency changes, so it doubles
  as a change record for anything security-relevant.
- **Versioning:** unversioned.

---

## Skill: not-impressed

**Identifier:** `not-impressed`
**Repository:** `.claude/skills/not-impressed/` (harness) · `skills/not-impressed/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Owns exactly one verdict nothing else in this repository owns: **is this code overdeveloped?**

**The stance: assume the code is machine-generated and untrusted until validated.** Not malicious —
*plausible.* Machine-generated code fails in a specific direction: it is fluent, well-formatted,
reasonably named, and *too much*. It reaches for an abstraction before there are two callers, adds a
cache before there is a measurement, wraps a working call in an adapter, and pulls a dependency for
six lines of logic. **None of that looks like a bug. All of it is cost the reader pays forever.**

So the default verdict is neither "approve" nor "reject" — it is **trim**, until the code shows why
each part earns its place. A finding is not an opinion about taste: it names what to delete and
asserts, in a sentence, that deleting it preserves the original behaviour.

*Being unimpressed is the discipline. Fluent code reads as correct code, and the reviewer who is
impressed has stopped reviewing.*

### Purpose and Use Cases

Fires when reviewing code not written by hand — an agent-generated diff, a large pasted
implementation, a PR that looks finished.

The boundary table is unusually candid: **two of its rows are honest de-escalations.** If the diff is
small, human-written and uncontroversial, `code-reviewer` is the correct answer and this skill is
overkill — *which is the same mistake this skill exists to find, pointed at itself.*

**The procedure's first step is a dispatch, and it is not optional: never review inline.** Dispatch
the `adversarial-reviewer` agent, and give it the diff, the surrounding conventions to measure
against, and **nothing about why the code was written the way it was** — rationale is exactly what it
must not have. Two independent reasons, either sufficient (ADR-0101):

- *A reviewer sharing the author's context inherits the author's rationalisations.* The session that
  wrote the abstraction already believes the second caller is coming; a fresh context does not.
- *An invoked skill body never unwinds.* There is no call stack: invoking this skill inline from a
  build loop leaves its body plus three references resident for every remaining turn. A dispatched
  agent has a real context boundary and returns a real value.

### Scripts

This skill does not define any scripts.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "is this overdeveloped" / "too many abstractions" / review-what-I-did-not-write intent | Names this skill in the routing hint | none |

### Gates

This skill does not use any feature gates.

Its one hard rule — dispatch, never review inline — is a procedural constraint recorded as ADR-0101,
not a checked predicate. The corpus-wide gates in the overview still apply.

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `adversarial-reviewer` (agent, not a skill) | **dispatches — required** | The verdict must come from a context that did not write the code | ADR-0101. Reports; never edits |
| `consistency` | complements | *That is the precondition, not the review.* A diff reimplementing something the tree already has is overdevelopment this skill can only find **afterwards** | The cheaper question is the earlier one |
| `code-reviewer` (agent) | de-escalates to | The default reviewer for a routine change | Named explicitly as the correct answer when this skill is overkill |
| `security-reviewer` (agent) | cites | Security-only review carries its own triggers and remediation ladder | Cited, never restated |
| `plan-adversary` (agent) | complements | Critiquing a plan before code exists — no diff, so severity tables and style checks do not apply | Cited as a boundary |
| `refactor-cleaner` (agent) | hands off to | Removing dead code and duplication is **remediation**; this skill reports and never deletes | Ordering: verdict here, removal there |
| `impeccable` | complements | Design judgment, not structural judgment | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the overdevelopment catalog is owned here; the reviewer agent is
  `.claude/agents/adversarial-reviewer.md`.
- **Related documentation:** `references/review-rubric.md` (eleven verification bullets and, for
  each, *what evidence discharges it* — read first; a review that skipped a bullet is not finished),
  `references/overdevelopment-catalog.md` (six patterns, each with its recognition signal, the
  simpler-alternative recipe, and the behaviour-preservation sentence that must be written before the
  finding counts), `references/report-template.md` (five classes in a fixed order — copy it, do not
  improvise); ADR-0101.
- **Known limitations / technical debt:** the skill is expensive by design — a hostile prior plus a
  dispatched agent — and the body says so, naming its own overuse as an instance of the failure it
  hunts.
- **Observability:** the report, in the five fixed classes.
- **Security / compliance:** security review is explicitly routed elsewhere; a finding here is
  structural.
- **Versioning:** unversioned.

---

## Skill: odin-skill-manager

**Identifier:** `odin-skill-manager`
**Repository:** `.claude/skills/odin-skill-manager/` (harness) · `skills/odin-skill-manager/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

> *A skill's provenance is not a fact about its content. It is a fact about what may be done to it —
> and the only place that fact can live is somewhere a gate can read.*

Owns **where a skill came from, whether it may be overwritten, whether it is published, and how far
it has drifted.** Four other skills already own parts of skill work — `skill-creator` and
`writing-skills` write bodies, `skill-comply` checks whether a body's own instructions are followed,
`find-skills` and `skill-repo` find one, `consistency` asks whether a new thing duplicates an
existing one — and this owns what none of them does: **classification, mirror membership, packaging,
freshness, refresh, publication.**

**Creating a skill is therefore always two steps:** `skill-creator` writes it, and this registers it.
*A skill that exists but is not registered is invisible to the gate that decides what a refresh may
destroy.*

**This skill is the authority behind the document you are reading** — the membership predicate, the
four classes, and the per-skill class in every entry above come from it.

### Purpose and Use Cases

Fires when a skill enters, changes or leaves the harness: registering a new one, forking a vendored
one, refreshing vendored skills from upstream, publishing an owned skill to this mirror, retiring
one, or answering "is this skill ours".

**The four classes, derived on every run from four inputs** — the vend map, the `FROZEN` list, an
`UPSTREAM.md`, and mirror membership: `vendored` (third-party, unmodified — a refresh **may**
overwrite it, which is the point), `forked` (third-party, modified here — a refresh may not; data
loss with no upstream copy), `authored` (written here, no upstream exists), `frozen` (vendored, but
upstream is gone or unusable — there is nothing to refresh from).

**A fifth answer exists and is not a class: `undetermined`, rc 3.** Nothing claims the skill and
nothing declares it. *It is never folded into `authored`, because a skill installed by a provisioner
looks identical on disk to one written here, and guessing either way protects or exposes the wrong
thing.* `sp_protected_set` **refuses entirely** while any skill is undetermined — a partial protect
list is the shape that overwrites exactly the skill nobody could classify.

**Precedence, and the one line of it that matters: fork evidence outranks the vend map**, because a
forked skill is usually still in the map. `rules-distill` is vended from ECC *and* forked here.

**Five operations**, each with a runbook: a new skill (write → register → publish → route); forking a
vendored skill (decide fork vs freeze, write `UPSTREAM.md` **before** editing the body, verify the
class flipped, publish with the licence artefact); refreshing (**never hand-edit a vendored body** —
the next refresh reverts it, silently, and the finding closes while the cost comes back); publishing
to the mirror (a one-way publication; *a change made in the mirror is destroyed by the next sync*);
and retiring (deletion is not enough — remove it from the vend list **with the reason inline**, or
the next run re-vendors it; `grill-me` was re-created on every run for weeks after being retired).

### Scripts

This skill does not define scripts of its own; it owns a set of harness scripts and the mirror's own.

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `skill-provenance-check.sh` | `.claude/scripts/skill-provenance-check.sh` | Every skill has a class; `--membership` checks every owned skill is published | `ci-local.sh` step *Skill provenance* **and** `PRE_PUSH_GATES` (declared 386ms, worst of three offline) | `--membership` |
| `skill-provenance.sh` | `.claude/scripts/lib/skill-provenance.sh` | The library: `sp_class`, `sp_list`, `sp_protected_set`, `sp_mirror_members`, `sp_enumerate`. **One implementation, two calling conventions** — `_sp_class_var` answers through a variable because a command substitution per skill is a fork per skill, measured at 1.3s of a gate inside a 30-second budget | sourced by the gates | `sp_list <root>` → TSV `name class origin mirrored` |
| `skill-freshness.sh` | `.claude/scripts/skill-freshness.sh` | Did any upstream move, and by how much | run by hand | `--quick` (17 `ls-remote`), `--deep`, `--deep --only <name>` |
| `vendor-skills.sh` | `.claude/scripts/vendor-skills.sh` | The upstream map and the refresh | `--print-map` (TSV, no network); `--refresh` replaces vendored skills only | the vend list, with retirement reasons inline |
| `sync-from-odin.sh` | `projects/Odin-Skills/scripts/sync-from-odin.sh` | Mirror drift, and the one-way publication | `--check` in `ci-local.sh` (*Skill mirror drift*) and in `PRE_PUSH_GATES` as `mirror_drift --uninitialised-ok` (213ms) | `--check --odin <harness root>` |
| `validate-skills.sh` | `projects/Odin-Skills/scripts/validate-skills.sh` | This repository's own gate, including **check 6** — a fork must ship a licence artefact | run in the mirror | — |

**Exit codes are the interface.** `skill-freshness` separates **1** (a vendored skill is behind) from
**3** (an upstream could not be read) on purpose: *"it moved" and "nobody could tell" are different
sentences, and only one of them is a finding about a skill.*

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-provenance-guard.sh` | `PreToolUse` on `Write\|Edit\|NotebookEdit\|Bash` | a write targeting a skill body | Refuses a hand-edit of a body the provenance library says a refresh owns | `skill-provenance.sh`; matrix at `skill-provenance-guard.test.sh` |
| `odin-surface-router.sh` | `PreToolUse` on writes | the file being written is under `.claude/skills/` | Names this skill and the `skills` rule namespace for the surface | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches skill-lifecycle intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `skill-provenance-check.sh` | that every skill on disk has a class | always on | `ci-local.sh` **and** `PRE_PUSH_GATES` | the four-input derivation; `undetermined` is rc 3 |
| `skill-provenance-guard.test.sh` | that the hand-edit guard fires | always on | `ci-local.sh` **and** `PRE_PUSH_GATES` (930ms) | BLOCK/ALLOW matrix |
| `skill-provenance.test.sh` | the library's own predicate | always on | `ci-local.sh` step *Skill provenance matrix* | per-class cases |
| `mirror_drift` | that this mirror matches the harness | always on | `ci-local.sh` step *Skill mirror drift* **and** `PRE_PUSH_GATES` with `--uninitialised-ok` (caught `harness:RM-0458`) | file-by-file comparison |
| `skill-freshness.test.sh` | the freshness reporter | always on | `ci-local.sh` step *Skill freshness matrix* | exit-code separation of 1 and 3 |
| `vendor-refresh.test.sh` | that a refresh does not overwrite a protected skill | always on | `ci-local.sh` step *Vendor-refresh matrix* | the protect set, which **refuses** while any skill is undetermined |
| `skill-invocability-check.sh` | that a routed skill is actually invocable | always on | `ci-local.sh` step *Routed skills are invocable*, clean-clone | `disable-model-invocation` must be absent — **a refresh reintroduced it on four routed skills in one command** |
| `skill-routing-check.sh`, `skill-reachability-check.sh`, `skill-registry-coverage.sh` | that a skill something owns is a skill something names | always on | three `ci-local.sh` steps | *a skill nothing names is a skill nothing fires* |
| `validate-skills.sh` check 6 | that a published fork ships a licence artefact | always on, in the mirror | run in this repository | a `LICENSE`, or the literal declaration `no LICENSE file accompanied` plus a `NOTICE` |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `skill-creator`, `writing-skills` | **paired with** | They write the body; this registers it | **Ordering is mandatory and both steps are required.** An unregistered skill is invisible to the refresh guard |
| `skill-comply` | complements | Whether a body's own instructions are being followed | Different question about the same file |
| `consistency` | complements | Whether a new thing duplicates an existing one | Fires before authoring |
| `find-skills`, `skill-repo` | complements | Finding a skill that already does the thing | Discovery, not lifecycle |
| `rules-distill` | **is an instance of its own hard case** | Vended from ECC *and* forked here — the precedence rule exists because of it | Fork evidence outranks the vend map |
| every member of this catalog | classifies | The class in each entry above is `sp_class`'s answer | This skill is the source of the membership predicate |

### Additional Relevant Information

- **Ownership:** the provenance library, the four scripts, the mirror's publication runbook, and the
  `skills` rule namespace (`.claude/rules/skills/lifecycle.md`).
- **Related documentation:** `references/classification.md` (what each class licenses and how it is
  derived), `references/refresh-runbook.md`, `references/membership-runbook.md`,
  `references/fork-runbook.md`; `.claude/docs/skill-provenance.tsv` (declared rows, *and why most of
  them are debts*); `FORKS.md` at the harness root; `odin-skills:ADR-0003`.
- **Known limitations / technical debt:**
  - **Two mechanical edits are applied by `vend()` on every refresh** — the frontmatter `name:`
    rewrite and stripping `disable-model-invocation: true` — precisely so that nobody hand-edits a
    vendored body for those two reasons.
  - The red-flags table records a real regression: *"the refresh was clean, nothing broke" — run
    `skill-invocability-check.sh`; a refresh reintroduced `disable-model-invocation` on four routed
    skills in one command.*
  - **"No diff means up to date" is only true if the comparison used the upstream's own directory
    name.** Guessing by target name misses every renamed skill.
  - A declared row in `skill-provenance.tsv` is described by the skill itself as usually a **debt**,
    not a record — the derivation is preferred.
- **Observability:** `sp_list <root>`; `skill-freshness.sh --deep`; the gates' own output.
- **Security / compliance:** **publishing is a licensing act, not a copy.** `validate-skills.sh`
  check 6 refuses a fork with no licence artefact, and the fork runbook requires the upstream
  `LICENSE` beside the `UPSTREAM.md` — or, where upstream published none, the literal declaration
  plus a `NOTICE`.
- **Versioning:** unversioned; freshness is measured against upstream shas, never asserted by a
  document. *"The freshness doc says…" — a document cannot notice that upstream moved. Run `--deep`.*

---

## Skill: off-topic

**Identifier:** `off-topic`
**Repository:** `.claude/skills/off-topic/` (harness) · `skills/off-topic/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Owns **the work a mid-run task displaced.** A task introduced into a run in flight creates an
**obligation to return**, and that obligation is the only thing worth writing down — everything else
about the interrupted work is already recorded somewhere with an owner: the item, the plan, the
branch, the ledger. *A checkpoint that copies them becomes a second, staler opinion about facts it
does not own.*

So a checkpoint here is **a pointer plus a relation**: which work was displaced, what displaced it,
what condition means the displacement is over, and what to do first on returning. Nothing else.

**The honest limit is stated rather than implied away:** the return itself is held by the agent, and
*nothing can make a session resume*. What is mechanical is that an **owed** return cannot stay
invisible — the checkpoint is committed, so every checkout reaches the same verdict about it, and
`.claude/scripts/off-topic-check.sh` reports a return that has come due.

Declared a **rigid** skill: the trigger predicate, the schema and the refusals are not judgment
calls.

### Purpose and Use Cases

Fires on an interruption, a pivot, being sidetracked, parking work, or coming back to it — and on
"before I forget", "hold that thought", "where were we".

**Three conditions, all of which must hold:** work is in flight that a reader could not reconstruct
from the tree alone (a claimed roadmap item, an open plan, an unpushed branch, a part-done
integration); a new task arrives that is not that work, and finishing the in-flight work would not
finish it; and the new task **displaces rather than interleaves** — it needs an edit, a branch or a
plan of its own.

**The origin of the new task does not matter.** A defect the agent finds mid-run displaces exactly as
hard as one a human introduces.

**Explicitly not triggers:** a question (answering displaces nothing — *a question is not a task*); a
defect fixed in the same breath inside the same unit of work; one skill routing to another.

**Against `pause`.** `work-loop`'s `pause` outcome describes the event well, and this is still a
separate skill for two reasons: a `work-loop` ledger exists only where somebody opened a contract,
and displacement arrives most often in a session that never did; and *`pause` ends the loop, while a
displacement does not* — the interrupting task runs inside the same run and the return is owed while
the loop is still live. Where a loop *is* open, use both.

Checkpoints **stack by `parent` and close LIFO**.

### Scripts

This skill does not define any scripts.

Its gate is `.claude/scripts/off-topic-check.sh`, a harness script the body names as its enforcement.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches interruption / "hold that thought" / "where were we" intent | Names this skill in the routing hint. Its arming is separately asserted by `off-topic-skill-gate.test.sh` | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `off-topic-check.sh` | that an owed return cannot stay invisible | always on | `ci-local.sh` step *Off-topic checkpoints* | reports a return that has come due, from the **committed** checkpoint — so every checkout reaches the same verdict |
| `off-topic-check.test.sh` | the checker's own matrix | always on | `ci-local.sh` step *Off-topic check matrix*, `--timeout 180` | — |
| `off-topic-skill-gate.test.sh` | that the intent actually arms the routing | always on | `ci-local.sh` step *Off-topic skill-gate arm matrix*, `--timeout 60` | routing-surface coverage |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `work-loop` | complements | `pause` is the adjacent outcome | **This skill neither extends that vocabulary nor writes to that ledger.** They answer different questions — `pause` says this cycle stopped, a checkpoint says a return is owed |
| `handoff` | shares a record | A handoff written while a checkpoint is open **names it** | *That is the whole interaction.* Otherwise the successor inherits the branch without the debt |
| `out-of-scope` | complements | A `fix-now` verdict can **produce** a displacement, and then this skill fires **on its own predicate — never because that one asked it to** | The boundary is one word: **who brought the work.** New task → here; discovered defect → there |
| `endless` | complements | `endless`'s checkpoint is a decision point in a long run; this one is a **debt** | Same word, deliberately distinguished |
| `roadmap` | references | A checkpoint references an item and holds **no second opinion** about it | Item identity stays there |
| `tidy` | explicitly excluded | An open checkpoint is **not residue**; closing one is a return, never a sweep | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** checkpoints live under `.claude/docs/off-topic/` and are committed.
- **Related documentation:** `references/checkpoint-format.md`, `references/return-contract.md`;
  DEC-0108 (a committed checkpoint holding the displacement edge and the resume condition, never a
  copy of state another file owns).
- **Known limitations / technical debt:** the resume is unenforceable. The gate can report that a
  return is due; it cannot cause one.
- **Observability:** `bash .claude/scripts/off-topic-check.sh`; the committed checkpoint files.
- **Security / compliance:** checkpoints are committed, so they must not carry anything sensitive —
  they are pointers, which is also why.
- **Versioning:** unversioned.

---

## Skill: oops

**Identifier:** `oops`
**Repository:** `.claude/skills/oops/` (harness) · `skills/oops/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

The incident front door. **An incident is worth exactly one thing: the guard it buys.** Fixing the
symptom and moving on spends the incident and gets nothing back.

**The deliverable is a check a machine runs** — a test, an assertion, a lint or type rule, a hook, or
a CI gate. *Not a resolution, not a note, not a paragraph in a commit message. A rule nobody checks is
wrong by the second change.*

### Purpose and Use Cases

Fires on the incident itself, whether or not a fix or a check was requested: code did the wrong thing
or the right thing for the wrong reason; an assumption was held that was never verified (a file
exists, a field is non-null, an API returns in order, a value is fresh); validation was missing at a
boundary; an unsafe, destructive or irreversible action ran or nearly ran; a review or postmortem
produced a "we should always…"; a guard was found to pass when it should have failed.

**Not for a bug you have not diagnosed yet.** A failing test is a symptom — run
`systematic-debugging` / `diagnosing-bugs` first. *OOPS starts once the cause is known: you cannot
guard a mechanism you have not identified.*

**Step 1 — name the incident with its artifact**, then name the **failure mode in the vocabulary of
the check that will catch it**: "no input validation", "missing null check", "assumed the file
exists", "used a stale read", "unbounded retry", "no test for the empty case". *"Links were wrong" is
not an incident; "`getUser(id)` returned `undefined` for a deleted user and the caller dereferenced
`.email`" is.* The artifact becomes the first test case.

**Step 2 — root cause is the condition, not the symptom.** Ask what condition allowed this, then ask
it again of the answer, and stop when you reach something expressible as a predicate. **The test of a
real root cause: you can state the guard from it in one sentence.** If you cannot, you are still on
the symptom. The body's worked table includes the one this repository keeps re-learning: *a
destructive command ran → the command's target was inferred from ambient state, never named.*

**Step 3 — classify the guard, and this fork decides everything after it:** a predicate over
repository state → **CI gate**, handed to `mistake-to-gate`, *which owns that branch end to end — do
not rebuild it here*; untrusted data entering the system → **input guard** at the boundary function;
required state assumed to exist → **precondition**; a result used unchecked → **postcondition**; a
failure path nobody exercised → **error-path guard** at the call site; judgment → **not mechanically
checkable**, say so out loud and route to `rules-distill`.

**When the incident is outside the work in hand**, the guard still belongs here; what is decided
elsewhere is whether it lands in this run or is routed and left — `out-of-scope` scores that.

### Scripts

This skill does not define any scripts.

It appends to the log through `mistake-to-gate`'s engine:
`python3 .claude/skills/mistake-to-gate/scripts/mistakes.py append . --key '<class>/<predicate-slug>'
--context … --artifact … --fix …`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-safety-guard.sh` | `PreToolUse` on `Bash\|Edit\|Write\|NotebookEdit` | a destructive or ambiguous command | Blocks always-on; names `oops` in the guidance it prints, because a refused command is frequently an incident | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "that shouldn't have happened" / "add a guard" / "I assumed" intent | Names this skill in the routing hint. *An incident is exactly the moment nobody stops to pick a skill*, which the hook's own comment says | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `mistakes-check.sh` | that the appended row is well-formed, and the "promotion due" signal | always on | `ci-local.sh` and `PRE_PUSH_GATES` | owned by `mistake-to-gate`; this skill is a writer to it |
| the promotion band | when an incident stops being a mistake | fires at the fourth occurrence of a key | announced by `oops`, executed by `mistake-to-gate` §11 | recurrence count per failure-mode key (ADR-0057) |
| the diagnosis precondition | whether the skill may run at all | requires a known cause | procedural | *you cannot guard a mechanism you have not identified* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | **hands off to** | The CI-gate branch, end to end, plus the log engine this skill appends through | ADR-0057. **Do not rebuild that branch here** |
| `systematic-debugging`, `diagnosing-bugs` | **gated by** | The cause must be known first | Hard ordering: diagnose, then guard |
| `test-driven-development` | hands off to | Input guards, preconditions and postconditions are written test-first | Three of the six guard classes route here |
| `error-handling-patterns` | hands off to | The error-path guard class | Bounded retry, fallback, explicit surfaced error |
| `rules-distill` | hands off to | The not-mechanically-checkable class — *and the last row now terminates somewhere* | Produces a drafted rule rather than leaving judgment unowned |
| `caveat` | complements | A hazard may be met with nothing yet gone wrong; an incident already went wrong and is **counted** | Both can fire on one event; the key goes in `MISTAKES.md`, the condition in `CAVEAT.md` |
| `mutations` | complements | Its Oops gate hands over here for the occurrence and the guard | One event, two records, joined by a citation |
| `out-of-scope` | complements | Whether the guard lands in this run or is routed and left | A deferral it records names the item or issue the guard now waits on |
| `endless`, `gauntlet` | invoked by | Phase 8's second half — a loop that captures features and drops its own mistakes re-makes them on a schedule | Per iteration, per batch |

### Additional Relevant Information

- **Ownership:** the incident procedure and the guard classification are owned here; `MISTAKES.md`
  and the engine by `mistake-to-gate`.
- **Related documentation:** ADR-0057; `MISTAKES.md`; `.claude/rules/common/security.md` (the
  destructive-command class that produces many of these incidents).
- **Known limitations / technical debt:** the failure-mode key is chosen by the author, so two
  spellings of one class never reach the promotion threshold together — a limitation this skill
  shares with `mistake-to-gate` and which nothing detects.
- **Observability:** `mistakes.py report .`; the guard itself, once it exists.
- **Security / compliance:** many incidents recorded here are destructive-command near-misses, so
  entries quote commands that must not be replayed.
- **Versioning:** unversioned.

---

## Skill: out-of-scope

**Identifier:** `out-of-scope`
**Repository:** `.claude/skills/out-of-scope/` (harness) · `skills/out-of-scope/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Resolves a genuine contradiction between two contract items, neither of which is wrong:

- **CLAUDE.md item 8** — on audit, review or structural work, file one issue per distinct concern
  rather than fixing out-of-scope items in the same pass.
- **CLAUDE.md item 3** — never close a turn reporting in-scope work as deferred-by-choice.

Item 3 governs work *inside* the scope; item 8 governs work *outside* it. **Between them sits work
that is genuinely out of scope and whose deferral costs the next session more than fixing it costs
this one — and that case had no rule, so it was settled by whoever held the keyboard.**

This skill makes it decidable: the call is scored by the `decision-matrix` engine against **six
weighted dimensions**, the winner is taken, and a **deferral** is written into a committed store
carrying the spec that produced it. *That last part is half the value: a deferral today is invisible
tomorrow unless the reasoning travels with it.* The tracker is where this repository has watched
findings go to be re-discovered late — one burn-down found **31 of 43** examined issues already fixed
on `main`, each re-established from context by somebody who did not have it.

Declared a **rigid** skill: the trigger predicate, the six criteria, the tie-break and the refusals
are not judgment calls. *The scores are.*

### Purpose and Use Cases

Fires on a defect noticed in passing, a landmine the next session would trip over, "that's out of
scope but", "should we fix this now or file it", "is this worth fixing now" — and when a deferral
needs to be **auditable rather than remembered.**

**A near-tie defers**, and a deferral is either supported by its own score or names the bar that made
fixing unavailable (DEC-0112, DEC-0113; the whole resolution is ADR-0168).

**Against `off-topic`, the boundary is one word: who brought the work.**

| | `off-topic` | `out-of-scope` |
|---|---|---|
| Subject | A new task introduced into a run in flight | A defect discovered inside a run |
| Question | How does the displaced work get resumed | Should this be fixed now, or routed and left |
| Artifact | A checkpoint, deleted on return | A deferral record, **kept for the audit** |
| Nesting | Stacks by `parent`, closes LIFO | **Never nests** |

A `fix-now` verdict can *produce* a displacement, and then `off-topic` fires — but only on its own
predicate, unchanged. *A defect fixed in the same breath, inside the same unit of work, is explicitly
not an `off-topic` trigger, and this skill does not make it one.*

### Scripts

This skill does not define any scripts.

It supplies a spec to `decision-matrix`'s engine and reads the winner; **it never computes a score by
hand.** Its own gate is `.claude/scripts/out-of-scope-check.sh`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-safety-guard.sh` | `PreToolUse` | a command near a deferral record | Names `out-of-scope` in its guidance | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "file it or fix it" / "out of scope but" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `out-of-scope-check.sh` | that a deferral record is well-formed and carries the spec that produced it | always on | `ci-local.sh` step *Out-of-scope deferrals*, matrix `out-of-scope-check.test.sh` `--timeout 300` | the record schema; a deferral must be **supported by its own score** or name the bar that made fixing unavailable |
| the near-tie rule | what happens when the two options score within the noise | **defers** | inside the scoring spec | DEC-0113 |
| `decision-matrix`'s own refusals | whether the score may be computed at all | incomplete spec is refused | delegated wholly | a missing score is a question nobody answered |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `decision-matrix` | **invokes — required** | All the math: scoring, sensitivity, vetoes, the DEC record | **This skill supplies a spec and reads the winner; it never computes a score by hand** |
| `off-topic` | complements | Who brought the work | A `fix-now` verdict may produce a displacement; that skill then fires on its own predicate |
| `to-issues`, `triage` | hands off to | Turning the finding into a tracker row | Issue shape, labels and the triage state machine stay there |
| `roadmap` | references | Capturing the work as an item with acceptance criteria | A record here references an item and holds no second opinion |
| `oops`, `mistake-to-gate` | complements | The guard for an incident found out of scope still belongs there; this decides only whether it lands now | A deferral names the item or issue the guard waits on |
| `caveat`, `mutations` | complements | Neighbouring ledgers with their own contracts | Cited, never re-derived |
| `campaign`, `gauntlet` | complements | Whether a batch may close, and what re-arms it | Cited as boundaries |
| `superplan`, `writing-plans` | hands off to | Planning the fix once `fix-now` wins and it is big | The plan-depth bar applies |

### Additional Relevant Information

- **Ownership:** the six dimensions and the deferral record are owned here; the arithmetic by
  `decision-matrix`; the tracker row by `to-issues`.
- **Related documentation:** `references/record-schema.md`, `references/worked-example.md`;
  ADR-0168 (the full resolution), DEC-0112 (where the record lives), DEC-0113 (the six dimensions).
- **Known limitations / technical debt:** the dimensions are weighted, and the weights are a policy;
  re-running with different weights is the documented way to revisit a deferral, which means an old
  deferral's verdict is only as good as the weights of its day.
- **Observability:** `bash .claude/scripts/out-of-scope-check.sh`; the committed deferral records and
  their DEC specs.
- **Security / compliance:** none specific.
- **Versioning:** unversioned.

---

## Skill: projects

**Identifier:** `projects`
**Repository:** `.claude/skills/projects/` (harness) · `skills/projects/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

**The routing table** over a project subtree's lifecycle, plus the two things that had no owner: the
**project-switch ritual** and the **per-project artifact checklist**.

**There is no engine here, and no state anybody sets by hand.** A project's state — initialized,
active, dormant, completed — is *read from its tree*.

### Purpose and Use Cases

Fires when starting or switching to a project subtree, when a project's own README, changelog, ADR
set, decision ledger, roadmap or data-provenance manifest may be missing, or when deciding whether a
project is initialized, active, dormant or completed.

**The project-switch ritual runs on starting and on switching, before any other action.** The failure
it prevents is silent: *nothing errors when the previous project's scope is carried into a new one —
the work is simply aimed at the wrong target, and reads as correct all the way to the commit.* Each
step is an assertion about **this** project; state the answer, do not assume it carried over.

1. **Name the subtree** — `projects/<slug>/`, and whether it is a **nested repository of its own**;
   the harness enumerates such a project, skips it, and says so on every run. *Its git state is not
   the harness's git state.*
2. **Read the project's own goal and scope**, in its own words. *The previous project's goal is not
   evidence about this one.*
3. **Assert the memory namespace** — `task:<slug>`. Operational records are read-only context inside
   a project and are never merged into project memory.
4. **Assert the id sequences are the project's own.** Roadmap ids and decision ids are **per-file
   counters**, so the same number names different work in every project. Outside the project, cite
   them qualified: `<slug>:RM-0007`.
5. **Assert the project's own gate** — the command that is *this* project's CI — and **run it once
   before changing anything**, so a later red is attributable to your change.
6. **Walk the artifact checklist**, and read its warning about silence.

The red-flags table is the operational core: *"Same repo, I already know the setup" — a subtree is
not the harness.* *"The tests were passing earlier" — earlier, in a different project's gate.*
*"The guard found nothing, so it is clean" — or it is not configured.* *"This project has no roadmap,
so I'll just start" — a project with more than one unit of remaining work owes one; **absence is a
finding**.*

### Scripts

This skill does not define any scripts.

Its frontmatter declares `artifact: projects/*/README.md` — the per-project README is the artifact
whose existence `skill-artifact-check.sh` asserts.

### Hooks

`projects` is named by more hooks than any other member — six — because a project subtree changes
what several harness guards must do.

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-project-context.sh` | `PreToolUse` on `Read\|Write\|Edit\|NotebookEdit\|Bash\|Grep\|Glob` | any tool call touching a project path | Establishes which project subtree is in scope and surfaces its context | the project's own docs |
| `odin-project-doc-guard.sh` | `PreToolUse` on writes; also `--scan` | a write into a project subtree | Enforces that a project carries its own README, changelog, ADR set and ledger | in `PRE_PUSH_GATES` as `--scan` (4220ms; caught `harness:RM-0455`) |
| `odin-memory-guard.sh` | `PreToolUse` on memory MCP tools | a memory write | Enforces the `task:<slug>` namespace, fail-closed (ADR-0025) | the active memory class |
| `odin-hardcode-guard.sh` | `PreToolUse` on writes; also `--scan` | domain data appearing in source | Refuses hardcoded project vocabulary; needs a per-project manifest to say anything | `ci-local.sh` step *Domain data in source (tree)* |
| `odin-roadmap-gate.sh` | `UserPromptSubmit` | a prompt about what to work on | Routes to the **project's own** roadmap | the project's `roadmap.json` |
| `odin-plan-gate.sh`, `odin-safety-guard.sh` | `PreToolUse` | writes, and destructive commands | Both name `projects` in their guidance for subtree paths | — |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `odin-project-doc-guard.sh --scan` | that every project carries its own required documents | always on | `ci-local.sh` step *Project-doc routing (tree)* **and** `PRE_PUSH_GATES` (4220ms) | the artifact checklist, as a repository-state predicate |
| `project-doc-guard-test.sh` | the guard's own matrix | always on | `ci-local.sh` step *Project-doc guard matrix* | BLOCK/ALLOW cases |
| `project-context-test.sh` | that the slug resolution is correct | always on | `ci-local.sh` step *Project-context slug* | slug derivation |
| `nested-repo-sync.test.sh` | that a nested-repository project is enumerated, skipped, and **said so** | always on | `ci-local.sh` step *Nested-repo sync check matrix* | the enumeration's own output |
| `project-roadmap-scope-check.sh` | that a project's roadmap ids stay in the project's sequence | always on | `ci-local.sh` steps *Project roadmap scope* and its matrix | per-file counters; qualified citation outside the project |
| `memory-guard-test.sh`, `claude-mem-guard.test.sh` | the `task:<slug>` namespace guard | fail-closed | two `ci-local.sh` steps | ADR-0025 |
| `skill-artifact-check.sh` | that `projects/*/README.md` exists | always on | `ci-local.sh` step *Skill artifact (tree)* | the declared `artifact` glob |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `roadmap` | routes to | A project's remaining work is items in **that project's own** roadmap | **This skill never ranks or picks** |
| `codebase-onboarding`, `repo-scan` | routes to | How to read an unfamiliar codebase | This skill only says that phase comes first and names them |
| `superplan`, `blueprint` | routes to | Planning before source is edited | *Nothing here relaxes or restates the plan-depth bar* |
| `domain-modeling` | routes to | Terms live in the project's own `CONTEXT.md` | Written by that skill |
| `handoff` / `/relay`, `successor` | complements | A handoff is a session-level act; **a project switch inside one session is not a handoff** | Cited as a boundary |
| `endless` | complements | Continuation is about the loop, not about the project | Cited as a boundary |
| the project's own docs | defers to | *This skill describes the model; it never writes into anybody's project* | A hard constraint on its own scope |

### Additional Relevant Information

- **Ownership:** the ritual and the checklist are owned here; every phase it routes to is owned by
  the skill named in the row.
- **Related documentation:** `references/operating-model.md` (every lifecycle phase and its owner;
  the artifact checklist), `references/state-transitions.md` (the four states and the evidence each
  transition requires); ADR-0106; ADR-0025 (the memory class guard).
- **Known limitations / technical debt:**
  - `odin-hardcode-guard.sh` **needs a per-project manifest to say anything** — silence on a new
    project means it is unconfigured, not clean, which is exactly the red flag the skill names.
  - The skill deliberately writes nothing into a project, so every artifact it requires is created by
    somebody else; the guard can only report absence.
- **Observability:** `bash .claude/hooks/odin-project-doc-guard.sh --scan`;
  `bash .claude/hooks/odin-hardcode-guard.sh --scan`.
- **Security / compliance:** the memory-class guard is fail-closed, which is the boundary that keeps
  one project's records out of another's context.
- **Versioning:** unversioned.

---

## Skill: revive

**Identifier:** `revive`
**Repository:** `.claude/skills/revive/` (harness) · `skills/revive/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

**The fleet comes back on its own.** Owns one thing nothing else owns: *what restarts a fleet that
has stopped, and what proves it should be restarted at all.*

**The stance is a single sentence with the whole design in it: a schedule may not decide what to do;
it may only decide when to look.** The cadence is dumb — two crontab entries, always the same, gated
on nothing. Every decision lives in a committed manifest and in facts measured at the moment the tick
fires. That split is what makes the mechanism survive the two-day gap it exists for: *a handoff
written on Saturday and fired on Monday describes a fleet that has moved, and a status written into a
file reads identically whether it is current or six hours old.*

So the manifest stores **the assignment and a not-before instant, and never a status.**
`revival-manifest-check.sh` refuses `status`, `state` and `progress` **at any depth** rather than at
the top level — *because the field people actually add is a note inside a role row.*

### Purpose and Use Cases

Fires when a campaign must survive a shutdown, a weekly limit, or a turn that ends with work
remaining.

**Five preconditions, in order, and the order is the substance: each channel after the first cannot
report its own absence.**

1. **The bridge** — a session launched without it is unreachable, unlistable and unstoppable.
   Checked as pid **plus `procStart`** plus a control socket, *because a pid alone is reused within
   hours on a busy host and a liveness test that reads only the number passes forever.* (exit 4)
2. **The daemon**, via `fleet-health.sh`, whose exits 2 and 3 are forwarded unchanged. Without this,
   step 5 is meaningless: **a registry outlives the daemon that served it, and on 2026-08-19 five
   dead sessions rendered as ordinary for eight hours** (M-0014, ADR-0072).
3. **The not-before**, read from the manifest. A weekly limit, a maintenance window or a deliberate
   pause is a fact about the work, so it lives with the work.
4. **Open items**, from the `campaign` engine. *Its `undetermined` is forwarded, never collapsed into
   "nothing to do" — those are different sentences.*
5. **Absence**, from the daemon's roster — **never from the session's own `state`**: a wedged session
   reports `running`, and a dead one reports whatever the registry last knew.

**Only the coordinator is relaunched.** A cron job that also launched workers would be a second actor
provisioning worktrees and reserving identifiers for the same items — *the collision `successor`
Phase 1 exists to prevent, arriving from a new direction.* An absent worker is a **finding**,
reported for the coordinator to act on.

### Scripts

This skill does not define scripts of its own; it owns four harness scripts.

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `fleet-revive.sh` | `.claude/scripts/fleet-revive.sh` | The engine: evaluates the five preconditions and relaunches the coordinator, or refuses **naming which precondition failed** | fired by cron; runnable by hand | the revival manifest |
| `revival-cron.sh` | `.claude/scripts/revival-cron.sh` | The dumb cadence — two crontab entries, gated on nothing | cron | none |
| `revival-manifest-check.sh` | `.claude/scripts/revival-manifest-check.sh` | Refuses a manifest carrying `status`, `state` or `progress` at any depth | `ci-local.sh` step *Revival manifest* | the manifest |
| `fleet-heartbeat.sh` | `.claude/scripts/fleet-heartbeat.sh` | Liveness signal | called by the engine | — |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-role-claim.sh` | `SessionStart` | every session start | Claims the session's role; names `revive` because a revived coordinator must claim its role on start | the role register |
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write is attempted | Names `revive` among the skills whose documents satisfy or are exempt from the plan requirement | the plan directories |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches restart-the-fleet / survive-a-shutdown intent | Names this skill in the routing hint | none |

The **cron entries are not hooks** — they are host scheduling, outside the six registered events, and
the skill is explicit that they decide only *when to look*.

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `revival-manifest-check.sh` | that no status is stored in the manifest | always on | `ci-local.sh` step *Revival manifest* | refuses `status`/`state`/`progress` **at any depth** (ADR-0113 applied to the second file that could carry one) |
| `fleet-revive.test.sh` | the five preconditions and their exit codes | always on | `ci-local.sh` step *Fleet revival matrix*, `--timeout 600` | one case per precondition, plus the refusal messages |
| the five preconditions | whether a launch happens at all | **all five must hold** | evaluated at fire time, never at write time | exits: 4 bridge, 2/3 daemon (forwarded), 0 not-before / no open items / coordinator present |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `campaign` | reads from | Precondition 4 asks the campaign engine for open items | The manifest **references a campaign by slug and copies nothing from it**. `undetermined` is forwarded, never collapsed |
| `successor` | launches one instance of | This skill launches exactly **one** session — a campaign's coordinator — which then runs Phase 1 for its own workers | The six-element bar is cited, never restated |
| `successor-manager` | shares channels | Asks a narrower question — present or absent — of the same channels | The five verdicts stay there |
| `handoff` | generates | A handoff is generated **at fire time**, not written in advance | *A handoff written on Saturday and fired on Monday describes a fleet that has moved* |
| `gauntlet` | invoked by | The budget terminal state writes a revival manifest | Ordering: gauntlet stops, revive restarts |
| `status` | invoked by | A timed resume writes `not_before` into **this** manifest | There is no second not-before format |
| `endless`, `work-loop`, `tidy` | explicitly excluded | Continuation doctrine, one cycle's ledger, deleting residue | *This engine issues no delete verdicts, prunes nothing, and retires no row* |

### Additional Relevant Information

- **Ownership:** the manifest schema, the five preconditions and the cron shape.
- **Related documentation:** `references/revival-record.md`; ADR-0121 (the committed manifest, the
  not-before instant, the five preconditions, the handoff generated at fire time); ADR-0072 and
  M-0014 (the registry outlives the daemon); ADR-0113 (no stored status).
- **Known limitations / technical debt:** the mechanism depends on host cron and on the Remote
  Control bridge; where either is absent the fleet does not come back and the refusal names which
  precondition failed — visible only to whoever reads the cron output.
- **Observability:** `fleet-revive.sh`'s refusal messages, each naming its precondition; the
  committed manifest.
- **Security / compliance:** the manifest is committed and names branches and campaigns, no
  credentials. It launches sessions unattended, which is the highest-trust action in the fleet
  tooling — hence five preconditions rather than one.
- **Versioning:** unversioned.

---

## Skill: roadmap

**Identifier:** `roadmap`
**Repository:** `.claude/skills/roadmap/` (harness) · `skills/roadmap/` (this mirror)
**Status:** `active`
**Class:** `authored`
**Command form:** `/roadmap`

---

### Description

The standing inventory of everything a project still needs — features, pages, functions,
integrations, infra — plus the dependency graph between them. **`roadmap.json` is canonical;
`ROADMAP.md` and `graph.{dot,svg}` are generated.** A script computes the graph; **never compute
"what's next" yourself.**

It also **owns the hand-offs**: when to grill, when to score, when one item needs a multi-PR
blueprint, and how a wave of items gets executed. *Those are gates with observable predicates, not
suggestions.*

This is the skill CLAUDE.md names as the only sanctioned answer to "what should I work on next", and
the one whose canonical file is never hand-edited.

### Purpose and Use Cases

Fires on "what should I work on next", "start the next thing", a new feature/page/function/
integration being mentioned (**record it first**), project initialization, "what can run in
parallel", more than about 8 items competing for a slot, an item finishing, or nothing reconciled in
`RECONCILE_AFTER_DAYS` (7) days — *ask `due`, never restate it.*

**Not** for how to build one item (`superplan`; `blueprint` for multi-PR), phase narrative
(`PLAN.md`), or vocabulary (`CONTEXT.md`, owned by `domain-modeling`).

**Storage:** project at `<root>/docs/roadmap/roadmap.json`; harness at
`.claude/docs/roadmap/roadmap.json`.

**Never hand-edit `roadmap.json` or `ROADMAP.md` — hand edits are detected and fail `validate`.**
**`blocked` is not a status**; it is computed from unmet deps.

**Generated files self-heal.** `next`, `waves`, `prioritize` and `reconcile` re-render `ROADMAP.md`
and the graph whenever they no longer match, so a project never reads a stale rendering — including
after an out-of-band edit. `validate` still *reports* staleness rather than hiding it, because it is
the CI gate, and `--no-render` opts out for read-only checkouts. **Never quote `ROADMAP.md` back to
the user without having run one of the refreshing commands in the same turn.**

**The four gates**, each on an observable predicate:

| Gate | Fires when | Skill |
|---|---|---|
| **Sharpen** | acceptance is thin | `grilling` / `grill-with-docs` |
| **Score** | >8 items compete, or two look equally next | `decision-matrix` (`/decide`) |
| **Decompose** | one item exceeds one PR | `blueprint` |
| **Plan** | always, before source | `superplan` |

Gate 1's predicate is precise: fewer than 2 `acceptance` entries; acceptance containing an
unmeasurable word (*fast, better, nice, robust, seamless*); no `links.prd` on a product-facing item;
or the title being the only description. *An item that survives a grill with unchanged acceptance was
already sharp — that is a pass, not a wasted step. Planning an item whose acceptance nobody can test
is how a plan gets approved and then rebuilt.*

Gate 2's exported spec carries a `decisions_dir` naming the ledger that owns this roadmap, **so a
project's prioritisation never lands in the harness DEC sequence** (`harness:RM-0170`). Scores land
in `priority.score` with the `DEC-####` that produced them, so the ordering in `next` carries its own
audit trail.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `roadmap` | `.claude/skills/roadmap/scripts/roadmap.py` | The engine: `next`, `waves`, `add`, `set`, `prioritize`, `validate`, `render`, `reconcile`, `due`, `bootstrap`, `init` | `python3 -m scripts.roadmap <command>` from the skill directory; engine tests are the `ci-local.sh` step *Roadmap engine tests* | `--limit`, `--status`, `--deps`, `--acceptance`, `--evidence`, `--scope task:<slug>`, `--fail-on <kind>`, `--no-render` |
| `graph` | `scripts/graph.py` | The dependency graph and wave layering | called by `next`/`waves` | the item edges |
| `prioritize` | `scripts/prioritize.py` | RICE spec export and score write-back | `--export --out spec.json` / `--from result.json` | the `decisions_dir` naming the owning ledger |
| `reconcile` | `scripts/reconcile.py` | Drift report between the roadmap and reality | `reconcile [--fail-on <kind>]` | exit 1 on the named finding kind, for a CI gate |
| `render` | `scripts/render.py` | Regenerates `ROADMAP.md` and `graph.{dot,svg}` | called automatically by the self-healing commands | — |
| `schema` | `scripts/schema.py` | Item schema and validation | `validate` | exit 1 on error |
| `sweep` | `scripts/sweep.py` | The `bootstrap --surface-sweep` starter surfaces | `bootstrap --from INIT.md` | project docs |
| `docsurface` | `scripts/docsurface.py` | Documentation-surface derivation | `bootstrap` | — |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

Harness gates it owns: `roadmap-check.sh`, `roadmap-drift-check.sh`, `roadmap-issue-link-check.sh`,
`roadmap-regression-check.sh`, `roadmap-scope-test.sh`, `roadmap-command-doc-test.sh`,
`project-roadmap-scope-check.sh`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-roadmap-gate.sh` | `UserPromptSubmit` | a prompt about what to work on next | Emits the next unblocked items and the source file, and states when the last reconcile was | the roadmap's own engine; the **primary checkout**'s copy |
| `odin-project-context.sh` | `PreToolUse` on most tools | a project path is touched | Resolves which roadmap is in scope | the project slug |
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write is attempted | Names `roadmap` in the chain that satisfies it | — |
| `odin-compact-boundary.sh` | `PostToolUse` on `TaskUpdate` | a task completes | Names `roadmap` in the boundary note | a task list must exist |
| `odin-task-gate.sh` | `PreToolUse`/`PostToolUse` | task bookkeeping | Names `roadmap` in its guidance | — |
| `odin-unfinished-work.sh` | `Stop` | a turn ends with work outstanding | Names `roadmap` as where the remaining work is captured | — |
| `odin-safety-guard.sh` | `PreToolUse` | a write near `roadmap.json` | Names `roadmap` in its guidance; hand edits are refused by `validate` regardless | — |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `roadmap-check.sh` | schema, cycles, freshness, and hand edits | always on | `ci-local.sh` step *Roadmap validation*, clean-clone | `validate` — exit 1 on error; a hand edit is **detected** |
| `roadmap-drift-check.sh` | that the roadmap matches reality | always on | `ci-local.sh` step *Roadmap drift*, `--timeout 600`, plus *Roadmap drift matrix* | `reconcile --fail-on <kind>` |
| `roadmap-issue-link-check.sh` | that an item's issue links resolve | always on | `ci-local.sh` step *Roadmap issue links* **and** `PRE_PUSH_GATES` (`--links-only`, 66ms, ADR-0136) | link resolution only, in the pre-push half |
| `roadmap-regression-check.sh` | that a claim already made is not re-made | always on | `ci-local.sh` step *Roadmap claim regression*, clean-clone | prior claims vs the current tree |
| `roadmap-scope-test.sh`, `project-roadmap-scope-check.sh` | that ids stay in their own per-file sequence | always on | two `ci-local.sh` steps | the slug rule; qualified citation outside the project |
| `roadmap-command-doc-test.sh` | that the `/roadmap` command doc matches the engine | always on | `ci-local.sh` step *Roadmap command-doc gate* | command coverage |
| `doc-reference-roadmap-citation.test.sh` | that a roadmap citation in a document resolves | always on | `ci-local.sh` step *Roadmap citation matrix* | citation → item |
| `RECONCILE_AFTER_DAYS` | when a reconcile is overdue | **7** | `due` is **silent when not overdue**, so a caller needs no comparison | date arithmetic against the last reconcile |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `grilling` / `grill-with-docs` | invokes (Gate 1) | Acceptance is thin | Use `grill-with-docs` when the item introduces a noun not yet in `CONTEXT.md` — the interview then lands the glossary entry and any ADR as it goes |
| `decision-matrix` | invokes (Gate 2), bidirectionally | `prioritize --export` → score → `prioritize --from` | The DEC id lands on the item as `priority.dec`; re-run with different weights to revisit |
| `blueprint` | invokes (Gate 3) | One item exceeds one PR | Blueprint registers its tasks back as **roadmap children**, and the roadmap computes the waves so no wave number is ever stored (DEC-0001) |
| `superplan` | invokes (Gate 4) | **Always, before source** | No exceptions in the gate table |
| `out-of-scope` | receives from | Capturing a defect found mid-run is this skill's job; **whether capturing is the right answer at all** is that skill's | An item captured from a deferral is **named by the record that deferred it** |
| `endless`, `gauntlet` | invoked by | Phase 3 picks; the frontier reads | Never from `ROADMAP.md` prose |
| `campaign` | shares a record | Campaign items **are** roadmap items | The manifest references qualified ids and copies nothing |
| `projects` | routes from | A project's remaining work is in that project's own roadmap | Per-file counters; qualified ids outside |
| `domain-modeling` | explicitly excluded | Vocabulary lives in `CONTEXT.md` | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** `roadmap.json`, the engine, the four gates and seven checker scripts.
- **Related documentation:** `references/roadmap-schema.md` (field reference),
  `references/workflows.md` (entry chains and handoff text); ADR-0039 (the
  `roadmap` → `blueprint` → `superplan` chain); DEC-0001 (waves computed, never stored);
  `harness:RM-0170` (the `decisions_dir` in the exported spec).
- **Known limitations / technical debt:**
  - `odin-roadmap-gate.sh` reads the **primary checkout**'s roadmap, so a session working in a
    worktree can be shown a stale "next unblocked" list. The hint states when the last reconcile was,
    which is the only signal that this has happened.
  - `blocked` being computed rather than stored means a hard external blocker is not visible in the
    item's status at all — it lives in a `work-loop` ledger, and `gauntlet frontier` is what reports
    the two kinds apart.
- **Observability:** `next --limit 3`, `waves --limit 3`, `reconcile`, `due` (silent when not due),
  `validate`.
- **Security / compliance:** none specific; the roadmap is committed and public to anyone with the
  repository.
- **Versioning:** unversioned; the schema is validated rather than versioned.

---

## Skill: rules-distill

**Identifier:** `rules-distill`
**Repository:** `.claude/skills/rules-distill/` (harness) · `skills/rules-distill/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `affaan-m/ECC`; **no LICENSE file accompanied the vendored copy**, and the blanket ECC row in `FORKS.md` carries the provenance. Forked 2026-08-15 (`skills/mistake-system`, `harness:RM-0063`)

---

### Description

Scans installed skills and the repository's mistake logs, extracts principles that recur across them,
and distils them into rules — appending to existing rule files, revising outdated content, or
creating new ones. It applies the "deterministic collection + LLM judgment" principle: **scripts
collect facts exhaustively, then an LLM cross-reads the full context and produces verdicts.**

**Two evidence sources, two predicates, deliberately not merged.** A principle appearing in **2+
skills** answers *what is cross-cutting in the catalog*; a failure-mode key with **4+ recorded
occurrences** answers *what keeps breaking*. *Overloading one predicate onto the other would make a
four-occurrence incident invisible unless it also happened to appear in two skills.*

**This skill is the corpus's own hard case for provenance:** it is vended from ECC **and** forked
here, which is why `odin-skill-manager`'s precedence rule states that fork evidence outranks the vend
map. Its refresh protection is **derived from this mirror directory**, not from a hand-typed list —
*deleting the mirror re-exposes the fork.*

### Purpose and Use Cases

Fires on periodic rules maintenance (monthly, or after installing new skills); after a skill
stocktake reveals patterns that should be rules; on **promotion**, when a key in a `MISTAKES.md` has
reached the threshold and `mistake-to-gate` §11 needs the rule-text half; and as **the judgment
hatch** — `oops` §3 classified a condition as not mechanically checkable, *and that route used to end
nowhere; it ends here, and it ends with a drafted rule and a tier, not an intention.*

**Every rule carries its `tier`:** `scoped` (has `paths:` frontmatter, loads only when a session
touches a matching file) or `always-on` (no `paths:`, and therefore **costs context on every turn of
every session**). Choosing the tier is the consequential half of the output.

**Phase 1 fails closed.** Any of the three collection commands exiting non-zero stops the phase — *an
empty enumeration reported as a clean pass is the shape being refused.* Promotion evidence is read in
full (`--key K`): the `context` and `artifact` columns are the concrete evidence the draft rule must
be true of, and **a rule that does not cover all four occurrences is the wrong rule.**

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `scan-skills.sh` | `.claude/skills/rules-distill/scripts/scan-skills.sh` | Phase 1a — the skill inventory | invoked by the skill body | repository-relative paths only |
| `scan-rules.sh` | `.claude/skills/rules-distill/scripts/scan-rules.sh` | Phase 1b — the rules index, each rule with its `tier` | invoked by the skill body; matrix at `rules-distill-scan.test.sh` | `RULES_DIR` defaults to the repository's `.claude/rules`, **not `$HOME`** |
| `mistakes.py report` | `.claude/skills/mistake-to-gate/scripts/mistakes.py` | Phase 1c — promotion evidence, the second source | invoked by the skill body | `report .`, `report . --key K` |

**All paths are repository-relative.** Skills and rules are vendored into the repository (ADR-0001),
so nothing reads `$HOME` — *upstream's `~/.claude/...` commands resolved to nothing here, which is
why this skill sat unrunnable for 49 days.*

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-surface-router.sh` | `PreToolUse` on writes | the file being written is under `.claude/rules/` | Names this skill and the rule namespace for the surface | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches distillation / promotion intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `rules-distill-scan.test.sh` | the two scanners' output and their fail-closed behaviour | always on | `ci-local.sh` step *Rules-distill scan matrix* | non-zero from any collection command stops Phase 1 |
| `rule-citations.test.sh` | that every citation in a rule file resolves — path, line **and** anchor phrase | always on | `ci-local.sh` step *Rule-citation matrix* **and** `PRE_PUSH_GATES` (5819ms) | *a bare line number resolves to real, wrong text after a refresh; the anchor is what survives* |
| `rule-count-claims-check.sh` | that a stated rule count matches the corpus | always on | `ci-local.sh` steps *Rule count claims* and its matrix | the count is asserted in exactly one place |
| `context-budget.test.sh` | the always-on rule byte total | always on | `ci-local.sh` step *Context-budget matrix* | `ao_total_bytes` over `.claude/rules`; the figure lives in one gated block |
| `retry-bounds-check.sh` | a rule-derived predicate this skill's body names | always on | `ci-local.sh` | the retry-bound rule |
| the tier decision | whether a new rule costs context on every turn | **`scoped` unless argued otherwise** | `paths:` frontmatter | *a file without `paths:` is a permanent tax on every session* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `mistake-to-gate` | **paired with** | §11 promotion is two halves — the check there, the rule text here | Reads `mistakes.py report`; a key at band `promoted` is a candidate on the ≥4-occurrence predicate **independent of** how many skills mention it |
| `oops` | receives from | §3's judgment class — the not-mechanically-checkable route | *It used to end nowhere.* Now it ends with a drafted rule and a tier |
| `caveat` | receives from | A safeguard whose kind is `rule` | At a `paths:`-scoped tier |
| `improve` | complements | A pattern in 2+ skills is a rule, not an improvement | Ordering: `improve` hands over rather than writing rule text |
| `consistency` | complements | It records a difference; this distils a recurring principle into always-follow text | Different durability tiers |
| `odin-skill-manager` | classified by | The precedence rule exists because of this skill | Fork evidence outranks the vend map |

### Additional Relevant Information

- **Ownership:** the two scanners and the distillation procedure; the rule namespaces themselves are
  owned by `.claude/rules/README.md`.
- **Related documentation:** `.claude/skills/rules-distill/UPSTREAM.md` **and** the mirror copy (one
  of only two forks carrying it in both places); `.claude/rules/README.md` (tiers and namespaces);
  ADR-0001 (skills and rules are vendored into the repository); ADR-0067 and DEC-0008 (a pass leaves
  committed evidence — **upstream stored `results.json` outside the tree**); the 2026-08-15
  mistake-pipeline audit, F9–F16.
- **Known limitations / technical debt:**
  - The fork exists because the vendored skill was **non-functional in this harness** — its first
    documented command could not succeed here, which is why "No record of last distill pass" stayed
    open for **49 days**.
  - `scan-rules.sh` cannot source `.claude/scripts/lib/always-on-rules.sh` because it ships as a
    published plugin, so the always-on predicate exists twice; the exemption is registered and a
    conformance case holds the two to agreement (DEC-0040). *It is a registered second
    implementation, not an unnoticed one.*
- **Observability:** the two scanners' output; `DISTILLATIONS.md` at the root records each pass.
- **Security / compliance:** the licence position is explicit — **no LICENSE accompanied the
  vendored copy**, and the blanket ECC row in `FORKS.md` carries the provenance. That declaration is
  what `validate-skills.sh` check 6 accepts in place of a file.
- **Versioning:** unversioned; forked at a stated date rather than a sha.

---

## Skill: s2s

**Identifier:** `s2s`
**Repository:** `.claude/skills/s2s/` (harness) · `skills/s2s/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

The channel between two running sessions.

**The stance is one sentence, and it is a measurement rather than a caution: a send reports on the
send.** `MISTAKES.md` M-0125 — a monitor brief named cross-session `SendMessage` to its coordinator
as its only reporting path. Every send is held for the recipient user's approval. **Two expired
undelivered. Each returned `success:true`.** The role produced correct findings and delivered none of
them, and nothing anywhere said so.

So the channel is real and the channel is **not a delivery guarantee**, and a session that treats it
as one loses its work silently. Three things follow:

1. **The deliverable is a durable path** — something committed and pushed, that the reader can pull
   whether or not any message arrives. The message is a **pointer** to it, plus an ask.
2. **A delegated session's terminal is a log, not a report.** Nobody is sitting in front of it. It is
   read, if at all, through `claude logs` — *a channel measured at ten escape sequences per hundred
   bytes, redrawn by cursor moves, whose word spacing does not survive the transport.* Writing a long
   report there is writing to a lossy channel with no reader.
3. **Those are different audiences with different budgets**, and a session that has not decided which
   one it is addressing writes for neither.

Rigid on the message bar and the report contract; the rest is judgment.

### Purpose and Use Cases

Fires when a session must say something to another session rather than to a person: reporting back to
a coordinator, messaging a peer or worker, deciding what belongs in a terminal versus a report, or
asking who is actually reading this output. Also on "cut the chatter", "nobody is reading this
terminal", and **when a message was sent and the reader never acted on it.**

**The seam is testable:** `s2s` governs a message and a report **in flight**; `successor` governs a
session's **lifecycle**; `handoff` governs the **document** that starts one. *If the question is
about a session that exists or is about to, it is not this skill's.*

**Two audiences.** A human reads now, in the terminal, and can say "shorter" — budget is as much as
the decision needs, and the failure is too little context to decide. Another session reads later,
cold, with none of your context — the channel is a durable path plus a pointer, the budget is **four
lines plus structure**, and the failure is a claim the reader cannot resolve or act on.

**An orphan has no human column.** A delegated session launched by `odin-relay.sh` is bounded on
**narration** rather than length: it speaks only to declare one of a fixed set of kinds, as a label
at the start of a line, and evidence under a declaration is free.

**The gap this fills**, measured at `55bb7609`:
`grep -rn 'SendMessage' .claude/rules/ .claude/docs/*.md` returned **0**. Every campaign in this
workspace ran on that channel, and no rule, no skill and no gate said anything about it. *Re-measure
before quoting the number; it is a fact about a commit.*

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `report-volume.py` | `.claude/skills/s2s/scripts/report-volume.py` | Measures a report's volume against the bound | invoked by the skill body | the report text |
| `s2s-brief-check.sh` | `.claude/scripts/s2s-brief-check.sh` | Checks a brief against the message bar | `ci-local.sh` | the brief |
| `s2s_kinds.py`, `s2s_report.py` | `.claude/scripts/lib/` | The declared-kind vocabulary and the report predicate, as libraries so there is one implementation | sourced by the gates and by `odin-voice-lint.sh` | — |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-voice-lint.sh` | `Stop` | every turn end | Lints the turn's prose for undeclared narration in a delegated session; **warns, never blocks** on the s2s clause (`harness:RM-0565`) | `s2s_kinds.py`, `voice_lint.py` |
| `odin-voice-midturn.sh` | `PostToolUse`, all tools | mid-turn | Restates the contract before a lapse rather than after one, and names the declared kinds | `s2s_kinds.py` |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches cross-session-message / "report back" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `s2s.test.sh` | the channel contract | always on | `ci-local.sh` step *s2s channel matrix* | the message bar |
| `s2s-kinds.test.sh` | the declared-kind vocabulary | always on | `ci-local.sh` step *s2s declared-kind matrix* | one implementation, in `s2s_kinds.py` |
| `voice-kind-delivery.test.sh` | that a declared kind actually reaches the reader | always on | `ci-local.sh` step *s2s kind delivery matrix* | delivery, not emission |
| `supervision-channels.test.sh` | the inbound channel order this skill added one row to | always on | `ci-local.sh` step *Supervision channels matrix* | health first |
| `s2s-brief-check.sh` | that a brief carries the message bar | always on | `ci-local.sh` | the bar's fields |
| the narration bound | how much a delegated session may say | **warn**, never block | DEC-0106, DEC-0107 | measured on narration rather than length; `harness:RM-0565` |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `successor` | complements | Lifecycle versus a message in flight | The six-element bar and the five phases stay there |
| `successor-manager` | **derives from** | *Its red flag "a send reports on the send" is where this skill's stance comes from* | **Cited, not copied** |
| `handoff` | complements, and extends by one row | The inbound supervision channel table is `handoff` §3's; this skill added the **outbound** row and owns nothing else in it | A precise, minimal extension |
| `campaign`, `gauntlet` | cited by | What a worker sends back, and that a queued message is not a delivered one (ADR-0162) | Cited from both |
| `.claude/rules/common/agents.md` | defers to | *A cited path is a claim about the reader's position* — **every word of it** | A message is that same claim in a different envelope |
| ADR-0011 / `voice_lint.py` | extends | The **shape** of prose to a human is the voice contract's | *This skill adds volume and touches no existing class* |

### Additional Relevant Information

- **Ownership:** the message bar, the report contract and the narration bound.
- **Related documentation:** ADR-0162 (the channel has an owner; the decision, its rejected
  alternatives and what the design costs); DEC-0106 and DEC-0107 (where the bound lives and why it
  warns); M-0125 (the measured incident).
- **Known limitations / technical debt:**
  - **The channel cannot be made reliable from this side.** `success:true` on a send means queued,
    not delivered, and no gate can change that — which is why the deliverable is a durable path.
  - The narration bound warns rather than blocks, so a chatty orphan is reported and not prevented.
- **Observability:** `report-volume.py`; the lint's warnings; the durable path itself, which is the
  only channel that can be checked from the reader's side.
- **Security / compliance:** messages cross session boundaries and are held for the recipient user's
  approval — treat anything sent as reaching another person.
- **Versioning:** unversioned.

---

## Skill: status

**Identifier:** `status`
**Repository:** `.claude/skills/status/` (harness) · `skills/status/` (this mirror)
**Status:** `active`
**Class:** `authored`
**Command form:** `/odin-status`

---

### Description

**The four words a human says to a fleet**, and what each one costs.

**A status is computed at read time, every time, and stored nowhere.** A status written to a file
reads identically whether it is current or six hours old — which is why `campaign` refuses a stored
status (ADR-0113), why `revive`'s manifest refuses one **at any depth**, and why nothing this skill
touches has a `state:` field.

The other three controls are **not new capability**. They are the *order the existing machinery runs
in* when a human says a word, plus the one thing no engine can supply: **what the answer costs.** *A
pause that is not accompanied by what it fails to preserve is a promise the mechanism does not make.*

Rigid skill: the bound, the channel order, the verdict vocabulary and the refusals are not judgment
calls.

### Purpose and Use Cases

Fires when a human addresses the fleet itself rather than the work.

| The human says | Verb | What runs | What it costs |
|---|---|---|---|
| "status", "what's running" | `status` | `status-report.sh` — one line, **≤300 codepoints**, computed now | Detail is elided, severity-ordered; **the counts never are** |
| "pause", "hold everything" | `pause` | quiesce the reachable sessions; report the rest | **Nothing is preserved by contract** |
| "stop and wait an hour" | `resume-at` | checkpoint, stop cleanly, write `not_before` into `revive`'s manifest | The context window. What comes back reads committed state |
| "stop so I can start fresh" | `handoff` | `handoff` / `/relay`, unchanged | Nothing — *this is the control that preserves things, by writing them down first* |

The report reads like
`odin · daemon up · sessions 18 (5 live, 8 idle, 3 blocked, 2 absent) · tasks 29 · agents ? · …`

**Three rules are load-bearing:**

1. **Liveness is never read from the subject.** `fleet-health.sh` runs first, and a roster row is
   believed only when that row's *own* socket exists. A wedged session reports `running`; a dead one
   reports whatever the registry last knew, *because the registry outlives the daemon* (ADR-0072).
2. **A count that could not be obtained renders `?`.** An invented `0` reads as a finished fleet.
   **`agents ?` is the steady state** — no channel enumerates a session's in-context subagents.
3. **An elision announces itself, and never drops the failing worker.** Blocked and absent rows sort
   ahead of live; the tail is what goes. If the counts alone will not fit, nothing is cut.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `status-report.sh` | `.claude/scripts/status-report.sh` | Computes the one-line report | run by hand, or by the `/odin-status` command | `--json` for the same content, **machine-readable and unbounded** |
| `fleet-health.sh` | `.claude/scripts/fleet-health.sh` | The first channel; its exits are **forwarded, never re-interpreted** | called first, always | — |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-compact-boundary.sh` | `PostToolUse` on `TaskUpdate` | a task completes | Names `status` among the fleet-facing skills | — |
| `odin-hardcode-guard.sh` | `PreToolUse` on writes | domain data in source | Names `status` in its guidance | — |
| `odin-task-gate.sh` | `PreToolUse`/`PostToolUse` | task bookkeeping | Names `status` in its guidance | — |
| `odin-unfinished-work.sh` | `Stop` | a turn ends with work outstanding | Names `status` as the fleet-level report | — |
| `odin-safety-guard.sh` | `PreToolUse` | a fleet-affecting command | Names `status` in its guidance | — |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "what's running" / "hold everything" / "resume in an hour" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `status-report.sh`'s 300-codepoint bound | how much of the report reaches a terminal | always on | measured over the rendered line; `--json` is unbounded | elision is severity-ordered, announces itself, and **never drops the failing worker**; if the counts alone will not fit, nothing is cut |
| `status-report.test.sh` | the bound, the elision order and the `?` rendering | always on | `ci-local.sh` step *Status report matrix*, `--timeout 180` | one case per rule |
| the `?` rule | whether an unobtainable count may render `0` | **`?`, never `0`** | inside the report | *an invented `0` reads as a finished fleet* |
| `fleet-health.sh`'s exits | whether any roster row may be believed | forwarded unchanged | first channel, always | ADR-0072 |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `handoff` (`/relay`) | **is** control 4 | "Stop so I can start fresh" | *This one routes to it and adds nothing* |
| `revive` | writes into | A timed resume writes `not_before` into that manifest | There is no second not-before format |
| `successor-manager` | defers to | What is true of one delegated session right now | The health gate, the five verdicts and the ownership register stay there |
| `successor` | defers to | Launching, integrating, tearing down a worker | **An absent worker is a finding here, never a relaunch** |
| `off-topic` | writes into | A pause that needs a checkpoint writes **that** checkpoint | *There is no second format* |
| `work-loop` | complements | **`work-loop`'s `pause` ends a cycle; this one stops a session acting** | Neither writes to the other's record |
| `s2s` | inherits from | A pause request travels that channel and inherits its rule — a send reports on the send | Cited, not restated |
| `campaign`, `gauntlet`, `endless` | defers to | Landedness, the frontier, continuation doctrine | Cited as boundaries |

### Additional Relevant Information

- **Ownership:** the four controls, the report contract and the bound.
- **Related documentation:** `references/report-contract.md` (what the 300 is measured over, why
  elision is severity-ordered, why `unknown` is never `0`, the exit codes),
  `references/pause-contract.md`, `references/report-template.txt`; DEC-0115; ADR-0072; ADR-0113.
- **Known limitations / technical debt:**
  - **`pause` preserves nothing by contract.** The skill says so rather than implying a guarantee
    the machinery does not make; anything that must survive is written down by control 4 instead.
  - `agents ?` is permanent, not a bug — no channel enumerates in-context subagents.
- **Observability:** `bash .claude/scripts/status-report.sh` and `--json`.
- **Security / compliance:** the report names sessions and projects; `--json` is unbounded and should
  be treated as the more revealing form.
- **Versioning:** unversioned.

---

## Skill: successor

**Identifier:** `successor`
**Repository:** `.claude/skills/successor/` (harness) · `skills/successor/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

A successor is a **separate OS-level Claude session** — its own context window, its own harness, its
own lifetime — launched by `.claude/scripts/odin-relay.sh` and reachable through `claude agents`.
**Not a subagent:** a subagent shares the parent's lifetime, returns text, and dies with the turn; a
successor outlives the session that spawned it, pushes commits, and is integrated by branch.

**Core principle: a successor knows only what its handoff says.** Everything else it must rediscover
at its own cost, or guess at yours. *The handoff bar is therefore the whole skill; the rest is
procedure around it.*

Rigid skill: the phases run in order, and **the bar has no optional elements.**

### Purpose and Use Cases

Fires for two or more independent coordinated workers, a campaign with waves and per-worker branches,
a delegated session that has stalled or wedged, and a worker's branch that is ready to land. **One
successor is the `handoff` skill (`/relay` is its command form); a coordinated fleet is this one.**

**Not for** work that fits one session (just do it), parallel work inside one context window
(`dispatching-parallel-agents` — subagents, not sessions), or work whose steps share mutable state:
*parallel sessions on one checkout corrupt each other's index* (ADR-0054).

**The six-element handoff quality bar** — the canonical statement, which every other skill cites
rather than restates. *A missing element is not a gap the worker fills in; it is a wrong turn the
worker takes confidently.*

1. **Relevant skill set** — a `## Suggested skills` section naming the skills that own the work.
2. **Assigned task and desired outcome** — what to build, and what "done" looks like as an artifact.
3. **Current context** — progress so far, decisions already made and their reasons, constraints.
4. **Open questions, risks, dependencies, next actions.**
5. **Authorization scope** — an explicit `edit only: <paths>` line: what the worker may touch, and
   what belongs to a sibling worker or the coordinator.
6. **Standing invariants** — **restated, not assumed.**

Plus the frontmatter's six fields, the `## Suggested skills` section, and qualified roadmap ids —
**already refused by `odin-relay.sh`** (ADR-0038, ADR-0050, ADR-0056). *Cite them, do not restate
their rules, and never re-implement the checks.*

**"The successor manager" is a role, and `successor-manager` is the skill that owns it** (ADR-0105).
Its occupant is whoever launched the sessions — the delegating session for one successor, the
coordinator for a fleet.

### Scripts

This skill does not define scripts of its own. It launches through
`.claude/scripts/odin-relay.sh` and reads fleet state through `.claude/scripts/fleet-health.sh`,
`.claude/scripts/session-burn.sh` and `.claude/scripts/odin-autonomous.sh` — all harness scripts,
shared with `handoff` and `successor-manager`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write is attempted | Names `successor` among the skills in the chain that satisfies it | the plan directories |
| `odin-voice-lint.sh` | `Stop` | every turn end | Names `successor` — a delegated session's narration bound is what the lint measures | `s2s_kinds.py` |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches delegation / fleet intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `odin-relay.sh`'s refusals | whether a handoff may launch | refuses, never warns | at launch | three of the six bar elements are mechanical: frontmatter fields, `## Suggested skills`, qualified ids (ADR-0038, ADR-0050, ADR-0056) |
| `handoff-delegation.test.sh` | that delegation is the default rather than a follow-up step | always on | `ci-local.sh` step *Handoff delegation matrix* | — |
| `relay-seed.test.sh`, `relay.test.sh`, `relay-handoff-test.sh` | the seed's content, the relay's behaviour, the launch directory | always on | three `ci-local.sh` steps | one refusal or seed invariant each |
| `supervision-channels.test.sh` | Phase 3's channel order | always on | `ci-local.sh` step *Supervision channels matrix* | health first |
| the posture requirement | whether a worker's gates block or warn | **each worker arms its own** | `odin-autonomous.sh on`, per session | **a coordinator cannot arm a child** (ADR-0051) |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `handoff` (`/relay`) | complements | One successor is that skill; a fleet is this one (ADR-0059) | **Both launch through the same script and inherit its refusals; neither re-implements them** |
| `successor-manager` | **hands the role to** | Phase 3 is the monitoring duty; the ownership register and the five verdicts are that skill's | ADR-0105. Cited, never restated |
| `campaign` | invoked by | A campaign decides *what* is delegated and in what order; this performs each delegation | The six-element bar is cited from there, never copied — *two copies drift and the looser copy wins silently* |
| `gauntlet` | invoked by | Step 4 assigns campaign-shaped rows with colliding surfaces held back | Ordering: the frontier first |
| `revive` | invoked by | A revived coordinator runs Phase 1 for its own workers | Revive launches exactly one session |
| `endless` | invoked by | The Delegate continuation, when ≥2 items share a wave and their surfaces do not overlap | Then integrate, then resume at phase 1 |
| `s2s` | complements | What a worker says back, and its terminal's narration bound | Lifecycle here, message in flight there |
| `dispatching-parallel-agents` | explicitly excluded | Subagents share the parent's lifetime and die with the turn | *There is no register row and no verdict to compute* |

### Additional Relevant Information

- **Ownership:** the six-element bar, the five phases, and the fleet's provisioning discipline.
- **Related documentation:** `references/fleet-runbook.md`, `references/handoff-template.md`;
  ADR-0059 (one successor vs a fleet), ADR-0105 (the successor-manager role), ADR-0054 (parallel
  sessions on one checkout), ADR-0051 (posture is per-session), ADR-0038/0050/0056 (the three
  mechanical refusals).
- **Known limitations / technical debt:**
  - Three of the six bar elements are mechanically refused; **the other three are not**, and a
    handoff that satisfies the relay can still send a worker down a wrong turn confidently.
  - Each worker must arm its own posture, and nothing can do it on their behalf — a worker that skips
    it runs with warned gates for its whole life.
- **Observability:** `claude agents --json`, `claude logs <id>`, branch movement — after
  `fleet-health.sh`, never before.
- **Security / compliance:** the `edit only:` line is the access-control boundary between sibling
  workers, and it is prose rather than an enforced permission.
- **Versioning:** unversioned.

---

## Skill: successor-manager

**Identifier:** `successor-manager`
**Repository:** `.claude/skills/successor-manager/` (harness) · `skills/successor-manager/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

Owns two things nothing else owns: **who is responsible for a delegated session**, and **how that
session's state is decided from evidence rather than from its own report of itself.**

**The stance: a session's own report of itself is never sufficient evidence.** A wedged session
reports that it is running. A dead session reports whatever the registry last knew, because the
registry outlives the daemon that served it — **on 2026-08-19 five sessions died together and went on
rendering as ordinary for eight hours** (M-0014, ADR-0072). Both are the subject describing itself,
and *neither can report its own absence.*

So the verdict is computed from channels the subject does not control, in a fixed order, **and the
order is the point.**

### Purpose and Use Cases

Fires when delegated sessions already exist and the question is who owns one or what is actually true
of it — a worker that may be stalled, a fleet whose state nobody trusts, a branch to resume without
re-running landed work.

**Three signals, in order:**

1. **`fleet-health.sh` first**, because the other two cannot report their own absence. **Its exit
   code gates everything after it:** `2` means the daemon is gone and *every* session is dead
   regardless of what the registry says; `3` means the registry is unreadable and **no verdict may be
   claimed for anything.**
2. **Branch movement** — `git ls-remote --heads origin <branch>` for the published sha.
3. **Landedness by content**, never by ancestry.

Out of those comes **one of five verdicts**.

The boundary with `s2s` is stated crisply: *this skill decides what is **true** of a session; that one
decides what it **says**.* The red flag "a send reports on the send" originates here and is cited
there.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `successor-status.sh` | `.claude/skills/successor-manager/scripts/successor-status.sh` | Computes the verdict for a delegated session from the three signals | invoked by the skill body; matrix at `.claude/tests/successor-status.test.sh` (`ci-local.sh` step *Successor status matrix*) | the session id and its branch |
| `successor-deliverable.sh` | `scripts/successor-deliverable.sh` | Establishes what a worker actually produced | invoked by the skill body; matrix at `successor-deliverable.test.sh` | the branch |
| `fleet-health.sh` | `.claude/scripts/fleet-health.sh` | Signal 1, and the gate on the other two | called first, always | exits **forwarded unchanged** |
| `session-burn.sh` | `.claude/scripts/session-burn.sh` | Spend, as a separate quantity from progress | consulted for escalation | ADR-0097 |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "is that worker stalled" / ownership intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `successor-status.test.sh` | the three signals, their order, and the five verdicts | always on | `ci-local.sh` step *Successor status matrix* | one case per signal and per verdict |
| `successor-deliverable.test.sh` | what counts as a worker's deliverable | always on | `ci-local.sh` step *Successor deliverable matrix* | — |
| `fleet-health.sh` exit 2 / exit 3 | whether any verdict may be claimed | **gates everything after it** | first signal, always | `2` → every session dead; `3` → **no verdict for anything** |
| `supervision-channels.test.sh` | the channel order | always on | `ci-local.sh` step *Supervision channels matrix* | health first |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `successor` | receives the role from | It owns the five phases; this starts once a session exists | **Its bar is cited here, never restated — two copies of a bar drift, and the looser copy wins silently** |
| `handoff` (`/relay`) | consulted by | One-off delegation with its own gates | *This skill is what you consult about either afterwards* |
| `campaign` | invoked by | A campaign **asks** it and never re-derives it | Nothing here opens a daemon socket |
| `revive` | shares channels | Precondition 5 asks a narrower question — present or absent — of the same channels | The five verdicts stay here |
| `status` | invoked by | The fleet report defers to this skill for what is true of one session | Cited, never re-derived |
| `s2s` | **originates** | "A send reports on the send" is this skill's red flag | True versus said |
| `endless` | explicitly excluded | Continuation doctrine | *This skill says what happened; it never says whether to carry on* |
| `dispatching-parallel-agents` | explicitly excluded | Subagents have no register row and no verdict | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the ownership register and the five verdicts.
- **Related documentation:** `references/ownership-register.md`, `references/escalation-paths.md`;
  ADR-0105 (the register and a verdict from channels the session does not control); ADR-0072 and
  M-0014 (the registry outlives the daemon); ADR-0097 (the burn predicate, and the still-open
  question of when spend alone earns an escalation).
- **Known limitations / technical debt:**
  - **A named seam, deliberately unfilled:** when spend alone earns an escalation is open, and
    `escalation-paths.md` names it rather than inventing a threshold.
  - The skill's own boundary table names `campaign` as *"harness:RM-0302, **not yet built**"* — a
    statement that has since been overtaken, since `campaign` is a member of this catalog. Recorded
    here rather than corrected; `.claude/skills/` is not this document's to edit.
- **Observability:** `successor-status.sh`, `successor-deliverable.sh`, `fleet-health.sh`.
- **Security / compliance:** reads only; changes no session state.
- **Versioning:** unversioned.

---

## Skill: superplan

**Identifier:** `superplan`
**Repository:** `.claude/skills/superplan/` (harness) · `skills/superplan/` (this mirror)
**Status:** `active`
**Class:** `authored` · formerly named `ultraplan`

---

### Description

> *Ship signal, not noise. Parallel perspectives, one coherent plan, an approval gate that matches
> the posture — human when a human is driving, self-served and recorded when none is.*

A multi-agent deep-planning workflow: fan out to `planner`, `architect` and an adversarial reviewer
**in parallel**, then synthesise their output into one approved plan document.

It is the harness's default answer to "plan before editing" — CLAUDE.md item 5's third precondition —
and `roadmap`'s Gate 4 fires it **always, before source**.

### Purpose and Use Cases

Fires on any implementation task where scope, architecture or approach is non-obvious; before writing
code for a feature touching multiple files or systems; and when a written plan doc is required for
approval.

**Phase 1 fans out to three agents simultaneously.** The instruction that matters operationally is
about context, not about planning: **fill `<CONTEXT>` with ≤10 paths, one line each, path + role —
never file contents.** *Each agent starts its own session, so `<CONTEXT>` is paid three times — on
top of `CLAUDE.md` and the always-on rules, which every one of those sessions loads in full before it
reads a word of the task. Two of the three copies are pure duplication; the first is the cost of
doing the work at all.* Every agent has its own Read and Grep; what it needs is **where to start
looking, not the material itself.**

**The skill refuses to state its own context figures**, and says why: run
`bash .claude/scripts/context-budget.sh report` for today's numbers. *This line said `~52 KB` while
the rules index said `38.8 KB` and a skill sample said `34.8 KB` — none of them agreeing and none of
them produced by anything* (`harness:RM-0164`).

**The announce line is a fragment, deliberately.** The skill instructs
`superplan — fan-out: planner, architect, adversary`, and states the reason: *Odin voice does not
lapse inside a skill (ADR-0011), and a quotable first-person sentence in skill text is the shape that
causes the lapse.*

**The approval gate matches the posture** — human when a human is driving, **self-served and
recorded** when none is (ADR-0052).

### Scripts

This skill does not define any scripts.

It names three harness scripts: `.claude/scripts/context-budget.sh` (today's figures, rather than a
number in the body), `.claude/scripts/odin-autonomous.sh` (the posture the approval gate reads), and
its own matrix `.claude/tests/superplan-template.test.sh`.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches deep-planning intent | Names this skill in the routing hint | none |
| `odin-plan-gate.sh` | `PreToolUse` on writes | a write with no active plan | **warn** interactive, **block** unattended; a superplan document satisfies it | the plan directories; the posture ticket |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `superplan-template.test.sh` | that the plan document's template is intact | always on | `ci-local.sh` step *Superplan template matrix* | the template's required sections |
| `odin-plan-gate.sh` | whether any write may proceed | **warn** interactive, **block** unattended | `odin-autonomous.sh on`, per session (ADR-0051) | `ODIN_PLAN_ENFORCE` overrides; plan, ADR and memory files exempt |
| the plan-depth bar | whether the plan is deep enough to be finished | planner sends back below 4/5 | `.claude/docs/plan-depth-standard.md` (ADR-0027) | three preconditions: a named process skill, **≥3 genuine decision forks (target 3–5)**, and a **recorded scope decision** |
| the approval gate | who approves the plan | **posture-dependent** | human when attended; **self-served and recorded** when not | ADR-0052 — `AskUserQuestion` must not stop an unattended run |
| the `<CONTEXT>` bound | how much each fanned-out agent pays | **≤10 paths, no file contents** | inside Phase 1 | paid three times over, on top of the always-on load |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `planner`, `architect`, `plan-adversary` (agents, not skills) | **dispatches, in parallel** | Three independent perspectives, synthesised once | Simultaneous dispatch is the design; sequential would triple the wall clock without changing the cost |
| `roadmap` | invoked by (Gate 4) | **Always, before source** | No exception in the gate table |
| `blueprint` | hands off to | More than about 12 steps out of a superplan **is a decomposition failure reported as a step list** | The step count is the boundary |
| `writing-plans` | complements | The decision-plan artifact and its rubric | `blueprint`'s entry documents the two-plan distinction |
| `grilling`, `brainstorming` | invoked before | The first plan-depth precondition — a named process skill for intent | Ordering: intent, then plan |
| `decision-matrix` | invoked during | Each enumerated fork is resolved and recorded rather than handed to the user | `.claude/rules/common/decision-authority.md` |
| `test-driven-development`, `executing-plans`, `subagent-driven-development` | hands off to | Execution | Superplan plans; it does not build |

### Additional Relevant Information

- **Ownership:** the fan-out shape and the synthesis; the depth bar by
  `.claude/docs/plan-depth-standard.md`; the posture by `odin-autonomous.sh`.
- **Related documentation:** `.claude/docs/plan-depth-standard.md` (ADR-0027, the planner rubric —
  send back below 4/5); ADR-0052 (a question ends the turn); ADR-0011 (voice does not lapse inside a
  skill); `harness:RM-0164` (why the context figures are not written here).
- **Known limitations / technical debt:**
  - **The three-times cost is intrinsic.** Every fanned-out agent loads `CLAUDE.md` and the always-on
    rules in full before reading the task; the `<CONTEXT>` bound is the only lever.
  - The skill's former name, `ultraplan`, survives in older documents and transcripts.
  - A known operational trap: the posture check reads *interactive* in a background job, so an armed
    background session must re-arm and re-check in one command.
- **Observability:** `bash .claude/scripts/context-budget.sh report`; the plan document itself.
- **Security / compliance:** none specific.
- **Versioning:** unversioned; renamed once, from `ultraplan`.

---

## Skill: test-driven-development

**Identifier:** `test-driven-development`
**Repository:** `.claude/skills/test-driven-development/` (harness) · `skills/test-driven-development/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `obra/superpowers`, MIT (Copyright (c) 2025 Jesse Vincent); upstream HEAD last audited `b36e082` (2026-08-12)

---

### Description

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle: if you didn't watch the test fail, you don't know if it tests the right thing.**

**The Iron Law:** `NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST`. Write code before the test?
Delete it. Start over. *"Violating the letter of the rules is violating the spirit of the rules."*

**Forked from `obra/superpowers`.** The fork's `UPSTREAM.md` records a decision that had been left
open: upstream replaced roughly 60 lines of rationalisation-catalogue with three- or four-line
entries — *"I'll test after"*, *"Tests after achieve same goals"* — and carries material the retired
file had no equivalent of, including **Principle 1, "Name the behaviour"**. The divergence table
records which upstream hunks were adopted and which were not, and why.

### Purpose and Use Cases

Fires when implementing **any** feature or bugfix, before writing implementation code. Always: new
features, bug fixes, refactoring, behaviour changes.

*Thinking "skip TDD just this once"? Stop. That's rationalization.*

**The upstream exception clause — "Exceptions (ask your human partner)" for throwaway prototypes,
generated code and configuration files — is discharged in this harness rather than followed.**
`.claude/rules/common/testing.md` owns Odin's exception policy (the coverage floor and required test
types) and the recovery when RED was skipped, so *the skill is asking about a decision an always-on
rule has already made.* That discharge is recorded per-line in
`.claude/rules/common/decision-authority.md`, which cites `SKILL.md:24` and `SKILL.md:331` by path,
line and anchor phrase.

**The recovery when RED was skipped is Odin's, not upstream's**, and it is not "write the tests now
and move on": *a test that has never been seen red asserts nothing, and one written against finished
code usually asserts what the code does rather than what it should do.* Instead — **mutate the
implementation and prove the tests catch it.** Flip a condition, delete a branch, drop a guard, return
a constant, one change at a time; each mutation must turn at least one test red, then restore it. A
mutation nothing catches names a missing case. **State in the PR that RED was skipped and that
mutation checks stand in for it** — a repair with a cost, not an equivalent path.

**No hook checks any of this.** Commit ordering is destroyed by a squash merge and by `--amend`, so
test-first-ness is **not a repository-state predicate** — it is held by the agent doing the work.

### Scripts

This skill does not define any scripts.

It ships `writing-good-tests.md` beside `SKILL.md` rather than a `scripts/` directory.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-surface-router.sh` | `PreToolUse` on `Write\|Edit\|NotebookEdit\|Bash` | the file being written is source or a test | Names this skill and the language rule namespace for the surface, **with no prompt involved** — which is what still fires at turn thirty | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches feature / bugfix intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `elicitation-contract.test.sh` | the discharge of the skill's "ask your human partner" clause | always on | `ci-local.sh` step *Elicitation-contract matrix* | the contract's own predicate |
| `rule-citations.test.sh` | that `decision-authority.md`'s citations into this skill resolve — **path, line and anchor phrase** | always on | `ci-local.sh` step *Rule-citation matrix* **and** `PRE_PUSH_GATES` (5819ms) | *a vendored skill that gains ten lines leaves every bare line number resolving to real, wrong text, silently*; the row citing `:331` read `:371` for as long as nobody checked |
| the 80% coverage floor | the minimum coverage for `projects/<slug>/` work | 80% | `.claude/rules/common/testing.md`, ADR-0123 | **The harness ships no application source, so the floor binds the vendored project trees**, each with its own coverage tooling; the harness's own bash and Python are covered by their matrices instead |
| the Iron Law | whether production code may be written | absolute | procedural — **no hook checks it** | commit ordering does not survive a squash merge or `--amend` |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `tdd-guide` (agent) | paired with | The agent enforces write-tests-first and is used proactively | Named in `.claude/rules/common/testing.md` |
| `oops` | receives from | Three of the six guard classes — input guard, precondition, postcondition — are written test-first | Ordering: classify there, write the test here |
| `roadmap`, `superplan`, `blueprint` | invoked by | The build phase of every planned item | Plan first, then RED |
| `.claude/rules/common/testing.md` | **discharged by** | Odin's exception policy and the RED-skipped recovery | *The skill is asking about a decision an always-on rule has made* |
| `react-testing`, `e2e-testing`, `ai-regression-testing` | complements | Surface-specific test practice | Routed by surface, not by this skill |
| `verification-before-completion` | complements | Evidence before a completion claim | Different moment in the same discipline |

### Additional Relevant Information

- **Ownership:** the discipline is upstream's; the exception policy, the RED-skipped recovery and the
  coverage floor are Odin's, in `.claude/rules/common/testing.md`.
- **Related documentation:** `writing-good-tests.md` beside the skill;
  `skills/test-driven-development/UPSTREAM.md` in this mirror;
  `.claude/rules/common/decision-authority.md` (the per-line discharge, with anchor phrases);
  `.claude/rules/common/testing.md`; ADR-0123 (whose coverage floor this is).
- **Known limitations / technical debt:**
  - **Nothing enforces test-first-ness**, and the skill and the rule both say so. The mutation
    recovery is what stands in for it after the fact.
  - The upstream divergence includes material this fork has **not** adopted, listed hunk by hunk in
    `UPSTREAM.md`; a refresh is a re-reading, not a restore.
- **Observability:** the failing test itself; a mutation that no test catches.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror.
- **Versioning:** unversioned; upstream divergence pinned by sha.

---

## Skill: tidy

**Identifier:** `tidy`
**Repository:** `.claude/skills/tidy/` (harness) · `skills/tidy/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

> *The deliberate act, never the sweep. A path arrives; a verdict comes out. Nothing here searches
> for candidates, and nothing here removes anything.*

Decides whether something that has outlived its purpose may go. **One path per run**, and a directory
argument is a **usage error, not a candidate list.**

### Purpose and Use Cases

Fires when a plan doc, report, brief or scratch file looks finished; when a `leek` finding named a
path and the next question is what to do about it; before deleting anything when the answer is not
already obvious; and when a **branch** is being considered for deletion — *ask, and get told no, with
the reason.*

**Four verdicts**, and exit codes are the interface (`0` remove, `10` retain, `11` refuse, `12`
unresolved, `2` usage):

| Verdict | Means | Do |
|---|---|---|
| `remove` | A removal ledger records the basename — **its content survived somewhere** | Run the printed **dry-run** line, read what it names, then run the **apply** line. Two commands, in that order, *both read before either runs* |
| `retain` | No ledger names it, **so this copy may be the only one** | Keep it. If it really is spent, **write the ledger record first**, then re-run — *the record is the durable half, the file is the disposable one* |
| `refuse` | The argument is a branch | Nothing. **Not now and not with better evidence** |
| `unresolved` | The path resolved to nothing, or no ledger was readable | Report the gap and fix what could not be read. *A check that could not look is a finding, never a silence* |

**Every verdict other than `remove` keeps the material, and that is the whole shape: a wrong retain
costs disk, a wrong removal costs the content.**

**A branch is always `refuse`, permanently, and it is nobody's to delete** — ADR-0093: *the error is
asymmetric and force-push is blocked, so a wrongly deleted branch has no reflex that restores it.*

**An open checkpoint under `.claude/docs/off-topic/` also always refuses.** It *looks* like residue
and is an outstanding obligation; closing one is a **return** — the file is deleted by the commit
that resumes the work, never by a sweep.

**The removal is yours, not the script's.** `tidy-verdict.sh` prints commands and runs none of them.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `tidy-verdict.sh` | `.claude/skills/tidy/scripts/tidy-verdict.sh` | Returns one of four verdicts for one path, and **prints the dry-run and apply commands without running either** | invoked by the skill body; matrix at `.claude/tests/tidy-verdict.test.sh` (`ci-local.sh` step *Tidy verdict matrix*) | `<path>`, `--root <dir>`, or `<branch-name>`. Exits `0`/`10`/`11`/`12`/`2` |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "can this be deleted" / "is this still needed" intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `tidy-verdict.test.sh` | the four verdicts and their exit codes | always on | `ci-local.sh` step *Tidy verdict matrix* | one case per verdict, including the permanent branch refusal |
| the branch refusal | whether a branch may ever be deleted through this skill | **refuse, permanently** | ADR-0093 | the argument is a branch name |
| `plan-retention-check.sh`, `branch-retention-check.sh` | the retention policies the verdicts read against | always on | `ci-local.sh` steps *Plan retention (tree)* and *Branch retention (tree)* (`--timeout 420 --hygiene`, clean-clone, `gh`) | ledger and age predicates |
| `runtime-retention.sh` | session-keyed runtime state | swept **mechanically on a schedule** | outside this skill | *a class nobody declared is swept by nothing — a declaration bug, not a tidy decision* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `leek` | receives from | It finds; this decides | **This skill performs no discovery.** Two non-destructive skills by design |
| `workflows` | defers to | Retiring a workflow is a **lifecycle transition on a manifest with its own enforced refusal**, not a filesystem removal | Never a `remove` verdict |
| `off-topic` | refuses for | An open checkpoint is an obligation, not residue | Always `refuse` |
| `campaign`, `gauntlet` | receives from | Close-out hands residue over as a list | *This skill removes nothing* |
| CLAUDE.md item 8 | reads | *A plan is spent once its work is in living docs or code **and recorded in `CHANGELOG.md`*** | **This skill reads that record; it does not form the judgement** |
| `roadmap` | explicitly excluded | Removing spent material is not planning | Cited as a boundary |

### Additional Relevant Information

- **Ownership:** the four verdicts; the removal ledgers themselves (`CHANGELOG.md` chief among them)
  are owned by the contract.
- **Related documentation:** `references/verdict-rules.md` (what counts as evidence, how the basename
  is matched, **why history and appearance are not evidence**, and how to override a verdict
  honestly); ADR-0110; ADR-0093; ADR-0088.
- **Known limitations / technical debt:**
  - The `remove` verdict rests on a **basename match** in a ledger, which is a correlate of "the
    content survived somewhere" rather than the property itself.
  - Because the skill never searches, nothing here will ever tell you what you *should* be asking
    about — that asymmetry is deliberate and is why `leek` exists.
- **Observability:** the verdict and its exit code; the printed dry-run line.
- **Security / compliance:** the skill is non-destructive by construction; the destructive step is
  always the operator's own command.
- **Versioning:** unversioned.

---

## Skill: using-superpowers

**Identifier:** `using-superpowers`
**Repository:** `.claude/skills/using-superpowers/` (harness) · `skills/using-superpowers/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `obra/superpowers`, MIT (Copyright (c) 2025 Jesse Vincent); upstream HEAD last audited `b36e082` (2026-08-12)

---

### Description

The skill-first discipline itself: **invoke relevant or requested skills before any response or
action**, including before clarifying questions. *If there is even a 1% chance a skill applies, invoke
it to check.*

It is the one member whose **full text is injected at session start** rather than loaded on demand,
which makes it the corpus's entry point rather than one of its entries.

Its instruction-priority ladder is what makes it safe to inject: **user instructions
(`CLAUDE.md`/`AGENTS.md`, direct requests) outrank superpowers skills, which outrank default system
behaviour.** *If the instructions file says "don't use TDD" and a skill says "always use TDD", follow
the instructions. The user is in control.*

**Forked from `obra/superpowers`, with the body otherwise upstream's.** Two local changes, both
structural rather than editorial:

1. **Activation adapted to a vendored `SessionStart` hook.** Upstream assumes its own installer wires
   activation; Odin injects the skill's text from `.claude/hooks/superpowers-session-start.sh`.
2. **Two platform reference files retained that upstream has since removed** —
   `references/claude-code-tools.md` and `references/copilot-tools.md`. **Both are reachable from the
   injected session-start text, so dropping them breaks the injection rather than merely losing a
   document.**

The 2026-08-15 audit measured +88 lines upstream against −195 lines here across four shared files, and
upstream has added `references/hermes-tools.md`, which this fork does not carry. *Refreshing needs
care in both directions: adopt upstream's edits, but do not let the refresh delete the two retained
reference files.*

### Purpose and Use Cases

Fires at the start of **any** conversation. Its operative content is a decision flow and two tables:

- **Skill priority when several could apply:** *process skills first* (`brainstorming`,
  `systematic-debugging`) — these determine **how** to approach the task — then implementation
  skills. "Let's build X" → brainstorming first. "Fix this bug" → systematic-debugging first.
- **Skill types:** *rigid* (TDD, systematic-debugging) — follow exactly, do not adapt away the
  discipline; *flexible* (patterns) — adapt to context. **The skill itself says which it is.**
- **A red-flags table of twelve rationalisations**, each with the reality: *"This is just a simple
  question" → questions are tasks; "Let me explore the codebase first" → skills tell you HOW to
  explore; "I remember this skill" → skills evolve, read the current version; "The skill is overkill"
  → simple things become complex.*
- **Never read a skill file manually with file tools** — always use the platform's skill-loading
  mechanism, so the skill is properly activated.
- It carries a `<SUBAGENT-STOP>`: a subagent dispatched to execute a specific task skips it.

### Scripts

This skill does not define any scripts.

Its activation is `.claude/hooks/superpowers-session-start.sh`, a harness hook.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `superpowers-session-start.sh` | `SessionStart` | every session start | **Injects this skill's full text into the session**, together with the two retained platform reference files | those two reference files must exist; matrix at `superpowers-session-start.test.sh` |
| `odin-skill-gate.sh` | `UserPromptSubmit` | every prompt | The mechanical half of the same discipline — reads intent and names the skills that should fire | none |
| `odin-surface-router.sh` | `PreToolUse` on writes | every edit | The other mechanical half — reads the **surface** and names skills with no prompt involved | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `superpowers-session-start.test.sh` | that the injection works and its references resolve | always on | `ci-local.sh` step *Superpowers session-start* | the hook's output and the two retained files |
| `skill-invocability-check.sh` | that a routed skill can actually be invoked | always on | `ci-local.sh` step *Routed skills are invocable*, clean-clone | `disable-model-invocation` must be absent |
| `skill-routing-check.sh`, `skill-gate-test.sh`, `skill-reachability-check.sh` | that intent reaches a skill at all | always on | three `ci-local.sh` steps | routing-surface coverage |
| the instruction-priority ladder | which instruction wins when two conflict | **user first, skills second, defaults last** | stated in the injected text | a conflict is resolved in the user's favour, explicitly |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| **every skill in the harness** | routes to | This is the discipline that makes any of them fire | Injected at session start, so it is the only member that is always resident |
| `brainstorming`, `systematic-debugging` | prioritises | Process skills before implementation skills | *These determine HOW to approach the task* |
| `find-skills`, `skill-repo` | invokes | Discovering a skill that might apply | The 1% rule's escape hatch |
| `test-driven-development` | classifies | Named as an example of a **rigid** skill | *Follow exactly; do not adapt away the discipline* |
| `odin-skill-manager` | classified by | Its two retained reference files are the fork evidence a refresh must not delete | Refresh protection is derived from this mirror |

### Additional Relevant Information

- **Ownership:** upstream's body, held as a fork; the injection hook is harness machinery.
- **Related documentation:** six platform reference files under `references/` —
  `claude-code-tools.md`, `codex-tools.md`, `copilot-tools.md`, `gemini-tools.md`, `pi-tools.md`,
  `antigravity-tools.md`; `skills/using-superpowers/UPSTREAM.md` in this mirror.
- **Known limitations / technical debt:**
  - **This skill costs context on every session, unconditionally**, because it is injected rather
    than routed. That is the deliberate trade for the discipline it enforces.
  - Two of its reference files exist **only here**; a careless refresh deletes them and silently
    breaks the session-start injection. `UPSTREAM.md` warns in both directions.
- **Observability:** the injected block at session start; the session-start matrix.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror.
- **Versioning:** unversioned; upstream divergence pinned by sha and measured in lines.

---

## Skill: verification-before-completion

**Identifier:** `verification-before-completion`
**Repository:** `.claude/skills/verification-before-completion/` (harness) · `skills/verification-before-completion/` (this mirror)
**Status:** `active`
**Class:** `forked` — upstream `obra/superpowers`, MIT (Copyright (c) 2025 Jesse Vincent); upstream HEAD last audited `b36e082` (2026-08-12)

---

### Description

**Claiming work is complete without verification is dishonesty, not efficiency.**

**Core principle: evidence before claims, always.** *Violating the letter of this rule is violating
the spirit of this rule.*

**The Iron Law:** `NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE`. *If you haven't run the
verification command in this message, you cannot claim it passes.*

**Forked from `obra/superpowers`**, and the divergence is unusual: **the overwhelming majority of
what looks like local divergence is upstream deletion.** Upstream has trimmed the skill — the "Why
This Matters" failure-memory list and "The Bottom Line" section are gone, −25 lines relative to this
fork, with no upstream additions. *A refresh here would remove content, not add it.*

### Purpose and Use Cases

Fires before **any** variation of a success or completion claim, any expression of satisfaction, any
positive statement about work state, before committing, PR creation or task completion, before moving
to the next task, and before delegating to agents.

**The gate function is five steps, and skipping any one is named as lying rather than verifying:**
identify what command proves the claim → run the **full** command, fresh and complete → read the full
output, check the exit code, count failures → verify the output confirms the claim → only then make
it.

**The common-failure table is the operational core**, because each row names a substitute that feels
sufficient and is not:

| Claim | Requires | Not sufficient |
|---|---|---|
| Tests pass | Test command output: 0 failures | A previous run, "should pass" |
| Linter clean | Linter output: 0 errors | A partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs looking good |
| Bug fixed | Test the **original symptom**: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | The test passing once |
| **Agent completed** | **VCS diff shows changes** | **The agent reporting "success"** |
| Requirements met | Line-by-line checklist | Tests passing |

**Red flags that mean stop:** "should", "probably", "seems to"; expressing satisfaction before
verification ("Great!", "Perfect!", "Done!"); trusting agent success reports; *"just this once"*;
being tired and wanting the work over; **any wording implying success without having run
verification.**

The rule is explicitly written to apply to **paraphrases, synonyms and implications** as well as
exact phrases — *"different words so the rule doesn't apply" → spirit over letter.*

### Scripts

This skill does not define any scripts.

The command it demands is always the caller's own — the test, build, or lint command that proves the
specific claim.

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-completion-evidence.sh` | `Stop` | a turn ends making a completion claim | **The mechanical half of this skill** — requires evidence behind the claim | matrix at `completion-evidence.test.sh` |
| `odin-unfinished-work.sh` | `Stop` | a turn ends with work outstanding | Reports what remains rather than letting the turn close silently | matrix at `unfinished-work.test.sh` |
| `odin-surface-router.sh` | `PreToolUse` on writes | any edit | Names this skill for surfaces where a claim is about to be made | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches "is it done" / pre-commit intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `completion-evidence.test.sh` | that a completion claim carries evidence | always on | `ci-local.sh` step *Completion-evidence matrix* | the `Stop` hook's own predicate |
| `unfinished-work.test.sh` | that outstanding work is reported at turn end | always on | `ci-local.sh` step *Unfinished-work matrix* | — |
| the Iron Law | whether a claim may be made at all | absolute; **no exceptions** | procedural, backed by the `Stop` hook | *if you haven't run the command in this message, you cannot claim it passes* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `verification-loop` | hands off to | *This is a **gate mindset**; that is a structured multi-phase build/type/lint/test/security/diff workflow producing a formal VERIFICATION REPORT* | The skill body draws this distinction itself |
| `test-driven-development` | complements | The red-green cycle is the verification a regression test requires | *"I've written a regression test" without red-green is a named failure* |
| `requesting-code-review`, `finishing-a-development-branch` | precedes | Before a PR or a merge | Ordering: verify, then request review |
| `successor`, `successor-manager` | reinforces | **"Agent completed" requires a VCS diff, not the agent's report** | The same stance `successor-manager` derives its verdicts from |
| `endless`, `gauntlet` | invoked by | Phase 6 / step 6 of each loop | Locally, on the working tree |

### Additional Relevant Information

- **Ownership:** upstream's body, held as a fork; the `Stop`-hook enforcement is Odin's.
- **Related documentation:** `skills/verification-before-completion/UPSTREAM.md` in this mirror;
  `.claude/rules/common/git-workflow.md` (*never report work as verified on the strength of a remote
  run you did not run locally first*).
- **Known limitations / technical debt:**
  - The retained "Why This Matters" section cites **24 failure memories** and a partner saying *"I
    don't believe you"* — upstream has deleted it, so a refresh would silently remove the strongest
    part of the argument.
  - The `Stop` hook can require *evidence-shaped* output; it cannot verify that the command quoted
    was actually run in this turn.
- **Observability:** the verification command's own output; the `Stop` hook's finding.
- **Security / compliance:** MIT obligations discharged by the `LICENSE` beside the skill in this
  mirror.
- **Versioning:** unversioned; upstream divergence pinned by sha, and **negative** in line terms.

---

## Skill: work-loop

**Identifier:** `work-loop`
**Repository:** `.claude/skills/work-loop/` (harness) · `skills/work-loop/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

A Loop is **bounded work with a declared contract**, iterations that each end in exactly one of six
outcomes, and **a ledger a fresh session can resume from without repeating a single completed
action.**

### Purpose and Use Cases

Fires when a bounded work cycle needs a contract and a resumable ledger — declaring what one iteration
is, recording which outcome ended it, detecting a stalled loop mechanically, or resuming a loop a dead
session left half-done.

**The contract is twelve fields, declared before the first iteration and refused if any is missing or
empty:** purpose, owner, starting state, inputs, expected outputs, success criteria, failure criteria,
dependencies, iteration limit, timeout behaviour, escalation path, quality rubric.

**The quality rubric is the twelfth field and the one that makes "better" checkable rather than
asserted.** A weighted list of dimensions, each naming **the command that produces its number**, plus
baseline, target, weight, failure threshold, direction, and whether it is a hard gate. *`open` refuses
a dimension with no evidence command — a dimension you cannot write a command for is a judgment, and
a judgment belongs in review rather than in a rubric.*

**A hard-gate failure outranks any weighted total, including one that went up.** `score` exits **6**
in that case — distinct from malformed (1) and ok (0) — *and still prints the improved total, because
a verdict that hid the improvement would be as unreadable as one that accepted it.*

**The engine reads the evidence commands and never runs one.** Executing a contract-supplied string
from inside the engine was **vetoed**: *a subprocess there is not a tool call and would sit outside
every always-on guard* (DEC-0091, ADR-0143). `open` refuses a command that cannot parse, one whose
program resolves nowhere, and one carrying an unresolved placeholder.
`--baseline-evidence <dimension>=<path>` takes a transcript **the caller produced**, refuses it unless
the declared baseline appears in it, and records that dimension `measured` rather than `declared`.

**The iteration record is what a later reader has instead of the session that wrote it.** The engine
**derives** what it can and **refuses** what it cannot check, *because the alternative — more optional
fields — is the defect itself:* one coordinator ledger held **29 iterations** whose `note` and
`recommended_next` were both already unusable.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `loop` | `.claude/skills/work-loop/scripts/loop.py` | The engine: `open` (declare the contract and the rubric), `iterate` (record an outcome), `score` (one measurement per dimension, weighted total, hard gates, one verdict), `resume` | `python3 -m scripts.loop <sub>` from the skill directory; engine tests are the `ci-local.sh` step *Work-loop engine tests* (`py_tests work-loop`) | `--outcome`, `--decision`, `--blocker`, `--evidence`, `--recommended-next`, `--baseline-evidence <dim>=<path>`. Exits: `0` ok, `1` malformed, **`6` hard gate breached**, **`7` `iterate --decision retain`** |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |
| `blocker-record-check.sh` | `.claude/scripts/blocker-record-check.sh` | That an `escalate` outcome carries all three of blocker, evidence and recommended-next | `ci-local.sh` step *Blocker record*, with its matrix | the ledger |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-task-gate.sh` | `PreToolUse` on writes, `PostToolUse` on `TaskCreate\|TaskUpdate` | task bookkeeping | Names `work-loop` in its guidance — an iteration and a task list are the same bookkeeping seen twice | ADR-0031 |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches bounded-cycle / stalled-loop / resume intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `py_tests work-loop` | the engine's own correctness | always on | `ci-local.sh` step *Work-loop engine tests* | the twelve fields, six outcomes, four stall predicates |
| `blocker-record-check.sh` + its matrix | that an escalation is actionable | always on | `ci-local.sh` steps *Blocker record* and *Blocker record matrix* | all three of `--blocker`, `--evidence`, `--recommended-next` |
| the twelve-field refusal | whether a loop may open at all | **refuses on any missing or empty field** | inside `open` | field presence |
| the evidence-command refusal | whether a rubric dimension may exist | refuses a dimension with no command, an unparseable command, a program that resolves nowhere, or an unresolved placeholder | inside `open` | *a judgment belongs in review rather than in a rubric* |
| `score` exit 6 | whether a hard-gate breach may be outranked by a rising total | **it may not** | distinct exit code | the breach outranks; the improved total is still printed |
| `iterate --decision retain` exit 7 | the retain decision's own hard gate | distinct exit code | inside `iterate` | — |
| the engine's no-subprocess rule | whether the engine may run a contract-supplied string | **vetoed** | DEC-0091, ADR-0143 | *a subprocess there is not a tool call and would sit outside every always-on guard* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `endless` | complements | That decides whether another cycle should start; this describes one cycle | *This skill never decides whether another should start* |
| `gauntlet` | shares a record | The cycle's contract, outcomes, stall predicates, rubric, critic packet and ledger belong here; `gauntlet` maps its own naming onto them | `references/ledger-conformance.md`, DEC-0118 |
| `off-topic` | complements | **`pause` ends this cycle; a displacement suspends work inside a run that is still live**, often in a session that opened no contract at all | Two different senses of stopping |
| `out-of-scope` | complements | An iteration's scope is the contract's; **that skill's deferral record is not a seventh outcome** | A precise refusal to extend the vocabulary |
| `verification-loop` | explicitly excluded | Polling until an exit code flips needs no contract and no ledger | Cited as a boundary |
| `executing-plans` | explicitly excluded | The plan is the sequence; **a Loop is a cycle with a limit** | Cited as a boundary |
| `workflows` | explicitly excluded | *A chain is emitted once, in order. A Loop iterates* | Cited as a boundary |
| wall-clock scheduling | **excluded entirely** | *Nothing here schedules, triggers, or wakes anything* | Stated as "not this skill, at all" |

### Additional Relevant Information

- **Ownership:** the contract, the six outcomes, the rubric and the ledger.
- **Related documentation:** `references/loop-contract.md` (field by field, with what goes wrong when
  each is absent), `references/quality-rubric.md` (the eight keys, the arithmetic, what a `measured`
  provenance does and does not prove, and this repository's default dimension set — DEC-0090),
  `references/iteration-record.md`, `references/stall-detection.md`, `references/critic-pass.md`;
  ADR-0103; ADR-0143 and DEC-0091 (the subprocess veto).
- **Known limitations / technical debt:**
  - **The engine cannot run its own evidence commands**, by decision, so a rubric's numbers are only
    as good as the transcripts the caller supplies — which is why `measured` and `declared` are
    distinguished at all.
  - A ledger is only resumable to the extent the iteration records were written honestly; the engine
    refuses what it can check and nothing more.
- **Observability:** the ledger; `score`'s verdict and its distinct exit codes.
- **Security / compliance:** the no-subprocess veto is a security decision — an engine-run string
  would bypass every always-on guard in the harness.
- **Versioning:** unversioned.

---

## Skill: workflows

**Identifier:** `workflows`
**Repository:** `.claude/skills/workflows/` (harness) · `skills/workflows/` (this mirror)
**Status:** `active`
**Class:** `authored`

---

### Description

**The lifecycle of a reusable chain.** A chain document under `.claude/docs/workflows/` says *which
skills fire in which order* (ADR-0021, superseded on the storage question by ADR-0104); this skill
owns the other half — **who owns the chain, which version is current, and whether it is still the
right one** — by validating, versioning, superseding and retiring the manifest the chain document
carries.

**It does not write the chain's prose, and it never executes a step.**

### Purpose and Use Cases

Fires when a reusable workflow chain is being defined, validated, versioned, superseded or retired —
including finding a chain nobody owns and nobody can say is current.

**Three non-goals, decided rather than merely absent:**

- **No general workflow engine.** `run` resolves a manifest and emits its ordered steps for the agent
  to follow; it executes nothing. *A runtime that executes manifest-supplied strings is a second
  harness growing inside the first* (ADR-0102).
- **A workflow never dispatches a remote run.** `.claude/rules/common/security.md` §*Run CI Locally,
  Never Remotely* blocks that always-on; **this skill does not restate what the guard blocks, and adds
  no path around it.**
- **This skill schedules nothing.** No periodic trigger, no cron, no nightly registration.

**The lifecycle:** `draft` → (`validate`) → `active` → (`revise`/`version`) → `active` →
(`retire --reason` or `retire --superseded-by`) → `retired`, and **`run` on a retired chain is
refused.** A definition needs ten lifecycle fields present with `status: draft`; a revision must
**bump the version, because the manifest is an interface**; a supersede requires that the new id
exists and is not itself retired.

### Scripts

| Script Name | File Path | Description | Execution Context | Inputs / Configuration |
|---|---|---|---|---|
| `workflow` | `.claude/skills/workflows/scripts/workflow.py` | The engine: `validate`, `run` (emit steps; open a run record), `status` (one row per workflow — id, version, lifecycle state, owner), `retire` | `python3 -m scripts.workflow <sub>` from the skill directory; engine tests are the `ci-local.sh` step *Workflows engine tests* (`py_tests workflows`) | `validate [--id ID] [--json]`, `run ID [--dry-run]`, `retire ID --reason … \| --superseded-by NEW`. Findings on stderr |
| `__init__.py` | `scripts/__init__.py` | Package marker | import time | none |

### Hooks

| Hook Name | Type | Trigger Conditions | Behavior / Side Effects | Dependencies |
|---|---|---|---|---|
| `odin-safety-guard.sh` | `PreToolUse` on `Bash\|Edit\|Write\|NotebookEdit` | `gh workflow run`, `gh run rerun`, a `dispatches` API call | **Blocks always-on (Layer 1D)**; names `workflows` in its guidance | none; no posture lifts it |
| `odin-surface-router.sh` | `PreToolUse` on writes | the file being written is a workflow chain document | Names this skill for the surface | none |
| `odin-skill-gate.sh` | `UserPromptSubmit` | prompt matches chain-lifecycle intent | Names this skill in the routing hint | none |

### Gates

| Gate Name | Controls | Default State | Rollout Strategy | Evaluation Logic |
|---|---|---|---|---|
| `workflow.py validate` | that a chain's manifest is well-formed and current | always on | invoked by the skill; engine tests in `ci-local.sh` | ten lifecycle fields; findings on stderr, `--json` for machine use; exit 0 clean |
| `workflow-trigger-check.sh` | that **no workflow file in `.github/workflows/` carries an automatic trigger** | always on | `ci-local.sh` step *Workflow triggers are inert* **and** `PRE_PUSH_GATES` (114ms) | an **allow-set of one name** (`workflow_dispatch`) rather than a block-list — *a block-list silently permits every trigger GitHub adds after it was written* (ADR-0117) |
| `workflow-trigger.test.sh` | the trigger checker's matrix | always on | `ci-local.sh` step *Workflow trigger matrix* | — |
| safety-guard Layer 1D | whether a run may be dispatched remotely | **blocked always-on** | `.claude/hooks/odin-safety-guard.sh` | `gh workflow run`, `gh run rerun`, `dispatches`. **Reading a run — `gh run view\|list\|watch` — is unrestricted** |
| the retirement refusal | whether a retired chain may run | **refused** | inside `run` | lifecycle state |
| the version bump | whether a revision may keep its version | must bump | inside `validate` after a revision | *the manifest is an interface* |

### Integrations with Other Skills

| Integrated Skill | Nature | Reason | Coupling Notes |
|---|---|---|---|
| `.claude/scripts/ci-local.sh` | complements | **The repository's gate chain is one script with an exit code, not a manifest** | Explicitly not this skill's subject |
| `dynamic-workflow-mode` | complements | Whether a task-local harness is warranted at all is a judgment about **whether to build**; this is the lifecycle of one already built | Cited as a boundary |
| `automate` | receives from | An automation at the `routed` level becomes a step in a chain, and its rollback bumps the chain's manifest version | Ordering: level decided there, manifest changed here |
| `endless` | explicitly excluded | This emits one chain's steps once; continuation across items is a different problem | Cited as a boundary |
| `tidy` | complements | **Retiring a workflow is a lifecycle transition with its own enforced refusal, not a filesystem removal** | `tidy` defers to this skill and never issues a `remove` verdict for a chain |
| `roadmap` | explicitly excluded | *A workflow is how a class of work is done, never which work is next* | Cited as a boundary |
| the chain's owning skill | defers to | **The prose says how the work is done; this skill only asserts that the manifest in the same file is well-formed and current** | A precise division inside one file |

### Additional Relevant Information

- **Ownership:** the manifest and its lifecycle; the chain's prose belongs to the skill that owns the
  work.
- **Related documentation:** `references/lifecycle.md`, `references/manifest-schema.md`; ADR-0021
  (chain documents), ADR-0104 (superseding it on the storage question), ADR-0102 (no general workflow
  engine), ADR-0117 (no automatic triggers; the allow-set of one).
- **Known limitations / technical debt:**
  - **`run` emits steps for an agent to follow and verifies nothing about their execution** — the
    manifest is a contract with a reader, not a runtime.
  - The workflow files under `.github/workflows/` are **kept deliberately** as the specification the
    local scripts are checked against, and as a human's visible escape hatch — which means the
    repository ships files that intentionally never run.
  - A consequence worth stating: **`main` has no required status checks**, because nothing reports
    one. The gate moved to the push (`.claude/scripts/pre-push`), not away.
- **Observability:** `status` — one row per workflow; `validate --json`.
- **Security / compliance:** the remote-dispatch prohibition is a security boundary enforced
  always-on, and the trigger checker uses an allow-set precisely so it cannot be outgrown.
- **Versioning:** the **manifest** is versioned, and a revision must bump it — one of the few
  versioned artefacts in the corpus.

---

## Appendix — how this document was derived

Every entry above was written from the skill's own files. The commands that produced the structural
sections, so a reader can re-derive rather than trust:

```sh
# membership and class
ls -1 projects/Odin-Skills/skills
bash projects/Odin-Skills/scripts/sync-from-odin.sh --check --odin "$PWD"
. .claude/scripts/lib/skill-provenance.sh && sp_list "$PWD"     # name  class  origin  mirrored

# which hooks name a skill  (grep -qwF, not an anchored alternation — see the note below)
for m in $(ls -1 projects/Odin-Skills/skills); do
  for h in .claude/hooks/*.sh; do grep -qwF -- "$m" "$h" && printf '%s\t%s\n' "${h##*/}" "$m"; done
done

# which ci-local.sh step runs a skill's gate
grep -nE '^\s*step ' .claude/scripts/ci-local.sh

# which gates run before a push, with their declared costs
sed -n '/PRE_PUSH_GATES=(/,/^)/p' .claude/scripts/pre-push
```

**One caveat about that second command, recorded because it changed a number in this document.** The
natural way to write a whole-word name sweep — `grep -E '(^|[^a-z-])NAME([^a-z-]|$)'` — returns
**zero matches** under `ugrep`, which is what `grep` resolves to on the host this was written on. The
same file and term match under `[^a-z-]NAME[^a-z-]` and under `-w`. A sweep written the first way
reports a hook as naming no skills, silently; it produced a "36 of 39" reading of
`odin-skill-gate.sh` where the true answer is 39 of 39. **Use `grep -qwF`.**

---
