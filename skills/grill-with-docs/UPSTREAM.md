# Upstream: `grill-with-docs`

| | |
|---|---|
| Upstream | https://github.com/mattpocock/skills (`skills/engineering/grill-with-docs/`) |
| License | MIT — Copyright (c) 2026 Matt Pocock (see `LICENSE` in this directory) |
| Fork point | `8b78b53` (2026-08-13) |
| Modified by Odin | **Yes — the stub was replaced with a real skill body** |

## What upstream ships

A 245-byte delegation stub, in full:

```
Run a `/grilling` session, using the `/domain-modeling` skill.
```

plus `agents/openai.yaml` carrying `policy: allow_implicit_invocation: false`, and frontmatter
carrying `disable-model-invocation: true`.

## Why Odin forked it

The 2026-08-15 elicitation audit (`.claude/docs/audits/2026-08-15-elicitation-tdd.md`, findings
D-F1 through D-F5) found four defects that a 245-byte stub structurally cannot fix:

1. **The harness named a skill the agent was forbidden to invoke.** `disable-model-invocation: true`
   made the Skill tool refuse it — reproduced in the audit session, from the tool's own refusal
   message — while Odin's contract named it in seven places, two of them load-bearing: a satisfier
   of the plan bar's process-skill precondition, and a per-iteration option in the one execution
   mode that has no human to fall back on. Removed.
2. **A stub cannot assert its dependencies loaded**, and upstream's own documentation names partial
   loading as this skill's most reported problem: `grilling` loads, `domain-modeling` does not, and
   the result is a good interview with no paper trail. Silent, and plausible-looking — the worst
   shape for an unattended run. The fork opens with a loud assertion step.
3. **The delegation target writes ADRs to the wrong tree.** `domain-modeling` writes to `docs/adr/`;
   Odin's ADRs live in `.claude/docs/adr/`, and a second tree would collide with the reserved
   numbering ranges that index holds. The fork pins the path for its own delegation. The defect in
   `domain-modeling` itself is untouched — that skill stays vendored and byte-identical.
4. **It did not do the thing Odin routes to it for.** Three routing surfaces promise a requirements
   interview over a heavy document corpus; neither `grilling` nor `domain-modeling` verifies a claim
   against source material. The fork adds that pass — cite-or-flag, with four verdict labels
   (supported / contradicted / gap / weak) — which is the capability that made "grow" the better
   branch than "retire the stub".

Delegation itself was kept (audit fork DF-4): `grilling` and `domain-modeling` stay vendored and on
upstream's refresh path. The fix for silent partial loading is a loud first step, not duplicating
1.9 KB of another skill into a fork forever.

## What a refresh must not clobber

**All of `SKILL.md`.** There is no line of upstream's stub left in it. A `--refresh` that replaced
this file would restore the 245-byte stub, re-add `disable-model-invocation`, and silently undo
every item above. Protection is derived from the existence of this directory
(`vendor-skills.sh` → `protected_set()`), and asserted against the real tree by
`.claude/tests/vendor-refresh.test.sh`.

`agents/openai.yaml` is also modified — `allow_implicit_invocation` is now `true`, matching the
frontmatter change. Leaving it `false` would reproduce the same defect on the Codex runtime.

## Divergence from current upstream

None tracked beyond the fork itself. If upstream ever grows the stub into a real skill, that body is
worth reading against this one — but it is a merge, never a copy.
