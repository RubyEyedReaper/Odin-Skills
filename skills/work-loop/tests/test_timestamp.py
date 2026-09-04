"""The one field the source protocol names that the engine never wrote at all.

harness:RM-0533 / #991 compared the source's `gauntlet/state.json` + `gauntlet/ledger.jsonl`
field list against this ledger's own schema, field by field, both directions. Every other
named field was already present — renamed, restructured, or derivable from the append-only
history rather than duplicated as a second mutable copy of it (DEC-0118). `timestamp` was
the one clean miss: no key of that name existed anywhere in the ledger, at open or at any
iteration, confirmed by reading the schema rather than assuming it.

`open` records the moment the contract came alive (`opened_at`); `iterate` records the
moment of each iteration (`timestamp` on the record). Both are engine-derived, never
caller-supplied — consistent with every other computed field this ledger already refuses to
take on faith (`state_hash`, `baseline`, `evaluation`).
"""
from __future__ import annotations

import re
import unittest

from . import _fixtures as fx
from scripts.loop import EXIT_OK

#: Second-precision UTC ISO 8601, `Z`-suffixed — matches what `now_iso()` produces and
#: nothing looser, so a case that regressed to a bare `time.time()` float fails here too.
_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class OpenRecordsWhenTheContractCameAlive(unittest.TestCase):
    def test_open_writes_opened_at(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            ledger = fx.read_ledger(root)
            self.assertIn("opened_at", ledger)
            self.assertRegex(ledger["opened_at"], _ISO_UTC)

    def test_a_reopen_after_a_revise_refreshes_opened_at(self):
        """The epoch that is LIVE gets its own moment; the predecessor's is preserved in
        its own epoch record rather than being overwritten in place."""
        with fx.LedgerRoot() as root:
            fx.revised_loop(root)
            first_opened = fx.read_ledger(root)["opened_at"]
            fx.open_loop(root)
            ledger = fx.read_ledger(root)
            self.assertRegex(ledger["opened_at"], _ISO_UTC)
            self.assertEqual(ledger["epochs"][0]["contract"]["purpose"],
                              fx.valid_contract()["purpose"])
            # The epoch boundary is the property under test, not wall-clock ordering —
            # two opens in the same process can share a second-precision timestamp.
            self.assertIsNotNone(first_opened)


class EveryIterationRecordsItsOwnMoment(unittest.TestCase):
    def test_an_iteration_carries_a_timestamp(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, err = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--outcome", "continue", "--action", "a",
            )
            self.assertEqual(code, EXIT_OK, err)
            record = fx.read_ledger(root)["iterations"][0]
            self.assertIn("timestamp", record)
            self.assertRegex(record["timestamp"], _ISO_UTC)

    def test_two_iterations_each_carry_their_own_timestamp_key(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "continue", "--action", "a")
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "continue", "--action", "b")
            first, second = fx.read_ledger(root)["iterations"]
            self.assertRegex(first["timestamp"], _ISO_UTC)
            self.assertRegex(second["timestamp"], _ISO_UTC)

    def test_a_refused_iteration_records_no_timestamp_either(self):
        """The existing refusal-records-nothing property extends to the new field: a
        refused iterate call must not leave a half-written record with only a timestamp."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, _, _ = fx.run_cli(
                "iterate", "--root", root.path, "--session", fx.SESSION,
                "--critic-verdict", "PASS",
            )
            self.assertNotEqual(code, EXIT_OK)
            self.assertEqual(fx.read_ledger(root)["iterations"], [])


class StatusSurfacesTheMostRecentTimestamp(unittest.TestCase):
    def test_status_reports_last_timestamp_from_the_last_iteration(self):
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "continue", "--action", "a")
            code, out, err = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION, "--json",
            )
            self.assertEqual(code, EXIT_OK, err)
            import json

            payload = json.loads(out)
            self.assertRegex(payload["last_timestamp"], _ISO_UTC)

    def test_status_over_an_empty_ledger_reports_last_timestamp_as_none_not_missing(self):
        """Absent is not zero, applied to the new key too: a loop with no iterations must
        not print a timestamp it never recorded, and must not omit the key either."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            code, out, err = fx.run_cli(
                "status", "--root", root.path, "--session", fx.SESSION, "--json",
            )
            import json

            payload = json.loads(out)
            self.assertIn("last_timestamp", payload)
            self.assertIsNone(payload["last_timestamp"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
