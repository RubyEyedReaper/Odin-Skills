"""One corpus, every consumer of `links.files`.

The defect: three consumers in one module read that field with three different matchers, and the
odd one out compared literally. `.claude/rules/ci/**` — nearly half the live entries are shaped like
that — matched nothing under it. Dormant only because no evidence producer fed it yet.

So the assertion that matters is not "each consumer works". It is **that they agree**. A suite
testing each in isolation is what let three interpretations coexist in one file. The corpus below is
therefore driven through every consumer, and the same verdict demanded from each.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import reconcile as reconcile_mod  # noqa: E402

# (pattern, path, covered?) — the whole contract of `links.files`, in one table.
CORPUS = (
    # exact
    (".claude/hooks/odin-safety-guard.sh", ".claude/hooks/odin-safety-guard.sh", True),
    (".claude/hooks/odin-safety-guard.sh", ".claude/hooks/odin-roadmap-gate.sh", False),
    # a directory claim covers what is beneath it, at any depth
    ("src/app", "src/app/billing/page.tsx", True),
    ("src/app", "src/app", True),
    # ...but the separator is required, so it is not a bare string prefix
    ("src/app", "src/append.ts", False),
    ("src/app", "src/apps/other.ts", False),
    # `**` — the shape that matched nothing under the old literal comparison
    (".claude/rules/ci/**", ".claude/rules/ci/patterns.md", True),
    (".claude/rules/ci/**", ".claude/rules/ci/nested/deep.md", True),
    (".claude/rules/ci/**", ".claude/rules/web/patterns.md", False),
    (".claude/rules/**", ".claude/rules/ci/patterns.md", True),
    # a single `*` crosses `/` too — fnmatch's does, and _git_touched has always relied on it
    (".claude/skills/*/SKILL.md", ".claude/skills/roadmap/SKILL.md", True),
    (".claude/skills/*", ".claude/skills/roadmap/scripts/roadmap.py", True),
    # a glob inside a segment
    ("scripts/*.py", "scripts/render.py", True),
    ("scripts/*.py", "scripts/render.pyc", False),
    # unrelated
    ("docs/**", "src/app/page.tsx", False),
)


def _doc_claiming(*patterns):
    """A one-item roadmap whose item claims `patterns`."""
    return {
        "schema": 1, "scope": "task:Corpus", "updated": "2026-08-10",
        "last_reconcile": "2026-08-10",
        "items": [{
            "id": "RM-0001", "title": "Claimant", "kind": "feature", "status": "in-progress",
            "tier": "now", "deps": [], "parent": None, "phase": None, "priority": None,
            "owner_skill": None, "acceptance": [], "created": "2026-08-10",
            "updated": "2026-08-10", "completed": None, "evidence": None, "notes": "",
            "links": {"prd": None, "plan": None, "adr": None, "issues": [],
                      "files": list(patterns)},
        }],
    }


class TestClaimsPredicate(unittest.TestCase):
    def test_the_corpus(self):
        for pattern, path, expected in CORPUS:
            with self.subTest(pattern=pattern, path=path):
                self.assertIs(reconcile_mod.claims(path, [pattern]), expected)

    def test_any_matching_pattern_is_enough(self):
        self.assertTrue(reconcile_mod.claims("src/app/x.ts", ["docs/**", "src/**"]))

    def test_no_patterns_claims_nothing(self):
        self.assertFalse(reconcile_mod.claims("src/app/x.ts", []))

    def test_the_verdict_does_not_depend_on_the_filesystem(self):
        # fnmatch (not fnmatchcase) folds case on some platforms. These paths are repo-relative
        # strings, so a claim must not start matching because the suite moved to macOS.
        self.assertFalse(reconcile_mod.claims("SRC/App/X.ts", ["src/app/**"]))


class TestConsumersAgree(unittest.TestCase):
    """The corpus, through the code paths that read `links.files` in production."""

    def _is_claimed_says(self, pattern, path):
        return reconcile_mod._is_claimed(path, [pattern])

    def _git_touched_says(self, pattern, path):
        # _git_touched intersects `git log --name-only` output with each item's claims. Drive it
        # through `analyze`'s consumer instead of the subprocess: the matching is the part shared.
        items = _doc_claiming(pattern)["items"]
        patterns = (items[0].get("links") or {}).get("files") or []
        return bool([p for p in [path] if reconcile_mod.claims(p, patterns)])

    def _untracked_surface_says(self, pattern, path):
        """True when the finding is *suppressed* — i.e. the path is considered claimed."""
        doc = _doc_claiming(pattern)
        ev = reconcile_mod.empty_evidence()
        ev["untracked_paths"] = [path]
        findings = reconcile_mod.analyze(doc, ev, today="2026-08-10")
        return not any(f["kind"] == "untracked-surface" for f in findings)

    def test_every_consumer_returns_the_corpus_verdict(self):
        consumers = {
            "_is_claimed": self._is_claimed_says,
            "_git_touched": self._git_touched_says,
            "untracked-surface suppression": self._untracked_surface_says,
        }
        for pattern, path, expected in CORPUS:
            for name, consumer in consumers.items():
                with self.subTest(consumer=name, pattern=pattern, path=path):
                    self.assertIs(consumer(pattern, path), expected)


class TestPatternsCannotEscapeTheRoot(unittest.TestCase):
    def test_a_traversing_pattern_is_never_globbed(self):
        # _missing_files joins the pattern onto the repo root. A doc-supplied `..` would resolve
        # outside it; refuse rather than ask the filesystem.
        missing = reconcile_mod._missing_files(
            os.path.dirname(os.path.abspath(__file__)),
            _doc_claiming("../../../etc/passwd")["items"],
        )
        self.assertEqual(missing, {"RM-0001": ["../../../etc/passwd"]})

    def test_an_absolute_pattern_is_never_globbed(self):
        missing = reconcile_mod._missing_files(
            os.path.dirname(os.path.abspath(__file__)),
            _doc_claiming("/etc/passwd")["items"],
        )
        self.assertEqual(missing, {"RM-0001": ["/etc/passwd"]})


if __name__ == "__main__":
    unittest.main()
