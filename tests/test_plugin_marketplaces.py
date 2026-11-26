"""Static checks for independently distributed Copilot and Claude plugins.

Run with: python -m unittest tests/test_plugin_marketplaces.py -v
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def discover_skills():
    """Treat every immediate skills/ subdirectory as a required skill."""
    root = ROOT / "skills"
    directories = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    names = {p.name for p in directories}
    if not names:
        raise AssertionError("No skills found")
    for directory in directories:
        if not (directory / "SKILL.md").is_file():
            raise AssertionError(f"Missing SKILL.md: {directory}")
    return names


class PluginMarketplaceTests(unittest.TestCase):
    def test_catalogs_match_discovered_independent_plugins(self):
        expected = discover_skills()
        for path in (
            ROOT / ".github/plugin/marketplace.json",
            ROOT / ".claude-plugin/marketplace.json",
        ):
            with self.subTest(path=path):
                catalog = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(catalog["name"], "simorex-skills")
                self.assertEqual(catalog["owner"]["name"], "simorex80")
                self.assertEqual({p["name"] for p in catalog["plugins"]}, expected)
                self.assertEqual(len(catalog["plugins"]), len(expected))
                if path.parts[-2:] == (".claude-plugin", "marketplace.json"):
                    self.assertRegex(catalog["version"], r"^\d+\.\d+\.\d+$")

                for plugin in catalog["plugins"]:
                    source = plugin["source"]
                    self.assertEqual(source, f"./skills/{plugin['name']}")
                    directory = (ROOT / source).resolve()
                    self.assertTrue(directory.is_relative_to(ROOT.resolve()))
                    self.assertTrue((directory / "SKILL.md").is_file())
                    self.assertNotIn("version", plugin, "Plugin versions belong in their manifests")
                    self.assertTrue(plugin["description"])

    def test_manifests_and_skill_names_are_consistent(self):
        for name in discover_skills():
            with self.subTest(plugin=name):
                directory = ROOT / "skills" / name
                copilot = json.loads((directory / "plugin.json").read_text(encoding="utf-8"))
                claude = json.loads((directory / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
                skill = (directory / "SKILL.md").read_text(encoding="utf-8")
                self.assertRegex(skill, rf"\A---\s+name:\s*{re.escape(name)}\s")
                self.assertEqual(copilot["name"], name)
                self.assertEqual(claude["name"], name)
                self.assertRegex(copilot["version"], r"^\d+\.\d+\.\d+$")
                self.assertEqual(copilot["version"], claude["version"])
                self.assertNotIn("$schema", copilot, "Copilot must use legacy root SKILL.md discovery")
                self.assertEqual(claude["skills"], ["."])
                self.assertTrue(claude.get("author", {}).get("name"))
                self.assertTrue(claude.get("repository", "").startswith("https://"))


if __name__ == "__main__":
    unittest.main()
