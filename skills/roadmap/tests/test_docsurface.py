"""The documented-surface checkers, unit-tested.

They lived as three verbatim heredocs inside `roadmap-check.sh`, where nothing could import them.
`.claude/scripts/roadmap-command-doc-test.sh` exercises them end-to-end through the real gate; this
file pins the parsing rules that file cannot reach cheaply.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import docsurface  # noqa: E402


def _md(body):
    handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    handle.write(body)
    handle.close()
    return handle.name


class TestInvocationExtraction(unittest.TestCase):
    def test_an_indented_fence_is_still_a_fence(self):
        """The bug this check shipped with: `projects/README.md` indents its fence inside a list
        item, so anchoring on column zero reported `checked=0` for the one document the gate was
        written for."""
        path = _md("1. Step:\n\n   ```sh\n   roadmap --root x init\n   ```\n")
        problems, checked = docsurface.check_invocations(path)
        self.assertEqual(1, checked)
        self.assertEqual([], problems)

    def test_prose_outside_a_fence_is_not_an_instruction(self):
        path = _md("Run `roadmap set RM-0001 --link plan=x.md` sometime.\n")
        _problems, checked = docsurface.check_invocations(path)
        self.assertEqual(0, checked)

    def test_a_quoted_value_is_one_argument(self):
        path = _md('```sh\nroadmap add --title "Two words" --kind page\n```\n')
        problems, checked = docsurface.check_invocations(path)
        self.assertEqual((1, []), (checked, problems))

    def test_a_continuation_is_one_invocation(self):
        path = _md('```sh\nroadmap add --title "A" \\\n  --kind feature\n```\n')
        problems, checked = docsurface.check_invocations(path)
        self.assertEqual((1, []), (checked, problems))

    def test_a_placeholder_does_not_fail_a_choice_argument(self):
        path = _md("```sh\nroadmap add --title \"T\" --kind <K>\n```\n")
        problems, _checked = docsurface.check_invocations(path)
        self.assertEqual([], problems)

    def test_a_flag_the_engine_rejects_is_reported(self):
        path = _md("```sh\nroadmap set RM-0001 --link plan=x.md\n```\n")
        problems, checked = docsurface.check_invocations(path)
        self.assertEqual(1, checked)
        self.assertEqual(1, len(problems))

    def test_a_global_flag_after_its_subcommand_is_reported(self):
        """`--root` is global: `next --root .` exits 2 while `--root . next` exits 0. The flag-name
        check cannot see this, because the flag does exist."""
        bad = _md("```sh\nroadmap next --root .\n```\n")
        good = _md("```sh\nroadmap --root . next\n```\n")
        self.assertEqual(1, len(docsurface.check_invocations(bad)[0]))
        self.assertEqual([], docsurface.check_invocations(good)[0])


class TestVocabulary(unittest.TestCase):
    def test_the_shipped_tree_keeps_the_two_mechanisms_apart(self):
        self.assertEqual([], docsurface.check_vocabulary())


if __name__ == "__main__":
    unittest.main()
