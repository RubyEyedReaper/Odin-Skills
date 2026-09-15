"""autorecord: the --auto search lands in qa.json, whether or not a candidate passed."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from ._fixtures import SKILL_DIR  # noqa: F401  (puts the skill on sys.path)
from scripts import autorecord

SEARCH = {"chosen": None, "nearest": 0, "flags": ["--scale", "8"], "grid": [{"pass": False}], "seconds": 1.0}


class AutoRecord(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.search = os.path.join(self.dir, "search.json")
        self.qa = os.path.join(self.dir, "Name.qa.json")
        with open(self.search, "w", encoding="utf-8") as fh:
            json.dump(SEARCH, fh)

    def tearDown(self):
        for name in os.listdir(self.dir):
            os.unlink(os.path.join(self.dir, name))
        os.rmdir(self.dir)

    def test_search_is_added_to_an_existing_report(self):
        with open(self.qa, "w", encoding="utf-8") as fh:
            json.dump({"iou": 0.99, "pass": True, "failures": []}, fh)
        self.assertEqual(autorecord.main([self.search, self.qa]), 0)
        report = json.load(open(self.qa))
        self.assertEqual(report["iou"], 0.99)
        self.assertEqual(report["search"], SEARCH)

    def test_refusal_writes_a_failing_report_carrying_the_search(self):
        self.assertEqual(autorecord.main([self.search, self.qa]), 0)
        report = json.load(open(self.qa))
        self.assertFalse(report["pass"])
        self.assertEqual(report["failures"], ["auto"])
        self.assertEqual(report["search"]["flags"], ["--scale", "8"])

    def test_unreadable_search_is_a_tool_failure(self):
        self.assertEqual(autorecord.main([os.path.join(self.dir, "missing.json"), self.qa]), 2)
        self.assertFalse(os.path.exists(self.qa))


if __name__ == "__main__":
    unittest.main()
