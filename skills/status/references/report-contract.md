# The report contract — one line, 300 codepoints, computed every time

`.claude/scripts/status-report.sh` renders it. `.claude/tests/status-report.test.sh` holds a case per
rule below. Nothing here is a style preference; each line is a matrix case.

## What the bound is measured over

| Question | Answer | Why |
|---|---|---|
| Unit | **Unicode codepoints**, not bytes | The bound exists for a human's screen. Bytes count every `·` and `—` in this house style two to three times over, so a truthful line would be refused for using the separators the rest of the tree uses |
| Scaffolding | **Included** | A bound that excludes the template bounds a string nobody sees |
| Trailing newline | Excluded | One newline, never counted |
| `--json` | **Unbounded** | Machine output has no screen to overflow. Bounding it is how a JSON contract quietly becomes lossy |
| Default | 300 | `--bound N` exists for the matrix, and for a caller with a narrower surface |

**Recorded residue:** a terminal renders *grapheme clusters*, not codepoints. A name carrying an
emoji or a combining mark measures short here and prints wide. Computing clusters needs a dependency
this tree does not carry, so the gap is stated rather than closed — see
`ci/rule-enforcement.md` § Three Honest Outcomes.

## The shape

```
odin · daemon {daemon} · sessions {sessions} ({live} live, {idle} idle, {blocked} blocked, {absent} absent) · tasks {tasks} · agents {agents}{detail}
```

The template is [`report-template.txt`](report-template.txt), read by the renderer at run time.
One copy: a second in prose drifts, and the looser copy wins.

Two halves with different rights:

- **The prefix — everything before `{detail}` — is never elided.** It carries the counts.
- **`{detail}` is severity-ordered and elided from the tail**, behind an announced marker.

## Elision, never a silent cut

1. **Counts survive elision.** The totals are in the prefix, so dropping a detail row never changes a
   number. A report whose numbers move when it is shortened is lying about the fleet.
2. **Severity ordering.** `blocked` and `absent` rows sort ahead of `live`, which sorts ahead of
   `idle`. The row that gets dropped is never the failing worker. This ordering is what makes elision
   safe — it is the mechanism, not a nicety.
3. **The elision announces itself** — ` (+K more)`, with `K` exact, and the marker's own length
   counted inside the budget.
4. **If the prefix alone will not fit, nothing is cut** — the renderer emits the prefix and exits 5.
   A report that cannot state its own totals is not a report, and shortening it further would mean
   dropping a count.

## `unknown` is never `0`

A count that could not be obtained renders `?`, and `?` occupies the prefix, never the elidable tail.
An invented `0` reads as a finished fleet — the failure ADR-0072 exists over, and the reason
`fleet-health.sh` prints `unknown` for its own subordinate probes.

`agents ?` is the steady state, not a defect: the runtime exposes no channel that enumerates a
session's in-context subagents. The field is present and honest rather than absent and assumed.

## Channel order — inherited, never re-derived

1. `fleet-health.sh` first. Its exits are forwarded **unchanged**: `2` daemon down, `3` registry
   unreadable. A registry outlives the daemon that served it, so nothing downstream is believed until
   this answers.
2. The roster (`ODIN_FLEET_AGENTS_CMD`, default `claude agents --json`).
3. Per-session socket existence under `ODIN_FLEET_DAEMON_DIR`. A roster row **plus** its own socket
   is presence; a row alone is `absent`.
4. The roadmap's in-progress claims, for `tasks`. Unreadable → `?`, never `0`.

## Exit codes are the interface

| Code | Means |
|---|---|
| 0 | Rendered; every channel answered |
| 1 | Rendered, with a finding — a channel returned `?`, or a session is registered with no socket |
| 2 | Daemon down — forwarded from `fleet-health.sh` |
| 3 | A channel could not be read — forwarded, or the roster command failed or did not parse |
| 5 | The prefix alone exceeds the bound |
| 64 | Usage |

**An empty roster is two different facts.** A roster that parsed and holds no sessions renders
`sessions 0` and exits 0 — the daemon answered, and zero is the reading. A roster command that failed,
returned nothing, or did not parse exits 3. `count: 0, exit 0` on an unread channel is how a check
goes quiet without ever failing.
