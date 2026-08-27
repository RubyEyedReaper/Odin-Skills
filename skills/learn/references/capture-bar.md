# The capture bar

Five refusal classes, evaluated highest-harm first, **each with its own exit code**.

```sh
python3 -m scripts.capture_bar check --candidate cand.json --root ../../.. --corpus <dir>
```

The candidate is a JSON object with a non-empty `title` and `body`; any other field is carried
along and scanned. Accept prints `{"outcome": "record", …}` and exits 0.

| # | Class | Exit | Keyed on |
|---|---|---|---|
| 1 | credential | 3 | The record's **key names**, and its **values** by shape |
| 2 | personal | 4 | Value shape: email, national-id, phone, postal address |
| 3 | chatter | 5 | Session **deixis** — phrases whose referent is the conversation |
| 4 | duplicate | 6 | Token-set similarity ≥ 0.70 against a record in `--corpus` |
| 5 | derivable | 7 | ≥ 85% of the record's distinctive terms present on **one line** under `--root` |

## Why the codes differ

Five refusals sharing one non-zero code report "no" and nothing else. The remedies are not
interchangeable: a credential is removed, a duplicate is **merged**, chatter is rewritten into a
durable claim, and a derivable record is deleted in favour of the line it restates. A caller that
cannot tell them apart cannot do any of those automatically.

`duplicate` is the one refusal that carries a recommended outcome — `"outcome": "merge"`, naming the
record it collides with. The others carry `null`, because the candidate is not captured at all.

## Why this order

Highest harm first. Once secret material is present, nothing else about the record matters, and the
record is refused before any check that would need to read more of it or write a comparison to a
log. The order is `CLASS_ORDER` in `scripts/capture_bar.py`, and a record that is both a secret and
a duplicate is refused as a secret.

## Class 1 — credential

Two independent branches:

- **By key name.** A field whose normalised name contains `password`, `token`, `secret`, `api_key`,
  `private_key`, `authorization`, `client_secret` and the rest of `CREDENTIAL_KEYS`.
- **By value shape.** AWS access-key ids, GitHub tokens, vendor `sk-` keys, Slack tokens, PEM
  private-key blocks, `Bearer` headers, credentials embedded in a URL, and JWTs — each a **named**
  pattern.

**The matched value never leaves the detector.** The refusal names the field and either the key
marker or the pattern name; the match itself is discarded after the boolean. Masking is refused as
a design: a masked secret is still a secret in every log the caller writes, and the mask is a guess
about which half mattered.

The two branches are separate on purpose, and the suite exercises each **alone**. A fixture whose
credential-shaped value also sits under a credential-named key can only ever prove that one of them
fired — disabling either check leaves such a suite green.

**Deliberately not caught:** the word. A record *about* credential handling — "a secret surfaced
during a task never enters operational recall" — carries `secret`, `password` and `token` in its
prose and is accepted. The key branch reads keys, never values; the value branch reads shapes, never
vocabulary. That negative control is in the suite.

## Class 2 — personal

Reported by class name, never by match, for the same reason as class 1. Four shapes: `email-address`,
`national-id` (a `NNN-NN-NNNN` run), `phone-number` (separator-bearing, so a version string is not
one), `postal-address`.

**Deliberately not caught:** a name. There is no mechanical shape for "this is a person's name", and
a detector that guessed would refuse every record naming a tool's author. Names are the bar's
judgement half, stated here so nobody reads the script's silence as a verdict.

## Class 3 — task chatter

A record that is true only inside the conversation that produced it. Keyed on **deixis** — `this
session`, `as discussed above`, `just ran`, `right now`, `let me`, `the previous message` — phrases
whose referent is the conversation rather than the tree.

**Not keyed on the noun.** `session` is harness vocabulary, and "an autonomous posture ticket is
scoped to one session" is durable knowledge. Refusing the noun would refuse a large fraction of
everything this repository knows about itself. Negative control in the suite.

## Class 4 — duplicate

Jaccard similarity over distinctive tokens (lowercased, ≥3 characters, stopwords removed) between
the candidate's `title + body` and each file in `--corpus`, threshold 0.70. Symmetric, because both
sides are records of comparable length.

A candidate with fewer than four distinctive tokens is **not judged** — below that, similarity
scores are noise, and refusing on noise is how a bar loses its users.

## Class 5 — derivable

**Containment**, not Jaccard: the fraction of the *record's* distinctive tokens that appear on a
single line under `--root`, threshold 0.85. Asymmetric on purpose — a long line that contains the
whole record is a restatement of it, and Jaccard would score that low for the length mismatch
alone.

**Deliberately not caught: inference.** A fact assembled by reading three files is a *finding*, not
a restatement, and a check that refused it would refuse nearly every genuine finding about the
harness — which necessarily carries the harness's own vocabulary. A check that fires on everything
is a false positive, not a coverage win. The suite carries the negative control this was tuned
against: a real finding about branch landedness, in a fixture tree whose `CLAUDE.md` talks about
topic branches, is accepted.

Lines over 600 characters are skipped as data blobs rather than prose somebody could have restated.

## A class with no input is announced, never silently passed

`--corpus` and `--root` are optional. Without them the corresponding class reports `"skipped"` in
the stdout payload **and** says so on stderr. A check that quietly passes when its subject is
missing is indistinguishable from one that agrees with every input — and the accept payload names
all five classes with their state, so a caller can see exactly what was examined.

## Thresholds

`--duplicate-threshold` and `--derivable-threshold` are arguments, not constants to be edited. The
defaults (0.70 and 0.85) are what the suite's positive and negative controls were chosen against;
moving one without re-running both controls replaces a measured predicate with a preference.
