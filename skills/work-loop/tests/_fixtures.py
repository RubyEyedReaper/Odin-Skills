"""Fixture builders shared by the three test modules.

Named with a leading underscore so `unittest discover`'s `test*.py` pattern does not
collect it: a helper module that reports itself as a test suite is how a suite comes to
claim more coverage than it has.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

# The skill directory, so `import scripts.loop` resolves however the test is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SESSION = "sess-fixture"


#: One well-formed rubric dimension, before overrides. Eight keys, no more and no fewer —
#: `validate_rubric` refuses an unknown key for the same reason `validate_contract` refuses
#: an unknown field: an interface that silently accepts extras cannot tell a typo from an
#: extension.
def dimension(**overrides) -> dict:
    entry = {
        "dimension": "gate-integrity",
        "evidence_command": "bash .claude/scripts/ci-local.sh",
        "baseline": 2,
        "target": 0,
        "weight": 40,
        "failure_threshold": 0,
        "direction": "lower-is-better",
        "hard_gate": True,
    }
    entry.update(overrides)
    return entry


def default_rubric() -> list:
    """The four-dimension default set recorded as DEC-0090.

    Baselines here are fixture values, not claims about this repository: a real contract
    measures its own baseline at `open` time. Restating a live count in a fixture is how a
    fixture comes to assert something about a tree it never read.
    """
    return [
        dimension(),
        dimension(
            dimension="regression-matrix-strength",
            evidence_command="ls .claude/tests/*.test.sh | wc -l",
            baseline=90, target=100, weight=15, failure_threshold=90,
            direction="higher-is-better", hard_gate=True,
        ),
        dimension(
            dimension="record-integrity",
            evidence_command="bash .claude/scripts/doc-reference-check.sh",
            baseline=1, target=0, weight=25, failure_threshold=0,
            direction="lower-is-better", hard_gate=True,
        ),
        dimension(
            dimension="context-budget",
            evidence_command="bash .claude/scripts/context-budget.sh bytes --component always-on",
            baseline=38000, target=34000, weight=20, failure_threshold=40000,
            direction="lower-is-better", hard_gate=False,
        ),
    ]


def valid_contract(**overrides) -> dict:
    """A contract carrying all twelve declared fields, before overrides are applied."""
    contract = {
        "purpose": "drive the coverage gate to 80%",
        "owner": "harness",
        "starting_state": "coverage at 61% on branch harness/coverage",
        "inputs": ["the failing coverage report"],
        "expected_outputs": ["a committed test module per uncovered file"],
        "success_criteria": ["ci-local.sh reports coverage >= 80"],
        "failure_criteria": ["the same suite fails three times with one signature"],
        "dependencies": ["postgres"],
        "iteration_limit": 5,
        "timeout_behaviour": "checkpoint and pause after 20 minutes without progress",
        "escalation_path": "capture a roadmap item and end the loop",
        "quality_rubric": default_rubric(),
    }
    contract.update(overrides)
    return contract


class LedgerRoot:
    """A throwaway --root whose .claude/.runtime/work-loop/ the engine writes into."""

    def __enter__(self) -> "LedgerRoot":
        self.path = tempfile.mkdtemp(prefix="work-loop-test-")
        os.makedirs(os.path.join(self.path, ".claude", ".runtime", "work-loop"))
        return self

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def ledger_path(self, session: str = SESSION) -> str:
        return os.path.join(
            self.path, ".claude", ".runtime", "work-loop", session + ".json"
        )


def run_cli(*argv) -> tuple[int, str, str]:
    """Invoke the engine in-process; stdout is data, stderr is diagnostics."""
    from scripts.loop import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def open_loop(root: LedgerRoot, session: str = SESSION, **overrides):
    """`open` with a valid contract, returning the CLI result triple."""
    import json

    contract_file = os.path.join(root.path, session + "-contract.json")
    with open(contract_file, "w", encoding="utf-8") as handle:
        json.dump(valid_contract(**overrides), handle)
    return run_cli(
        "open", "--root", root.path, "--session", session, "--contract", contract_file
    )


def read_ledger(root: LedgerRoot, session: str = SESSION) -> dict:
    import json

    with open(root.ledger_path(session), encoding="utf-8") as handle:
        return json.load(handle)
