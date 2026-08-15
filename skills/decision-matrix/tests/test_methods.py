"""Tests for scripts/methods.py — Sprint 1 (original) + Sprint 2 additions."""
import math
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.methods import (
    normalize_weights,
    weighted_sum,
    WeightNormalizationError,
    # Sprint 2
    pugh_matrix,
    topsis,
    ahp_weights,
    ahp_consistency_ratio,
    rice_score,
    wsjf_score,
    ice_score,
    kano_classify,
    MethodError,
)


def _make_criteria(weights_and_directions):
    """Build criteria list from [(id, label, weight, direction), ...]."""
    return [
        {"id": cid, "label": lbl, "weight": w, "direction": d}
        for cid, lbl, w, d in weights_and_directions
    ]


# ── Sprint 1 tests (unchanged) ────────────────────────────────────────────────

class TestNormalizeWeights(unittest.TestCase):

    def test_sums_to_one(self):
        criteria = _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])
        normed = normalize_weights(criteria)
        self.assertAlmostEqual(sum(normed.values()), 1.0)

    def test_proportions_correct(self):
        criteria = _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])
        normed = normalize_weights(criteria)
        self.assertAlmostEqual(normed["c1"], 0.6)
        self.assertAlmostEqual(normed["c2"], 0.4)

    def test_equal_weights_proportional(self):
        criteria = _make_criteria([
            ("c1", "A", 25, "higher-is-better"),
            ("c2", "B", 25, "higher-is-better"),
            ("c3", "C", 25, "higher-is-better"),
            ("c4", "D", 25, "higher-is-better"),
        ])
        normed = normalize_weights(criteria)
        for cid in ["c1", "c2", "c3", "c4"]:
            self.assertAlmostEqual(normed[cid], 0.25)

    def test_single_criterion_is_1(self):
        criteria = _make_criteria([("c1", "Only", 70, "higher-is-better")])
        normed = normalize_weights(criteria)
        self.assertAlmostEqual(normed["c1"], 1.0)

    def test_all_zero_weights_raises(self):
        criteria = _make_criteria([
            ("c1", "A", 0, "higher-is-better"),
            ("c2", "B", 0, "higher-is-better"),
        ])
        with self.assertRaises(WeightNormalizationError):
            normalize_weights(criteria)

    def test_returns_dict_keyed_by_criterion_id(self):
        criteria = _make_criteria([
            ("alpha", "Alpha", 30, "higher-is-better"),
            ("beta",  "Beta",  70, "higher-is-better"),
        ])
        normed = normalize_weights(criteria)
        self.assertIn("alpha", normed)
        self.assertIn("beta", normed)

    def test_single_zero_among_others_excluded_from_proportion(self):
        criteria = _make_criteria([
            ("c1", "A", 0,  "higher-is-better"),
            ("c2", "B", 50, "higher-is-better"),
            ("c3", "C", 50, "higher-is-better"),
        ])
        normed = normalize_weights(criteria)
        self.assertAlmostEqual(normed["c1"], 0.0)
        self.assertAlmostEqual(normed["c2"], 0.5)
        self.assertAlmostEqual(normed["c3"], 0.5)
        self.assertAlmostEqual(sum(normed.values()), 1.0)


class TestWeightedSum(unittest.TestCase):
    """
    Hand-computed expected values:

    criteria:
        c1: weight=60, direction=higher-is-better   → normalized=0.6
        c2: weight=40, direction=lower-is-better    → normalized=0.4

    opt-a: c1=80, c2=30  → lower-is-better invert: 100-30=70
        score = 80*0.6 + 70*0.4 = 48 + 28 = 76.0

    opt-b: c1=60, c2=50  → invert: 100-50=50
        score = 60*0.6 + 50*0.4 = 36 + 20 = 56.0

    opt-c: c1=90, c2=20  → invert: 100-20=80
        score = 90*0.6 + 80*0.4 = 54 + 32 = 86.0

    Ranking: opt-c(86) > opt-a(76) > opt-b(56)
    """

    def _criteria(self):
        return _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])

    def _score_matrix(self):
        return {
            "opt-a": {"c1": 80.0, "c2": 30.0},
            "opt-b": {"c1": 60.0, "c2": 50.0},
            "opt-c": {"c1": 90.0, "c2": 20.0},
        }

    def test_winner_is_correct(self):
        results = weighted_sum(
            active_options=["opt-a", "opt-b", "opt-c"],
            criteria=self._criteria(),
            score_matrix=self._score_matrix(),
        )
        by_option = {r["option"]: r for r in results}
        self.assertEqual(by_option["opt-c"]["rank"], 1)

    def test_scores_are_correct(self):
        results = weighted_sum(
            active_options=["opt-a", "opt-b", "opt-c"],
            criteria=self._criteria(),
            score_matrix=self._score_matrix(),
        )
        by_option = {r["option"]: r for r in results}
        self.assertAlmostEqual(by_option["opt-c"]["score"], 86.0)
        self.assertAlmostEqual(by_option["opt-a"]["score"], 76.0)
        self.assertAlmostEqual(by_option["opt-b"]["score"], 56.0)

    def test_ranks_are_descending(self):
        results = weighted_sum(
            active_options=["opt-a", "opt-b", "opt-c"],
            criteria=self._criteria(),
            score_matrix=self._score_matrix(),
        )
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_result_sorted_score_desc(self):
        results = weighted_sum(
            active_options=["opt-a", "opt-b", "opt-c"],
            criteria=self._criteria(),
            score_matrix=self._score_matrix(),
        )
        self.assertEqual(results[0]["option"], "opt-c")
        self.assertEqual(results[1]["option"], "opt-a")
        self.assertEqual(results[2]["option"], "opt-b")

    def test_ranks_assigned_correctly(self):
        results = weighted_sum(
            active_options=["opt-a", "opt-b", "opt-c"],
            criteria=self._criteria(),
            score_matrix=self._score_matrix(),
        )
        by_option = {r["option"]: r for r in results}
        self.assertEqual(by_option["opt-c"]["rank"], 1)
        self.assertEqual(by_option["opt-a"]["rank"], 2)
        self.assertEqual(by_option["opt-b"]["rank"], 3)

    def test_single_option_rank_1(self):
        criteria = _make_criteria([("c1", "Speed", 100, "higher-is-better")])
        matrix = {"only": {"c1": 75.0}}
        results = weighted_sum(["only"], criteria, matrix)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["option"], "only")
        self.assertEqual(results[0]["rank"], 1)
        self.assertAlmostEqual(results[0]["score"], 75.0)

    def test_all_equal_scores_all_rank_1(self):
        criteria = _make_criteria([("c1", "Speed", 100, "higher-is-better")])
        matrix = {
            "opt-a": {"c1": 50.0},
            "opt-b": {"c1": 50.0},
            "opt-c": {"c1": 50.0},
        }
        results = weighted_sum(["opt-a", "opt-b", "opt-c"], criteria, matrix)
        for r in results:
            self.assertEqual(r["rank"], 1, f"Expected rank 1 for {r['option']}, got {r['rank']}")

    def test_lower_is_better_inversion(self):
        """Lower cost should produce a higher effective score."""
        criteria = _make_criteria([("cost", "Cost", 100, "lower-is-better")])
        matrix = {
            "cheap": {"cost": 20.0},   # inverted → 80
            "pricey": {"cost": 80.0},  # inverted → 20
        }
        results = weighted_sum(["cheap", "pricey"], criteria, matrix)
        by_option = {r["option"]: r for r in results}
        self.assertEqual(by_option["cheap"]["rank"], 1)
        self.assertGreater(by_option["cheap"]["score"], by_option["pricey"]["score"])
        self.assertAlmostEqual(by_option["cheap"]["score"], 80.0)
        self.assertAlmostEqual(by_option["pricey"]["score"], 20.0)

    def test_result_has_required_keys(self):
        criteria = _make_criteria([("c1", "A", 100, "higher-is-better")])
        matrix = {"x": {"c1": 50.0}, "y": {"c1": 40.0}}
        results = weighted_sum(["x", "y"], criteria, matrix)
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)

    def test_partial_tie_same_rank(self):
        """Two options with same score share the same rank."""
        criteria = _make_criteria([("c1", "A", 100, "higher-is-better")])
        matrix = {
            "opt-a": {"c1": 70.0},
            "opt-b": {"c1": 70.0},
            "opt-c": {"c1": 40.0},
        }
        results = weighted_sum(["opt-a", "opt-b", "opt-c"], criteria, matrix)
        by_option = {r["option"]: r for r in results}
        self.assertEqual(by_option["opt-a"]["rank"], by_option["opt-b"]["rank"])
        self.assertGreater(by_option["opt-c"]["rank"], by_option["opt-a"]["rank"])

    def test_higher_is_better_no_inversion(self):
        """higher-is-better scores should pass through unchanged."""
        criteria = _make_criteria([("perf", "Perf", 100, "higher-is-better")])
        matrix = {
            "fast": {"perf": 90.0},
            "slow": {"perf": 30.0},
        }
        results = weighted_sum(["fast", "slow"], criteria, matrix)
        by_option = {r["option"]: r for r in results}
        self.assertAlmostEqual(by_option["fast"]["score"], 90.0)
        self.assertAlmostEqual(by_option["slow"]["score"], 30.0)
        self.assertEqual(by_option["fast"]["rank"], 1)


# ── Sprint 2: pugh_matrix ──────────────────────────────────────────────────────

class TestPughMatrix(unittest.TestCase):
    """
    Baseline defaults to the weighted-sum rank-1 option when baseline_id is None.

    Criteria: c1=60/higher-is-better, c2=40/lower-is-better
    Score matrix (raw confidence-adjusted values):
        opt-a: c1=80, c2=30
        opt-b: c1=60, c2=50
        opt-c: c1=90, c2=20

    weighted_sum winner = opt-c (score 86).

    Pugh comparison vs opt-c baseline:
      opt-c (baseline): all 0  → sum = 0
      opt-a vs opt-c:
        c1: 80 vs 90 (higher-is-better) → lower → -1
        c2: 30 vs 20 (lower-is-better)  → higher raw → WORSE → -1  (lower raw is better)
        sum = -2
      opt-b vs opt-c:
        c1: 60 vs 90 → -1
        c2: 50 vs 20 → worse → -1
        sum = -2

    Ranking: opt-c(0) > opt-a(-2) tied with opt-b(-2)
    """

    def _setup(self):
        criteria = _make_criteria([
            ("c1", "Speed", 60, "higher-is-better"),
            ("c2", "Cost",  40, "lower-is-better"),
        ])
        score_matrix = {
            "opt-a": {"c1": 80.0, "c2": 30.0},
            "opt-b": {"c1": 60.0, "c2": 50.0},
            "opt-c": {"c1": 90.0, "c2": 20.0},
        }
        return criteria, score_matrix

    def test_baseline_scores_zero(self):
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["opt-c"]["score"], 0)

    def test_baseline_rank_1(self):
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["opt-c"]["rank"], 1)

    def test_dominated_option_negative_score(self):
        """opt-a and opt-b are both worse than opt-c on all criteria."""
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        by_opt = {r["option"]: r for r in results}
        self.assertLess(by_opt["opt-a"]["score"], 0)
        self.assertLess(by_opt["opt-b"]["score"], 0)

    def test_default_baseline_is_weighted_sum_winner(self):
        """When baseline_id is None, baseline = weighted_sum rank-1."""
        criteria, sm = self._setup()
        # opt-c is the weighted-sum winner
        results_explicit = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        results_default = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm)
        by_e = {r["option"]: r["score"] for r in results_explicit}
        by_d = {r["option"]: r["score"] for r in results_default}
        for opt in ["opt-a", "opt-b", "opt-c"]:
            self.assertEqual(by_e[opt], by_d[opt])

    def test_result_sorted_desc(self):
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_required_keys_present(self):
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)

    def test_better_option_positive_score(self):
        """An option better than baseline on all criteria should score positive."""
        criteria = _make_criteria([("c1", "Perf", 100, "higher-is-better")])
        score_matrix = {
            "strong": {"c1": 90.0},
            "baseline": {"c1": 50.0},
            "weak": {"c1": 20.0},
        }
        results = pugh_matrix(["strong", "baseline", "weak"], criteria, score_matrix, baseline_id="baseline")
        by_opt = {r["option"]: r for r in results}
        self.assertGreater(by_opt["strong"]["score"], 0)
        self.assertLess(by_opt["weak"]["score"], 0)

    def test_ties_share_rank(self):
        """Options with equal Pugh sums share the same rank."""
        criteria, sm = self._setup()
        results = pugh_matrix(["opt-a", "opt-b", "opt-c"], criteria, sm, baseline_id="opt-c")
        by_opt = {r["option"]: r for r in results}
        # opt-a and opt-b both score -2
        self.assertEqual(by_opt["opt-a"]["rank"], by_opt["opt-b"]["rank"])


# ── Sprint 2: topsis ──────────────────────────────────────────────────────────

class TestTopsis(unittest.TestCase):
    """
    Small 2-criterion, 3-option example with known winner.

    criteria: c1=50/higher-is-better, c2=50/lower-is-better
    scores:
        A: c1=80, c2=20  (best on both after direction-adjustment)
        B: c1=50, c2=50
        C: c1=20, c2=80  (worst on both)

    A should be rank 1 (closeness → 1.0), C rank 3 (closeness → 0.0), B rank 2.
    """

    def _setup(self):
        criteria = _make_criteria([
            ("c1", "Perf", 50, "higher-is-better"),
            ("c2", "Cost", 50, "lower-is-better"),
        ])
        score_matrix = {
            "A": {"c1": 80.0, "c2": 20.0},
            "B": {"c1": 50.0, "c2": 50.0},
            "C": {"c1": 20.0, "c2": 80.0},
        }
        return criteria, score_matrix

    def test_winner_rank_1(self):
        criteria, sm = self._setup()
        results = topsis(["A", "B", "C"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["A"]["rank"], 1)

    def test_worst_rank_last(self):
        criteria, sm = self._setup()
        results = topsis(["A", "B", "C"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["C"]["rank"], 3)

    def test_closeness_in_0_1(self):
        criteria, sm = self._setup()
        results = topsis(["A", "B", "C"], criteria, sm)
        for r in results:
            self.assertGreaterEqual(r["score"], 0.0)
            self.assertLessEqual(r["score"], 1.0)

    def test_sorted_desc(self):
        criteria, sm = self._setup()
        results = topsis(["A", "B", "C"], criteria, sm)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_required_keys(self):
        criteria, sm = self._setup()
        results = topsis(["A", "B", "C"], criteria, sm)
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)

    def test_lower_is_better_honored(self):
        """Option with lower raw score on lower-is-better criterion should rank higher."""
        criteria = _make_criteria([("cost", "Cost", 100, "lower-is-better")])
        sm = {"cheap": {"cost": 10.0}, "expensive": {"cost": 90.0}}
        results = topsis(["cheap", "expensive"], criteria, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertEqual(by_opt["cheap"]["rank"], 1)

    def test_all_identical_scores_handled(self):
        """All options identical → closeness is undefined; no crash."""
        criteria = _make_criteria([("c1", "X", 100, "higher-is-better")])
        sm = {"a": {"c1": 50.0}, "b": {"c1": 50.0}}
        # Should not raise; all closeness 0 or 0.5 depending on implementation
        results = topsis(["a", "b"], criteria, sm)
        self.assertEqual(len(results), 2)


# ── Sprint 2: ahp_weights ─────────────────────────────────────────────────────

class TestAhpWeights(unittest.TestCase):
    """
    3x3 perfectly consistent pairwise matrix:
        [[1, 3, 5],
         [1/3, 1, 3],
         [1/5, 1/3, 1]]
    Geometric means: (1*3*5)^(1/3), (1/3*1*3)^(1/3), (1/5*1/3*1)^(1/3)
                   ≈ 2.466, 1.000, 0.405
    Normalized:    ≈ 0.637, 0.258, 0.105  (sums to 1)
    """

    def _pairwise(self):
        return [
            [1,     3,   5  ],
            [1/3,   1,   3  ],
            [1/5, 1/3,   1  ],
        ]

    def test_weights_sum_to_one(self):
        pw = self._pairwise()
        ids = ["c1", "c2", "c3"]
        weights = ahp_weights(pw, ids)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

    def test_returns_dict_with_all_ids(self):
        pw = self._pairwise()
        ids = ["c1", "c2", "c3"]
        weights = ahp_weights(pw, ids)
        for cid in ids:
            self.assertIn(cid, weights)

    def test_higher_weight_for_higher_priority(self):
        """c1 is 3× and 5× more important than c2/c3 → highest weight."""
        pw = self._pairwise()
        ids = ["c1", "c2", "c3"]
        weights = ahp_weights(pw, ids)
        self.assertGreater(weights["c1"], weights["c2"])
        self.assertGreater(weights["c2"], weights["c3"])

    def test_identity_matrix_equal_weights(self):
        """Identity pairwise → all criteria equally important."""
        pw = [[1, 1], [1, 1]]
        ids = ["a", "b"]
        weights = ahp_weights(pw, ids)
        self.assertAlmostEqual(weights["a"], 0.5, places=6)
        self.assertAlmostEqual(weights["b"], 0.5, places=6)

    def test_all_weights_positive(self):
        pw = self._pairwise()
        ids = ["c1", "c2", "c3"]
        weights = ahp_weights(pw, ids)
        for w in weights.values():
            self.assertGreater(w, 0)


class TestAhpConsistencyRatio(unittest.TestCase):

    def test_consistent_matrix_cr_low(self):
        """A perfectly consistent matrix should have CR ≈ 0."""
        pw = [
            [1,    3,   9  ],
            [1/3,  1,   3  ],
            [1/9, 1/3,  1  ],
        ]
        cr = ahp_consistency_ratio(pw)
        self.assertLess(cr, 0.1)

    def test_inconsistent_matrix_cr_high(self):
        """A badly inconsistent matrix should have CR > 0.1."""
        # Inconsistent: A > B, B > C, but C > A
        pw = [
            [1, 9, 1/9],
            [1/9, 1, 9],
            [9, 1/9, 1],
        ]
        cr = ahp_consistency_ratio(pw)
        self.assertGreater(cr, 0.1)

    def test_returns_float(self):
        pw = [[1, 2], [0.5, 1]]
        cr = ahp_consistency_ratio(pw)
        self.assertIsInstance(cr, float)


# ── Sprint 2: rice_score ──────────────────────────────────────────────────────

class TestRiceScore(unittest.TestCase):
    """
    RICE = reach * impact * confidence / effort

    opt-a: 1000 * 3 * 0.8 / 2 = 1200
    opt-b: 500  * 5 * 0.9 / 4 = 562.5
    """

    def _setup(self):
        active = ["opt-a", "opt-b"]
        score_matrix = {
            "opt-a": {"reach": 1000, "impact": 3, "confidence": 0.8, "effort": 2},
            "opt-b": {"reach": 500,  "impact": 5, "confidence": 0.9, "effort": 4},
        }
        return active, score_matrix

    def test_rice_scores_correct(self):
        active, sm = self._setup()
        results = rice_score(active, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertAlmostEqual(by_opt["opt-a"]["score"], 1200.0)
        self.assertAlmostEqual(by_opt["opt-b"]["score"], 562.5)

    def test_winner_rank_1(self):
        active, sm = self._setup()
        results = rice_score(active, sm)
        self.assertEqual(results[0]["option"], "opt-a")
        self.assertEqual(results[0]["rank"], 1)

    def test_sorted_desc(self):
        active, sm = self._setup()
        results = rice_score(active, sm)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_zero_effort_raises_method_error(self):
        active = ["opt-a"]
        sm = {"opt-a": {"reach": 100, "impact": 3, "confidence": 0.8, "effort": 0}}
        with self.assertRaises(MethodError):
            rice_score(active, sm)

    def test_missing_required_criterion_raises_method_error(self):
        active = ["opt-a"]
        sm = {"opt-a": {"reach": 100, "impact": 3, "confidence": 0.8}}  # missing effort
        with self.assertRaises(MethodError):
            rice_score(active, sm)

    def test_required_keys_present(self):
        active, sm = self._setup()
        results = rice_score(active, sm)
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)


# ── Sprint 2: wsjf_score ──────────────────────────────────────────────────────

class TestWsjfScore(unittest.TestCase):
    """
    WSJF = (user_business_value + time_criticality + risk_reduction) / job_size

    opt-a: (8 + 5 + 3) / 4 = 4.0
    opt-b: (5 + 8 + 5) / 8 = 2.25
    """

    def _setup(self):
        active = ["opt-a", "opt-b"]
        score_matrix = {
            "opt-a": {
                "user_business_value": 8,
                "time_criticality": 5,
                "risk_reduction": 3,
                "job_size": 4,
            },
            "opt-b": {
                "user_business_value": 5,
                "time_criticality": 8,
                "risk_reduction": 5,
                "job_size": 8,
            },
        }
        return active, score_matrix

    def test_wsjf_scores_correct(self):
        active, sm = self._setup()
        results = wsjf_score(active, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertAlmostEqual(by_opt["opt-a"]["score"], 4.0)
        self.assertAlmostEqual(by_opt["opt-b"]["score"], 2.25)

    def test_winner_rank_1(self):
        active, sm = self._setup()
        results = wsjf_score(active, sm)
        self.assertEqual(results[0]["option"], "opt-a")

    def test_zero_job_size_raises_method_error(self):
        active = ["opt-a"]
        sm = {
            "opt-a": {
                "user_business_value": 8,
                "time_criticality": 5,
                "risk_reduction": 3,
                "job_size": 0,
            }
        }
        with self.assertRaises(MethodError):
            wsjf_score(active, sm)

    def test_missing_field_raises_method_error(self):
        active = ["opt-a"]
        sm = {
            "opt-a": {
                "user_business_value": 8,
                "time_criticality": 5,
                "risk_reduction": 3,
                # missing job_size
            }
        }
        with self.assertRaises(MethodError):
            wsjf_score(active, sm)


# ── Sprint 2: ice_score ───────────────────────────────────────────────────────

class TestIceScore(unittest.TestCase):
    """
    ICE = impact * confidence * ease

    opt-a: 9 * 8 * 7 = 504
    opt-b: 5 * 9 * 3 = 135
    """

    def _setup(self):
        active = ["opt-a", "opt-b"]
        score_matrix = {
            "opt-a": {"impact": 9, "confidence": 8, "ease": 7},
            "opt-b": {"impact": 5, "confidence": 9, "ease": 3},
        }
        return active, score_matrix

    def test_ice_scores_correct(self):
        active, sm = self._setup()
        results = ice_score(active, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertAlmostEqual(by_opt["opt-a"]["score"], 504.0)
        self.assertAlmostEqual(by_opt["opt-b"]["score"], 135.0)

    def test_winner_rank_1(self):
        active, sm = self._setup()
        results = ice_score(active, sm)
        self.assertEqual(results[0]["option"], "opt-a")

    def test_missing_field_raises_method_error(self):
        active = ["opt-a"]
        sm = {"opt-a": {"impact": 9, "confidence": 8}}  # missing ease
        with self.assertRaises(MethodError):
            ice_score(active, sm)

    def test_required_keys_present(self):
        active, sm = self._setup()
        results = ice_score(active, sm)
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)


# ── Sprint 2: kano_classify ───────────────────────────────────────────────────

class TestKanoClassify(unittest.TestCase):
    """
    Criteria tagged by id suffix pattern:
      must_be      → must-have; must pass threshold (>=50) to stay in
      performance  → score on criterion contributes to rank
      delighter    → premium tier; highest delighter value wins

    Ranking: delighter value desc, then performance value desc.
    """

    def _setup(self):
        active = ["feat-a", "feat-b", "feat-c"]
        # must_be criterion: must score >=50
        # performance criterion: higher better
        # delighter criterion: higher better (tiebreaker first)
        score_matrix = {
            "feat-a": {"must_be_1": 80, "performance_1": 70, "delighter_1": 90},
            "feat-b": {"must_be_1": 60, "performance_1": 85, "delighter_1": 40},
            "feat-c": {"must_be_1": 30, "performance_1": 90, "delighter_1": 50},  # fails must_be
        }
        return active, score_matrix

    def test_must_be_failure_ranks_last(self):
        active, sm = self._setup()
        results = kano_classify(active, sm)
        by_opt = {r["option"]: r for r in results}
        # feat-c fails must_be threshold, should be last
        max_rank = max(r["rank"] for r in results)
        self.assertEqual(by_opt["feat-c"]["rank"], max_rank)

    def test_required_keys_present(self):
        active, sm = self._setup()
        results = kano_classify(active, sm)
        for r in results:
            self.assertIn("option", r)
            self.assertIn("score", r)
            self.assertIn("rank", r)

    def test_delighter_beats_performance(self):
        """feat-a has higher delighter → ranked above feat-b (higher performance)."""
        active, sm = self._setup()
        results = kano_classify(active, sm)
        by_opt = {r["option"]: r for r in results}
        self.assertLess(by_opt["feat-a"]["rank"], by_opt["feat-b"]["rank"])

    def test_sorted_desc(self):
        active, sm = self._setup()
        results = kano_classify(active, sm)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_no_criteria_raises_method_error(self):
        """If no kano-tagged criteria found, raise MethodError."""
        active = ["x", "y"]
        sm = {
            "x": {"generic_1": 70},
            "y": {"generic_1": 40},
        }
        with self.assertRaises(MethodError):
            kano_classify(active, sm)


if __name__ == "__main__":
    unittest.main()
