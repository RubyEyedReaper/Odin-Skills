"""Property-based tests for scoring methods (Sprint 2, stdlib only).

(a) Scaling all weights by a constant does not change weighted_sum ranking.
(b) A strictly-dominated option (lowest on every criterion) is never rank 1.
(c) Adding a zero-weight criterion does not change ranking.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.methods import weighted_sum


def _make_criteria(weights_and_directions):
    return [
        {"id": cid, "label": lbl, "weight": w, "direction": d}
        for cid, lbl, w, d in weights_and_directions
    ]


def _ranking_order(results):
    """Return list of option ids sorted by rank (ascending), score desc as tiebreak."""
    return [r["option"] for r in sorted(results, key=lambda x: (x["rank"], -x["score"]))]


class TestWeightScalingInvariance(unittest.TestCase):
    """(a) Multiplying all weights by a positive constant preserves ranking."""

    def _criteria(self, scale=1):
        return _make_criteria([
            ("c1", "Speed", 60 * scale, "higher-is-better"),
            ("c2", "Cost",  40 * scale, "lower-is-better"),
        ])

    def _matrix(self):
        return {
            "opt-a": {"c1": 80.0, "c2": 30.0},
            "opt-b": {"c1": 60.0, "c2": 50.0},
            "opt-c": {"c1": 90.0, "c2": 20.0},
        }

    def test_scale_by_2_preserves_ranking(self):
        opts = ["opt-a", "opt-b", "opt-c"]
        sm = self._matrix()
        rank1 = _ranking_order(weighted_sum(opts, self._criteria(scale=1), sm))
        rank2 = _ranking_order(weighted_sum(opts, self._criteria(scale=2), sm))
        self.assertEqual(rank1, rank2)

    def test_scale_by_10_preserves_ranking(self):
        opts = ["opt-a", "opt-b", "opt-c"]
        sm = self._matrix()
        rank1 = _ranking_order(weighted_sum(opts, self._criteria(scale=1), sm))
        rank10 = _ranking_order(weighted_sum(opts, self._criteria(scale=10), sm))
        self.assertEqual(rank1, rank10)

    def test_scale_by_fractional_preserves_ranking(self):
        opts = ["opt-a", "opt-b", "opt-c"]
        sm = self._matrix()
        rank1 = _ranking_order(weighted_sum(opts, self._criteria(scale=1), sm))
        rank_half = _ranking_order(weighted_sum(opts, self._criteria(scale=0.5), sm))
        self.assertEqual(rank1, rank_half)

    def test_single_option_always_rank_1_regardless_of_scale(self):
        for scale in [1, 3, 100]:
            criteria = self._criteria(scale=scale)
            sm = {"solo": {"c1": 70.0, "c2": 30.0}}
            results = weighted_sum(["solo"], criteria, sm)
            self.assertEqual(results[0]["rank"], 1)


class TestDominatedOptionNeverRank1(unittest.TestCase):
    """(b) A strictly-dominated option (lowest on every direction-adjusted criterion) is never rank 1."""

    def test_dominated_higher_is_better(self):
        criteria = _make_criteria([
            ("c1", "A", 50, "higher-is-better"),
            ("c2", "B", 50, "higher-is-better"),
        ])
        sm = {
            "strong": {"c1": 90.0, "c2": 90.0},
            "middle": {"c1": 60.0, "c2": 60.0},
            "dominated": {"c1": 10.0, "c2": 10.0},  # lowest on every criterion
        }
        results = weighted_sum(["strong", "middle", "dominated"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertNotEqual(by_opt["dominated"]["rank"], 1)

    def test_dominated_mixed_directions(self):
        """Dominated in direction-adjusted space (worst effective score on all)."""
        criteria = _make_criteria([
            ("c1", "Perf", 60, "higher-is-better"),
            ("c2", "Cost", 40, "lower-is-better"),
        ])
        # dominated: worst c1 (lowest higher-is-better) AND worst c2 (highest lower-is-better)
        sm = {
            "best":      {"c1": 90.0, "c2": 10.0},
            "middle":    {"c1": 60.0, "c2": 50.0},
            "dominated": {"c1": 10.0, "c2": 90.0},
        }
        results = weighted_sum(["best", "middle", "dominated"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertNotEqual(by_opt["dominated"]["rank"], 1)
        self.assertEqual(by_opt["best"]["rank"], 1)

    def test_dominated_option_last_rank(self):
        criteria = _make_criteria([("c1", "X", 100, "higher-is-better")])
        sm = {
            "first":     {"c1": 100.0},
            "second":    {"c1": 50.0},
            "dominated": {"c1": 0.0},
        }
        results = weighted_sum(["first", "second", "dominated"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        max_rank = max(r["rank"] for r in results)
        self.assertEqual(by_opt["dominated"]["rank"], max_rank)


class TestZeroWeightCriterionInvariance(unittest.TestCase):
    """(c) Adding a zero-weight criterion does not change the ranking."""

    def _base_criteria(self):
        return _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])

    def _matrix_without_zero(self):
        return {
            "opt-a": {"c1": 80.0, "c2": 30.0},
            "opt-b": {"c1": 60.0, "c2": 50.0},
            "opt-c": {"c1": 90.0, "c2": 20.0},
        }

    def test_zero_weight_criterion_does_not_change_order(self):
        opts = ["opt-a", "opt-b", "opt-c"]
        base_sm = self._matrix_without_zero()

        criteria_with_zero = self._base_criteria() + _make_criteria([
            ("c3", "Noise", 0, "higher-is-better"),
        ])
        sm_with_zero = {
            k: dict(v, c3=99.0)  # extreme score, but zero weight
            for k, v in base_sm.items()
        }

        rank_base = _ranking_order(weighted_sum(opts, self._base_criteria(), base_sm))
        rank_with_zero = _ranking_order(weighted_sum(opts, criteria_with_zero, sm_with_zero))
        self.assertEqual(rank_base, rank_with_zero)

    def test_zero_weight_extreme_values_ignored(self):
        """Even wildly different scores on a zero-weight criterion don't affect ranks."""
        criteria = _make_criteria([
            ("c1", "Main",  100, "higher-is-better"),
            ("c2", "Noise",   0, "higher-is-better"),
        ])
        sm = {
            "high-main":  {"c1": 90.0, "c2": 0.0},   # worst on noise
            "low-main":   {"c1": 10.0, "c2": 100.0},  # best on noise
        }
        results = weighted_sum(["high-main", "low-main"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["high-main"]["rank"], 1)
        self.assertEqual(by_opt["low-main"]["rank"], 2)

    def test_multiple_zero_weight_criteria_no_effect(self):
        criteria = _make_criteria([
            ("c1", "Speed", 50, "higher-is-better"),
            ("c2", "Cost",  50, "lower-is-better"),
            ("c3", "Foo",    0, "higher-is-better"),
            ("c4", "Bar",    0, "lower-is-better"),
        ])
        sm = {
            "a": {"c1": 80.0, "c2": 20.0, "c3": 0.0,   "c4": 100.0},
            "b": {"c1": 40.0, "c2": 80.0, "c3": 100.0,  "c4": 0.0},
        }
        results = weighted_sum(["a", "b"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["a"]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
