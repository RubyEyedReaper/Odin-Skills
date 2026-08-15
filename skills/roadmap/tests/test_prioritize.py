"""Tests for scripts/prioritize.py — roadmap <-> decision-matrix hand-off.

The roadmap owns its own file in both directions (DEC-0001 fork 5): it exports a
decision spec for `decision-matrix` to score, and ingests the result back into
`priority`. The decision engine never learns the roadmap format.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.prioritize import dec_id_from_path, export_spec, ingest  # noqa: E402
from scripts.schema import default_doc  # noqa: E402

TODAY = "2026-08-08"


def _item(item_id, **kw):
    base = {
        "id": item_id,
        "title": "Item " + item_id,
        "kind": "feature",
        "status": "proposed",
        "tier": "now",
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


def _result(*pairs, method="RICE"):
    return {
        "method_results": {
            method: {
                "ranking": [
                    {"option": oid, "score": score, "rank": n + 1}
                    for n, (oid, score) in enumerate(pairs)
                ]
            }
        },
        "recommendation": {"winner": pairs[0][0] if pairs else None},
        "dec_record_path": "/repo/.claude/docs/decisions/DEC-0007-what-to-build-next.md",
    }


class TestExport(unittest.TestCase):
    def test_option_per_competing_item(self):
        spec = export_spec(_doc(_item("RM-0001"), _item("RM-0002")))
        self.assertEqual([o["id"] for o in spec["options"]], ["RM-0001", "RM-0002"])

    def test_rice_criteria_with_effort_inverted(self):
        spec = export_spec(_doc(_item("RM-0001"), _item("RM-0002")))
        by_id = {c["id"]: c for c in spec["criteria"]}
        self.assertEqual(set(by_id), {"reach", "impact", "confidence", "effort"})
        self.assertEqual(by_id["effort"]["direction"], "lower-is-better")
        self.assertEqual(by_id["reach"]["direction"], "higher-is-better")

    def test_scores_are_null_placeholders_never_invented(self):
        spec = export_spec(_doc(_item("RM-0001"), _item("RM-0002")))
        scores = spec["scorers"][0]["scores"]
        self.assertEqual(set(scores), {"RM-0001", "RM-0002"})
        self.assertEqual(set(scores["RM-0001"]), {"reach", "impact", "confidence", "effort"})
        for entry in scores["RM-0001"].values():
            self.assertIsNone(entry["value"])

    def test_only_pickable_items_compete(self):
        doc = _doc(
            _item("RM-0001"),
            _item("RM-0002", status="done"),
            _item("RM-0003", status="in-progress"),
            _item("RM-0004"),
        )
        self.assertEqual(
            [o["id"] for o in export_spec(doc)["options"]], ["RM-0001", "RM-0004"]
        )

    def test_tier_filter(self):
        doc = _doc(
            _item("RM-0001", tier="now"),
            _item("RM-0002", tier="someday"),
            _item("RM-0003", tier="now"),
        )
        spec = export_spec(doc, tier="now")
        self.assertEqual([o["id"] for o in spec["options"]], ["RM-0001", "RM-0003"])

    def test_explicit_ids_win_over_filters(self):
        doc = _doc(
            _item("RM-0001", tier="now"),
            _item("RM-0002", tier="someday"),
            _item("RM-0003", tier="someday"),
        )
        spec = export_spec(doc, ids=["RM-0002", "RM-0003"])
        self.assertEqual([o["id"] for o in spec["options"]], ["RM-0002", "RM-0003"])

    def test_unblocked_only_drops_items_waiting_on_deps(self):
        doc = _doc(
            _item("RM-0001"),
            _item("RM-0002"),
            _item("RM-0003", deps=["RM-0001"]),
        )
        spec = export_spec(doc, unblocked_only=True)
        self.assertEqual([o["id"] for o in spec["options"]], ["RM-0001", "RM-0002"])

    def test_unknown_explicit_id_is_an_error(self):
        with self.assertRaises(ValueError):
            export_spec(_doc(_item("RM-0001")), ids=["RM-0001", "RM-9999"])

    def test_fewer_than_two_options_is_an_error(self):
        with self.assertRaises(ValueError):
            export_spec(_doc(_item("RM-0001")))

    def test_goal_names_the_scope(self):
        spec = export_spec(_doc(_item("RM-0001"), _item("RM-0002")))
        self.assertIn("task:Demo", spec["goal"])
        self.assertEqual(spec["reversibility"], "two-way")


class TestIngest(unittest.TestCase):
    def test_writes_score_method_and_dec(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002"))
        changed = ingest(doc, _result(("RM-0001", 41.5), ("RM-0002", 22.0)))
        self.assertEqual(changed, ["RM-0001", "RM-0002"])
        first = doc["items"][0]["priority"]
        self.assertEqual(first["score"], 41.5)
        self.assertEqual(first["method"], "RICE")
        self.assertEqual(first["dec"], "DEC-0007")

    def test_unknown_option_is_an_error_not_a_silent_skip(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002"))
        with self.assertRaises(ValueError):
            ingest(doc, _result(("RM-0001", 10.0), ("RM-9999", 5.0)))

    def test_items_absent_from_the_ranking_are_untouched(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002", priority={"method": "manual", "score": 3}))
        ingest(doc, _result(("RM-0001", 10.0)))
        self.assertEqual(doc["items"][1]["priority"], {"method": "manual", "score": 3})

    def test_method_is_taken_from_the_result_not_assumed(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002"))
        ingest(doc, _result(("RM-0001", 8.0), method="weighted-sum"))
        self.assertEqual(doc["items"][0]["priority"]["method"], "weighted-sum")

    def test_missing_method_results_is_an_error(self):
        doc = _doc(_item("RM-0001"))
        with self.assertRaises(ValueError):
            ingest(doc, {"recommendation": {}})

    def test_unrecorded_run_leaves_dec_null(self):
        doc = _doc(_item("RM-0001"), _item("RM-0002"))
        result = _result(("RM-0001", 12.0))
        result["dec_record_path"] = None
        ingest(doc, result)
        self.assertIsNone(doc["items"][0]["priority"]["dec"])


class TestDecId(unittest.TestCase):
    def test_extracts_id_from_filename(self):
        self.assertEqual(
            dec_id_from_path("/x/.claude/docs/decisions/DEC-0012-pick-a-cache.md"),
            "DEC-0012",
        )

    def test_none_path_yields_none(self):
        self.assertIsNone(dec_id_from_path(None))

    def test_unparseable_path_yields_none(self):
        self.assertIsNone(dec_id_from_path("/x/notes.md"))


if __name__ == "__main__":
    unittest.main()
