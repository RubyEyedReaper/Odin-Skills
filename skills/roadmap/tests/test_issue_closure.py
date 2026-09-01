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

    def _closer(self, number, reason):
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
        def boom(number, reason):
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
