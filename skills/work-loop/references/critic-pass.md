# The critic pass — a verdict the builder cannot author

A builder's report of its own work is not evidence. Fresh-context critique already existed in this
harness — `adversarial-reviewer`, `plan-adversary`, `code-reviewer`, the `not-impressed` skill — but
nothing controlled the channel a verdict arrived through. An iteration could carry
`--critic-verdict PASS` written by the same call that recorded the work.

The critic pass closes that channel. It has two halves, and **which half is mechanical and which is
held by judgment is stated here rather than blurred.**

## The handshake

```sh
cd .claude/skills/work-loop

# 1. The engine assembles the packet and records a single-use brief. Produce the change
#    scope yourself — the engine runs no git — and hand it over, so the diff is checked
#    against the change rather than trusted to be it.
git show "$SHA" --stat > /tmp/scope.txt
python3 -m scripts.loop brief --root ../../.. --session "$SID" \
        --diff-file /tmp/change.diff \
        --change-scope /tmp/scope.txt \
        --verification-file /tmp/suite.txt --json

# 2. A context that did not build the change reads the packet and returns a verdict.
#    Dispatch `adversarial-reviewer` — it is a fresh context by construction, it reports
#    and never edits, and it already carries the prompt-defence and voice blocks.

# 3. The verdict is recorded, bound to the brief, which is spent by this iteration.
python3 -m scripts.loop iterate --root ../../.. --session "$SID" --outcome continue \
        --action tighten-guard \
        --evidence-path /tmp/suite.txt \
        --critic-brief 4f2a91c0d3b17e58 \
        --critic-verdict REVISE \
        --critic-next "assert the guard's refusal, not merely that it runs"
```

## The packet

`brief` emits exactly seven keys, and a test asserts the key set:

| Key | What the critic gets |
|---|---|
| `brief_id` | The sha256 of the diff, the verification output and the rubric, truncated to 16 hex |
| `diff` | The change under review, verbatim |
| `verification` | The verification output, verbatim |
| `rubric` | The contract's own dimensions — weights, thresholds, hard-gate flags |
| `baseline` | The previous measured iteration's readings, or the rubric's declared baselines |
| `scope` | What the diff was found to cover: `provenance` (`verified` / `unverified`), `declared_paths`, `diff_paths`, `undeclared_paths` |
| `verdicts` | `PASS` `FAIL` `REVISE` `REVERT` `ESCALATE` |
| `asks` | Compare before versus after; name regressions and unsupported claims; return one verdict and the single most valuable next improvement; say which evidence supports it |

**There is no `summary` key, and there will not be one.** A summary is the builder's case for its own
work, and a critic that receives the framing reviews the framing.

## The binding

The `brief_id` is **derived from the artifacts, not assigned**. Change the diff, the verification
output or the rubric and the id changes — which is what makes a re-used brief detectable rather than
merely discouraged.

`iterate --critic-verdict` refuses, before anything is written:

| Refused | Why |
|---|---|
| A verdict with no `--critic-brief` | The wave-2 shape: a verdict written by the builder in the same breath as the work |
| A brief id the engine never emitted | A verdict carrying an unknown id is about a packet nobody assembled |
| A brief when none is pending | Also how a **spent** brief is caught on its second use |
| A verdict with no `--critic-next` | The critic names the single most valuable next improvement |
| A verdict with no `--evidence-path` | Inherited from the record's own rule |

**A brief is single-use.** A verdict is about one change; re-using a brief would attach change N's
judgment to change N+1 — a stale verdict wearing a fresh timestamp.

**The obligation runs one way.** An iteration with no verdict needs no brief and is untouched.

## `brief` refuses what it cannot read

An unreadable diff or verification file exits **8**, naming the file. So does an **empty** one — the
same defect from the other side, because a packet with an empty diff section has the critic return a
confident verdict about a change it never saw. An unreadable or empty `--change-scope` transcript
exits 8 for the same reason.

A channel that could not be read is a finding, never a silence.

## `brief` refuses a diff that does not cover the change

Readable and non-empty were the only tests, and **a one-file excerpt of a nine-file commit passes
both**. That is not a hypothetical: it is what the critic pass's own second use produced. The tests,
both reference documents, the CHANGELOG and four mirror files were present in the packet only as
names inside a stat block, and the reference above said the `diff` key holds "the change under
review, verbatim". The critic noticed and read the commit from the repository — the good outcome,
and not one a design may rely on.

`--change-scope <path>` takes a transcript **the caller produced** — `git show <sha> --stat`, or
`git show <sha> --name-only` — and the engine cross-checks it:

| Condition | Exit |
|---|---|
| A path the transcript declares is absent from the diff | **9**, naming every one |
| An abbreviated `.../` path matching more than one diff path | **9** — an ambiguous path is not a path |
| A transcript that parses to no paths at all | **9** — the caller passed the wrong file |
| The diff covers every declared path | 0, `scope.provenance: "verified"` |
| No `--change-scope` at all | 0, `scope.provenance: "unverified"` |

**The engine runs no `git`.** A subprocess spawned inside `loop.py` is not a tool call, so it would
run outside Layers 1D, 1E and 1G of `.claude/hooks/odin-safety-guard.sh` — a PreToolUse hook.
ADR-0143 vetoed executing a contract's `evidence_command` for that reason, and DEC-0093 extends the
veto here: a *fixed* command carrying an operator-supplied revision range is still argv, and
`git diff --output=<path> <range>` writes an arbitrary file. So the caller runs the scope command
through its own tool path, where every guard applies, exactly as `--baseline-evidence` already works.

**The flag is optional, and its absence is recorded rather than silent.** `scope.provenance:
"unverified"` says nothing was established either way, and the packet's asks tell the critic to read
it first. Requiring the flag would red every existing caller at once — the blast radius ADR-0143
rejected for the same reason.

## What this proves, and what it does not

**Mechanical:** no verdict can be recorded that is not bound to a packet the engine assembled from
the actual diff, the actual verification output and the contract's own rubric — and each such packet
buys exactly one verdict.

**The binding's subject is the packet, never the change.** `brief_id` proves "this verdict is about
this packet". It proves "this packet is the change" only as far as the packet's `scope` block says
it does: with a declared scope, the diff covers every path the transcript named; with
`provenance: "unverified"`, nothing was established at all. This sentence is the one the reference
was missing — it described the binding while the packet's *completeness* went unchecked and
unmentioned, which is how a verdict about a third of a change came to carry an id that reads like a
review of all of it.

**Also not mechanical:** that the transcript describes the change under review. A caller can hand
over the stat block of a different commit. Nothing in a non-executing engine closes that, and a
check that claimed to would be the failure named two paragraphs down.

**Not mechanical, and no gate here claims otherwise:** that a *different context* produced the
verdict. No predicate over repository state can establish it. A check that claimed to would be worse
than none, because a rule that looks enforced and is not is indistinguishable from an enforced one to
everybody who reads it.

That half is a **review criterion**: dispatch `adversarial-reviewer` with the packet. It is a fresh
context by construction — that is the whole reason it exists — it reports and never edits, and the
harness audit already checks that it keeps its voice and prompt-defence blocks. Reusing it beats a
second critic agent that would be one more thing to keep in sync for no new capability.

## What the engine still does not do

It runs no critic and dispatches nothing. That boundary is stated in the module's own docstring and
this item did not move it: the engine packages, and it refuses. Because the packet is JSON on stdout,
any dispatcher can be layered above it without the engine changing.
