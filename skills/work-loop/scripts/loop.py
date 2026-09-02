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
EXIT_CLOSED = 3  # refused: the ledger is not in a state this command acts on
#                  (iterate/close over a closed ledger; open over a live one)
EXIT_EMPTY = 4  # refused: nothing was examined
EXIT_REPEAT = 5  # refused: the action is already recorded complete
EXIT_GATE = 6  # refused: a hard-gate dimension breached its failure threshold
EXIT_REGRESSION = 7  # refused: a change retained over a breached hard gate
EXIT_UNREADABLE = 8  # refused: an input the critic brief needs could not be read

# ---------------------------------------------------------------- vocabulary

OUTCOMES = ("continue", "complete", "revise", "escalate", "pause", "stop")

#: The critic's verdict on a CHANGE, from the five words the gauntlet spec names. Kept
#: separate from OUTCOMES on purpose: an outcome ends an *iteration* and a verdict judges a
#: *change*, and `continue` means nothing as a verdict.
CRITIC_VERDICTS = ("PASS", "FAIL", "REVISE", "REVERT", "ESCALATE")

#: What was done with the change once the verdict was in. `retain` is the one the engine
#: refuses over a breached hard gate.
DECISIONS = ("retain", "revert", "revise", "escalate")

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
    "quality_rubric",
)

RUBRIC_FIELDS = (
    "dimension",
    "evidence_command",
    "baseline",
    "target",
    "weight",
    "failure_threshold",
    "direction",
    "hard_gate",
)

#: Declared, and cross-checked against the baseline -> target ordering rather than derived
#: from it. Derivation is one key cheaper and silently inverts the failure test when an
#: author swaps two numbers, which reads correct on the page.
DIRECTIONS = ("higher-is-better", "lower-is-better")

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


def validate_rubric(raw):
    """Return (rubric, findings) for the `quality_rubric` field.

    A dimension earns its place only if an iteration can decide it without a judgment
    call. That is the same bar `success_criteria` has always carried, made mechanical: a
    dimension names the **command** that produces its number, and a dimension with no
    command is refused rather than accepted as prose. If you cannot write the command, the
    dimension belongs in review, and references/quality-rubric.md says so in the open
    rather than pretending the rubric covers it.
    """
    findings = []
    if not isinstance(raw, list):
        return None, ["quality_rubric: expected a list of dimensions, got %r" % type(raw).__name__]
    if not raw:
        return None, [
            "quality_rubric: declared empty — a rubric needs at least one dimension, or "
            "`better` is asserted rather than measured"
        ]

    rubric, seen = [], set()
    for index, entry in enumerate(raw):
        where = "quality_rubric[%d]" % index
        if not isinstance(entry, dict):
            findings.append("%s: expected an object carrying the eight declared keys" % where)
            continue

        name = str(entry.get("dimension") or "").strip()
        if name:
            where = "quality_rubric[%s]" % name

        # Shape first. Every check below reads a key by name, so a missing or unknown key
        # is reported once here rather than as a cascade of consequences.
        local = []
        for field in RUBRIC_FIELDS:
            if field not in entry:
                local.append(
                    "%s: %s missing — a dimension declares all eight keys" % (where, field)
                )
        for field in sorted(set(entry) - set(RUBRIC_FIELDS)):
            local.append(
                "%s: %s is not one of the eight declared keys — an interface that accepts "
                "unknown keys cannot tell a typo from an extension" % (where, field)
            )
        if local:
            findings.extend(local)
            continue

        if not name:
            findings.append("%s: dimension declared empty — a nameless dimension cannot be measured" % where)
            continue
        if name in seen:
            findings.append(
                "%s: duplicate dimension name — two dimensions with one name make the "
                "weighted total depend on which was read last" % where
            )
            continue
        seen.add(name)

        if not str(entry["evidence_command"]).strip():
            local.append(
                "%s: evidence_command declared empty — a dimension with no command is a "
                "judgment, and a judgment belongs in review rather than in a rubric" % where
            )
        for field in ("baseline", "target", "weight", "failure_threshold"):
            value = entry[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                local.append("%s: %s must be a number, got %r" % (where, field, value))
        if not isinstance(entry["hard_gate"], bool):
            local.append(
                "%s: hard_gate must be true or false, got %r — a truthy string would make "
                "every dimension a hard gate" % (where, entry["hard_gate"])
            )
        if entry["direction"] not in DIRECTIONS:
            local.append(
                "%s: direction must be one of %s, got %r"
                % (where, " / ".join(DIRECTIONS), entry["direction"])
            )
        if local:
            findings.extend(local)
            continue

        # Only now are the numbers known to be numbers and the direction known to be one
        # of the two, so the two relational checks below can be trusted.
        if entry["weight"] <= 0:
            findings.append(
                "%s: weight must be positive — a zero-weight dimension is declared and "
                "counts for nothing, which reads as coverage it does not provide" % where
            )
            continue
        if entry["target"] == entry["baseline"]:
            findings.append(
                "%s: target equals its baseline — a dimension that cannot move scores "
                "nothing and measures nothing" % where
            )
            continue
        rising = entry["target"] > entry["baseline"]
        if rising != (entry["direction"] == "higher-is-better"):
            findings.append(
                "%s: direction is %r but the target moves the other way (baseline %r -> "
                "target %r) — a swapped pair reads correct and inverts the failure test"
                % (where, entry["direction"], entry["baseline"], entry["target"])
            )
            continue

        rubric.append(dict(entry))

    return rubric, findings


# ---------------------------------------------------------------- scoring


def score_dimension(entry, measured):
    """One dimension's normalised score, and whether it breached its own threshold.

    The two are separate questions on purpose. A dimension can score well and still be
    over its threshold — that is precisely the case a rubric exists to catch, and folding
    them together is how a good total comes to buy a broken gate.
    """
    baseline = float(entry["baseline"])
    target = float(entry["target"])
    raw = (measured - baseline) / (target - baseline) * 100.0
    score = max(0.0, min(100.0, raw))
    if entry["direction"] == "lower-is-better":
        gate_failed = measured > entry["failure_threshold"]
    else:
        gate_failed = measured < entry["failure_threshold"]
    return {
        "dimension": entry["dimension"],
        "measured": measured,
        "score": round(score, 4),
        "weight": entry["weight"],
        "hard_gate": entry["hard_gate"],
        "gate_failed": gate_failed,
        "failure_threshold": entry["failure_threshold"],
        "evidence_command": entry["evidence_command"],
    }


def score_rubric(rubric, measurements):
    """The weighted total, the hard gates breached, and one verdict.

    HARD GATES OUTRANK THE TOTAL, ALWAYS. The total is still reported when a gate fails —
    a verdict that hid the improvement would be as unreadable as one that accepted it —
    but no total, however improved, turns `fail` into `pass`.
    """
    dimensions = [score_dimension(e, measurements[e["dimension"]]) for e in rubric]
    total_weight = sum(float(e["weight"]) for e in rubric)
    weighted = sum(float(d["weight"]) * d["score"] for d in dimensions)
    failures = [d["dimension"] for d in dimensions if d["hard_gate"] and d["gate_failed"]]
    return {
        "dimensions": dimensions,
        "weighted_total": round(weighted / total_weight, 4) if total_weight else 0.0,
        "hard_gate_failures": failures,
        "verdict": "fail" if failures else "pass",
    }


def validate_contract(raw):
    """Return (contract, findings). A finding names the field it is about."""
    findings = []
    if not isinstance(raw, dict):
        return None, ["contract: expected a JSON object"]
    contract = {}
    for field in CONTRACT_FIELDS:
        if field not in raw:
            findings.append("%s: missing — a loop declares all twelve fields before its first iteration" % field)
            continue
        value = raw[field]
        if field == "quality_rubric":
            rubric, rubric_findings = validate_rubric(value)
            if rubric_findings:
                findings.extend(rubric_findings)
                continue
            contract[field] = rubric
            continue
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
        findings.append("%s: not one of the twelve declared fields" % field)
    return contract, findings


# ---------------------------------------------------------------- predicates


def detect_stall(ledger, signature, state, dependency_missing, threshold):
    """Run the four predicates over the CURRENT EPOCH plus this iteration's reported facts.

    Order is deliberate and documented: a dependency that is simply gone is reported
    before a repetition that is its symptom.

    Scoped to the epoch because a revised contract is a different approach to the same work,
    and its history is not the predecessor's. Read across a revision, `circular-state`
    re-fires on the very state hash that produced the `revise` — wedging the loop a second
    time in a new way — and `retries-exhausted` reports a fresh contract's first iteration
    as its last (harness:RM-0478). A ledger written before epochs existed has no `epoch` on
    either side of this filter and defaults to 1, so a single-contract loop is unaffected.
    """
    epoch = ledger.get("epoch", 1)
    history = [it for it in ledger["iterations"] if it.get("epoch", 1) == epoch]

    if dependency_missing:
        return STALL_DEPENDENCY

    if signature:
        repeats = 1 + sum(
            1 for it in history if it.get("error_signature") == signature
        )
        if repeats >= threshold:
            return STALL_REPEATED_ERROR

    if state:
        if any(it.get("state_hash") == state for it in history):
            return STALL_CIRCULAR

    if len(history) + 1 >= ledger["contract"]["iteration_limit"]:
        return STALL_RETRIES

    return None


# ---------------------------------------------------------------- terminal state


#: The two states a ledger is ever in, and the words every refusal message draws from. Two
#: commands describing one unchanged ledger with two different words is the defect this
#: vocabulary exists to make impossible, not a symptom of it.
LEDGER_STATES = ("open", "closed")


def state_refusal(session, ledger, detail):
    """Render every refusal that turns on a ledger's state, in one place.

    The wedge was two commands describing one unchanged ledger in opposite words: `close`
    said *already closed* while `open` said *already open*, and one of them was a lie
    whichever way the ledger read. Prose cannot be held to that by review — each message was
    locally reasonable. So the state clause is generated from `ledger["status"]` rather than
    written, and every caller supplies only the way forward (harness:RM-0478).
    """
    return "%s: ledger is %s — %s" % (session, ledger.get("status", "closed"), detail)


def close_ledger(ledger, outcome, note=None, blocker=None,
                 evidence=None, recommended_next=None):
    """The ONE writer of terminal state, for both paths that can end a loop.

    `cmd_iterate`'s terminal branch and `cmd_close` wrote overlapping subsets of the same
    fields in two different shapes, so a reader had to know which path ended the loop before
    it could read the ledger — and `blocker-record-check.sh`, which reads every ledger, had
    to know both. A test asserting that two implementations agree is weaker than one
    implementation both of them call (harness:RM-0478).
    """
    ledger["status"] = "closed"
    ledger["final_outcome"] = outcome
    ledger["close_note"] = note
    ledger["close_blocker"] = blocker
    ledger["close_evidence"] = evidence
    ledger["close_recommended_next"] = recommended_next
    return ledger


# ---------------------------------------------------------------- subcommands


def cmd_open(args):
    existing = read_ledger(args.root, args.session)
    if existing is not None and existing.get("status") == "open" and not args.force:
        # STATUS, never existence. Every other command in this engine dispatches on the
        # ledger's status; `open` was the one that did not, and it was the one that wedged.
        # A `revise` means the approach is wrong and the contract needs changing — it ends
        # the loop, and then had nowhere to put the revised contract, while `close` refused
        # the same ledger for the opposite reason and said so in the opposite words. A
        # ledger's existence is not its state (harness:RM-0478).
        print(
            state_refusal(args.session, existing,
                          "end it with `close`, or pass --force to discard it"),
            file=sys.stderr,
        )
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

    # A closed ledger is RE-OPENED, not overwritten. The history is the thing a `revise`
    # exists to keep, which is why `--force` — whose whole meaning is to discard — was never
    # the answer to the wedge. `--force` keeps that meaning, for the corrupt ledger nobody
    # wants; it stops being the only way in.
    epochs = []
    iterations = []
    completed = []
    resumed = 0
    if existing is not None and not args.force and existing.get("status") == "closed":
        epochs = list(existing.get("epochs") or [])
        epochs.append({
            "n": len(epochs) + 1,
            "contract": existing["contract"],
            "final_outcome": existing["final_outcome"],
            "iterations": [it["n"] for it in existing["iterations"]],
            "close_note": existing.get("close_note"),
            "close_blocker": existing.get("close_blocker"),
            "close_evidence": existing.get("close_evidence"),
            "close_recommended_next": existing.get("close_recommended_next"),
        })
        iterations = existing["iterations"]
        completed = existing["completed_actions"]
        resumed = existing.get("resumed", 0)

    ledger = {
        "session": args.session,
        "contract": contract,
        "status": "open",
        "final_outcome": None,
        # The scalar is which contract is live; the list is every contract that preceded it.
        # Iterations stay cumulative and carry this number, so `n` is monotonic across a
        # revise and `quality_from` keeps naming exactly one record.
        "epoch": len(epochs) + 1,
        "epochs": epochs,
        "iterations": iterations,
        "completed_actions": completed,
        "resumed": resumed,
        "stall_threshold": args.stall_threshold,
        # A brief's id hashes the contract's rubric, so one that outlived its contract names
        # a packet this engine would no longer assemble — exactly what the single-use binding
        # exists to refuse.
        "pending_brief": None,
    }
    write_ledger(args.root, args.session, ledger)
    return emit(
        args,
        {"session": args.session, "status": "open", "epoch": ledger["epoch"],
         "next_iteration": len(iterations) + 1},
        "loop open: %s (epoch %d, limit %d)"
        % (args.session, ledger["epoch"], contract["iteration_limit"]),
    )


def cmd_iterate(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE
    if ledger["status"] != "open":
        print(
            state_refusal(
                args.session, ledger,
                "it ended with outcome '%s'; open a revised contract over it, or resume it "
                "if it was paused" % ledger["final_outcome"],
            ),
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

    # ---- the richer record (harness:RM-0468). Every check below runs BEFORE the first
    # write: a refusal that still records is not one, and a half-claimed action makes the
    # next resume skip work nobody did.
    record_findings = []

    critic_verdict = (getattr(args, "critic_verdict", None) or "").strip() or None
    decision = (getattr(args, "decision", None) or "").strip() or None
    evidence_paths = [p for p in (args.evidence_path or []) if str(p).strip()]

    if critic_verdict is not None and critic_verdict not in CRITIC_VERDICTS:
        record_findings.append(
            "--critic-verdict %s: not one of %s — a verdict outside the set cannot be "
            "compared with any other iteration's" % (critic_verdict, " / ".join(CRITIC_VERDICTS))
        )
    if decision is not None and decision not in DECISIONS:
        record_findings.append(
            "--decision %s: not one of %s" % (decision, " / ".join(DECISIONS))
        )
    critic_brief = (getattr(args, "critic_brief", None) or "").strip() or None
    pending = (ledger.get("pending_brief") or {}).get("brief_id")
    if critic_verdict is not None:
        # THE BINDING. A verdict must name a brief the engine emitted, and each brief is
        # spent by the iteration that uses it. This does not prove a different CONTEXT
        # produced the verdict — no predicate over repository state can — but it does mean
        # no verdict is recordable that was not about a packet the engine assembled from
        # the actual diff, the actual verification output and the contract's own rubric.
        if not critic_brief:
            record_findings.append(
                "--critic-brief required with --critic-verdict — run `loop brief` and hand "
                "the packet to a context that did not build the change; a verdict written "
                "by the builder in the same breath as the work is a self-assessment"
            )
        elif pending is None:
            record_findings.append(
                "--critic-brief %s: no brief is pending for this session — a brief is spent "
                "by the iteration that records its verdict, so run `loop brief` again"
                % critic_brief
            )
        elif critic_brief != pending:
            record_findings.append(
                "--critic-brief %s: not the brief this engine emitted (%s) — a verdict "
                "carrying an unknown id is about a packet nobody assembled"
                % (critic_brief, pending)
            )
        if not (args.critic_next or "").strip():
            record_findings.append(
                "--critic-next required with --critic-verdict — the critic names the single "
                "most valuable next improvement, and an obligation nobody enforces is "
                "indistinguishable from one nobody has"
            )
    if critic_verdict is not None and not evidence_paths:
        record_findings.append(
            "--evidence-path required with --critic-verdict — a verdict with nothing behind "
            "it is the self-assessment a critic pass exists to replace"
        )

    rubric = ledger["contract"].get("quality_rubric") or []
    measurements = None
    evaluation = None
    if args.measure:
        measurements, measure_findings = parse_measurements(rubric, args.measure)
        record_findings.extend(measure_findings)
        if not measure_findings:
            evaluation = score_rubric(rubric, measurements)

    if record_findings:
        for finding in record_findings:
            print(finding, file=sys.stderr)
        return EXIT_INVALID

    # Capability 5, made mechanical: a change is not retained over a breached hard gate.
    # Refused rather than warned — a warning in an unattended run is a line nobody reads,
    # and "net improvement" is never an excuse for silently breaking core behaviour. The
    # engine refuses what it MEASURED; with no measurements there is no breached gate to
    # protect against, and inventing one would be a check that could not run passing itself
    # off as a check that ran and found nothing.
    if decision == "retain" and evaluation and evaluation["hard_gate_failures"]:
        print(
            "retain refused: hard gate(s) breached — %s. Record `revert`, `revise` or "
            "`escalate`; a higher weighted total (%.2f) does not buy them."
            % (", ".join(evaluation["hard_gate_failures"]), evaluation["weighted_total"]),
            file=sys.stderr,
        )
        return EXIT_REGRESSION

    # The baseline is the engine's, so it cannot disagree with what was measured: the
    # previous MEASURED iteration's readings, or the rubric's declared baselines when there
    # is none. An unmeasured pass must not erase the last real reading, or before-versus-
    # after silently compares an after against nothing.
    baseline = None
    if measurements is not None:
        for previous in reversed(ledger["iterations"]):
            if previous.get("measurements"):
                baseline = previous["measurements"]
                break
        else:
            baseline = {e["dimension"]: e["baseline"] for e in rubric}

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
        "epoch": ledger.get("epoch", 1),
        "reported_outcome": args.outcome,
        "outcome": outcome,
        "stall": stall,
        "error_signature": signature,
        "state_hash": state,
        "dependency_missing": args.dependency_missing,
        "actions": list(args.action),
        "baseline": baseline,
        "measurements": measurements,
        "evaluation": evaluation,
        "files_changed": list(args.files_changed or []),
        "commands_run": list(args.command_run or []),
        "evidence_paths": evidence_paths,
        "critic_verdict": critic_verdict,
        "critic_next": args.critic_next,
        "critic_brief": critic_brief,
        "decision": decision,
        "blocker": blocker,
        "evidence": evidence,
        "recommended_next": recommended,
        "note": args.note,
    }
    ledger["iterations"].append(record)
    ledger["completed_actions"].extend(args.action)
    if critic_verdict is not None:
        ledger["pending_brief"] = None
    if outcome in TERMINAL_OUTCOMES:
        close_ledger(ledger, outcome, note=args.note, blocker=blocker,
                     evidence=evidence, recommended_next=recommended)
    write_ledger(args.root, args.session, ledger)

    human = "iteration %d: %s" % (record["n"], outcome)
    if stall:
        human += " (stall: %s, reported '%s')" % (stall, args.outcome)
    return emit(args, record, human)


def brief_digest(diff, verification, rubric):
    """A brief's identity: the hash of exactly what the critic will be shown.

    Derived from the artifacts rather than assigned, so a verdict carrying this id is a
    verdict about *this* diff, this verification output and this rubric. Change any of the
    three and the id changes, which is what makes a re-used brief detectable rather than
    merely discouraged.
    """
    payload = json.dumps(
        {"diff": diff, "verification": verification, "rubric": rubric},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


#: What the brief asks of the critic, in the packet itself rather than in a prompt the
#: builder writes. A critic that receives the builder's framing is reviewing the framing.
BRIEF_ASKS = (
    "Evaluate the diff against the rubric and the baseline, not against the builder's claims.",
    "Compare before versus after. A verdict about the after alone is not a comparison.",
    "Name any regression and any claim the verification output does not support.",
    "Return exactly one verdict from the set, and the single most valuable next improvement.",
    "Say which evidence supports the verdict.",
)


def cmd_brief(args):
    """Assemble the packet the critic receives, and record it as a single-use brief.

    The engine runs no critic and dispatches nothing — that boundary is unchanged. It
    packages the artifacts, and it refuses to record any verdict later that is not bound to
    a packet it packaged.
    """
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE

    texts = {}
    for label, path in (("diff", args.diff_file), ("verification", args.verification_file)):
        try:
            with open(path, encoding="utf-8") as handle:
                texts[label] = handle.read()
        except OSError as exc:
            # A channel that could not be read is a finding, never a silence: a brief with
            # an empty diff section would have the critic return a confident verdict about
            # a change it never saw.
            print(
                "brief: cannot read the %s at %s (%s)" % (label, path, exc.strerror),
                file=sys.stderr,
            )
            return EXIT_UNREADABLE
        if not texts[label].strip():
            print(
                "brief: the %s at %s is empty — a critic pass over no change is a verdict "
                "about nothing" % (label, path),
                file=sys.stderr,
            )
            return EXIT_UNREADABLE

    rubric = ledger["contract"].get("quality_rubric") or []
    baseline = None
    for previous in reversed(ledger["iterations"]):
        if previous.get("measurements"):
            baseline = previous["measurements"]
            break
    else:
        baseline = {e["dimension"]: e["baseline"] for e in rubric}

    digest = brief_digest(texts["diff"], texts["verification"], rubric)
    packet = {
        "brief_id": digest,
        "rubric": rubric,
        "baseline": baseline,
        "diff": texts["diff"],
        "verification": texts["verification"],
        "verdicts": list(CRITIC_VERDICTS),
        "asks": list(BRIEF_ASKS),
    }
    ledger["pending_brief"] = {"brief_id": digest}
    write_ledger(args.root, args.session, ledger)
    return emit(
        args, packet,
        "brief %s: %d rubric dimension(s), %d byte diff — hand this to a context that did "
        "not build the change"
        % (digest, len(rubric), len(texts["diff"])),
    )


def parse_measurements(rubric, raw_measures):
    """Return (measurements, findings) for a list of `<dimension>=<number>` strings.

    One parser, shared by `score` and `iterate`. Two parsers for one flag shape is how
    they come to disagree about what counts as a number, and the disagreement shows up as
    a ledger whose evaluation nobody can reproduce.
    """
    findings = []
    measurements = {}
    for raw in raw_measures:
        name, separator, value = raw.partition("=")
        name = name.strip()
        if not separator or not name:
            findings.append("--measure %r: expected <dimension>=<number>" % raw)
            continue
        if name in measurements:
            findings.append(
                "%s: measured twice — one measurement per dimension, or the score depends "
                "on which was read last" % name
            )
            continue
        try:
            measurements[name] = float(value)
        except ValueError:
            findings.append(
                "%s: %r is not a number — a channel that could not be read is a finding, "
                "never a zero" % (name, value)
            )

    declared = [entry["dimension"] for entry in rubric]
    for name in measurements:
        if name not in declared:
            findings.append(
                "%s: not a declared dimension — this rubric declares %s"
                % (name, ", ".join(declared))
            )
    for name in declared:
        if name not in measurements:
            findings.append(
                "%s: declared but not measured — a total over a subset is a score about a "
                "smaller rubric, reported as though it were this one" % name
            )
    return measurements, findings


def cmd_score(args):
    """Score one measurement per declared dimension against the rubric the loop was opened with.

    The engine does NOT run the evidence commands. Running arbitrary shell out of a JSON
    file under an unattended posture is a different and much larger safety question than
    this subcommand; what the engine enforces is that every dimension DECLARED a command,
    and it scores the numbers the caller measured with it.

    A measurement this pass could not read is a finding, never a zero — a rubric that
    silently scored an unreadable channel as its worst value would report a regression
    nobody caused, and one that scored it as its best would hide a real one.
    """
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE
    rubric = ledger["contract"].get("quality_rubric") or []
    if not rubric:
        print(
            "%s: this ledger's contract carries no quality rubric — it was opened before "
            "the field existed; open a new loop with one" % args.session,
            file=sys.stderr,
        )
        return EXIT_INVALID

    measurements, findings = parse_measurements(rubric, args.measure)

    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        return EXIT_INVALID

    result = score_rubric(rubric, measurements)
    human = "score %s: %.2f weighted" % (result["verdict"], result["weighted_total"])
    if result["hard_gate_failures"]:
        human += " — hard gate(s) breached: %s (the total does not buy them)" % ", ".join(
            result["hard_gate_failures"]
        )
    emit(args, result, human)
    return EXIT_GATE if result["verdict"] == "fail" else EXIT_OK


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
            "rubric_verdict": None,
            "weighted_total": None,
            "critic_verdict": None,
            "decision": None,
            "quality_from": None,
        }
        emit(args, payload, "%s: open, no iterations recorded" % ledger["session"])
        # A report over an empty history is distinguished from a clean one: a caller
        # that cannot tell "nothing found" from "nothing examined" cannot detect the
        # failure this repository has been bitten by most.
        return EXIT_EMPTY
    # The quality the record carries, surfaced — resolved from ONE record, never composed
    # field by field across several.
    #
    # `iterate` refuses `--decision retain` while a hard gate is breached, with an exit code
    # behind it (EXIT_REGRESSION). A reader that took the rubric verdict from iteration 2 and
    # the decision from iteration 1 would print exactly that refused pairing — the read path
    # contradicting the write path, with a snapshot that never existed at any moment.
    #
    # The record is the last one that was JUDGED — scored, reviewed, or decided. Preferring a
    # scored record over a later reviewed one drops the loop's most recent judgment: a reader
    # sees `rubric pass ... (iteration 1)` and concludes nobody reviewed the loop, while
    # iteration 2 carries a REVISE. `quality_from` names the record, so a reader never has to
    # guess which iteration the quality describes.
    #
    # ABSENT IS NOT ZERO. Every key is present and null when nothing scored, rather than
    # defaulted to 0.0: a loop nobody scored must not read as a loop that scored badly, and
    # a number is indistinguishable from a real one once it is printed.
    source = None
    for record in reversed(ledger["iterations"]):
        if (record.get("evaluation") or record.get("critic_verdict")
                or record.get("decision")):
            source = record
            break
    evaluation = (source or {}).get("evaluation") or {}
    quality = {
        "rubric_verdict": evaluation.get("verdict"),
        "weighted_total": evaluation.get("weighted_total"),
        "critic_verdict": (source or {}).get("critic_verdict"),
        "decision": (source or {}).get("decision"),
        "quality_from": (source or {}).get("n"),
    }

    payload = {
        "session": ledger["session"],
        "status": ledger["status"],
        "final_outcome": ledger["final_outcome"],
        "iterations": len(ledger["iterations"]),
        "completed_actions": ledger["completed_actions"],
        "stalls": [it["stall"] for it in ledger["iterations"] if it["stall"]],
        "last_outcome": ledger["iterations"][-1]["outcome"],
    }
    payload.update(quality)

    human = ("%s: %s after %d iteration(s), outcome %s"
             % (ledger["session"], ledger["status"], len(ledger["iterations"]),
                ledger["final_outcome"] or ledger["iterations"][-1]["outcome"]))
    if quality["rubric_verdict"] is not None:
        human += " — rubric %s at %.2f weighted" % (
            quality["rubric_verdict"], quality["weighted_total"])
    else:
        human += " — rubric not scored"
    if quality["quality_from"] is not None:
        human += " (iteration %d)" % quality["quality_from"]
    if quality["critic_verdict"] is not None:
        human += ", critic %s" % quality["critic_verdict"]
    if quality["decision"] is not None:
        human += ", %s" % quality["decision"]
    return emit(args, payload, human)


def cmd_resume(args):
    ledger = require_ledger(args)
    if ledger is None:
        return EXIT_USAGE

    if ledger["status"] == "closed":
        if ledger["final_outcome"] != "pause":
            print(
                state_refusal(
                    args.session, ledger,
                    "it ended with outcome '%s', and only a paused loop is resumable; open "
                    "a revised contract over it instead" % ledger["final_outcome"],
                ),
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
        # Names the state it read, and the way forward from it. The wedge was two commands
        # describing one unchanged ledger in opposite words: this said `already closed`
        # while `open` said `already open`, and one of them was a lie either way.
        print(
            state_refusal(
                args.session, ledger,
                "it ended with outcome '%s'; open a revised contract over it, or resume it "
                "if it was paused" % ledger["final_outcome"],
            ),
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
    close_ledger(ledger, args.outcome, note=args.note, blocker=args.blocker,
                 evidence=args.evidence, recommended_next=args.recommended_next)
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
    opened.add_argument("--contract", required=True, help="path to the twelve-field contract JSON")
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
    iterated.add_argument(
        "--measure", action="append", default=[], metavar="DIMENSION=NUMBER",
        help="the number a rubric dimension's evidence command produced; the engine scores it",
    )
    iterated.add_argument(
        "--files-changed", action="append", default=[], metavar="PATH",
        help="a file or artifact this iteration changed",
    )
    iterated.add_argument(
        "--command-run", action="append", default=[], metavar="COMMAND",
        help="a command this iteration ran, verbatim",
    )
    iterated.add_argument(
        "--evidence-path", action="append", default=[], metavar="PATH",
        help="where the evidence lives; required with --critic-verdict",
    )
    iterated.add_argument(
        "--critic-verdict", metavar="VERDICT",
        help="PASS / FAIL / REVISE / REVERT / ESCALATE, from a context that did not build the change",
    )
    iterated.add_argument(
        "--critic-next", help="the single most valuable next improvement, in the critic's words",
    )
    iterated.add_argument(
        "--critic-brief", metavar="BRIEF_ID",
        help="the id `loop brief` emitted; required with --critic-verdict, and spent by this iteration",
    )
    iterated.add_argument(
        "--decision", metavar="DECISION",
        help="retain / revert / revise / escalate — refused as `retain` over a breached hard gate",
    )
    iterated.add_argument("--note", help="free text recorded with the iteration")
    iterated.set_defaults(func=cmd_iterate)

    briefed = common(subparsers.add_parser(
        "brief", help="assemble the packet a critic receives, as a single-use brief"))
    briefed.add_argument("--diff-file", required=True, help="the change under review")
    briefed.add_argument(
        "--verification-file", required=True, help="the verification output, verbatim")
    briefed.set_defaults(func=cmd_brief)

    scored = common(subparsers.add_parser(
        "score", help="score one measurement per declared rubric dimension"))
    scored.add_argument(
        "--measure", action="append", default=[], metavar="DIMENSION=NUMBER",
        help="the number the dimension's evidence command produced; one per declared dimension",
    )
    scored.set_defaults(func=cmd_score)

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
