"""Tests for scripts/schema.py (stdlib only) — written before implementation."""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.schema import (  # noqa: E402
    SCHEMA_VERSION,
    add_item,
    alloc_id,
    canonical_json,
    content_hash,
    default_doc,
    find,
    load,
    paths_for,
    pattern_escapes_root,
    save,
    set_item,
    validate,
)

TODAY = "2026-07-29"


def _doc(*items):
    doc = default_doc("task:Demo", today=TODAY)
    doc["items"] = list(items)
    return doc


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


class TestDefaults(unittest.TestCase):
    def test_default_doc_shape(self):
        doc = default_doc("task:Demo", today=TODAY)
        self.assertEqual(doc["schema"], SCHEMA_VERSION)
        self.assertEqual(doc["scope"], "task:Demo")
        self.assertEqual(doc["items"], [])
        self.assertIsNone(doc["last_reconcile"])

    def test_default_doc_validates_clean(self):
        self.assertEqual(validate(default_doc("task:Demo", today=TODAY)), [])


class TestIdAllocation(unittest.TestCase):
    def test_alloc_id_starts_at_one(self):
        self.assertEqual(alloc_id(_doc()), "RM-0001")

    def test_alloc_id_takes_max_plus_one_not_count(self):
        doc = _doc(_item("RM-0001"), _item("RM-0009"))
        self.assertEqual(alloc_id(doc), "RM-0010")

    def test_alloc_id_survives_deleted_middle_ids(self):
        doc = _doc(_item("RM-0004"))
        self.assertEqual(alloc_id(doc), "RM-0005")

    def test_add_item_assigns_and_stamps(self):
        doc = _doc()
        item = add_item(doc, title="Login page", kind="page", today=TODAY)
        self.assertEqual(item["id"], "RM-0001")
        self.assertEqual(item["created"], TODAY)
        self.assertEqual(item["status"], "proposed")
        self.assertIs(find(doc, "RM-0001"), item)


class TestHashing(unittest.TestCase):
    def test_hash_is_stable_across_key_order(self):
        a = _doc(_item("RM-0001"))
        b = _doc(_item("RM-0001"))
        b["items"][0] = dict(reversed(list(b["items"][0].items())))
        self.assertEqual(content_hash(a), content_hash(b))

    def test_hash_changes_with_content(self):
        a = _doc(_item("RM-0001"))
        b = _doc(_item("RM-0001", title="Different"))
        self.assertNotEqual(content_hash(a), content_hash(b))

    def test_saved_bytes_equal_canonical_json(self):
        doc = _doc(_item("RM-0001"))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "docs", "roadmap", "roadmap.json")
            save(path, doc)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), canonical_json(doc))
            self.assertEqual(load(path), doc)


class TestValidation(unittest.TestCase):
    def _errs(self, doc):
        return " | ".join(validate(doc))

    def test_duplicate_id_rejected(self):
        self.assertIn("duplicate", self._errs(_doc(_item("RM-0001"), _item("RM-0001"))))

    def test_bad_id_format_rejected(self):
        self.assertIn("id", self._errs(_doc(_item("RM-1"))))

    def test_unknown_kind_rejected(self):
        self.assertIn("kind", self._errs(_doc(_item("RM-0001", kind="widget"))))

    def test_unknown_tier_rejected(self):
        self.assertIn("tier", self._errs(_doc(_item("RM-0001", tier="urgent"))))

    def test_stored_blocked_status_rejected_with_guidance(self):
        errs = self._errs(_doc(_item("RM-0001", status="blocked")))
        self.assertIn("blocked", errs)
        self.assertIn("computed", errs)

    def test_unknown_dep_rejected(self):
        self.assertIn("RM-0099", self._errs(_doc(_item("RM-0001", deps=["RM-0099"]))))

    def test_self_dep_rejected(self):
        self.assertIn("itself", self._errs(_doc(_item("RM-0001", deps=["RM-0001"]))))

    def test_done_item_with_unfinished_dep_rejected(self):
        doc = _doc(
            _item("RM-0001", status="ready"),
            _item("RM-0002", status="done", deps=["RM-0001"]),
        )
        self.assertIn("RM-0002", self._errs(doc))

    def test_unknown_parent_rejected(self):
        self.assertIn("parent", self._errs(_doc(_item("RM-0001", parent="RM-0077"))))

    def test_self_parent_rejected(self):
        self.assertIn("parent", self._errs(_doc(_item("RM-0001", parent="RM-0001"))))

    def test_valid_doc_has_no_errors(self):
        doc = _doc(
            _item("RM-0001", status="done"),
            _item("RM-0002", deps=["RM-0001"], parent=None),
        )
        self.assertEqual(validate(doc), [])


class TestSetItem(unittest.TestCase):
    def test_set_updates_and_restamps(self):
        doc = _doc(_item("RM-0001"))
        set_item(doc, "RM-0001", status="ready", today="2026-08-01")
        self.assertEqual(find(doc, "RM-0001")["status"], "ready")
        self.assertEqual(find(doc, "RM-0001")["updated"], "2026-08-01")

    def test_set_done_stamps_completed(self):
        doc = _doc(_item("RM-0001"))
        set_item(doc, "RM-0001", status="done", today="2026-08-01")
        self.assertEqual(find(doc, "RM-0001")["completed"], "2026-08-01")

    def test_set_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            set_item(_doc(), "RM-0404", status="ready")

    def test_set_rejects_unknown_field(self):
        doc = _doc(_item("RM-0001"))
        with self.assertRaises(ValueError):
            set_item(doc, "RM-0001", nonsense="x")


class TestFilePatternBoundary(unittest.TestCase):
    """`links.files` is doc data that reconcile joins onto the repo root and globs.

    An absolute or traversing pattern therefore reaches the filesystem outside the repository. It
    is refused at the gate, where a bad value fails CI, rather than at sweep time where it would
    already have read something.
    """

    def _doc_with_files(self, *patterns):
        doc = default_doc("task:Demo", today=TODAY)
        add_item(doc, "Claimant", "feature", today=TODAY,
                 links={"prd": None, "plan": None, "adr": None, "issues": [],
                        "files": list(patterns)})
        return doc

    def test_a_repo_relative_pattern_is_fine(self):
        self.assertEqual(validate(self._doc_with_files(".claude/rules/ci/**")), [])

    def test_an_absolute_pattern_is_rejected(self):
        errors = validate(self._doc_with_files("/etc/passwd"))
        self.assertEqual(len(errors), 1)
        self.assertIn("outside the repository", errors[0])

    def test_a_traversing_pattern_is_rejected(self):
        errors = validate(self._doc_with_files("../../../etc/passwd"))
        self.assertEqual(len(errors), 1)

    def test_a_home_relative_pattern_is_rejected(self):
        self.assertEqual(len(validate(self._doc_with_files("~/.ssh/id_rsa"))), 1)

    def test_a_dotdot_inside_a_segment_is_not_traversal(self):
        # `..` as a path component escapes; `a..b` is an ordinary filename and must stay legal.
        self.assertEqual(validate(self._doc_with_files("src/weird..name.ts")), [])

    def test_an_empty_pattern_is_rejected(self):
        self.assertEqual(len(validate(self._doc_with_files("   "))), 1)

    def test_the_predicate_is_shared_not_copied(self):
        # reconcile.escapes_root delegates here. Two copies of this rule is the defect RM-0029
        # exists to remove, so the delegation is pinned.
        from scripts.reconcile import escapes_root
        for pattern in ("/etc/passwd", "../x", "~/x", "src/app/**", "a..b/c.ts"):
            self.assertIs(escapes_root(pattern), pattern_escapes_root(pattern), pattern)


class TestSurfaceRoots(unittest.TestCase):
    """`surface_roots` becomes a directory the sweep walks — the same boundary rule applies."""

    def _doc(self, roots):
        doc = default_doc("task:Demo", today=TODAY)
        doc["surface_roots"] = roots
        return doc

    def test_absent_is_legal(self):
        self.assertEqual(validate(default_doc("task:Demo", today=TODAY)), [])

    def test_repo_relative_roots_are_fine(self):
        self.assertEqual(validate(self._doc(["src", "packages"])), [])

    def test_an_absolute_root_is_rejected(self):
        errors = validate(self._doc(["/"]))
        self.assertEqual(len(errors), 1)
        self.assertIn("outside the repository", errors[0])

    def test_a_traversing_root_is_rejected(self):
        self.assertEqual(len(validate(self._doc(["../elsewhere"]))), 1)

    def test_a_non_list_is_rejected(self):
        self.assertEqual(len(validate(self._doc("src"))), 1)

    def test_a_non_string_entry_is_rejected(self):
        self.assertEqual(len(validate(self._doc([3]))), 1)


class TestPaths(unittest.TestCase):
    def test_project_layout_puts_md_at_project_root(self):
        p = paths_for("/repo/projects/Demo/docs/roadmap/roadmap.json")
        self.assertTrue(p["md"].endswith("/projects/Demo/ROADMAP.md"))
        self.assertTrue(p["dot"].endswith("/docs/roadmap/graph.dot"))
        self.assertTrue(p["svg"].endswith("/docs/roadmap/graph.svg"))

    def test_harness_layout_keeps_md_beside_json(self):
        p = paths_for("/repo/.claude/docs/roadmap/roadmap.json")
        self.assertTrue(p["md"].endswith("/.claude/docs/roadmap/ROADMAP.md"))

    def test_project_layout_root_is_the_project(self):
        p = paths_for("/repo/projects/Demo/docs/roadmap/roadmap.json")
        self.assertEqual(p["root"], "/repo/projects/Demo")

    def test_harness_layout_root_is_the_repo_not_dot_claude(self):
        # root is what every repo-relative consumer resolves against — file globs in
        # reconcile, CHANGELOG.md, git. Returning `<repo>/.claude` made reconcile glob
        # `.claude/.claude/**` and call every finished item's files missing.
        p = paths_for("/repo/.claude/docs/roadmap/roadmap.json")
        self.assertEqual(p["root"], "/repo")


if __name__ == "__main__":
    unittest.main()
