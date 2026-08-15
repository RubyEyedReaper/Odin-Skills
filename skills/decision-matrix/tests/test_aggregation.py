"""Tests for scripts/aggregation.py (Sprint 3, stdlib only) — written before implementation."""
import unittest
import sys
import os
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.aggregation import (
    aggregate_scores,
    conflict_detect,
    scorer_variance_summary,
)


def _entry(value, confidence=1.0):
    return {"value": value, "confidence": confidence}


def _multi_scorer_spec():
    """3 scorers, known mean/std_dev per option×criterion cell.

    opt-a / crit-1 values: 80, 90, 70 → mean 80, pstdev = sqrt(((0)^2+(10)^2+(-10)^2)/3)
    opt-a / crit-2 values: 50, 50, 50 → mean 50, std_dev 0
    opt-b / crit-1 values: 60, 60, 60 → mean 60, std_dev 0
    opt-b / crit-2 values: 20, 80, 50 → mean 50, high variance (conflict candidate)
    """
    return {
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
                "label": "Reviewer 1",
                "scores": {
                    "opt-a": {"crit-1": _entry(80, 1.0), "crit-2": _entry(50, 1.0)},
                    "opt-b": {"crit-1": _entry(60, 1.0), "crit-2": _entry(20, 1.0)},
                },
            },
            {
                "id": "scorer-2",
                "label": "Reviewer 2",
                "scores": {
                    "opt-a": {"crit-1": _entry(90, 1.0), "crit-2": _entry(50, 1.0)},
                    "opt-b": {"crit-1": _entry(60, 1.0), "crit-2": _entry(80, 1.0)},
                },
            },
            {
                "id": "scorer-3",
                "label": "Reviewer 3",
                "scores": {
                    "opt-a": {"crit-1": _entry(70, 1.0), "crit-2": _entry(50, 1.0)},
                    "opt-b": {"crit-1": _entry(60, 1.0), "crit-2": _entry(50, 1.0)},
                },
            },
        ],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }


def _single_scorer_spec():
    return {
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
                    "opt-a": {"crit-1": _entry(80, 0.9), "crit-2": _entry(40, 0.8)},
                    "opt-b": {"crit-1": _entry(60, 0.7), "crit-2": _entry(70, 0.9)},
                },
            },
        ],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }


class TestAggregateScoresSingleScorer(unittest.TestCase):
    """Single scorer must remain pass-through (std_dev 0.0)."""

    def test_passthrough_single_scorer(self):
        result = aggregate_scores(_single_scorer_spec())
        self.assertIn("opt-a", result)
        self.assertIn("crit-1", result["opt-a"])

    def test_mean_equals_value_single_scorer(self):
        result = aggregate_scores(_single_scorer_spec())
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["mean"], 80.0)

    def test_std_dev_zero_single_scorer(self):
        result = aggregate_scores(_single_scorer_spec())
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["std_dev"], 0.0)

    def test_confidence_adjusted_single_scorer(self):
        result = aggregate_scores(_single_scorer_spec())
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["confidence_adjusted"], 72.0)

    def test_empty_scorers_returns_empty_dict(self):
        spec = _single_scorer_spec()
        spec["scorers"] = []
        result = aggregate_scores(spec)
        self.assertEqual(result, {})


class TestAggregateScoresMultiScorer(unittest.TestCase):

    def test_mean_across_scorers(self):
        result = aggregate_scores(_multi_scorer_spec())
        # opt-a/crit-1: 80, 90, 70 → mean 80
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["mean"], 80.0)

    def test_std_dev_across_scorers(self):
        result = aggregate_scores(_multi_scorer_spec())
        expected_std = statistics.pstdev([80, 90, 70])
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["std_dev"], expected_std)

    def test_std_dev_zero_when_all_scorers_agree(self):
        result = aggregate_scores(_multi_scorer_spec())
        # opt-a/crit-2: 50, 50, 50 → std_dev 0
        self.assertAlmostEqual(result["opt-a"]["crit-2"]["std_dev"], 0.0)

    def test_confidence_adjusted_is_mean_of_value_times_confidence(self):
        result = aggregate_scores(_multi_scorer_spec())
        # opt-b/crit-1: all confidence 1.0, values 60,60,60 → mean(60*1)=60
        self.assertAlmostEqual(result["opt-b"]["crit-1"]["confidence_adjusted"], 60.0)

    def test_confidence_adjusted_with_varying_confidence(self):
        spec = _multi_scorer_spec()
        spec["scorers"][0]["scores"]["opt-a"]["crit-1"] = _entry(80, 0.5)
        spec["scorers"][1]["scores"]["opt-a"]["crit-1"] = _entry(90, 1.0)
        spec["scorers"][2]["scores"]["opt-a"]["crit-1"] = _entry(70, 1.0)
        result = aggregate_scores(spec)
        expected = statistics.mean([80 * 0.5, 90 * 1.0, 70 * 1.0])
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["confidence_adjusted"], expected)

    def test_missing_confidence_defaults_to_1(self):
        spec = _multi_scorer_spec()
        del spec["scorers"][0]["scores"]["opt-a"]["crit-1"]["confidence"]
        result = aggregate_scores(spec)
        # confidence defaults to 1.0 for that scorer; values unaffected
        expected = statistics.mean([80 * 1.0, 90 * 1.0, 70 * 1.0])
        self.assertAlmostEqual(result["opt-a"]["crit-1"]["confidence_adjusted"], expected)

    def test_all_option_criterion_pairs_present(self):
        spec = _multi_scorer_spec()
        result = aggregate_scores(spec)
        for opt in spec["options"]:
            for crit in spec["criteria"]:
                self.assertIn(crit["id"], result[opt["id"]])

    def test_each_cell_has_required_keys(self):
        result = aggregate_scores(_multi_scorer_spec())
        for opt_id, crits in result.items():
            for cid, agg in crits.items():
                self.assertIn("mean", agg)
                self.assertIn("std_dev", agg)
                self.assertIn("confidence_adjusted", agg)


class TestConflictDetect(unittest.TestCase):

    def test_flags_high_variance_cell(self):
        # opt-b/crit-2: 20, 80, 50 → pstdev ~24.5; lower threshold to detect it clearly.
        conflicts = conflict_detect(_multi_scorer_spec(), conflict_threshold_std=20.0)
        cells = [(c["option"], c["criterion"]) for c in conflicts]
        self.assertIn(("opt-b", "crit-2"), cells)

    def test_does_not_flag_low_variance_cells(self):
        conflicts = conflict_detect(_multi_scorer_spec(), conflict_threshold_std=25.0)
        cells = [(c["option"], c["criterion"]) for c in conflicts]
        self.assertNotIn(("opt-a", "crit-2"), cells)
        self.assertNotIn(("opt-b", "crit-1"), cells)

    def test_conflict_entry_has_required_keys(self):
        conflicts = conflict_detect(_multi_scorer_spec(), conflict_threshold_std=5.0)
        self.assertGreater(len(conflicts), 0)
        for c in conflicts:
            self.assertIn("option", c)
            self.assertIn("criterion", c)
            self.assertIn("std_dev", c)
            self.assertIn("scorer_values", c)

    def test_scorer_values_keyed_by_scorer_id(self):
        conflicts = conflict_detect(_multi_scorer_spec(), conflict_threshold_std=5.0)
        flagged = [c for c in conflicts if c["option"] == "opt-a" and c["criterion"] == "crit-1"]
        self.assertEqual(len(flagged), 1)
        sv = flagged[0]["scorer_values"]
        self.assertEqual(sv, {"scorer-1": 80, "scorer-2": 90, "scorer-3": 70})

    def test_no_conflicts_when_threshold_very_high(self):
        conflicts = conflict_detect(_multi_scorer_spec(), conflict_threshold_std=1000.0)
        self.assertEqual(conflicts, [])

    def test_single_scorer_never_conflicts(self):
        conflicts = conflict_detect(_single_scorer_spec(), conflict_threshold_std=0.0)
        self.assertEqual(conflicts, [])

    def test_empty_scorers_returns_empty_list(self):
        spec = _single_scorer_spec()
        spec["scorers"] = []
        conflicts = conflict_detect(spec)
        self.assertEqual(conflicts, [])


class TestScorerVarianceSummary(unittest.TestCase):

    def test_returns_mean_abs_dev_per_scorer(self):
        summary = scorer_variance_summary(_multi_scorer_spec())
        self.assertIn("scorer-1", summary)
        self.assertIn("scorer-2", summary)
        self.assertIn("scorer-3", summary)

    def test_identifies_outlier_scorer(self):
        # Build a spec where scorer-2 consistently scores far from the group mean
        # on every cell (pegged at 100), while scorer-1/scorer-3 stay close together.
        spec = _multi_scorer_spec()
        spec["scorers"][1]["scores"]["opt-a"]["crit-1"] = _entry(100, 1.0)
        spec["scorers"][1]["scores"]["opt-a"]["crit-2"] = _entry(100, 1.0)
        spec["scorers"][1]["scores"]["opt-b"]["crit-1"] = _entry(100, 1.0)
        spec["scorers"][1]["scores"]["opt-b"]["crit-2"] = _entry(100, 1.0)
        summary = scorer_variance_summary(spec)
        self.assertIn("outliers", summary)
        self.assertIn("scorer-2", summary["outliers"])

    def test_no_outliers_when_scorers_agree(self):
        spec = _single_scorer_spec()
        spec["scorers"].append({
            "id": "scorer-2",
            "label": "Team 2",
            "scores": spec["scorers"][0]["scores"],
        })
        summary = scorer_variance_summary(spec)
        self.assertEqual(summary["outliers"], [])

    def test_single_scorer_has_zero_deviation(self):
        summary = scorer_variance_summary(_single_scorer_spec())
        self.assertAlmostEqual(summary["scorer-1"], 0.0)
        self.assertEqual(summary["outliers"], [])

    def test_empty_scorers_returns_empty_summary(self):
        spec = _single_scorer_spec()
        spec["scorers"] = []
        summary = scorer_variance_summary(spec)
        self.assertEqual(summary, {"outliers": []})


if __name__ == "__main__":
    unittest.main()
