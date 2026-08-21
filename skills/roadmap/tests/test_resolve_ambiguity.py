"""A mutating subcommand must not pick its target out of an ambient working directory.

`harness:RM-0163` / #355, carrying DEC-0022's contract. The engine is the only party holding both
the true `cwd` and the resolved target — a `PreToolUse` hook sees a command string, not the
directory the process will run in, so a guard placed there is a guess. Here it is a refusal by
construction.

The fixture is a real git repository with two real worktrees, each holding its own roadmap. A
fake — two directories and a stubbed worktree list — would assert that the stub was read.

Note the asymmetry the cases pin down: **read-only is unaffected, always.** A wrong-repo read is
visible in its own output and changes nothing, which is the same line `safety-guard` Layer 1C draws
between `gh pr view` and `gh pr merge`.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import roadmap  # noqa: E402
from scripts import schema  # noqa: E402


def git(*args, cwd):
    subprocess.run(("git",) + args, cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def seed_roadmap(root, scope):
    path = os.path.join(root, "docs", "roadmap", "roadmap.json")
    doc = schema.default_doc(scope, today="2026-08-20")
    doc["items"].append(schema.new_item("RM-0001", "an item", "ops", today="2026-08-20"))
    schema.save(path, doc)
    schema.forget(path)
    return path


class AmbiguityFixture(unittest.TestCase):
    """One git repository, two worktrees, a roadmap in each."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="roadmap-ambig-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.base = os.path.join(self.tmp, "base")
        os.makedirs(self.base)
        git("init", "-q", "-b", "main", ".", cwd=self.base)
        git("config", "user.email", "t@example.invalid", cwd=self.base)
        git("config", "user.name", "t", cwd=self.base)
        with open(os.path.join(self.base, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("fixture\n")
        git("add", "README.md", cwd=self.base)
        git("commit", "-qm", "init", cwd=self.base)
        self.base_json = seed_roadmap(self.base, "operational")

        self.second = os.path.join(self.tmp, "second")
        git("worktree", "add", "-q", self.second, "-b", "second", cwd=self.base)
        self.second_json = seed_roadmap(self.second, "operational")

        self.solo = os.path.join(self.tmp, "solo")
        os.makedirs(self.solo)
        git("init", "-q", "-b", "main", ".", cwd=self.solo)
        git("config", "user.email", "t@example.invalid", cwd=self.solo)
        git("config", "user.name", "t", cwd=self.solo)
        self.solo_json = seed_roadmap(self.solo, "operational")

    def run_engine(self, argv, cwd):
        """Run the engine with `cwd` as the working directory, capturing both streams."""
        previous = os.getcwd()
        os.chdir(cwd)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = roadmap.main(argv)
                except SystemExit as exc:
                    code = exc.code
        finally:
            os.chdir(previous)
        return code, out.getvalue(), err.getvalue()

    def status_of(self, path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["items"][0]["status"]


class TestAmbiguousTargetIsRefused(AmbiguityFixture):
    def test_a_bare_mutating_call_refuses_and_names_the_candidates(self):
        code, _, err = self.run_engine(["set", "RM-0001", "--status", "ready"], cwd=self.base)

        self.assertNotEqual(code, 0, "an ambiguous mutating call must not write")
        self.assertIn(self.base_json, err)
        self.assertIn(self.second_json, err)
        self.assertIn("--root", err, "a refusal must name its remedy")
        self.assertEqual(self.status_of(self.base_json), "proposed",
                         "nothing may be written by a refused call")

    def test_an_explicit_root_proceeds(self):
        code, out, err = self.run_engine(
            ["--root", self.base, "set", "RM-0001", "--status", "ready"], cwd=self.base)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(self.base_json), "ready")

    def test_an_explicit_path_proceeds(self):
        code, out, err = self.run_engine(
            ["--path", self.base_json, "set", "RM-0001", "--status", "ready"], cwd=self.base)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(self.base_json), "ready")

    def test_a_read_only_call_is_unaffected(self):
        code, out, err = self.run_engine(["next"], cwd=self.base)
        self.assertEqual(code, 0, err)
        self.assertIn("RM-0001", out)

    def test_a_single_worktree_repository_gains_no_friction(self):
        code, out, err = self.run_engine(["set", "RM-0001", "--status", "ready"], cwd=self.solo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(self.solo_json), "ready")

    def test_a_sibling_worktree_without_a_roadmap_is_not_a_candidate(self):
        """Two worktrees is not the predicate — two reachable roadmaps is.

        A guard that fires where no second target exists is friction with no hazard behind it,
        and friction with no hazard is how a guard gets switched off.
        """
        empty = os.path.join(self.tmp, "empty")
        git("worktree", "add", "-q", empty, "-b", "empty", cwd=self.base)
        shutil.rmtree(os.path.join(self.second, "docs"))

        code, out, err = self.run_engine(["set", "RM-0001", "--status", "ready"], cwd=self.base)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(self.base_json), "ready")


if __name__ == "__main__":
    unittest.main()
