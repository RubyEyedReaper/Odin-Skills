"""The staleness pass — how a record is re-verified, demoted, or retired.

The primary testable core: `verified-by` names a *command*, and a pass over it produces a
named outcome rather than an opinion. A date says someone looked; a command says what
would have to be re-run to look again, and these cases are the difference showing up as
behaviour.

The second core is the one that keeps the pass safe to run: **reading a record must never
execute the command inside it.** Execution is opt-in, and the case that proves it is a
record whose command would leave a file behind.
"""
from __future__ import annotations

import json
import os
import unittest

from . import _fixtures as fx
from scripts.capture_bar import (
    EXIT_ACCEPT,
    EXIT_DEMOTED,
    EXIT_MALFORMED,
    EXIT_RETIRED,
    EXIT_USAGE,
    TIERS,
)


def verify(root, *, run=False, today="2026-08-27", max_age=180, **fields):
    path = os.path.join(root.path, "record.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(fields, handle)
    argv = [
        "verify", "--record", path,
        "--cwd", root.path,
        "--today", today,
        "--max-age-days", str(max_age),
    ]
    if run:
        argv.append("--run")
    return fx.run_cli(*argv)


class TheLadder(unittest.TestCase):
    """Five rungs, ordered, floor first."""

    def test_there_are_exactly_five_tiers(self):
        self.assertEqual(len(TIERS), 5)

    def test_the_floor_is_first_and_the_ceiling_is_last(self):
        self.assertEqual(TIERS[0], "asserted")
        self.assertEqual(TIERS[-1], "enforced")

    def test_the_ladder_is_reported_by_its_own_subcommand(self):
        code, out, _ = fx.run_cli("tiers")
        self.assertEqual(code, EXIT_ACCEPT)
        payload = json.loads(out)
        self.assertEqual([t["tier"] for t in payload["tiers"]], list(TIERS))
        for tier in payload["tiers"]:
            self.assertTrue(tier["promoted_by"])
            self.assertTrue(tier["demoted_by"])


class Refresh(unittest.TestCase):
    """The command still passes: the rung holds and the date moves."""

    def test_a_passing_command_refreshes_and_holds_the_tier(self):
        with fx.Root() as root:
            code, out, _ = verify(
                root, run=True,
                title="t", body="b",
                confidence="reproduced",
                verified_by="true",
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_ACCEPT)
            payload = json.loads(out)
            self.assertEqual(payload["outcome"], "refresh")
            self.assertEqual(payload["confidence"], "reproduced")
            self.assertEqual(payload["verified_on"], "2026-08-27")


class Demote(unittest.TestCase):
    """The evidence for the rung no longer holds."""

    def test_a_failing_command_demotes_one_rung(self):
        with fx.Root() as root:
            code, out, err = verify(
                root, run=True,
                title="t", body="b",
                confidence="enforced",
                verified_by="false",
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_DEMOTED)
            payload = json.loads(out)
            self.assertEqual(payload["outcome"], "demote")
            self.assertEqual(payload["confidence"], "gated")
            self.assertIn("exit", err)

    def test_an_unresolvable_command_demotes_to_observed(self):
        """The fact may still be true; what is gone is the ability to re-check it."""
        with fx.Root() as root:
            code, out, _ = verify(
                root, run=True,
                title="t", body="b",
                confidence="gated",
                verified_by="odin-definitely-not-a-real-command-xyz",
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_DEMOTED)
            payload = json.loads(out)
            self.assertEqual(payload["confidence"], "observed")
            self.assertEqual(payload["reason"], "unresolvable")

    def test_demotion_moves_exactly_one_rung_from_the_top(self):
        with fx.Root() as root:
            _, out, _ = verify(
                root, run=True, title="t", body="b",
                confidence="reproduced", verified_by="false", verified_on="2026-08-01",
            )
            self.assertEqual(json.loads(out)["confidence"], "observed")


class Retire(unittest.TestCase):
    """Demotion at the floor is retirement, and it carries its reason."""

    def test_a_failing_command_on_the_floor_rung_retires_the_record(self):
        with fx.Root() as root:
            code, out, _ = verify(
                root, run=True,
                title="t", body="b",
                confidence="asserted",
                verified_by="false",
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_RETIRED)
            payload = json.loads(out)
            self.assertEqual(payload["outcome"], "retire")
            self.assertTrue(payload["reason"])


class ExecutionIsOptIn(unittest.TestCase):
    """Reading a record never runs the command inside it."""

    def test_the_default_pass_executes_nothing(self):
        with fx.Root() as root:
            sentinel = os.path.join(root.path, "sentinel")
            code, out, _ = verify(
                root,
                title="t", body="b",
                confidence="gated",
                verified_by="touch " + sentinel,
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_ACCEPT)
            self.assertFalse(os.path.exists(sentinel), "the default pass executed the command")
            payload = json.loads(out)
            self.assertIsNone(payload["outcome"])
            self.assertEqual(payload["would_run"], "touch " + sentinel)

    def test_opting_in_does_execute(self):
        with fx.Root() as root:
            sentinel = os.path.join(root.path, "sentinel")
            verify(
                root, run=True,
                title="t", body="b",
                confidence="gated",
                verified_by="touch " + sentinel,
                verified_on="2026-08-01",
            )
            self.assertTrue(os.path.exists(sentinel))


class AgeFlagsButNeverDemotes(unittest.TestCase):
    """A date says someone looked. It is never, on its own, evidence that they should not
    have — so age flags a record and the command decides its rung."""

    def test_an_old_record_whose_command_passes_keeps_its_tier(self):
        with fx.Root() as root:
            code, out, _ = verify(
                root, run=True, max_age=30,
                title="t", body="b",
                confidence="enforced",
                verified_by="true",
                verified_on="2020-01-01",
            )
            self.assertEqual(code, EXIT_ACCEPT)
            payload = json.loads(out)
            self.assertTrue(payload["stale"])
            self.assertEqual(payload["confidence"], "enforced")
            self.assertEqual(payload["outcome"], "refresh")

    def test_a_recent_record_is_not_stale(self):
        with fx.Root() as root:
            _, out, _ = verify(
                root, max_age=30,
                title="t", body="b",
                confidence="gated",
                verified_by="true",
                verified_on="2026-08-20",
            )
            payload = json.loads(out)
            self.assertFalse(payload["stale"])
            self.assertEqual(payload["age_days"], 7)


class NothingToReRun(unittest.TestCase):
    """The floor rungs may carry no command. Say so; do not invent an outcome."""

    def test_a_rung_with_no_command_reports_that_it_cannot_be_re_checked(self):
        with fx.Root() as root:
            code, out, err = verify(
                root, run=True, title="t", body="b", confidence="observed",
            )
            self.assertEqual(code, EXIT_ACCEPT)
            payload = json.loads(out)
            self.assertIsNone(payload["outcome"])
            self.assertIn("no verifying command", err)


class Malformed(unittest.TestCase):
    """A rung above `observed` without its two fields is malformed, not merely stale."""

    def test_a_command_requiring_rung_without_a_command_is_malformed(self):
        with fx.Root() as root:
            code, _, err = verify(
                root, title="t", body="b", confidence="gated", verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_MALFORMED)
            self.assertIn("verified_by", err)

    def test_a_command_requiring_rung_without_a_date_is_malformed(self):
        with fx.Root() as root:
            code, _, err = verify(
                root, title="t", body="b", confidence="reproduced", verified_by="true",
            )
            self.assertEqual(code, EXIT_MALFORMED)
            self.assertIn("verified_on", err)

    def test_an_unknown_tier_is_malformed(self):
        with fx.Root() as root:
            code, _, err = verify(
                root, title="t", body="b", confidence="fairly-sure", verified_by="true",
                verified_on="2026-08-01",
            )
            self.assertEqual(code, EXIT_MALFORMED)
            self.assertIn("fairly-sure", err)

    def test_an_unparseable_date_is_malformed(self):
        with fx.Root() as root:
            code, _, err = verify(
                root, title="t", body="b", confidence="gated", verified_by="true",
                verified_on="last tuesday",
            )
            self.assertEqual(code, EXIT_MALFORMED)
            self.assertIn("verified_on", err)

    def test_a_missing_record_file_is_a_usage_error(self):
        with fx.Root() as root:
            code, _, _ = fx.run_cli(
                "verify", "--record", os.path.join(root.path, "absent.json")
            )
            self.assertEqual(code, EXIT_USAGE)


class TheIndexMarker(unittest.TestCase):
    """The two fields are rendered short enough for the always-loaded memory index.

    The index has a 300-character-per-line ceiling because it is read whole into every
    session in its scope. The command — the long half — lives on the record; the index
    carries the tier and the date only.
    """

    def test_the_marker_is_the_tier_and_the_date_and_not_the_command(self):
        with fx.Root() as root:
            _, out, _ = verify(
                root, title="t", body="b",
                confidence="enforced",
                verified_by="bash .claude/scripts/ci-local.sh --fast",
                verified_on="2026-08-01",
            )
            marker = json.loads(out)["index_marker"]
            self.assertIn("enforced", marker)
            self.assertIn("2026-08-01", marker)
            self.assertNotIn("ci-local", marker)

    def test_the_longest_marker_leaves_the_index_line_under_its_ceiling(self):
        longest = max(len("· %s %s" % (t, "2026-08-27")) for t in TIERS)
        self.assertLess(longest, 30)


if __name__ == "__main__":
    unittest.main()
