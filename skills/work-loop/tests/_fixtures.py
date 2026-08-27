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


def valid_contract(**overrides) -> dict:
    """A contract carrying all eleven declared fields, before overrides are applied."""
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
