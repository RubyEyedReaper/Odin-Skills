"""Tests for scripts/ledger.py (Sprint 4, stdlib only) — written before implementation."""
import re
import tempfile
import unittest
import shutil
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ledger import (
    next_dec_number,
    slugify,
    write_dec_record,
    update_readme_index,
    promote_to_adr_hint,
)


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


def _result(**overrides):
    result = {
        "schema_version": "1",
        "vetoed_options": [],
        "active_options": ["redis", "memcached"],
        "aggregated_scores": {
            "redis": {
                "features": {"mean": 90.0, "std_dev": 0.0, "confidence_adjusted": 90.0},
                "ops": {"mean": 70.0, "std_dev": 0.0, "confidence_adjusted": 70.0},
            },
            "memcached": {
                "features": {"mean": 50.0, "std_dev": 0.0, "confidence_adjusted": 50.0},
                "ops": {"mean": 85.0, "std_dev": 0.0, "confidence_adjusted": 85.0},
            },
        },
        "criteria_quality": {"warnings": []},
        "method_results": {
            "weighted-sum": {
                "ranking": [
                    {"option": "redis", "score": 82.0, "rank": 1},
                    {"option": "memcached", "score": 64.0, "rank": 2},
                ]
            }
        },
        "ties": {"near_tie_pairs": []},
        "disagreement_report": {"methods_agree": True, "winner_by_method": {}, "disagreement_pairs": []},
        "sensitivity": {
            "winner_analyzed": "redis",
            "break_even": {},
            "tornado": [],
            "fragile": False,
            "fragile_reason": "",
        },
        "multi_scorer_analysis": {"conflicts": [], "variance": {"outliers": []}},
        "recommendation": {
            "winner": "redis",
            "winner_label": "Redis",
            "rationale": "Redis ranks first by weighted-sum across 2 criteria",
            "confidence": "high",
            "caveats": [],
        },
    }
    result.update(overrides)
    return result


class TestNextDecNumber(unittest.TestCase):

    def test_empty_dir_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            self.assertEqual(next_dec_number(decisions_dir), 1)

    def test_missing_dir_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "does-not-exist"
            self.assertEqual(next_dec_number(decisions_dir), 1)

    def test_dir_with_dec_0003_returns_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "DEC-0003-pick-a-cache.md").write_text("# stub")
            self.assertEqual(next_dec_number(decisions_dir), 4)

    def test_returns_max_plus_1_with_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "DEC-0001-first.md").write_text("# stub")
            (decisions_dir / "DEC-0007-seventh.md").write_text("# stub")
            self.assertEqual(next_dec_number(decisions_dir), 8)

    def test_ignores_non_dec_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "README.md").write_text("# index")
            (decisions_dir / "DEC-0002-second.md").write_text("# stub")
            self.assertEqual(next_dec_number(decisions_dir), 3)


class TestSlugify(unittest.TestCase):

    def test_spaces_become_hyphens(self):
        self.assertEqual(slugify("Pick a database"), "pick-a-database")

    def test_lowercased(self):
        self.assertEqual(slugify("PICK A DATABASE"), "pick-a-database")

    def test_special_chars_stripped(self):
        self.assertEqual(slugify("Build vs. Buy? (Auth!)"), "build-vs-buy-auth")

    def test_collapses_repeated_hyphens(self):
        self.assertEqual(slugify("a   b---c"), "a-b-c")

    def test_strips_leading_trailing_hyphens(self):
        self.assertEqual(slugify("-leading and trailing-"), "leading-and-trailing")

    def test_max_40_chars(self):
        long_title = "a" * 100
        result = slugify(long_title)
        self.assertLessEqual(len(result), 40)

    def test_max_40_chars_no_trailing_hyphen(self):
        title = "this is a very long decision title that exceeds forty characters easily"
        result = slugify(title)
        self.assertLessEqual(len(result), 40)
        self.assertFalse(result.endswith("-"))

    def test_empty_string_returns_empty(self):
        self.assertEqual(slugify(""), "")

    def test_unicode_stripped(self):
        result = slugify("Café — caching choice")
        self.assertNotIn("—", result)
        self.assertNotIn("é", result.replace("e", ""))  # no raw accented chars leak through


class TestWriteDecRecord(unittest.TestCase):

    def test_creates_file_with_correct_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            spec = _spec()
            result = _result()
            path, _ = write_dec_record("DEC-0001", spec, result, decisions_dir)
            self.assertTrue(path.exists())
            self.assertTrue(path.name.startswith("DEC-0001-"))
            self.assertTrue(path.name.endswith(".md"))

    def test_creates_decisions_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "nested" / "decisions"
            write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            self.assertTrue(decisions_dir.exists())

    def test_frontmatter_has_dec_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("dec_id: DEC-0001", content)

    def test_frontmatter_has_date_in_iso_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertRegex(content, r"date: \d{4}-\d{2}-\d{2}")

    def test_frontmatter_has_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("Pick the best caching layer for the API", content)

    def test_frontmatter_has_reversibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("reversibility: two-way", content)

    def test_frontmatter_has_winner_and_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("winner: redis", content)
            self.assertIn("confidence: high", content)

    def test_frontmatter_has_fragile(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("fragile: false", content)

    def test_body_has_recommendation_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("## Recommendation", content)
            self.assertIn("Redis ranks first by weighted-sum across 2 criteria", content)

    def test_body_has_scored_matrix_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("|", content)  # markdown table present
            self.assertIn("Redis", content)
            self.assertIn("Memcached", content)
            self.assertIn("82.0", content)

    def test_body_has_sensitivity_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            content = path.read_text()
            self.assertIn("## Sensitivity", content)

    def test_returns_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            path, _ = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            self.assertIsInstance(path, Path)


class TestUpdateReadmeIndex(unittest.TestCase):

    def test_creates_readme_with_header_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            dec_path = decisions_dir / "DEC-0001-pick-a-cache.md"
            dec_path.write_text("# stub")
            update_readme_index("DEC-0001", "Pick a cache", dec_path, decisions_dir, winner="redis")
            readme = decisions_dir / "README.md"
            self.assertTrue(readme.exists())
            content = readme.read_text()
            self.assertIn("DEC-0001", content)
            self.assertIn("Pick a cache", content)

    def test_upserts_without_duplicating_existing_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            dec_path = decisions_dir / "DEC-0001-pick-a-cache.md"
            dec_path.write_text("# stub")
            update_readme_index("DEC-0001", "Pick a cache", dec_path, decisions_dir, winner="redis")
            update_readme_index("DEC-0001", "Pick a cache", dec_path, decisions_dir, winner="redis")
            readme = decisions_dir / "README.md"
            content = readme.read_text()
            row_count = sum(1 for line in content.splitlines() if line.startswith("| DEC-0001 |"))
            self.assertEqual(row_count, 1)

    def test_appends_new_row_for_new_dec_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            p1 = decisions_dir / "DEC-0001-first.md"
            p1.write_text("# stub")
            p2 = decisions_dir / "DEC-0002-second.md"
            p2.write_text("# stub")
            update_readme_index("DEC-0001", "First Decision", p1, decisions_dir, winner="redis")
            update_readme_index("DEC-0002", "Second Decision", p2, decisions_dir, winner="memcached")
            content = (decisions_dir / "README.md").read_text()
            self.assertIn("DEC-0001", content)
            self.assertIn("DEC-0002", content)

    def test_new_row_lands_inside_the_table_not_after_trailing_prose(self):
        """The shipped README ends with an HTML comment; a row appended past it
        would sit outside the table and stop rendering as a row."""
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "README.md").write_text(
                "# Decision Ledger\n"
                "\n"
                "| DEC | Title | Winner | Record |\n"
                "|---|---|---|---|\n"
                "\n"
                "<!-- New DEC rows are appended above by ledger.py -->\n"
            )
            dec_path = decisions_dir / "DEC-0001-pick.md"
            dec_path.write_text("# stub")
            update_readme_index("DEC-0001", "Pick", dec_path, decisions_dir, winner="redis")
            lines = (decisions_dir / "README.md").read_text().splitlines()
            row_index = next(i for i, l in enumerate(lines) if l.startswith("| DEC-0001 |"))
            comment_index = next(i for i, l in enumerate(lines) if l.startswith("<!--"))
            self.assertLess(row_index, comment_index)
            self.assertTrue(lines[row_index - 1].startswith("|"))

    def test_creates_decisions_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "nested" / "decisions"
            dec_path = decisions_dir / "DEC-0001-pick.md"
            update_readme_index("DEC-0001", "Pick", dec_path, decisions_dir)
            self.assertTrue((decisions_dir / "README.md").exists())


class TestPromoteToAdrHint(unittest.TestCase):

    def test_true_when_one_way_and_high_confidence(self):
        result = _result()
        result["reversibility"] = "one-way"
        self.assertTrue(promote_to_adr_hint(result))

    def test_false_when_two_way(self):
        result = _result()
        result["reversibility"] = "two-way"
        self.assertFalse(promote_to_adr_hint(result))

    def test_false_when_one_way_but_low_confidence(self):
        result = _result()
        result["reversibility"] = "one-way"
        result["recommendation"]["confidence"] = "low"
        self.assertFalse(promote_to_adr_hint(result))

    def test_true_when_one_way_and_medium_confidence(self):
        result = _result()
        result["reversibility"] = "one-way"
        result["recommendation"]["confidence"] = "medium"
        self.assertTrue(promote_to_adr_hint(result))


class TestWriteDecRecordReturnsResolvedId(unittest.TestCase):
    """The caller must learn which id was actually written.

    write_dec_record bumps the number on collision (a concurrent session claiming the
    slot between the read and the write). A caller that keeps using the id it *asked*
    for labels the ledger row with one id and links a file carrying another — and, since
    the index upserts on the id prefix, overwrites the row belonging to the real holder.
    """

    def test_returns_bumped_id_when_the_number_is_already_taken(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp)
            (decisions_dir / "DEC-0001-claimed-by-another-session.md").write_text(
                "---\ndec_id: DEC-0001\n---\n", encoding="utf-8"
            )

            path, resolved_id = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)

            self.assertEqual(resolved_id, "DEC-0002")
            self.assertTrue(path.name.startswith("DEC-0002-"), path.name)

    def test_returned_id_matches_the_records_own_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp)
            (decisions_dir / "DEC-0001-claimed.md").write_text("x", encoding="utf-8")

            path, resolved_id = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)

            self.assertIn(f"dec_id: {resolved_id}\n", path.read_text(encoding="utf-8"))

    def test_index_row_built_from_the_returned_id_does_not_clobber_the_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp)
            holder = decisions_dir / "DEC-0001-claimed.md"
            holder.write_text("x", encoding="utf-8")
            update_readme_index("DEC-0001", "Claimed first", holder, decisions_dir, winner="first")

            path, resolved_id = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            update_readme_index(resolved_id, "Second decision", path, decisions_dir, winner="redis")

            readme = (decisions_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("| DEC-0001 | Claimed first |", readme)
            self.assertIn("| DEC-0002 | Second decision |", readme)


if __name__ == "__main__":
    unittest.main()
