"""The mistake log's contract, exercised through its pure seams.

The defect this whole engine exists to prevent is a count that cannot be taken: incidents recorded
in commit messages are organised by *when they were committed*, so nothing can say "this is the
fourth time". Everything below therefore asserts on **derived** counts and on the grammar that makes
two sessions land on the same key — never on a stored tally, which would be the correlate the
`mistake-to-gate` procedure forbids keying a check on.

The second thing under test is fail-closed behaviour. A scanner that returns "0 found, all clean"
for a wrong path is the failure mode this system was built after (audit F10), so an empty
enumeration is asserted to be an error, never a pass.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import mistakes  # noqa: E402

HEADER = (
    "# Mistakes — test evidence log\n\n"
    "| id | date | key | class | context | artifact | fix | status |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def log(*rows):
    """Build a log body from `(id, date, key, class, context, artifact, fix, status)` tuples."""
    return HEADER + "".join("| " + " | ".join(r) + " |\n" for r in rows)


def row(rid, key, status="logged", cls=None, date="2026-08-15"):
    return (rid, date, key, cls if cls is not None else key.split("/")[0],
            "context", "`path/to/file.py:1`", "a guard", status)


class ParseGrammar(unittest.TestCase):
    def test_parses_a_well_formed_row(self):
        rows = mistakes.parse_log(log(row("M-0001", "precondition/assumed-file-exists")))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].key, "precondition/assumed-file-exists")
        self.assertEqual(rows[0].cls, "precondition")
        self.assertEqual(rows[0].status, "logged")

    def test_empty_table_under_a_header_is_legal(self):
        self.assertEqual(mistakes.parse_log(HEADER), [])

    def test_unknown_class_prefix_is_a_grammar_error(self):
        with self.assertRaises(mistakes.GrammarError) as cm:
            mistakes.parse_log(log(row("M-0001", "typo/foo", cls="typo")))
        self.assertIn("typo", str(cm.exception))

    def test_class_column_disagreeing_with_the_key_prefix_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError) as cm:
            mistakes.parse_log(log(row("M-0001", "precondition/x", cls="input")))
        self.assertIn("class", str(cm.exception).lower())

    def test_two_slashes_in_a_key_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(log(row("M-0001", "input/a/b", cls="input")))

    def test_uppercase_in_a_key_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(log(row("M-0001", "input/Stale-Read", cls="input")))

    def test_bad_id_shape_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(log(row("1", "input/x")))

    def test_bad_date_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(log(row("M-0001", "input/x", date="15-08-2026")))

    def test_unknown_status_is_an_error(self):
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(log(row("M-0001", "input/x", status="fixed")))

    def test_error_names_the_line_number_of_the_offending_row(self):
        body = log(row("M-0001", "input/ok"), row("M-0002", "typo/bad", cls="typo"))
        with self.assertRaises(mistakes.GrammarError) as cm:
            mistakes.parse_log(body, path="MISTAKES.md")
        # header(1) blank(2) columns(3) sep(4) first row(5) second row(6)
        self.assertIn("MISTAKES.md:6", str(cm.exception))

    def test_a_row_missing_a_column_is_an_error_not_a_skip(self):
        broken = HEADER + "| M-0001 | 2026-08-15 | input/x | input |\n"
        with self.assertRaises(mistakes.GrammarError):
            mistakes.parse_log(broken)


class Counts(unittest.TestCase):
    def test_counts_occurrences_per_key(self):
        rows = mistakes.parse_log(log(
            row("M-0001", "input/x"), row("M-0002", "input/x"), row("M-0003", "input/y")))
        self.assertEqual(mistakes.counts(rows), {"input/x": 2, "input/y": 1})

    def test_wontfix_rows_are_excluded_from_the_count(self):
        rows = mistakes.parse_log(log(
            row("M-0001", "input/x"), row("M-0002", "input/x", status="wontfix"),
            row("M-0003", "input/x", status="wontfix")))
        self.assertEqual(mistakes.counts(rows), {"input/x": 1})

    def test_band_names_the_required_response(self):
        self.assertEqual(mistakes.band(1), "logged")
        self.assertEqual(mistakes.band(2), "attention")
        self.assertEqual(mistakes.band(3), "attention")

    def test_band_at_threshold_without_the_rows_says_due_not_done(self):
        # harness:RM-0362. The threshold decides whether promotion is OWED; only the rows say
        # whether it HAPPENED. Asked without the rows, the honest answer is the owed one —
        # a band that assumes closure is the defect, not a default.
        self.assertEqual(mistakes.band(4), "promotion due")

    def test_band_reads_the_rows_when_it_is_given_them(self):
        key = "ci-gate/x"
        logged = mistakes.parse_log(log(*[
            row("M-%04d" % (i + 1), key) for i in range(4)]))
        promoted = mistakes.parse_log(log(*[
            row("M-%04d" % (i + 1), key, status="promoted") for i in range(4)]))
        self.assertEqual(mistakes.band(4, rows=logged, key=key), "promotion due")
        self.assertEqual(mistakes.band(4, rows=promoted, key=key), "promoted")

    def test_band_keeps_promoted_rule_distinguishable_from_promoted(self):
        # The two statuses carry different obligations — `promoted-rule` closes a CROSS-OWNER
        # promotion. Collapsing them in the display is this same defect one level down.
        key = "ci-gate/x"
        by_rule = mistakes.parse_log(log(*[
            row("M-%04d" % (i + 1), key, status="promoted-rule") for i in range(4)]))
        self.assertEqual(mistakes.band(4, rows=by_rule, key=key), "promoted-rule")

    def test_band_is_not_closed_by_one_unpromoted_row(self):
        key = "ci-gate/x"
        rows = mistakes.parse_log(log(
            *[row("M-%04d" % (i + 1), key, status="promoted") for i in range(3)],
            row("M-0004", key, status="guarded")))
        self.assertEqual(mistakes.band(4, rows=rows, key=key), "promotion due")

    def test_band_ignores_wontfix_rows_when_deciding_closure(self):
        # `counts` already excludes wontfix, so closure must too, or a key can never read closed.
        key = "ci-gate/x"
        rows = mistakes.parse_log(log(
            *[row("M-%04d" % (i + 1), key, status="promoted") for i in range(4)],
            row("M-0005", key, status="wontfix")))
        self.assertEqual(mistakes.band(4, rows=rows, key=key), "promoted")


class Due(unittest.TestCase):
    def _rows(self, n, status="logged"):
        return mistakes.parse_log(log(*[
            row("M-%04d" % (i + 1), "ci-gate/stale-reference", status=status) for i in range(n)]))

    def test_three_occurrences_are_not_due(self):
        self.assertEqual(mistakes.due(self._rows(3)), [])

    def test_four_occurrences_are_due(self):
        self.assertEqual(mistakes.due(self._rows(4)), ["ci-gate/stale-reference"])

    def test_four_promoted_occurrences_are_not_due(self):
        self.assertEqual(mistakes.due(self._rows(4, status="promoted")), [])

    def test_one_unpromoted_row_among_promoted_ones_is_still_due(self):
        rows = mistakes.parse_log(log(
            *[row("M-%04d" % (i + 1), "ci-gate/x", status="promoted") for i in range(3)],
            row("M-0004", "ci-gate/x", status="guarded")))
        self.assertEqual(mistakes.due(rows), ["ci-gate/x"])

    def test_five_rows_two_wontfix_are_not_due(self):
        rows = mistakes.parse_log(log(
            *[row("M-%04d" % (i + 1), "input/x") for i in range(3)],
            row("M-0004", "input/x", status="wontfix"),
            row("M-0005", "input/x", status="wontfix")))
        self.assertEqual(mistakes.due(rows), [])

    def test_threshold_is_a_parameter(self):
        self.assertEqual(mistakes.due(self._rows(2), threshold=2), ["ci-gate/stale-reference"])


class Siblings(unittest.TestCase):
    def test_reports_other_keys_sharing_a_class(self):
        rows = mistakes.parse_log(log(
            row("M-0001", "input/stale-read"), row("M-0002", "input/unbounded-retry"),
            row("M-0003", "ci-gate/other")))
        self.assertEqual(mistakes.siblings(rows, "input/stale-read"), ["input/unbounded-retry"])

    def test_near_duplicate_slug_is_flagged(self):
        rows = mistakes.parse_log(log(
            row("M-0001", "input/stale-read"), row("M-0002", "input/staleread")))
        self.assertEqual(mistakes.near_duplicates(rows, "input/stale-read"), ["input/staleread"])

    def test_a_key_is_never_its_own_sibling(self):
        rows = mistakes.parse_log(log(row("M-0001", "input/x"), row("M-0002", "input/x")))
        self.assertEqual(mistakes.siblings(rows, "input/x"), [])


class Owners(unittest.TestCase):
    def _tree(self, *projects_with_changelog, nested=()):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "CHANGELOG.md").write_text("# changelog\n")
        for slug in projects_with_changelog:
            d = tmp / "projects" / slug
            d.mkdir(parents=True)
            (d / "CHANGELOG.md").write_text("# changelog\n")
        for slug in nested:
            d = tmp / "projects" / slug
            d.mkdir(parents=True)
            (d / "CHANGELOG.md").write_text("# changelog\n")
            (d / ".git").mkdir()
        return tmp

    def test_root_and_projects_with_a_changelog_are_owners(self):
        tmp = self._tree("alpha", "beta")
        included, skipped = mistakes.owners(tmp)
        self.assertEqual([p.name for p in included], [tmp.name, "alpha", "beta"])
        self.assertEqual(skipped, [])

    def test_a_project_without_a_changelog_is_not_an_owner(self):
        tmp = self._tree("alpha")
        (tmp / "projects" / "gamma").mkdir()
        included, _ = mistakes.owners(tmp)
        self.assertNotIn("gamma", [p.name for p in included])

    def test_a_nested_repository_is_skipped_and_reported(self):
        tmp = self._tree("alpha", nested=("Nested",))
        included, skipped = mistakes.owners(tmp)
        self.assertNotIn("Nested", [p.name for p in included])
        self.assertEqual([p.name for p in skipped], ["Nested"])

    def test_a_root_that_is_not_a_directory_raises(self):
        with self.assertRaises(mistakes.EnumerationError):
            mistakes.owners(Path(tempfile.mkdtemp()) / "does-not-exist")

    def test_a_root_with_no_changelog_anywhere_raises(self):
        with self.assertRaises(mistakes.EnumerationError):
            mistakes.owners(Path(tempfile.mkdtemp()))


class Append(unittest.TestCase):
    def _log_path(self, body=None):
        tmp = Path(tempfile.mkdtemp()) / "MISTAKES.md"
        tmp.write_text(body if body is not None else log(row("M-0001", "input/x")))
        return tmp

    def test_appends_a_row_and_leaves_prior_lines_byte_identical(self):
        p = self._log_path()
        before = p.read_text()
        mistakes.append_row(p, key="input/y", context="c", artifact="`a.py:1`",
                            fix="f", date="2026-08-16")
        after = p.read_text()
        self.assertTrue(after.startswith(before))
        rows = mistakes.parse_log(after)
        self.assertEqual([r.key for r in rows], ["input/x", "input/y"])

    def test_allocates_the_next_id_in_the_owner_sequence(self):
        p = self._log_path()
        mistakes.append_row(p, key="input/y", context="c", artifact="`a.py:1`", fix="f")
        self.assertEqual(mistakes.parse_log(p.read_text())[-1].id, "M-0002")

    def test_first_row_of_an_empty_log_is_M_0001(self):
        p = self._log_path(HEADER)
        mistakes.append_row(p, key="input/y", context="c", artifact="`a.py:1`", fix="f")
        self.assertEqual(mistakes.parse_log(p.read_text())[0].id, "M-0001")

    def test_derives_the_class_column_from_the_key(self):
        p = self._log_path(HEADER)
        mistakes.append_row(p, key="error-path/unbounded-retry", context="c",
                            artifact="`a.py:1`", fix="f")
        self.assertEqual(mistakes.parse_log(p.read_text())[0].cls, "error-path")

    def test_refuses_an_ungrammatical_key_rather_than_writing_it(self):
        p = self._log_path(HEADER)
        with self.assertRaises(mistakes.GrammarError):
            mistakes.append_row(p, key="typo/foo", context="c", artifact="`a.py:1`", fix="f")
        self.assertEqual(p.read_text(), HEADER)

    def test_escapes_a_pipe_in_free_text_so_the_row_stays_parseable(self):
        p = self._log_path(HEADER)
        mistakes.append_row(p, key="input/x", context="a | b", artifact="`a.py:1`", fix="f")
        rows = mistakes.parse_log(p.read_text())
        self.assertEqual(len(rows), 1)
        self.assertIn("a", rows[0].context)


class BandAgreesWithCheck(unittest.TestCase):
    """harness:RM-0362 — one file, two readings, and the one a human reads first said the work
    was finished.

    THE FIXTURE IS LOAD-BEARING, and this is not a stylistic preference. The defect does NOT
    reproduce against the live `MISTAKES.md`: `check` reads clean there and the banded keys are
    genuinely promoted, so a matrix built from the live file is green before and after the fix and
    asserts nothing. The fixture is the real log with one key's rows set back to the status `main`
    carried before wave 3f promoted them — the recorded occurrence, not a plausible variant.

    Both commands are driven as SUBPROCESSES rather than through their functions: what the item is
    about is the word a human reads on `report`'s output line, which no call to `band()` proves.
    """
    KEY = "ci-gate/stale-count-assertion"

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[4]
        cls.engine = cls.repo / ".claude/skills/mistake-to-gate/scripts/mistakes.py"
        cls.real_log = cls.repo / "MISTAKES.md"
        if not cls.real_log.is_file() or not cls.engine.is_file():
            raise unittest.SkipTest("not running inside the harness repository")

    def fixture_from_real_log(self, key, status):
        """The real log with every row for `key` set to `status`, in its own owner root.

        The root needs a CHANGELOG.md or the tool refuses to scan it at all — owner enumeration
        is keyed on that file, and a root with none raises rather than reporting zero owners.
        """
        root = Path(tempfile.mkdtemp())
        (root / "CHANGELOG.md").write_text("# changelog\n")
        out, touched = [], 0
        for line in self.real_log.read_text().splitlines(True):
            if line.startswith("| M-") and ("| %s |" % key) in line:
                cells = line.rstrip("\n").split("|")
                for i in range(len(cells) - 1, -1, -1):
                    if cells[i].strip():
                        cells[i] = " %s " % status
                        touched += 1
                        break
                line = "|".join(cells) + "\n"
            out.append(line)
        self.assertGreaterEqual(
            touched, 4,
            "the fixture rewrote %d rows for %s — below the threshold, so it cannot reproduce "
            "the defect. Re-point this at a key the live log still carries." % (touched, key))
        (root / "MISTAKES.md").write_text("".join(out))
        return root

    def _run(self, *args):
        import subprocess
        proc = subprocess.run([sys.executable, str(self.engine)] + list(args),
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def _band_line(self, out):
        for line in out.splitlines():
            if self.KEY in line and "also in" not in line and line.startswith("  "):
                return line
        self.fail("no band line for %s in:\n%s" % (self.KEY, out))

    def test_band_and_check_agree_when_promotion_is_due(self):
        root = self.fixture_from_real_log(self.KEY, "logged")
        _, band = self._run("report", str(root), "--key", self.KEY)
        rc, _ = self._run("check", str(root))
        line = self._band_line(band)
        self.assertEqual(rc, 1, "check must call this promotion due")
        self.assertNotIn("promoted", line)   # check says due; report must not say done
        self.assertIn("due", line)

    def test_band_reads_promoted_when_the_rows_are_promoted(self):
        root = self.fixture_from_real_log(self.KEY, "promoted")
        _, band = self._run("report", str(root), "--key", self.KEY)
        rc, _ = self._run("check", str(root))
        self.assertEqual(rc, 0)
        self.assertIn("promoted", self._band_line(band))


if __name__ == "__main__":
    unittest.main()
