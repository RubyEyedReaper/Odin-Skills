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

    def write(self, name: str, text: str) -> str:
        """Write a scratch file inside the throwaway root and return its absolute path.

        Inside the root on purpose: a fixture that wrote to the checkout would make the
        case's verdict depend on the tree it ran in.
        """
        path = os.path.join(self.path, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def write_json(self, name: str, payload) -> str:
        """Write a JSON scratch file inside the throwaway root and return its path."""
        import json

        return self.write(name, json.dumps(payload))

    def ledger_path(self, session: str = SESSION) -> str:
        return os.path.join(
            self.path, ".claude", ".runtime", "work-loop", session + ".json"
        )

    def discard_ledger(self, session: str = SESSION) -> None:
        """Remove one session's ledger, leaving the runtime directory in place.

        For a case that must drive the SAME session to two different terminal states and
        compare them. A fresh LedgerRoot per arm would also work and would hide which
        directory the second arm wrote into.
        """
        if os.path.exists(self.ledger_path(session)):
            os.remove(self.ledger_path(session))


def brief_for(root, session: str = SESSION, diff: str | None = None) -> str:
    """Emit a critic brief inside `root` and return its id.

    Shared by the record and critic suites so both bind a verdict the same way; two
    helpers for one handshake is how they come to disagree about what a brief is.
    """
    diff_file = root.write("brief.diff", diff or "--- a/x\n+++ b/x\n+one line\n")
    ver_file = root.write("brief-verification.txt", "Ran 1 test\n\nOK\n")
    code, out, err = run_cli(
        "brief", "--root", root.path, "--session", session,
        "--diff-file", diff_file, "--verification-file", ver_file, "--json",
    )
    if code != 0:
        raise AssertionError("brief fixture failed (%d): %s" % (code, err))
    import json as _json

    return _json.loads(out)["brief_id"]


def run_cli(*argv) -> tuple[int, str, str]:
    """Invoke the engine in-process; stdout is data, stderr is diagnostics."""
    from scripts.loop import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def open_loop(root: LedgerRoot, session: str = SESSION, extra_argv=None, **overrides):
    """`open` with a valid contract, returning the CLI result triple.

    `extra_argv` appends flags the case is about — `--baseline-evidence` in particular. It
    is a list rather than a second keyword per flag so a case can pass the same flag twice,
    which is how a repeatable flag is actually used.
    """
    import json

    contract_file = os.path.join(root.path, session + "-contract.json")
    with open(contract_file, "w", encoding="utf-8") as handle:
        json.dump(valid_contract(**overrides), handle)
    return run_cli(
        "open", "--root", root.path, "--session", session, "--contract", contract_file,
        *(extra_argv or []),
    )


def read_ledger(root: LedgerRoot, session: str = SESSION) -> dict:
    import json

    with open(root.ledger_path(session), encoding="utf-8") as handle:
        return json.load(handle)


def revised_loop(root: LedgerRoot, session: str = SESSION) -> None:
    """Drive a ledger to a terminal `revise` — the exact state harness:RM-0478 was filed over.

    Two iterations, the second reporting `revise`, so the ledger ends `closed` with a
    `final_outcome` of `revise`, two completed actions and two distinct state hashes. Cases
    that re-open build on this; cases about the wedge itself assert against it.
    """
    open_loop(root, session)
    run_cli("iterate", "--root", root.path, "--session", session,
            "--outcome", "continue", "--action", "probe", "--state", "s=1")
    run_cli("iterate", "--root", root.path, "--session", session,
            "--outcome", "revise", "--action", "rethink", "--state", "s=2")
