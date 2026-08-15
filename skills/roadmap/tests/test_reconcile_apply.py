"""`reconcile --apply-auto` applies something.

The flag shipped with no appliers behind it: `reconcile()` is pure, and nothing downstream ever
turned a finding's `proposal` into a mutation. Every case here asserts the **item** afterwards —
that a roadmap item now exists with the link that made the finding fire — because a test that
asserted the flag was accepted, or that the output mentioned applying, would have passed against
the version that applied nothing.

Idempotence is the second half. A finding is applied by adding an item that carries the evidence
key (`links.issues`, `links.files`), which is what makes the next `analyze` stop reporting it. If
that link were dropped, `--apply-auto` would add a duplicate item on every run.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import reconcile as reconcile_mod  # noqa: E402
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


def _issue(number, title):
    return {
        "number": number,
        "title": title,
        "state": "OPEN",
        "labels": [reconcile_mod.READY_LABEL],
    }


def _drifted_evidence(issues=(), paths=()):
    """A `gather_evidence` stand-in that reports the drift the appliers exist to close."""
    def _gather(json_path, doc, run_git=True, run_gh=True, surface_roots=None):
        ev = reconcile_mod.empty_evidence()
        ev["issues"] = list(issues)
        ev["untracked_paths"] = list(paths)
        return ev
    return _gather


class TestApplyAuto(unittest.TestCase):
    """The applier layer, called directly — no CLI, no rendering."""

    def setUp(self):
        self.doc = {"schema": 1, "scope": "task:Demo", "updated": TODAY,
                    "last_reconcile": None, "items": []}

    def test_an_untracked_ready_issue_becomes_an_item(self):
        findings = reconcile_mod.analyze(
            self.doc, _drifted_evidence(issues=[_issue(41, "Ship the widget")])(None, self.doc),
            today=TODAY)
        added = reconcile_mod.apply_auto(self.doc, findings, today=TODAY)
        self.assertEqual(len(added), 1)
        self.assertEqual(self.doc["items"][0]["title"], "Ship the widget")
        self.assertEqual(self.doc["items"][0]["links"]["issues"], ["41"])
        self.assertEqual(self.doc["items"][0]["status"], "proposed")

    def test_an_untracked_surface_becomes_an_item_carrying_its_path(self):
        findings = reconcile_mod.analyze(
            self.doc, _drifted_evidence(paths=["src/app/billing"])(None, self.doc), today=TODAY)
        added = reconcile_mod.apply_auto(self.doc, findings, today=TODAY)
        self.assertEqual(len(added), 1)
        self.assertIn("src/app/billing", added[0]["title"])
        self.assertEqual(added[0]["links"]["files"], ["src/app/billing"])
        self.assertEqual(added[0]["tier"], "someday")

    def test_applying_twice_adds_the_item_once(self):
        # The whole point of writing the evidence key onto the item. Second pass re-analyzes the
        # mutated doc, which is what a second `--apply-auto` run does.
        gather = _drifted_evidence(issues=[_issue(41, "Ship the widget")],
                                   paths=["src/app/billing"])
        reconcile_mod.apply_auto(
            self.doc, reconcile_mod.analyze(self.doc, gather(None, self.doc), today=TODAY),
            today=TODAY)
        reconcile_mod.apply_auto(
            self.doc, reconcile_mod.analyze(self.doc, gather(None, self.doc), today=TODAY),
            today=TODAY)
        self.assertEqual(len(self.doc["items"]), 2)

    def test_a_confirmation_finding_is_never_applied(self):
        # `analyze` marks these `auto: False`; apply_auto must not reach for an applier anyway.
        self.doc["items"] = [{
            "id": "RM-0001", "title": "Done thing", "kind": "feature", "status": "done",
            "tier": "now", "deps": [], "parent": None, "phase": None, "priority": None,
            "owner_skill": None, "acceptance": [], "links": reconcile_mod.schema_mod.empty_links(),
            "created": TODAY, "updated": TODAY, "completed": TODAY, "evidence": None, "notes": "",
        }]
        self.doc["items"][0]["links"]["files"] = ["nowhere/at/all.ts"]
        ev = reconcile_mod.empty_evidence()
        ev["missing_files"] = {"RM-0001": ["nowhere/at/all.ts"]}
        findings = reconcile_mod.analyze(self.doc, ev, today=TODAY)
        self.assertTrue(any(f["kind"] == "false-done" for f in findings))
        self.assertEqual(reconcile_mod.apply_auto(self.doc, findings, today=TODAY), [])
        self.assertEqual(len(self.doc["items"]), 1)


class TestApplyAutoThroughTheCli(unittest.TestCase):
    """End to end: the drift is seeded, the command runs, the saved file carries the item."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self._tmp.name, "docs", "roadmap", "roadmap.json")
        _run(self.json_path, "init", "--scope", "task:Demo")
        _run(self.json_path, "add", "--title", "First thing", "--kind", "feature")
        self.addCleanup(self._tmp.cleanup)

    def _reconcile(self, *argv, issues=(), paths=()):
        with mock.patch.object(reconcile_mod, "gather_evidence",
                               _drifted_evidence(issues=issues, paths=paths)):
            return _run(self.json_path, "reconcile", "--no-git", "--no-gh", *argv)

    def test_apply_auto_writes_the_new_item_to_disk(self):
        code, out, _ = self._reconcile("--apply-auto", issues=[_issue(41, "Ship the widget")])
        self.assertEqual(code, 0)
        titles = [item["title"] for item in _load(self.json_path)["items"]]
        self.assertIn("Ship the widget", titles)
        self.assertIn("applied", out)

    def test_without_the_flag_nothing_is_added(self):
        self._reconcile(issues=[_issue(41, "Ship the widget")])
        self.assertEqual(len(_load(self.json_path)["items"]), 1)

    def test_the_result_still_validates_and_renders(self):
        self._reconcile("--apply-auto", issues=[_issue(41, "Ship the widget")],
                        paths=["src/app/billing"])
        code, _, err = _run(self.json_path, "validate")
        self.assertEqual(code, 0, err)

    def test_no_render_applies_nothing(self):
        # A read-only checkout: report the drift, mutate neither the doc nor the rendering.
        with mock.patch.object(reconcile_mod, "gather_evidence",
                               _drifted_evidence(issues=[_issue(41, "Ship the widget")])):
            _run(self.json_path, "--no-render", "reconcile", "--no-git", "--no-gh", "--apply-auto")
        self.assertEqual(len(_load(self.json_path)["items"]), 1)

    def test_the_new_item_appears_in_the_rendered_roadmap(self):
        # The rendering is what a human reads; an item applied into the JSON alone is invisible.
        self._reconcile("--apply-auto", issues=[_issue(41, "Ship the widget")])
        md_path = os.path.join(self._tmp.name, "ROADMAP.md")
        with open(md_path, encoding="utf-8") as fh:
            self.assertIn("Ship the widget", fh.read())


if __name__ == "__main__":
    unittest.main()
