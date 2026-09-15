"""trace.options: presets merged with --binary and --set overrides, typed as vtracer expects."""
from __future__ import annotations

import unittest

from ._fixtures import SKILL_DIR  # noqa: F401  (puts the skill on sys.path)
from scripts import trace


class Options(unittest.TestCase):
    def test_preset_is_copied_not_shared(self):
        opts = trace.options("icon", False, [])
        opts["filter_speckle"] = 99
        self.assertEqual(trace.PRESETS["icon"]["filter_speckle"], 6)

    def test_binary_switches_colormode_only(self):
        opts = trace.options("logo", True, [])
        self.assertEqual(opts["colormode"], "binary")
        self.assertEqual(opts["layer_difference"], 20)

    def test_set_values_are_typed(self):
        opts = trace.options("icon", False, ["filter_speckle=12", "length_threshold=3.5", "mode=polygon"])
        self.assertEqual(opts["filter_speckle"], 12)
        self.assertEqual(opts["length_threshold"], 3.5)
        self.assertEqual(opts["mode"], "polygon")

    def test_malformed_set_refused(self):
        with self.assertRaises(ValueError):
            trace.options("icon", False, ["filter_speckle"])


if __name__ == "__main__":
    unittest.main()
