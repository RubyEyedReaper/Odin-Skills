"""Tests for scripts/graph.waves — parallel execution layers (stdlib only).

Waves are *computed* from the dependency graph, never stored (DEC-0001).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.graph import next_items, waves  # noqa: E402
from scripts.schema import default_doc  # noqa: E402

TODAY = "2026-08-08"


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


def _ids(layers):
    return [[i["id"] for i in layer] for layer in layers]


class TestWaveLayering(unittest.TestCase):
    def test_diamond_yields_three_waves(self):
        doc = _doc(
            _item("RM-0001"),
            _item("RM-0002", deps=["RM-0001"]),
            _item("RM-0003", deps=["RM-0001"]),
            _item("RM-0004", deps=["RM-0002", "RM-0003"]),
        )
        self.assertEqual(
            _ids(waves(doc)),
            [["RM-0001"], ["RM-0002", "RM-0003"], ["RM-0004"]],
        )

    def test_wave_zero_equals_next_items(self):
        doc = _doc(
            _item("RM-0001"),
            _item("RM-0002"),
            _item("RM-0003", deps=["RM-0001"]),
        )
        self.assertEqual(
            [i["id"] for i in waves(doc)[0]],
            [i["id"] for i in next_items(doc)],
        )

    def test_done_dep_does_not_push_an_item_out_of_wave_zero(self):
        doc = _doc(
            _item("RM-0001", status="done"),
            _item("RM-0002", deps=["RM-0001"]),
        )
        self.assertEqual(_ids(waves(doc)), [["RM-0002"]])

    def test_independent_items_share_one_wave(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002"), _item("RM-0003"))
        self.assertEqual(len(waves(doc)), 1)
        self.assertEqual(len(waves(doc)[0]), 3)

    def test_limit_truncates_waves(self):
        doc = _doc(
            _item("RM-0001"),
            _item("RM-0002", deps=["RM-0001"]),
            _item("RM-0003", deps=["RM-0002"]),
        )
        self.assertEqual(_ids(waves(doc, limit=2)), [["RM-0001"], ["RM-0002"]])

    def test_layer_is_ordered_by_tier_then_score(self):
        doc = _doc(
            _item("RM-0001", tier="later"),
            _item("RM-0002", tier="now"),
            _item("RM-0003", tier="next", priority={"method": "RICE", "score": 9.0}),
        )
        self.assertEqual(_ids(waves(doc)), [["RM-0002", "RM-0003", "RM-0001"]])


class TestWaveExclusions(unittest.TestCase):
    def test_in_progress_item_is_not_a_wave_member(self):
        doc = _doc(_item("RM-0001", status="in-progress"), _item("RM-0002"))
        self.assertEqual(_ids(waves(doc)), [["RM-0002"]])

    def test_item_waiting_on_in_flight_work_is_not_schedulable(self):
        """A dep that is in-progress is unmet but cannot be placed in a wave."""
        doc = _doc(
            _item("RM-0001", status="in-progress"),
            _item("RM-0002", deps=["RM-0001"]),
        )
        self.assertEqual(_ids(waves(doc)), [])

    def test_deferred_reports_what_waves_left_out(self):
        doc = _doc(
            _item("RM-0001", status="in-progress"),
            _item("RM-0002", deps=["RM-0001"]),
            _item("RM-0003"),
        )
        layers, deferred = waves(doc, with_deferred=True)
        self.assertEqual(_ids(layers), [["RM-0003"]])
        self.assertEqual([i["id"] for i in deferred], ["RM-0002"])

    def test_dropped_dep_counts_as_satisfied(self):
        doc = _doc(
            _item("RM-0001", status="dropped"),
            _item("RM-0002", deps=["RM-0001"]),
        )
        self.assertEqual(_ids(waves(doc)), [["RM-0002"]])

    def test_empty_roadmap_yields_no_waves(self):
        self.assertEqual(waves(_doc()), [])


class TestWaveErrors(unittest.TestCase):
    def test_cycle_raises(self):
        doc = _doc(
            _item("RM-0001", deps=["RM-0002"]),
            _item("RM-0002", deps=["RM-0001"]),
        )
        with self.assertRaises(ValueError):
            waves(doc)


if __name__ == "__main__":
    unittest.main()
