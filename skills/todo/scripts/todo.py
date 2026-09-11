#!/usr/bin/env python3
"""todo — a facade over the work-loop ledger, and deliberately not a store.

WHY THIS IS A FACADE AND NOT A LIST FILE. `odin-task-gate.sh` accepts exactly two pieces of
evidence that a session is tracking its work: the native `TaskCreate`/`TaskUpdate` marker, and an
OPEN work-loop ledger whose own `session` field matches this session (`odin-task-gate.sh`, the
reader half; M-0043, harness:RM-0337). There is no third route, on purpose — every additional
thing the gate would accept moves it one step closer to a `touch`, and the gate's whole value is
that the evidence is hard to fake.

So this program writes no state of its own. The todo LIST is the contract's `expected_outputs`,
declared once when the ledger opens. PROGRESS is the ledger's `completed_actions`, which is
`loop.py`'s own derived field. Neither is stored twice, and neither is stored here.

That makes the open/closed standing of an item **computed at read time**, which is the same rule
the campaign manifest and the goal record follow and for the same reason (ADR-0113): a stored
answer is correct until the next write and believed forever after.

WHAT IT ADDS OVER CALLING `loop.py` DIRECTLY. One thing: a twelve-field contract is the right
shape for a bounded work cycle and the wrong shape to type out for "four things to do". `contract`
synthesises an honest one from a list of items — including a rubric dimension that is REAL rather
than invented, because `count-open` below is a command anything can run:

    dimension        items-open
    evidence_command python3 .claude/skills/todo/scripts/todo.py count-open --root . --session S
    baseline         the number of items declared
    target           0
    direction        lower-is-better

A rubric dimension whose evidence command cannot be run is a judgment wearing a dimension's
clothes, and `loop.py` refuses one. This one is runnable, and its number is derived from the
ledger rather than asserted about it.

TWO SHAPES THIS DELIBERATELY AVOIDS.

  * No pipe, and no quoted metacharacter, in the generated `evidence_command`. `loop.py` splits a
    command into segments BEFORE `shlex.split` sees it, so a `|` inside a quoted regex breaks the
    quoting and the contract is refused with `No closing quotation` — a message that names the
    quote and not the pipe. Measured in this campaign.
  * No `--root` inferred from the working directory. Every subcommand requires it, exactly as
    `loop.py` does, for the reason `cli/patterns.md` § Resolving the Target gives: a tool inherits
    whatever directory an earlier command left behind.

Exit codes follow `cli/coding-style.md`:
  0  the operation succeeded
  1  a substantive failure — an item that is not declared, a ledger that is not open
  2  usage, or an input this program could not read
  3  no ledger for this session: could not look, which is not the same as an empty list
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_NO_LEDGER = 3

#: The incumbent. Named by path, invoked as a module, never imported and never reimplemented —
#: `consistency`'s rule, and the reason this file holds no ledger logic at all.
LOOP_SKILL_DIR = os.path.join(".claude", "skills", "work-loop")
LOOP_MODULE = "scripts.loop"

#: The rubric dimension `contract` synthesises. One dimension, because a todo list has exactly one
#: measurable property and inventing a second would be padding a contract to look thorough.
RUBRIC_DIMENSION = "items-open"


def die(message: str, code: int = EXIT_USAGE) -> int:
    print("todo: " + message, file=sys.stderr)
    return code


def loop_call(root: str, argv: list[str]) -> tuple[int, str, str]:
    """Invoke the work-loop engine as a module. Returns (rc, stdout, stderr).

    Run with cwd set to the skill directory because `loop.py` is `scripts.loop` relative to it —
    the same invocation its own SKILL.md documents. The engine resolves the repository from its
    own `--root`, which is passed through unchanged, so the cwd decides nothing but the import.
    """
    skill_dir = os.path.join(root, LOOP_SKILL_DIR)
    if not os.path.isdir(skill_dir):
        return (EXIT_USAGE, "", "the work-loop skill is not at %s" % skill_dir)
    proc = subprocess.run(
        [sys.executable, "-m", LOOP_MODULE] + argv,
        cwd=skill_dir, capture_output=True, text=True,
    )
    return (proc.returncode, proc.stdout, proc.stderr)


def loop_status(root: str, session: str) -> tuple[int, dict | None, str]:
    """The ledger's own status payload, or None when there is no ledger to read.

    `loop.py status` exits EXIT_EMPTY (a distinct code) for an open ledger with no iterations yet,
    and that is a real answer — an empty history, not a missing one. It is passed through as a
    payload rather than folded into the failure branch, because "nothing found" and "nothing
    examined" are different sentences (`ci/testing.md`).
    """
    rc, out, err = loop_call(root, ["status", "--root", os.path.abspath(root),
                                    "--session", session, "--json"])
    if not out.strip():
        return (EXIT_NO_LEDGER, None, err.strip() or "no ledger for session %r" % session)
    try:
        return (rc, json.loads(out), err.strip())
    except ValueError:
        return (EXIT_USAGE, None, "the engine's --json output did not parse: %s" % out[:200])


def read_contract(root: str, session: str) -> dict | None:
    """The contract this session's ledger was opened with, read back from the ledger.

    Read from the ledger rather than from the file that was passed to `open`, because that file is
    the caller's and may have been edited, moved or deleted since. The ledger holds what was
    actually declared.
    """
    path = os.path.join(root, ".claude", ".runtime", "work-loop", session + ".json")
    try:
        with open(path, encoding="utf-8") as handle:
            return (json.load(handle) or {}).get("contract")
    except (OSError, ValueError):
        return None


def declared_items(root: str, session: str) -> list[str] | None:
    contract = read_contract(root, session)
    if not isinstance(contract, dict):
        return None
    outputs = contract.get("expected_outputs")
    if isinstance(outputs, str):
        outputs = [outputs]
    if not isinstance(outputs, list):
        return None
    return [str(x) for x in outputs]


def item_id(text: str) -> str:
    """The stable id an item is recorded under. The text before the first colon, or the whole line.

    Declared in the item rather than derived from its position: a positional id renumbers when an
    item is inserted, and every record written before the insertion then names the wrong item.
    """
    head = text.split(":", 1)[0].strip()
    return head if head and " " not in head else text.strip()


# ---------------------------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------------------------

def cmd_contract(args) -> int:
    items = [i for i in args.item if i.strip()]
    if not items:
        return die("no items — a contract with an empty item list declares nothing to track")

    ids = [item_id(i) for i in items]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        return die("duplicate item id(s): %s — two items sharing an id means one `done` closes "
                   "both, silently" % ", ".join(dupes))

    evidence = ("python3 .claude/skills/todo/scripts/todo.py count-open "
                "--root . --session " + args.session)

    contract = {
        "purpose": args.purpose,
        "owner": args.owner,
        "starting_state": "%d item(s) declared, none recorded complete" % len(items),
        "inputs": ["the item list declared in expected_outputs"],
        "expected_outputs": items,
        "success_criteria": "every declared item has been recorded complete by `todo done`, "
                            "which is the same thing as `%s` printing 0" % RUBRIC_DIMENSION,
        "failure_criteria": "an item cannot be completed and no other item can proceed without it",
        "dependencies": args.dependency or ["none declared"],
        "iteration_limit": args.iteration_limit,
        "timeout_behaviour": "record `pause` and hand the remaining items forward in a handoff; "
                             "the ledger is resumable and the item list survives the session",
        "escalation_path": args.escalation_path,
        "quality_rubric": [{
            "dimension": RUBRIC_DIMENSION,
            "evidence_command": evidence,
            "baseline": len(items),
            "target": 0,
            "weight": 1.0,
            "failure_threshold": len(items),
            "direction": "lower-is-better",
            # Declared false, never omitted. `loop.py` requires all eight keys and refuses a
            # dimension missing one; `must_not_regress` is the single optional key, not this.
            # An item list is an OPTIMISATION objective — it moves from N to 0 — so it is not
            # a line being held, and a hard gate over it would refuse `retain` on the first
            # iteration that has not finished the list.
            "hard_gate": False,
        }],
    }
    print(json.dumps(contract, indent=2))
    return EXIT_OK


def cmd_count_open(args) -> int:
    """The rubric's evidence command. Prints one integer and nothing else."""
    items = declared_items(args.root, args.session)
    if items is None:
        return die("no ledger for session %r under %s — nothing to count, which is not the "
                   "same as nothing open" % (args.session, args.root), EXIT_NO_LEDGER)
    rc, payload, err = loop_status(args.root, args.session)
    if payload is None:
        return die(err, EXIT_NO_LEDGER)
    done = set(payload.get("completed_actions") or [])
    print(sum(1 for i in items if item_id(i) not in done))
    return EXIT_OK


def cmd_list(args) -> int:
    items = declared_items(args.root, args.session)
    if items is None:
        return die("no ledger for session %r under %s" % (args.session, args.root), EXIT_NO_LEDGER)
    rc, payload, err = loop_status(args.root, args.session)
    if payload is None:
        return die(err, EXIT_NO_LEDGER)
    done = set(payload.get("completed_actions") or [])

    rows = [{"id": item_id(i), "text": i, "done": item_id(i) in done} for i in items]
    if args.json:
        print(json.dumps({
            "session": args.session,
            "ledger_status": payload.get("status"),
            "items": rows,
            "open": sum(1 for r in rows if not r["done"]),
        }, indent=2))
        return EXIT_OK

    for row in rows:
        print("%s %-24s %s" % ("[x]" if row["done"] else "[ ]", row["id"], row["text"]))
    print("%d of %d open · ledger %s" % (sum(1 for r in rows if not r["done"]),
                                         len(rows), payload.get("status")))
    return EXIT_OK


def cmd_done(args) -> int:
    items = declared_items(args.root, args.session)
    if items is None:
        return die("no ledger for session %r under %s" % (args.session, args.root), EXIT_NO_LEDGER)
    ids = [item_id(i) for i in items]
    if args.item not in ids:
        return die("%r is not a declared item. Declared: %s. An item nobody declared cannot be "
                   "completed, and recording it would put a second list in the ledger"
                   % (args.item, ", ".join(ids) or "<none>"), EXIT_FAIL)

    argv = ["iterate", "--root", os.path.abspath(args.root), "--session", args.session,
            "--outcome", "continue", "--action", args.item]
    remaining = sum(1 for i in ids if i != args.item)
    argv += ["--measure", "%s=%d" % (RUBRIC_DIMENSION, remaining)]
    if args.note:
        argv += ["--note", args.note]
    rc, out, err = loop_call(args.root, argv)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return rc


def cmd_route(args) -> int:
    """Which of the two routes `odin-task-gate.sh` accepts is live for this session.

    Reports; it never establishes one. A probe that armed the thing it probes would be the
    `ci-gate/fixture-reads-ambient-state` shape — read-only is a property of the effect, not of
    the intention.
    """
    # The path is `odin-task-gate.sh`'s own (its writer half), not a second convention:
    # `$REPO_ROOT/.claude/.runtime/tasks/$session`. A probe that invented its own path would
    # report "absent" forever and read exactly like a gate nobody satisfied.
    marker = os.path.join(args.root, ".claude", ".runtime", "tasks", args.session)
    native = os.path.exists(marker)

    ledger_open = False
    ledger_path = os.path.join(args.root, ".claude", ".runtime", "work-loop",
                               args.session + ".json")
    try:
        with open(ledger_path, encoding="utf-8") as handle:
            doc = json.load(handle)
        ledger_open = doc.get("session") == args.session and doc.get("status") == "open"
    except (OSError, ValueError):
        ledger_open = False

    if args.json:
        print(json.dumps({"session": args.session, "task_create_marker": native,
                          "work_loop_ledger_open": ledger_open,
                          "satisfied": native or ledger_open}, indent=2))
    else:
        print("TaskCreate marker:      %s" % ("present" if native else "absent"))
        print("work-loop ledger open:  %s" % ("yes" if ledger_open else "no"))
        print("task gate satisfied:    %s" % ("yes" if native or ledger_open else "NO"))
        if not (native or ledger_open):
            print("    Neither route is live. `TaskCreate` is the cheaper one and is tried first;")
            print("    when it is unavailable, open a ledger:")
            print("      python3 .claude/skills/todo/scripts/todo.py contract --session <id> \\")
            print("          --item 'a: the first thing' --item 'b: the second' > /tmp/c.json")
            print("      cd .claude/skills/work-loop && python3 -m scripts.loop open \\")
            print("          --root <repo> --session <id> --contract /tmp/c.json")
    return EXIT_OK if (native or ledger_open) else EXIT_FAIL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="todo",
        description="A facade over the work-loop ledger. Writes no state of its own.")
    subs = parser.add_subparsers(dest="command")

    def rooted(sub):
        sub.add_argument("--root", required=True, help="repository root; never inferred")
        sub.add_argument("--session", required=True, help="the ledger's session id")
        return sub

    c = subs.add_parser("contract", help="synthesise a twelve-field contract from an item list")
    c.add_argument("--session", required=True, help="the session the rubric's command will name")
    c.add_argument("--item", action="append", default=[], metavar="ID: TEXT",
                   help="one todo item; the text before the first colon is its stable id")
    c.add_argument("--purpose", default="drive a declared list of items to done")
    c.add_argument("--owner", default="this session")
    c.add_argument("--dependency", action="append", default=[])
    c.add_argument("--iteration-limit", type=int, default=50)
    c.add_argument("--escalation-path",
                   default="record `escalate` with a blocker, evidence and a recommended next, "
                           "then hand the remaining items forward")
    c.set_defaults(func=cmd_contract)

    lst = rooted(subs.add_parser("list", help="every declared item, open or done"))
    lst.add_argument("--json", action="store_true")
    lst.set_defaults(func=cmd_list)

    cnt = rooted(subs.add_parser("count-open", help="the rubric's evidence command; one integer"))
    cnt.set_defaults(func=cmd_count_open)

    dn = rooted(subs.add_parser("done", help="record one declared item complete"))
    dn.add_argument("--item", required=True, help="the item's declared id")
    dn.add_argument("--note")
    dn.set_defaults(func=cmd_done)

    rt = rooted(subs.add_parser("route", help="which task-gate route is live for this session"))
    rt.add_argument("--json", action="store_true")
    rt.set_defaults(func=cmd_route)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    if getattr(args, "root", None) is not None and not os.path.isdir(args.root):
        return die("no such directory: %s" % args.root)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
