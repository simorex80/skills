"""Verify that skill instructions document a shared trust boundary."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UntrustedContentBoundaryTests(unittest.TestCase):
    def test_skill_documents_keep_explicit_trust_boundary(self):
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text.lower(), r"untrusted(?: repository)? data")
                self.assertIn("separate", text.lower())
                self.assertIn("authorization", text.lower())


if __name__ == "__main__":
    unittest.main()
