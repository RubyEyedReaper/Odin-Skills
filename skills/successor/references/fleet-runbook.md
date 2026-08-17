# Fleet runbook

Command sequences per phase, then the facts that cost something to learn. Everything here
orchestrates `.claude/scripts/odin-relay.sh`; nothing here reimplements it.

Notation: `<worker>` is a short slug (`c1`, `b3`), `<class>` a branch class (`skills`, `harness`,
`docs`, `adr`, `mcp`, `deps`).

## 1. Provision

One worktree per worker, cut from `main`:

```sh
git -C "$REPO" fetch origin
git -C "$REPO" worktree add ../odin-wt-<worker> -b <class>/<topic> origin/main
cp "$REPO/.claude/settings.local.json" ../odin-wt-<worker>/.claude/settings.local.json
```

`settings.local.json` is gitignored and holds this machine's permission allowlist. A worker without
it stalls on a permission prompt with nobody there to answer.

Confirm the worktree can resolve a harness before writing a handoff for it:

```sh
test -f ../odin-wt-<worker>/CLAUDE.md && ls ../odin-wt-<worker>/.claude/skills | head -1
```

Both must succeed. The relay enforces the same predicate at launch (ADR-0056); checking now turns a
launch-time refusal into a provisioning step.

Reserve ids for the whole fleet in one pass, then write each worker's allocation into its handoff:

```sh
ls .claude/docs/adr/ | tail -3          # next free ADR number
python3 -m scripts.roadmap next          # roadmap items, qualified ids
```

Reserved-but-unused numbers are cheap: leave a placeholder file naming the owner, and retire it in
the close-out commit if the worker concludes it was not needed.

## 2. Launch

```sh
HANDOFF="$(cd .claude/.runtime/handoff && pwd)/<file>.md"
.claude/scripts/odin-relay.sh --handoff "$HANDOFF" --name "<worker>: <topic>" --dry-run
.claude/scripts/odin-relay.sh --handoff "$HANDOFF" --name "<worker>: <topic>"
```

Dry-run first, always: it runs every refuse gate and prints the exact argument vector without
spending a session. Launch from a harness root — the repository root or one of its worktrees.

## 3. Monitor

```sh
claude agents --json                       # id, sessionId, state, cwd
claude logs <id>                           # recent output from one worker
git ls-remote --heads origin '<class>/*'   # branch movement, the second signal
```

Watch loop — poll both signals, emit only on a transition:

```sh
while :; do
  claude agents --json > /tmp/fleet.now
  git ls-remote --heads origin >> /tmp/fleet.now
  diff -q /tmp/fleet.prev /tmp/fleet.now >/dev/null 2>&1 || {
    date -u +%FT%TZ; diff /tmp/fleet.prev /tmp/fleet.now || true; }
  cp /tmp/fleet.now /tmp/fleet.prev
  sleep 300
done
```

Escalation:

| Observation | Read it as | Do |
|---|---|---|
| `running`, no branch push, quiet in logs | working, or wedged — undecided | `claude logs <id>` and read the last turn |
| logs repeating the same tool call | wedged | `claude stop <id>`, amend the handoff, relaunch |
| branch pushed, session idle | finished | move to integration |
| **every** worker silent at once | a shared dependency died | check it before touching any session |
| session gone from `agents --json` | exited or evicted | read its branch; the work may be pushed |

A relaunch always uses an **amended** handoff. The same document reproduces the same stall.

## 4. Integrate — coordinator only

Per branch, serialized, in a fixed order (registry-touching branches last):

```sh
# 1. scope-diff against the declared authorization
git diff --name-only origin/main...<branch>

# 2. rebase in the worker's worktree, resolve there
git -C ../odin-wt-<worker> rebase origin/main

# 3. gate the MERGED result, not the pre-rebase branch
bash .claude/scripts/ci-local.sh --fast
bash .claude/scripts/harness-audit.sh

# 4. land by fast-forward; main stays linear
git -C "$REPO" merge --ff-only <branch>
git -C "$REPO" push origin main
```

Any file outside the branch's `Edit only:` line is a finding to resolve before the merge, not after.

Shared registries — inventory counts, category lists, generated roadmap renders — are **recomputed**
after the last branch lands, never textually merged. Two workers each bumping the same `# expect N`
produce a conflict whose "resolution" is a number that was never counted.

## 5. Teardown

```sh
git -C "$REPO" worktree remove ../odin-wt-<worker>
git -C "$REPO" branch -d <class>/<topic>
git -C "$REPO" push origin --delete <class>/<topic>
claude stop <id>
```

Remove spent worktrees. A registered worktree keeps Layer 1F armed against the main checkout
(ADR-0054), so leftovers block the coordinator's own commits.

## Pinned facts

Each cost something. The citation is where the reasoning lives.

| Fact | Source |
|---|---|
| `claude --bg -p` is **invalid** — `--bg` and `--print` conflict. The prompt is positional. | ADR-0038; `.claude/tests/relay-seed.test.sh` |
| Never pass `--remote-control`. A background session brings up remote control by itself; the flag disables it. | ADR-0038 |
| Posture is armed **inside** the successor (`odin-autonomous.sh on`). A coordinator cannot arm a child — the claim ticket is stamped by the claiming session's own next hook, and a workspace-wide flag would block the human in the same tree. | ADR-0051 |
| Handoffs live under gitignored `.claude/.runtime/`, so they are invisible from a sibling worktree. Pass **absolute** paths. | `.gitignore`; `handoff` skill |
| The launch **directory** decides whether the successor has a skill catalog at all — `CLAUDE.md` walks up the tree, the catalog does not. | ADR-0056 |
| A roadmap id is a per-file counter. `RM-0065` names different work in every roadmap; the relay refuses an unqualified id. | ADR-0050 |
| Sequential ids (ADR/DEC/RM) minted in parallel sessions collide. Reserve up front; if two land anyway, renumber at integration **before** the merge, then re-run the ledger gate. | campaign experience; ADR-0059 |
| Shared registry files are integrated in a fixed order and their counts **recomputed**, never textually merged. | ADR-0059 |
| State-changing `gh` and `git` need `-R owner/name` or a same-command `cd` anchor — both otherwise infer the repo from the working directory. | `.claude/rules/common/security.md` § Name the Target |
| `gh` 2.46.0 has **no** `pr update-branch`. When protection reports BEHIND: `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`, then re-gate, then rebase-merge. | verified on this host |
| A `DIRTY` merge state means real conflicts. Rebase in the worktree and resolve there — never in the web editor. | campaign experience |
| Force-push is blocked. Amending an already-pushed commit means a **new ref** (`<branch>-v2`) plus a fresh PR, and closing the old one. | memory: force-push-blocked-land-via-new-branch |
| A branch green **before** its rebase says nothing about what lands. Gate the merged result. | memory: verify-the-merged-result-not-the-branch |
| A whole fleet going silent at once is one dead shared dependency, not N dead agents. | memory: successors-die-when-spp-pg-exits |
| CI runs locally (`ci-local.sh`). Dispatching a workflow is blocked always-on and would test the pushed tree, not the one being edited. | `.claude/rules/common/security.md` § Run CI Locally |
