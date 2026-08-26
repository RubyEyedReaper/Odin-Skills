"""`run`, `status` and `record`.

`run` never executes anything. It resolves a manifest, refuses the manifests it must
refuse, emits the ordered steps for the agent to follow, and opens a run record. The
break each case names: a runner that emits steps out of order, one whose `--dry-run`
writes anyway, or a `record` that invents a run nobody started.
"""
from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from . import _fixtures as fx
from scripts.workflow import (
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_USAGE,
    main,
)

SESSION = "11111111-2222-3333-4444-555555555555"


def run_cli(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class RunTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)
        self.fixture.write(fx.valid_manifest("sample-chain"))
        os.environ["CLAUDE_SESSION_ID"] = SESSION
        self.addCleanup(os.environ.pop, "CLAUDE_SESSION_ID", None)

    def records(self) -> list[str]:
        directory = self.fixture.runtime(SESSION)
        return sorted(os.listdir(directory)) if os.path.isdir(directory) else []

    def test_run_emits_the_steps_in_order(self):
        code, out, _ = run_cli("run", "sample-chain", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_OK)
        self.assertLess(out.index("systematic-debugging"), out.index("diagnosing-bugs"))

    def test_run_opens_a_record_under_the_session_keyed_runtime_class(self):
        run_cli("run", "sample-chain", "--root", self.fixture.root)
        self.assertEqual(len(self.records()), 1)
        with open(os.path.join(self.fixture.runtime(SESSION), self.records()[0])) as handle:
            record = json.load(handle)
        self.assertEqual(record["workflow"], "sample-chain")
        self.assertEqual(record["version"], "1.0.0")
        self.assertIsNone(record["outcome"])

    def test_dry_run_takes_the_same_path_but_writes_no_record(self):
        code, out, _ = run_cli("run", "sample-chain", "--root", self.fixture.root, "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("systematic-debugging", out)
        self.assertEqual(self.records(), [])

    def test_running_an_unknown_workflow_is_a_usage_error(self):
        code, _, err = run_cli("run", "no-such-chain", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("no-such-chain", err)

    def test_an_invalid_manifest_is_not_run(self):
        broken = fx.valid_manifest("broken-chain")
        del broken["completion_criteria"]
        self.fixture.write(broken)
        code, _, _ = run_cli("run", "broken-chain", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertEqual(self.records(), [])

    def test_run_json_carries_the_steps_and_the_record_path(self):
        code, out, _ = run_cli("run", "sample-chain", "--root", self.fixture.root, "--json")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual([s["skill"] for s in payload["steps"]],
                         ["systematic-debugging", "diagnosing-bugs"])
        self.assertTrue(payload["record"].endswith(".json"))


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)

    def test_status_reports_id_version_and_lifecycle_state(self):
        self.fixture.write(fx.valid_manifest("sample-chain"))
        code, out, _ = run_cli("status", "--root", self.fixture.root, "--json")
        self.assertEqual(code, EXIT_OK)
        row = json.loads(out)["workflows"][0]
        self.assertEqual(
            (row["id"], row["version"], row["status"]),
            ("sample-chain", "1.0.0", "active"),
        )

    def test_status_over_an_empty_set_exits_nonzero(self):
        from scripts.workflow import EXIT_EMPTY

        code, _, _ = run_cli("status", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_EMPTY)

    def test_status_reports_a_malformed_manifest_rather_than_omitting_it(self):
        self.fixture.write(None, name="unreadable", raw="{")
        code, out, _ = run_cli("status", "--root", self.fixture.root, "--json")
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertEqual(json.loads(out)["workflows"][0]["status"], "unreadable")


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)
        self.fixture.write(fx.valid_manifest("sample-chain"))
        os.environ["CLAUDE_SESSION_ID"] = SESSION
        self.addCleanup(os.environ.pop, "CLAUDE_SESSION_ID", None)

    def test_recording_an_outcome_with_no_open_run_is_a_usage_error(self):
        code, _, err = run_cli(
            "record", "sample-chain", "--outcome", "ok", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("no open run", err.lower())

    def test_recording_closes_the_open_run(self):
        run_cli("run", "sample-chain", "--root", self.fixture.root)
        code, _, _ = run_cli(
            "record", "sample-chain", "--outcome", "failed",
            "--note", "step 3 never went red", "--root", self.fixture.root,
        )
        self.assertEqual(code, EXIT_OK)
        directory = self.fixture.runtime(SESSION)
        with open(os.path.join(directory, os.listdir(directory)[0])) as handle:
            record = json.load(handle)
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(record["note"], "step 3 never went red")

    def test_a_closed_run_is_not_reopened_by_a_second_record(self):
        run_cli("run", "sample-chain", "--root", self.fixture.root)
        run_cli("record", "sample-chain", "--outcome", "ok", "--root", self.fixture.root)
        code, _, _ = run_cli(
            "record", "sample-chain", "--outcome", "failed", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
