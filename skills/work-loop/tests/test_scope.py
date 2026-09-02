"""A critic packet declares what it covers, or says that it does not.

`brief` refused a diff it could not read and a diff that was empty. It could not tell a
**partial** diff from a complete one — and a partial diff is the shape a builder produces by
accident. Observed on the critic pass's own second use: a packet assembled from
`git show <sha> -- one/file.py` for a commit touching four files. Readable, non-empty, exit 0,
and a `brief_id` that makes the resulting verdict look like a review of the whole commit.

The check is a cross-check, never a derivation. The engine does not run `git`: a subprocess
spawned from inside `loop.py` is not a tool call, so it would sit outside every always-on
PreToolUse guard (ADR-0143, extended here by DEC-0093). The caller runs the scope command
through its own tool path and hands over the transcript, exactly as `--baseline-evidence`
already takes a measurement transcript.

**What a declared scope proves, and what it does not.** It proves the diff covers every path a
transcript named. It does not prove the transcript describes the change under review — a caller
can hand over the stat block of a different commit. Nothing in a non-executing engine can close
that, and the residue is stated here, in `references/critic-pass.md`, and in the ADR rather than
left for a reader to find.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import (
    EXIT_INCOMPLETE,
    EXIT_OK,
    EXIT_UNREADABLE,
    declared_paths,
    diff_paths,
)

GIT_DIFF = (
    "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n@@ -1 +1 @@\n-a\n+b\n"
    "diff --git a/two.md b/two.md\n--- a/two.md\n+++ b/two.md\n@@ -1 +1 @@\n-c\n+d\n"
)
ONE_FILE_DIFF = (
    "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n@@ -1 +1 @@\n-a\n+b\n"
)
TWO_FILE_STAT = " one.py | 2 +-\n two.md | 2 +-\n 2 files changed, 2 insertions(+), 2 deletions(-)\n"
ONE_FILE_STAT = " one.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n"

#: The observed shape: a stat block naming four files, one of which `--stat` abbreviated.
FOUR_FILE_STAT = (
    " .claude/skills/work-loop/scripts/loop.py        | 206 ++++++++++-\n"
    " .claude/skills/work-loop/tests/_fixtures.py     |  12 +-\n"
    " .../work-loop/tests/test_baseline_provenance.py | 184 ++++++++++\n"
    " .claude/skills/work-loop/tests/test_rubric.py   | 124 +++++++++\n"
    " 4 files changed, 518 insertions(+), 8 deletions(-)\n"
)


def _diff_for(*paths):
    """A minimal but well-formed git diff touching each named path."""
    return "".join(
        "diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-a\n+b\n" % (p, p, p, p)
        for p in paths
    )


def _brief(root, diff=GIT_DIFF, verification="Ran 152 tests\n\nOK\n", scope=None,
           scope_path=None, session=fx.SESSION):
    """Emit a brief and return (code, packet-or-None, stderr).

    `scope` writes a transcript into the throwaway root; `scope_path` passes a path
    verbatim, which is how the unreadable case is exercised without a file existing.
    """
    argv = [
        "brief", "--root", root.path, "--session", session,
        "--diff-file", root.write("change.diff", diff),
        "--verification-file", root.write("suite.txt", verification),
        "--json",
    ]
    if scope is not None:
        argv += ["--change-scope", root.write("scope.txt", scope)]
    elif scope_path is not None:
        argv += ["--change-scope", scope_path]
    code, out, err = fx.run_cli(*argv)
    return code, (json.loads(out) if code == EXIT_OK else None), err


class ADiffNamesItsOwnPaths(unittest.TestCase):
    """`diff_paths` reads the packet's diff — the only side the engine always has."""

    def test_a_git_diff_yields_every_touched_path(self):
        self.assertEqual(diff_paths(GIT_DIFF), ["one.py", "two.md"])

    def test_a_deletion_resolves_to_the_removed_path(self):
        text = "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n"
        self.assertEqual(diff_paths(text), ["gone.py"])

    def test_an_addition_resolves_to_the_created_path(self):
        text = "diff --git a/new.py b/new.py\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+a\n"
        self.assertEqual(diff_paths(text), ["new.py"])

    def test_a_plain_unified_diff_without_git_headers_is_read(self):
        text = "--- a/plain.txt\n+++ b/plain.txt\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(diff_paths(text), ["plain.txt"])

    def test_text_carrying_no_diff_headers_yields_nothing(self):
        # A verification log handed to --diff-file by mistake names no paths, and the
        # refusal that follows says so rather than reporting a mysterious mismatch.
        self.assertEqual(diff_paths("Ran 152 tests in 1.7s\n\nOK\n"), [])


class ATranscriptNamesTheChange(unittest.TestCase):
    """`declared_paths` reads what the caller's own command printed."""

    def test_a_stat_transcript_yields_its_paths(self):
        self.assertEqual(
            declared_paths(TWO_FILE_STAT), ["one.py", "two.md"]
        )

    def test_the_summary_line_is_not_a_path(self):
        for path in declared_paths(FOUR_FILE_STAT):
            self.assertNotIn("files changed", path)

    def test_an_abbreviated_path_is_preserved_verbatim(self):
        # Resolving the abbreviation is the comparison's job, not the parser's: the parser
        # has no diff to resolve it against, and a guess here would be invisible later.
        self.assertIn(
            ".../work-loop/tests/test_baseline_provenance.py",
            declared_paths(FOUR_FILE_STAT),
        )

    def test_a_name_only_transcript_yields_its_paths(self):
        self.assertEqual(declared_paths("one.py\ntwo.md\n"), ["one.py", "two.md"])

    def test_a_rename_yields_the_destination(self):
        self.assertEqual(declared_paths(" old.py => new.py | 0\n"), ["new.py"])

    def test_a_braced_rename_yields_the_destination_path(self):
        self.assertEqual(
            declared_paths(" src/{old => new}/x.py | 2 +-\n"), ["src/new/x.py"]
        )

    def test_a_braced_rename_into_the_parent_collapses_the_separator(self):
        self.assertEqual(declared_paths(" src/{old => }x.py | 2 +-\n"), ["src/x.py"])

    def test_a_binary_stat_line_is_a_path(self):
        self.assertEqual(declared_paths(" logo.png | Bin 0 -> 12 bytes\n"), ["logo.png"])

    def test_an_empty_transcript_yields_nothing(self):
        self.assertEqual(declared_paths("\n  \n"), [])

    def test_a_whole_git_show_stat_transcript_yields_only_its_paths(self):
        # The shape a caller actually produces. `git show <sha> --stat` prints the commit
        # header and the message body ABOVE the stat block, and reading those as paths
        # turned the first live run of this check into 22 findings, 19 of them prose.
        text = (
            "commit c6a7186e209227d59172d1d8acd4f47dd4227a5e\n"
            "Author: Ruby <someone@example.com>\n"
            "Date:   Wed Sep 2 14:56:50 2026 -0400\n"
            "\n"
            "    feat(work-loop): inspect a rubric's evidence commands\n"
            "\n"
            "    Suite 129 -> 152.\n"
            "\n"
            "    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "\n"
            " one.py | 2 +-\n"
            " 1 file changed, 1 insertion(+), 1 deletion(-)\n"
        )
        self.assertEqual(declared_paths(text), ["one.py"])

    def test_a_git_show_name_only_transcript_yields_only_its_paths(self):
        # Same header, no stat column — so the header must be recognised in its own right
        # rather than only crowded out by the presence of stat lines.
        text = (
            "commit c6a7186e209227d59172d1d8acd4f47dd4227a5e\n"
            "Author: Ruby <someone@example.com>\n"
            "Date:   Wed Sep 2 14:56:50 2026 -0400\n"
            "\n"
            "    feat(work-loop): inspect a rubric's evidence commands\n"
            "\n"
            "one.py\n"
            "two.md\n"
        )
        self.assertEqual(declared_paths(text), ["one.py", "two.md"])

    def test_a_merge_header_line_is_not_a_path(self):
        text = "commit abc1234\nMerge: 111aaa 222bbb\nAuthor: R <r@example.com>\n\none.py\n"
        self.assertEqual(declared_paths(text), ["one.py"])


class TheDiffMustCoverTheDeclaredChange(unittest.TestCase):
    """The refusal, in the shape the defect was observed in."""

    def test_a_partial_diff_is_refused_against_its_declared_scope(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(
                root,
                diff=_diff_for(".claude/skills/work-loop/scripts/loop.py"),
                scope=FOUR_FILE_STAT,
            )
            self.assertEqual(code, EXIT_INCOMPLETE, err)
            self.assertIn("test_rubric.py", err)
            self.assertIn("_fixtures.py", err)

    def test_a_refused_brief_leaves_no_pending_brief_behind(self):
        # A refusal that still armed a brief would let the next iterate record a verdict
        # bound to the packet the engine had just declined to assemble.
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _brief(root, diff=ONE_FILE_DIFF, scope=TWO_FILE_STAT)
            self.assertIsNone(fx.read_ledger(root).get("pending_brief"))

    def test_a_complete_diff_is_accepted_and_records_verified_provenance(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, packet, err = _brief(root, diff=GIT_DIFF, scope=TWO_FILE_STAT)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(packet["scope"]["provenance"], "verified")
            self.assertEqual(packet["scope"]["declared_paths"], ["one.py", "two.md"])

    def test_an_abbreviated_stat_path_is_resolved_by_suffix(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(
                root,
                diff=_diff_for(
                    ".claude/skills/work-loop/scripts/loop.py",
                    ".claude/skills/work-loop/tests/_fixtures.py",
                    ".claude/skills/work-loop/tests/test_baseline_provenance.py",
                    ".claude/skills/work-loop/tests/test_rubric.py",
                ),
                scope=FOUR_FILE_STAT,
            )
            self.assertEqual(code, EXIT_OK, err)

    def test_an_abbreviated_path_matching_two_diff_paths_is_refused_as_ambiguous(self):
        # A suffix match that accepted on any hit would turn an abbreviation into a false
        # ACCEPT — the failure direction this item exists to prevent.
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(
                root,
                diff=_diff_for("first/pkg/mod.py", "second/pkg/mod.py"),
                scope=" .../pkg/mod.py | 2 +-\n",
            )
            self.assertEqual(code, EXIT_INCOMPLETE, err)
            self.assertIn("ambiguous", err)

    def test_a_diff_covering_more_than_declared_is_accepted_and_the_extra_recorded(self):
        # Not the observed defect, and not refused. A critic reading a packet whose diff
        # exceeds its declared scope should still be told which paths were undeclared.
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, packet, err = _brief(root, diff=GIT_DIFF, scope=ONE_FILE_STAT)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(packet["scope"]["undeclared_paths"], ["two.md"])


class TheResidueIsRecordedWhenNoScopeIsDeclared(unittest.TestCase):
    """Absent is not silent: the flag stays optional, and the packet says what is unchecked."""

    def test_a_brief_without_a_scope_records_unverified_provenance(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, packet, err = _brief(root)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(packet["scope"]["provenance"], "unverified")
            self.assertIsNone(packet["scope"]["declared_paths"])

    def test_the_packet_always_names_the_diff_paths_it_did_find(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            self.assertEqual(packet["scope"]["diff_paths"], ["one.py", "two.md"])

    def test_the_asks_tell_the_critic_to_read_the_scope_block(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            self.assertTrue(
                any("scope" in ask for ask in packet["asks"]),
                "the critic reads the asks, so the residue has to be named there too",
            )


class AnUnreadableScopeIsTheEightKind(unittest.TestCase):
    """The transcript is an input the packet needs — the same failure as an unreadable diff."""

    def test_an_unreadable_scope_transcript_exits_eight(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(root, scope_path="/nonexistent/scope.txt")
            self.assertEqual(code, EXIT_UNREADABLE, err)
            self.assertIn("/nonexistent/scope.txt", err)

    def test_an_empty_scope_transcript_exits_eight(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(root, scope="\n   \n")
            self.assertEqual(code, EXIT_UNREADABLE, err)

    def test_a_transcript_naming_no_paths_is_refused_rather_than_read_as_empty_scope(self):
        # A non-empty file that parses to zero paths is a caller who passed the wrong file.
        # Read as "nothing declared" it would silently downgrade to today's behaviour.
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(root, scope="Ran 152 tests in 1.7s\n\nOK\n")
            self.assertEqual(code, EXIT_INCOMPLETE, err)


class TheDeclaredScopeIsPartOfTheBinding(unittest.TestCase):
    """The id hashes what the critic will be shown, and the scope block is shown."""

    def test_the_declared_scope_changes_the_brief_id(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, scoped, _ = _brief(root, diff=GIT_DIFF, scope=TWO_FILE_STAT)
            _, unscoped, _ = _brief(root, diff=GIT_DIFF)
            self.assertNotEqual(scoped["brief_id"], unscoped["brief_id"])

    def test_two_briefs_with_the_same_scope_share_an_id(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, first, _ = _brief(root, diff=GIT_DIFF, scope=TWO_FILE_STAT)
            _, second, _ = _brief(root, diff=GIT_DIFF, scope=TWO_FILE_STAT)
            self.assertEqual(first["brief_id"], second["brief_id"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
