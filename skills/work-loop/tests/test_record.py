"""The iteration record — what a later reader has instead of the session that wrote it.

The measured break: one coordinator ledger held 29 iterations, every one carrying only
`actions`, `dependency_missing`, `error_signature`, `n`, `note`, `outcome`,
`recommended_next`, `reported_outcome`, `stall`, `state_hash` — and the last one had `note`
and `recommended_next` both null. No baseline, no evidence path, no verdict, no decision.
An iteration that improved something is indistinguishable from one that merely ran.

The design answer is not "more optional fields", because optional fields are exactly what
was null 29 times. It is that **the engine derives everything it can** — the baseline from
the previous iteration's own measurements, the evaluation from the rubric — and **refuses
what it cannot check**: a critic verdict with no evidence path, a verdict outside the five
words, and a `retain` decision over a breached hard gate.
"""
from __future__ import annotations

import unittest

from . import _fixtures as fx
from scripts.loop import (
    CRITIC_VERDICTS,
    DECISIONS,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_REGRESSION,
)

#: The four measurements that satisfy every dimension of the fixture's default rubric with
#: every hard gate held. Named once: a case that wanted a passing evaluation and typed the
#: four flags itself would drift from the fixture rubric the moment either changed.
CLEAN = (
    "--measure", "gate-integrity=0",
    "--measure", "regression-matrix-strength=100",
    "--measure", "record-integrity=0",
    "--measure", "context-budget=34000",
)

#: The same, with `gate-integrity` over its threshold of 0 — one breached hard gate.
BREACHED = (
    "--measure", "gate-integrity=2",
    "--measure", "regression-matrix-strength=100",
    "--measure", "record-integrity=0",
    "--measure", "context-budget=34000",
)


def _iterate(root, *extra, session=fx.SESSION, outcome="continue", action="a"):
    argv = [
        "iterate", "--root", root.path, "--session", session,
        "--outcome", outcome, "--action", action,
    ]
    return fx.run_cli(*argv, *extra)


class TheVocabulariesAreClosed(unittest.TestCase):
    def test_the_critic_verdict_set_is_the_specs_five_words(self):
        self.assertEqual(
            CRITIC_VERDICTS, ("PASS", "FAIL", "REVISE", "REVERT", "ESCALATE")
        )

    def test_the_decision_set_is_four_words(self):
        self.assertEqual(DECISIONS, ("retain", "revert", "revise", "escalate"))

    def test_the_two_vocabularies_are_separate_from_the_loops_outcomes(self):
        """A critic verdict judges a CHANGE; an outcome ends an ITERATION. Merging them
        would put `continue` in a set where it means nothing."""
        from scripts.loop import OUTCOMES

        self.assertEqual(set(CRITIC_VERDICTS) & set(OUTCOMES), set())


class CriticVerdictNeedsEvidence(unittest.TestCase):
    """A verdict with nothing behind it is the self-assessment this campaign removes."""

    def test_a_critic_verdict_with_no_evidence_path_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--critic-verdict", "PASS")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("evidence-path", err)

    def test_a_verdict_outside_the_five_words_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "LGTM", "--evidence-path", "logs/ci.log"
            )
            # EXIT_INVALID specifically, not merely "not ok": argparse's own usage error
            # is EXIT_USAGE, and a looser assertion here passed against an engine that had
            # never heard of the flag.
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("LGTM", err)

    def test_a_decision_outside_the_four_words_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--decision", "ship-it")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("ship-it", err)

    def test_a_refused_iteration_records_nothing_and_claims_no_action(self):
        """A refusal that still records is not one, and a half-claimed action makes the
        next resume skip work nobody did."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = _iterate(root, "--critic-verdict", "PASS", action="wrote-test-a")
            self.assertEqual(code, EXIT_INVALID)
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["iterations"], [])
            self.assertEqual(ledger["completed_actions"], [])

    def test_an_evidence_path_with_no_verdict_is_accepted(self):
        """Evidence without a verdict is an ordinary iteration that collected artifacts.
        The obligation runs one way only."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--evidence-path", "logs/ci.log")
            self.assertEqual(code, EXIT_OK, err)
            record = fx.read_ledger(root)["iterations"][0]
            self.assertEqual(record["evidence_paths"], ["logs/ci.log"])
            self.assertIsNone(record["critic_verdict"])

    def test_a_complete_record_carries_every_declared_field(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            # harness:RM-0469 bound a verdict to a brief the engine emitted, so a COMPLETE
            # record now includes one. This case was written in wave 2 with an unbound
            # verdict and is updated here rather than relaxed: the property it asserts —
            # every declared field round-trips — is unchanged.
            brief = fx.brief_for(root)
            code, _, err = _iterate(
                root, *CLEAN, "--critic-brief", brief,
                "--files-changed", "scripts/loop.py",
                "--command-run", "python3 -m unittest discover -s tests -t .",
                "--evidence-path", "logs/suite.txt",
                "--critic-verdict", "PASS",
                "--critic-next", "measure the suite's wall clock next",
                "--decision", "retain",
            )
            self.assertEqual(code, EXIT_OK, err)
            record = fx.read_ledger(root)["iterations"][0]
            self.assertEqual(record["files_changed"], ["scripts/loop.py"])
            self.assertEqual(
                record["commands_run"], ["python3 -m unittest discover -s tests -t ."]
            )
            self.assertEqual(record["evidence_paths"], ["logs/suite.txt"])
            self.assertEqual(record["critic_verdict"], "PASS")
            self.assertEqual(record["critic_next"], "measure the suite's wall clock next")
            self.assertEqual(record["decision"], "retain")
            self.assertEqual(record["critic_brief"], brief)


class BaselineIsDerived(unittest.TestCase):
    """The baseline is the engine's, so it cannot disagree with what was measured."""

    def test_the_first_iterations_baseline_is_the_rubrics_declared_baselines(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, *CLEAN)
            self.assertEqual(code, EXIT_OK, err)
            record = fx.read_ledger(root)["iterations"][0]
            self.assertEqual(record["baseline"]["gate-integrity"], 2)
            self.assertEqual(record["baseline"]["context-budget"], 38000)

    def test_the_second_iterations_baseline_is_the_firsts_measurements(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _iterate(root, *CLEAN, action="a")
            _iterate(
                root, "--measure", "gate-integrity=0",
                "--measure", "regression-matrix-strength=97",
                "--measure", "record-integrity=0",
                "--measure", "context-budget=35000",
                action="b",
            )
            first, second = fx.read_ledger(root)["iterations"]
            self.assertEqual(second["baseline"], first["measurements"])
            self.assertEqual(second["baseline"]["context-budget"], 34000.0)

    def test_an_unmeasured_iteration_does_not_become_the_next_ones_baseline(self):
        """A blank pass must not erase the last real reading, or before-versus-after
        silently compares an after against nothing."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _iterate(root, *CLEAN, action="a")
            _iterate(root, action="b")                       # no --measure at all
            _iterate(root, *BREACHED, action="c", outcome="pause")
            first, blank, third = fx.read_ledger(root)["iterations"]
            self.assertIsNone(blank["measurements"])
            self.assertIsNone(blank["evaluation"])
            self.assertEqual(third["baseline"], first["measurements"])

    def test_the_evaluation_is_the_engines_and_carries_a_verdict(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _iterate(root, *CLEAN)
            evaluation = fx.read_ledger(root)["iterations"][0]["evaluation"]
            self.assertEqual(evaluation["verdict"], "pass")
            self.assertEqual(evaluation["weighted_total"], 100.0)
            self.assertEqual(
                [d["dimension"] for d in evaluation["dimensions"]],
                ["gate-integrity", "regression-matrix-strength",
                 "record-integrity", "context-budget"],
            )

    def test_a_measurement_naming_an_undeclared_dimension_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, *CLEAN, "--measure", "invented=1")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("invented", err)

    def test_a_partial_measurement_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--measure", "gate-integrity=0")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("not measured", err)


class RegressionProtection(unittest.TestCase):
    """Capability 5, made mechanical: a change is not retained over a breached hard gate.

    These cases carry no `--critic-verdict`. They did in wave 2, where it was decoration:
    the predicate is over the DECISION and the MEASUREMENTS, and a verdict alongside it
    asserted nothing. harness:RM-0469 made a verdict cost a brief, which turned that
    decoration into a second refusal firing before the one under test — so it is dropped
    rather than fed. Narrowing a case to exactly its property is the repair; feeding it a
    brief would have kept a case that tests two things and reports one.

    "Net improvement" is never an excuse for silently breaking core behaviour, so the
    engine refuses the decision rather than warning about it — a warning in an unattended
    run is a line nobody reads.
    """

    def test_retain_over_a_breached_hard_gate_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, *BREACHED,
                "--evidence-path", "logs/ci.log",
                "--decision", "retain",
            )
            self.assertEqual(code, EXIT_REGRESSION)
            self.assertIn("gate-integrity", err)
            self.assertEqual(fx.read_ledger(root)["iterations"], [])

    def test_revert_over_the_same_measurements_is_accepted(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, *BREACHED,
                "--evidence-path", "logs/ci.log",
                "--decision", "revert",
            )
            self.assertEqual(code, EXIT_OK, err)
            record = fx.read_ledger(root)["iterations"][0]
            self.assertEqual(record["decision"], "revert")
            self.assertEqual(record["evaluation"]["verdict"], "fail")

    def test_retain_with_every_hard_gate_held_is_accepted(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, *CLEAN,
                "--evidence-path", "logs/ci.log",
                "--decision", "retain",
            )
            self.assertEqual(code, EXIT_OK, err)

    def test_retain_with_no_measurements_is_accepted(self):
        """No evaluation means no breached gate to protect against. The engine refuses
        what it measured, never what it did not look at — a check that could not run must
        not pass itself off as a check that ran and found nothing."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--decision", "retain")
            self.assertEqual(code, EXIT_OK, err)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
