"""Tests for scripts/render.py (stdlib only) — written before implementation."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.render import (  # noqa: E402
    BANNER_PREFIX,
    md_hash,
    md_is_stale,
    render_all,
    render_dot,
    render_md,
)
from scripts.schema import content_hash, default_doc, paths_for, save  # noqa: E402

TODAY = "2026-07-29"


def _item(item_id, **kw):
    base = {
        "id": item_id,
        "title": "Item " + item_id,
        "kind": "feature",
        "status": "proposed",
        "tier": "next",
        "deps": [],
        "parent": None,
        "phase": None,
        "priority": None,
        "owner_skill": None,
        "acceptance": [],
        "links": {"prd": None, "plan": None, "adr": None, "issues": [], "files": []},
        "created": TODAY,
        "updated": TODAY,
        "completed": None,
        "evidence": None,
        "notes": "",
    }
    base.update(kw)
    return base


def _doc(*items):
    doc = default_doc("task:Demo", today=TODAY)
    doc["items"] = list(items)
    return doc


class TestDot(unittest.TestCase):
    def test_emits_digraph_with_left_right_rank(self):
        dot = render_dot(_doc(_item("RM-0001")))
        self.assertIn("digraph roadmap", dot)
        self.assertIn("rankdir=LR", dot)

    def test_nodes_and_edges_present(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002", deps=["RM-0001"]))
        dot = render_dot(doc)
        self.assertIn('"RM-0001"', dot)
        self.assertIn('"RM-0001" -> "RM-0002"', dot)

    def test_quotes_in_title_are_escaped(self):
        dot = render_dot(_doc(_item("RM-0001", title='The "big" one')))
        self.assertNotIn('"The "big" one', dot)
        self.assertIn(r"\"big\"", dot)

    def test_newlines_in_title_do_not_break_label(self):
        dot = render_dot(_doc(_item("RM-0001", title="line1\nline2")))
        for line in dot.splitlines():
            self.assertLessEqual(line.count('"') % 2, 0, "unbalanced quotes: " + line)

    def test_parent_becomes_cluster(self):
        doc = _doc(
            _item("RM-0001", title="Auth"),
            _item("RM-0002", title="Login", parent="RM-0001"),
        )
        self.assertIn("subgraph cluster_RM_0001", render_dot(doc))

    def test_status_colours_applied(self):
        dot = render_dot(_doc(_item("RM-0001", status="done")))
        self.assertIn("fillcolor", dot)


class TestMarkdown(unittest.TestCase):
    def test_banner_carries_source_hash(self):
        doc = _doc(_item("RM-0001"))
        md = render_md(doc, "docs/roadmap/graph.svg")
        self.assertTrue(md.startswith(BANNER_PREFIX))
        self.assertIn(content_hash(doc), md.splitlines()[0])

    def test_banner_warns_against_hand_editing(self):
        md = render_md(_doc(_item("RM-0001")), "docs/roadmap/graph.svg")
        self.assertIn("do not edit by hand", md.splitlines()[0])

    def test_next_up_section_lists_unblocked_item(self):
        doc = _doc(
            _item("RM-0001", status="ready", title="Signup page", kind="page"),
            _item("RM-0002", status="ready", deps=["RM-0001"]),
        )
        md = render_md(doc, "docs/roadmap/graph.svg")
        self.assertIn("Signup page", md)
        self.assertIn("RM-0001", md)

    def test_graph_image_embedded(self):
        md = render_md(_doc(_item("RM-0001")), "docs/roadmap/graph.svg")
        self.assertIn("docs/roadmap/graph.svg", md)

    def test_blocked_item_shows_its_blockers(self):
        doc = _doc(
            _item("RM-0001", status="ready"),
            _item("RM-0002", status="ready", deps=["RM-0001"]),
        )
        md = render_md(doc, "docs/roadmap/graph.svg")
        self.assertIn("RM-0002", md)

    def test_md_hash_roundtrips(self):
        doc = _doc(_item("RM-0001"))
        md = render_md(doc, "docs/roadmap/graph.svg")
        self.assertEqual(md_hash(md), content_hash(doc))


class TestFreshness(unittest.TestCase):
    def _write(self, tmp, doc):
        path = os.path.join(tmp, "projects", "Demo", "docs", "roadmap", "roadmap.json")
        save(path, doc)
        return path

    def test_fresh_render_is_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = _doc(_item("RM-0001"))
            path = self._write(tmp, doc)
            render_all(path)
            self.assertFalse(md_is_stale(path))

    def test_md_missing_counts_as_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, _doc(_item("RM-0001")))
            self.assertTrue(md_is_stale(path))

    def test_json_change_makes_md_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = _doc(_item("RM-0001"))
            path = self._write(tmp, doc)
            render_all(path)
            doc["items"].append(_item("RM-0002"))
            save(path, doc)
            self.assertTrue(md_is_stale(path))

    def test_hand_edited_md_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = _doc(_item("RM-0001"))
            path = self._write(tmp, doc)
            render_all(path)
            md_path = paths_for(path)["md"]
            with open(md_path, "a", encoding="utf-8") as fh:
                fh.write("\nsneaky manual edit\n")
            self.assertTrue(md_is_stale(path))


class TestRenderAll(unittest.TestCase):
    def test_writes_md_and_dot_at_expected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "projects", "Demo", "docs", "roadmap", "roadmap.json")
            save(path, _doc(_item("RM-0001")))
            written = render_all(path)
            self.assertTrue(os.path.exists(written["md"]))
            self.assertTrue(os.path.exists(written["dot"]))
            self.assertTrue(written["md"].endswith(os.path.join("Demo", "ROADMAP.md")))

    def test_svg_absence_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "projects", "Demo", "docs", "roadmap", "roadmap.json")
            save(path, _doc(_item("RM-0001")))
            written = render_all(path, dot_binary="definitely-not-a-real-binary")
            self.assertIsNone(written["svg"])
            self.assertTrue(os.path.exists(written["dot"]))


if __name__ == "__main__":
    unittest.main()
