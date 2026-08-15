"""Tests for scripts/validate.py — written before implementation (TDD RED phase)."""
import unittest
import sys
import os

# Ensure the skill root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.validate import validate_spec, apply_constraints, criteria_quality_warnings, aggregate_scores


def _minimal_spec(**overrides):
    """Return a minimal valid spec, applying any keyword overrides."""
    spec = {
        "goal": "Pick the best option",
        "reversibility": "two-way",
        "constraints": [],
        "options": [
            {"id": "opt-a", "label": "Option A"},
            {"id": "opt-b", "label": "Option B"},
        ],
        "criteria": [
            {"id": "crit-1", "label": "Performance", "weight": 50, "direction": "higher-is-better"},
            {"id": "crit-2", "label": "Cost", "weight": 50, "direction": "lower-is-better"},
        ],
        "scorers": [
            {
                "id": "scorer-1",
                "label": "Team",
                "scores": {
                    "opt-a": {
                        "crit-1": {"value": 80, "confidence": 0.9},
                        "crit-2": {"value": 40, "confidence": 0.8},
                    },
                    "opt-b": {
                        "crit-1": {"value": 60, "confidence": 0.7},
                        "crit-2": {"value": 70, "confidence": 0.9},
                    },
                },
            }
        ],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }
    spec.update(overrides)
    return spec


class TestValidateSpec(unittest.TestCase):

    # ── happy path ──────────────────────────────────────────────────────────
    def test_valid_spec_returns_empty_list(self):
        errors = validate_spec(_minimal_spec())
        self.assertEqual(errors, [])

    # ── goal ────────────────────────────────────────────────────────────────
    def test_missing_goal_fails(self):
        spec = _minimal_spec()
        del spec["goal"]
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("goal" in e.lower() for e in errors))

    def test_empty_goal_fails(self):
        errors = validate_spec(_minimal_spec(goal=""))
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("goal" in e.lower() for e in errors))

    def test_non_string_goal_fails(self):
        errors = validate_spec(_minimal_spec(goal=123))
        self.assertTrue(len(errors) > 0)

    # ── reversibility ───────────────────────────────────────────────────────
    def test_bad_reversibility_fails(self):
        errors = validate_spec(_minimal_spec(reversibility="maybe"))
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("reversibility" in e.lower() for e in errors))

    def test_valid_reversibility_two_way(self):
        errors = validate_spec(_minimal_spec(reversibility="two-way"))
        self.assertEqual(errors, [])

    def test_valid_reversibility_one_way(self):
        errors = validate_spec(_minimal_spec(reversibility="one-way"))
        self.assertEqual(errors, [])

    def test_missing_reversibility_fails(self):
        spec = _minimal_spec()
        del spec["reversibility"]
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)

    # ── options ─────────────────────────────────────────────────────────────
    def test_fewer_than_two_options_fails(self):
        spec = _minimal_spec()
        spec["options"] = [{"id": "opt-a", "label": "Only One"}]
        # Must also fix scorer to match
        spec["scorers"][0]["scores"] = {
            "opt-a": {
                "crit-1": {"value": 80},
                "crit-2": {"value": 40},
            }
        }
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("option" in e.lower() for e in errors))

    def test_zero_options_fails(self):
        spec = _minimal_spec()
        spec["options"] = []
        spec["scorers"][0]["scores"] = {}
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)

    # ── criteria ────────────────────────────────────────────────────────────
    def test_no_criteria_fails(self):
        spec = _minimal_spec()
        spec["criteria"] = []
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("criterion" in e.lower() or "criteria" in e.lower() for e in errors))

    def test_weight_above_100_fails(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = 150
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("weight" in e.lower() for e in errors))

    def test_weight_below_0_fails(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = -1
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("weight" in e.lower() for e in errors))

    def test_weight_at_boundary_0_ok(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = 0
        errors = validate_spec(spec)
        # weight=0 is valid (just a quality warning, not an error)
        self.assertEqual(errors, [])

    def test_weight_at_boundary_100_ok(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = 100
        errors = validate_spec(spec)
        self.assertEqual(errors, [])

    def test_non_numeric_weight_fails(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = "heavy"
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)

    def test_bad_direction_fails(self):
        spec = _minimal_spec()
        spec["criteria"][0]["direction"] = "sideways"
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("direction" in e.lower() for e in errors))

    def test_valid_direction_higher_is_better(self):
        errors = validate_spec(_minimal_spec())
        self.assertEqual(errors, [])

    # ── scorers ─────────────────────────────────────────────────────────────
    def test_no_scorers_fails(self):
        spec = _minimal_spec()
        spec["scorers"] = []
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("scorer" in e.lower() for e in errors))

    def test_score_above_100_fails(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["value"] = 110
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("score" in e.lower() for e in errors))

    def test_score_below_0_fails(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["value"] = -5
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("score" in e.lower() for e in errors))

    def test_score_at_boundaries_ok(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["value"] = 0
        spec["scorers"][0]["scores"]["opt-b"]["crit-1"]["value"] = 100
        errors = validate_spec(spec)
        self.assertEqual(errors, [])

    def test_confidence_above_1_fails(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["confidence"] = 1.5
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("confidence" in e.lower() for e in errors))

    def test_confidence_below_0_fails(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["confidence"] = -0.1
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("confidence" in e.lower() for e in errors))

    def test_confidence_at_boundaries_ok(self):
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["confidence"] = 0.0
        spec["scorers"][0]["scores"]["opt-b"]["crit-1"]["confidence"] = 1.0
        errors = validate_spec(spec)
        self.assertEqual(errors, [])

    def test_confidence_absent_defaults_to_valid(self):
        spec = _minimal_spec()
        # Remove confidence from one entry
        del spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["confidence"]
        errors = validate_spec(spec)
        self.assertEqual(errors, [])

    def test_missing_score_for_option_criterion_pair_fails(self):
        spec = _minimal_spec()
        # Remove a required score entry
        del spec["scorers"][0]["scores"]["opt-b"]["crit-2"]
        errors = validate_spec(spec)
        self.assertTrue(len(errors) > 0)

    def test_collects_all_errors(self):
        """validate_spec must collect all errors, not stop at first."""
        spec = {
            "goal": "",                    # error 1
            "reversibility": "bad",        # error 2
            "constraints": [],
            "options": [{"id": "x", "label": "X"}],  # error 3 (<2)
            "criteria": [],                # error 4 (<1)
            "scorers": [],                 # error 5 (<1)
            "methods": ["weighted-sum"],
            "tie_threshold": 5,
        }
        errors = validate_spec(spec)
        self.assertGreaterEqual(len(errors), 3)


class TestApplyConstraints(unittest.TestCase):

    def test_no_constraint_results_all_active(self):
        spec = _minimal_spec()
        vetoed, active = apply_constraints(spec)
        self.assertEqual(vetoed, [])
        self.assertIn("opt-a", active)
        self.assertIn("opt-b", active)

    def test_false_constraint_vetoes_option(self):
        spec = _minimal_spec()
        spec["options"][0]["constraint_results"] = {"budget": False}
        vetoed, active = apply_constraints(spec)
        self.assertIn("opt-a", vetoed)
        self.assertNotIn("opt-a", active)
        self.assertIn("opt-b", active)

    def test_all_true_constraints_active(self):
        spec = _minimal_spec()
        spec["options"][0]["constraint_results"] = {"budget": True, "timeline": True}
        vetoed, active = apply_constraints(spec)
        self.assertEqual(vetoed, [])
        self.assertIn("opt-a", active)

    def test_mixed_true_false_constraint_vetoes(self):
        """Even one False in constraint_results vetoes the option."""
        spec = _minimal_spec()
        spec["options"][0]["constraint_results"] = {"budget": True, "timeline": False}
        vetoed, active = apply_constraints(spec)
        self.assertIn("opt-a", vetoed)
        self.assertNotIn("opt-a", active)

    def test_both_vetoed(self):
        spec = _minimal_spec()
        spec["options"][0]["constraint_results"] = {"budget": False}
        spec["options"][1]["constraint_results"] = {"timeline": False}
        vetoed, active = apply_constraints(spec)
        self.assertIn("opt-a", vetoed)
        self.assertIn("opt-b", vetoed)
        self.assertEqual(active, [])


class TestCriteriaQualityWarnings(unittest.TestCase):

    def _spec_with_scores(self, weights, scores_by_opt_crit):
        """Build a spec with custom weights and scores for warning tests."""
        criteria = [
            {"id": f"crit-{i}", "label": f"Criterion {i}", "weight": w, "direction": "higher-is-better"}
            for i, w in enumerate(weights)
        ]
        options = [{"id": "opt-a", "label": "A"}, {"id": "opt-b", "label": "B"}]
        scorer_scores = {}
        for opt in ["opt-a", "opt-b"]:
            scorer_scores[opt] = {}
            for i, crit in enumerate(criteria):
                val = scores_by_opt_crit.get(f"{opt}_{crit['id']}", 50)
                scorer_scores[opt][crit["id"]] = {"value": val, "confidence": 1.0}
        spec = _minimal_spec()
        spec["criteria"] = criteria
        spec["scorers"][0]["scores"] = scorer_scores
        return spec

    def test_overweight_criterion_flagged(self):
        # weight 90 vs total 100 → normalized = 0.9 > 0.6 → overweight
        spec = self._spec_with_scores([90, 10], {})
        warnings = criteria_quality_warnings(spec)
        types = [w["type"] for w in warnings]
        self.assertIn("overweight", types)

    def test_zero_weight_flagged(self):
        spec = self._spec_with_scores([0, 50], {})
        warnings = criteria_quality_warnings(spec)
        types = [w["type"] for w in warnings]
        self.assertIn("zero-weight", types)

    def test_duplicate_label_flagged(self):
        spec = _minimal_spec()
        spec["criteria"][0]["label"] = "Cost"
        spec["criteria"][1]["label"] = "Cost"
        warnings = criteria_quality_warnings(spec)
        types = [w["type"] for w in warnings]
        self.assertIn("redundant", types)

    def test_non_discriminating_criterion_flagged(self):
        # Both options have same score on crit-1
        spec = _minimal_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["value"] = 70
        spec["scorers"][0]["scores"]["opt-b"]["crit-1"]["value"] = 70
        warnings = criteria_quality_warnings(spec)
        types = [w["type"] for w in warnings]
        self.assertIn("non-discriminating", types)

    def test_no_warnings_clean_spec(self):
        warnings = criteria_quality_warnings(_minimal_spec())
        self.assertEqual(warnings, [])

    def test_warning_has_required_keys(self):
        spec = _minimal_spec()
        spec["criteria"][0]["weight"] = 0
        warnings = criteria_quality_warnings(spec)
        self.assertTrue(len(warnings) > 0)
        for w in warnings:
            self.assertIn("type", w)
            self.assertIn("criterion", w)
            self.assertIn("message", w)


class TestAggregateScores(unittest.TestCase):

    def test_passthrough_single_scorer(self):
        spec = _minimal_spec()
        result = aggregate_scores(spec)
        # Should have entries for both options
        self.assertIn("opt-a", result)
        self.assertIn("opt-b", result)
        # Each criterion should be present
        self.assertIn("crit-1", result["opt-a"])
        self.assertIn("crit-2", result["opt-a"])

    def test_mean_equals_value_single_scorer(self):
        spec = _minimal_spec()
        result = aggregate_scores(spec)
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["mean"], 80.0)

    def test_std_dev_zero_single_scorer(self):
        spec = _minimal_spec()
        result = aggregate_scores(spec)
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["std_dev"], 0.0)

    def test_confidence_adjusted_value(self):
        spec = _minimal_spec()
        result = aggregate_scores(spec)
        # value=80, confidence=0.9 → 80 * 0.9 = 72.0
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["confidence_adjusted"], 72.0)

    def test_confidence_absent_defaults_to_1(self):
        spec = _minimal_spec()
        del spec["scorers"][0]["scores"]["opt-b"]["crit-1"]["confidence"]
        result = aggregate_scores(spec)
        # value=60, confidence defaults to 1.0 → 60 * 1.0 = 60.0
        self.assertAlmostEqual(result["opt-b"]["crit-1"]["confidence_adjusted"], 60.0)


if __name__ == "__main__":
    unittest.main()
