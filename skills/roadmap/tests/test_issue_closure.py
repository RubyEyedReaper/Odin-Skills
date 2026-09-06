"""Reaching a terminal status closes the item's tracker issues.

The gate `.claude/scripts/roadmap-issue-link-check.sh` refuses a `done` item whose issue is still
open. That gate is the backstop; this is the path that makes the fact true at the moment it becomes
true, so a human is not left reconciling two records by hand.

Two properties matter here, and only one of them is the happy path:

1. the closer is called once per linked issue, with that issue's number
2. **the status is still written when the closer fails.** `roadmap.json` is canonical and the
   tracker is a mirror. Refusing to record a true local fact — this work is finished — because a
   remote service is unreachable inverts that, and an offline session would be unable to record
   completed work at all. The failure is reported loudly with the exact command to retry.

The closer is a seam. A test that called the real `gh` would file network traffic against a live
tracker from a unit suite, and would answer differently on every host and on every day
(`ci-gate/fixture-reads-ambient-state`).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import roadmap as roadmap_mod  # noqa: E402


def _roadmap(tmp, items):
    d = os.path.join(tmp, "docs", "roadmap")
    os.makedirs(d)
    p = os.path.join(d, "roadmap.json")
    with open(p, "w") as fh:
        json.dump({"schema": 1, "scope": "harness", "updated": "2026-09-01",
                   "items": items}, fh)
    return p


def _item(id_, status, issues=None):
    it = {"id": id_, "title": "fixture %s" % id_, "kind": "infra", "tier": "next",
          "status": status, "created": "2026-09-01", "updated": "2026-09-01"}
    if issues:
        it["links"] = {"issues": list(issues)}
    return it


class _Args(object):
    """The attribute surface `cmd_set` reads. A namespace rather than argparse, so a field the
    engine starts reading tomorrow fails loudly here instead of silently defaulting."""

    def __init__(self, path, id_, status):
        self.path = path
        self.root = None
        self.id = id_
        self.status = status
        self.today = "2026-09-01"
        self.force = True
        for f in ("title", "kind", "tier", "deps", "parent", "phase", "owner_skill",
                  "acceptance", "score", "method", "notes", "evidence", "prd", "plan",
                  "adr", "issues", "files"):
            setattr(self, f, None)


class IssueClosureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.calls = []

    def _run(self, items, id_, status, closer):
        path = _roadmap(self.tmp, items)
        args = _Args(path, id_, status)
        prev = roadmap_mod.ISSUE_CLOSER
        roadmap_mod.ISSUE_CLOSER = closer
        try:
            rc = roadmap_mod.cmd_set(args)
        finally:
            roadmap_mod.ISSUE_CLOSER = prev
        with open(path) as fh:
            doc = json.load(fh)
        return rc, doc

    def _closer(self, number, reason, cwd):
        self.calls.append((number, reason))

    def test_done_closes_each_linked_issue_once(self):
        rc, doc = self._run([_item("RM-0001", "in-progress", ["705", "706"])],
                            "RM-0001", "done", self._closer)
        self.assertEqual(rc, 0)
        self.assertEqual([c[0] for c in self.calls], ["705", "706"])
        self.assertEqual(doc["items"][0]["status"], "done")

    def test_dropped_closes_too_and_says_dropped_not_fixed(self):
        rc, _ = self._run([_item("RM-0002", "proposed", ["707"])],
                          "RM-0002", "dropped", self._closer)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 1)
        # The reason must distinguish the two: a dropped item's work was NOT done, and an issue
        # closed as "fixed" when nobody fixed it is a false record in the tracker read by people
        # who were not here for the decision.
        #
        # Asserted as a CLAIM rather than a substring. An earlier version of this case asserted
        # that the word "fixed" was absent, and failed against the text "dropped, not fixed" —
        # which is the clearest possible wording. A substring is not the property; the property is
        # what the sentence says.
        reason = self.calls[0][1].lower()
        self.assertIn("dropped", reason)
        self.assertIn("not fixed", reason)
        self.assertNotIn("reached `done`", reason)

    def test_unfinished_transition_closes_nothing(self):
        rc, _ = self._run([_item("RM-0003", "proposed", ["708"])],
                          "RM-0003", "in-progress", self._closer)
        self.assertEqual(rc, 0)
        self.assertEqual(self.calls, [])

    def test_item_with_no_issue_closes_nothing(self):
        rc, _ = self._run([_item("RM-0004", "proposed")], "RM-0004", "done", self._closer)
        self.assertEqual(rc, 0)
        self.assertEqual(self.calls, [])

    def test_already_terminal_does_not_reclose(self):
        rc, _ = self._run([_item("RM-0005", "done", ["709"])], "RM-0005", "done", self._closer)
        self.assertEqual(rc, 0)
        self.assertEqual(self.calls, [])

    def test_status_is_written_even_when_the_closer_fails(self):
        def boom(number, reason, cwd):
            self.calls.append((number, reason))
            raise RuntimeError("no network")

        rc, doc = self._run([_item("RM-0006", "in-progress", ["710"])],
                            "RM-0006", "done", boom)
        # The local fact is recorded regardless. This is the property that keeps an offline
        # session able to finish work.
        self.assertEqual(doc["items"][0]["status"], "done")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()


class IssueClosureTargetTest(unittest.TestCase):
    """The closure must name the repository it acts on, never infer it.

    The incident (2026-09-06, M-00XX): closing two items in `projects/KinNest`'s roadmap from a
    shell sitting in `.claude/skills/roadmap` posted both closure comments onto **Odin's** tracker.
    `gh` resolves its repository from the working directory, the engine passed neither `-R` nor a
    `cwd`, and the process's directory happened to be a different repository. Nothing errored: the
    numbers existed in both trackers.

    The two read-only `gh` calls in this codebase (`reconcile._gh_issues`, `gauntlet`) already pass
    `cwd=root`. This is the one state-changing call, and it was the one that did not.

    `common/security.md` § *Name the Target, Don't Infer It* states the rule, and
    `odin-safety-guard.sh` Layer 1C enforces it — but only for commands issued through the Bash
    tool. A `subprocess.run(["gh", ...])` inside an engine never reaches that hook, so this
    property has to be held here.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.calls = []

    def test_closer_is_told_the_roadmap_s_own_root(self):
        path = _roadmap(self.tmp, [_item("RM-0001", "in-progress", ["705"])])
        args = _Args(path, "RM-0001", "done")

        def closer(number, reason, cwd):
            self.calls.append((number, cwd))

        prev = roadmap_mod.ISSUE_CLOSER
        roadmap_mod.ISSUE_CLOSER = closer
        try:
            rc = roadmap_mod.cmd_set(args)
        finally:
            roadmap_mod.ISSUE_CLOSER = prev

        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 1)
        number, cwd = self.calls[0]
        self.assertEqual(number, "705")
        # The root the roadmap belongs to, not os.getcwd(). Compared by realpath because
        # tempfile hands out /tmp paths that are symlinks on some hosts.
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(self.tmp))
        self.assertNotEqual(os.path.realpath(cwd), os.path.realpath(os.getcwd()))

    def test_gh_close_issue_anchors_the_subprocess_to_that_directory(self):
        """The default closer must hand the directory to `gh`, not merely accept it.

        A signature that takes `cwd` and drops it is the same defect with a passing unit test.
        """
        import subprocess

        seen = {}

        def fake_run(argv, **kwargs):
            seen["argv"] = argv
            seen["cwd"] = kwargs.get("cwd")

            class _R(object):
                returncode = 0
                stdout = ""
                stderr = ""

            return _R()

        prev = subprocess.run
        subprocess.run = fake_run
        try:
            roadmap_mod._gh_close_issue("705", "because", self.tmp)
        finally:
            subprocess.run = prev

        self.assertEqual(seen["cwd"], self.tmp)
        self.assertEqual(seen["argv"][:3], ["gh", "issue", "close"])
