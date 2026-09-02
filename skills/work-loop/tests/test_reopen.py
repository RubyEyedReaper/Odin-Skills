"""A `revise` outcome must not wedge its own session (harness:RM-0478, issue #877).

`revise` means *the approach is wrong; the contract needs changing*, and the skill's own
six-outcomes table says the loop ends and a revised one is re-opened. Before this suite the
ledger reached a state all three re-entry paths refused, and two of the refusals described
that one ledger with two different words:

    close  -> exit 3 | already closed with outcome 'revise'
    open   -> exit 3 | a ledger is already open for this session
    resume -> exit 3 | only a paused loop is resumable

`cmd_open` was the one command in the engine that dispatched on the ledger's EXISTENCE
rather than its status, and it was the one that wedged. These cases hold the fix to four
things: the re-open works, it keeps the predecessor, the predicates read only the current
contract's history, and the two commands never disagree about which state a ledger is in.
"""
from __future__ import annotations

import json
import re
import unittest

from ._fixtures import (
    LedgerRoot,
    SESSION,
    open_loop,
    read_ledger,
    revised_loop,
    run_cli,
    valid_contract,
)


class ReopenAfterRevise(unittest.TestCase):
    """Requirements 1 and 2: `open` decides on status, and keeps what it found."""

    def test_a_revised_loop_can_be_reopened_with_a_new_contract(self):
        with LedgerRoot() as root:
            revised_loop(root)
            contract = root.write_json(
                "revised.json", valid_contract(purpose="a different approach")
            )
            code, _, err = run_cli(
                "open", "--root", root.path, "--session", SESSION,
                "--contract", contract, "--json",
            )

            self.assertEqual(code, 0, err)
            ledger = read_ledger(root)
            self.assertEqual(ledger["status"], "open")
            self.assertIsNone(ledger["final_outcome"])
            self.assertEqual(ledger["contract"]["purpose"], "a different approach")

    def test_reopening_preserves_the_predecessors_terminal_state(self):
        """The history is the thing a revise exists to keep, which is why `--force` — which
        overwrites — was never the answer to this."""
        with LedgerRoot() as root:
            revised_loop(root)
            before = read_ledger(root)
            contract = root.write_json(
                "revised.json", valid_contract(purpose="a different approach")
            )

            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            ledger = read_ledger(root)
            self.assertEqual(len(ledger["epochs"]), 1)
            epoch = ledger["epochs"][0]
            self.assertEqual(epoch["final_outcome"], "revise")
            self.assertEqual(epoch["contract"]["purpose"], before["contract"]["purpose"])
            self.assertEqual(len(ledger["iterations"]), len(before["iterations"]))
            self.assertEqual(ledger["completed_actions"], before["completed_actions"])

    def test_an_open_ledger_is_still_refused(self):
        """The negative control. A fix that let `open` clobber a LIVE loop would pass every
        other case in this module."""
        with LedgerRoot() as root:
            open_loop(root)
            contract = root.write_json("second.json", valid_contract())

            code, _, err = run_cli(
                "open", "--root", root.path, "--session", SESSION, "--contract", contract
            )

            self.assertEqual(code, 3)
            self.assertIn("open", err)

    def test_force_still_overwrites_a_live_ledger(self):
        """`--force` keeps its destructive meaning for the corrupt ledger nobody wants; it
        stops being the only way to re-open a closed one."""
        with LedgerRoot() as root:
            open_loop(root)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "continue", "--action", "probe")
            contract = root.write_json("second.json", valid_contract())

            code, _, err = run_cli(
                "open", "--root", root.path, "--session", SESSION,
                "--contract", contract, "--force",
            )

            self.assertEqual(code, 0, err)
            self.assertEqual(read_ledger(root)["iterations"], [])

    def test_a_reopen_clears_a_pending_brief(self):
        """A brief's id hashes the contract's rubric. One that outlived its contract names a
        packet this engine would no longer assemble."""
        from ._fixtures import brief_for

        with LedgerRoot() as root:
            open_loop(root)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "revise", "--action", "rethink")
            brief_for(root)
            self.assertIsNotNone(read_ledger(root).get("pending_brief"))
            contract = root.write_json("revised.json", valid_contract())

            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            self.assertIsNone(read_ledger(root).get("pending_brief"))


class PredicatesScopeToTheCurrentEpoch(unittest.TestCase):
    """A revised contract is a different approach to the same work. Read across the
    revision, the predicates re-wedge the loop in a second way."""

    def test_a_state_hash_from_a_previous_epoch_does_not_fire_circular(self):
        with LedgerRoot() as root:
            revised_loop(root)                       # ends holding state s=2
            contract = root.write_json(
                "revised.json", valid_contract(purpose="a different approach")
            )
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            code, out, err = run_cli(
                "iterate", "--root", root.path, "--session", SESSION,
                "--outcome", "continue", "--action", "retry", "--state", "s=2", "--json",
            )

            self.assertEqual(code, 0, err)
            record = json.loads(out)
            self.assertIsNone(record["stall"])
            self.assertEqual(record["outcome"], "continue")

    def test_a_repeated_error_from_a_previous_epoch_does_not_count(self):
        with LedgerRoot() as root:
            open_loop(root)
            for state in ("s=1", "s=2"):
                run_cli("iterate", "--root", root.path, "--session", SESSION,
                        "--outcome", "continue", "--action", "try-" + state,
                        "--state", state, "--error", "connection refused on port 5432")
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "revise", "--action", "rethink")
            contract = root.write_json("revised.json", valid_contract())
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            code, out, err = run_cli(
                "iterate", "--root", root.path, "--session", SESSION,
                "--outcome", "continue", "--action", "retry-after-revise",
                "--error", "connection refused on port 5432", "--json",
            )

            self.assertEqual(code, 0, err)
            self.assertIsNone(json.loads(out)["stall"])

    def test_the_iteration_limit_counts_the_current_epoch_only(self):
        with LedgerRoot() as root:
            open_loop(root, iteration_limit=2)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "revise", "--action", "a1")
            contract = root.write_json("revised.json", valid_contract(iteration_limit=2))
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            code, out, err = run_cli(
                "iterate", "--root", root.path, "--session", SESSION,
                "--outcome", "continue", "--action", "a2", "--json",
            )

            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["outcome"], "continue")

    def test_every_iteration_record_carries_its_epoch(self):
        """`n` stays monotonic across a revise so `quality_from` keeps naming exactly one
        record; the epoch tag is what the predicates filter on."""
        with LedgerRoot() as root:
            revised_loop(root)
            contract = root.write_json("revised.json", valid_contract())
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "continue", "--action", "third")

            iterations = read_ledger(root)["iterations"]
            self.assertEqual([it["epoch"] for it in iterations], [1, 1, 2])
            self.assertEqual([it["n"] for it in iterations], [1, 2, 3])


class TheTwoCommandsAgree(unittest.TestCase):
    """Requirements 3 and 4: one writer of terminal state, and one reading of it."""

    def test_close_and_open_never_disagree_about_the_ledgers_state(self):
        """The contradiction the item was filed for. Over ONE unchanged ledger, `close` said
        *already closed* while `open` said *already open*. One of those was a lie whichever
        way the ledger read."""
        with LedgerRoot() as root:
            for drive in (open_loop, revised_loop):
                with self.subTest(drive=drive.__name__):
                    root.discard_ledger()
                    drive(root)
                    expected = read_ledger(root)["status"]
                    contract = root.write_json("probe.json", valid_contract())

                    _, _, open_err = run_cli(
                        "open", "--root", root.path, "--session", SESSION,
                        "--contract", contract,
                    )
                    root.discard_ledger()
                    drive(root)
                    _, _, close_err = run_cli(
                        "close", "--root", root.path, "--session", SESSION,
                        "--outcome", "complete",
                    )

                    for stream, name in ((open_err, "open"), (close_err, "close")):
                        if not stream.strip():
                            continue        # the command succeeded; it made no claim
                        # Parse the STATE CLAUSE, not any occurrence of the words. Both
                        # messages go on to name a way forward, and "open a revised
                        # contract" is advice rather than a claim about the ledger. The
                        # clause is generated from `ledger["status"]` by one renderer both
                        # commands call, which is what makes it parseable at all.
                        said = re.findall(r"ledger is (\w+)", stream)
                        self.assertEqual(
                            said, [expected],
                            "%s described the ledger as %s, not %s: %s"
                            % (name, said, expected, stream.strip()),
                        )

    def test_both_terminal_paths_write_the_same_shape(self):
        """A test that two implementations agree is weaker than one implementation both
        call. This asserts the former so the latter is what satisfies it."""
        terminal = ("status", "final_outcome", "close_note", "close_blocker",
                    "close_evidence", "close_recommended_next")

        with LedgerRoot() as root:
            open_loop(root)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "complete", "--action", "a1")
            by_iterate = read_ledger(root)

            root.discard_ledger()
            open_loop(root)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "continue", "--action", "a1")
            run_cli("close", "--root", root.path, "--session", SESSION, "--outcome", "complete")
            by_close = read_ledger(root)

            self.assertEqual([k for k in terminal if k in by_iterate],
                             [k for k in terminal if k in by_close])
            self.assertEqual(by_iterate["status"], by_close["status"])
            self.assertEqual(by_iterate["final_outcome"], by_close["final_outcome"])

    def test_an_escalate_by_iterate_records_its_blocker_where_close_records_one(self):
        """`blocker-record-check.sh` reads every ledger. Both paths must leave the blocker
        somewhere it looks, or a stop recorded by `iterate` reads as a stop that named
        nothing."""
        with LedgerRoot() as root:
            open_loop(root)
            run_cli(
                "iterate", "--root", root.path, "--session", SESSION,
                "--outcome", "escalate", "--action", "give-up",
                "--blocker", "the declared postgres dependency is unreachable",
                "--evidence", "pg_isready exited 2",
                "--recommended-next", "start the container, then re-open this contract",
            )

            ledger = read_ledger(root)
            self.assertEqual(ledger["close_blocker"],
                             "the declared postgres dependency is unreachable")
            self.assertEqual(ledger["close_evidence"], "pg_isready exited 2")
            self.assertEqual(ledger["close_recommended_next"],
                             "start the container, then re-open this contract")


class ResumeAcrossARevise(unittest.TestCase):
    """The brief's stated risk: `cmd_resume` keys on completed action ids, so whatever a
    re-open does must leave them intact."""

    def test_an_action_completed_before_a_revise_is_still_refused_after_it(self):
        with LedgerRoot() as root:
            revised_loop(root)                       # completed: probe, rethink
            contract = root.write_json("revised.json", valid_contract())
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)

            code, _, err = run_cli(
                "iterate", "--root", root.path, "--session", SESSION,
                "--outcome", "continue", "--action", "probe",
            )

            self.assertEqual(code, 5, err)

    def test_resume_after_a_revise_and_a_pause_re_enters_the_revised_contract(self):
        with LedgerRoot() as root:
            revised_loop(root)
            contract = root.write_json(
                "revised.json", valid_contract(purpose="a different approach")
            )
            run_cli("open", "--root", root.path, "--session", SESSION, "--contract", contract)
            run_cli("iterate", "--root", root.path, "--session", SESSION,
                    "--outcome", "pause", "--action", "checkpoint")

            code, out, err = run_cli(
                "resume", "--root", root.path, "--session", SESSION, "--json"
            )

            self.assertEqual(code, 0, err)
            payload = json.loads(out)
            self.assertEqual(payload["contract"]["purpose"], "a different approach")
            self.assertEqual(payload["next_iteration"], 4)
            self.assertIn("probe", payload["completed_actions"])


if __name__ == "__main__":
    unittest.main()
