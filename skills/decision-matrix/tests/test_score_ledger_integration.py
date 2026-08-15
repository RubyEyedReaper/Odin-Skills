"""Tests for scripts/score.py Sprint 4 wiring: ledger recording + recall + revisit reminder.

Written before implementation (TDD RED phase). Library/default calls must NOT write any
files — only record=True (always with an explicit tmp decisions_dir in tests) writes.
"""
import json
import tempfile
import unittest
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score import run


def _spec(**overrides):
    spec = {
        "goal": "Pick the best caching layer for the API",
        "reversibility": "two-way",
        "constraints": [],
        "options": [
            {"id": "redis", "label": "Redis"},
            {"id": "memcached", "label": "Memcached"},
        ],
        "criteria": [
            {"id": "features", "label": "Feature Set", "weight": 60, "direction": "higher-is-better"},
            {"id": "ops", "label": "Ops Simplicity", "weight": 40, "direction": "higher-is-better"},
        ],
        "scorers": [{
            "id": "s1", "label": "Team",
            "scores": {
                "redis": {"features": {"value": 90}, "ops": {"value": 70}},
                "memcached": {"features": {"value": 50}, "ops": {"value": 85}},
            },
        }],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }
    spec.update(overrides)
    return spec


class TestRunDefaultNoRecord(unittest.TestCase):
    """Default behavior (record=False) must never write files."""

    def test_default_record_false_no_decisions_dir_writes(self):
        result, exit_code = run(_spec())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["prior_decisions"], [])
        self.assertIsNone(result["dec_record_path"])

    def test_explicit_record_false_with_decisions_dir_still_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=False)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["prior_decisions"], [])
            self.assertIsNone(result["dec_record_path"])
            self.assertFalse(decisions_dir.exists())


class TestRunWithRecord(unittest.TestCase):

    def test_record_true_writes_dec_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)
            self.assertIsNotNone(result["dec_record_path"])
            dec_path = Path(result["dec_record_path"])
            self.assertTrue(dec_path.exists())
            self.assertTrue(dec_path.name.startswith("DEC-0001-"))

    def test_record_true_writes_readme_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            run(_spec(), decisions_dir=decisions_dir, record=True)
            readme = decisions_dir / "README.md"
            self.assertTrue(readme.exists())

    def test_record_true_sets_promote_to_adr_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, _ = run(_spec(reversibility="one-way"), decisions_dir=decisions_dir, record=True)
            self.assertTrue(result["promote_to_adr_hint"])

    def test_record_true_second_run_increments_dec_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result1, _ = run(_spec(), decisions_dir=decisions_dir, record=True)
            result2, _ = run(_spec(goal="Pick a different cache layer"), decisions_dir=decisions_dir, record=True)
            self.assertNotEqual(
                Path(result1["dec_record_path"]).name,
                Path(result2["dec_record_path"]).name,
            )
            self.assertTrue(Path(result2["dec_record_path"]).name.startswith("DEC-0002-"))

    def test_record_true_populates_prior_decisions_on_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            run(_spec(), decisions_dir=decisions_dir, record=True)
            result2, _ = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertGreater(len(result2["prior_decisions"]), 0)

    def test_vetoed_all_options_with_record_true_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            spec = _spec()
            spec["options"][0]["constraint_results"] = {"x": False}
            spec["options"][1]["constraint_results"] = {"x": False}
            result, exit_code = run(spec, decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)
            # No winner to record; result should still have the keys, even if no DEC was written.
            self.assertIn("prior_decisions", result)
            self.assertIn("dec_record_path", result)


class TestRevisitReminder(unittest.TestCase):

    def test_revisit_after_days_two_way_sets_reminder(self):
        result, _ = run(_spec(revisit_after_days=30))
        self.assertIn("revisit_reminder", result)
        self.assertIn("due_date", result["revisit_reminder"])
        self.assertIn("message", result["revisit_reminder"])

    def test_no_revisit_after_days_no_reminder_key_or_none(self):
        result, _ = run(_spec())
        # Either absent or explicitly None — must not silently populate a reminder.
        self.assertIn(result.get("revisit_reminder"), [None, {}])

    def test_revisit_after_days_one_way_no_reminder(self):
        result, _ = run(_spec(revisit_after_days=30, reversibility="one-way"))
        self.assertIn(result.get("revisit_reminder"), [None, {}])

    def test_due_date_is_n_days_from_today(self):
        import datetime
        result, _ = run(_spec(revisit_after_days=7))
        due_date = result["revisit_reminder"]["due_date"]
        expected = (datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=7))
        self.assertEqual(due_date, expected.isoformat())


class TestRunSignatureIsKeywordOnly(unittest.TestCase):
    """decisions_dir / record must be keyword-only per spec: run(spec, *, decisions_dir=None, record=False)."""

    def test_cannot_pass_decisions_dir_positionally(self):
        with self.assertRaises(TypeError):
            run(_spec(), None, True)


if __name__ == "__main__":
    unittest.main()
