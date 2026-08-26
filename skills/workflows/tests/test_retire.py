"""Retire and supersede — the transitions, their evidence, and the refusal.

The primary testable core lives here: a retired manifest is refused by the runner with a
distinct exit code. The break: a runner that treats `status` as documentation, so a chain
everyone agreed to stop using keeps being followed.
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from . import _fixtures as fx
from scripts.workflow import (
    EXIT_OK,
    EXIT_RETIRED,
    EXIT_USAGE,
    main,
)


def run_cli(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class RefusalTest(unittest.TestCase):
    """The core: retired means the runner will not run it."""

    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)
        self.fixture.write(
            fx.valid_manifest(
                "retired-chain",
                status="retired",
                retired={"reason": "superseded by direct diagnosis"},
            )
        )

    def test_a_retired_manifest_is_refused_by_the_runner(self):
        code, _, err = run_cli("run", "retired-chain", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_RETIRED)
        self.assertIn("retired", err.lower())

    def test_the_refusal_has_its_own_exit_code(self):
        """Distinct from a validation finding: a caller branches on it without parsing text."""
        from scripts.workflow import EXIT_EMPTY, EXIT_FINDINGS

        self.assertNotIn(EXIT_RETIRED, (EXIT_OK, EXIT_FINDINGS, EXIT_USAGE, EXIT_EMPTY))

    def test_a_retired_manifest_still_validates(self):
        """Retirement is a lifecycle state, not corruption — `validate` must not conflate them."""
        code, _, _ = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_OK)

    def test_dry_run_does_not_bypass_the_refusal(self):
        code, _, _ = run_cli("run", "retired-chain", "--root", self.fixture.root, "--dry-run")
        self.assertEqual(code, EXIT_RETIRED)


class RetireTransitionTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)
        self.fixture.write(fx.valid_manifest("old-chain"))
        self.fixture.write(fx.valid_manifest("new-chain"))

    def test_retiring_with_a_reason_records_the_reason(self):
        code, _, _ = run_cli(
            "retire", "old-chain", "--reason", "the gate it fed was deleted",
            "--root", self.fixture.root,
        )
        self.assertEqual(code, EXIT_OK)
        manifest = self.fixture.read("old-chain")
        self.assertEqual(manifest["status"], "retired")
        self.assertEqual(manifest["retired"]["reason"], "the gate it fed was deleted")

    def test_retiring_with_a_successor_records_the_successor(self):
        code, _, _ = run_cli(
            "retire", "old-chain", "--superseded-by", "new-chain", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.fixture.read("old-chain")["retired"]["superseded_by"], "new-chain")

    def test_a_named_successor_must_exist(self):
        code, _, err = run_cli(
            "retire", "old-chain", "--superseded-by", "imaginary", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("imaginary", err)
        self.assertEqual(self.fixture.read("old-chain")["status"], "active")

    def test_a_named_successor_must_not_itself_be_retired(self):
        run_cli("retire", "new-chain", "--reason", "abandoned", "--root", self.fixture.root)
        code, _, _ = run_cli(
            "retire", "old-chain", "--superseded-by", "new-chain", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(self.fixture.read("old-chain")["status"], "active")

    def test_retiring_without_evidence_is_a_usage_error(self):
        code, _, _ = run_cli("retire", "old-chain", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_USAGE)
        self.assertEqual(self.fixture.read("old-chain")["status"], "active")

    def test_retiring_an_already_retired_workflow_is_refused(self):
        run_cli("retire", "old-chain", "--reason", "first", "--root", self.fixture.root)
        code, _, _ = run_cli(
            "retire", "old-chain", "--reason", "second", "--root", self.fixture.root
        )
        self.assertEqual(code, EXIT_RETIRED)
        self.assertEqual(self.fixture.read("old-chain")["retired"]["reason"], "first")

    def test_dry_run_leaves_the_manifest_untouched(self):
        code, out, _ = run_cli(
            "retire", "old-chain", "--reason", "considering it",
            "--root", self.fixture.root, "--dry-run",
        )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("old-chain", out)
        self.assertEqual(self.fixture.read("old-chain")["status"], "active")

    def test_retiring_preserves_the_prose_around_the_manifest_block(self):
        """The file is a document a human reads; the transition edits one block, not the file."""
        run_cli("retire", "old-chain", "--reason", "obsolete", "--root", self.fixture.root)
        with open(self.fixture.manifests + "/old-chain.workflow.md") as handle:
            text = handle.read()
        self.assertIn("Prose a human reads.", text)
        self.assertEqual(text.count("```json"), 1)

    def test_retiring_bumps_the_minor_version(self):
        """A lifecycle transition is a change to the interface, so the version moves with it."""
        run_cli("retire", "old-chain", "--reason", "obsolete", "--root", self.fixture.root)
        self.assertEqual(self.fixture.read("old-chain")["version"], "1.1.0")


if __name__ == "__main__":
    unittest.main()
