"""The outcome set — exactly one of six per iteration, and none of them blocks.

The primary testable core: an iteration records one outcome, drawn from a closed set of
six, and only `continue` permits a further iteration. The break: a ledger that records
two outcomes for one iteration, or a seventh outcome nobody enumerated, so "why did this
cycle end" has no single answer.

The second core here is the one ADR-0103 exists for: `escalate` and `pause` are outcomes
of the *iteration*, never of the session. Neither waits for a human.
"""
from __future__ import annotations

import json
import os
import unittest

from . import _fixtures as fx
from scripts.loop import (
    EXIT_CLOSED,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_REPEAT,
    EXIT_USAGE,
    OUTCOMES,
    TERMINAL_OUTCOMES,
)


class OutcomeSet(unittest.TestCase):
    def test_exactly_six_outcomes(self):
        self.assertEqual(
            OUTCOMES,
            ("continue", "complete", "revise", "escalate", "pause", "stop"),
        )

    def test_only_continue_is_non_terminal(self):
        self.assertEqual(set(OUTCOMES) - set(TERMINAL_OUTCOMES), {"continue"})


class OneOutcomePerIteration(unittest.TestCase):
    def test_an_iteration_records_exactly_one_outcome(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "wrote-test-a",
            )
            self.assertEqual(code, EXIT_OK)
            iterations = fx.read_ledger(root)["iterations"]
            self.assertEqual(len(iterations), 1)
            recorded = iterations[0]
            self.assertIn(recorded["outcome"], OUTCOMES)
            # Mutual exclusion is a property of the record, not of the caller's care:
            # one `outcome` key, one value, and no second outcome-bearing key.
            outcome_keys = [k for k in recorded if k.endswith("outcome")]
            self.assertEqual(sorted(outcome_keys), ["outcome", "reported_outcome"])
            self.assertIsInstance(recorded["outcome"], str)

    def test_an_unknown_outcome_is_a_usage_error(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "retry",
            )
            self.assertEqual(code, EXIT_USAGE)

    def test_a_terminal_outcome_closes_the_loop(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "complete",
            )
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["status"], "closed")
            self.assertEqual(ledger["final_outcome"], "complete")

    def test_a_closed_loop_refuses_a_further_iteration(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "stop",
            )
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue",
            )
            self.assertEqual(code, EXIT_CLOSED)
            self.assertEqual(len(fx.read_ledger(root)["iterations"]), 1)


class TheContract(unittest.TestCase):
    ELEVEN = (
        "purpose", "owner", "starting_state", "inputs", "expected_outputs",
        "success_criteria", "failure_criteria", "dependencies", "iteration_limit",
        "timeout_behaviour", "escalation_path",
    )

    def test_open_records_all_eleven_fields(self):
        with fx.LedgerRoot() as root:
            code, _, _ = fx.open_loop(root)
            self.assertEqual(code, EXIT_OK)
            contract = fx.read_ledger(root)["contract"]
            self.assertEqual(sorted(contract), sorted(self.ELEVEN))

    def test_a_missing_field_refuses_the_open(self):
        for field in self.ELEVEN:
            with self.subTest(field=field), fx.LedgerRoot() as root:
                contract = fx.valid_contract()
                del contract[field]
                path = os.path.join(root.path, "c.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(contract, handle)
                code, _, err = fx.run_cli(
                    "open", "--root", root.path, "--session", fx.SESSION,
                    "--contract", path,
                )
                self.assertEqual(code, EXIT_INVALID)
                self.assertIn(field, err)
                self.assertFalse(os.path.exists(root.ledger_path()))

    def test_an_empty_field_refuses_the_open(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(root, purpose="")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("purpose", err)

    def test_iteration_limit_must_be_a_positive_integer(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(root, iteration_limit=0)
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("iteration_limit", err)


class NeitherEscalateNorPauseBlocks(unittest.TestCase):
    """ADR-0103. A run that stops has ended; these two outcomes end the *loop*."""

    def test_escalate_requires_a_recommended_next_action(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "escalate", "--note", "postgres refused the connection",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("recommended-next", err)

    def test_escalate_records_the_blocker_and_ends_the_loop(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "escalate", "--note", "postgres refused the connection",
                "--recommended-next", "capture a roadmap item for the container",
            )
            self.assertEqual(code, EXIT_OK)
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["status"], "closed")
            self.assertEqual(ledger["final_outcome"], "escalate")
            self.assertEqual(
                ledger["iterations"][-1]["recommended_next"],
                "capture a roadmap item for the container",
            )

    def test_pause_checkpoints_the_completed_actions_and_ends_the_loop(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "wrote-test-a",
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "pause", "--note", "context past half the ceiling",
            )
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["status"], "closed")
            self.assertEqual(ledger["final_outcome"], "pause")
            self.assertEqual(ledger["completed_actions"], ["wrote-test-a"])

    def test_no_outcome_path_can_wait_for_a_human(self):
        """Mechanical, at the source: the engine has no interactive call to make.

        Asserted this way on purpose. An outcome that blocks would do so by reading
        stdin or by asking the harness a question, and both are visible in the source
        of a module whose every other decision is a pure function of the ledger.
        """
        import inspect

        import scripts.loop as engine

        source = inspect.getsource(engine)
        for forbidden in ("input(", "AskUserQuestion", "getpass", "sys.stdin.read"):
            self.assertNotIn(forbidden, source)


class Close(unittest.TestCase):
    def test_close_refuses_a_non_terminal_outcome(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "close", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue",
            )
            self.assertEqual(code, EXIT_USAGE)

    def test_close_refuses_an_already_closed_ledger(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "close", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "complete",
            )
            code, _, _ = fx.run_cli(
                "close", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "complete",
            )
            self.assertEqual(code, EXIT_CLOSED)


class Usage(unittest.TestCase):
    def test_no_arguments_prints_help_and_exits_non_zero(self):
        code, out, _ = fx.run_cli()
        self.assertNotEqual(code, EXIT_OK)
        self.assertIn("open", out)

    def test_a_missing_ledger_is_a_usage_error_not_a_crash(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.run_cli(
                "iterate", "--root", root.path, "--session", "never-opened",
                "--outcome", "continue",
            )
            self.assertEqual(code, EXIT_USAGE)
            self.assertIn("never-opened", err)

    def test_repeat_and_closed_are_distinct_codes(self):
        self.assertNotEqual(EXIT_REPEAT, EXIT_CLOSED)
        self.assertNotEqual(EXIT_REPEAT, EXIT_INVALID)


if __name__ == "__main__":
    unittest.main()
