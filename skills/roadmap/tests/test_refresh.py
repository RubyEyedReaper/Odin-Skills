"""Generated files stay fresh: read commands re-render stale output.

ROADMAP.md and graph.* are artifacts, never sources of truth — so a project
reading the roadmap must never be shown a stale rendering.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import render as render_mod  # noqa: E402
from scripts.roadmap import main  # noqa: E402

TODAY = "2026-08-08"


class RoadmapFixture:
    def __init__(self, tmp):
        self.json_path = os.path.join(tmp, "docs", "roadmap", "roadmap.json")
        self._run("init", "--scope", "task:Demo")
        self._run("add", "--title", "First thing", "--kind", "feature")

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--path", self.json_path, "--today", TODAY, *argv])
        return code, out.getvalue(), err.getvalue()

    run = _run

    @property
    def md_path(self):
        return render_mod.paths_for(self.json_path)["md"]

    def read_md(self):
        with open(self.md_path, encoding="utf-8") as fh:
            return fh.read()

    def corrupt_md(self):
        with open(self.md_path, "w", encoding="utf-8") as fh:
            fh.write("# stale hand-written content\n")

    def add_item_behind_the_cli(self, title):
        """Mutate roadmap.json directly — the shape of an out-of-band edit."""
        with open(self.json_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        item = dict(doc["items"][0])
        item["id"] = "RM-9001"
        item["title"] = title
        doc["items"].append(item)
        with open(self.json_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)


class TestReadCommandsRefresh(unittest.TestCase):
    def test_next_rerenders_stale_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            fixture.corrupt_md()
            code, _, err = fixture.run("next")
            self.assertEqual(code, 0)
            self.assertIn("re-rendered", err)
            self.assertIn("First thing", fixture.read_md())

    def test_waves_rerenders_stale_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            fixture.corrupt_md()
            fixture.run("waves")
            self.assertIn("First thing", fixture.read_md())

    def test_out_of_band_json_edit_shows_up_in_the_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            fixture.add_item_behind_the_cli("Snuck in")
            fixture.run("next")
            self.assertIn("Snuck in", fixture.read_md())

    def test_fresh_roadmap_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            before = os.path.getmtime(fixture.md_path)
            _, _, err = fixture.run("next")
            self.assertNotIn("re-rendered", err)
            self.assertEqual(before, os.path.getmtime(fixture.md_path))

    def test_no_render_flag_leaves_stale_output_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            fixture.corrupt_md()
            fixture.run("--no-render", "next")
            self.assertEqual(fixture.read_md(), "# stale hand-written content\n")

    def test_validate_still_reports_staleness_rather_than_hiding_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapFixture(tmp)
            fixture.corrupt_md()
            code, _, err = fixture.run("validate")
            self.assertEqual(code, 1)
            self.assertIn("stale", err)


if __name__ == "__main__":
    unittest.main()
