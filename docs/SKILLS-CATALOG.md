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

A skill with none of the three still gets the prescribed sentence,
`This skill does not use any feature gates.`

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
