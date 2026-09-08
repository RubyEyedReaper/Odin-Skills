"""A campaign whose work lives in a nested repository.

`--root` names the repository the manifest and the harness live in. A campaign's *work*
may live somewhere else — `projects/<slug>`, its own git repository with its own remote
and its own `docs/roadmap/roadmap.json` and no `.claude/` above it. Before this, no
`--root` value reached that roadmap and landedness was computed in the wrong repository,
so every row came back `undetermined` and `close` could never exit 0.

The manifest's `project` key says where the work is. These cases pin what it must do, and
— the half that matters — what it must refuse.
"""
from __future__ import annotations

import json
import os
import unittest

from ._fixtures import Campaign, run_cli, live_tree_signature


class ProjectResolution(unittest.TestCase):
    def test_project_roadmap_is_resolved_and_landedness_is_computed_there(self):
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one", landed=True,
                                 roadmap_status="done")
            c.add_project_worker("demo:RM-0002", "demo/two")
            c.write_project_roadmap()
            c.write_roadmap()          # the harness roadmap, deliberately unrelated
            manifest = c.manifest(
                project=c.project_rel,
                waves=[{"wave": 1, "workers": c.project_workers}],
            )
            code, out, err = run_cli("status", "--root", c.root,
                                     "--manifest", manifest, "--json")
            self.assertEqual(code, 0, err)
            doc = json.loads(out)
            by = {r["item"]: r["verdict"] for r in doc["rows"]}
            self.assertEqual(by["demo:RM-0001"], "landed", doc)
            self.assertEqual(by["demo:RM-0002"], "open", doc)

    def test_close_can_reach_zero_for_a_project_campaign(self):
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one", landed=True,
                                 roadmap_status="done")
            c.write_project_roadmap()
            c.write_roadmap()
            manifest = c.manifest(
                project=c.project_rel,
                waves=[{"wave": 1, "workers": c.project_workers}],
            )
            code, out, err = run_cli("close", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, 0, err + out)

    def test_an_unresolvable_project_is_undetermined_and_names_the_path(self):
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one")
            c.write_project_roadmap()
            c.write_roadmap()
            manifest = c.manifest(
                project="projects/Nope",
                waves=[{"wave": 1, "workers": c.project_workers}],
            )
            code, out, err = run_cli("status", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, 2, out + err)
            self.assertIn("projects/Nope", err + out)

    def test_a_manifest_with_no_project_is_unchanged(self):
        with Campaign() as c:
            c.add_worker("fixture:RM-0001", "fix/one", landed=True,
                         roadmap_status="done")
            c.write_roadmap(slug="fixture")
            manifest = c.manifest()
            code, out, err = run_cli("status", "--root", c.root,
                                     "--manifest", manifest, "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], "landed")

    def test_the_roadmap_flag_still_beats_the_manifest_key(self):
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one", landed=True,
                                 roadmap_status="done")
            project_roadmap = c.write_project_roadmap()
            c.write_roadmap()
            manifest = c.manifest(
                project=c.project_rel,
                waves=[{"wave": 1, "workers": c.project_workers}],
            )
            # An explicit --roadmap wins; pointing it at a file that is not there is the
            # cheapest proof the flag was consulted at all.
            gone = os.path.join(c.tmp, "not-a-roadmap.json")
            code, out, err = run_cli("status", "--root", c.root,
                                     "--manifest", manifest, "--roadmap", gone)
            self.assertEqual(code, 2, out + err)
            self.assertIn("not-a-roadmap.json", err + out)
            # …and with the real one it agrees with the manifest's own resolution.
            code, out, err = run_cli("status", "--root", c.root, "--manifest", manifest,
                                     "--roadmap", project_roadmap, "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["rows"][0]["verdict"], "landed")

    def test_validate_accepts_project_and_still_refuses_a_status(self):
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one")
            c.write_project_roadmap()
            manifest = c.manifest(
                project=c.project_rel,
                waves=[{"wave": 1, "workers": c.project_workers}],
            )
            code, out, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, 0, err + out)

            with open(manifest, encoding="utf-8") as handle:
                doc = json.load(handle)
            doc["status"] = "in-progress"
            with open(manifest, "w", encoding="utf-8") as handle:
                json.dump(doc, handle)
            code, out, err = run_cli("validate", "--root", c.root, "--manifest", manifest)
            self.assertEqual(code, 1, out + err)


class TheSuiteStayedHome(unittest.TestCase):
    def test_the_live_tree_is_untouched(self):
        before = live_tree_signature()
        with Campaign() as c:
            c.nest_project()
            c.add_project_worker("demo:RM-0001", "demo/one")
            c.write_project_roadmap()
        self.assertEqual(before, live_tree_signature())


if __name__ == "__main__":
    unittest.main()
