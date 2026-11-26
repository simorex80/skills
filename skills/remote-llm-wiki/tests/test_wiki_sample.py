"""Verify that the public sample satisfies the Wiki helper's contract."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wiki", SKILL_ROOT / "scripts" / "wiki.py")
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


class SampleTests(unittest.TestCase):
    def test_public_sample_conforms(self):
        sample = REPO_ROOT / "examples" / "remote-llm-wiki" / "sample-memory"
        self.assertTrue(sample.is_dir(), f"Public sample missing from source checkout: {sample}")
        files = {path.relative_to(sample).as_posix(): path.read_text(encoding="utf-8")
                 for path in sample.rglob("*") if path.is_file()}
        for path in ("AGENTS.md", "memory.yaml", "raw/.gitkeep"):
            self.assertEqual(files.get(path), wiki.DEFAULT_FILES[path])
        oids = {path: f"{i + 1:040x}" for i, path in enumerate(files)}
        by_oid = {oid: files[path] for path, oid in oids.items()}
        with patch.object(wiki, "_snapshot_entries", return_value=oids), \
             patch.object(wiki, "read_blob", side_effect=lambda h, r, oid: by_oid[oid]):
            self.assertEqual(wiki.lint_memory("github.com", "o/r", "a" * 40)["issues"], [])
