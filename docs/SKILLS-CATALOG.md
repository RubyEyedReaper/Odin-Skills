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
