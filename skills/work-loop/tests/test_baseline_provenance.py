"""A baseline is recorded as measured or as declared, and the two are never confused.

The engine cannot verify a number without running something, and running a
contract-supplied command from inside this process was scored and vetoed (DEC-0091): a
subprocess spawned here is not a tool call, so it would sit outside every always-on guard.
What is left is the strongest claim a non-executing engine can honestly make — the caller
runs the command through its own tool path, where the guards apply, and hands back the
transcript; `open` refuses unless the declared baseline appears in it, and records which
dimensions were backed that way.

What a `measured` provenance proves: a transcript carrying that number was supplied at open
time. What it does not prove: that the number came from that command. The residue is stated
here, in the reference, and in the ADR, rather than left for a reader to discover.
"""
from __future__ import annotations

import json
import unittest

from . import _fixtures as fx
from scripts.loop import EXIT_INVALID, EXIT_OK, EXIT_UNREADABLE


def _status(root, session=fx.SESSION):
    code, out, err = fx.run_cli(
        "status", "--root", root.path, "--session", session, "--json"
    )
    return code, json.loads(out) if out.strip() else None, err


class ProvenanceIsRecordedAtOpen(unittest.TestCase):
    def test_every_baseline_is_declared_when_no_transcript_is_supplied(self):
        with fx.LedgerRoot() as root:
            code, _, _ = fx.open_loop(root)
            self.assertEqual(code, EXIT_OK)
            provenance = fx.read_ledger(root)["baseline_provenance"]
            self.assertEqual(len(provenance), 4)
            self.assertEqual(set(provenance.values()), {"declared"})

    def test_a_transcript_carrying_the_baseline_promotes_it_to_measured(self):
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "ci-local.sh: 2 failing gate(s)\n")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            self.assertEqual(code, EXIT_OK, err)
            provenance = fx.read_ledger(root)["baseline_provenance"]
            self.assertEqual(provenance["gate-integrity"], "measured")
            self.assertEqual(provenance["record-integrity"], "declared")

    def test_the_flag_is_repeatable(self):
        with fx.LedgerRoot() as root:
            gate = root.write("gate.txt", "2\n")
            record = root.write("record.txt", "doc-reference-check: 1 finding\n")
            code, _, err = fx.open_loop(
                root,
                extra_argv=[
                    "--baseline-evidence", "gate-integrity=" + gate,
                    "--baseline-evidence", "record-integrity=" + record,
                ],
            )
            self.assertEqual(code, EXIT_OK, err)
            provenance = fx.read_ledger(root)["baseline_provenance"]
            self.assertEqual(provenance["gate-integrity"], "measured")
            self.assertEqual(provenance["record-integrity"], "measured")


class TranscriptsThatProveNothingAreRefused(unittest.TestCase):
    def test_a_transcript_missing_the_declared_baseline_is_refused(self):
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "ci-local.sh: 9 failing gate(s)\n")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("does not appear", err)

    def test_a_substring_match_does_not_count_as_the_baseline(self):
        """A baseline of 2 is not evidenced by a transcript whose only number is 20."""
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "ran 20 checks\n")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("does not appear", err)

    def test_an_empty_transcript_exits_unreadable(self):
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            self.assertEqual(code, EXIT_UNREADABLE)
            self.assertIn("gate.txt", err)

    def test_a_transcript_that_cannot_be_read_exits_unreadable(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root,
                extra_argv=["--baseline-evidence", "gate-integrity=/nonexistent/x.txt"],
            )
            self.assertEqual(code, EXIT_UNREADABLE)
            self.assertIn("/nonexistent/x.txt", err)

    def test_a_transcript_for_an_undeclared_dimension_is_refused(self):
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "2\n")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "no-such-dimension=" + path]
            )
            self.assertEqual(code, EXIT_INVALID)
            self.assertIn("not a declared dimension", err)

    def test_an_argument_with_no_equals_sign_is_a_usage_refusal(self):
        with fx.LedgerRoot() as root:
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity"]
            )
            self.assertNotEqual(code, EXIT_OK)
            self.assertIn("dimension=path", err)

    def test_a_float_baseline_matches_its_integer_spelling(self):
        """38000 and 38000.0 are one reading; a transcript spells whichever the tool prints."""
        with fx.LedgerRoot() as root:
            path = root.write("ctx.txt", "always-on bytes: 38000\n")
            code, _, err = fx.open_loop(
                root, extra_argv=["--baseline-evidence", "context-budget=" + path]
            )
            self.assertEqual(code, EXIT_OK, err)


class StatusSurfacesProvenance(unittest.TestCase):
    """A reader asks `status` how a loop is doing; an unverified baseline belongs there."""

    def test_status_reports_how_many_baselines_were_measured(self):
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "2 failing\n")
            fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "continue", "--action", "probe", "--state", "s=1")
            _, payload, _ = _status(root)
            self.assertEqual(payload["baselines_measured"], 1)
            self.assertEqual(payload["baselines_total"], 4)

    def test_absent_is_not_zero_over_a_ledger_that_predates_this_change(self):
        """A ledger with no provenance key reads null, never 0 — the same discipline the
        five quality keys carry, for the same reason: a loop nobody measured must not read
        as a loop that measured nothing."""
        with fx.LedgerRoot() as root:
            fx.open_loop(root)
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "continue", "--action", "probe", "--state", "s=1")
            ledger = fx.read_ledger(root)
            del ledger["baseline_provenance"]
            with open(root.ledger_path(), "w", encoding="utf-8") as handle:
                json.dump(ledger, handle)
            _, payload, _ = _status(root)
            self.assertIsNone(payload["baselines_measured"])
            self.assertIsNone(payload["baselines_total"])


class ProvenanceIsPerEpoch(unittest.TestCase):
    def test_a_reopen_resets_provenance_for_the_new_contract(self):
        """A revise means the approach was wrong; the predecessor's transcript is not
        evidence for the successor's baselines, which may not even be the same numbers."""
        with fx.LedgerRoot() as root:
            path = root.write("gate.txt", "2 failing\n")
            fx.open_loop(
                root, extra_argv=["--baseline-evidence", "gate-integrity=" + path]
            )
            fx.run_cli("iterate", "--root", root.path, "--session", fx.SESSION,
                       "--outcome", "revise", "--action", "rethink", "--state", "s=2")
            code, _, err = fx.open_loop(root)
            self.assertEqual(code, EXIT_OK, err)
            ledger = fx.read_ledger(root)
            self.assertEqual(ledger["epoch"], 2)
            self.assertEqual(set(ledger["baseline_provenance"].values()), {"declared"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
