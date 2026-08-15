"""Tests for scripts/recall.py (Sprint 4, stdlib only) — written before implementation."""
import tempfile
import unittest
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.recall import extract_keywords, search_prior_decisions


_STUB_DEC_CACHE = """---
dec_id: DEC-0001
date: 2026-01-15
goal: Pick a caching layer for the API
reversibility: two-way
winner: redis
confidence: high
fragile: false
---

## Recommendation

Redis ranks first by weighted-sum across 2 criteria.

| Option | features | ops | Score |
|---|---|---|---|
| Redis | 90.0 | 70.0 | 82.0 |
| Memcached | 50.0 | 85.0 | 64.0 |
"""

_STUB_DEC_DATABASE = """---
dec_id: DEC-0002
date: 2026-01-20
goal: Choose a database for a tight-budget SaaS
reversibility: one-way
winner: postgres
confidence: medium
fragile: false
---

## Recommendation

PostgreSQL ranks first by weighted-sum across 3 criteria.
"""

_STUB_DEC_UNRELATED = """---
dec_id: DEC-0003
date: 2026-02-01
goal: Decide on the office snack vendor
reversibility: two-way
winner: vendor-a
confidence: low
fragile: true
---

## Recommendation

Vendor A ranks first by weighted-sum across 2 criteria.
"""


class TestExtractKeywords(unittest.TestCase):

    def test_lowercases_tokens(self):
        kws = extract_keywords("Pick A Database")
        self.assertIn("pick", kws)
        self.assertIn("database", kws)

    def test_removes_stopwords(self):
        kws = extract_keywords("pick the best database for the API")
        self.assertNotIn("the", kws)
        self.assertNotIn("for", kws)

    def test_unique_tokens_only(self):
        kws = extract_keywords("database database database choice")
        self.assertEqual(kws.count("database"), 1)

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(extract_keywords(""), [])

    def test_strips_punctuation(self):
        kws = extract_keywords("Build vs. Buy? (Auth!)")
        self.assertIn("build", kws)
        self.assertIn("buy", kws)
        self.assertIn("auth", kws)
        self.assertNotIn("vs.", kws)


class TestSearchPriorDecisions(unittest.TestCase):

    def _make_decisions_dir(self, tmp):
        decisions_dir = Path(tmp) / "decisions"
        decisions_dir.mkdir()
        (decisions_dir / "DEC-0001-pick-a-cache.md").write_text(_STUB_DEC_CACHE)
        (decisions_dir / "DEC-0002-choose-a-database.md").write_text(_STUB_DEC_DATABASE)
        (decisions_dir / "DEC-0003-office-snacks.md").write_text(_STUB_DEC_UNRELATED)
        return decisions_dir

    def test_keyword_match_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = self._make_decisions_dir(tmp)
            results = search_prior_decisions(
                "Choose a database for a SaaS",
                ["postgres", "mysql"],
                decisions_dir,
            )
            dec_ids = [r["dec_id"] for r in results]
            self.assertIn("DEC-0002", dec_ids)

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = self._make_decisions_dir(tmp)
            results = search_prior_decisions(
                "Pick a payroll provider",
                ["gusto", "rippling"],
                decisions_dir,
            )
            self.assertEqual(results, [])

    def test_missing_dir_returns_empty_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "does-not-exist"
            results = search_prior_decisions(
                "Choose a database",
                ["postgres"],
                decisions_dir,
            )
            self.assertEqual(results, [])

    def test_result_entries_have_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = self._make_decisions_dir(tmp)
            results = search_prior_decisions(
                "Pick a cache layer",
                ["redis", "memcached"],
                decisions_dir,
            )
            self.assertGreater(len(results), 0)
            for r in results:
                self.assertIn("dec_id", r)
                self.assertIn("title", r)
                self.assertIn("path", r)
                self.assertIn("relevance_snippet", r)

    def test_option_label_overlap_also_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = self._make_decisions_dir(tmp)
            results = search_prior_decisions(
                "Pick the right tool",
                ["redis", "elasticache"],
                decisions_dir,
            )
            dec_ids = [r["dec_id"] for r in results]
            self.assertIn("DEC-0001", dec_ids)

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            results = search_prior_decisions("Anything", ["a", "b"], decisions_dir)
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
