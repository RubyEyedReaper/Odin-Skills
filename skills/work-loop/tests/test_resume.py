"""Resume — a fresh session performs zero actions the ledger already records as complete.

The primary testable core. The break: a session that dies mid-loop and whose successor
starts from the top, re-running every migration, re-opening every PR, re-sending every
message the first session already sent. An index counter cannot detect this — a ledger
written by a session that died mid-iteration has a counter that is either one too high
or one too low, with nothing to say which. A recorded set of completed action ids can.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import EXIT_CLOSED, EXIT_OK, EXIT_REPEAT, EXIT_USAGE


class ResumeReportsWhatIsDone(unittest.TestCase):
    def test_resume_returns_the_completed_actions(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db", "--action", "seed",
            )
            code, out, _ = fx.run_cli(
                "resume", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            self.assertEqual(code, EXIT_OK)
            payload = json.loads(out)
            self.assertEqual(payload["completed_actions"], ["migrate-db", "seed"])
            self.assertEqual(payload["next_iteration"], 2)

    def test_resume_of_an_unopened_ledger_is_a_usage_error(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.run_cli(
                "resume", "--root", root.path, "--session", "no-such-session"
            )
            self.assertEqual(code, EXIT_USAGE)
            self.assertIn("no-such-session", err)


class ZeroRepeatedActions(unittest.TestCase):
    """The exit criterion, asserted directly."""

    def test_a_completed_action_is_refused_not_repeated(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db",
            )
            before = fx.read_ledger(root)
            code, _, err = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db",
            )
            self.assertEqual(code, EXIT_REPEAT)
            self.assertIn("migrate-db", err)
            # Nothing was recorded: a refusal that still writes is not a refusal.
            self.assertEqual(fx.read_ledger(root), before)

    def test_a_batch_containing_one_completed_action_records_none_of_it(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db",
            )
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "seed", "--action", "migrate-db",
            )
            self.assertEqual(code, EXIT_REPEAT)
            self.assertEqual(
                fx.read_ledger(root)["completed_actions"], ["migrate-db"]
            )

    def test_a_successor_session_replaying_the_whole_plan_performs_only_the_rest(self):
        """The scenario the core exists for, end to end."""
        plan = ["migrate-db", "seed", "build", "publish"]
        with fx.LedgerRoot() as root:
            fx.open_loop(root, iteration_limit=20)
            # First session gets two steps in, then dies.
            for action in plan[:2]:
                fx.run_cli(
                    "iterate", "--root", root.path, "--session", fx.SESSION,
                    "--outcome", "continue", "--action", action, "--state", action,
                )
            # A fresh session resumes and walks the plan from the top.
            _, out, _ = fx.run_cli(
                "resume", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            done = set(json.loads(out)["completed_actions"])
            performed = []
            for action in plan:
                if action in done:
                    continue
                code, _, _ = fx.run_cli(
                    "iterate", "--root", root.path, "--session", fx.SESSION,
                    "--outcome", "continue", "--action", action, "--state", action,
                )
                self.assertEqual(code, EXIT_OK)
                performed.append(action)
            self.assertEqual(performed, ["build", "publish"])
            self.assertEqual(fx.read_ledger(root)["completed_actions"], plan)


class ResumeIgnoresTheCounter(unittest.TestCase):
    """Resume keys on completed action ids, never on an index — held against the richer record.

    NOT A NEVER-RED TEST BY ACCIDENT. The property is one the engine already had; this case
    exists so that harness:RM-0468's additions to the record cannot quietly break it. It was
    written green on purpose, and mutating `cmd_resume` to compute its answer from
    `len(iterations)` turns it red — which is what makes it load-bearing rather than
    decorative.
    """

    def test_resume_reads_action_ids_when_the_counter_is_wrong(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db",
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "pause", "--action", "seed-fixtures",
            )

            # A session that died mid-iteration leaves a counter that is either one too
            # high or one too low, with nothing in the ledger to say which. Corrupt it in
            # both directions at once.
            ledger = fx.read_ledger(root)
            ledger["iterations"][0]["n"] = 7
            ledger["iterations"][1]["n"] = 1
            with open(root.ledger_path(), "w", encoding="utf-8") as handle:
                json.dump(ledger, handle)

            code, out, _ = fx.run_cli(
                "resume", "--root", root.path, "--session", fx.SESSION, "--json"
            )
            self.assertEqual(code, EXIT_OK)
            payload = json.loads(out)
            self.assertEqual(
                sorted(payload["completed_actions"]), ["migrate-db", "seed-fixtures"]
            )

            # And each of them is still refused rather than repeated.
            for action in ("migrate-db", "seed-fixtures"):
                code, _, err = fx.run_cli(
                    "iterate", "--root", root.path, "--session", fx.SESSION,
                    "--outcome", "continue", "--action", action,
                )
                self.assertEqual(code, EXIT_REPEAT)
                self.assertIn(action, err)


class ResumingAPausedLoop(unittest.TestCase):
    """`pause` ends the loop and checkpoints; `resume` is how a later session re-enters."""

    def test_resume_reopens_a_paused_ledger(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "migrate-db",
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "pause", "--note", "context past half the ceiling",
            )
            self.assertEqual(fx.read_ledger(root)["status"], "closed")

            code, _, _ = fx.run_cli(
                "resume", "--root", root.path, "--session", fx.SESSION
            )
            self.assertEqual(code, EXIT_OK)
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["status"], "open")
            self.assertIsNone(ledger["final_outcome"])
            self.assertEqual(ledger["completed_actions"], ["migrate-db"])
            self.assertEqual(ledger["resumed"], 1)

            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "seed",
            )
            self.assertEqual(code, EXIT_OK)

    def test_resume_refuses_to_reopen_a_completed_loop(self):
        for outcome, extra in (
            ("complete", []),
            ("stop", []),
            (
                "escalate",
                [
                    "--blocker", "the credential the contract declares is absent",
                    "--evidence", "gh auth status exited 1",
                    "--recommended-next", "capture a roadmap item",
                ],
            ),
        ):
            with self.subTest(outcome=outcome), fx.LedgerRoot() as root:
                fx.open_loop(root)
                fx.run_cli(
                    "iterate", "--root", root.path, "--session", fx.SESSION,
                    "--outcome", outcome, *extra
                )
                code, _, _ = fx.run_cli(
                    "resume", "--root", root.path, "--session", fx.SESSION
                )
                self.assertEqual(code, EXIT_CLOSED)
                self.assertEqual(fx.read_ledger(root)["status"], "closed")


class TheLedgerPath(unittest.TestCase):
    def test_the_ledger_is_session_keyed_under_the_declared_runtime_class(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            import os

            expected = os.path.join(
                root.path, ".claude", ".runtime", "work-loop", fx.SESSION + ".json"
            )
            self.assertTrue(os.path.exists(expected))

    def test_two_sessions_do_not_share_a_ledger(self):
        with fx.LedgerRoot() as root:
            fx.run_cli(
                "open", "--root", root.path, "--session", "sess-a",
                "--contract", _write_contract(root, "sess-a"),
            )
            fx.run_cli(
                "open", "--root", root.path, "--session", "sess-b",
                "--contract", _write_contract(root, "sess-b"),
            )
            fx.run_cli(
                "iterate", "--root", root.path, "--session", "sess-a",
                "--outcome", "continue", "--action", "only-a",
            )
            self.assertEqual(
                fx.read_ledger(root, "sess-a")["completed_actions"], ["only-a"]
            )
            self.assertEqual(fx.read_ledger(root, "sess-b")["completed_actions"], [])

    def test_the_root_is_never_inferred_from_the_working_directory(self):
        code, _, err = fx.run_cli("status", "--session", fx.SESSION)
        self.assertNotEqual(code, EXIT_OK)
        self.assertIn("--root", err)


def _write_contract(root, session):
    import os

    path = os.path.join(root.path, session + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(fx.valid_contract(), handle)
    return path


if __name__ == "__main__":
    unittest.main()
