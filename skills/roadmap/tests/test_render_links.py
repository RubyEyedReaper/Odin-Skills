"""A rendered plan link must resolve from the rendered file's own directory (stdlib only).

`links.plan` is stored relative to the roadmap's root, because that is what every other
consumer resolves against — the plan gate's search paths, `reconcile`'s file globs, a human
running `cat`. A markdown link, though, is resolved relative to the file it is written in,
both by whatever renders it and by `.claude/scripts/doc-reference-check.sh`.

For the harness layout those two differ by three directories: root-relative
`.claude/docs/plans/x.md` written into `.claude/docs/roadmap/ROADMAP.md` points at
`.claude/docs/roadmap/.claude/docs/plans/x.md`, which never exists. The link renders fine and
404s on click — the exact failure doc-reference-check.sh exists to catch, produced by a
generator rather than by a typo. The svg and json links in the same document were already
rebased for this reason; the plan link was not.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.render import expected_md  # noqa: E402
from scripts.schema import paths_for  # noqa: E402


def _doc(plan_rel):
    return {
        "version": 1,
        "scope": "harness",
        "updated": "2026-08-17",
        "last_reconcile": None,
        "items": [
            {
                "id": "RM-0001",
                "title": "An item whose plan link has to resolve",
                "kind": "ops",
                "status": "ready",
                "tier": "now",
                "deps": [],
                "acceptance": [],
                "links": {"plan": plan_rel, "prd": None, "adr": None, "issues": [], "files": []},
                "created": "2026-08-17",
                "updated": "2026-08-17",
                "completed": None,
                "evidence": None,
                "notes": None,
                "owner_skill": None,
                "parent": None,
                "phase": None,
                "priority": None,
            }
        ],
    }


def _write(json_path, doc):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# a plan\n")


def _plan_links(markdown):
    links, marker = [], "[plan]("
    for line in markdown.splitlines():
        start = line.find(marker)
        while start != -1:
            end = line.find(")", start)
            links.append(line[start + len(marker):end])
            start = line.find(marker, end)
    return links


class PlanLinkResolution(unittest.TestCase):
    def test_harness_layout_link_resolves_from_the_md_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_rel = ".claude/docs/plans/2026-08-17-a-plan.md"
            json_path = os.path.join(tmp, ".claude", "docs", "roadmap", "roadmap.json")
            doc = _doc(plan_rel)
            _write(json_path, doc)
            _touch(os.path.join(tmp, plan_rel))

            links = _plan_links(expected_md(doc, json_path))
            self.assertTrue(links, "the rendered roadmap carries no plan link at all")

            md_dir = os.path.dirname(paths_for(json_path)["md"])
            for link in links:
                self.assertTrue(
                    os.path.exists(os.path.join(md_dir, link)),
                    "rendered link %r does not resolve from %s (would 404)" % (link, md_dir),
                )

    def test_project_layout_link_resolves_from_the_md_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_rel = "docs/plans/a-plan.md"
            json_path = os.path.join(tmp, "docs", "roadmap", "roadmap.json")
            doc = _doc(plan_rel)
            _write(json_path, doc)
            _touch(os.path.join(tmp, plan_rel))

            md_dir = os.path.dirname(paths_for(json_path)["md"])
            for link in _plan_links(expected_md(doc, json_path)):
                self.assertTrue(
                    os.path.exists(os.path.join(md_dir, link)),
                    "rendered link %r does not resolve from %s" % (link, md_dir),
                )

    def test_a_url_plan_link_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = "https://example.com/plan.md"
            json_path = os.path.join(tmp, ".claude", "docs", "roadmap", "roadmap.json")
            doc = _doc(url)
            _write(json_path, doc)

            self.assertIn(url, _plan_links(expected_md(doc, json_path)),
                          "a URL must survive rebasing untouched")


if __name__ == "__main__":
    unittest.main()
