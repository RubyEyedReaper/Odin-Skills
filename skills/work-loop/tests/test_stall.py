"""The four stall predicates — each one a mechanical decision over the ledger.

The primary testable core: each predicate turns an iteration into a *named non-continue
outcome*, rather than into another iteration. The break: a loop that reports `continue`
forever because nothing in the engine ever contradicts the caller — thirty identical
failures recorded as thirty ordinary iterations.

The predicates run inside `iterate`, over the ledger's own history. There is no separate
command to forget.
"""
from __future__ import annotations

import unittest

from . import _fixtures as fx
from scripts.loop import (
    EXIT_OK,
    STALL_CIRCULAR,
    STALL_DEPENDENCY,
    STALL_REPEATED_ERROR,
    STALL_RETRIES,
    error_signature,
)


def iterate(root, **kwargs):
    argv = ["iterate", "--root", root.path, "--session", fx.SESSION]
    for flag, value in kwargs.items():
        flag = "--" + flag.replace("_", "-")
        if isinstance(value, list):
            for item in value:
                argv += [flag, item]
        else:
            argv += [flag, str(value)]
    return fx.run_cli(*argv)


class ErrorSignature(unittest.TestCase):
    """A predicate keyed on raw text never fires; one keyed on a signature does."""

    def test_two_renderings_of_one_failure_share_a_signature(self):
        first = (
            "Traceback (most recent call last):\n"
            '  File "/home/dell/Repos/Odin/api/db.py", line 42, in connect\n'
            "ConnectionError at 0x7f3a2b1c: connection to 'pg-1' timed out after 30s"
        )
        second = (
            "Traceback (most recent call last):\n"
            '  File "/tmp/build-99/api/db.py", line 117, in connect\n'
            "ConnectionError at 0x55ff0142: connection to 'pg-2' timed out after 5s"
        )
        self.assertEqual(error_signature(first), error_signature(second))

    def test_two_different_failures_do_not_share_a_signature(self):
        self.assertNotEqual(
            error_signature("ConnectionError: connection refused"),
            error_signature("KeyError: 'coverage'"),
        )

    def test_the_signature_is_stable_and_short(self):
        sig = error_signature("ConnectionError: connection refused")
        self.assertEqual(sig, error_signature("connectionerror:   connection refused"))
        self.assertLessEqual(len(sig), 64)

    def test_no_error_has_no_signature(self):
        self.assertIsNone(error_signature(""))
        self.assertIsNone(error_signature(None))


class RepeatedError(unittest.TestCase):
    """Predicate 1 — N identical failures by normalised error signature."""

    ERR = "ConnectionError at 0x1: connection to 'pg' timed out after 30s"

    def test_below_the_threshold_the_loop_continues(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            for n in range(2):
                code, _, _ = iterate(root, outcome="continue", error=self.ERR)
                self.assertEqual(code, EXIT_OK)
            self.assertEqual(fx.read_ledger(root)["iterations"][-1]["outcome"], "continue")

    def test_the_third_identical_failure_overrides_continue(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            for n in range(3):
                iterate(root, outcome="continue", error=self.ERR.replace("0x1", "0x%d" % n))
            last = fx.read_ledger(root)["iterations"][-1]
            self.assertEqual(last["reported_outcome"], "continue")
            self.assertNotEqual(last["outcome"], "continue")
            self.assertEqual(last["stall"], STALL_REPEATED_ERROR)

    def test_the_override_ends_the_loop(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            for n in range(3):
                iterate(root, outcome="continue", error=self.ERR)
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["status"], "closed")
            self.assertIn(ledger["final_outcome"], ("escalate", "revise", "stop"))

    def test_three_different_failures_do_not_stall(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            for err in ("KeyError: 'a'", "ValueError: b", "TimeoutError: c"):
                iterate(root, outcome="continue", error=err)
            last = fx.read_ledger(root)["iterations"][-1]
            self.assertEqual(last["outcome"], "continue")
            self.assertIsNone(last["stall"])


class CircularState(unittest.TestCase):
    """Predicate 2 — circular behaviour by repeated state hash."""

    def test_a_state_seen_before_overrides_continue(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            iterate(root, outcome="continue", state="coverage=61 files=4")
            iterate(root, outcome="continue", state="coverage=67 files=3")
            iterate(root, outcome="continue", state="coverage=61 files=4")
            last = fx.read_ledger(root)["iterations"][-1]
            self.assertNotEqual(last["outcome"], "continue")
            self.assertEqual(last["stall"], STALL_CIRCULAR)

    def test_monotonic_state_does_not_stall(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            for pct in (61, 67, 74):
                iterate(root, outcome="continue", state="coverage=%d" % pct)
            self.assertIsNone(fx.read_ledger(root)["iterations"][-1]["stall"])


class RetriesExhausted(unittest.TestCase):
    """Predicate 3 — the declared iteration limit is a limit, not a note."""

    def test_the_last_permitted_iteration_overrides_continue(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root, iteration_limit=3)
            for n in range(3):
                code, _, _ = iterate(root, outcome="continue", state="s%d" % n)
                self.assertEqual(code, EXIT_OK)
            ledger = fx.read_ledger(root)
            last = ledger["iterations"][-1]
            self.assertEqual(last["stall"], STALL_RETRIES)
            self.assertNotEqual(last["outcome"], "continue")
            self.assertEqual(ledger["status"], "closed")

    def test_the_limit_is_read_from_the_contract_not_a_constant(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root, iteration_limit=1)
            iterate(root, outcome="continue", state="s0")
            self.assertEqual(
                fx.read_ledger(root)["iterations"][-1]["stall"], STALL_RETRIES
            )


class DependencyUnavailable(unittest.TestCase):
    """Predicate 4 — a declared dependency the iteration could not reach."""

    def test_a_declared_dependency_going_missing_overrides_continue(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            iterate(root, outcome="continue", dependency_missing="postgres")
            last = fx.read_ledger(root)["iterations"][-1]
            self.assertEqual(last["stall"], STALL_DEPENDENCY)
            self.assertNotEqual(last["outcome"], "continue")

    def test_an_undeclared_dependency_is_a_finding_not_a_stall(self):
        """Naming a dependency the contract never declared is a contract defect.

        Refusing it keeps the predicate honest: the four predicates decide over
        *declared* state, and a caller inventing a dependency name at iteration time
        would otherwise be able to end any loop it liked.
        """
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = iterate(root, outcome="continue", dependency_missing="redis")
            self.assertNotEqual(code, EXIT_OK)
            self.assertIn("redis", err)


class EveryPredicateNamesItsOutcome(unittest.TestCase):
    def test_each_stall_reason_maps_to_a_non_continue_outcome(self):
        from scripts.loop import OUTCOMES, STALL_OUTCOME

        reasons = {STALL_REPEATED_ERROR, STALL_CIRCULAR, STALL_RETRIES, STALL_DEPENDENCY}
        self.assertEqual(set(STALL_OUTCOME), reasons)
        for reason, outcome in STALL_OUTCOME.items():
            with self.subTest(reason=reason):
                self.assertIn(outcome, OUTCOMES)
                self.assertNotEqual(outcome, "continue")

    def test_a_reported_terminal_outcome_is_never_overridden(self):
        """The predicates contradict a `continue`; they do not relabel a decision."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root, iteration_limit=1)
            iterate(root, outcome="complete", state="done")
            last = fx.read_ledger(root)["iterations"][-1]
            self.assertEqual(last["outcome"], "complete")


class Status(unittest.TestCase):
    def test_status_reports_the_standing_verdict_and_does_not_re_decide(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root, iteration_limit=1)
            iterate(root, outcome="continue", state="s0")
            before = fx.read_ledger(root)
            code, out, _ = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            self.assertEqual(code, EXIT_OK)
            self.assertIn(before["final_outcome"], out)
            self.assertEqual(fx.read_ledger(root), before)


if __name__ == "__main__":
    unittest.main()
