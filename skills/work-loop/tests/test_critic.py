"""The critic pass — a verdict the builder cannot author.

Fresh-context critique already existed in this harness; what did not exist was a verdict the
*engine* controls the channel for. Wave 2 accepted `--critic-verdict PASS` from the same
call that recorded the work — which is a self-assessment with a field name on it.

The binding is modest and mechanical, and the honesty about its limit is part of the
design: **no predicate over repository state can prove that a different context produced a
verdict.** What is checkable is that the verdict is bound to a packet the engine assembled
from the actual diff, the actual verification output and the contract's own rubric, and
that no verdict can be written without one. The fresh context itself is held by dispatching
`adversarial-reviewer` — a review criterion, named as such in references/critic-pass.md
rather than dressed up as a gate.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import (
    CRITIC_VERDICTS,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_UNREADABLE,
)

DIFF = "--- a/scripts/loop.py\n+++ b/scripts/loop.py\n+one added line\n"
VERIFICATION = "Ran 88 tests in 0.773s\n\nOK\n"


def _iterate(root, *extra, session=fx.SESSION, outcome="continue", action="a"):
    return fx.run_cli(
        "iterate", "--root", root.path, "--session", session,
        "--outcome", outcome, "--action", action, *extra,
    )


def _brief(root, diff=DIFF, verification=VERIFICATION, session=fx.SESSION):
    """Emit a brief and return (code, packet-or-None, stderr)."""
    diff_file = root.write("change.diff", diff)
    ver_file = root.write("suite.txt", verification)
    code, out, err = fx.run_cli(
        "brief", "--root", root.path, "--session", session,
        "--diff-file", diff_file, "--verification-file", ver_file, "--json",
    )
    return code, (json.loads(out) if code == EXIT_OK else None), err


class TheBriefIsThePacket(unittest.TestCase):
    """The critic receives the artifacts and the rubric — never the builder's summary."""

    def test_the_brief_carries_the_rubric_and_both_artifacts(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, packet, err = _brief(root)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("+one added line", packet["diff"])
            self.assertIn("Ran 88 tests", packet["verification"])
            self.assertEqual(len(packet["rubric"]), 4)
            self.assertEqual(packet["verdicts"], list(CRITIC_VERDICTS))
            self.assertTrue(packet["brief_id"])

    def test_the_packet_carries_no_field_the_builder_supplied(self):
        """Every key is the engine's: the two artifacts, the rubric, the vocabulary, the
        asks. A `summary` or `rationale` key would be the builder's case for its own work,
        which is exactly what a critic must not receive."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            self.assertEqual(
                sorted(packet),
                ["asks", "baseline", "brief_id", "diff", "rubric", "verdicts", "verification"],
            )

    def test_an_unreadable_diff_is_refused_and_names_the_file(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            ver = root.write("suite.txt", VERIFICATION)
            code, _, err = fx.run_cli(
                "brief", "--root", root.path, "--session", fx.SESSION,
                "--diff-file", root.path + "/absent.diff",
                "--verification-file", ver, "--json",
            )
            self.assertEqual(code, EXIT_UNREADABLE)
            self.assertIn("absent.diff", err)
            self.assertIsNone(fx.read_ledger(root).get("pending_brief"))

    def test_an_unreadable_verification_file_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            diff = root.write("change.diff", DIFF)
            code, _, err = fx.run_cli(
                "brief", "--root", root.path, "--session", fx.SESSION,
                "--diff-file", diff,
                "--verification-file", root.path + "/absent.txt", "--json",
            )
            self.assertEqual(code, EXIT_UNREADABLE)
            self.assertIn("absent.txt", err)

    def test_an_empty_diff_is_refused(self):
        """A critic pass over no change is a verdict about nothing — the same defect as an
        unreadable file, arrived at from the other side."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _brief(root, diff="   \n")
            self.assertEqual(code, EXIT_UNREADABLE)
            self.assertIn("empty", err.lower())

    def test_the_digest_is_stable_for_one_packet_and_differs_for_another(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, first, _ = _brief(root)
            _, again, _ = _brief(root)
            _, other, _ = _brief(root, diff=DIFF + "+a second line\n")
            self.assertEqual(first["brief_id"], again["brief_id"])
            self.assertNotEqual(first["brief_id"], other["brief_id"])

    def test_the_ledger_holds_the_pending_brief(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            self.assertEqual(
                fx.read_ledger(root)["pending_brief"]["brief_id"], packet["brief_id"]
            )


class ABuilderAuthoredVerdictCannotBeWritten(unittest.TestCase):
    """The property this item exists for.

    Wave 2 accepted a verdict from the call that recorded the work. It no longer does.
    """

    NEXT = ("--critic-next", "measure the suite's wall clock before adding a gate")

    def test_a_verdict_with_no_brief_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "PASS", *self.NEXT,
                "--evidence-path", "logs/ci.log",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("critic-brief", err)
            self.assertEqual(fx.read_ledger(root)["iterations"], [])

    def test_a_brief_id_the_engine_never_emitted_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _brief(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "PASS", *self.NEXT,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", "deadbeefdeadbeef",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("deadbeefdeadbeef", err)
            self.assertEqual(fx.read_ledger(root)["iterations"], [])

    def test_a_brief_with_no_pending_brief_at_all_is_refused(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "PASS", *self.NEXT,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", "0123456789abcdef",
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("no brief", err.lower())

    def test_a_verdict_with_no_next_improvement_is_refused(self):
        """The critic names the single most valuable next improvement. An obligation
        nobody enforces is indistinguishable from one nobody has."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "PASS",
                "--evidence-path", "logs/ci.log",
                "--critic-brief", packet["brief_id"],
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("critic-next", err)

    def test_a_bound_verdict_is_recorded_with_its_brief(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            code, _, err = _iterate(
                root, "--critic-verdict", "REVISE", *self.NEXT,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", packet["brief_id"],
            )
            self.assertEqual(code, EXIT_OK, err)
            ledger = fx.read_ledger(root)
            record = ledger["iterations"][0]
            self.assertEqual(record["critic_verdict"], "REVISE")
            self.assertEqual(record["critic_brief"], packet["brief_id"])
            self.assertIsNone(ledger.get("pending_brief"))

    def test_a_brief_is_single_use(self):
        """A verdict is about one change. Re-using a brief attaches change N's judgment to
        change N+1 — a stale verdict wearing a fresh timestamp."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            _, packet, _ = _brief(root)
            first, _, _ = _iterate(
                root, "--critic-verdict", "PASS", *self.NEXT,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", packet["brief_id"], action="a",
            )
            second, _, err = _iterate(
                root, "--critic-verdict", "PASS", *self.NEXT,
                "--evidence-path", "logs/ci.log",
                "--critic-brief", packet["brief_id"], action="b",
            )
            self.assertEqual(first, EXIT_OK)
            self.assertEqual(second, EXIT_INVALID)
            self.assertIn("no brief", err.lower())
            self.assertEqual(len(fx.read_ledger(root)["iterations"]), 1)

    def test_an_iteration_with_no_verdict_needs_no_brief(self):
        """The obligation runs one way. An ordinary iteration is unaffected by this wave."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = _iterate(root, "--evidence-path", "logs/ci.log")
            self.assertEqual(code, EXIT_OK, err)
            self.assertIsNone(fx.read_ledger(root)["iterations"][0]["critic_verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
