"""Tests for scripts/prioritize.py — roadmap <-> decision-matrix hand-off.

The roadmap owns its own file in both directions (DEC-0001 fork 5): it exports a
decision spec for `decision-matrix` to score, and ingests the result back into
`priority`. The decision engine never learns the roadmap format.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.prioritize import (  # noqa: E402
    dec_id_from_path, export_spec, ingest, ledger_for,
)
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


class TestTheExportedSpecDeclaresItsLedger(unittest.TestCase):
    """harness:RM-0170 / #380 — the spec must name the ledger that owns the roadmap.

    `decision-matrix` resolves a spec with no `decisions_dir` against its own fallback, which is
    the *harness* ledger. For a harness roadmap that is right by luck; for a project roadmap the
    project's RICE decision lands in the harness DEC sequence, invisible to the project that owns
    it. The exporter is where the destination is known, so it is where it gets stated.
    """

    def test_the_harness_layout_resolves_to_the_harness_ledger(self):
        json_path = "/repo/.claude/docs/roadmap/roadmap.json"
        self.assertEqual(ledger_for(json_path), "/repo/.claude/docs/decisions")

    def test_a_project_layout_resolves_to_the_project_ledger(self):
        json_path = "/repo/projects/Thing/docs/roadmap/roadmap.json"
        self.assertEqual(ledger_for(json_path), "/repo/projects/Thing/docs/decisions")

    def test_the_exported_spec_carries_the_key(self):
        doc = default_doc("operational", today=TODAY)
        doc["items"] = [_item("RM-0001"), _item("RM-0002")]
        spec = export_spec(doc, decisions_dir="projects/Thing/docs/decisions")
        self.assertEqual(spec["decisions_dir"], "projects/Thing/docs/decisions")

    def test_an_export_with_no_ledger_omits_the_key_rather_than_writing_a_null(self):
        """A null `decisions_dir` is worse than no key: `resolve_decisions_dir` treats a falsy
        declaration as undeclared, so it would read as declared to a human and as absent to the
        engine."""
        doc = default_doc("operational", today=TODAY)
        doc["items"] = [_item("RM-0001"), _item("RM-0002")]
        self.assertNotIn("decisions_dir", export_spec(doc))


class TestTheRoundTripResolvesToTheDeclaredLedger(unittest.TestCase):
    """The point is not a key in a file — it is where `decision-matrix` actually writes.

    Asserted through **the real `resolve_decisions_dir`**, in a subprocess. Two reasons it is not
    an in-process import: `decision-matrix` and `roadmap` both ship a package called `scripts`,
    so importing one while the other is loaded resolves the wrong module; and a test that
    re-implements the consumer's precedence rules proves the assumption rather than the
    behaviour.
    """

    REPO_ROOT = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    MATRIX = os.path.join(REPO_ROOT, ".claude", "skills", "decision-matrix")

    def resolve_through_the_real_engine(self, spec):
        if not os.path.isdir(self.MATRIX):
            self.skipTest("decision-matrix skill not present in this checkout")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(spec, fh)
            spec_path = fh.name
        self.addCleanup(os.unlink, spec_path)
        probe = (
            "import json, sys\n"
            "from scripts.score import resolve_decisions_dir\n"
            "spec = json.load(open(sys.argv[1]))\n"
            "print(resolve_decisions_dir(spec, None))\n"
        )
        done = subprocess.run([sys.executable, "-c", probe, spec_path],
                              cwd=self.MATRIX, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def spec_for(self, json_path):
        doc = default_doc("operational", today=TODAY)
        doc["items"] = [_item("RM-0001"), _item("RM-0002")]
        return export_spec(doc, decisions_dir=ledger_for(json_path, relative_to=self.REPO_ROOT))

    def test_a_project_roadmap_records_into_the_project_ledger(self):
        spec = self.spec_for(os.path.join(
            self.REPO_ROOT, "projects", "Thing", "docs", "roadmap", "roadmap.json"))
        self.assertEqual(spec["decisions_dir"], os.path.join("projects", "Thing", "docs", "decisions"))
        self.assertEqual(
            self.resolve_through_the_real_engine(spec),
            os.path.join(self.REPO_ROOT, "projects", "Thing", "docs", "decisions"),
            "a project's prioritisation must not land in the harness DEC sequence",
        )

    def test_a_harness_roadmap_still_records_into_the_harness_ledger(self):
        spec = self.spec_for(os.path.join(
            self.REPO_ROOT, ".claude", "docs", "roadmap", "roadmap.json"))
        self.assertEqual(
            self.resolve_through_the_real_engine(spec),
            os.path.join(self.REPO_ROOT, ".claude", "docs", "decisions"),
        )
