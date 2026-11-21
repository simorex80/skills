"""Offline contract tests for remote LLM Wiki V2.

Run: python -m unittest discover -s skills/remote-llm-wiki/tests -v
"""
import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wiki_v2", ROOT / "scripts" / "wiki.py")
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


class FakeBackend:
    """In-memory snapshot backend for deterministic tests."""

    def __init__(self):
        self.head = "a" * 40
        self.files = {}
        self.counter = 0

    def get_snapshot(self, branch):
        return self.head

    def list_files(self, sha):
        if sha != self.head:
            raise wiki.WikiError("Unknown snapshot")
        return sorted(self.files)

    def read_file(self, sha, path):
        return self.files[path]

    def commit(self, branch, expected_sha, message, plan):
        if expected_sha != self.head:
            raise wiki.WikiError("Branch advanced")
        wiki.validate_plan(plan, set(self.files))
        self.files.update(plan.get("upsert", {}))
        for path in plan.get("delete", []):
            self.files.pop(path)
        self.counter += 1
        self.head = f"{self.counter:040x}"
        return {"oid": self.head}


class WikiV2Tests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()

    def test_raw_append_only(self):
        sha = self.backend.get_snapshot("main")
        self.backend.commit("main", sha, "add source",
                            {"upsert": {"raw/source.md": "Original"}})
        with self.assertRaisesRegex(wiki.WikiError, "immutable"):
            self.backend.commit("main", self.backend.head, "overwrite",
                                {"upsert": {"raw/source.md": "Modified"}})

    def test_stale_snapshot_rejected(self):
        old = self.backend.head
        self.backend.commit("main", old, "first",
                            {"upsert": {"wiki/a.md": "# A"}})
        with self.assertRaisesRegex(wiki.WikiError, "advanced"):
            self.backend.commit("main", old, "second",
                                {"upsert": {"wiki/b.md": "# B"}})

    def test_reject_path_traversal(self):
        with self.assertRaises(wiki.WikiError):
            wiki.validate_plan({"upsert": {"wiki/../private.md": "x"}}, set())

    def test_reject_raw_deletion(self):
        with self.assertRaises(wiki.WikiError):
            wiki.validate_plan({"delete": ["raw/a.md"]}, {"raw/a.md"})

    def test_reject_oversize(self):
        with self.assertRaisesRegex(wiki.WikiError, "size limit"):
            wiki.validate_plan(
                {"upsert": {"wiki/huge.md": "x" * (wiki.MAX_FILE_BYTES + 1)}},
                set())

    def test_bootstrap_can_create_manifest(self):
        wiki.validate_plan({"upsert": dict(wiki.DEFAULT_FILES)}, set(),
                           bootstrap=True)
        changes = wiki.file_changes({"upsert": dict(wiki.DEFAULT_FILES)},
                                    bootstrap=True)
        self.assertEqual(len(changes["additions"]), len(wiki.DEFAULT_FILES))

    def test_regular_ingest_cannot_modify_manifest(self):
        with self.assertRaises(wiki.WikiError):
            wiki.validate_plan({"upsert": {"AGENTS.md": "bad"}}, set())

    def test_duplicate_json_plan_keys(self):
        with self.assertRaisesRegex(wiki.WikiError, "Duplicate key"):
            json.loads('{"upsert":{},"upsert":{}}',
                       object_pairs_hook=wiki.unique_plan_keys)

    def test_markdown_link_lint(self):
        files = {"wiki/index.md", "wiki/a.md", *wiki.DEFAULT_FILES.keys()}
        with patch.object(wiki, "list_files", return_value=list(files)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, p: (
                 "[Exists](a.md) [Missing](missing.md)" if p == "wiki/index.md" else ""
             )):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(
            [i["kind"] for i in result["issues"]], ["broken_link"])


if __name__ == "__main__":
    unittest.main()
