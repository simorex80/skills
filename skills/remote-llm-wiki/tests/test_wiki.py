"""Offline contract tests for Remote LLM Wiki.

Run: python -m unittest discover -s skills/remote-llm-wiki/tests -v
"""
import importlib.util
import contextlib
import hashlib
import json
import pathlib
import re
import subprocess
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wiki", ROOT / "scripts" / "wiki.py")
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


@contextlib.contextmanager
def lint_snapshot(files, read):
    """Serve a snapshot whose blobs are read through read(path); yields read paths."""
    oids = {path: f"{index + 1:040x}" for index, path in enumerate(sorted(files))}
    paths = {oid: path for path, oid in oids.items()}
    reads = []

    def blob(host, repo, oid):
        reads.append(paths[oid])
        return read(paths[oid])

    with patch.object(wiki, "_snapshot_entries", return_value=oids), \
         patch.object(wiki, "read_blob", side_effect=blob):
        yield reads

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


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()

    def remote_commit(self, pages, plan, *, error=None, stale=False):
        prefix = "repos/org/memory/git/"
        sha, tree_sha = self.backend.head, "c" * 40
        def oid(text):
            return hashlib.sha1(text.encode() if isinstance(text, str) else text).hexdigest()

        blobs = {oid(text): text for text in pages.values()}
        tree = [{"path": p, "type": "blob", "mode": "100644",
                 "sha": oid(t)} for p, t in pages.items()]
        responses = {
            prefix + f"commits/{sha}": json.dumps({"tree": {"sha": tree_sha}}),
            prefix + f"trees/{tree_sha}?recursive=1": json.dumps({"tree": tree, "truncated": False}),
            prefix + "ref/heads/main": "d" * 40 if stale else sha,
            **{prefix + "blobs/" + oid: text for oid, text in blobs.items()},
        }
        calls, mutations = [], []

        def gh(host, args, payload=None):
            self.assertEqual(host, "github.com")
            calls.append(args[0])
            if args[0] == "graphql":
                mutations.append(payload["variables"]["input"])
                return json.dumps({"data": {"createCommitOnBranch": {"commit": {
                    "oid": "b" * 40, "url": "https://github.com/example/commit",
                }}}})
            response = responses[args[0]]
            return response.decode("utf-8") if isinstance(response, bytes) else response

        with patch.object(wiki, "gh_api", side_effect=gh):
            if error:
                try:
                    wiki.commit("github.com", "org/memory", "main", sha, "Test commit", plan)
                except wiki.WikiError as exc:
                    self.assertRegex(str(exc).lower(), error)
                else:
                    self.fail("Invalid plan was accepted")
                self.assertEqual(mutations, [])
                return
            result = wiki.commit("github.com", "org/memory", "main", sha, "Test commit", plan)
        self.assertEqual(result["oid"], "b" * 40)
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0]["expectedHeadOid"], sha)
        self.assertEqual(mutations[0]["branch"], {
            "repositoryNameWithOwner": "org/memory", "branchName": "main",
        })
        self.assertEqual([call for call in calls if "/trees/" in call],
                         [prefix + f"trees/{tree_sha}?recursive=1"])
        reads = [call for call in calls if "/blobs/" in call]
        self.assertEqual(len(reads), len(set(reads)))

    def ingest_plan(self, pages):
        return {"upsert": {
            "raw/a.txt": "Original",
            "wiki/sources/a.md": "[Source](../../raw/a.txt)\n",
            "wiki/index.md": pages["wiki/index.md"].replace("## Sources\n", "## Sources\n[A](sources/a.md)\n"),
            "wiki/log.md": pages["wiki/log.md"] + "\n## [2026-11-24] ingest | A\n",
        }}

    def test_commit_valid_ingest_reads_tree_once(self):
        self.remote_commit(wiki.DEFAULT_FILES, self.ingest_plan(wiki.DEFAULT_FILES))

    def test_images_cannot_satisfy_index_or_source_links(self):
        for path, issue in (("wiki/index.md", "unindexed_page"),
                            ("wiki/sources/a.md", "invalid_source_summary")):
            for form in ("inline", "reference", "shortcut"):
                with self.subTest(path=path, form=form):
                    plan = self.ingest_plan(wiki.DEFAULT_FILES)
                    pages = plan["upsert"]
                    text = pages[path]
                    destination = "sources/a.md" if path == "wiki/index.md" else "../../raw/a.txt"
                    original = "[A]" if path == "wiki/index.md" else "[Source]"
                    image = {
                        "inline": f"![Image]({destination})",
                        "reference": f"![Image][target]\n\n[target]: {destination}",
                        "shortcut": f"![Image]\n\n[Image]: {destination}",
                    }[form]
                    pages[path] = text.replace(f"{original}({destination})", image)
                    self.assertIn(issue, [item["kind"] for item in self.lint_pages(pages)])
                    self.remote_commit(wiki.DEFAULT_FILES, plan, error=issue)

    def test_lint_still_checks_image_targets(self):
        issues = self.lint_pages({
            "wiki/overview.md": "![Diagram](../raw/assets/missing.png)",
        })
        self.assertIn({"kind": "broken_link", "path": "wiki/overview.md",
                       "target": "../raw/assets/missing.png"}, issues)

    def test_commit_allows_preexisting_issues_and_agents_drift(self):
        pages = {**wiki.DEFAULT_FILES, "AGENTS.md": "# Old wording",
                 "wiki/overview.md": "[Broken](missing.md)"}
        self.remote_commit(pages, self.ingest_plan(pages))

    def test_commit_allows_unrelated_legacy_encoding(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/overview.md": "# Overview".encode("utf-16")}
        self.remote_commit(pages, self.ingest_plan(pages))

    def test_commit_detects_dangling_shortcut_reference(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/overview.md": "See [A].\n\n[A]: concepts/a.md\n",
                 "wiki/concepts/a.md": "# A\n"}
        self.remote_commit(pages, {"delete": ["wiki/concepts/a.md"], "upsert": {
            "wiki/log.md": "# Log\n\n## [2026-11-24] update | Delete A\n",
        }}, error="broken_link")

    def test_commit_new_source_cannot_reuse_preexisting_invalid_summary(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/sources/a.md": "# Orphan summary"}
        plan = self.ingest_plan(pages)
        plan["upsert"]["wiki/sources/a.md"] = "# Still missing the source link"
        self.remote_commit(pages, plan, error="invalid_source_summary")

    def test_commit_rejects_bad_manifest_or_source_plan(self):
        pages = wiki.DEFAULT_FILES
        upserts = self.ingest_plan(pages)["upsert"]
        log = upserts["wiki/log.md"]
        for changes, error in (
            ({"raw/a.txt": "Original", "wiki/log.md": log}, "missing_source_summary"),
            ({**upserts, "wiki/sources/a.md": "# Missing backlink"}, "invalid_source_summary"),
            ({**upserts, "wiki/index.md": pages["wiki/index.md"]}, "unindexed_page"),
            ({"raw/nested/a.txt": "Original", "wiki/log.md": log}, "permitted"),
            ({"AGENTS.md": "# Local", "wiki/log.md": log}, "permitted"),
            ({"memory.yaml": "version: 1", "wiki/log.md": log}, "permitted"),
        ):
            with self.subTest(error=error, paths=changes.keys()):
                self.remote_commit(pages, {"upsert": changes}, error=error)
        self.remote_commit({**pages, "memory.yaml": "version: 1\n"},
                           {"upsert": upserts}, error="v1 schema")

    def test_commit_rejects_invalid_log_changes(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/log.md": "# Log\n\n## [2026-11-23] update | Old\n"}
        old = pages["wiki/log.md"]
        for log, error in ((None, "append"), ("# Log\n", "append"),
                           (old + "## [2026-11-24] update | A\n", "ingest"),
                           (old + "## [2026-02-30] ingest | Bad\n", "append"),
                           (old + "<!--\n## [2026-11-24] ingest | Hidden\n-->\n", "append"),
                           (old + "```\n## [2026-11-24] ingest | In code\n", "append"),
                           (old + "## [2026-11-24] ingest | Valid\n## Bad\n", "invalid_log_entry")):
            with self.subTest(log=log):
                plan = self.ingest_plan(pages)
                if log is None:
                    del plan["upsert"]["wiki/log.md"]
                else:
                    plan["upsert"]["wiki/log.md"] = log
                self.remote_commit(pages, plan, error=error)

    def test_commit_rejects_summary_deletion_and_unindexing(self):
        pages = {**wiki.DEFAULT_FILES, **self.ingest_plan(wiki.DEFAULT_FILES)["upsert"]}
        log = pages["wiki/log.md"] + "\n## [2026-11-24] update | Cleanup\n"
        self.remote_commit(pages, {"upsert": {"wiki/log.md": log,
                                               "wiki/index.md": wiki.DEFAULT_FILES["wiki/index.md"]},
                                   "delete": ["wiki/sources/a.md"]}, error="missing_source_summary")
        self.remote_commit(pages, {"upsert": {"wiki/log.md": log,
                                               "wiki/index.md": wiki.DEFAULT_FILES["wiki/index.md"]}},
                           error="unindexed_page")
        self.remote_commit(pages, {"upsert": {"wiki/log.md": log}, "delete": ["wiki/sources/a.md"]},
                           error="broken_link|missing_source_summary")
        self.remote_commit(pages, {"upsert": {"wiki/log.md": log, "wiki/overview.md": "# Overview"}},
                           error="unindexed_page")

    def test_commit_allows_merging_pages_and_adding_attachment(self):
        index = wiki.DEFAULT_FILES["wiki/index.md"].replace("## Concepts\n", "## Concepts\n[A](concepts/a.md)\n")
        pages = {**wiki.DEFAULT_FILES, "wiki/index.md": index, "wiki/concepts/a.md": "# A"}
        plan = {"upsert": {
            "wiki/index.md": index.replace("concepts/a.md", "concepts/b.md"),
            "wiki/concepts/b.md": "# B",
            "raw/assets/exhibit.txt": "An attachment",
            "wiki/log.md": "# Log\n\n## [2026-11-24] update | Merge A into B\n",
        }, "delete": ["wiki/concepts/a.md"]}
        self.remote_commit(pages, plan)

    def test_commit_rejects_stale_snapshot_before_mutating(self):
        self.remote_commit(wiki.DEFAULT_FILES, self.ingest_plan(wiki.DEFAULT_FILES),
                           error="advanced", stale=True)

    def lint_pages(self, additions):
        pages = {**wiki.DEFAULT_FILES, **additions}
        with lint_snapshot(pages, pages.__getitem__) as reads:
            result = wiki.lint_memory("github.com", "o/r", self.backend.head)
        self.assertFalse(any(path.startswith("raw/assets/") for path in reads))
        return result["issues"]

    def test_source_summary_pairing(self):
        indexed = wiki.DEFAULT_FILES["wiki/index.md"].replace("## Sources\n", "## Sources\n[A](sources/a.md)\n")
        for additions, kind in (
            ({"raw/a.txt": "original"}, "missing_source_summary"),
            ({"wiki/sources/a.md": "[Source](../../raw/a.txt)"}, "invalid_source_summary"),
            ({"raw/a.txt": "original", "wiki/sources/a.md": "# No link"}, "invalid_source_summary"),
            ({"raw/a.txt": "original", "raw/a.pdf": "original"}, "invalid_source_summary"),
            ({"raw/nested/a.txt": "original"}, "nonstandard_path"),
            ({"wiki/sources/nested/a.md": "# Nested"}, "nonstandard_path"),
            ({"memory.yaml": "version: 1\n"}, "manifest_mismatch"),
        ):
            with self.subTest(additions=additions):
                self.assertIn(kind, [i["kind"] for i in self.lint_pages(additions)])
        self.assertEqual(self.lint_pages({
            "wiki/index.md": indexed, "raw/a.txt": "original", "README.md": "project",
            "wiki/sources/a.md": "[Source](../../raw/a.txt) [Asset](../../raw/assets/a.md#note)",
            "raw/assets/a.md": "# Note",
        }), [])
        self.assertIn({"kind": "schema_drift", "path": "AGENTS.md", "severity": "warning"},
                      self.lint_pages({"AGENTS.md": "# Old wording"}))

    def test_index_rules(self):
        pages = {"wiki/overview.md": "# Overview", "wiki/concepts/a.md": "# A"}
        index = wiki.DEFAULT_FILES["wiki/index.md"].replace("## Sources\n", "## Sources\n[A](concepts/a.md)\n")
        index += "[Overview](overview.md)\n"
        self.assertIn("unindexed_page", [i["kind"] for i in self.lint_pages({**pages, "wiki/index.md": index})])
        index = index.replace("## Concepts\n", "## Concepts\n[A][a]\n[A](concepts/a.md)\n")
        index += "\n[a]: concepts/a.md\n"
        self.assertEqual(self.lint_pages({**pages, "wiki/index.md": index}), [])
        self.assertIn("invalid_index", [i["kind"] for i in self.lint_pages(
            {"wiki/index.md": index.replace("## Entities", "## Other"), **pages})])
        hidden = wiki.DEFAULT_FILES["wiki/index.md"].replace(
            "## Concepts\n", "## Concepts\n<!--\n[A](concepts/a.md)\n-->\n")
        self.assertIn("unindexed_page", [i["kind"] for i in self.lint_pages(
            {"wiki/index.md": hidden, "wiki/concepts/a.md": "# A"})])

    def test_source_summary_can_cite_another_original(self):
        index = wiki.DEFAULT_FILES["wiki/index.md"].replace(
            "## Sources\n", "## Sources\n[A](sources/a.md)\n[B](sources/b.md)\n")
        self.assertEqual(self.lint_pages({
            "wiki/index.md": index, "raw/a.txt": "A", "raw/b.txt": "B",
            "wiki/sources/a.md": "[Original](../../raw/a.txt) [Context](../../raw/b.txt)",
            "wiki/sources/b.md": "[Original](../../raw/b.txt)",
        }), [])

    def test_log_entry_format(self):
        log = ("# Log\n\n## [2026-02-28] update | Valid\n"
               "## [2026-02-30] ingest | Bad date\n"
               "## [2026-02-28] other | Bad op\n## [2026-02-28] query | \n"
               "```\n## Not a heading\n```\n")
        self.assertEqual([i["kind"] for i in self.lint_pages({"wiki/log.md": log})],
                         ["invalid_log_entry"] * 3)

    def test_skill_ingest_example_is_a_valid_commit(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        example = re.search(r"```json\n(.*?)```", skill, re.S)
        self.assertIsNotNone(example)
        self.remote_commit(wiki.DEFAULT_FILES, json.loads(example[1]))

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
                            {"upsert": {"wiki/concepts/a.md": "# A"}})
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
                {"upsert": {"wiki/concepts/huge.md": "x" * (wiki.MAX_FILE_BYTES + 1)}},
                set())

    def test_bootstrap_can_create_manifest(self):
        wiki.validate_plan({"upsert": dict(wiki.DEFAULT_FILES)}, set(),
                           bootstrap=True)
        changes = wiki.file_changes({"upsert": dict(wiki.DEFAULT_FILES)},
                                    bootstrap=True)
        self.assertEqual(len(changes["additions"]), len(wiki.DEFAULT_FILES))

    def test_init_creates_v1_manifest(self):
        with patch.object(wiki, "snapshot", return_value="a" * 40), \
             patch.object(wiki, "list_files", return_value=[]), \
             patch.object(wiki, "commit", return_value={"oid": "b" * 40}) as commit:
            result = wiki.init_memory("github.com", "org/repo", "main")
        self.assertEqual(result["status"], "initialized")
        files = commit.call_args.args[5]["upsert"]
        self.assertEqual(set(files), {"AGENTS.md", "memory.yaml", "wiki/index.md",
                                      "wiki/log.md", "raw/.gitkeep"})
        self.assertEqual(files["memory.yaml"], (
            "version: 1\nformat: llm-wiki\npaths:\n  schema: AGENTS.md\n"
            "  index: wiki/index.md\n  log: wiki/log.md\n  sources: raw/\n"
            "  summaries: wiki/sources/\n  entities: wiki/entities/\n"
            "  concepts: wiki/concepts/\n  syntheses: wiki/syntheses/\n"
        ))
        self.assertEqual(files["wiki/index.md"],
                         "# Index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n")
        self.assertEqual(files["wiki/log.md"], "# Log\n")
        self.assertEqual(files["raw/.gitkeep"], "")
        self.assertIn("Teams add knowledge, not rules.", files["AGENTS.md"])

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

    def test_init_rejects_trial_manifest_with_same_version(self):
        existing = list(wiki.DEFAULT_FILES)
        trial = ("version: 1\nformat: llm-wiki\npaths:\n  schema: AGENTS.md\n"
                 "  index: wiki/index.md\n  pages: wiki/\n  sources: raw/\n  log: wiki/log.md\n")
        for manifest in (trial, "invalid manifest"):
            with self.subTest(manifest=manifest), \
                 patch.object(wiki, "snapshot", return_value="a" * 40), \
                 patch.object(wiki, "list_files", return_value=existing), \
                 patch.object(wiki, "read_file", return_value=manifest), \
                 patch.object(wiki, "commit") as commit:
                with self.assertRaisesRegex(wiki.WikiError, "V1 schema"):
                    wiki.init_memory("github.com", "org/repo", "main")
                commit.assert_not_called()

    def test_init_noop_with_agents_drift(self):
        pages = {**wiki.DEFAULT_FILES, "AGENTS.md": "",
                 "memory.yaml": wiki.DEFAULT_FILES["memory.yaml"].replace("\n", "\r\n")}
        with patch.object(wiki, "snapshot", return_value=self.backend.head), \
             patch.object(wiki, "list_files", return_value=list(pages)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, p: pages[p]), \
             patch.object(wiki, "commit") as commit:
            result = wiki.init_memory("github.com", "org/repo", "main")
        self.assertEqual(result["status"], "already_initialized")
        commit.assert_not_called()

    def test_init_never_overwrites_partial_memory(self):
        with patch.object(wiki, "snapshot", return_value=self.backend.head), \
             patch.object(wiki, "list_files", return_value=["wiki/index.md"]), \
             patch.object(wiki, "commit") as commit:
            with self.assertRaisesRegex(wiki.WikiError, "Partial"):
                wiki.init_memory("github.com", "org/repo", "main")
        commit.assert_not_called()

    def test_lint_rejects_links_escaping_repository(self):
        files = set(wiki.DEFAULT_FILES)
        with lint_snapshot(files, lambda path:
                           wiki.DEFAULT_FILES[path] + "[escape](../../secret.md)"
                           if path == "wiki/index.md" else wiki.DEFAULT_FILES[path]):
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
        with lint_snapshot(files, lambda p: pages.get(p, "")):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertFalse(any(i["kind"] in {"broken_link", "broken_anchor", "invalid_link"}
                             for i in result["issues"]))

    def test_lint_invalid_scheme_and_missing_anchor(self):
        files = set(wiki.DEFAULT_FILES)
        pages = {
            "wiki/index.md": "[Bad](javascript:alert) [Anchor](#missing)\n",
        }
        with lint_snapshot(files, lambda p: pages.get(p, "")):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(
            [issue["kind"] for issue in result["issues"] if "severity" not in issue],
            ["invalid_link", "broken_anchor"],
        )

    def test_lint_heading_anchor_uses_visible_link_text(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/index.md":
                 wiki.DEFAULT_FILES["wiki/index.md"].replace(
                     "# Index", "# [Project](https://example.com)\n\n[Jump](#project)")}
        with lint_snapshot(pages, pages.__getitem__):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(result["issues"], [])

    def test_lint_checks_uppercase_markdown_extension(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/notes.MD": "[Missing](missing.md)\n"}
        with lint_snapshot(pages, pages.__getitem__):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual([i for i in result["issues"] if i["kind"] != "nonstandard_path"], [
            {"kind": "broken_link", "path": "wiki/notes.MD", "target": "missing.md"},
        ])

    def test_lint_skips_out_of_scope_anchor_and_continues(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/index.md":
                 "[Setup](../README.md#setup)\n[Broken](missing.md)\n"}
        pages["README.md"] = "# Setup\n"
        with lint_snapshot(pages, pages.__getitem__) as reads:
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertNotIn("README.md", reads)
        self.assertEqual([i for i in result["issues"] if "severity" not in i], [
            {"kind": "broken_link", "path": "wiki/index.md", "target": "missing.md"},
        ])
        self.assertEqual(result["unchecked_anchors"], [
            {"path": "wiki/index.md", "target": "../README.md#setup"},
        ])

    def test_lint_reports_missing_out_of_scope_target_as_broken_link(self):
        pages = {**wiki.DEFAULT_FILES, "wiki/index.md": "[Setup](../README.md#setup)\n"}
        with lint_snapshot(pages, pages.__getitem__):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual([i for i in result["issues"] if "severity" not in i], [
            {"kind": "broken_link", "path": "wiki/index.md", "target": "../README.md#setup"},
        ])
        self.assertNotIn("unchecked_anchors", result)

    def test_markdown_link_lint(self):
        files = {"wiki/index.md", "wiki/a.md", *wiki.DEFAULT_FILES.keys()}
        with lint_snapshot(files, lambda p: (
                 "[Exists](a.md) [Missing](missing.md)" if p == "wiki/index.md" else ""
             )):
            result = wiki.lint_memory("github.com", "o/r", "a" * 40)
        self.assertEqual(
            [i["kind"] for i in result["issues"] if i["kind"] == "broken_link"], ["broken_link"])


class BudgetTests(unittest.TestCase):
    def setUp(self):
        wiki.reset_budget()
        self.addCleanup(wiki.reset_budget)

    def run_gh(self, stdout=b"ok"):
        return patch.object(wiki.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["gh"], 0, stdout=stdout, stderr=b""))

    def test_request_budget_stops_before_spawning(self):
        with patch.object(wiki, "MAX_REQUESTS", 2):
            wiki.reset_budget()
            with self.run_gh() as run:
                wiki.gh_api("github.com", ["a"])
                wiki.gh_api("github.com", ["b"])
                with self.assertRaisesRegex(wiki.WikiError, "request budget exhausted"):
                    wiki.gh_api("github.com", ["c"])
        self.assertEqual(run.call_count, 2)

    def test_response_byte_budget(self):
        with patch.object(wiki, "MAX_RESPONSE_BYTES", 5):
            wiki.reset_budget()
            with self.run_gh(b"abc") as run:
                wiki.gh_api("github.com", ["a"])
                with self.assertRaisesRegex(wiki.WikiError, "Response budget exhausted"):
                    wiki.gh_api("github.com", ["b"])
                with self.assertRaisesRegex(wiki.WikiError, "Response budget exhausted"):
                    wiki.gh_api("github.com", ["c"])
        self.assertEqual(run.call_count, 3)

    def test_time_budget_and_capped_timeout(self):
        clock = [1000.0]
        with patch.object(wiki.time, "monotonic", side_effect=lambda: clock[0]):
            wiki.reset_budget()
            clock[0] += wiki.MAX_RUN_SECONDS - 5
            with self.run_gh() as run:
                wiki.gh_api("github.com", ["a"])
                self.assertEqual(run.call_args.kwargs["timeout"], 5)
                clock[0] += 5
                with self.assertRaisesRegex(wiki.WikiError, "Time budget exhausted"):
                    wiki.gh_api("github.com", ["b"])
        self.assertEqual(run.call_count, 1)

    def test_reset_budget_starts_a_fresh_command(self):
        with patch.object(wiki, "MAX_REQUESTS", 1):
            wiki.reset_budget()
            with self.run_gh() as run:
                wiki.gh_api("github.com", ["a"])
                wiki.reset_budget()
                wiki.gh_api("github.com", ["b"])
        self.assertEqual(run.call_count, 2)

    def test_exhausted_budget_aborts_commit_before_mutation(self):
        sha, tree = "a" * 40, "c" * 40
        tree_entries = [{"path": path, "type": "blob", "mode": "100644", "sha": f"{i + 1:040x}"}
                        for i, path in enumerate(wiki.DEFAULT_FILES)]
        replies = {
            f"repos/o/r/git/commits/{sha}": json.dumps({"tree": {"sha": tree}}),
            f"repos/o/r/git/trees/{tree}?recursive=1": json.dumps(
                {"tree": tree_entries, "truncated": False}),
        }
        replies.update({f"repos/o/r/git/blobs/{entry['sha']}": wiki.DEFAULT_FILES[entry["path"]]
                        for entry in tree_entries})
        calls = []

        def run(command, **kwargs):
            endpoint = command[4]
            calls.append(endpoint)
            body = replies[endpoint]
            return subprocess.CompletedProcess(command, 0, stdout=body.encode(), stderr=b"")

        plan = {"upsert": {"wiki/log.md": wiki.DEFAULT_FILES["wiki/log.md"] + "\nx\n"}}
        with patch.object(wiki, "MAX_REQUESTS", 3), \
             patch.object(wiki.subprocess, "run", side_effect=run):
            wiki.reset_budget()
            with self.assertRaisesRegex(wiki.WikiError, "budget exhausted"):
                wiki.commit("github.com", "o/r", "main", sha, "msg", plan)
        self.assertNotIn("graphql", calls)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
