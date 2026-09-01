# ADR-0002: Split licensing — authored skills dual-licensed, forks under their upstream

## Status

Accepted — 2026-09-01 (records a decision in force since the repository was assembled)

## Context

This repository redistributes two kinds of work under one roof, and they cannot carry the same
licence:

- **Skills authored for Odin.** No upstream exists. They are mostly prose — a `SKILL.md`, its
  references — with some shell and Python alongside.
- **Skills forked from upstream projects.** A real upstream exists, published under its own terms,
  and Odin's copy diverges from it. `impeccable` is Apache-2.0; four skills come from `superpowers`
  under MIT; one upstream (`rules-distill`) published **no LICENSE file at all**.

The arrangement was already implemented and enforced before it was written down. `NOTICE` states it,
`docs/PROVENANCE.md` tabulates it per skill, `LICENSE-CC-BY-SA-4.0` and `LICENSE-MIT` sit at the
repository root, each fork directory ships its upstream `LICENSE` and an `UPSTREAM.md`, and
`scripts/validate-skills.sh` fails a publish where any of that is missing. What did not exist was the
record of *why* — so the arrangement was reconstructable only by reading the validator, and a future
contributor simplifying "two licence files at the root" had nothing to read first.

[ADR-0001](0001-distribution-monorepo-and-per-skill-repos.md) lists "licensing and attribution must
survive redistribution in both shapes" as a decision driver and then decides something else. This
record closes that gap.

## Decision Drivers

- Redistribution must be lawful in both shapes: the bundle, and each per-skill repository split out
  of it.
- Prose and code have different reuse expectations. A share-alike licence on prose keeps derived
  skill text open; the same licence on a helper script makes the script awkward to vendor.
- A fork's terms are the upstream's to set, not this repository's.
- An upstream that granted nothing must not be represented as having granted something.
- Whatever the rule is, `scripts/validate-skills.sh` has to be able to check it per skill.

## Considered Options

### Option 1: One licence for the whole repository

Pick a single permissive licence and apply it everywhere.

- **Pros**: One file, one sentence in the README, nothing per-skill to maintain.
- **Cons**: Unlawful for the forks — an Apache-2.0 work does not become MIT by being copied, and
  relicensing someone else's skill is the failure mode that matters. Also loses share-alike on the
  authored prose, which is the licence chosen deliberately for it.

### Option 2: Per-skill licence with no repository-level default

Every skill directory carries its own `LICENSE`, authored ones included.

- **Pros**: Uniform mechanism; a per-skill split carries the licence with it automatically.
- **Cons**: Twenty-plus copies of the same two files for the authored set, drifting the first time
  one is edited. Says nothing about the prose/code distinction, which is the whole reason the
  authored set is dual-licensed.

### Option 3: Dual-licensed authored set at the root, upstream terms per fork

Authored skills: prose CC-BY-SA-4.0, accompanying code MIT, declared once at the repository root.
Forks: the upstream licence, shipped verbatim inside the skill directory, with an `UPSTREAM.md`
stating the local delta. Where an upstream published no licence, the fork says so and ships a
`NOTICE` in place of a licence it was never granted.

- **Pros**: Lawful in both shapes. One statement per authored skill rather than one file per skill.
  Each fork carries its own terms into a per-skill split, which is where they are needed. The
  no-licence case is stated rather than papered over.
- **Cons**: Two rules instead of one, so `docs/PROVENANCE.md` must say which skill is which, and the
  validator must enforce it. A reader must consult a table to answer "under what terms may I use
  this?".

## Decision

**Option 3.**

- **Authored skills** — prose under CC-BY-SA-4.0, code shipped alongside under MIT,
  `Copyright (c) 2026 RubyEyedReaper`. Declared once in `NOTICE`, `README.md` and the root
  `LICENSE-CC-BY-SA-4.0` / `LICENSE-MIT` files.
- **Forks** — the upstream licence, unchanged, shipped as `LICENSE` **inside the skill directory**,
  with `UPSTREAM.md` naming the upstream, its audited HEAD, and the local delta. Apache-2.0 forks
  additionally carry the section 4(b) modification notice in the root `NOTICE`.
- **An upstream with no published licence** is declared as such in that fork's `UPSTREAM.md`, and the
  directory ships a `NOTICE` instead of a licence. Nothing is inferred in the absence of a grant.
- **`docs/PROVENANCE.md` is the per-skill record** of which rule applies, and
  `scripts/validate-skills.sh` cross-checks it against `skills/` on every publish.

## Consequences

**Positive**

- Both distribution shapes are lawful without a per-shape argument: a per-skill split of a fork
  carries that fork's licence in the directory being split.
- The prose/code split is stated once, at the root, rather than copied into every authored skill.
- The un-licensed upstream is visible in the artefact rather than resolved by assumption.

**Negative**

- Answering "what licence is this skill under?" needs `docs/PROVENANCE.md`, not a glance at the
  directory. The row is the record, so a skill added without one is a licensing gap.
- Two authored licences mean a contributor must know which half of a skill they are touching.

**Mitigations**

- `scripts/validate-skills.sh` fails a publish where a fork lacks `LICENSE`/`UPSTREAM.md` or a skill
  lacks a provenance row, so the gap is loud rather than latent.
- `NOTICE` restates the two rules in six lines for a reader who never opens the table.

## Related

- [ADR-0001](0001-distribution-monorepo-and-per-skill-repos.md) — the distribution shapes this
  licensing has to survive.
- [ADR-0003](0003-mirror-membership-rule.md) — which skills are in the set that this licensing
  applies to.
- [`../PROVENANCE.md`](../PROVENANCE.md) — the per-skill record.
- [`../../NOTICE`](../../NOTICE) — the redistribution notice, including Apache-2.0 § 4(b).
