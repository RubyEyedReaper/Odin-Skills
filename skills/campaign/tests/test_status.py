"""What the manifest may hold, and what a computed status says about it.

Every case asserts an outcome — an exit code, a verdict, bytes on disk. None of them
greps the engine for the branch that was supposed to produce it: reading your own source
back proves the author's intent, never the tool's behaviour.
"""
from __future__ import annotations

import json
import os
import unittest

from ._fixtures import Campaign, git_rc, live_tree_signature, run_cli

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_UNDETERMINED = 2
EXIT_USAGE = 64

LANDED = "landed"


class ValidateRefusesAStoredStatus(unittest.TestCase):
    """Fork 5: the no-stored-status rule is a predicate, not a convention."""

    def test_campaign_level_status_field_is_refused(self):
        with Campaign() as c:
            c.add_worker("harness:RM-0001", "skills/one")
            c.write_roadmap()
            manifest = c.manifest(status="in-progress")
            code, _, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertIn("status", err)

    def test_worker_level_status_field_is_refused(self):
        with Campaign() as c:
            worker = c.add_worker("harness:RM-0001", "skills/one")
            worker["status"] = "done"
            c.write_roadmap()
            manifest = c.manifest()
            code, _, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertIn("skills/one", err)

    def test_copied_roadmap_title_is_refused(self):
        """A copied title is a second source of truth that drifts silently."""
        with Campaign() as c:
            worker = c.add_worker("harness:RM-0001", "skills/one")
            worker["title"] = "Author the campaign skill"
            c.write_roadmap()
            manifest = c.manifest()
            code, _, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertIn("title", err)

    def test_a_plan_only_manifest_validates(self):
        with Campaign() as c:
            c.add_worker("harness:RM-0001", "skills/one")
            c.write_roadmap()
            code, _, _ = run_cli(
                "validate", "--root", c.root, "--manifest", c.manifest()
            )
            self.assertEqual(code, EXIT_OK)

    def test_a_campaign_with_no_workers_is_malformed(self):
        """Nothing examined is never a pass — the zero-collected-tests failure, again."""
        with Campaign() as c:
            c.write_roadmap()
            manifest = c.manifest(waves=[])
            code, _, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertIn("no workers", err)

    def test_an_unreadable_manifest_is_undetermined_not_malformed(self):
        with Campaign() as c:
            c.write_roadmap()
            code, _, _ = run_cli(
                "validate", "--root", c.root,
                "--manifest", os.path.join(c.root, "absent.json"),
            )
            self.assertEqual(code, EXIT_UNDETERMINED)


class StatusIsComputed(unittest.TestCase):
    def test_landed_and_open_rows_are_computed_from_the_two_channels(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker("harness:RM-0002", "skills/two")
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_OK)
            rows = {r["item"]: r for r in json.loads(out)["rows"]}
            self.assertEqual(rows["harness:RM-0001"]["verdict"], "landed")
            self.assertEqual(rows["harness:RM-0002"]["verdict"], "open")

    def test_no_status_is_written_back_into_the_manifest(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            manifest = c.manifest()
            with open(manifest, "rb") as handle:
                before = handle.read()
            run_cli("status", "--root", c.root, "--manifest", manifest, "--json")
            with open(manifest, "rb") as handle:
                self.assertEqual(handle.read(), before)

    def test_a_roadmap_claiming_done_over_absent_content_is_undetermined(self):
        """The channels disagree. Resolving that in favour of either one is a guess."""
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one",
                landed=False, roadmap_status="done", evidence="deadbeef",
            )
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_UNDETERMINED)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], "undetermined")

    def test_an_item_absent_from_the_roadmap_is_undetermined(self):
        with Campaign() as c:
            c.add_worker("harness:RM-0001", "skills/one", in_roadmap=False)
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_UNDETERMINED)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], "undetermined")

    def test_landedness_is_not_decided_by_ancestry(self):
        """The landed fixture is a rebase merge: same patch, different sha.

        `git merge-base --is-ancestor` reports "not merged" for it, so a row reading
        `landed` here can only have come from a content comparison.
        """
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            self.assertNotEqual(
                git_rc(c.root, "merge-base", "--is-ancestor", "skills/one", "origin/main",
                       home=c.home),
                0,
                "fixture is not a rebase merge: ancestry already answers it",
            )
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], "landed")

    def test_the_id_prefix_is_the_roadmap_slug_not_its_memory_class(self):
        """The live roadmap's `scope` is `operational` while its ids read `harness:RM-…`.

        Comparing the prefix against `scope` reads every real id as foreign, which is what
        a dogfood run against the live roadmap reported. The identity rule belongs to the
        roadmap engine and is called, not copied.
        """
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap(scope="operational")
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], LANDED)

    def test_a_declared_slug_wins_over_the_derived_one(self):
        with Campaign() as c:
            c.add_worker(
                "elsewhere:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap(slug="elsewhere")
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], LANDED)

    def test_an_id_naming_another_roadmap_is_undetermined(self):
        """Resolving it here would answer a question about the wrong roadmap."""
        with Campaign() as c:
            c.add_worker(
                "someproject:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, EXIT_UNDETERMINED)
            self.assertIn("someproject", json.loads(out)["rows"][0]["reason"])

    def test_usage_error_exits_64_and_never_0(self):
        code, _, _ = run_cli("status")
        self.assertEqual(code, EXIT_USAGE)


class TheFixturesStayHome(unittest.TestCase):
    """`git -C ""` means the current repository. A root is validated, never assumed."""

    def test_an_empty_root_is_refused_rather_than_run_against_the_live_tree(self):
        from scripts import campaign

        with self.assertRaises(ValueError):
            campaign.git_out("", "status", "--porcelain")

    def test_the_live_working_tree_is_untouched_by_this_suite(self):
        before = live_tree_signature()
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.write_roadmap()
            run_cli("status", "--root", c.root, "--manifest", c.manifest(), "--json")
            run_cli("close", "--root", c.root, "--manifest", c.manifest())
        self.assertEqual(live_tree_signature(), before)


if __name__ == "__main__":
    unittest.main()


class StatusPublishesTheOpenCount(unittest.TestCase):
    """`open` is published here so no caller derives it.

    Three consumers counted rows themselves — `fleet-revive.sh`, `fleet-heartbeat.sh` and this
    module — and two of them counted `verdict != "landed"`, which reads a dropped item as
    outstanding. That disagreement revived a coordinator every twenty minutes for a campaign that
    had closed. The count belongs to the engine that owns the verdicts.
    """

    def test_json_carries_an_open_count(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker("harness:RM-0002", "skills/two")
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, 0)
            doc = json.loads(out)
            self.assertEqual(doc["open"], 1)

    def test_a_dropped_row_is_not_counted_open(self):
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker("harness:RM-0002", "skills/two", roadmap_status="dropped")
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            self.assertEqual(code, 0)
            doc = json.loads(out)
            self.assertEqual(doc["open"], 0)
            self.assertEqual(doc["counts"]["dropped"], 1)
            self.assertEqual(doc["counts"]["landed"], 1)

    def test_an_undetermined_row_is_counted_open(self):
        """The near miss: terminal is `landed` and `dropped`, not `anything but open`. A row nobody
        could determine is outstanding — concluding otherwise is how a check that could not look
        reports a clear result."""
        with Campaign() as c:
            c.add_worker(
                "harness:RM-0001", "skills/one", landed=True, roadmap_status="done"
            )
            c.add_worker("harness:RM-0002", "skills/two", in_roadmap=False)
            c.write_roadmap()
            code, out, _ = run_cli(
                "status", "--root", c.root, "--manifest", c.manifest(), "--json"
            )
            doc = json.loads(out)
            self.assertEqual(doc["counts"]["undetermined"], 1)
            self.assertEqual(doc["open"], 1)
