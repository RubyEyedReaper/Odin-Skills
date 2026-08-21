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
    MAX_CHANGELOG_UNLINKED,
    STALE_AFTER_DAYS,
    _changelog_unlinked,
    analyze,
    auto_applicable,
    empty_evidence,
    needs_reconcile,
)
from scripts.schema import default_doc  # noqa: E402

TODAY = "2026-07-29"

# Four levels up from `tests/`: roadmap -> skills -> .claude -> repository root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))


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



class TestUnlinkedIssueEvidence(unittest.TestCase):
    """DEC-0014: an open issue with no roadmap item is reported whatever its labels.

    `untracked-issue` keys on the `ready-for-agent` label. That label was never created on this
    tracker — 0 of 77 open issues carried it — so the check that should have caught 76 missing
    issues could not fire once. The new kind is advisory by construction: it is absent from
    `APPLIERS`, so it cannot reach `apply_auto` even if a future caller marks it `auto`.
    """

    def _issue(self, number, **kw):
        base = {"number": number, "state": "OPEN", "title": "Issue %s" % number, "labels": []}
        base.update(kw)
        return base

    def test_unlabelled_unlinked_open_issue_is_reported(self):
        ev = _ev(issues=[self._issue(41)])
        self.assertIn("unlinked-issue", _kinds(analyze(_doc(), ev, today=TODAY)))

    def test_unlinked_issue_never_auto_applies(self):
        ev = _ev(issues=[self._issue(41)])
        finding = [f for f in analyze(_doc(), ev, today=TODAY)
                   if f["kind"] == "unlinked-issue"][0]
        self.assertFalse(finding["auto"])

    def test_unlinked_issue_cannot_reach_an_applier(self):
        from scripts.reconcile import APPLIERS, apply_auto
        self.assertNotIn("unlinked-issue", APPLIERS)
        doc = _doc()
        ev = _ev(issues=[self._issue(41)])
        added = apply_auto(doc, analyze(doc, ev, today=TODAY), today=TODAY)
        self.assertEqual([a for a in added if a["title"].startswith("Issue 41")], [])

    def test_linked_issue_is_not_unlinked(self):
        doc = _doc(_item("RM-0001", links={
            "prd": None, "plan": None, "adr": None, "issues": ["#41"], "files": []}))
        ev = _ev(issues=[self._issue(41)])
        self.assertNotIn("unlinked-issue", _kinds(analyze(doc, ev, today=TODAY)))

    def test_closed_issue_is_not_unlinked(self):
        ev = _ev(issues=[self._issue(41, state="CLOSED")])
        self.assertNotIn("unlinked-issue", _kinds(analyze(_doc(), ev, today=TODAY)))

    def test_ready_labelled_issue_reports_the_actionable_kind_only(self):
        """No double report. `untracked-issue` is the actionable superset for a labelled issue;
        emitting both would put the same issue on two lines with two different proposals."""
        ev = _ev(issues=[self._issue(41, labels=["ready-for-agent"])])
        kinds = _kinds(analyze(_doc(), ev, today=TODAY))
        self.assertIn("untracked-issue", kinds)
        self.assertNotIn("unlinked-issue", kinds)

    def test_unlinked_issues_are_capped_and_the_overflow_counted(self):
        from scripts.reconcile import MAX_UNLINKED_ISSUES
        ev = _ev(issues=[self._issue(n) for n in range(MAX_UNLINKED_ISSUES + 3)])
        findings = analyze(_doc(), ev, today=TODAY)
        self.assertEqual(len([f for f in findings if f["kind"] == "unlinked-issue"]),
                         MAX_UNLINKED_ISSUES)
        truncated = [f for f in findings if f["kind"] == "unlinked-issue-truncated"][0]
        self.assertIn("3", truncated["message"])

    def test_untracked_issue_behaviour_is_unchanged(self):
        """The four cases in TestIssueEvidence are the contract; this pins the payload too."""
        ev = _ev(issues=[self._issue(99, title="Blog index", labels=["ready-for-agent"])])
        finding = [f for f in analyze(_doc(), ev, today=TODAY)
                   if f["kind"] == "untracked-issue"][0]
        self.assertTrue(finding["auto"])
        self.assertEqual(finding["payload"], {"issue": "99", "title": "Blog index"})

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




class TestChangelogChannel(unittest.TestCase):
    """The channel itself — `_changelog_unlinked`, which reads a file.

    #188: a roadmap that has never been reconciled has `last_reconcile: null`, and the channel
    returned `[]` on exactly that input. Every roadmap starts there, so the source could not fire
    until after a reconcile that had nothing to report — which is how 76 unlinked issues and 43
    unlinked CHANGELOG entries accumulated under a standing "no drift".
    """

    def _write(self, tmp, body):
        with open(os.path.join(tmp, "CHANGELOG.md"), "w", encoding="utf-8") as fh:
            fh.write(body)

    def test_never_reconciled_roadmap_examines_every_dated_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "- **Shipped the blog** (2026-07-20)\n"
                             "- **Dropped the old importer** (2026-07-21)\n")
            entries, dropped = _changelog_unlinked(tmp, _doc(last_reconcile=None))
        self.assertEqual(len(entries), 2)
        self.assertEqual(dropped, 0)

    def test_never_reconciled_roadmap_skips_linked_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "- **Shipped the blog** (2026-07-20, `RM-0004`)\n"
                             "- **Dropped the old importer** (2026-07-21)\n")
            entries, _ = _changelog_unlinked(tmp, _doc(last_reconcile=None))
        self.assertEqual(len(entries), 1)
        self.assertIn("importer", entries[0])

    def test_reconciled_roadmap_still_filters_by_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "- **Old, already seen** (2026-07-01)\n"
                             "- **New since last reconcile** (2026-07-28)\n")
            entries, _ = _changelog_unlinked(tmp, _doc(last_reconcile="2026-07-20"))
        self.assertEqual(len(entries), 1)
        self.assertIn("New since", entries[0])

    def test_overflow_is_counted_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "".join(
                "- **Change %02d** (2026-07-20)\n" % n
                for n in range(MAX_CHANGELOG_UNLINKED + 5)))
            entries, dropped = _changelog_unlinked(tmp, _doc(last_reconcile=None))
        self.assertEqual(len(entries), MAX_CHANGELOG_UNLINKED)
        self.assertEqual(dropped, 5)

    def test_absent_changelog_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_changelog_unlinked(tmp, _doc(last_reconcile=None)), ([], 0))

    def test_regex_matches_this_repositorys_real_changelog(self):
        """The examine-everything branch is the first thing to point this regex at real history.

        A synthetic fixture proves the branch runs; only the repository's own accumulated
        CHANGELOG proves the pattern matches the entries people actually write.
        """
        entries, dropped = _changelog_unlinked(REPO_ROOT, _doc(last_reconcile=None))
        self.assertTrue(entries, "no unlinked entries found in the repository's own CHANGELOG.md")
        self.assertLessEqual(len(entries), MAX_CHANGELOG_UNLINKED)
        for entry in entries:
            self.assertNotRegex(entry, r"RM-\d{4}")
        self.assertGreaterEqual(dropped, 0)

class TestTruncatedEvidence(unittest.TestCase):
    """A capped channel must say how much it dropped.

    Mirrors `untracked-surface-truncated`, which already exists for the sweep. Without these a
    reconcile on a long CHANGELOG or a busy tracker reports a bounded slice as if it were the whole
    truth, and the next run's output depends on what this one happened to see.
    """

    def test_changelog_truncation_is_reported(self):
        findings = analyze(_doc(), _ev(changelog_truncated=23), today=TODAY)
        self.assertIn("unrecorded-change-truncated", _kinds(findings))

    def test_changelog_truncation_names_the_count(self):
        finding = [f for f in analyze(_doc(), _ev(changelog_truncated=23), today=TODAY)
                   if f["kind"] == "unrecorded-change-truncated"][0]
        self.assertIn("23", finding["message"])

    def test_changelog_truncation_never_auto_applies(self):
        finding = [f for f in analyze(_doc(), _ev(changelog_truncated=23), today=TODAY)
                   if f["kind"] == "unrecorded-change-truncated"][0]
        self.assertFalse(finding["auto"])

    def test_no_changelog_truncation_no_finding(self):
        findings = analyze(_doc(), _ev(changelog_truncated=0), today=TODAY)
        self.assertNotIn("unrecorded-change-truncated", _kinds(findings))

    def test_unlinked_issue_truncation_is_reported(self):
        findings = analyze(_doc(), _ev(unlinked_truncated=7), today=TODAY)
        self.assertIn("unlinked-issue-truncated", _kinds(findings))

    def test_unlinked_issue_truncation_never_auto_applies(self):
        finding = [f for f in analyze(_doc(), _ev(unlinked_truncated=7), today=TODAY)
                   if f["kind"] == "unlinked-issue-truncated"][0]
        self.assertFalse(finding["auto"])

    def test_no_unlinked_issue_truncation_no_finding(self):
        findings = analyze(_doc(), _ev(unlinked_truncated=0), today=TODAY)
        self.assertNotIn("unlinked-issue-truncated", _kinds(findings))

    def test_truncation_counters_are_channels_of_empty_evidence(self):
        ev = empty_evidence()
        self.assertEqual(ev.get("changelog_truncated"), 0)
        self.assertEqual(ev.get("unlinked_truncated"), 0)

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
