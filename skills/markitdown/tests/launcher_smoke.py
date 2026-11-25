"""Exercise the platform launcher without installing the converter."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
LAUNCH = (
    ["pwsh", "-NoProfile", "-File", str(SCRIPTS / "convert.ps1")]
    if os.name == "nt"
    else [str(SCRIPTS / "convert.sh")]
)


class LauncherSmokeTests(unittest.TestCase):
    def test_extract_help_from_outside_skill(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [*LAUNCH, "extract", "--help"], cwd=cwd,
                capture_output=True, text=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: convert.py extract", result.stdout)

    def test_invalid_operation_preserves_argument_and_exit_code(self):
        result = subprocess.run(
            [*LAUNCH, "not a subcommand"], capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("invalid choice: 'not a subcommand'", result.stderr)


if __name__ == "__main__":
    unittest.main()
