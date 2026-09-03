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
import os
import unittest

from . import _fixtures as fx
from scripts.loop import (
    CONTRACT_FIELDS,
    EXIT_GATE,
    EXIT_INVALID,
    EXIT_OK,
    RUBRIC_FIELDS,
    command_findings,
    validate_rubric,
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


class StaticCommandInspection(unittest.TestCase):
    """`open` reads each evidence command — it never runs one (harness:RM-0476, DEC-0091).

    The defect: the engine tested `evidence_command` for non-emptiness and nothing else, so
    the first real loop opened under the rubric declared a command carrying the literal
    placeholders `--root R --session S`, scored 100.0 and passed. Execution at open was
    scored and vetoed — a subprocess spawned inside this engine is not a tool call, so it
    would run outside every always-on guard. What is left is everything a reader can decide
    about the string without running it.
    """

    #: Every evidence command committed in this repository, as of this change. The negative
    #: control for all three refusals below: a predicate that fires on the real population
    #: is a false positive, not a gate, and the way to know is to measure the hit rate
    #: against the population before adopting it.
    REAL_COMMANDS = (
        "bash .claude/scripts/ci-local.sh",
        "ls .claude/tests/*.test.sh | wc -l",
        "bash .claude/scripts/doc-reference-check.sh",
        "bash .claude/scripts/context-budget.sh bytes --component always-on",
        "bash .claude/scripts/blocker-record-check.sh",
        "bash .claude/scripts/sample-contract-check.sh",
    )

    #: The command the defect was observed on, reduced to its shape. The placeholders sit
    #: inside a quoted python program, so a token-wise scan of the argv would never see
    #: them — the pattern reads the raw command text for exactly that reason.
    OBSERVED = (
        "python3 -c \"import subprocess;"
        "subprocess.run(['python3','-m','scripts.loop','status',"
        "'--root','R','--session','S','--json'])\""
    )

    def test_open_refuses_the_command_the_defect_was_observed_on(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(evidence_command=self.OBSERVED)]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("placeholder", err)

    def test_open_refuses_an_angle_bracket_placeholder(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[fx.dimension(evidence_command="bash run.sh <session-id>")],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("placeholder", err)

    def test_open_refuses_a_command_whose_program_does_not_resolve(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(evidence_command="this-binary-does-not-exist --wat")
                ],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("this-binary-does-not-exist", err)

    def test_open_refuses_a_command_that_is_not_shell_parseable(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(evidence_command="bash -c 'unbalanced")]
            )
            self.assertEqual(code, EXIT_INVALID)
            # The engine's own words, not shlex's — a case asserting on a dependency's
            # message text reds on that dependency's next release.
            self.assertIn("cannot be parsed as a shell command", err)

    def test_every_segment_of_a_pipeline_is_inspected(self):
        """A pipeline's later segments are where an unrunnable program hides."""
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(evidence_command="ls . | no-such-counter -l")
                ],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("no-such-counter", err)

    def test_an_environment_assignment_prefix_is_not_read_as_the_program(self):
        with fx.LedgerRoot() as root:
            code, _, _ = fx.open_loop(
                root,
                quality_rubric=[fx.dimension(evidence_command="LC_ALL=C bash script.sh")],
            )
            self.assertEqual(code, EXIT_OK)

    def test_the_repositorys_own_evidence_commands_all_pass(self):
        for command in self.REAL_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(command_findings(command, ".", "d"), [])

    def test_a_flag_taking_an_uppercase_word_is_not_a_placeholder(self):
        """`--format JSON` reads like a placeholder to a loose pattern and is not one."""
        self.assertEqual(
            command_findings("jq --format JSON . file.json", ".", "d"), []
        )


class AHoldTheLineDimension(unittest.TestCase):
    """harness:RM-0473 — a dimension whose job is to NOT move.

    Found by using the rubric, not by reading it. `validate_rubric` refused a dimension whose
    `target` equals its `baseline`, on the stated grounds that a dimension that cannot move scores
    nothing and measures nothing (ADR-0137). That is true of an optimisation objective and false of
    a hard gate, whose entire job is to not move — so two honest dimensions were unwritable:

        suite-failures     baseline 0, must stay 0
        record-integrity   baseline 0, must stay 0

    Those are exactly the checks a rubric most wants as hard gates. The workaround reached for first
    was a fractional target (0 -> 0.0001) to slip past the refusal, which is a lie written into the
    contract to satisfy a validator.

    `must_not_regress` is DECLARED, never inferred from the numbers coinciding. The same reasoning
    `DIRECTIONS` carries: a derived flag silently changes what a dimension means when an author
    mistypes a number, and reads correct on the page.
    """

    def test_a_declared_hold_the_line_dimension_is_accepted(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(
                        dimension="suite-failures", baseline=0, target=0,
                        failure_threshold=0, direction="lower-is-better",
                        hard_gate=True, must_not_regress=True,
                    )
                ],
            )
            self.assertEqual(code, EXIT_OK, err)

    def test_holding_a_ceiling_is_accepted_too(self):
        """`higher-is-better` at 100% must stay declarable: the direction cross-check compares
        baseline to target, and for a line being held they are equal in both directions."""
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(
                        dimension="arm-coverage", baseline=100, target=100,
                        failure_threshold=100, direction="higher-is-better",
                        hard_gate=True, must_not_regress=True,
                    )
                ],
            )
            self.assertEqual(code, EXIT_OK, err)

    def test_a_hold_the_line_dimension_that_names_a_different_target_is_refused(self):
        """The contradiction case. A dimension claiming to hold a line while naming a target it
        does not sit at is two declarations disagreeing, and taking either one silently is how a
        swapped pair gets accepted."""
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[fx.dimension(baseline=2, target=0, must_not_regress=True)],
            )
            self.assertEqual(code, EXIT_INVALID)
            # Asserted on the reason, not on the key name. Before the key existed this case passed
            # against "must_not_regress is not one of the eight declared keys" — a refusal for a
            # completely different reason, which is how a case comes to assert nothing.
            self.assertIn("hold a line", err)

    def test_a_non_boolean_must_not_regress_is_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                quality_rubric=[fx.dimension(baseline=0, target=0, must_not_regress="yes")],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("must be true or false", err)

    def test_a_held_line_scores_100_and_passes(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(
                        dimension="suite-failures", baseline=0, target=0,
                        failure_threshold=0, direction="lower-is-better",
                        hard_gate=True, must_not_regress=True,
                    )
                ],
            )
            code, out, err = _score(root, "suite-failures=0")
            self.assertEqual(code, EXIT_OK, err)
            result = json.loads(out)
            self.assertEqual(result["weighted_total"], 100.0)
            self.assertEqual(result["verdict"], "pass")

    def test_a_broken_line_scores_zero_and_fails_the_verdict(self):
        """The whole point. A hold-the-line dimension that moved has failed, and no weighted total
        turns that into a pass."""
        with fx.LedgerRoot() as root:
            fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(
                        dimension="suite-failures", baseline=0, target=0,
                        failure_threshold=0, direction="lower-is-better",
                        hard_gate=True, must_not_regress=True,
                    )
                ],
            )
            code, out, _ = _score(root, "suite-failures=3")
            result = json.loads(out)
            self.assertEqual(code, EXIT_GATE)
            self.assertEqual(result["verdict"], "fail")
            self.assertEqual(result["hard_gate_failures"], ["suite-failures"])
            held = result["dimensions"][0]
            self.assertEqual(held["score"], 0.0)

    def test_the_reference_documents_sample_validates_against_the_engine(self):
        """`sample-contract-check.sh` validates sample *contracts*; a sample *dimension* is outside
        what it scans, so the one in quality-rubric.md would rot silently. Driven through the real
        validator here rather than read — ADR-0141's principle, applied one level down."""
        import json as _json
        import re

        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "references", "quality-rubric.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        samples = [
            _json.loads(block)
            for block in re.findall(r"```json\n(\{.*?\})\n```", text, re.S)
            if '"must_not_regress"' in block
        ]
        self.assertEqual(len(samples), 1, "the hold-the-line sample moved or was removed")
        rubric, findings = validate_rubric(samples, root=".")
        self.assertEqual(findings, [])
        self.assertTrue(rubric[0]["must_not_regress"])

    def test_the_fractional_target_workaround_is_no_longer_the_only_way(self):
        """The evidence that the defect was real was a 0 -> 0.0001 target invented to pass
        validation. That declaration is still legal — it is a well-formed optimisation objective —
        so this asserts the honest declaration is available, not that the dishonest one is banned."""
        with fx.LedgerRoot() as root:
            code, _, _ = fx.open_loop(
                root,
                quality_rubric=[
                    fx.dimension(baseline=0, target=0, failure_threshold=0,
                                 must_not_regress=True)
                ],
            )
            self.assertEqual(code, EXIT_OK)


class TheRubricArithmeticCannotDivideByZero(unittest.TestCase):
    """Pins what this change must not disturb — the brief names both as at risk."""

    def test_a_target_equal_to_its_baseline_is_still_refused(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, quality_rubric=[fx.dimension(baseline=3, target=3)]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("target equals its baseline", err)

    def test_no_dimension_that_survives_validation_has_a_zero_divisor(self):
        """`score_dimension` divides by target - baseline; open refuses the only way it is 0."""
        with fx.LedgerRoot() as root:
            code, _, _ = fx.open_loop(root)
            self.assertEqual(code, EXIT_OK)
            for entry in fx.read_ledger(root)["contract"]["quality_rubric"]:
                self.assertNotEqual(entry["target"], entry["baseline"])


class ScoringRefusesWhatItCannotRead(unittest.TestCase):
    def test_scoring_a_session_with_no_ledger_is_a_usage_error(self):
        with fx.LedgerRoot() as root:
            code, _, err = _score(root, "gate-integrity=0", session="never-opened")
            self.assertNotEqual(code, EXIT_OK)
            self.assertIn("no ledger", err)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
