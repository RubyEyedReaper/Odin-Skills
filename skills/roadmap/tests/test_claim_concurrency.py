"""The lost update, replayed.

Two worktrees each hold a full copy of roadmap.json. Agent 1 claims RM-0001 and pushes. Agent 2's
branch was cut before that claim, so its copy still says `proposed`; its own unrelated write
rewrites the whole file, and the rebase resolves in its favour. Agent 1's claim is gone, and
nothing in the diff looks wrong — the file is valid JSON either way.

So the assertion is not "the write succeeded". It is that a status moving BACKWARDS, or evidence
going from recorded to absent, is reported.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import schema  # noqa: E402


def doc(status, evidence=None):
    item = {"id": "RM-0001", "title": "t", "status": status}
    if evidence is not None:
        item["evidence"] = evidence
    return {"slug": "harness", "items": [item]}


class TestClaimRegression(unittest.TestCase):
    def test_forward_move_is_allowed(self):
        self.assertEqual(schema.status_regressions(doc("proposed"), doc("in-progress")), [])

    def test_backward_move_is_reported(self):
        found = schema.status_regressions(doc("in-progress"), doc("proposed"))
        self.assertEqual([f["id"] for f in found], ["RM-0001"])

    def test_done_to_proposed_is_reported(self):
        found = schema.status_regressions(doc("done"), doc("proposed"))
        self.assertEqual([f["id"] for f in found], ["RM-0001"])

    def test_a_new_item_is_not_a_regression(self):
        base = {"slug": "harness", "items": []}
        self.assertEqual(schema.status_regressions(base, doc("proposed")), [])

    def test_a_deleted_item_is_reported(self):
        base = doc("in-progress")
        self.assertEqual(
            [f["id"] for f in schema.status_regressions(base, {"slug": "harness", "items": []})],
            ["RM-0001"],
        )

    def test_cleared_evidence_is_reported_even_when_status_holds(self):
        # The 2026-08-12 incident's own note: the status reverted while the acceptance rewrite
        # survived. A ratchet on `status` alone would not have seen the mirror image of that.
        found = schema.status_regressions(doc("done", "abc1234"), doc("done"))
        self.assertEqual([f["id"] for f in found], ["RM-0001"])

    def test_unchanged_evidence_is_not_a_regression(self):
        self.assertEqual(schema.status_regressions(doc("done", "abc1234"), doc("done", "abc1234")), [])


if __name__ == "__main__":
    unittest.main()
