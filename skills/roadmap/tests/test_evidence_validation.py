"""`--evidence` must name a commit, because since ADR-0136 it is read by people, not just stored.

harness:RM-0471, issue #853. Observed on 2026-09-01 while closing harness:RM-0470:

    $ python3 -m scripts.roadmap --path … set harness:RM-0470 --status done --evidence PENDING
    updated harness:RM-0470

The item went `done`, and the engine closed the linked issue and posted a comment citing `PENDING`
as the evidence. The work had not landed at that moment.

Two things make this worth refusing rather than noting:

1. **The evidence field is the audit trail.** `campaign status` reads "done with a landed sha" as
   one of its three channels. A placeholder there produces a row that reads `landed` to a human and
   can be checked by nothing.
2. **The closure is outward-facing.** Before ADR-0136 a bad value sat in a local JSON file. It now
   closes a tracker issue and writes a comment that anybody reading the repository can see.

**Refusal, not a block-list.** `PENDING`, `TODO`, `TBD` and `-` are the placeholders someone
happened to think of; the next one nobody thought of is exactly as damaging and would pass. The
predicate is what the field is *for* — `git rev-parse --verify <value>^{commit}` in the repository
the roadmap belongs to.

**Three outcomes, not two.** A roadmap whose root is not a git repository is a real configuration,
and "could not look" is not "looked and found nothing" — answering `not a commit` there would be a
claim the tool cannot support. That case is accepted with the limit stated on stderr, so the notice
is visible to whoever reads the run rather than being a silent pass.

Every fixture builds a real repository with a real commit. Resolving a sha is precisely the
behaviour under test, so a mocked resolver would assert this file's own picture of git.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import roadmap as roadmap_mod  # noqa: E402


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", root, "-c", "user.email=fixture@example.invalid",
         "-c", "user.name=fixture", "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True,
    )


def _roadmap(root, items):
    d = os.path.join(root, "docs", "roadmap")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "roadmap.json")
    with open(p, "w") as fh:
        json.dump({"schema": 1, "scope": "harness", "updated": "2026-09-01",
                   "items": items}, fh)
    return p


def _item(id_, status="in-progress"):
    return {"id": id_, "title": "fixture %s" % id_, "kind": "infra", "tier": "next",
            "status": status, "created": "2026-09-01", "updated": "2026-09-01"}


class _Args(object):
    """The attribute surface `cmd_set` reads, as a namespace rather than argparse, so a field the
    engine starts reading tomorrow fails loudly here instead of silently defaulting."""

    def __init__(self, path, id_, status, evidence):
        self.path = path
        self.root = None
        self.id = id_
        self.status = status
        self.evidence = evidence
        self.today = "2026-09-01"
        self.force = True
        for f in ("title", "kind", "tier", "deps", "parent", "phase", "owner_skill",
                  "acceptance", "score", "method", "notes", "prd", "plan",
                  "adr", "issues", "files"):
            setattr(self, f, None)


class EvidenceValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.closed = []
        # The closer is a seam: a test that called the real `gh` would file network traffic against
        # a live tracker from a unit suite (`ci-gate/fixture-reads-ambient-state`).
        self._prev_closer = roadmap_mod.ISSUE_CLOSER
        roadmap_mod.ISSUE_CLOSER = lambda number, reason: self.closed.append(number)
        self.addCleanup(self._restore)

    def _restore(self):
        roadmap_mod.ISSUE_CLOSER = self._prev_closer

    def _repo(self):
        """A repository with one real commit, and the sha it produced."""
        root = os.path.join(self.tmp, "repo")
        os.makedirs(root)
        _git(root, "init", "-q", "-b", "main")
        with open(os.path.join(root, "README.md"), "w") as fh:
            fh.write("fixture\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "base")
        sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        return root, sha

    def _set(self, path, evidence, id_="RM-0001", status="done"):
        rc = roadmap_mod.cmd_set(_Args(path, id_, status, evidence))
        with open(path) as fh:
            return rc, json.load(fh)["items"][0]

    # --- the defect -----------------------------------------------------------------------

    def test_a_placeholder_is_refused_and_nothing_is_written(self):
        root, _ = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, "PENDING")
        self.assertNotEqual(rc, 0)
        # The status must NOT have moved. A refusal that still records `done` leaves the exact row
        # the issue is about, minus the evidence that would have explained it.
        self.assertEqual(item["status"], "in-progress")
        self.assertIsNone(item.get("evidence"))

    def test_a_refused_evidence_closes_no_issue(self):
        """The outward-facing half. Before ADR-0136 a bad value sat in a local file; it now closes
        a tracker issue and comments. A refusal that had already closed the issue would have done
        the damage the check exists to prevent."""
        root, _ = self._repo()
        path = _roadmap(root, [dict(_item("RM-0001"), links={"issues": ["851"]})])
        rc, _ = self._set(path, "PENDING")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.closed, [])

    def test_an_unknown_placeholder_is_refused_too(self):
        """The case a block-list would miss. Nothing about `LATER` is on anybody's list of
        placeholder words, and it is exactly as unresolvable as `PENDING`."""
        root, _ = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, "LATER")
        self.assertNotEqual(rc, 0)
        self.assertEqual(item["status"], "in-progress")

    # --- the negative control -------------------------------------------------------------

    def test_a_real_sha_still_passes(self):
        root, sha = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, sha)
        self.assertEqual(rc, 0)
        self.assertEqual(item["status"], "done")
        self.assertEqual(item["evidence"], sha)

    def test_a_short_sha_still_passes(self):
        """The form a human actually types, and the form the issue names."""
        root, sha = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, sha[:8])
        self.assertEqual(rc, 0)
        self.assertEqual(item["evidence"], sha[:8])

    def test_no_evidence_at_all_is_unaffected(self):
        """Most `set` calls carry no evidence. A check that made those fail would be a worse
        defect than the one it fixes."""
        root, _ = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, None, status="ready")
        self.assertEqual(rc, 0)
        self.assertEqual(item["status"], "ready")

    # --- could not look ≠ looked and found nothing ----------------------------------------

    def test_a_non_git_root_is_a_distinct_outcome_and_says_so(self):
        root = os.path.join(self.tmp, "notarepo")
        os.makedirs(root)
        path = _roadmap(root, [_item("RM-0001")])
        rc, item = self._set(path, "PENDING")
        self.assertEqual(rc, 0, "a roadmap outside a repository must stay usable")
        self.assertEqual(item["evidence"], "PENDING")

    def test_the_non_git_outcome_is_reported_not_silent(self):
        """An unobtainable answer is never read as a pass without saying so. Asserted on the
        function that decides, so the message is a property of the check rather than of whichever
        caller happens to print it."""
        root = os.path.join(self.tmp, "notarepo2")
        os.makedirs(root)
        verdict, detail = roadmap_mod.evidence_verdict(_roadmap(root, [_item("RM-0001")]),
                                                       "PENDING")
        self.assertEqual(verdict, "unverifiable")
        self.assertTrue(detail, "the unverifiable outcome must name what could not be determined")

    def test_the_three_verdicts_are_distinct(self):
        root, sha = self._repo()
        path = _roadmap(root, [_item("RM-0001")])
        self.assertEqual(roadmap_mod.evidence_verdict(path, sha)[0], "commit")
        self.assertEqual(roadmap_mod.evidence_verdict(path, "PENDING")[0], "not-a-commit")


if __name__ == "__main__":
    unittest.main()
