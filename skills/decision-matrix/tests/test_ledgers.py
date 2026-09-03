"""Unit tests for scripts/ledgers.py — DEC ledger discovery and integrity.

The shell matrix (.claude/tests/decision-ledger.test.sh) covers the gate's exit codes and
messages end to end. These cover the parsing decisions underneath it, where the subtle
failures live: what counts as a table row, what counts as a record, and which subtrees are
in scope.

Every case builds its own tree under a TemporaryDirectory and passes it as the root — none
of them reads the repository, so the verdict cannot depend on the checkout.
"""
import tempfile
import unittest
from pathlib import Path

from scripts.ledgers import check_ledger, discover_ledgers, render_to, _index_rows


def write_record(ledger: Path, number: str, dec_id: str = None) -> Path:
    ledger.mkdir(parents=True, exist_ok=True)
    path = ledger / f"DEC-{number}-fixture.md"
    path.write_text(
        f"---\ndec_id: {dec_id or f'DEC-{number}'}\ndate: 2026-08-19\n"
        f"goal: Fixture {number}\nwinner: a\n---\n## Recommendation\n",
        encoding="utf-8",
    )
    return path


def render_ledger(ledger: Path) -> Path:
    """The index as the engine writes it — the only shape a healthy ledger has.

    `write_index` below stays for the cases that need an index the renderer would never
    produce. A passing case must not use it, or these tests assert that a hand-written
    index is acceptable, which is what the gate stopped accepting (harness:RM-0224).
    """
    ledger.mkdir(parents=True, exist_ok=True)
    return render_to(ledger)


def write_index(ledger: Path, *numbers: str) -> Path:
    ledger.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f"| DEC-{n} | Fixture {n} | a | [DEC-{n}-fixture.md](DEC-{n}-fixture.md) |" for n in numbers
    )
    path = ledger / "README.md"
    path.write_text(
        "# Decision Ledger\n\n| DEC | Title | Winner | Record |\n|---|---|---|---|\n"
        + (rows + "\n" if rows else "")
        + "\n<!-- trailing prose -->\n",
        encoding="utf-8",
    )
    return path


class TestIndexRows(unittest.TestCase):
    def test_reads_rows_inside_the_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            readme = write_index(Path(tmp), "0001", "0002")
            self.assertEqual(sorted(_index_rows(readme)), ["DEC-0001", "DEC-0002"])

    def test_a_row_after_a_blank_line_is_not_a_row(self):
        """A blank line ends a GFM table. Counting pipe-prefixed lines anywhere is what
        let the harness ledger's split index read as healthy."""
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "# Decision Ledger\n\n| DEC | Title | Winner | Record |\n|---|---|---|---|\n"
                "| DEC-0001 | One | a | [DEC-0001-fixture.md](DEC-0001-fixture.md) |\n"
                "\n"
                "| DEC-0002 | Orphan | a | [DEC-0002-fixture.md](DEC-0002-fixture.md) |\n",
                encoding="utf-8",
            )
            rows = _index_rows(readme)
            self.assertIn("DEC-0001", rows)
            self.assertNotIn("DEC-0002", rows, "the orphaned row is not in the table")

    def test_prose_containing_pipes_is_not_a_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "Prose with | a pipe | in it.\n\n"
                "| DEC | Title | Winner | Record |\n|---|---|---|---|\n"
                "| DEC-0001 | One | a | [DEC-0001-fixture.md](DEC-0001-fixture.md) |\n",
                encoding="utf-8",
            )
            self.assertEqual(list(_index_rows(readme)), ["DEC-0001"])

    def test_missing_readme_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_index_rows(Path(tmp) / "nope.md"), {})


class TestCheckLedger(unittest.TestCase):
    def test_clean_ledger_has_no_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0001")
            write_record(ledger, "0002")
            render_ledger(ledger)
            self.assertEqual(check_ledger(ledger), [])

    def test_record_without_a_row_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0001")
            write_record(ledger, "0002")
            write_index(ledger, "0001")
            failures = check_ledger(ledger)
            # Two failures, not one: the record has no row, AND the index no longer matches
            # what the records render. Both are true and each is worth naming — a reader who
            # sees only "no row" reaches for the row rather than for the renderer.
            self.assertTrue(any("DEC-0002" in f and "no row" in f for f in failures), failures)
            self.assertTrue(any("stale or hand-edited" in f for f in failures), failures)

    def test_dec_id_disagreeing_with_the_filename_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0002", dec_id="DEC-0001")
            write_index(ledger, "0002")
            self.assertTrue(any("disagree" in f for f in check_ledger(ledger)))

    def test_row_naming_no_record_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0001")
            write_index(ledger, "0001", "0002")
            self.assertTrue(any("names no record" in f for f in check_ledger(ledger)))

    def test_two_records_sharing_a_number_fails(self):
        """THE INCIDENT (2026-08-20). Two live sessions each read the ledger's high-water
        mark in their own worktree and both minted DEC-0028, for two unrelated decisions.
        Both records were correct in isolation — right frontmatter, one index row between
        them — so every predicate here passed and the gate exited 0. Uniqueness of the
        number across records was the one thing nothing asserted.

        This is the half of harness:RM-0165 that survives a fresh clone: no local counter
        can see a duplicate that arrived by `git pull`."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            ledger.mkdir(parents=True)
            for slug in ("alpha", "beta"):
                (ledger / f"DEC-0028-{slug}.md").write_text(
                    "---\ndec_id: DEC-0028\ndate: 2026-08-20\n"
                    f"goal: Fixture {slug}\nwinner: a\n---\n## Recommendation\n",
                    encoding="utf-8",
                )
            (ledger / "README.md").write_text(
                "# Decision Ledger\n\n| DEC | Title | Winner | Record |\n|---|---|---|---|\n"
                "| DEC-0028 | Alpha | a | [DEC-0028-alpha.md](DEC-0028-alpha.md) |\n",
                encoding="utf-8",
            )
            failures = check_ledger(ledger)
            self.assertTrue(any("share the number" in f for f in failures), failures)
            joined = " ".join(failures)
            self.assertIn("DEC-0028-alpha.md", joined)
            self.assertIn("DEC-0028-beta.md", joined)

    def test_one_record_per_number_passes(self):
        """The negative control. Without it the uniqueness check could be unconditional."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0027")
            write_record(ledger, "0028")
            render_ledger(ledger)
            self.assertEqual(check_ledger(ledger), [])

    def test_numbering_gaps_are_not_a_failure(self):
        """next_dec_number is max+1 and workers reserve id blocks, so gaps are the
        expected residue of normal operation rather than drift."""
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            for n in ("0001", "0004", "0009"):
                write_record(ledger, n)
            render_ledger(ledger)
            self.assertEqual(check_ledger(ledger), [])

    def test_html_artifacts_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0001")
            (ledger / "DEC-0001-fixture.html").write_text("<html></html>", encoding="utf-8")
            render_ledger(ledger)
            self.assertEqual(check_ledger(ledger), [])

    def test_records_with_no_readme_fail_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            write_record(ledger, "0001")
            failures = check_ledger(ledger)
            self.assertEqual(len(failures), 1)
            self.assertIn("no README.md", failures[0])

    def test_empty_ledger_directory_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "decisions"
            ledger.mkdir()
            self.assertEqual(check_ledger(ledger), [])


class TestDiscoverLedgers(unittest.TestCase):
    def test_finds_the_harness_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude/docs/decisions").mkdir(parents=True)
            ledgers, skipped = discover_ledgers(root)
            self.assertEqual([p.name for p in ledgers], ["decisions"])
            self.assertEqual(skipped, [])

    def test_finds_project_ledgers_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude/docs/decisions").mkdir(parents=True)
            (root / "projects/demo/docs/decisions").mkdir(parents=True)
            ledgers, _ = discover_ledgers(root)
            self.assertEqual(len(ledgers), 2)

    def test_a_nested_repository_is_skipped_and_named(self):
        """DEC-0003's exclude-and-report precedent: the harness cannot commit a fix into
        another repository, so a failure there is one its owner cannot clear."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude/docs/decisions").mkdir(parents=True)
            (root / "projects/nested/docs/decisions").mkdir(parents=True)
            (root / "projects/nested/.git").mkdir()
            ledgers, skipped = discover_ledgers(root)
            self.assertEqual(len(ledgers), 1)
            self.assertEqual(len(skipped), 1)
            self.assertIn("nested repository", skipped[0][1])

    def test_a_project_without_a_ledger_is_absent_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude/docs/decisions").mkdir(parents=True)
            (root / "projects/demo/docs").mkdir(parents=True)
            ledgers, skipped = discover_ledgers(root)
            self.assertEqual(len(ledgers), 1)
            self.assertEqual(skipped, [])

    def test_no_ledgers_at_all_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledgers, skipped = discover_ledgers(Path(tmp))
            self.assertEqual(ledgers, [])
            self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
