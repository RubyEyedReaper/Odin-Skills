"""Tests for a roadmap's identity — the `slug`, which is not its `scope`.

`RM-####` is a per-file counter. Two roadmaps in one tree hand out the same ids for different work,
and a handoff that cited one without saying which roadmap it belonged to sent a session at the wrong
item. These cover the mechanism that makes an id resolvable, and in particular the two cases where a
plausible implementation would quietly reintroduce the ambiguity: a slug derived from the checkout
directory, and a document that declares no slug at all.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.schema import (  # noqa: E402
    HARNESS_SLUG,
    ForeignRoadmapError,
    default_doc,
    derive_slug,
    qualify,
    resolve_id,
    slug_of,
    split_qualified,
    validate,
)


def _harness_roadmap(root, enclosing="Odin"):
    """<tmp>/<enclosing>/.claude/docs/roadmap/roadmap.json"""
    path = os.path.join(root, enclosing, ".claude", "docs", "roadmap", "roadmap.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _project_roadmap(root, project):
    """<tmp>/projects/<project>/docs/roadmap/roadmap.json"""
    path = os.path.join(root, "projects", project, "docs", "roadmap", "roadmap.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


class DeriveSlugTest(unittest.TestCase):
    def test_harness_layout_derives_the_constant(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(derive_slug(_harness_roadmap(tmp)), HARNESS_SLUG)

    def test_harness_slug_ignores_the_checkout_directory(self):
        """The case that decided the design.

        This repository is routinely worked on inside `.claude/worktrees/<branch-ish-name>/`, so a
        slug read off the enclosing directory would give one roadmap two identities depending on
        where it was checked out — the same ambiguity the field exists to remove, one level up.
        """
        with tempfile.TemporaryDirectory() as tmp:
            mangled = _harness_roadmap(tmp, enclosing="harness+dependabot-subtree-coverage")
            plain = _harness_roadmap(tmp, enclosing="Odin")
            self.assertEqual(derive_slug(mangled), HARNESS_SLUG)
            self.assertEqual(derive_slug(mangled), derive_slug(plain))

    def test_project_layout_derives_its_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(derive_slug(_project_roadmap(tmp, "ServerPartPicker")),
                             "serverpartpicker")

    def test_project_slug_is_normalised(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(derive_slug(_project_roadmap(tmp, "My Project v2")),
                             "my-project-v2")


class SlugOfTest(unittest.TestCase):
    def test_declared_beats_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _project_roadmap(tmp, "ServerPartPicker")
            doc = default_doc("task:ServerPartPicker")
            doc["slug"] = "spp"
            self.assertEqual(slug_of(doc, path), "spp")

    def test_absent_slug_still_resolves(self):
        """A roadmap inside a submodule cannot be edited from the repository that reads it.

        That is the real condition of the roadmap whose ids collided, so a missing field must never
        be an error — it must derive.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = _project_roadmap(tmp, "ServerPartPicker")
            doc = default_doc("task:ServerPartPicker")
            self.assertNotIn("slug", doc)
            self.assertEqual(slug_of(doc, path), "serverpartpicker")
            self.assertEqual(validate(doc), [])

    def test_malformed_declared_slug_falls_back_and_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _harness_roadmap(tmp)
            doc = default_doc("operational")
            doc["slug"] = "Not A Slug"
            self.assertEqual(slug_of(doc, path), HARNESS_SLUG)
            errors = validate(doc)
            self.assertTrue(any("slug" in e for e in errors), errors)

    def test_scope_is_not_the_slug(self):
        """`scope` is the memory class. Two roadmaps may share one; that is not a collision."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _harness_roadmap(tmp)
            doc = default_doc("operational")
            self.assertEqual(doc["scope"], "operational")
            self.assertNotEqual(slug_of(doc, path), doc["scope"])


class QualifiedIdTest(unittest.TestCase):
    def test_qualify(self):
        self.assertEqual(qualify("harness", "RM-0035"), "harness:RM-0035")

    def test_split_bare(self):
        self.assertEqual(split_qualified("RM-0035"), (None, "RM-0035"))

    def test_split_qualified(self):
        self.assertEqual(split_qualified("harness:RM-0035"), ("harness", "RM-0035"))

    def test_split_rejects_nonsense(self):
        for text in ("", "RM-35", "harness:RM-35", "ARM-0035", "harness:", None):
            self.assertEqual(split_qualified(text), (None, None), text)


class ResolveIdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = _harness_roadmap(self.tmp.name)
        self.doc = default_doc("operational")

    def tearDown(self):
        self.tmp.cleanup()

    def test_bare_id_passes_through(self):
        self.assertEqual(resolve_id(self.doc, self.path, "RM-0035"), "RM-0035")

    def test_matching_prefix_is_stripped(self):
        self.assertEqual(resolve_id(self.doc, self.path, "harness:RM-0035"), "RM-0035")

    def test_foreign_prefix_is_refused(self):
        with self.assertRaises(ForeignRoadmapError) as caught:
            resolve_id(self.doc, self.path, "serverpartpicker:RM-0035")
        message = str(caught.exception)
        self.assertIn("serverpartpicker", message)
        self.assertIn("harness", message)
        self.assertIn("Nothing was changed", message)

    def test_unparseable_text_is_left_alone(self):
        """`find` owns the "no such item" error; this helper only strips prefixes."""
        self.assertEqual(resolve_id(self.doc, self.path, "nonsense"), "nonsense")


if __name__ == "__main__":
    unittest.main()
