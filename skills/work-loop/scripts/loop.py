#!/usr/bin/env python3
"""work-loop — a bounded execution cycle and its resumable ledger.

The engine decides only what a script can decide about a *ledger*: is the contract
complete, which of six outcomes ended this iteration, does a stall predicate fire on the
recorded history, and which actions are already done. It runs no work, dispatches
nothing, and schedules nothing.

Whether to keep going at all belongs to `endless`; polling until a command goes green
belongs to `verification-loop`; running a written plan belongs to `executing-plans`.

Stdout is data, stderr is diagnostics. Every subcommand takes `--root` and `--session`;
nothing is inferred from the working directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

# ---------------------------------------------------------------- exit codes

EXIT_OK = 0
EXIT_INVALID = 1  # the contract or the iteration's facts are malformed
EXIT_USAGE = 2  # usage error, or a ledger that cannot be read
EXIT_CLOSED = 3  # refused: this loop has ended
EXIT_EMPTY = 4  # refused: nothing was examined
EXIT_REPEAT = 5  # refused: the action is already recorded complete

# ---------------------------------------------------------------- vocabulary

OUTCOMES = ("continue", "complete", "revise", "escalate", "pause", "stop")

#: Only `continue` permits a further iteration. Every other outcome ends the loop —
#: including `escalate` and `pause`, which end it without ever waiting for a human.
TERMINAL_OUTCOMES = ("complete", "revise", "escalate", "pause", "stop")

CONTRACT_FIELDS = (
    "purpose",
    "owner",
    "starting_state",
    "inputs",
    "expected_outputs",
    "success_criteria",
    "failure_criteria",
    "dependencies",
    "iteration_limit",
    "timeout_behaviour",
    "escalation_path",
)

STALL_REPEATED_ERROR = "repeated-error"
STALL_CIRCULAR = "circular-state"
STALL_RETRIES = "retries-exhausted"
STALL_DEPENDENCY = "dependency-unavailable"

#: Every predicate names the non-continue outcome it produces. A predicate that fires
#: into another iteration is not a predicate.
STALL_OUTCOME = {
    STALL_REPEATED_ERROR: "escalate",
    STALL_CIRCULAR: "revise",
    STALL_RETRIES: "stop",
    STALL_DEPENDENCY: "escalate",
}

STALL_RECOMMENDED = {
    STALL_REPEATED_ERROR: "one failure has repeated to threshold — capture it as a roadmap item with the signature and end the loop",
    STALL_CIRCULAR: "the loop has revisited a state it already held — revise the contract's approach before re-opening",
    STALL_RETRIES: "the declared iteration limit is spent — record what was achieved and re-scope",
    STALL_DEPENDENCY: "a declared dependency was unavailable — capture the dependency as a roadmap item and end the loop",
}

#: A stall-promoted escalate is written by the engine, not by an author: nobody passed a blocker,
#: and the record must still carry one or it is exactly the shape `blocker-record-check.sh` refuses.
#: The engine holds the facts — which predicate fired, and the signature or dependency behind it —
#: so it names the blocker rather than leaving the field empty and calling that honest.
STALL_BLOCKER = {
    STALL_REPEATED_ERROR: "the same failure repeated to the declared threshold and the loop cannot clear it",
    STALL_DEPENDENCY: "a dependency the contract declares was unreachable from inside the loop",
}

#: The three fields an `escalate` record must carry. CLAUDE.md item 3 makes a hard external blocker
#: the only sanctioned reason to stop short of done; this skill's own body has always said the
#: blocker, its evidence and a recommended next action go to the ledger. Until harness:RM-0361 the
#: engine enforced one of the three, so a stop could be recorded that named nothing.
ESCALATE_FIELDS = ("blocker", "evidence", "recommended_next")

DEFAULT_REPEATED_ERROR_THRESHOLD = 3

RUNTIME_CLASS = os.path.join(".claude", ".runtime", "work-loop")

# ---------------------------------------------------------------- signatures

_NOISE = (
    (re.compile(r'"[^"]*"|\'[^\']*\''), " <q> "),
    (re.compile(r"0x[0-9a-f]+"), " <hex> "),
    (re.compile(r"(?:/[\w.@+-]+)+"), " <path> "),
    (re.compile(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}:\d{2}\S*"), " <ts> "),
    (re.compile(r"\d+"), " <n> "),
    (re.compile(r"\s+"), " "),
)


def error_signature(text):
    """Normalise a failure's text, then hash it.

    A predicate keyed on raw error text never fires: a stack trace carries a changing
    path, pid, address, timestamp or quoted value on every run, so two renderings of one
    failure hash differently. Normalising first is what makes "the same failure, three
    times" a decidable question. The rules are stated in references/stall-detection.md.
    """
    if not text:
        return None
    normalised = text.lower()
    for pattern, replacement in _NOISE:
        normalised = pattern.sub(replacement, normalised)
    normalised = normalised.strip()
    if not normalised:
        return None
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


def state_hash(text):
    """A state's identity, for the circular-behaviour predicate."""
    if not text:
        return None
    return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- the ledger


def ledger_path(root, session):
    return os.path.join(root, RUNTIME_CLASS, session + ".json")


def read_ledger(root, session):
    path = ledger_path(root, session)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_ledger(root, session, ledger):
    path = ledger_path(root, session)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, indent=2, sort_keys=True)
        handle.write("\n")


# ---------------------------------------------------------------- validation


def validate_contract(raw):
    """Return (contract, findings). A finding names the field it is about."""
    findings = []
    if not isinstance(raw, dict):
        return None, ["contract: expected a JSON object"]
    contract = {}
    for field in CONTRACT_FIELDS:
        if field not in raw:
            findings.append("%s: missing — a loop declares all eleven fields before its first iteration" % field)
            continue
        value = raw[field]
        if field == "iteration_limit":
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                findings.append("iteration_limit: must be a positive integer, got %r" % (value,))
                continue
        elif isinstance(value, list):
            if not value or not all(str(item).strip() for item in value):
                findings.append("%s: declared empty — an empty declaration is an undeclared field" % field)
                continue
        elif not str(value).strip():
            findings.append("%s: declared empty — an empty declaration is an undeclared field" % field)
            continue
        contract[field] = value
    extra = sorted(set(raw) - set(CONTRACT_FIELDS))
    for field in extra:
        findings.append("%s: not one of the eleven declared fields" % field)
    return contract, findings


# ---------------------------------------------------------------- predicates


def detect_stall(ledger, signature, state, dependency_missing, threshold):
    """Run the four predicates over the ledger plus this iteration's reported facts.

    Order is deliberate and documented: a dependency that is simply gone is reported
    before a repetition that is its symptom.
    """
    if dependency_missing:
        return STALL_DEPENDENCY

    if signature:
        repeats = 1 + sum(
            1 for it in ledger["iterations"] if it.get("error_signature") == signature
        )
        if repeats >= threshold:
            return STALL_REPEATED_ERROR

    if state:
        if any(it.get("state_hash") == state for it in ledger["iterations"]):
            return STALL_CIRCULAR

    if len(ledger["iterations"]) + 1 >= ledger["contract"]["iteration_limit"]:
        return STALL_RETRIES

    return None


# ---------------------------------------------------------------- subcommands


def cmd_open(args):
    existing = read_ledger(args.root, args.session)
    if existing is not None and not args.force:
        print("%s: a ledger is already open for this session" % args.session, file=sys.stderr)
        return EXIT_CLOSED

    try:
        with open(args.contract, encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        print("contract: cannot read %s (%s)" % (args.contract, exc.strerror), file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        print("contract: not valid JSON (%s)" % exc, file=sys.stderr)
        return EXIT_INVALID

    contract, findings = validate_contract(raw)
    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return EXIT_INVALID

    ledger = {
        "session": args.session,
        "contract": contract,
        "status": "open",
        "final_outcome": None,
        "iterations": [],
        "completed_actions": [],
        "resumed": 0,
        "stall_threshold": args.stall_threshold,
    }
    write_ledger(args.root, args.session, ledger)
    return emit(args, {"session": args.session, "status": "open", "next_iteration": 1},
                "loop open: %s (limit %d)" % (args.session, contract["iteration_limit"]))


def cmd_iterate(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE
    if ledger["status"] != "open":
        print(
            "%s: the loop ended with outcome '%s' — open a new one, or resume a paused one"
            % (args.session, ledger["final_outcome"]),
            file=sys.stderr,
        )
        return EXIT_CLOSED

    already = [a for a in args.action if a in ledger["completed_actions"]]
    if already:
        # Refused before anything is written. A refusal that still records is not one,
        # and a batch is refused whole: a partial record is a repeat by another name.
        print(
            "already complete, nothing recorded: %s" % ", ".join(already), file=sys.stderr
        )
        return EXIT_REPEAT

    if args.dependency_missing and args.dependency_missing not in ledger["contract"]["dependencies"]:
        print(
            "%s: not a declared dependency — the contract declares %s"
            % (args.dependency_missing, ", ".join(ledger["contract"]["dependencies"])),
            file=sys.stderr,
        )
        return EXIT_INVALID

    if args.outcome == "escalate":
        # A blocker record is EVIDENCE, not permission. Requiring all three makes escalating
        # harder than it was, never easier: the record is what a later reader has instead of the
        # session, and a stop that names no blocker is indistinguishable from giving up.
        # What is checkable is that the stop RECORDED a blocker in a stated form — never whether
        # the blocker was genuine, which is a judgment a gate must not encode.
        missing = [
            f for f in ESCALATE_FIELDS
            if not (getattr(args, f, None) or "").strip()
        ]
        if missing:
            print(
                "escalate: %s required — escalate writes the blocker, its evidence and its next "
                "action into the ledger and ends the loop; it never asks and waits"
                % ", ".join("--" + f.replace("_", "-") for f in missing),
                file=sys.stderr,
            )
            return EXIT_INVALID

    signature = error_signature(args.error)
    state = state_hash(args.state)
    stall = None
    outcome = args.outcome
    recommended = args.recommended_next
    blocker = args.blocker
    evidence = args.evidence

    if args.outcome == "continue":
        stall = detect_stall(
            ledger, signature, state, args.dependency_missing,
            ledger.get("stall_threshold", DEFAULT_REPEATED_ERROR_THRESHOLD),
        )
        if stall:
            outcome = STALL_OUTCOME[stall]
            if outcome == "escalate":
                if not recommended:
                    recommended = STALL_RECOMMENDED[stall]
                if not blocker:
                    blocker = STALL_BLOCKER[stall]
                if not evidence:
                    # The predicate's own input is the evidence, and it is the only evidence that
                    # exists: a normalised signature for a repeated failure, the dependency's name
                    # for an unreachable one.
                    evidence = (
                        "declared dependency unreachable: %s" % args.dependency_missing
                        if stall == STALL_DEPENDENCY
                        else "error signature %s repeated to threshold %d"
                        % (signature, ledger.get("stall_threshold", DEFAULT_REPEATED_ERROR_THRESHOLD))
                    )

    record = {
        "n": len(ledger["iterations"]) + 1,
        "reported_outcome": args.outcome,
        "outcome": outcome,
        "stall": stall,
        "error_signature": signature,
        "state_hash": state,
        "dependency_missing": args.dependency_missing,
        "actions": list(args.action),
        "blocker": blocker,
        "evidence": evidence,
        "recommended_next": recommended,
        "note": args.note,
    }
    ledger["iterations"].append(record)
    ledger["completed_actions"].extend(args.action)
    if outcome in TERMINAL_OUTCOMES:
        ledger["status"] = "closed"
        ledger["final_outcome"] = outcome
    write_ledger(args.root, args.session, ledger)

    human = "iteration %d: %s" % (record["n"], outcome)
    if stall:
        human += " (stall: %s, reported '%s')" % (stall, args.outcome)
    return emit(args, record, human)


def cmd_status(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE
    if not ledger["iterations"]:
        payload = {
            "session": ledger["session"],
            "status": ledger["status"],
            "final_outcome": ledger["final_outcome"],
            "iterations": 0,
            "completed_actions": [],
            "stalls": [],
        }
        emit(args, payload, "%s: open, no iterations recorded" % ledger["session"])
        # A report over an empty history is distinguished from a clean one: a caller
        # that cannot tell "nothing found" from "nothing examined" cannot detect the
        # failure this repository has been bitten by most.
        return EXIT_EMPTY
    payload = {
        "session": ledger["session"],
        "status": ledger["status"],
        "final_outcome": ledger["final_outcome"],
        "iterations": len(ledger["iterations"]),
        "completed_actions": ledger["completed_actions"],
        "stalls": [it["stall"] for it in ledger["iterations"] if it["stall"]],
        "last_outcome": ledger["iterations"][-1]["outcome"],
    }
    return emit(
        args, payload,
        "%s: %s after %d iteration(s), outcome %s"
        % (ledger["session"], ledger["status"], len(ledger["iterations"]),
           ledger["final_outcome"] or ledger["iterations"][-1]["outcome"]),
    )


def cmd_resume(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE

    if ledger["status"] == "closed":
        if ledger["final_outcome"] != "pause":
            print(
                "%s: the loop ended with outcome '%s' — only a paused loop is resumable"
                % (args.session, ledger["final_outcome"]),
                file=sys.stderr,
            )
            return EXIT_CLOSED
        ledger["status"] = "open"
        ledger["final_outcome"] = None
        ledger["resumed"] += 1
        write_ledger(args.root, args.session, ledger)

    payload = {
        "session": ledger["session"],
        "status": ledger["status"],
        "contract": ledger["contract"],
        "completed_actions": ledger["completed_actions"],
        "next_iteration": len(ledger["iterations"]) + 1,
        "resumed": ledger["resumed"],
    }
    return emit(
        args, payload,
        "%s: resume at iteration %d; %d action(s) already complete — perform none of them"
        % (ledger["session"], payload["next_iteration"], len(ledger["completed_actions"])),
    )


def cmd_close(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE
    if ledger["status"] != "open":
        print(
            "%s: already closed with outcome '%s'" % (args.session, ledger["final_outcome"]),
            file=sys.stderr,
        )
        return EXIT_CLOSED
    if args.outcome not in TERMINAL_OUTCOMES:
        print(
            "close --outcome must be one of: %s — 'continue' is not a way to end"
            % ", ".join(TERMINAL_OUTCOMES),
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.outcome == "escalate":
        missing = [
            f for f in ESCALATE_FIELDS
            if not (getattr(args, f, None) or "").strip()
        ]
        if missing:
            print(
                "escalate: %s required" % ", ".join("--" + f.replace("_", "-") for f in missing),
                file=sys.stderr,
            )
            return EXIT_INVALID
    ledger["status"] = "closed"
    ledger["final_outcome"] = args.outcome
    ledger["close_note"] = args.note
    ledger["close_recommended_next"] = args.recommended_next
    ledger["close_blocker"] = args.blocker
    ledger["close_evidence"] = args.evidence
    write_ledger(args.root, args.session, ledger)
    return emit(
        args,
        {"session": args.session, "status": "closed", "final_outcome": args.outcome},
        "%s: closed with outcome %s" % (args.session, args.outcome),
    )


# ---------------------------------------------------------------- plumbing


def require_ledger(args):
    ledger = read_ledger(args.root, args.session)
    if ledger is None:
        print(
            "%s: no ledger at %s — open one first"
            % (args.session, ledger_path(args.root, args.session)),
            file=sys.stderr,
        )
        return None
    return ledger


def emit(args, payload, human):
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(human)
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="loop",
        description="A bounded execution cycle and its resumable ledger.",
    )
    subparsers = parser.add_subparsers(dest="command")

    def common(sub, session_required=True):
        sub.add_argument("--root", required=True, help="repository root; never inferred")
        sub.add_argument("--session", required=session_required, help="the ledger's session id")
        sub.add_argument("--json", action="store_true", help="machine-readable output")
        return sub

    opened = common(subparsers.add_parser("open", help="declare the contract and open a ledger"))
    opened.add_argument("--contract", required=True, help="path to the eleven-field contract JSON")
    opened.add_argument("--stall-threshold", type=int, default=DEFAULT_REPEATED_ERROR_THRESHOLD)
    opened.add_argument("--force", action="store_true", help="overwrite an existing ledger")
    opened.set_defaults(func=cmd_open)

    iterated = common(subparsers.add_parser("iterate", help="record one iteration and its outcome"))
    iterated.add_argument("--outcome", required=True, choices=OUTCOMES)
    iterated.add_argument("--action", action="append", default=[], help="a stable id for work performed")
    iterated.add_argument("--error", help="the iteration's failure text, if it failed")
    iterated.add_argument("--state", help="the iteration's resulting state, for circularity")
    iterated.add_argument("--dependency-missing", help="a declared dependency the iteration could not reach")
    iterated.add_argument("--blocker", help="what stopped the loop; required for escalate")
    iterated.add_argument("--evidence", help="the evidence for the blocker; required for escalate")
    iterated.add_argument("--recommended-next", help="required for escalate")
    iterated.add_argument("--note", help="free text recorded with the iteration")
    iterated.set_defaults(func=cmd_iterate)

    status = common(subparsers.add_parser("status", help="report the standing verdict"))
    status.set_defaults(func=cmd_status)

    resumed = common(subparsers.add_parser("resume", help="report what is done; reopen a paused loop"))
    resumed.set_defaults(func=cmd_resume)

    closed = common(subparsers.add_parser("close", help="end the loop with a terminal outcome"))
    closed.add_argument("--outcome", required=True, choices=OUTCOMES)
    closed.add_argument("--blocker", help="what stopped the loop; required for escalate")
    closed.add_argument("--evidence", help="the evidence for the blocker; required for escalate")
    closed.add_argument("--recommended-next", help="required for escalate")
    closed.add_argument("--note", help="free text recorded with the close")
    closed.set_defaults(func=cmd_close)

    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return EXIT_USAGE
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return EXIT_USAGE
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
