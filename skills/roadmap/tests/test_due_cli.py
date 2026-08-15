"""`roadmap due` — the contract a hook depends on.

The defect this closes is a bash copy of the staleness policy at 14 days shadowing the documented
7, so the trigger never fired once. The cases that matter are therefore the **boundary** ones: 6
days must stay silent and 7 must speak. A suite that only asserted "something is printed when very
stale" would have passed against every version of the bug.

`due` prints nothing when nothing is due. That is deliberate and load-bearing — it is what lets a
caller assign the output straight into a variable with no comparison of its own, which is the only
shape that cannot drift from the engine.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import reconcile as reconcile_mod  # noqa: E402
from scripts import render as render_mod  # noqa: E402
from scripts.roadmap import main  # noqa: E402

RECONCILED_ON = date(2026, 8, 1)


def _at(days_later):
    return (RECONCILED_ON + timedelta(days=days_later)).isoformat()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _run(json_path, *argv, today=None):
    out, err = io.StringIO(), io.StringIO()
    argv = ["--path", json_path, *(["--today", today] if today else []), *argv]
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestDueCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self._tmp.name, "docs", "roadmap", "roadmap.json")
        _run(self.json_path, "init", "--scope", "task:Demo")
        _run(self.json_path, "add", "--title", "First thing", "--kind", "feature")
        # Stamp through the engine, so the render hash stays valid.
        _run(self.json_path, "reconcile", "--no-git", "--no-gh", today=RECONCILED_ON.isoformat())
        self.addCleanup(self._tmp.cleanup)

    def test_a_fresh_reconcile_says_nothing(self):
        code, out, _ = _run(self.json_path, "due", today=_at(0))
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_one_day_short_of_the_threshold_says_nothing(self):
        # The half that stops the fix from becoming "always notice".
        code, out, _ = _run(self.json_path, "due", today=_at(reconcile_mod.RECONCILE_AFTER_DAYS - 1))
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_the_documented_age_speaks(self):
        # The regression. A bash copy at 14 stayed silent here for as long as it existed.
        code, out, _ = _run(self.json_path, "due", today=_at(reconcile_mod.RECONCILE_AFTER_DAYS))
        self.assertEqual(code, 0)
        self.assertIn("reconcile", out)
        self.assertIn(str(reconcile_mod.RECONCILE_AFTER_DAYS), out)

    def test_the_notice_carries_the_actual_age(self):
        _, out, _ = _run(self.json_path, "due", today=_at(11))
        self.assertIn("11 days", out)

    def test_a_roadmap_never_reconciled_says_so(self):
        path = os.path.join(self._tmp.name, "other", "roadmap.json")
        _run(path, "init", "--scope", "task:Other")
        code, out, _ = _run(path, "due", today=_at(0))
        self.assertEqual(code, 0)
        self.assertIn("never been reconciled", out)

    def test_json_carries_the_threshold_so_a_caller_need_not_know_it(self):
        code, out, _ = _run(self.json_path, "due", "--format", "json", today=_at(3))
        self.assertEqual(code, 0)
        status = json.loads(out)
        self.assertEqual(status["threshold"], reconcile_mod.RECONCILE_AFTER_DAYS)
        self.assertEqual(status["days"], 3)
        self.assertIs(status["due"], False)
        self.assertEqual(status["last_reconcile"], RECONCILED_ON.isoformat())

    def test_json_is_emitted_whether_or_not_anything_is_due(self):
        # Text is a message and stays silent; json is a document and always answers.
        _, out, _ = _run(self.json_path, "due", "--format", "json", today=_at(30))
        self.assertIs(json.loads(out)["due"], True)

    def test_due_never_renders(self):
        # It runs on a per-turn hook path. A read command that rewrites ROADMAP.md and shells out
        # to graphviz is not a read command.
        with open(os.path.join(self._tmp.name, "ROADMAP.md"), "a", encoding="utf-8") as fh:
            fh.write("\nhand-edited\n")
        self.assertTrue(render_mod.md_is_stale(self.json_path))
        md = os.path.join(self._tmp.name, "ROADMAP.md")
        before = _read(md)
        _run(self.json_path, "due", today=_at(30))
        self.assertEqual(before, _read(md))

    def test_due_never_mutates_the_canonical_doc(self):
        before = _read(self.json_path)
        _run(self.json_path, "due", today=_at(30))
        _run(self.json_path, "due", "--format", "json", today=_at(30))
        self.assertEqual(before, _read(self.json_path))

    def test_the_verdict_matches_the_predicate_it_wraps(self):
        # reconcile_status must not re-implement the comparison; this pins the two together at the
        # boundary, where a duplicate implementation would differ.
        doc = {"last_reconcile": RECONCILED_ON.isoformat()}
        for offset in (0, 6, 7, 8, 30):
            today = _at(offset)
            self.assertEqual(
                reconcile_mod.reconcile_status(doc, today=today)["due"],
                reconcile_mod.needs_reconcile(doc, today=today),
                "diverged at %s" % today,
            )


if __name__ == "__main__":
    unittest.main()
