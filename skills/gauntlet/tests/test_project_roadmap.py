"""The frontier can be computed for a campaign whose work lives in another repository.

`read_roadmap` built `<root>/.claude/docs/roadmap/roadmap.json` and nothing could change
it, so `frontier --root <a project>` exited 2 — correctly, since the file is not there,
but with no way to say where it is. A gauntlet driving a project campaign could not start.

Two ways in, and the precedence between them is pinned here: an explicit `--roadmap`, and
a campaign manifest that declares its `project`.
"""

import json
import os
import shutil
import tempfile
import unittest

from scripts import gauntlet


def _roadmap(items, slug):
    return {"schema": 1, "scope": "task:Demo", "slug": slug, "items": items}


ITEM = {
    "id": "RM-0001",
    "title": "a project item",
    "kind": "ops",
    "tier": "now",
    "status": "proposed",
    "acceptance": ["it is done when the gate exits 0"],
    "deps": [],
    "links": {},
}


class ProjectRoadmap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gauntlet-project-")
        self.root = os.path.join(self.tmp, "harness")
        self.project = os.path.join(self.root, "projects", "Demo")
        os.makedirs(os.path.join(self.root, ".claude", "docs", "roadmap"))
        os.makedirs(os.path.join(self.project, "docs", "roadmap"))
        with open(os.path.join(self.root, ".claude", "docs", "roadmap", "roadmap.json"),
                  "w", encoding="utf-8") as h:
            json.dump(_roadmap([], "harness"), h)
        self.project_roadmap = os.path.join(self.project, "docs", "roadmap", "roadmap.json")
        with open(self.project_roadmap, "w", encoding="utf-8") as h:
            json.dump(_roadmap([dict(ITEM)], "demo"), h)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_an_explicit_roadmap_path_is_read(self):
        slug, items = gauntlet.read_roadmap(self.root, self.project_roadmap)
        self.assertEqual(slug, "demo")
        self.assertEqual([i["id"] for i in items], ["RM-0001"])

    def test_the_default_is_unchanged(self):
        slug, items = gauntlet.read_roadmap(self.root)
        self.assertEqual(slug, "harness")
        self.assertEqual(items, [])

    def test_a_manifest_declaring_a_project_resolves_its_roadmap(self):
        manifest = os.path.join(self.root, "campaign.json")
        with open(manifest, "w", encoding="utf-8") as h:
            json.dump({"campaign": "demo", "objective": "o",
                       "project": "projects/Demo",
                       "waves": [{"wave": 1, "workers": []}]}, h)
        self.assertEqual(
            gauntlet.roadmap_path_for(self.root, manifest),
            os.path.join(self.project, "docs", "roadmap", "roadmap.json"),
        )

    def test_a_manifest_with_no_project_resolves_the_default(self):
        manifest = os.path.join(self.root, "campaign.json")
        with open(manifest, "w", encoding="utf-8") as h:
            json.dump({"campaign": "demo", "objective": "o",
                       "waves": [{"wave": 1, "workers": []}]}, h)
        self.assertEqual(
            gauntlet.roadmap_path_for(self.root, manifest),
            os.path.join(self.root, ".claude", "docs", "roadmap", "roadmap.json"),
        )

    def test_a_declared_project_that_does_not_resolve_is_undetermined(self):
        manifest = os.path.join(self.root, "campaign.json")
        with open(manifest, "w", encoding="utf-8") as h:
            json.dump({"campaign": "demo", "objective": "o",
                       "project": "projects/Nope",
                       "waves": [{"wave": 1, "workers": []}]}, h)
        with self.assertRaises(gauntlet.Undetermined) as caught:
            gauntlet.roadmap_path_for(self.root, manifest)
        self.assertIn("projects/Nope", str(caught.exception))

    def test_an_unreadable_manifest_is_undetermined_not_the_default(self):
        with self.assertRaises(gauntlet.Undetermined):
            gauntlet.roadmap_path_for(self.root, os.path.join(self.root, "gone.json"))


if __name__ == "__main__":
    unittest.main()


class TrackerFollowsTheProject(unittest.TestCase):
    """The tracker reads the repository the work is in, not the one the manifest is in.

    A frontier that takes its roadmap from the project and its issues from the harness
    mixes two backlogs and looks entirely plausible — measured once at 165 project items
    beside 96 issues from the wrong tracker.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gauntlet-tracker-")
        self.root = os.path.join(self.tmp, "harness")
        self.project = os.path.join(self.root, "projects", "Demo")
        os.makedirs(os.path.join(self.root, ".claude", "docs", "roadmap"))
        os.makedirs(os.path.join(self.project, "docs", "roadmap"))
        with open(os.path.join(self.root, ".claude", "docs", "roadmap", "roadmap.json"),
                  "w", encoding="utf-8") as h:
            json.dump(_roadmap([], "harness"), h)
        with open(os.path.join(self.project, "docs", "roadmap", "roadmap.json"),
                  "w", encoding="utf-8") as h:
            json.dump(_roadmap([dict(ITEM)], "demo"), h)
        self.manifest = os.path.join(self.root, "campaign.json")
        with open(self.manifest, "w", encoding="utf-8") as h:
            json.dump({"campaign": "demo", "objective": "o", "project": "projects/Demo",
                       "waves": [{"wave": 1, "workers": []}]}, h)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_tracker_is_read_in_the_project_root(self):
        seen = []
        original = gauntlet._run

        def fake(argv, cwd=None, **kw):
            seen.append(cwd)
            return 0, "[]", ""

        gauntlet._run = fake
        try:
            gauntlet.build_frontier(
                self.root, want_tracker=True,
                roadmap_path=gauntlet.roadmap_path_for(self.root, self.manifest),
                work_root=gauntlet.project_root_for(self.root, self.manifest),
            )
        finally:
            gauntlet._run = original
        self.assertIn(self.project, seen)
        self.assertNotIn(self.root, seen)

    def test_with_no_project_the_tracker_is_read_in_the_root(self):
        seen = []
        original = gauntlet._run

        def fake(argv, cwd=None, **kw):
            seen.append(cwd)
            return 0, "[]", ""

        gauntlet._run = fake
        try:
            gauntlet.build_frontier(self.root, want_tracker=True)
        finally:
            gauntlet._run = original
        self.assertIn(self.root, seen)
