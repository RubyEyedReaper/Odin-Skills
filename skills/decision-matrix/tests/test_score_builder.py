"""RED for harness:RM-0646 — score.py exposed no parse-only entry point, so
skill-command-check.py could only check `python3 -m scripts.score ...` for existence, never for
parsing against score's own CLI. Asserts build_parser() constructs the same CLI main() used, and
that construction alone has no side effects (files, network, subprocess) — the checker's own
introspection probe imports the module and calls this function in a fresh subprocess."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score import build_parser


class BuildParserExposesTheRealCLI(unittest.TestCase):
    def test_prog_is_score(self):
        self.assertEqual(build_parser().prog, "score")

    def test_parses_the_documented_shorthand(self):
        args = build_parser().parse_args(["--spec", "spec.json", "--record"])
        self.assertEqual(args.spec, "spec.json")
        self.assertTrue(args.record)

    def test_rejects_an_invented_flag(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--not-a-real-flag"])


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
