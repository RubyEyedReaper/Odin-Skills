"""RED for harness:RM-0646 — plancheck.py exposed no parse-only entry point, so
skill-command-check.py could only check `python3 -m scripts.plancheck ...` for existence, never
for parsing against plancheck's own CLI. Asserts build_parser() constructs the same CLI main()
used, and that construction alone has no side effects."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.plancheck import build_parser


class BuildParserExposesTheRealCLI(unittest.TestCase):
    def test_prog_is_plancheck(self):
        self.assertEqual(build_parser().prog, "plancheck")

    def test_parses_a_plan_path(self):
        args = build_parser().parse_args(["some-plan.md"])
        self.assertEqual(args.plan, "some-plan.md")
        self.assertFalse(args.json)

    def test_parses_the_json_flag(self):
        args = build_parser().parse_args(["some-plan.md", "--json"])
        self.assertTrue(args.json)

    def test_rejects_an_invented_flag(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["some-plan.md", "--not-a-real-flag"])


class BuildParserHasNoSideEffects(unittest.TestCase):
    def test_construction_touches_no_file_in_an_empty_directory(self):
        with tempfile.TemporaryDirectory() as scratch:
            before = os.getcwd()
            os.chdir(scratch)
            try:
                build_parser()
                self.assertEqual(os.listdir(scratch), [])
            finally:
                os.chdir(before)

    def test_construction_spawns_no_subprocess(self):
        with mock.patch("subprocess.run") as run, mock.patch("subprocess.Popen") as popen:
            build_parser()
            run.assert_not_called()
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
