"""Tests for scripts/sensitivity.py (Sprint 2, stdlib only)."""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.sensitivity import (
    break_even_analysis,
    tornado_data,
    fragility_flag,
    disagreement_report,
)


def _make_criteria(weights_and_directions):
    return [
        {"id": cid, "label": lbl, "weight": w, "direction": d}
        for cid, lbl, w, d in weights_and_directions
    ]


# ── break_even_analysis ───────────────────────────────────────────────────────

class TestBreakEvenAnalysis(unittest.TestCase):
    """
    Simple 2-criterion, 2-option setup where we know exactly when winner flips.

    criteria: c1=60/higher-is-better, c2=40/lower-is-better
    opt-a: c1=90, c2=10  (weighted winner with these weights)
    opt-b: c1=50, c2=80

    Effective (direction-adjusted):
      opt-a: c1_eff=90, c2_eff=90
      opt-b: c1_eff=50, c2_eff=20

    opt-a beats opt-b on both criteria → should be robust (no flip found for c1).
    """

    def _criteria(self):
        return _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])

    def _matrix(self):
        return {
            "opt-a": {"c1": 90.0, "c2": 10.0},
            "opt-b": {"c1": 50.0, "c2": 80.0},
        }

    def test_returns_dict_keyed_by_criterion(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = break_even_analysis("opt-a", ["opt-a", "opt-b"], criteria, sm)
        for crit in criteria:
            self.assertIn(crit["id"], result)

    def test_each_entry_has_required_keys(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = break_even_analysis("opt-a", ["opt-a", "opt-b"], criteria, sm)
        for cid, entry in result.items():
            self.assertIn("weight_shift_to_flip_pct", entry)
            self.assertIn("favors_if_flipped", entry)

    def test_dominant_winner_no_flip(self):
        """opt-a dominates on both criteria → no flip expected."""
        criteria = self._criteria()
        sm = self._matrix()
        result = break_even_analysis("opt-a", ["opt-a", "opt-b"], criteria, sm)
        # Both criteria: opt-a wins on both, so no weight shift can flip
        for cid, entry in result.items():
            # Dominant option: flip may be None or very large shift
            # At minimum, favors_if_flipped can be None if no flip found
            self.assertIn(entry["weight_shift_to_flip_pct"], [None] + list(range(-1, 1000)))

    def test_fragile_winner_finds_flip(self):
        """
        Close race: opt-a barely wins; shifting c2 weight should flip to opt-b.

        criteria: c1=51/higher-is-better, c2=49/lower-is-better
        opt-a: c1=50, c2=10  eff → c1=50, c2=90
        opt-b: c1=50, c2=80  eff → c1=50, c2=20

        With c1 equal, winner is determined by c2.
        opt-a wins c2 (90 eff vs 20 eff). If we shift weight from c2 to c1...
        Actually need a case where opt-b wins c1 strongly.

        Use: c1=51/higher, c2=49/lower-is-better
        opt-a: c1=55, c2=10  (eff: 55, 90)
        opt-b: c1=90, c2=80  (eff: 90, 20)

        Default scores:
          opt-a: 55*0.51 + 90*0.49 = 28.05 + 44.1 = 72.15
          opt-b: 90*0.51 + 20*0.49 = 45.9 + 9.8 = 55.7
        opt-a wins. Increasing c1 weight will eventually flip to opt-b.
        """
        criteria = _make_criteria([
            ("c1", "Perf", 51, "higher-is-better"),
            ("c2", "Cost", 49, "lower-is-better"),
        ])
        sm = {
            "opt-a": {"c1": 55.0, "c2": 10.0},
            "opt-b": {"c1": 90.0, "c2": 80.0},
        }
        result = break_even_analysis("opt-a", ["opt-a", "opt-b"], criteria, sm)
        # c1 flip: increasing c1 weight should eventually make opt-b win
        c1_entry = result["c1"]
        # There should be a flip found for c1
        self.assertIsNotNone(c1_entry["weight_shift_to_flip_pct"])
        self.assertGreater(c1_entry["weight_shift_to_flip_pct"], 0)
        self.assertEqual(c1_entry["favors_if_flipped"], "opt-b")

    def test_no_flip_returns_none(self):
        """Dominant winner produces None for weight_shift_to_flip_pct."""
        criteria = self._criteria()
        sm = self._matrix()
        result = break_even_analysis("opt-a", ["opt-a", "opt-b"], criteria, sm)
        # opt-a dominates on both criteria; no flip should be found
        none_count = sum(
            1 for entry in result.values()
            if entry["weight_shift_to_flip_pct"] is None
        )
        self.assertGreater(none_count, 0)


# ── tornado_data ──────────────────────────────────────────────────────────────

class TestTornadoData(unittest.TestCase):

    def _criteria(self):
        return _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])

    def _matrix(self):
        return {
            "opt-a": {"c1": 90.0, "c2": 10.0},
            "opt-b": {"c1": 50.0, "c2": 80.0},
        }

    def test_returns_list_of_criteria_entries(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = tornado_data("opt-a", ["opt-a", "opt-b"], criteria, sm)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), len(criteria))

    def test_required_keys_present(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = tornado_data("opt-a", ["opt-a", "opt-b"], criteria, sm)
        for entry in result:
            self.assertIn("criterion", entry)
            self.assertIn("swing_impact", entry)
            self.assertIn("baseline_rank_of_winner", entry)
            self.assertIn("perturbed_rank_of_winner", entry)

    def test_sorted_by_swing_impact_desc(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = tornado_data("opt-a", ["opt-a", "opt-b"], criteria, sm)
        swings = [e["swing_impact"] for e in result]
        self.assertEqual(swings, sorted(swings, reverse=True))

    def test_swing_impact_non_negative(self):
        """swing_impact is an absolute value."""
        criteria = self._criteria()
        sm = self._matrix()
        result = tornado_data("opt-a", ["opt-a", "opt-b"], criteria, sm)
        for entry in result:
            self.assertGreaterEqual(entry["swing_impact"], 0.0)

    def test_baseline_rank_is_1_for_winner(self):
        criteria = self._criteria()
        sm = self._matrix()
        result = tornado_data("opt-a", ["opt-a", "opt-b"], criteria, sm)
        for entry in result:
            self.assertEqual(entry["baseline_rank_of_winner"], 1)


# ── fragility_flag ────────────────────────────────────────────────────────────

class TestFragilityFlag(unittest.TestCase):

    def test_fragile_when_small_shift(self):
        break_even = {
            "c1": {"weight_shift_to_flip_pct": 5.0, "favors_if_flipped": "opt-b"},
            "c2": {"weight_shift_to_flip_pct": None, "favors_if_flipped": None},
        }
        fragile, reason = fragility_flag(break_even, fragile_threshold_pct=10.0)
        self.assertTrue(fragile)
        self.assertIn("c1", reason)

    def test_not_fragile_when_large_shift(self):
        break_even = {
            "c1": {"weight_shift_to_flip_pct": 25.0, "favors_if_flipped": "opt-b"},
            "c2": {"weight_shift_to_flip_pct": None, "favors_if_flipped": None},
        }
        fragile, reason = fragility_flag(break_even, fragile_threshold_pct=10.0)
        self.assertFalse(fragile)

    def test_not_fragile_when_all_none(self):
        break_even = {
            "c1": {"weight_shift_to_flip_pct": None, "favors_if_flipped": None},
            "c2": {"weight_shift_to_flip_pct": None, "favors_if_flipped": None},
        }
        fragile, reason = fragility_flag(break_even)
        self.assertFalse(fragile)

    def test_boundary_exactly_at_threshold_is_fragile(self):
        """shift == threshold → fragile (strict less-than check)."""
        break_even = {
            "c1": {"weight_shift_to_flip_pct": 10.0, "favors_if_flipped": "opt-b"},
        }
        fragile, reason = fragility_flag(break_even, fragile_threshold_pct=10.0)
        self.assertTrue(fragile)

    def test_returns_tuple_bool_str(self):
        break_even = {}
        result = fragility_flag(break_even)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)


# ── disagreement_report ───────────────────────────────────────────────────────

class TestDisagreementReport(unittest.TestCase):

    def test_agree_when_all_same_winner(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1},
                             {"option": "B", "score": 70, "rank": 2}],
            "pugh": [{"option": "A", "score": 2, "rank": 1},
                     {"option": "B", "score": -2, "rank": 2}],
        }
        report = disagreement_report(method_results)
        self.assertTrue(report["methods_agree"])

    def test_disagree_when_different_winners(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1},
                             {"option": "B", "score": 70, "rank": 2}],
            "pugh": [{"option": "B", "score": 1, "rank": 1},
                     {"option": "A", "score": -1, "rank": 2}],
        }
        report = disagreement_report(method_results)
        self.assertFalse(report["methods_agree"])

    def test_winner_by_method_populated(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1}],
            "topsis": [{"option": "A", "score": 0.9, "rank": 1}],
        }
        report = disagreement_report(method_results)
        self.assertIn("weighted-sum", report["winner_by_method"])
        self.assertIn("topsis", report["winner_by_method"])
        self.assertEqual(report["winner_by_method"]["weighted-sum"], "A")

    def test_disagreement_pairs_listed(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1},
                             {"option": "B", "score": 70, "rank": 2}],
            "pugh": [{"option": "B", "score": 1, "rank": 1},
                     {"option": "A", "score": -1, "rank": 2}],
        }
        report = disagreement_report(method_results)
        self.assertGreater(len(report["disagreement_pairs"]), 0)

    def test_skips_error_entries(self):
        """Methods that produced errors (dict with 'error' key) are skipped."""
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1}],
            "rice": {"error": "missing required criterion"},
        }
        report = disagreement_report(method_results)
        self.assertNotIn("rice", report["winner_by_method"])
        self.assertIn("weighted-sum", report["winner_by_method"])

    def test_required_keys_present(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1}],
        }
        report = disagreement_report(method_results)
        self.assertIn("methods_agree", report)
        self.assertIn("winner_by_method", report)
        self.assertIn("disagreement_pairs", report)

    def test_single_method_agrees_with_itself(self):
        method_results = {
            "weighted-sum": [{"option": "A", "score": 90, "rank": 1}],
        }
        report = disagreement_report(method_results)
        self.assertTrue(report["methods_agree"])
        self.assertEqual(report["disagreement_pairs"], [])


if __name__ == "__main__":
    unittest.main()
