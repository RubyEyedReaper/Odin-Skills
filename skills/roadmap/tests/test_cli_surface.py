"""The CLI surface the documentation promises — flags and messages, not internals.

Every case here comes from the 2026-08-15 audit of this skill: a flag documented in nine places
that the parser never accepted, a `--from` path resolved against the wrong directory, and a "no
unblocked items" message that an empty roadmap cannot honestly produce. Each was invisible to the
existing suite because the suite tests the engine's functions and these are properties of its
*edges* — what it accepts, and what it says.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.roadmap import main  # noqa: E402

TODAY = "2026-08-15"


def _run(json_path, *argv, today=TODAY):
    out, err = io.StringIO(), io.StringIO()
    argv = ["--path", json_path, "--today", today, *argv]
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def _run_root(root, *argv, today=TODAY):
    out, err = io.StringIO(), io.StringIO()
    argv = ["--root", root, "--today", today, *argv]
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestPrioritizeExportFlag(unittest.TestCase):
    """`prioritize --export` is documented in nine places; the parser rejected it (audit F1).

    Export is already the default, so the flag changes nothing — it exists so that every copy of
    the documented command, including the ones already sitting in transcripts and memories, runs.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self._tmp.name, "docs", "roadmap", "roadmap.json")
        _run(self.json_path, "init", "--scope", "task:Demo")
        # Two items in one tier: exporting a spec with fewer than two competitors is a refusal,
        # not a decision, so a one-item fixture would test the wrong failure.
        _run(self.json_path, "add", "--title", "First thing", "--kind", "feature",
             "--tier", "now")
        _run(self.json_path, "add", "--title", "Second thing", "--kind", "feature",
             "--tier", "now")
        self.addCleanup(self._tmp.cleanup)

    def test_export_flag_is_accepted(self):
        spec = os.path.join(self._tmp.name, "spec.json")
        code, _, err = _run(self.json_path, "prioritize", "--export", "--tier", "now",
                            "--out", spec)
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(spec))

    def test_export_flag_changes_nothing(self):
        with_flag = os.path.join(self._tmp.name, "with.json")
        without = os.path.join(self._tmp.name, "without.json")
        _run(self.json_path, "prioritize", "--export", "--tier", "now", "--out", with_flag)
        _run(self.json_path, "prioritize", "--tier", "now", "--out", without)
        with open(with_flag, encoding="utf-8") as fh:
            a = json.load(fh)
        with open(without, encoding="utf-8") as fh:
            b = json.load(fh)
        self.assertEqual(a, b)

    def test_export_does_not_write_the_roadmap(self):
        """Layer 1F classifies this form as read-only; the engine must agree."""
        before = os.path.getmtime(self.json_path)
        spec = os.path.join(self._tmp.name, "spec.json")
        code, _, _ = _run(self.json_path, "prioritize", "--export", "--tier", "now", "--out", spec)
        self.assertEqual(code, 0)
        self.assertEqual(before, os.path.getmtime(self.json_path))


class TestBootstrapSourceResolution(unittest.TestCase):
    """`bootstrap --from` opened its sources relative to the working directory (audit F2).

    Every documented invocation begins by cd-ing into the skill directory, so `--from INIT.md`
    was looked for inside `.claude/skills/roadmap/` and never inside the project. The hook's own
    bootstrap nudge — the one shown to a project with no roadmap — could therefore not read either
    source file on any project, and said `bootstrapped … 0 new item(s)` on stdout while the
    "skipping missing source" line went to stderr.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        with open(os.path.join(self.root, "INIT.md"), "w", encoding="utf-8") as fh:
            fh.write("# Init\n\n## Phase 1\n\n- Signup page — collect an email\n"
                     "- Login page — session cookie\n")
        self.addCleanup(self._tmp.cleanup)

    def _items(self):
        with open(os.path.join(self.root, "docs", "roadmap", "roadmap.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)["items"]

    def test_relative_source_resolves_against_root(self):
        code, out, err = _run_root(self.root, "bootstrap", "--from", "INIT.md",
                                   "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertGreaterEqual(len(self._items()), 2, out + err)

    def test_absolute_source_still_works(self):
        code, _, err = _run_root(self.root, "bootstrap",
                                 "--from", os.path.join(self.root, "INIT.md"),
                                 "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertGreaterEqual(len(self._items()), 2)

    def test_every_source_missing_is_a_failure(self):
        """A bootstrap that read nothing is a failed bootstrap, not a 0-item success."""
        code, out, err = _run_root(self.root, "bootstrap", "--from", "NOPE.md",
                                   "--scope", "task:Demo")
        self.assertEqual(code, 1)
        self.assertIn("NOPE.md", out + err)
        self.assertNotIn("bootstrapped", out)

    def test_one_readable_source_is_not_a_failure(self):
        """Only *every* source missing is fatal — a partial sweep still bootstraps."""
        code, _, err = _run_root(self.root, "bootstrap", "--from", "NOPE.md",
                                 "--from", "INIT.md", "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertGreaterEqual(len(self._items()), 2)

    def test_a_sweep_does_not_excuse_unreadable_sources(self):
        """The hook's nudge pairs --from with --surface-sweep; a typo must not hide behind it.

        Otherwise the failure mode returns in a worse shape: the project doc is silently unread and
        the roadmap fills with starter surfaces nobody asked for. Nothing is written on this path,
        so re-running with a correct path is the whole recovery.
        """
        code, out, err = _run_root(self.root, "bootstrap", "--from", "NOPE.md",
                                   "--surface-sweep", "--scope", "task:Demo")
        self.assertEqual(code, 1)
        self.assertIn("NOPE.md", out + err)
        self.assertFalse(os.path.exists(
            os.path.join(self.root, "docs", "roadmap", "roadmap.json")))

    def test_surface_sweep_alone_is_not_a_missing_source(self):
        """`--surface-sweep` with no --from has no sources to miss."""
        code, _, err = _run_root(self.root, "bootstrap", "--surface-sweep",
                                 "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertGreater(len(self._items()), 0)


class TestStarterSurfaceProfiles(unittest.TestCase):
    """`--surface-sweep` assumed a web product, with no alternative and no way to decline (F5).

    Roughly thirty-five web surfaces — login, pricing page, terms of service — are right for the
    projects the list was written for and wrong for a plugin or library repository, where they
    produce items for pages that repository will never have. The skill's own advice was to "walk
    them with the user", which is a stop the autonomous contract does not have available.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _titles(self):
        with open(os.path.join(self.root, "docs", "roadmap", "roadmap.json"),
                  encoding="utf-8") as fh:
            return {i["title"].lower() for i in json.load(fh)["items"]}

    def test_bare_flag_still_sweeps_web_surfaces(self):
        """The hook's nudge and every transcript spell it bare; it must keep meaning `web`."""
        code, out, err = _run_root(self.root, "bootstrap", "--surface-sweep",
                                   "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertIn("login page", self._titles())
        self.assertIn("web", out)

    def test_library_profile_replaces_the_web_surfaces(self):
        code, out, err = _run_root(self.root, "bootstrap", "--surface-sweep", "library",
                                   "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        titles = self._titles()
        self.assertNotIn("login page", titles)
        self.assertNotIn("pricing page", titles)
        self.assertTrue(any("changelog" in t for t in titles), titles)
        self.assertIn("library", out)

    def test_the_summary_names_the_profile(self):
        """A wrong profile must be visible at a glance, not after thirty-five items land."""
        _, out, _ = _run_root(self.root, "bootstrap", "--surface-sweep", "library",
                              "--scope", "task:Demo")
        self.assertRegex(out, r"starter surfaces.*library")

    def test_an_unknown_profile_is_refused(self):
        """Engine convention: a caller error exits via SystemExit, naming what it knows."""
        err = io.StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stderr(err), \
                redirect_stdout(io.StringIO()):
            main(["--root", self.root, "--today", TODAY, "bootstrap",
                  "--surface-sweep", "nonsense", "--scope", "task:Demo"])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertIn("nonsense", err.getvalue())
        self.assertIn("library", err.getvalue())

    def test_no_flag_means_no_starter_surfaces(self):
        code, _, err = _run_root(self.root, "init", "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        code, _, err = _run_root(self.root, "bootstrap", "--scope", "task:Demo")
        self.assertEqual(code, 0, err)
        self.assertEqual(self._titles(), set())


class TestNextOnAnEmptyRoadmap(unittest.TestCase):
    """`next` described an empty roadmap as fully blocked (audit F6).

    "Everything is either done, in-progress, or waiting on a dependency" is false when the roadmap
    holds zero items — and it is exactly the message a silently failed bootstrap produced, so the
    failure was reported to the reader as a healthy, fully-committed roadmap.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self._tmp.name, "docs", "roadmap", "roadmap.json")
        _run(self.json_path, "init", "--scope", "task:Demo")
        self.addCleanup(self._tmp.cleanup)

    def test_empty_roadmap_is_not_reported_as_blocked(self):
        code, out, _ = _run(self.json_path, "next")
        self.assertEqual(code, 0)
        self.assertNotIn("waiting on a dependency", out)

    def test_empty_roadmap_names_the_way_out(self):
        _, out, _ = _run(self.json_path, "next")
        self.assertIn("empty", out.lower())
        self.assertIn("bootstrap", out)

    def test_a_genuinely_blocked_roadmap_still_says_blocked(self):
        """The old message is right in its own case, and must survive."""
        _run(self.json_path, "add", "--title", "First", "--kind", "feature")
        _run(self.json_path, "add", "--title", "Second", "--kind", "feature",
             "--deps", "RM-0001")
        _run(self.json_path, "set", "RM-0001", "--status", "in-progress")
        code, out, _ = _run(self.json_path, "next")
        self.assertEqual(code, 0)
        self.assertIn("waiting on a dependency", out)


if __name__ == "__main__":
    unittest.main()
