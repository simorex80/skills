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

    def test_unknown_plan_fields_rejected(self):
        with self.assertRaisesRegex(wiki.WikiError, "Unknown"):
            wiki.validate_plan({"upsert": {"wiki/a.md": "test"}, "unexpected": 1}, set())

    def test_duplicate_deletions_rejected(self):
        with self.assertRaisesRegex(wiki.WikiError, "Duplicate"):
            wiki.validate_plan({"delete": ["wiki/a.md", "wiki/a.md"]}, {"wiki/a.md"})

    def test_init_rejects_incompatible_manifest(self):
        existing = list(wiki.DEFAULT_FILES)
        with patch.object(wiki, "snapshot", return_value="a" * 40), \
             patch.object(wiki, "list_files", return_value=existing), \
             patch.object(wiki, "read_file", return_value="version: 999"):
            with self.assertRaisesRegex(wiki.WikiError, "schema"):
                wiki.init_memory("github.com", "org/repo", "main")

    def test_lint_rejects_links_escaping_repository(self):
        files = set(wiki.DEFAULT_FILES)
        with patch.object(wiki, "list_files", return_value=list(files)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, path:
                              "[escape](../../secret.md)" if path == "wiki/index.md" else ""):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(result["issues"][0]["kind"], "invalid_link")

    def test_lint_reference_encoded_path_and_anchor(self):
        files = set(wiki.DEFAULT_FILES) | {"wiki/my doc.md", "wiki/other.md"}
        pages = {
            "wiki/index.md": (
                "[Encoded](my%20doc.md#some-heading)\n"
                "[Reference][other]\n\n[other]: other.md\n"
            ),
            "wiki/my doc.md": "# Some Heading\n",
            "wiki/other.md": "# Other\n",
        }
        with patch.object(wiki, "list_files", return_value=list(files)), \
             patch.object(wiki, "read_file",
                          side_effect=lambda h, r, sha, p: pages.get(p, "")):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(result["issues"], [])

    def test_lint_invalid_scheme_and_missing_anchor(self):
        files = set(wiki.DEFAULT_FILES)
        pages = {
            "wiki/index.md": "[Bad](javascript:alert) [Anchor](#missing)\n",
        }
        with patch.object(wiki, "list_files", return_value=list(files)), \
             patch.object(wiki, "read_file",
                          side_effect=lambda h, r, sha, p: pages.get(p, "")):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(
            [issue["kind"] for issue in result["issues"]],
            ["invalid_link", "broken_anchor"],
        )

    def test_lint_heading_anchor_uses_visible_link_text(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/index.md":
                 "# [Project](https://example.com)\n\n[Jump](#project)\n"}
        with patch.object(wiki, "list_files", return_value=list(pages)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, p: pages[p]):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(result["issues"], [])

    def test_lint_checks_uppercase_markdown_extension(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/notes.MD": "[Missing](missing.md)\n"}
        with patch.object(wiki, "list_files", return_value=list(pages)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, p: pages[p]):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(result["issues"], [
            {"kind": "broken_link", "path": "wiki/notes.MD", "target": "missing.md"},
        ])

    def test_graphql_branch_name_payload(self):
        sha = "a" * 40
        response = {"data": {"createCommitOnBranch": {"commit": {
            "oid": "b" * 40, "url": "https://github.com/example/commit"
        }}}}
        with patch.object(wiki, "list_files", return_value=[]), \
             patch.object(wiki, "snapshot", return_value=sha), \
             patch.object(wiki, "gh_api", return_value=json.dumps(response)) as api:
            wiki.commit("github.com", "org/memory", "main", sha,
                        "Test commit", {"upsert": {"wiki/test.md": "# Test"}})
        branch = api.call_args.args[2]["variables"]["input"]["branch"]
        self.assertEqual(branch, {"repositoryNameWithOwner": "org/memory",
                                  "branchName": "main"})

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
