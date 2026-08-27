"""Close, which is the part with teeth.

Three refusals matter and they are different from each other: an item that is not done,
an item whose landedness could not be determined, and a remote that could not be reached
at all. The third must never collapse into "nothing is blocking" — a campaign declared
complete on the strength of a check that could not look is the failure the whole
mechanism exists to prevent.
"""
from __future__ import annotations

import json
import unittest

from ._fixtures import Campaign, run_cli

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_UNDETERMINED = 2


class CloseRefuses(unittest.TestCase):
    def test_an_unlanded_item_blocks_the_close_and_is_named(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker("harness:RM-0002", "skills/two")
            c.write_roadmap()
            code, out, err = run_cli(
                "close", "--root", c.root, "--manifest", c.manifest()
            )
            self.assertEqual(code, EXIT_BLOCKED)
            report = out + err
            self.assertIn("harness:RM-0002", report)
            self.assertIn("skills/two", report)

    def test_an_item_done_without_a_landed_sha_blocks_the_close(self):
        """`done` with no evidence is a claim with nothing behind it."""
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one",
                landed=True, roadmap_status="done", evidence="",
            )
            c.write_roadmap()
            code, out, err = run_cli(
                "close", "--root", c.root, "--manifest", c.manifest()
            )
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertIn("harness:RM-0001", out + err)

    def test_an_unreachable_remote_exits_2_rather_than_permitting_a_green_close(self):
        """The exit code is the assertion. Non-zero would not distinguish this from a
        blocker list, and that distinction is the entire point."""
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            manifest = c.manifest()
            c.unreachable_remote()
            code, out, err = run_cli("close", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_UNDETERMINED)
            self.assertIn("undetermined", (out + err).lower())

    def test_undetermined_outranks_a_named_blocker(self):
        """A run that names blockers *and* failed to look has an incomplete list."""
        with Campaign() as c:
            c.add_worker("harness:RM-0001", "skills/one")
            c.add_worker("harness:RM-0002", "skills/two", in_roadmap=False)
            c.write_roadmap()
            code, _, _ = run_cli("close", "--root", c.root, "--manifest", c.manifest())
            self.assertEqual(code, EXIT_UNDETERMINED)

    def test_a_manifest_that_stores_a_status_cannot_be_closed_against(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            manifest = c.manifest(status="complete")
            code, _, _ = run_cli("close", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_BLOCKED)


class ClosePermits(unittest.TestCase):
    def test_every_item_landed_permits_the_close(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker(
                "harness:RM-0002", "skills/two", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            code, out, _ = run_cli(
                "close", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(out)["verdict"], "closeable")

    def test_close_hands_residue_over_and_deletes_nothing(self):
        """Residue is listed for `tidy`. Nothing here removes a branch or a worktree."""
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            manifest = c.manifest()
            with open(manifest, "rb") as handle:
                before = handle.read()
            code, out, _ = run_cli(
                "close", "--root", c.root, "--manifest", manifest, "--json"
            )
            self.assertEqual(code, EXIT_OK)
            residue = json.loads(out)["residue"]
            self.assertIn("skills/one", json.dumps(residue))
            with open(manifest, "rb") as handle:
                self.assertEqual(handle.read(), before)
            self.assertEqual(
                c._git("rev-parse", "--verify", "skills/one", check=False) != "", True
            )


if __name__ == "__main__":
    unittest.main()
