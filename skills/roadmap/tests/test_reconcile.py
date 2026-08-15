"""Tests for scripts/reconcile.py (stdlib only) — written before implementation.

`analyze` is pure: it takes a doc plus already-gathered evidence and returns findings.
That keeps these tests hermetic — no git, no `gh`, no network.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.reconcile import (  # noqa: E402
    STALE_AFTER_DAYS,
    analyze,
    auto_applicable,
    empty_evidence,
    needs_reconcile,
)
from scripts.schema import default_doc  # noqa: E402

TODAY = "2026-07-29"


def _item(item_id, **kw):
    base = {
        "id": item_id,
        "title": "Item " + item_id,
        "kind": "feature",
        "status": "proposed",
        "tier": "next",
        "deps": [],
        "parent": None,
        "phase": None,
        "priority": None,
        "owner_skill": None,
        "acceptance": [],
        "links": {"prd": None, "plan": None, "adr": None, "issues": [], "files": []},
        "created": TODAY,
        "updated": TODAY,
        "completed": None,
        "evidence": None,
        "notes": "",
    }
    base.update(kw)
    return base


def _doc(*items, **kw):
    doc = default_doc("task:Demo", today=TODAY)
    doc["items"] = list(items)
    doc.update(kw)
    return doc


def _ev(**kw):
    ev = empty_evidence()
    ev.update(kw)
    return ev


def _kinds(findings):
    return [f["kind"] for f in findings]


class TestStaleMarkdown(unittest.TestCase):
    def test_stale_md_reported_and_auto_applicable(self):
        findings = analyze(_doc(_item("RM-0001")), _ev(md_stale=True), today=TODAY)
        self.assertIn("md-stale", _kinds(findings))
        stale = [f for f in findings if f["kind"] == "md-stale"][0]
        self.assertTrue(stale["auto"])

    def test_fresh_md_not_reported(self):
        findings = analyze(_doc(_item("RM-0001")), _ev(md_stale=False), today=TODAY)
        self.assertNotIn("md-stale", _kinds(findings))


class TestStaleItems(unittest.TestCase):
    def test_in_progress_item_untouched_too_long_is_flagged(self):
        doc = _doc(_item("RM-0001", status="in-progress", updated="2026-07-01"))
        findings = analyze(doc, _ev(), today=TODAY)
        self.assertIn("stale-item", _kinds(findings))

    def test_recent_in_progress_item_is_not_flagged(self):
        doc = _doc(_item("RM-0001", status="in-progress", updated="2026-07-28"))
        findings = analyze(doc, _ev(), today=TODAY)
        self.assertNotIn("stale-item", _kinds(findings))

    def test_in_progress_with_recent_commits_is_not_flagged(self):
        doc = _doc(_item("RM-0001", status="in-progress", updated="2026-07-01"))
        findings = analyze(doc, _ev(git_touched={"RM-0001": ["src/a.ts"]}), today=TODAY)
        self.assertNotIn("stale-item", _kinds(findings))

    def test_stale_threshold_is_two_weeks(self):
        self.assertEqual(STALE_AFTER_DAYS, 14)


class TestIssueEvidence(unittest.TestCase):
    def test_closed_issue_on_unfinished_item_proposes_done(self):
        doc = _doc(_item("RM-0001", status="in-progress", links={
            "prd": "#12", "plan": None, "adr": None, "issues": ["#12"], "files": []}))
        ev = _ev(issues=[{"number": 12, "state": "CLOSED", "title": "x", "labels": []}])
        findings = analyze(doc, ev, today=TODAY)
        self.assertIn("issue-closed", _kinds(findings))

    def test_closed_issue_proposal_requires_confirmation(self):
        doc = _doc(_item("RM-0001", status="in-progress", links={
            "prd": "#12", "plan": None, "adr": None, "issues": ["#12"], "files": []}))
        ev = _ev(issues=[{"number": 12, "state": "CLOSED", "title": "x", "labels": []}])
        finding = [f for f in analyze(doc, ev, today=TODAY) if f["kind"] == "issue-closed"][0]
        self.assertFalse(finding["auto"], "promoting to done must never auto-apply")

    def test_untracked_ready_issue_is_reported(self):
        ev = _ev(issues=[{"number": 99, "state": "OPEN", "title": "Blog index",
                          "labels": ["ready-for-agent"]}])
        findings = analyze(_doc(), ev, today=TODAY)
        self.assertIn("untracked-issue", _kinds(findings))

    def test_untracked_issue_may_auto_add_as_proposed(self):
        ev = _ev(issues=[{"number": 99, "state": "OPEN", "title": "Blog index",
                          "labels": ["ready-for-agent"]}])
        finding = [f for f in analyze(_doc(), ev, today=TODAY)
                   if f["kind"] == "untracked-issue"][0]
        self.assertTrue(finding["auto"])

    def test_issue_already_linked_is_not_untracked(self):
        doc = _doc(_item("RM-0001", links={
            "prd": None, "plan": None, "adr": None, "issues": ["#99"], "files": []}))
        ev = _ev(issues=[{"number": 99, "state": "OPEN", "title": "Blog index",
                          "labels": ["ready-for-agent"]}])
        self.assertNotIn("untracked-issue", _kinds(analyze(doc, ev, today=TODAY)))


class TestDiskEvidence(unittest.TestCase):
    def test_done_item_with_no_surviving_files_is_false_done(self):
        doc = _doc(_item("RM-0001", status="done", completed="2026-07-01", links={
            "prd": None, "plan": None, "adr": None, "issues": [],
            "files": ["src/gone/**"]}))
        findings = analyze(doc, _ev(missing_files={"RM-0001": ["src/gone/**"]}), today=TODAY)
        self.assertIn("false-done", _kinds(findings))

    def test_false_done_never_auto_applies(self):
        doc = _doc(_item("RM-0001", status="done", completed="2026-07-01", links={
            "prd": None, "plan": None, "adr": None, "issues": [],
            "files": ["src/gone/**"]}))
        finding = [f for f in analyze(doc, _ev(missing_files={"RM-0001": ["src/gone/**"]}),
                                      today=TODAY) if f["kind"] == "false-done"][0]
        self.assertFalse(finding["auto"])

    def test_untracked_surface_reported(self):
        findings = analyze(_doc(), _ev(untracked_paths=["app/blog/page.tsx"]), today=TODAY)
        self.assertIn("untracked-surface", _kinds(findings))


class TestChangelogEvidence(unittest.TestCase):
    def test_entry_without_item_reference_is_flagged(self):
        ev = _ev(changelog_unlinked=["- **Shipped the blog (2026-07-20)**"])
        self.assertIn("unrecorded-change", _kinds(analyze(_doc(), ev, today=TODAY)))


class TestAutoApply(unittest.TestCase):
    def test_auto_applicable_splits_findings(self):
        doc = _doc(_item("RM-0001", status="done", completed="2026-07-01", links={
            "prd": None, "plan": None, "adr": None, "issues": [],
            "files": ["src/gone/**"]}))
        ev = _ev(md_stale=True, missing_files={"RM-0001": ["src/gone/**"]})
        findings = analyze(doc, ev, today=TODAY)
        auto, manual = auto_applicable(findings)
        self.assertTrue(all(f["auto"] for f in auto))
        self.assertTrue(all(not f["auto"] for f in manual))
        self.assertIn("md-stale", _kinds(auto))
        self.assertIn("false-done", _kinds(manual))


class TestReconcileTrigger(unittest.TestCase):
    def test_never_reconciled_needs_reconcile(self):
        self.assertTrue(needs_reconcile(_doc(last_reconcile=None), today=TODAY))

    def test_recent_reconcile_does_not(self):
        self.assertFalse(needs_reconcile(_doc(last_reconcile="2026-07-27"), today=TODAY))

    def test_week_old_reconcile_does(self):
        self.assertTrue(needs_reconcile(_doc(last_reconcile="2026-07-01"), today=TODAY))


class TestCleanRoadmap(unittest.TestCase):
    def test_healthy_roadmap_yields_no_findings(self):
        doc = _doc(
            _item("RM-0001", status="done", completed="2026-07-20"),
            _item("RM-0002", status="ready", deps=["RM-0001"]),
        )
        self.assertEqual(analyze(doc, _ev(), today=TODAY), [])


class TestEvidenceShape(unittest.TestCase):
    def test_empty_evidence_has_all_channels(self):
        ev = empty_evidence()
        for key in ("md_stale", "git_touched", "issues", "missing_files",
                    "untracked_paths", "changelog_unlinked"):
            self.assertIn(key, ev)

    def test_tempdir_roundtrip_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(os.path.isdir(tmp))


if __name__ == "__main__":
    unittest.main()
