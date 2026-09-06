# The one-implementation registry

`.claude/scripts/one-implementation.conf` — read by
[`one-implementation-check.sh`](../../../scripts/one-implementation-check.sh). Tab-separated rows,
`#` comments ignored.

## Row grammar

```
owner   <lib-path>   <symbols>            <signature|->            <label>
exempt  <file-path>  <lib-path>           <reason>
```

| Field | Means |
|---|---|
| `<lib-path>` | repository-relative, e.g. `.claude/scripts/lib/tracked-files.sh` |
| `<symbols>` | space-separated function names the library owns. Arm A: a file naming one of these outside comments, quoted spans and heredocs, without sourcing the library, has a second answer |
| `<signature>` | an extended regex matching the predicate's own shape, for a restatement under other names. Arm B. `-` means none is declared, and the gate prints `UNCHECKED` for the row on every run |
| `<label>` | what the predicate answers, in one phrase |

## Adding an owner row

A library earns a row by **claiming sole ownership in its own header** — not by being useful. The
gate reads three phrasings the live headers use (`One answer, sourced …`, `One answer to: …`,
`the ONE implementation …`), and asserts the reverse direction: a claiming library with no row is
`UNREGISTERED-OWNER`, a row whose library no longer claims is `STALE-REGISTRY`.

Membership is **never** chosen by how noisy a candidate measured. A subject set selected for
greenness is a tautology with a registry, and the first library it would exclude is
`tracked-files.sh` — the corpus owner every gate depends on. What varies per row is which arms it
enables.

## Adding a signature — the bar

A signature is written when someone has **measured** it, not when someone can imagine it. Guessed
raw forms for the libraries that ship `-` measured 8 to 21 findings out of 203 files; a gate at that
rate is switched off within a week and takes its true positives with it.

Measure before adding:

```sh
bash .claude/scripts/one-implementation-check.sh .
```

Add the row, re-run, and read every finding it produces. A signature that fires on files nobody
considers wrong is not ready; leave `-` and the gate keeps saying so.

## Adding an exemption

Keyed on **both** the file and the owner, so exempting a file from one predicate leaves it checked
against every other. The reason is mandatory and must name why the copy cannot source the owner —
an exemption with no reason is the finding restated as configuration.

The path must exist. An exemption naming a file that has moved is `STALE-REGISTRY`, so it is removed
rather than forgotten; that is what stops exemptions accumulating until the gate asserts nothing.

Worked example, the tree's one real exemption:

```
exempt	.claude/skills/rules-distill/scripts/scan-rules.sh	.claude/scripts/lib/always-on-rules.sh	ships as a published plugin and cannot source a path under .claude/scripts/; L2's conformance case holds the two implementations to agreement (DEC-0040)
```

That copy cannot be deleted — the skill ships to consumers outside this repository — so the
exemption records the same decision `context-budget.test.sh` already made, in the same words, rather
than reaching a second one.

## The escape hatch already in the tree

A line carrying `predicate-owner:` is skipped on arm B. That marker was introduced by
`context-budget.test.sh` for its own restatement check and is honoured here rather than replaced: a
second spelling of one idea would be this gate's own failure.

## What a green run does not mean

Exemptions and unchecked rows print on passing runs, deliberately. A green run means *what is
checked* is clean — seven of eight rows check arm A only, and the gate names each of them every
time it runs.
