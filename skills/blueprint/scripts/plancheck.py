"""plancheck — the mechanical gate on a construction plan.

A plan is executable *cold* or it is not a plan. This checks the properties a script can
check: every task names its files, carries a command that verifies it, and states when it
is finished; nothing is left as a placeholder; and no task depends on one that comes after
it. Judgment — is this the right decomposition? — stays with the plan-depth rubric, which
a script has no business pretending to apply.

Usage:
    python3 -m scripts.plancheck <plan.md> [--json]

Exit 0 clean, 1 with findings, 2 when the file cannot be read.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Separator after the number is whatever the author reached for: "Task 1: x", "Task 1 — x",
# "Task 1. x". Requiring a colon silently reports "no tasks" on a perfectly good plan.
TASK_RE = re.compile(r"^#{2,4}\s+(Task\s+(\d+)\s*[:.–—-]\s*.+?)\s*$", re.I)
TASK_REF_RE = re.compile(r"\bTask\s+(\d+)\b", re.I)
FENCE_RE = re.compile(r"^\s*```")

#: Text that means "someone will decide this later" — the defining property of a plan
#: that cannot be executed cold. Matched case-insensitively against non-fenced lines.
PLACEHOLDER_PATTERNS = (
    (r"\bTBD\b", "TBD"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bimplement(ed)? later\b", "implement later"),
    (r"\bfill in (the )?details?\b", "fill in details"),
    (r"\bsimilar to task\b", "similar to Task N"),
    (r"\badd appropriate\b", "add appropriate ..."),
    (r"\bhandle edge cases\b", "handle edge cases"),
    (r"\bas needed\b", "as needed"),
    (r"\band so on\b", "and so on"),
)

VERIFICATION_HINTS = (
    re.compile(r"^\s*Run:\s*\S", re.I),
    re.compile(r"^\s*Expected:\s*\S", re.I),
    re.compile(r"^\s*Verify:\s*\S", re.I),
)

# Matched against the task's *raw* lines, not the fence-stripped body: a fence-opening
# line is exactly what _unfenced() drops, so a hint of this shape in VERIFICATION_HINTS
# could never fire (RM-0037). A runnable shell block is the strong form of verification;
# leaving it unrecognised pushed authors toward a prose `Verify:` line, which is the weak
# form this gate exists to discourage. Shells only — a fenced `python` or `node` snippet
# is usually illustration, and counting it would make every example a verification.
SHELL_FENCE_RE = re.compile(r"^\s*```(bash|sh|shell|console)\b", re.I)

FILES_RE = re.compile(r"^\s*\*\*Files:?\*\*", re.I)
EXIT_RE = re.compile(r"^\s*\*\*(Exit criteria|Done when|Acceptance):?\*\*", re.I)
GOAL_RE = re.compile(r"^\s*\*\*Goal:?\*\*\s*\S", re.I)


def _finding(code, message, task=None, line=0):
    return {"code": code, "message": message, "task": task, "line": line}


def _split_tasks(lines):
    """[(heading, number, start_index, end_index)] over the plan's task sections."""
    heads = []
    fenced = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = TASK_RE.match(line)
        if match:
            heads.append((match.group(1).strip(), int(match.group(2)), index))

    tasks = []
    for position, (heading, number, start) in enumerate(heads):
        end = heads[position + 1][2] if position + 1 < len(heads) else len(lines)
        tasks.append((heading, number, start, end))
    return tasks


def _unfenced(lines, start, end):
    """(index, line) pairs in [start, end) that are not inside a code fence."""
    out = []
    fenced = False
    for index in range(start, end):
        if FENCE_RE.match(lines[index]):
            fenced = not fenced
            continue
        if not fenced:
            out.append((index, lines[index]))
    return out


def check_text(text):
    """Return a list of findings. Empty means the plan passes the mechanical gate."""
    lines = text.splitlines()
    findings = []

    if not any(GOAL_RE.match(line) for line in lines):
        findings.append(_finding(
            "no-goal",
            "plan has no **Goal:** line — a plan whose objective is implicit cannot be "
            "checked against its own outcome",
        ))

    tasks = _split_tasks(lines)
    if not tasks:
        findings.append(_finding(
            "no-tasks",
            "no '### Task N: ...' sections found — nothing here can be dispatched",
        ))
        return findings

    numbers = {number for _, number, _, _ in tasks}

    for heading, number, start, end in tasks:
        body = _unfenced(lines, start + 1, end)
        body_text = "\n".join(line for _, line in body)

        if not any(FILES_RE.match(line) for _, line in body):
            findings.append(_finding(
                "no-files", "no **Files:** block — the executor cannot know what to touch",
                heading, start + 1))

        verified = any(
            hint.match(line) for _, line in body for hint in VERIFICATION_HINTS
        ) or any(SHELL_FENCE_RE.match(line) for line in lines[start + 1:end])
        if not verified:
            findings.append(_finding(
                "no-verification",
                "no verification command (Run:/Expected:/Verify: or a shell block) — "
                "'done' would be a claim, not an observation",
                heading, start + 1))

        if not any(EXIT_RE.match(line) for _, line in body):
            findings.append(_finding(
                "no-exit-criteria",
                "no **Exit criteria:** — without one the task ends when the executor "
                "gets bored", heading, start + 1))

        for index, line in body:
            for pattern, label in PLACEHOLDER_PATTERNS:
                if re.search(pattern, line, re.I):
                    findings.append(_finding(
                        "placeholder",
                        "placeholder %r — a cold executor cannot resolve it: %s"
                        % (label, line.strip()[:80]),
                        heading, index + 1))

        for referenced in {int(n) for n in TASK_REF_RE.findall(body_text)}:
            if referenced == number:
                continue
            if referenced not in numbers:
                findings.append(_finding(
                    "unknown-task",
                    "refers to Task %d, which this plan does not define" % referenced,
                    heading, start + 1))
            elif referenced > number:
                findings.append(_finding(
                    "forward-dependency",
                    "depends on Task %d, which runs later — reorder them or the "
                    "executor blocks on work that does not exist yet" % referenced,
                    heading, start + 1))

    return findings


def codes(findings):
    """Just the codes, for assertions and quick scanning."""
    return [f["code"] for f in findings]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="plancheck", description="Mechanical gate on a construction plan.")
    parser.add_argument("plan", help="path to the plan markdown file")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.plan):
        sys.stderr.write("[plancheck] no such plan: %s\n" % args.plan)
        return 2
    with open(args.plan, encoding="utf-8") as fh:
        findings = check_text(fh.read())

    if args.json:
        print(json.dumps(findings, indent=2))
    elif not findings:
        print("ok — %s passes the mechanical gate (judgment still yours)" % args.plan)
    else:
        for finding in findings:
            where = " [%s]" % finding["task"] if finding["task"] else ""
            print("%s:%d %s%s: %s" % (
                args.plan, finding["line"], finding["code"], where, finding["message"]))
        print("\n%d finding(s). Fix and re-run — this gate is not advisory."
              % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
