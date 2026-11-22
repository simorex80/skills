"""Static checks for the two independent Copilot and Claude plugin catalogs.

Run with: python -m unittest tests/test_plugin_marketplaces.py -v
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"markitdown", "remote-llm-wiki"}


class PluginMarketplaceTests(unittest.TestCase):
    def test_catalogs_contain_exactly_two_independent_plugins(self):
        for path in (
            ROOT / ".github/plugin/marketplace.json",
            ROOT / ".claude-plugin/marketplace.json",
        ):
            with self.subTest(path=path):
                catalog = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(catalog["name"], "simorex-skills")
                self.assertEqual(catalog["owner"]["name"], "simorex80")
                self.assertEqual({p["name"] for p in catalog["plugins"]}, EXPECTED)
                self.assertEqual(len(catalog["plugins"]), len(EXPECTED))
                if path.parts[-2:] == (".claude-plugin", "marketplace.json"):
                    self.assertEqual(catalog["version"], "1.0.0")

                for plugin in catalog["plugins"]:
                    source = plugin["source"]
                    self.assertEqual(source, f"./skills/{plugin['name']}")
                    directory = (ROOT / source).resolve()
                    self.assertTrue(directory.is_relative_to(ROOT.resolve()))
                    self.assertTrue((directory / "SKILL.md").is_file())
                    self.assertTrue((directory / "scripts").is_dir())
                    self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
                    self.assertTrue(plugin["description"])

    def test_manifests_and_skill_names_are_consistent(self):
        for name in EXPECTED:
            with self.subTest(plugin=name):
                directory = ROOT / "skills" / name
                copilot = json.loads((directory / "plugin.json").read_text(encoding="utf-8"))
                claude = json.loads((directory / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
                skill = (directory / "SKILL.md").read_text(encoding="utf-8")
                self.assertRegex(skill, rf"\A---\s+name:\s*{re.escape(name)}\s")
                self.assertEqual(copilot["name"], name)
                self.assertEqual(claude["name"], name)
                self.assertEqual(copilot["version"], claude["version"])
                self.assertNotIn("$schema", copilot, "Copilot must use legacy root SKILL.md discovery")
                self.assertEqual(claude["skills"], ["."])
                self.assertEqual(claude["author"]["name"], "simorex80")
                self.assertEqual(claude["repository"], "https://github.com/simorex80/skills")
                for catalog_path in (
                    ROOT / ".github/plugin/marketplace.json",
                    ROOT / ".claude-plugin/marketplace.json",
                ):
                    entries = json.loads(catalog_path.read_text(encoding="utf-8"))["plugins"]
                    entry = next(p for p in entries if p["name"] == name)
                    if catalog_path.parts[-3:] == (".github", "plugin", "marketplace.json"):
                        self.assertEqual(entry["version"], copilot["version"])
                    else:
                        self.assertNotIn("version", entry, "Claude plugin manifest owns the version")


if __name__ == "__main__":
    unittest.main()
