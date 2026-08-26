"""Manifest parsing and validation.

The break each case names is a production change that would be a bug: a validator that
accepts a manifest missing a lifecycle field, one that picks the first of several JSON
blocks rather than refusing the ambiguity, or one that reports success over a directory
holding nothing.
"""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from . import _fixtures as fx
from scripts.workflow import (
    EXIT_EMPTY,
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_USAGE,
    main,
)


def run_cli(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)

    def test_a_well_formed_manifest_validates(self):
        self.fixture.write(fx.valid_manifest())
        code, _, _ = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_OK)

    def test_an_invalid_manifest_exits_nonzero(self):
        broken = fx.valid_manifest()
        del broken["failure_handling"]
        self.fixture.write(broken)
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("failure_handling", err)

    def test_every_lifecycle_field_is_required(self):
        for field in (
            "inputs",
            "outputs",
            "dependencies",
            "decision_points",
            "failure_handling",
            "owner",
            "completion_criteria",
            "version",
            "supersedes",
            "status",
        ):
            with self.subTest(field=field):
                fixture = fx.RootFixture()
                self.addCleanup(fixture.cleanup)
                broken = fx.valid_manifest()
                del broken[field]
                fixture.write(broken)
                code, _, err = run_cli("validate", "--root", fixture.root)
                self.assertEqual(code, EXIT_FINDINGS)
                self.assertIn(field, err)

    def test_an_empty_manifest_set_exits_nonzero(self):
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_EMPTY)
        self.assertIn("no manifests", err.lower())

    def test_a_missing_manifest_directory_exits_nonzero(self):
        fixture = fx.RootFixture(create_dir=False)
        self.addCleanup(fixture.cleanup)
        code, _, _ = run_cli("validate", "--root", fixture.root)
        self.assertEqual(code, EXIT_EMPTY)

    def test_two_json_blocks_are_refused_rather_than_the_first_taken(self):
        self.fixture.write(fx.valid_manifest(), blocks=2)
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("exactly one", err)

    def test_a_file_with_no_json_block_is_a_finding(self):
        self.fixture.write(fx.valid_manifest(), blocks=0)
        code, _, _ = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)

    def test_unparseable_json_is_a_finding_not_a_traceback(self):
        self.fixture.write(None, name="broken", raw="{not json,}")
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("broken.workflow.md", err)

    def test_id_must_match_the_filename_stem(self):
        self.fixture.write(fx.valid_manifest("declared-id"), name="file-stem")
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("file-stem", err)

    def test_version_must_be_three_numeric_parts(self):
        self.fixture.write(fx.valid_manifest(version="v1"))
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("version", err)

    def test_an_unknown_status_is_a_finding(self):
        self.fixture.write(fx.valid_manifest(status="archived"))
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("status", err)

    def test_steps_must_be_numbered_from_one_without_gaps(self):
        manifest = fx.valid_manifest()
        manifest["steps"][1]["step"] = 7
        self.fixture.write(manifest)
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("step", err)

    def test_a_retired_manifest_must_carry_its_evidence(self):
        self.fixture.write(fx.valid_manifest(status="retired"))
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("retired", err)

    def test_a_decision_point_must_name_a_step_that_exists(self):
        manifest = fx.valid_manifest()
        manifest["decision_points"][0]["at"] = 9
        self.fixture.write(manifest)
        code, _, err = run_cli("validate", "--root", self.fixture.root)
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("decision_points", err)


class OutputContractTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fx.RootFixture()
        self.addCleanup(self.fixture.cleanup)

    def test_json_findings_go_to_stdout_as_parseable_data(self):
        broken = fx.valid_manifest()
        del broken["owner"]
        self.fixture.write(broken)
        code, out, _ = run_cli("validate", "--root", self.fixture.root, "--json")
        self.assertEqual(code, EXIT_FINDINGS)
        payload = json.loads(out)
        self.assertEqual(payload["examined"], 1)
        self.assertTrue(any("owner" in f["finding"] for f in payload["findings"]))

    def test_no_arguments_prints_help_and_exits_nonzero(self):
        code, _, _ = run_cli()
        self.assertEqual(code, EXIT_USAGE)

    def test_a_single_manifest_can_be_named_by_id(self):
        self.fixture.write(fx.valid_manifest("kept"))
        broken = fx.valid_manifest("broken-one")
        del broken["outputs"]
        self.fixture.write(broken)
        code, _, _ = run_cli("validate", "--root", self.fixture.root, "--id", "kept")
        self.assertEqual(code, EXIT_OK)


if __name__ == "__main__":
    unittest.main()
