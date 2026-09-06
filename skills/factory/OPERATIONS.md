# Operating a factory

Not how to build one — that is `SKILL.md`. This is what to do once one exists: arm it, read its
state, stop it, and recognise what a failed lap looks like before it has run forty more.

Everything here assumes the factory's own repository as the working directory, and
`factory/config.sh` as the one place project values live.

---

## Read the state before touching anything

```sh
. ./factory/config.sh
"$FACTORY_PYTHON" factory/state.py next          # what the dispatcher would do on the next tick
"$FACTORY_PYTHON" factory/state.py list issues --state accepted
python3 <skill>/scripts/factory_doctor.py --repo . --audit
```

Three answers and what each means:

| `state.py next` says | Meaning |
|---|---|
| a target | it will be dispatched on the next tick, at the current dial |
| `idle` | nothing to do. **Not a failure** — a factory with an empty queue is a factory that finished |
| `stalled` | a PR is `validating` with no run holding its lock: a validation was killed mid-flight and the queue is parked behind it |

`factory_doctor` exit codes are load-bearing and are not the same failure:

- **2** — it could not look (no such directory, unreadable repo). Fix the path, not the factory.
- **1** — it looked and found problems. Every `FAIL` line names its own remedy.
- **0** — clean at the level it was asked about. `--audit` asks the stricter question.

## Arm it

Only after a lap has been proven by hand. `install-trigger.sh` refuses below dial 1, and the dial
does not leave 0 until Phase 7 of the build has run one real issue all the way to a merged PR.

```sh
bash factory/install-trigger.sh --status     # what is armed right now
bash factory/install-trigger.sh --install    # cron, systemd timer, or Task Scheduler
bash factory/install-trigger.sh --remove
```

**Nothing pushes.** Filing an issue does not start a run. The scheduler wakes on a timer, reads
state, dispatches at most one thing. An issue filed at 09:01 waits for the next tick. This is
deliberate: a push trigger that breaks fails *silently* and looks exactly like a factory with
nothing to do, while a poll that breaks is a poll you can see not running.

**A fully built factory with nothing scheduled audits identically to a running one**, which is why
`factory_doctor` checks whether a scheduler is actually armed. `--status` is the other half of that
answer.

## Run one lap by hand, and watch it

Two front doors, and they do the same thing:

```sh
bash factory/orchestrator.sh                                  # one tick, in this terminal
bash .claude/scripts/archon.sh workflow run factory-lap       # one tick, as an Archon run
```

The Archon form buys the run record, the streamed log, cancel, and resume — not a different
decision. `orchestrator.sh` is still the only thing that decides what runs next, and it is
deliberately the dumbest component in the system: bash, a fixed priority order, state in something
boring. Copy `workflows/factory-lap.yaml` into the factory repo's `.archon/workflows/` to use it.

While a run is in flight:

```sh
bash .claude/scripts/archon.sh workflow status
bash .claude/scripts/archon.sh workflow get <run-id>
bash .claude/scripts/archon.sh workflow cancel <run-id>
```

## Stop it

Two mechanisms, because they fail in different places. **Use both when it matters.**

```sh
touch .factory/STOP                                   # the kill file — works with the network down
gh issue edit <n> --add-label factory:stop            # the label — works when you are not at the machine
```

The file is checked before any dispatch, including by `factory-lap.yaml`'s own preflight — a stop
honoured only by the thing you are trying to stop is not a stop button. Removing either is a
deliberate act; neither expires.

**Test the stop button on purpose, before you need it.** Set it, run a tick, confirm nothing
dispatched, clear it. A stop button nobody has ever pulled is a claim, not a control.

## Reading a failed lap

The failure modes that matter are the quiet ones. In rough order of how often they bite:

| Symptom | Almost always |
|---|---|
| every lap dispatches, nothing merges | the dial is below 3 — the validator is posting a verdict and waiting for a human who is not coming |
| the same target re-dispatches every tick forever | a node dies *before* the state transition that would move it on. Read the run log for the first `ESCALATE` |
| `GATE_FAILED: static` on code that compiles | the interpreter. `FACTORY_PYTHON`, or a `harness.config.json` command that names a binary this host does not have |
| green gate, broken software | the assertions are still the template's worked examples. `factory_doctor` blocks this at level 2+; if it is not blocking, the marker was deleted without the content being replaced |
| the deploy never fires and nothing errors | GitHub does not trigger workflows on commits made with the default `GITHUB_TOKEN`. `references/deployment.md` |
| every session goes silent at once | a host-level event, not forty agent failures. Check the machine before relaunching anything |
| a worktree per run accumulates | `git worktree remove` refuses a worktree containing a submodule. `--force` succeeds; something has to run it |

**A run that escalated told somebody, or it did not run.** `FACTORY_NOTIFY_CMD` needs a command that
actually executes — *"I'll just check the file"* is how unattended becomes unmonitored. If the last
escalation reached nobody, fix that before fixing what escalated.

## After editing anything under `factory/`

The runner is **copied into a repository and never linked**. A fix upstream has not reached a
factory already built, and a hand-edit drifts with nothing watching. Two commands, about two
minutes, and they are free:

```sh
python3 <skill>/scripts/_test_runner.py  --repo .
python3 <skill>/scripts/_audit_runner.py --repo .
```

Run both after any hand-edit, and **before re-arming a factory that has been idle**. A factory that
fails them fails *silently* — parking work nobody is told about, or re-running a workflow that can
only die.

In this repository the skill's own machinery is gated by `bash .claude/tests/factory.test.sh`, which
`ci-local.sh` runs. That covers the templates. It does not cover a factory somebody built; `--repo`
is what covers that one, and nothing runs it for you.

## Raising the dial

Evidence, then the notch. Never the other way round.

1. Prove a lap by hand at the current level and watch a full cycle.
2. `factory_doctor --audit` clean. It refuses level 3 while there is no holdout, which is the check
   that decides whether the validation harness was real.
3. Raise `FACTORY_AUTONOMY` in `config.sh` by one.
4. Watch a full cycle again before the next notch.

Stopping below 3 is a legitimate choice and it goes into `FACTORY.md` as **what would have to be
true to go further** — so it stays a decision with a way out of it rather than a dial nobody touched
again.

## Changing what the product is

Edit `MISSION.md`, in a human commit, on purpose. It is refused to the agent by
`factory/guard.py` and by Layer 1H of `.claude/hooks/odin-safety-guard.sh`, and that is the point:
an agent that can amend the rules it is judged by can widen its own scope and then satisfy it, with
every gate still green.

The PRD is a live document here. Nobody compensates for staleness — the factory will keep faithfully
building the old scope until someone notices.
