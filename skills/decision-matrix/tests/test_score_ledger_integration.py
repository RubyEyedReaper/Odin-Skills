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

from scripts.score import run, resolve_decisions_dir, DEFAULT_DECISIONS_DIR


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


class TestDecisionsDirResolution(unittest.TestCase):
    """A decision about a project belongs in that project's ledger, not the harness one.

    The engine is mandated to run with its CWD inside the skill directory, so the working
    directory carries no information about who owns the decision. The spec declares it.
    Precedence: explicit argument > spec's `decisions_dir` > harness default.
    """

    def test_spec_key_beats_the_harness_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "projects" / "demo" / "docs" / "decisions"
            resolved = resolve_decisions_dir(_spec(decisions_dir=str(declared)), None)
            self.assertEqual(resolved, declared.resolve())

    def test_explicit_argument_beats_the_spec_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "from-spec"
            override = Path(tmp) / "from-flag"
            resolved = resolve_decisions_dir(_spec(decisions_dir=str(declared)), override)
            self.assertEqual(resolved, override)

    def test_neither_falls_back_to_the_harness_ledger(self):
        resolved = resolve_decisions_dir(_spec(), None)
        self.assertEqual(resolved, DEFAULT_DECISIONS_DIR)

    def test_relative_spec_path_resolves_against_the_repo_not_the_skill_dir(self):
        # The mandated CWD is the skill directory; resolving a relative path against it
        # would bury a project's ledger inside the skill.
        resolved = resolve_decisions_dir(
            _spec(decisions_dir="projects/decision-matrix-web/docs/decisions"), None
        )
        self.assertTrue(
            str(resolved).endswith("/projects/decision-matrix-web/docs/decisions"), resolved
        )
        self.assertNotIn("/.claude/skills/", str(resolved))

    def test_a_run_records_where_the_spec_declares(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "docs" / "decisions"
            result, exit_code = run(_spec(decisions_dir=str(declared)), record=True)
            self.assertEqual(exit_code, 0)
            self.assertTrue(Path(result["dec_record_path"]).is_relative_to(declared))


class TestRecordedIdSurvivesACollision(unittest.TestCase):
    """End-to-end reproduction of the id/index-row desync.

    Simulates a concurrent session claiming the next number between this run's read and
    its write. The recorded file, the run's reported path, and the ledger row must all
    name the same DEC.
    """

    def test_ledger_row_names_the_file_that_was_written(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir(parents=True)
            (decisions_dir / "DEC-0001-claimed-by-another-session.md").write_text(
                "---\ndec_id: DEC-0001\n---\n", encoding="utf-8"
            )

            # The race: this run read the number *before* the other session's file landed,
            # so it walks in holding a number that is no longer free.
            with mock.patch("scripts.score.next_dec_number", return_value=1):
                result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)

            written = Path(result["dec_record_path"]).name
            written_id = written[: len("DEC-0000")]
            readme = (decisions_dir / "README.md").read_text(encoding="utf-8")

            self.assertEqual(written_id, "DEC-0002")
            self.assertIn(f"| {written_id} |", readme)
            self.assertIn(written, readme)
            # The row for the id this run did NOT write must not have been invented.
            self.assertNotIn("| DEC-0001 |", readme)


class TestRunSignatureIsKeywordOnly(unittest.TestCase):
    """decisions_dir / record must be keyword-only per spec: run(spec, *, decisions_dir=None, record=False)."""

    def test_cannot_pass_decisions_dir_positionally(self):
        with self.assertRaises(TypeError):
            run(_spec(), None, True)


if __name__ == "__main__":
    unittest.main()
