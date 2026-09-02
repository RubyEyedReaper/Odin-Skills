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

QUALITY_KEYS = ("rubric_verdict", "weighted_total", "critic_verdict", "decision",
                "quality_from")

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

    def test_a_blank_pass_after_a_scored_one_does_not_blank_the_report(self):
        """The last iteration that was *scored* is the one reported, not the last one run."""
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
            self.assertEqual(payload["quality_from"], 1)

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
            code, out, _ = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            self.assertEqual(code, EXIT_EMPTY)
            payload = json.loads(out)
            # The KEY SET, not the code alone. A consumer written against the documented
            # shape must not raise KeyError on exactly the path this command exists to keep
            # distinguishable — and asserting only the exit code is what let it.
            for key in QUALITY_KEYS:
                self.assertIn(key, payload)
                self.assertIsNone(payload[key])


class QualityIsOneRecordsQuality(unittest.TestCase):
    """Four fields resolved per-field compose a snapshot that never existed.

    `iterate` refuses `--decision retain` when a hard gate is breached — that pairing is a
    write-time invariant with an exit code behind it. A reader that takes the rubric verdict
    from iteration 2 and the decision from iteration 1 prints exactly the pairing the engine
    refuses, and the reader's contradiction of the writer is the defect, not the display.
    """

    CRITIC = ("--critic-verdict", "PASS", "--critic-next", "measure the wall clock")

    def test_a_stale_critic_verdict_is_not_pinned_to_a_fresh_rubric_failure(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            brief = fx.brief_for(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *CLEAN,
                "--evidence-path", "logs/ci.log", "--critic-brief", brief,
                *self.CRITIC, "--decision", "retain",
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "b", *BREACHED,
            )
            _, payload, _ = _status(root)
            self.assertEqual(payload["rubric_verdict"], "fail")
            self.assertEqual(payload["quality_from"], 2)
            # Iteration 2 was never reviewed and never decided. Saying so is the report.
            self.assertIsNone(payload["critic_verdict"])
            self.assertIsNone(payload["decision"])

    def test_the_reverse_orientation_reports_the_later_clean_record(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a", *BREACHED,
            )
            brief = fx.brief_for(root, diff="--- a/x\n+++ b/x\n+later\n")
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "b", *CLEAN,
                "--evidence-path", "logs/ci.log", "--critic-brief", brief,
                "--critic-verdict", "REVISE", "--critic-next", "tighten the guard",
                "--decision", "revise",
            )
            _, payload, _ = _status(root)
            self.assertEqual(payload["rubric_verdict"], "pass")
            self.assertEqual(payload["critic_verdict"], "REVISE")
            self.assertEqual(payload["decision"], "revise")
            self.assertEqual(payload["quality_from"], 2)

    def test_an_unscored_ledger_that_was_reviewed_still_names_its_record(self):
        """No iteration carries an evaluation, but one carries a verdict. The fallback is
        the last record carrying either, and `quality_from` names it — a reader must never
        have to guess which iteration the quality describes."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            brief = fx.brief_for(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a",
                "--evidence-path", "logs/ci.log", "--critic-brief", brief,
                "--critic-verdict", "REVISE", "--critic-next", "measure first",
                "--decision", "revise",
            )
            _, payload, _ = _status(root)
            self.assertIsNone(payload["rubric_verdict"])
            self.assertIsNone(payload["weighted_total"])
            self.assertEqual(payload["critic_verdict"], "REVISE")
            self.assertEqual(payload["quality_from"], 1)

    def test_quality_from_is_null_when_nothing_was_scored_or_reviewed(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a",
            )
            _, payload, _ = _status(root)
            self.assertIsNone(payload["quality_from"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
