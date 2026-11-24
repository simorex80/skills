import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wiki", ROOT / "skills" / "remote-llm-wiki" / "scripts" / "wiki.py")
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


class SampleTests(unittest.TestCase):
    def test_public_sample_conforms(self):
        sample = ROOT / "examples" / "remote-llm-wiki" / "sample-memory"
        files = {path.relative_to(sample).as_posix(): path.read_text(encoding="utf-8")
                 for path in sample.rglob("*") if path.is_file()}
        for path in ("AGENTS.md", "memory.yaml", "raw/.gitkeep"):
            self.assertEqual(files.get(path), wiki.DEFAULT_FILES[path])
        with patch.object(wiki, "list_files", return_value=list(files)), \
             patch.object(wiki, "read_file", side_effect=lambda h, r, sha, path: files[path]):
            self.assertEqual(wiki.lint_memory("github.com", "o/r", "a" * 40)["issues"], [])
