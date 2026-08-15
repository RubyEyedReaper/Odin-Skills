"""The surface sweep, against a real git tree.

Every assertion here is about **which paths come back**, because the thing being fixed is a producer
that returned nothing while a finding kind, an applier and a documented evidence source all claimed
otherwise. A test that asserted "the finding kind exists" passed for the entire life of that bug.

The fixture is a genuine `git init` rather than a directory of files: the sweep delegates ignore
semantics to git precisely so it inherits `.gitignore`, nested ignore files, and git's refusal to
descend into a nested repository. Mocking git would test the mock.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import sweep as sweep_mod  # noqa: E402
from scripts.roadmap import main  # noqa: E402

TODAY = "2026-08-10"
HAS_GIT = shutil.which("git") is not None


def _run(json_path, *argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--path", json_path, "--today", TODAY, *argv])
    return code, out.getvalue(), err.getvalue()


def _write(root, rel, body="x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def _git(root, *args):
    # GIT_CONFIG_GLOBAL is neutralised so the suite does not depend on the runner's identity or on
    # a global ignore file that would change which paths git reports.
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, env=env)


@unittest.skipUnless(HAS_GIT, "the sweep enumerates from git and has no fallback by design")
class TestSweep(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

        _write(self.root, ".gitignore", "dist/\n")
        _write(self.root, "src/app/billing/page.tsx")     # unclaimed  -> src/app/billing
        _write(self.root, "src/app/home/page.tsx")        # claimed below
        _write(self.root, "src/lib/deep/nested/thing.ts")  # folds to src/lib/deep
        _write(self.root, "dist/bundle.js")               # gitignored
        _write(self.root, "docs/notes.md")                # outside the root set
        _write(self.root, "src/top-level.ts")             # shallower than DEPTH
        _git(self.root, "init", "-q")
        _git(self.root, "add", "-A")

        self.doc = {
            "schema": 1, "scope": "task:Fixture", "updated": TODAY, "last_reconcile": TODAY,
            "items": [{
                "id": "RM-0001", "title": "Home", "kind": "page", "status": "in-progress",
                "tier": "now", "deps": [], "parent": None, "phase": None, "priority": None,
                "owner_skill": None, "acceptance": [], "created": TODAY, "updated": TODAY,
                "completed": None, "evidence": None, "notes": "",
                "links": {"prd": None, "plan": None, "adr": None, "issues": [],
                          "files": ["src/app/home"]},
            }],
        }

    def _sweep(self, **kw):
        return sweep_mod.untracked_surfaces(self.root, self.doc, **kw)

    def test_it_reports_the_unclaimed_surface(self):
        paths, _ = self._sweep()
        self.assertIn("src/app/billing", paths)

    def test_a_claimed_surface_is_not_reported(self):
        paths, _ = self._sweep()
        self.assertNotIn("src/app/home", paths)

    def test_paths_fold_to_the_configured_depth(self):
        paths, _ = self._sweep()
        self.assertIn("src/lib/deep", paths)
        self.assertNotIn("src/lib/deep/nested", paths)

    def test_a_gitignored_path_is_never_reported(self):
        paths, _ = self._sweep()
        self.assertFalse([p for p in paths if p.startswith("dist")])

    def test_paths_outside_the_root_set_are_not_reported(self):
        paths, _ = self._sweep()
        self.assertFalse([p for p in paths if p.startswith("docs")])

    def test_a_glob_claim_suppresses_everything_under_it(self):
        # The RM-0029 predicate, exercised through the sweep. Under the old literal matcher this
        # claim covered nothing and the sweep reported the whole tree.
        self.doc["items"][0]["links"]["files"] = ["src/**"]
        paths, _ = self._sweep()
        self.assertEqual(paths, [])

    def test_a_repo_with_none_of_the_default_roots_sweeps_nothing(self):
        # Odin's own case, and deliberate: a harness tree has no src/ or app/, and sweeping
        # .claude/ would produce a hundred findings against directories that are all intentional.
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare)
        _write(bare, ".claude/skills/thing/SKILL.md")
        _git(bare, "init", "-q")
        _git(bare, "add", "-A")
        self.assertEqual(sweep_mod.untracked_surfaces(bare, self.doc), ([], 0))

    def test_an_explicit_root_overrides_the_default(self):
        paths, _ = self._sweep(override=["docs"])
        self.assertEqual(paths, ["docs/notes.md"])

    def test_a_nested_repository_is_reported_as_one_entry_not_walked_into(self):
        # git does not descend into a nested repo, so a workspace holding other projects cannot
        # have this sweep propose roadmap items for a foreign project's source (ADR-0026).
        _write(self.root, "src/vendor/inner/a.ts")
        _write(self.root, "src/vendor/inner/b.ts")
        subprocess.run(["git", "init", "-q", os.path.join(self.root, "src/vendor/inner")],
                       check=True, capture_output=True,
                       env=dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull))
        # Deliberately not `git add`-ed: `--others` reports untracked paths, and an embedded
        # repository is reported as the directory itself rather than its contents. (`git add -A`
        # over an embedded repo fails outright, which is its own way of saying the same thing.)
        paths, _ = self._sweep()
        # The nested repo appears as one entry; none of its files do.
        self.assertIn("src/vendor/inner", paths)
        self.assertFalse([p for p in paths if p.startswith("src/vendor/inner/")], paths)

    def test_the_cap_bounds_the_run_and_reports_what_it_dropped(self):
        for n in range(sweep_mod.MAX_FINDINGS + 5):
            _write(self.root, "src/app/feature%02d/page.tsx" % n)
        _git(self.root, "add", "-A")
        paths, dropped = self._sweep()
        self.assertEqual(len(paths), sweep_mod.MAX_FINDINGS)
        self.assertGreater(dropped, 0)

    def test_the_cap_keeps_the_same_findings_across_runs(self):
        # Sorted before capping. Filesystem order would make a truncated run's output depend on
        # what the previous one happened to see.
        for n in range(sweep_mod.MAX_FINDINGS + 5):
            _write(self.root, "src/app/feature%02d/page.tsx" % n)
        _git(self.root, "add", "-A")
        self.assertEqual(self._sweep()[0], self._sweep()[0])


@unittest.skipUnless(HAS_GIT, "the sweep enumerates from git and has no fallback by design")
class TestSweepThroughReconcile(unittest.TestCase):
    """End to end: the sweep reaches findings, findings reach items, and a re-run adds nothing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.json_path = os.path.join(self.root, "docs", "roadmap", "roadmap.json")
        self.addCleanup(self._tmp.cleanup)
        _write(self.root, "src/app/billing/page.tsx")
        _write(self.root, "src/app/search/page.tsx")
        _run(self.json_path, "init", "--scope", "task:Fixture")
        _git(self.root, "init", "-q")
        _git(self.root, "add", "-A")

    def _items(self):
        with open(self.json_path, encoding="utf-8") as fh:
            return json.load(fh)["items"]

    def test_reconcile_reports_the_surfaces(self):
        _, out, _ = _run(self.json_path, "reconcile", "--no-gh")
        self.assertIn("src/app/billing", out)

    def test_apply_auto_adds_one_item_per_surface_carrying_its_path(self):
        _run(self.json_path, "reconcile", "--no-gh", "--apply-auto")
        claimed = [f for item in self._items() for f in item["links"]["files"]]
        self.assertIn("src/app/billing", claimed)
        self.assertIn("src/app/search", claimed)

    def test_a_second_run_adds_nothing(self):
        # The acceptance criterion, asserted on identity rather than on any message. This only
        # holds because the applier writes the path into links.files and `claims()` reads it back.
        _run(self.json_path, "reconcile", "--no-gh", "--apply-auto")
        before = sorted(i["id"] for i in self._items())
        _run(self.json_path, "reconcile", "--no-gh", "--apply-auto")
        self.assertEqual(before, sorted(i["id"] for i in self._items()))

    def test_the_result_still_validates(self):
        _run(self.json_path, "reconcile", "--no-gh", "--apply-auto")
        code, _, err = _run(self.json_path, "validate")
        self.assertEqual(code, 0, err)

    def test_no_git_disables_the_sweep(self):
        # There is deliberately no filesystem fallback: a hand-written ignore list reports a
        # different set of paths than git, and under --apply-auto that difference becomes items.
        _, out, _ = _run(self.json_path, "reconcile", "--no-git", "--no-gh")
        self.assertNotIn("src/app/billing", out)


if __name__ == "__main__":
    unittest.main()
