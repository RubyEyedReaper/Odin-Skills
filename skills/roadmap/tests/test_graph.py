"""Tests for scripts/graph.py (stdlib only) — written before implementation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.graph import (  # noqa: E402
    blockers,
    find_cycle,
    graph_errors,
    is_unblocked,
    next_items,
    topo,
)
from scripts.schema import default_doc  # noqa: E402

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


class TestCycles(unittest.TestCase):
    def test_acyclic_returns_none(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002", deps=["RM-0001"]))
        self.assertIsNone(find_cycle(doc))

    def test_two_node_cycle_detected(self):
        doc = _doc(
            _item("RM-0001", deps=["RM-0002"]),
            _item("RM-0002", deps=["RM-0001"]),
        )
        cycle = find_cycle(doc)
        self.assertIsNotNone(cycle)
        self.assertIn("RM-0001", cycle)
        self.assertIn("RM-0002", cycle)

    def test_cycle_path_is_closed(self):
        doc = _doc(
            _item("RM-0001", deps=["RM-0003"]),
            _item("RM-0002", deps=["RM-0001"]),
            _item("RM-0003", deps=["RM-0002"]),
        )
        cycle = find_cycle(doc)
        self.assertEqual(cycle[0], cycle[-1], "cycle path should return to its start")
        self.assertEqual(len(set(cycle)), 3)

    def test_self_dep_is_a_cycle(self):
        self.assertIsNotNone(find_cycle(_doc(_item("RM-0001", deps=["RM-0001"]))))

    def test_parent_cycle_detected(self):
        doc = _doc(
            _item("RM-0001", parent="RM-0002"),
            _item("RM-0002", parent="RM-0001"),
        )
        self.assertTrue(any("parent" in e for e in graph_errors(doc)))

    def test_graph_errors_empty_when_clean(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002", deps=["RM-0001"]))
        self.assertEqual(graph_errors(doc), [])


class TestTopo(unittest.TestCase):
    def test_topo_respects_dependencies(self):
        doc = _doc(
            _item("RM-0003", deps=["RM-0002"]),
            _item("RM-0001"),
            _item("RM-0002", deps=["RM-0001"]),
        )
        order = topo(doc)
        self.assertLess(order.index("RM-0001"), order.index("RM-0002"))
        self.assertLess(order.index("RM-0002"), order.index("RM-0003"))

    def test_topo_is_deterministic_for_independent_items(self):
        doc = _doc(_item("RM-0003"), _item("RM-0001"), _item("RM-0002"))
        self.assertEqual(topo(doc), topo(doc))
        self.assertEqual(topo(doc), ["RM-0001", "RM-0002", "RM-0003"])

    def test_topo_raises_on_cycle(self):
        doc = _doc(
            _item("RM-0001", deps=["RM-0002"]),
            _item("RM-0002", deps=["RM-0001"]),
        )
        with self.assertRaises(ValueError):
            topo(doc)


class TestBlocking(unittest.TestCase):
    def test_unmet_dep_blocks(self):
        doc = _doc(_item("RM-0001", status="ready"), _item("RM-0002", deps=["RM-0001"]))
        self.assertEqual(blockers(doc, doc["items"][1]), ["RM-0001"])
        self.assertFalse(is_unblocked(doc, doc["items"][1]))

    def test_done_dep_unblocks(self):
        doc = _doc(_item("RM-0001", status="done"), _item("RM-0002", deps=["RM-0001"]))
        self.assertEqual(blockers(doc, doc["items"][1]), [])
        self.assertTrue(is_unblocked(doc, doc["items"][1]))

    def test_dropped_dep_does_not_block(self):
        doc = _doc(
            _item("RM-0001", status="dropped"),
            _item("RM-0002", deps=["RM-0001"]),
        )
        self.assertEqual(blockers(doc, doc["items"][1]), [])

    def test_no_deps_is_unblocked(self):
        doc = _doc(_item("RM-0001"))
        self.assertTrue(is_unblocked(doc, doc["items"][0]))


class TestNextItems(unittest.TestCase):
    def test_excludes_done_dropped_and_in_progress(self):
        doc = _doc(
            _item("RM-0001", status="done"),
            _item("RM-0002", status="dropped"),
            _item("RM-0003", status="in-progress"),
            _item("RM-0004", status="ready"),
        )
        self.assertEqual([i["id"] for i in next_items(doc)], ["RM-0004"])

    def test_excludes_blocked_items(self):
        doc = _doc(
            _item("RM-0001", status="ready"),
            _item("RM-0002", status="ready", deps=["RM-0001"]),
        )
        self.assertEqual([i["id"] for i in next_items(doc)], ["RM-0001"])

    def test_orders_by_tier_then_score_then_id(self):
        doc = _doc(
            _item("RM-0001", tier="later"),
            _item("RM-0002", tier="now", priority={"method": "RICE", "score": 2.0}),
            _item("RM-0003", tier="now", priority={"method": "RICE", "score": 9.0}),
            _item("RM-0004", tier="now"),
        )
        self.assertEqual(
            [i["id"] for i in next_items(doc)],
            ["RM-0003", "RM-0002", "RM-0004", "RM-0001"],
        )

    def test_limit_applies_after_ordering(self):
        doc = _doc(
            _item("RM-0001", tier="later"),
            _item("RM-0002", tier="now"),
        )
        self.assertEqual([i["id"] for i in next_items(doc, limit=1)], ["RM-0002"])

    def test_unscored_item_sorts_after_scored_in_same_tier(self):
        doc = _doc(
            _item("RM-0001", tier="now"),
            _item("RM-0002", tier="now", priority={"method": "RICE", "score": 0.1}),
        )
        self.assertEqual([i["id"] for i in next_items(doc)], ["RM-0002", "RM-0001"])


if __name__ == "__main__":
    unittest.main()
