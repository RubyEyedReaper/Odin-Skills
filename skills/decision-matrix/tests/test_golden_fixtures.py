"""Golden-fixture regression tests (Sprint 2, stdlib only).

For each fixture, run score.run(spec) and assert that:
  - recommendation.winner matches the expected file
  - the top-3 weighted-sum ranking order matches the expected file

Expected files are in evals/fixtures/<name>.expected.json and were produced
by running scripts/score.py against the corresponding input fixture.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score import run

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIXTURES_DIR = os.path.join(_SKILL_ROOT, "evals", "fixtures")

# All 7 fixture stems
_FIXTURES = [
    "architecture-pattern",
    "build-vs-buy-auth",
    "choose-a-database",
    "feature-prioritization",
    "frontend-framework",
    "hiring-candidate",
    "state-management-lib",
]


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _ws_top3_order(result: dict) -> list:
    """Return top-3 option ids from weighted-sum ranking (by rank asc, score desc)."""
    ws = result.get("method_results", {}).get("weighted-sum", {})
    ranking = ws.get("ranking", [])
    # Already sorted desc; take first 3
    return [r["option"] for r in ranking[:3]]


class TestGoldenFixtures(unittest.TestCase):
    pass


def _make_test(fixture_name: str):
    """Factory: returns a test method for one fixture."""

    def test_fn(self):
        spec_path = os.path.join(_FIXTURES_DIR, f"{fixture_name}.json")
        expected_path = os.path.join(_FIXTURES_DIR, f"{fixture_name}.expected.json")

        self.assertTrue(
            os.path.exists(spec_path),
            f"Spec file missing: {spec_path}",
        )
        self.assertTrue(
            os.path.exists(expected_path),
            f"Expected output file missing: {expected_path}",
        )

        spec = _load_json(spec_path)
        expected = _load_json(expected_path)

        result, exit_code = run(spec)

        # Must succeed
        self.assertEqual(
            exit_code, 0,
            f"{fixture_name}: run() returned exit_code {exit_code}, result={result}",
        )

        # Winner must match
        self.assertEqual(
            result["recommendation"]["winner"],
            expected["recommendation"]["winner"],
            f"{fixture_name}: winner mismatch",
        )

        # Top-3 weighted-sum order must match
        actual_top3 = _ws_top3_order(result)
        expected_top3 = _ws_top3_order(expected)
        # Only compare the length that both have
        compare_len = min(len(actual_top3), len(expected_top3))
        self.assertEqual(
            actual_top3[:compare_len],
            expected_top3[:compare_len],
            f"{fixture_name}: top-{compare_len} weighted-sum order mismatch "
            f"actual={actual_top3} expected={expected_top3}",
        )

        # disagreement_report must be present and have required keys
        disagree = result.get("disagreement_report", {})
        self.assertIn("methods_agree", disagree, f"{fixture_name}: missing methods_agree")
        self.assertIn("winner_by_method", disagree, f"{fixture_name}: missing winner_by_method")
        self.assertIn("disagreement_pairs", disagree, f"{fixture_name}: missing disagreement_pairs")

        # sensitivity must be present and non-empty (active options exist)
        sensitivity = result.get("sensitivity", {})
        self.assertTrue(
            len(sensitivity) > 0,
            f"{fixture_name}: sensitivity block is empty",
        )
        self.assertIn("break_even", sensitivity, f"{fixture_name}: missing break_even")
        self.assertIn("tornado", sensitivity, f"{fixture_name}: missing tornado")

    test_fn.__name__ = f"test_{fixture_name.replace('-', '_')}"
    return test_fn


# Dynamically attach one test method per fixture
for _name in _FIXTURES:
    _test_method = _make_test(_name)
    setattr(TestGoldenFixtures, _test_method.__name__, _test_method)


if __name__ == "__main__":
    unittest.main()
