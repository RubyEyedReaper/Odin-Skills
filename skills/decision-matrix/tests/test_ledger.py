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
    IdCollision,
    allocate_dec_id,
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

    def test_new_row_lands_in_the_real_table_when_a_blank_line_split_it(self):
        """A blank line inside the table ends it, under GFM: every row after the gap
        renders as a paragraph of pipes. Inserting after the LAST pipe-prefixed line
        anywhere puts new rows into that orphan, so the ledger index silently stops
        being a table and every later row joins the wreckage.

        This is the shipped harness ledger's own state as of 2026-08-19 — a gap after
        the DEC-0015 row left DEC-0017..0019 outside the table.
        """
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "README.md").write_text(
                "# Decision Ledger\n"
                "\n"
                "| DEC | Title | Winner | Record |\n"
                "|---|---|---|---|\n"
                "| DEC-0001 | First | a | [DEC-0001-a.md](DEC-0001-a.md) |\n"
                "\n"
                "| DEC-0002 | Orphaned | b | [DEC-0002-b.md](DEC-0002-b.md) |\n"
                "\n"
                "<!-- New DEC rows are appended above by ledger.py -->\n"
            )
            dec_path = decisions_dir / "DEC-0003-third.md"
            dec_path.write_text("# stub")
            update_readme_index("DEC-0003", "Third", dec_path, decisions_dir, winner="c")

            lines = (decisions_dir / "README.md").read_text().splitlines()
            sep = next(i for i, l in enumerate(lines) if l.startswith("|---"))
            row = next(i for i, l in enumerate(lines) if l.startswith("| DEC-0003 |"))

            # Contiguous with the header separator: no blank line between them.
            self.assertTrue(
                all(lines[i].startswith("|") for i in range(sep, row + 1)),
                "the new row must be inside the table the header separator opens, "
                "not appended to a detached fragment",
            )

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


class TestVetoSectionInRecord(unittest.TestCase):
    """harness:RM-0228 — the record must say WHY an option was eliminated.

    Before this, a vetoed option printed real per-criterion numbers and an em-dash for its
    total, which is what an unscored option looks like. On the record that motivated this
    item the vetoed row scored 95 and 95 and read as the strongest contender.
    """

    def _vetoed(self, **constraint_overrides):
        constraint = {
            "id": "self-hostable",
            "description": "Must be self-hostable on our own hardware",
        }
        constraint.update(constraint_overrides)
        spec = _spec(constraints=[constraint])
        spec["options"][1]["constraint_results"] = {"self-hostable": False}
        result = _result(
            vetoed_options=["memcached"],
            active_options=["redis"],
            veto_reasons=[{
                "option": "memcached",
                "option_label": "Memcached",
                "constraints": [{
                    "id": "self-hostable",
                    "description": constraint["description"],
                    "lifted_by": constraint.get("lifted_by"),
                }],
            }],
        )
        result["method_results"]["weighted-sum"]["ranking"] = [
            {"option": "redis", "score": 82.0, "rank": 1},
        ]
        return spec, result

    def _write(self, spec, result):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path, _ = write_dec_record("DEC-0001", spec, result, Path(tmp) / "decisions")
        return path.read_text(encoding="utf-8")

    def test_the_record_names_the_violated_constraint_id(self):
        text = self._write(*self._vetoed())
        self.assertIn("self-hostable", text)

    def test_the_record_carries_the_constraint_description(self):
        """The id is the machine handle for a re-run; the description is what a human
        needs to know what would lift it. Neither is recoverable from the other."""
        text = self._write(*self._vetoed())
        self.assertIn("Must be self-hostable on our own hardware", text)

    def test_the_vetoed_row_is_marked_in_the_scored_matrix(self):
        """A section further down does not repair the table a reader scans first."""
        text = self._write(*self._vetoed())
        row = next(ln for ln in text.splitlines() if ln.startswith("| Memcached"))
        self.assertIn("(vetoed)", row)
        # Not an em-dash, which means "no data", and not a number either: an eliminated
        # option was never ranked, so a score beside it is the misreading this item names.
        self.assertNotIn("|—|", row.replace(" ", ""))
        self.assertTrue(row.rstrip().endswith("| vetoed |"), row)

    def test_the_active_row_is_untouched(self):
        text = self._write(*self._vetoed())
        row = next(ln for ln in text.splitlines() if ln.startswith("| Redis"))
        self.assertNotIn("vetoed", row)
        self.assertIn("82.00", row)

    def test_a_declared_expiry_condition_reaches_the_record(self):
        spec, result = self._vetoed(lifted_by="The Q3 hardware order, which adds a rack")
        text = self._write(spec, result)
        self.assertIn("The Q3 hardware order, which adds a rack", text)

    def test_no_declared_expiry_says_so_rather_than_inventing_one(self):
        """A sentence derived from {id, description} restates the veto in future tense
        and names no event outside the decision. An honest absence beats a tautology
        that satisfies a grep."""
        text = self._write(*self._vetoed())
        self.assertIn("no expiry condition declared", text.lower())

    def test_a_record_with_nothing_vetoed_has_no_veto_section(self):
        text = self._write(_spec(), _result(veto_reasons=[]))
        self.assertNotIn("Vetoed", text)

    def test_a_result_predating_the_key_still_renders_from_the_spec(self):
        """write_dec_record already receives the spec, and hand-built result dicts exist
        in this very module. A missing key must degrade, never raise."""
        spec, _ = self._vetoed()
        legacy = _result(vetoed_options=["memcached"], active_options=["redis"])
        self.assertNotIn("veto_reasons", legacy)

        text = self._write(spec, legacy)
        self.assertIn("self-hostable", text)
        self.assertIn("Must be self-hostable on our own hardware", text)

    def test_an_undeclared_constraint_id_renders_without_an_empty_gap(self):
        spec = _spec()
        spec["options"][1]["constraint_results"] = {"x": False}
        result = _result(
            vetoed_options=["memcached"],
            active_options=["redis"],
            veto_reasons=[{
                "option": "memcached",
                "option_label": "Memcached",
                "constraints": [{"id": "x", "description": None, "lifted_by": None}],
            }],
        )

        text = self._write(spec, result)
        section = text.split("## Vetoed by Constraint", 1)[1].split("## Sensitivity", 1)[0]
        self.assertIn("`x`", section)
        # Scoped to the section: the record's Caveats line legitimately reads "_None._".
        self.assertNotIn("None", section)

    def test_a_pipe_in_a_description_does_not_break_the_table(self):
        """Constraint text is free user input interpolated into markdown. The shell gate
        over DEC records parses frontmatter and index rows only, so a mangled body passes
        CI silently and is found by reading a record."""
        spec, result = self._vetoed()
        broken = "Must be self-hostable | on-prem or colo"
        spec["constraints"][0]["description"] = broken
        result["veto_reasons"][0]["constraints"][0]["description"] = broken

        text = self._write(spec, result)
        rows = [ln for ln in text.splitlines() if ln.startswith("|")]
        # Derived from the header, never hardcoded: the count is a property of the criteria
        # in the spec, and a literal here would fail for a reason that is not the defect.
        expected = rows[0].count("|")
        for line in rows:
            self.assertEqual(
                expected, line.count("|"), f"a description leaked a cell boundary into: {line}"
            )

    def test_a_newline_in_a_description_stays_on_one_line(self):
        spec, result = self._vetoed()
        broken = "Must be self-hostable\n\n---\nnot really frontmatter"
        spec["constraints"][0]["description"] = broken
        result["veto_reasons"][0]["constraints"][0]["description"] = broken

        text = self._write(spec, result)
        body = text.split("---\n", 2)[2]
        self.assertNotIn("\n---\n", body)
        self.assertIn("not really frontmatter", body)


class TestUpdateReadmeIndex(unittest.TestCase):

    def test_creates_readme_with_header_if_missing(self):
        """The title comes from the RECORD, never from the caller (harness:RM-0224).

        The arguments this function still takes are ignored: the index is rendered from
        every record's frontmatter, so a caller cannot tell it a row that the ledger does
        not already say. Being told a row is what let the index and the records disagree
        (issue #244) — a hand-written record never made the call.
        """
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            dec_path = decisions_dir / "DEC-0001-pick-a-cache.md"
            dec_path.write_text(
                "---\ndec_id: DEC-0001\ngoal: Pick a cache\nwinner: redis\n---\n# body",
                encoding="utf-8",
            )
            update_readme_index("DEC-0001", "ignored", dec_path, decisions_dir, winner="ignored")
            readme = decisions_dir / "README.md"
            self.assertTrue(readme.exists())
            content = readme.read_text()
            self.assertIn("| DEC-0001 | Pick a cache | redis |", content)
            self.assertNotIn("ignored", content)

    def test_upserts_without_duplicating_existing_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            dec_path = decisions_dir / "DEC-0001-pick-a-cache.md"
            dec_path.write_text(
                "---\ndec_id: DEC-0001\ngoal: Pick a cache\nwinner: redis\n---\n# body",
                encoding="utf-8",
            )
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
            p1.write_text("---\ndec_id: DEC-0001\ngoal: First Decision\nwinner: redis\n---\n",
                          encoding="utf-8")
            p2 = decisions_dir / "DEC-0002-second.md"
            p2.write_text("---\ndec_id: DEC-0002\ngoal: Second Decision\nwinner: memcached\n---\n",
                          encoding="utf-8")
            update_readme_index("DEC-0001", "First Decision", p1, decisions_dir, winner="redis")
            update_readme_index("DEC-0002", "Second Decision", p2, decisions_dir, winner="memcached")
            content = (decisions_dir / "README.md").read_text()
            self.assertIn("DEC-0001", content)
            self.assertIn("DEC-0002", content)

    def test_a_row_lands_inside_the_table_and_the_trailer_stays_below_it(self):
        """A row outside the table is not a row under GFM.

        The hazard this case was written for — an append walking past a trailing HTML
        comment — cannot occur any more: the whole file is generated, so the trailer is
        placed rather than stepped over, and a hand-edited file is caught by the checker
        rather than appended to. The invariant survives the mechanism: every row sits in
        the contiguous block the header separator opens, and prose sits below it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "README.md").write_text(
                "# Decision Ledger\n"
                "\n"
                "| DEC | Title | Winner | Record |\n"
                "|---|---|---|---|\n"
                "\n"
                "<!-- a hand-written index, which the render replaces outright -->\n"
            )
            dec_path = decisions_dir / "DEC-0001-pick.md"
            dec_path.write_text("---\ndec_id: DEC-0001\ngoal: Pick\nwinner: redis\n---\n",
                                encoding="utf-8")
            update_readme_index("DEC-0001", "Pick", dec_path, decisions_dir, winner="redis")
            lines = (decisions_dir / "README.md").read_text().splitlines()
            row_index = next(i for i, l in enumerate(lines) if l.startswith("| DEC-0001 |"))
            sep_index = next(i for i, l in enumerate(lines) if l.startswith("|--"))
            self.assertGreater(row_index, sep_index)
            self.assertTrue(all(lines[i].startswith("|") for i in range(sep_index, row_index + 1)))
            self.assertTrue(any(l.startswith(">") for l in lines[row_index + 1:]))

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
            holder.write_text("---\ndec_id: DEC-0001\ngoal: Claimed first\nwinner: first\n---\n",
                              encoding="utf-8")
            update_readme_index("DEC-0001", "Claimed first", holder, decisions_dir, winner="first")

            path, resolved_id = write_dec_record("DEC-0001", _spec(), _result(), decisions_dir)
            update_readme_index(resolved_id, "Second decision", path, decisions_dir, winner="redis")

            readme = (decisions_dir / "README.md").read_text(encoding="utf-8")
            # Each row's text comes from its own record, so the second write cannot
            # overwrite the holder's row even when it walks in holding the holder's id.
            self.assertIn("| DEC-0001 | Claimed first | first |", readme)
            self.assertIn("| DEC-0002 |", readme)
            self.assertIn("DEC-0002-", readme)


if __name__ == "__main__":
    unittest.main()


class TestAllocateDecId(unittest.TestCase):
    """harness:RM-0165 — the allocator, seen through the DEC ledger's own entry point.

    The cross-worktree behaviour is asserted by `.claude/tests/id-allocation.test.sh`,
    which builds real repositories. These cases cover the seam: that `allocate_dec_id`
    hands `next_dec_number`'s answer down as the floor, and that a requested id is either
    honoured exactly or refused loudly.

    THE EVIDENCE, three instances in one campaign. Two sessions minted DEC-0028 for
    unrelated decisions on 2026-08-20. A third worker, holding a reservation of 0036-0038
    in writing, minted 0029/0038/0038 and renamed the files and repaired the index rows by
    hand afterwards — because there was no way to tell the engine an id. That third one is
    the cleanest statement of the defect: a reservation that exists only in prose binds
    nothing.
    """

    def test_the_ledger_scan_is_the_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "DEC-0041-existing.md").write_text("x", encoding="utf-8")
            with allocate_dec_id(decisions_dir) as dec_id:
                self.assertEqual(dec_id, "DEC-0042")

    def test_a_requested_id_is_honoured_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            with allocate_dec_id(decisions_dir, want="DEC-0042") as dec_id:
                self.assertEqual(dec_id, "DEC-0042")

    def test_a_requested_id_already_on_disk_is_refused(self):
        """Not bumped. A caller that asked for DEC-0042 and silently received DEC-0043
        writes 0043's record under 0042's name in four places, all self-consistent."""
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            (decisions_dir / "DEC-0042-taken.md").write_text("x", encoding="utf-8")
            with self.assertRaises(IdCollision):
                with allocate_dec_id(decisions_dir, want="DEC-0042"):
                    pass

    def test_a_malformed_request_is_refused_rather_than_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir()
            with self.assertRaises(ValueError):
                with allocate_dec_id(decisions_dir, want="0042"):
                    pass
