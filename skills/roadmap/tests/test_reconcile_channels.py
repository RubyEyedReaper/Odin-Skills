"""Per-channel evidence status, and the CLI exit code built on it — written before implementation.

The invariant under test is ADR-0069: **evidence that could not be gathered is not evidence of
none.** Before this, `_run` collapsed "ran, found nothing" and "could not run" into the same bare
`None` at every call site, so a reconcile with no `gh` on PATH reported exactly what a reconcile of
a perfectly linked tracker reports — nothing. A CI gate built on that output is green precisely
when it is blind, which is the condition that let 76 unlinked issues accumulate.

`analyze` stays pure: it reads the status the gatherer recorded and emits findings, with no git,
no `gh`, and no network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.reconcile import (  # noqa: E402
    CHANNEL_RAN,
    CHANNEL_SKIPPED,
    CHANNEL_UNAVAILABLE,
    FINDING_KINDS,
    analyze,
    empty_evidence,
)
from scripts.schema import default_doc  # noqa: E402

TODAY = "2026-07-29"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*items, **kw):
    doc = default_doc("task:Demo", today=TODAY)
    doc["items"] = list(items)
    doc.update(kw)
    return doc


def _ev(**status):
    ev = empty_evidence()
    ev["channel_status"].update(status)
    return ev


def _kinds(findings):
    return [f["kind"] for f in findings]


def _roadmap(root, *args, **kw):
    """Drive the CLI the way a wrapper script does — argv in, `(exit, stdout, stderr)` out."""
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.roadmap", "--root", root, "--no-render"] + list(args),
        cwd=SKILL_DIR, capture_output=True, text=True, env=kw.get("env"),
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestChannelStatus(unittest.TestCase):
    def test_empty_evidence_carries_a_channel_status_map(self):
        self.assertIsInstance(empty_evidence().get("channel_status"), dict)

    def test_unavailable_channel_is_reported(self):
        findings = analyze(_doc(), _ev(gh=CHANNEL_UNAVAILABLE), today=TODAY)
        self.assertIn("evidence-unavailable", _kinds(findings))

    def test_unavailable_finding_names_the_channel(self):
        finding = [f for f in analyze(_doc(), _ev(gh=CHANNEL_UNAVAILABLE), today=TODAY)
                   if f["kind"] == "evidence-unavailable"][0]
        self.assertIn("gh", finding["message"])

    def test_unavailable_finding_never_auto_applies(self):
        finding = [f for f in analyze(_doc(), _ev(gh=CHANNEL_UNAVAILABLE), today=TODAY)
                   if f["kind"] == "evidence-unavailable"][0]
        self.assertFalse(finding["auto"])

    def test_channel_that_ran_is_not_reported(self):
        findings = analyze(_doc(), _ev(gh=CHANNEL_RAN, git=CHANNEL_RAN), today=TODAY)
        self.assertNotIn("evidence-unavailable", _kinds(findings))

    def test_deliberately_skipped_channel_is_not_reported(self):
        """`--no-gh` is a choice, not a blindness.

        A gate that failed on it could never be run offline on purpose, which is the only reason
        the flag exists.
        """
        findings = analyze(_doc(), _ev(gh=CHANNEL_SKIPPED), today=TODAY)
        self.assertNotIn("evidence-unavailable", _kinds(findings))

    def test_every_unavailable_channel_gets_its_own_finding(self):
        findings = analyze(
            _doc(), _ev(gh=CHANNEL_UNAVAILABLE, git=CHANNEL_UNAVAILABLE), today=TODAY)
        unavailable = [f for f in findings if f["kind"] == "evidence-unavailable"]
        self.assertEqual(len(unavailable), 2)
        self.assertEqual(
            sorted(f["payload"]["channel"] for f in unavailable), ["gh", "git"])

    def test_findings_are_deterministically_ordered(self):
        ev = _ev(gh=CHANNEL_UNAVAILABLE, git=CHANNEL_UNAVAILABLE)
        self.assertEqual(_kinds(analyze(_doc(), ev, today=TODAY)),
                         _kinds(analyze(_doc(), ev, today=TODAY)))


class TestGatheredStatus(unittest.TestCase):
    """The gatherer's half: a channel it was told not to run is `skipped`, not `unavailable`."""

    def _fixture(self, tmp):
        code, out, err = _roadmap(tmp, "init", "--scope", "task:Fixture")
        self.assertEqual(code, 0, err)

    def test_no_gh_records_skipped_not_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(tmp, "reconcile", "--no-gh", "--format", "json")
            self.assertEqual(code, 0, err)
        blind = [f["payload"]["channel"] for f in json.loads(out)
                 if f["kind"] == "evidence-unavailable"]
        self.assertNotIn("gh", blind)

    def test_missing_gh_binary_records_unavailable(self):
        """PATH without `gh` is the runner-without-a-token case, reproduced hermetically."""
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            empty_bin = os.path.join(tmp, "emptybin")
            os.makedirs(empty_bin)
            env = dict(os.environ, PATH=empty_bin)
            code, out, err = _roadmap(tmp, "reconcile", "--no-git", "--format", "json", env=env)
            self.assertEqual(code, 0, err)
        blind = [f["payload"]["channel"] for f in json.loads(out)
                 if f["kind"] == "evidence-unavailable"]
        self.assertEqual(blind, ["gh"])


class TestFindingKindRegistry(unittest.TestCase):
    """`FINDING_KINDS` is what `--fail-on` validates against, so it must not drift from `analyze`.

    Both directions matter. A kind `analyze` emits but the registry omits is unselectable — a gate
    that cannot be told to fail on it. A kind the registry lists but `analyze` cannot emit is a
    `--fail-on` value that is accepted and can never fire, which is a gate that passes for the
    wrong reason.
    """

    def _item(self, item_id, **kw):
        base = {
            "id": item_id, "title": "Item " + item_id, "kind": "feature",
            "status": "proposed", "tier": "next", "deps": [], "parent": None, "phase": None,
            "priority": None, "owner_skill": None, "acceptance": [],
            "links": {"prd": None, "plan": None, "adr": None, "issues": [], "files": []},
            "created": TODAY, "updated": TODAY, "completed": None, "evidence": None, "notes": "",
        }
        base.update(kw)
        return base

    def _everything(self):
        doc = _doc(
            self._item("RM-0001", status="in-progress", updated="2026-06-01"),
            self._item("RM-0002", status="in-progress", links={
                "prd": None, "plan": None, "adr": None, "issues": ["#7"], "files": []}),
            self._item("RM-0003", status="done", completed="2026-07-01", links={
                "prd": None, "plan": None, "adr": None, "issues": [], "files": ["src/gone/**"]}),
        )
        ev = empty_evidence()
        ev.update({
            "md_stale": True,
            "issues": [
                {"number": 7, "state": "CLOSED", "title": "closed", "labels": []},
                {"number": 8, "state": "OPEN", "title": "labelled", "labels": ["ready-for-agent"]},
                {"number": 9, "state": "OPEN", "title": "unlabelled", "labels": []},
            ],
            "missing_files": {"RM-0003": ["src/gone/**"]},
            "untracked_paths": ["app/blog/page.tsx"],
            "untracked_truncated": 1,
            "changelog_unlinked": ["- **Shipped something** (2026-07-20)"],
            "changelog_truncated": 1,
            "unlinked_truncated": 1,
        })
        ev["channel_status"]["gh"] = CHANNEL_UNAVAILABLE
        return doc, ev

    def test_every_emitted_kind_is_registered(self):
        doc, ev = self._everything()
        self.assertEqual(sorted(set(_kinds(analyze(doc, ev, today=TODAY))) - FINDING_KINDS), [])

    def test_every_registered_kind_is_reachable(self):
        doc, ev = self._everything()
        self.assertEqual(sorted(FINDING_KINDS - set(_kinds(analyze(doc, ev, today=TODAY)))), [])


class TestFailOn(unittest.TestCase):
    """`--fail-on` is what lets a CI wrapper key on an exit code instead of parsing a report."""

    def _fixture(self, tmp):
        code, out, err = _roadmap(tmp, "init", "--scope", "task:Fixture")
        self.assertEqual(code, 0, err)

    def _blind(self, tmp):
        empty_bin = os.path.join(tmp, "emptybin")
        if not os.path.isdir(empty_bin):
            os.makedirs(empty_bin)
        return dict(os.environ, PATH=empty_bin)

    def test_findings_alone_do_not_fail_without_fail_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            with open(os.path.join(tmp, "CHANGELOG.md"), "w", encoding="utf-8") as fh:
                fh.write("- **Shipped the blog** (2026-07-20)\n")
            code, out, err = _roadmap(tmp, "reconcile", "--no-gh")
        self.assertEqual(code, 0, err)
        self.assertIn("CHANGELOG entry references no roadmap item", out)

    def test_fail_on_exits_one_when_the_kind_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(
                tmp, "reconcile", "--no-git", "--fail-on", "evidence-unavailable",
                env=self._blind(tmp))
        self.assertEqual(code, 1, out + err)

    def test_fail_on_exits_zero_when_the_kind_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(
                tmp, "reconcile", "--no-gh", "--no-git", "--fail-on", "evidence-unavailable")
        self.assertEqual(code, 0, out + err)

    def test_fail_on_still_prints_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(
                tmp, "reconcile", "--no-git", "--fail-on", "evidence-unavailable",
                env=self._blind(tmp))
        self.assertIn("could not run", out)

    def test_unknown_kind_is_refused_not_silently_unmatched(self):
        """A typo'd kind that matched nothing would be a gate that passes for the wrong reason —
        the same failure shape as the `ready-for-agent` label that was never created."""
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(
                tmp, "reconcile", "--no-gh", "--no-git", "--fail-on", "evidence-unavailble")
        self.assertNotEqual(code, 0)
        self.assertIn("evidence-unavailble", err)

    def test_fail_on_accepts_a_comma_separated_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._fixture(tmp)
            code, out, err = _roadmap(
                tmp, "reconcile", "--no-git", "--fail-on", "md-stale,evidence-unavailable",
                env=self._blind(tmp))
        self.assertEqual(code, 1, out + err)


if __name__ == "__main__":
    unittest.main()
