"""Every path the engine writes is a child of the roadmap's own root.

`harness:RM-0364`. The suite was green for months while writing `/tmp/ROADMAP.md` on every run,
because `paths_for()` derived the root by walking up two directories from the json unconditionally
— so a roadmap at `<tmp>/other/roadmap.json` put its rendering two directories above the fixture,
in whatever directory happened to be there. The render succeeded; it just succeeded somewhere else.

These cases assert the **class**, not the filename. A test spelling `/tmp/ROADMAP.md` passes the
moment the stray file becomes `/tmp/graph.dot`, which is the shape that let this live. Each case
snapshots the directories above the fixture, drives the engine, and compares — so any escape, under
any name, by any future generated artifact, is caught by the case that already exists.

The fixtures are built through the engine's own `init`/`add`, never by writing a json file by hand:
the subject here is what the engine writes, so a hand-built document would be testing the parser's
tolerance instead.
"""
import hashlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import render as render_mod  # noqa: E402
from scripts.roadmap import main  # noqa: E402

TODAY = "2026-09-01"


def _run(json_path, *argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--path", json_path, "--today", TODAY, *argv])
    return code, out.getvalue(), err.getvalue()


def _digest(path):
    """A file's content, or the marker that it is a directory.

    Content, not `os.listdir` alone: the escape this closes writes `ROADMAP.md` at *init* and
    rewrites the same name at every render after it, so a comparison of directory entries sees
    an unchanged set and reports nothing. A guard that cannot see an overwrite has the same blind
    spot as the one that let this live.
    """
    if os.path.isdir(path):
        return "<dir>"
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError as exc:
        return "<unreadable:%s>" % exc.errno


def _snapshot(*dirs):
    """What each directory holds now, so a later comparison names the escapee."""
    return {
        d: {name: _digest(os.path.join(d, name)) for name in os.listdir(d)}
        for d in dirs
        if os.path.isdir(d)
    }


class _ContainmentCase(object):
    """A layout, a fixture root, and the assertion that nothing above it moved.

    A plain mixin, not a `TestCase`: a base that unittest can collect runs every case against an
    unset layout and reports errors that belong to no real scenario, which buries the failures
    that do.

    Subclasses name `relative_json` — where the roadmap sits under the fixture root.
    """

    relative_json = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Two levels of container above the fixture root, because the defect walked up exactly two.
        # Real temp directories, so nothing outside the test's own tree is ever a candidate to be
        # written into — an assertion over `/tmp` itself would read ambient host state and give a
        # different verdict on every machine (`ci-gate/fixture-reads-ambient-state`).
        self.outer = os.path.join(self._tmp.name, "outer")
        self.middle = os.path.join(self.outer, "middle")
        self.root = os.path.join(self.middle, "fixture-root")
        os.makedirs(self.root)
        self.json_path = os.path.join(self.root, *self.relative_json)

    def _watched(self):
        return (self._tmp.name, self.outer, self.middle)

    def assertNothingEscaped(self, before):
        after = _snapshot(*self._watched())
        for directory, entries in before.items():
            self.assertEqual(
                entries,
                after.get(directory, {}),
                "the engine wrote outside the fixture root, into %s" % directory,
            )

    def test_init_writes_nothing_above_the_root(self):
        before = _snapshot(*self._watched())
        code, _, err = _run(self.json_path, "init", "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertNothingEscaped(before)

    def test_render_writes_nothing_above_the_root(self):
        _run(self.json_path, "init", "--scope", "task:Demo")
        _run(self.json_path, "add", "--title", "First thing", "--kind", "feature")
        before = _snapshot(*self._watched())
        code, _, err = _run(self.json_path, "render")
        self.assertEqual(code, 0, err)
        self.assertNothingEscaped(before)

    def test_render_all_writes_nothing_above_the_root(self):
        # The module-level entry point, not only the CLI wrapper: `set` and `reconcile` call it
        # directly, so a containment guard that only covered the subcommand would miss them.
        _run(self.json_path, "init", "--scope", "task:Demo")
        before = _snapshot(*self._watched())
        written = render_mod.render_all(self.json_path)
        for name, target in written.items():
            if not target:
                continue
            self.assertTrue(
                os.path.abspath(target).startswith(os.path.abspath(self.root) + os.sep),
                "render_all reported %s outside the root: %s" % (name, target),
            )
        self.assertNothingEscaped(before)


class TestProjectLayout(_ContainmentCase, unittest.TestCase):
    """`<root>/docs/roadmap/roadmap.json` — ROADMAP.md belongs at the project root."""

    relative_json = ("docs", "roadmap", "roadmap.json")

    def test_the_rendering_lands_at_the_project_root(self):
        _run(self.json_path, "init", "--scope", "task:Demo")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "ROADMAP.md")))


class TestHarnessLayout(_ContainmentCase, unittest.TestCase):
    """`<repo>/.claude/docs/roadmap/roadmap.json` — ROADMAP.md stays beside the json."""

    relative_json = (".claude", "docs", "roadmap", "roadmap.json")

    def test_the_rendering_lands_beside_the_json(self):
        _run(self.json_path, "init", "--scope", "operational")
        self.assertTrue(
            os.path.isfile(os.path.join(os.path.dirname(self.json_path), "ROADMAP.md"))
        )


class TestUnrecognisedLayout(_ContainmentCase, unittest.TestCase):
    """A roadmap somewhere the two named layouts do not describe.

    This is the case that escaped: `paths_for()` had no third answer, so it applied the project
    layout's two-level walk to a path that was never a project root, and the rendering landed in
    whatever directory happened to be two above the json.
    """

    relative_json = ("other", "roadmap.json")

    def test_the_rendering_stays_beside_the_json(self):
        _run(self.json_path, "init", "--scope", "task:Other")
        self.assertTrue(
            os.path.isfile(os.path.join(os.path.dirname(self.json_path), "ROADMAP.md"))
        )


class TestShallowLayout(_ContainmentCase, unittest.TestCase):
    """The json directly at the root — the shallowest a caller can name."""

    relative_json = ("roadmap.json",)


if __name__ == "__main__":
    unittest.main()
