"""i2c.sh --auto refuses a tuning flag before any tool runs: choosing those flags is the search's job."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

from ._fixtures import SKILL_DIR

I2C = os.path.join(SKILL_DIR, "scripts", "i2c.sh")


class AutoArgs(unittest.TestCase):
    def setUp(self):
        self.dir = self.enterContext(tempfile.TemporaryDirectory())
        self.image = os.path.join(self.dir, "in.png")
        with open(self.image, "wb") as fh:
            fh.write(b"not decoded: the refusal comes first")

    def _run(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", I2C, self.image, "--name", "Glyph", "--kind", "icon",
                               "--out", os.path.join(self.dir, "out"), *extra],
                              capture_output=True, text=True, timeout=60)

    def test_tuning_flag_beside_auto_is_a_usage_error_naming_the_flag(self):
        for flag, value in (("--scale", "3"), ("--colors", "8"), ("--set", "filter_speckle=4"), ("--sharpen", "1")):
            result = self._run("--auto", flag, value)
            self.assertEqual(result.returncode, 2, flag)
            self.assertIn(f"drop {flag}", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
