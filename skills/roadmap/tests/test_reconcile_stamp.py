"""A reconcile that finds nothing still records that it ran.

`--apply-auto` answers "should items be mutated", not "did the check run". While the stamp lived
under that flag, the one outcome that should clear the staleness notice — no drift, nothing to
apply — was the one that never recorded it, so the roadmap gate's "never been reconciled" line
could never clear.

The second assertion in each case is the one that matters: `last_reconcile` is inside the content
hash that `ROADMAP.md`'s banner carries, so a stamp written without re-rendering leaves `validate`
— the CI gate — failing on a tree nobody edited. A test that only checked the date would pass while
reintroducing exactly that.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import render as render_mod  # noqa: E402
from scripts.roadmap import main  # noqa: E402

TODAY = "2026-08-10"


def _run(json_path, *argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--path", json_path, "--today", TODAY, *argv])
    return code, out.getvalue(), err.getvalue()


def _load(json_path):
    with open(json_path, encoding="utf-8") as fh:
        return json.load(fh)


class TestReconcileStamp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self._tmp.name, "docs", "roadmap", "roadmap.json")
        _run(self.json_path, "init", "--scope", "task:Demo")
        _run(self.json_path, "add", "--title", "First thing", "--kind", "feature")
        self.addCleanup(self._tmp.cleanup)

    def test_a_fresh_roadmap_has_never_been_reconciled(self):
        self.assertIsNone(_load(self.json_path)["last_reconcile"])

    def test_clean_reconcile_records_the_date(self):
        _run(self.json_path, "reconcile", "--no-git", "--no-gh")
        self.assertEqual(_load(self.json_path)["last_reconcile"], TODAY)

    def test_clean_reconcile_leaves_the_rendering_fresh(self):
        # The stamp changes the doc's content hash. If the render does not move with it, the
        # banner in ROADMAP.md disagrees with the doc and `validate` starts failing.
        _run(self.json_path, "reconcile", "--no-git", "--no-gh")
        self.assertFalse(render_mod.md_is_stale(self.json_path))

    def test_validate_stays_green_after_a_reconcile(self):
        # The outcome the previous test protects, asserted through the gate that would break.
        _run(self.json_path, "reconcile", "--no-git", "--no-gh")
        code, _, _ = _run(self.json_path, "validate")
        self.assertEqual(code, 0)

    def test_apply_auto_still_records(self):
        _run(self.json_path, "reconcile", "--no-git", "--no-gh", "--apply-auto")
        self.assertEqual(_load(self.json_path)["last_reconcile"], TODAY)
        self.assertFalse(render_mod.md_is_stale(self.json_path))

    def test_apply_auto_reports_zero_when_there_was_nothing_to_apply(self):
        # For as long as the flag had no appliers behind it, its message was the only thing
        # keeping it honest. Now that it applies, the counts have to stay honest instead: a clean
        # roadmap reports nothing added rather than a bare success line.
        _, out, _ = _run(self.json_path, "reconcile", "--no-git", "--no-gh", "--apply-auto")
        self.assertIn("0 item(s) added", out)
        self.assertNotIn("applied:", out)

    def test_no_render_writes_nothing_at_all(self):
        # --no-render documents itself as being for read-only checkouts and CI. Stamping the
        # canonical file there — while declining to update the rendering the stamp is hashed into
        # — would manufacture exactly the drift the other cases exist to prevent.
        _run(self.json_path, "--no-render", "reconcile", "--no-git", "--no-gh")
        self.assertIsNone(_load(self.json_path)["last_reconcile"])
        self.assertFalse(render_mod.md_is_stale(self.json_path))


if __name__ == "__main__":
    unittest.main()
