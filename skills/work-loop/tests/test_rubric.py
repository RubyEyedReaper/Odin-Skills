"""The quality rubric — a twelfth contract field, and a scoring pass hard gates outrank.

The primary testable core: "better" is decided by numbers a command produced, against
weights and thresholds declared *before* the first iteration. The break this prevents is
the one measured on the coordinator's own ledger — twenty-nine iterations, none of them
carrying a baseline, so a later reader cannot tell an iteration that improved something
from one that merely ran.

The second core is the property the whole rubric exists to protect, and it has exactly one
test: a hard-gate failure outranks any weighted total, including one that went *up*. A
rubric where a high enough score buys a broken gate is a rubric that will be used to
justify a broken gate.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import (
    CONTRACT_FIELDS,
    EXIT_GATE,
    EXIT_INVALID,
    EXIT_OK,
    RUBRIC_FIELDS,
)


class TheFieldIsDeclared(unittest.TestCase):
    def test_the_contract_declares_twelve_fields(self):
        self.assertIn("quality_rubric", CONTRACT_FIELDS)
        self.assertEqual(len(CONTRACT_FIELDS), 12)

    def test_a_dimension_declares_eight_keys(self):
        self.assertEqual(
            RUBRIC_FIELDS,
            (
                "dimension",
                "evidence_command",
                "baseline",
                "target",
                "weight",
                "failure_threshold",
                "direction",
                "hard_gate",
            ),
        )


class RubricValidation(unittest.TestCase):
    """`open` refuses a rubric that cannot decide anything, and says which key failed."""

    def test_a_dimension_with_no_evidence_command_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(evidence_command="")]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("evidence_command", err)

    def test_a_dimension_whose_evidence_command_is_absent_is_refused(self):
        with fx.LedgerRoot() as root:
            entry = fx.dimension()
            del entry["evidence_command"]
            code, _, err = fx.open_loop(root, quality_rubric=[entry])
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("evidence_command", err)

    def test_an_empty_rubric_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(root, quality_rubric=[])
            self.assertEqual(code, EXIT_INVALID)
            # Asserted on the specific message, not on the field name: the unknown-field
            # refusal that predates this item also names `quality_rubric`, so a looser
            # assertion here would pass against an engine with no rubric validation at all.
            self.assertIn("at least one dimension", err)

    def test_direction_disagreeing_with_baseline_to_target_is_refused(self):
        """A swapped baseline and target reads correct and inverts the failure test."""
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(baseline=0, target=10, direction="lower-is-better")
                ],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("direction", err)

    def test_a_target_equal_to_its_baseline_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(baseline=5, target=5)]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("target", err)

    def test_a_non_positive_weight_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(weight=0)]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("weight", err)

    def test_duplicate_dimension_names_are_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(dimension="a"),
                    fx.dimension(dimension="a", evidence_command="echo 1"),
                ],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("duplicate", err.lower())

    def test_an_unknown_dimension_key_is_refused(self):
        with fx.LedgerRoot() as root:
            entry = fx.dimension()
            entry["notes"] = "extra"
            code, _, err = fx.open_loop(root, quality_rubric=[entry])
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("notes", err)

    def test_a_non_boolean_hard_gate_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(hard_gate="yes")]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("hard_gate", err)

    def test_a_valid_rubric_is_carried_into_the_ledger(self):
        """`resume` must recover the rubric the loop was OPENED with, not the current one."""
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(root)
            self.assertEqual(code, EXIT_OK, err)
            rubric = fx.read_ledger(root)["contract"]["quality_rubric"]
            self.assertEqual(len(rubric), 4)
            self.assertEqual(rubric[0]["dimension"], "gate-integrity")


def _score(root, *measures, session=fx.SESSION):
    argv = ["score", "--root", root.path, "--session", session, "--json"]
    for measure in measures:
        argv += ["--measure", measure]
    return fx.run_cli(*argv)


class Scoring(unittest.TestCase):
    """Every declared dimension is measured, or the score is about a smaller field."""

    def test_a_dimension_left_unmeasured_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _score(root, "gate-integrity=0")
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("not measured", err)

    def test_an_undeclared_dimension_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _score(
                root,
                "gate-integrity=0",
                "regression-matrix-strength=95",
                "record-integrity=0",
                "context-budget=36000",
                "invented=1",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("invented", err)

    def test_a_non_numeric_measurement_is_refused_rather_than_coerced(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _score(
                root,
                "gate-integrity=green",
                "regression-matrix-strength=95",
                "record-integrity=0",
                "context-budget=36000",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("gate-integrity", err)

    def test_every_target_met_scores_100_and_passes(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, out, err = _score(
                root,
                "gate-integrity=0",
                "regression-matrix-strength=100",
                "record-integrity=0",
                "context-budget=34000",
            )
            self.assertEqual(code, EXIT_OK, err)
            result = json.loads(out)
            self.assertEqual(result["weighted_total"], 100.0)
            self.assertEqual(result["verdict"], "pass")
            self.assertEqual(result["hard_gate_failures"], [])

    def test_a_measurement_beyond_its_target_does_not_score_above_100(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, out, _ = _score(
                root,
                "gate-integrity=0",
                "regression-matrix-strength=250",
                "record-integrity=0",
                "context-budget=1",
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(out)["weighted_total"], 100.0)

    def test_a_soft_dimension_past_its_threshold_does_not_fail_the_verdict(self):
        """context-budget is an optimisation objective, not a gate. It reports, it does not veto."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, out, _ = _score(
                root,
                "gate-integrity=0",
                "regression-matrix-strength=100",
                "record-integrity=0",
                "context-budget=45000",
            )
            self.assertEqual(code, EXIT_OK)
            result = json.loads(out)
            budget = next(
                d for d in result["dimensions"] if d["dimension"] == "context-budget"
            )
            self.assertTrue(budget["gate_failed"])
            self.assertFalse(budget["hard_gate"])
            self.assertEqual(result["hard_gate_failures"], [])
            self.assertEqual(result["verdict"], "pass")


class HardGatesOutrankTheTotal(unittest.TestCase):
    """The property the whole rubric exists to protect.

    Two scoring passes over one rubric. The second has a STRICTLY HIGHER weighted total
    than the first and one breached hard gate. The verdict is `fail`, the exit code is
    distinct from both `malformed` and `ok`, and the improvement is still reported — a
    verdict that hid the improvement would be as unreadable as one that accepted it.
    """

    RUBRIC = [
        fx.dimension(
            dimension="hard-one",
            evidence_command="bash gate.sh",
            baseline=10, target=0, weight=20, failure_threshold=0,
            direction="lower-is-better", hard_gate=True,
        ),
        fx.dimension(
            dimension="soft-one",
            evidence_command="bash count.sh",
            baseline=0, target=100, weight=80, failure_threshold=0,
            direction="higher-is-better", hard_gate=False,
        ),
    ]

    def test_a_hard_gate_failure_outranks_an_improved_weighted_total(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root, quality_rubric=self.RUBRIC)

            ok_code, before_out, _ = _score(root, "hard-one=0", "soft-one=10")
            gate_code, after_out, _ = _score(root, "hard-one=5", "soft-one=100")

            before, after = json.loads(before_out), json.loads(after_out)

            self.assertGreater(after["weighted_total"], before["weighted_total"])
            self.assertEqual(before["verdict"], "pass")
            self.assertEqual(after["verdict"], "fail")
            self.assertEqual(after["hard_gate_failures"], ["hard-one"])
            self.assertEqual(ok_code, EXIT_OK)
            self.assertEqual(gate_code, EXIT_GATE)

    def test_the_breached_gate_scored_above_zero_on_its_own_dimension(self):
        """The gate failed on its THRESHOLD, not on scoring badly — the two are different
        questions, and conflating them is how a rubric starts letting a good score through."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root, quality_rubric=self.RUBRIC)
            _, out, _ = _score(root, "hard-one=5", "soft-one=100")
            hard = next(
                d for d in json.loads(out)["dimensions"] if d["dimension"] == "hard-one"
            )
            self.assertEqual(hard["score"], 50.0)
            self.assertTrue(hard["gate_failed"])


class ScoringRefusesWhatItCannotRead(unittest.TestCase):
    def test_scoring_a_session_with_no_ledger_is_a_usage_error(self):
        with fx.LedgerRoot() as root:
            code, _, err = _score(root, "gate-integrity=0", session="never-opened")
            self.assertNotEqual(code, EXIT_OK)
            self.assertIn("no ledger", err)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
