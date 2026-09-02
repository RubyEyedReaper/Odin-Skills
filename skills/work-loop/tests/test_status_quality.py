"""`status` answers how a loop is doing, not only how many times it ran.

The record carries a rubric verdict, a weighted total, a critic verdict and a decision
(harness:RM-0467 through RM-0469). `status` — the one command a reader runs to ask about a
loop — reported none of them, so the quality was recorded and unreadable. Measured at
`4809bb3e`: the payload had seven keys and not one was about quality.

The property that matters as much as the reporting: **absent is not zero.** A loop nobody
scored must not read as a loop that scored badly, and a `weighted_total` of `0.0` over an
unmeasured ledger says exactly the wrong thing.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import EXIT_OK

QUALITY_KEYS = ("rubric_verdict", "weighted_total", "critic_verdict", "decision")

CLEAN = (
    "--measure", "gate-integrity=0",
    "--measure", "regression-matrix-strength=100",
    "--measure", "record-integrity=0",
    "--measure", "context-budget=34000",
)

BREACHED = (
    "--measure", "gate-integrity=2",
    "--measure", "regression-matrix-strength=100",
    "--measure", "record-integrity=0",
    "--measure", "context-budget=34000",
)


def _status(root, session=fx.SESSION):
    code, out, err = fx.run_cli(
        "status", "--root", root.path, "--session", session, "--json"
    )
    return code, json.loads(out) if out.strip() else None, err


class StatusReportsQuality(unittest.TestCase):
    def test_a_scored_iteration_surfaces_all_four_quality_keys(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            brief = fx.brief_for(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *CLEAN,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", brief, "--critic-verdict", "PASS",
                "--critic-next", "measure the suite's wall clock",
                "--decision", "retain",
            )
            code, payload, err = _status(root)
            self.assertEqual(code, EXIT_OK, err)
            for key in QUALITY_KEYS:
                self.assertIn(key, payload)
            self.assertEqual(payload["rubric_verdict"], "pass")
            self.assertEqual(payload["weighted_total"], 100.0)
            self.assertEqual(payload["critic_verdict"], "PASS")
            self.assertEqual(payload["decision"], "retain")

    def test_a_failing_rubric_verdict_is_reported_as_failing(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *BREACHED,
                "--decision", "revert",
            )
            _, payload, _ = _status(root)
            self.assertEqual(payload["rubric_verdict"], "fail")
            self.assertEqual(payload["decision"], "revert")

    def test_an_unscored_ledger_reports_quality_absent_not_zero(self):
        """A loop nobody scored must not read as a loop that scored badly.

        `weighted_total: 0.0` over an unmeasured ledger is the same defect as a check that
        could not run reporting a clean result — the number is indistinguishable from a
        real one, and it is worse than no number at all.
        """
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a",
            )
            _, payload, _ = _status(root)
            for key in QUALITY_KEYS:
                self.assertIn(key, payload)
                self.assertIsNone(payload[key])

    def test_quality_comes_from_the_last_iteration_that_carried_it(self):
        """A blank pass after a scored one must not blank the report — the same rule the
        derived baseline follows, applied to the reader's view."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *CLEAN,
                "--decision", "retain",
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "b",
            )
            _, payload, _ = _status(root)
            self.assertEqual(payload["rubric_verdict"], "pass")
            self.assertEqual(payload["weighted_total"], 100.0)
            self.assertEqual(payload["decision"], "retain")

    def test_the_human_line_names_the_verdict_and_the_total(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *CLEAN,
                "--decision", "retain",
            )
            code, out, err = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("pass", out)
            self.assertIn("100.00", out)

    def test_an_empty_ledger_still_reports_nothing_examined(self):
        """Exit 4 is unchanged by this item: a report over no iterations must stay
        distinguishable from a clean one."""
        from scripts.loop import EXIT_EMPTY

        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            self.assertEqual(code, EXIT_EMPTY)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
