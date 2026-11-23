"""Deterministic MarkItDown V2 tests: no converter installation required."""
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert.py"
SPEC = importlib.util.spec_from_file_location("markitdown_v2", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class TestV2(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name).resolve()
        self.source = self.workspace / "manual.pdf"
        self.source.write_bytes(b"%PDF-1.4\n")

    @staticmethod
    def fake_worker(source, target, timeout):
        target.write_text("# Converted\n", encoding="utf-8")

    def test_extract_leaves_no_persistent_file(self):
        with patch.object(converter, "_run_worker", side_effect=self.fake_worker):
            result = converter.extract(self.workspace, self.source.name)
        self.assertEqual(result, "# Converted\n")
        self.assertEqual(list(self.workspace.iterdir()), [self.source])

    def test_extract_cli_writes_utf8_with_legacy_stdout_encoding(self):
        markdown = "# \u6771\n"
        def worker(source, target, timeout):
            target.write_bytes(markdown.encode("utf-8"))
        with io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as stdout, \
             patch("sys.stdout", stdout), patch("sys.stderr", io.StringIO()) as stderr, \
             patch.object(Path, "cwd", return_value=self.workspace), \
             patch.object(converter, "_run_worker", side_effect=worker):
            self.assertEqual(converter.main(["extract", self.source.name]), 0, stderr.getvalue())
            stdout.flush()
            self.assertEqual(stdout.buffer.getvalue(), b"# \xe6\x9d\xb1\n")

    def test_convert_cli_reports_unicode_destination_in_utf8(self):
        source = self.workspace / "\u6771.txt"
        source.touch()
        destination = source.with_suffix(".md")
        with io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as stdout, \
             patch("sys.stdout", stdout), patch("sys.stderr", io.StringIO()) as stderr, \
             patch.object(Path, "cwd", return_value=self.workspace), \
             patch.object(converter, "_run_worker", side_effect=self.fake_worker):
            self.assertEqual(converter.main(["convert", source.name]), 0, stderr.getvalue())
            stdout.flush()
            self.assertEqual(stdout.buffer.getvalue().decode("utf-8").splitlines(), [str(destination)])
        self.assertEqual(destination.read_text(encoding="utf-8"), "# Converted\n")

    def test_batch_cli_reports_unicode_paths_in_utf8(self):
        source = self.workspace / "input"
        source.mkdir()
        (source / "\u6771.txt").touch()

        def worker(path, target, timeout):
            if path.name == "\u897f.txt":
                raise converter.ConversionError("bad document")
            self.fake_worker(path, target, timeout)

        for output, status, failures in (
            ("result", 0, []),
            ("mixed", 1, [{"source": "\u897f.txt", "error": "bad document"}]),
        ):
            with self.subTest(status=status):
                if failures:
                    (source / "\u897f.txt").touch()
                with io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as stdout, \
                     patch("sys.stdout", stdout), patch("sys.stderr", io.StringIO()) as stderr, \
                     patch.object(Path, "cwd", return_value=self.workspace), \
                     patch.object(converter, "_run_worker", side_effect=worker):
                    self.assertEqual(converter.main(["batch", "input", "--output-dir", output]),
                                     status, stderr.getvalue())
                    stdout.flush()
                    reply = stdout.buffer.getvalue().decode("utf-8")
                    self.assertTrue(reply, stderr.getvalue())
                    self.assertEqual(json.loads(reply), {
                        "converted": [f"{output}/\u6771.md"], "failed": failures,
                    })
                self.assertEqual((self.workspace / output / "\u6771.md").read_text(encoding="utf-8"),
                                 "# Converted\n")

    def test_convert_and_cleanup(self):
        with patch.object(converter, "_run_worker", side_effect=self.fake_worker):
            result = converter.convert(self.workspace, self.source.name, "docs/result.md")
        self.assertEqual(result.read_text(encoding="utf-8"), "# Converted\n")
        self.assertEqual(list(result.parent.iterdir()), [result])

    def test_existing_destination_preserved(self):
        target = self.workspace / "manual.md"
        target.write_text("original", encoding="utf-8")
        with patch.object(converter, "_run_worker") as worker:
            with self.assertRaisesRegex(converter.ConversionError, "already exists"):
                converter.convert(self.workspace, self.source.name)
        worker.assert_not_called()
        self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_concurrent_destination_creation_preserved(self):
        target = self.workspace / "manual.md"
        def race(source, temporary, timeout):
            self.fake_worker(source, temporary, timeout)
            target.write_text("keep", encoding="utf-8")
        with patch.object(converter, "_run_worker", side_effect=race):
            with self.assertRaisesRegex(converter.ConversionError, "already exists"):
                converter.convert(self.workspace, self.source.name)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_source_escape_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            external = Path(tmp) / "outside.pdf"
            external.touch()
            with self.assertRaisesRegex(converter.ConversionError, "workspace"):
                converter.extract(self.workspace, str(external))
            link = self.workspace / "link.pdf"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unsupported")
            with self.assertRaisesRegex(converter.ConversionError, "workspace"):
                converter.extract(self.workspace, link.name)

    def test_destination_escape_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(converter.ConversionError, "workspace"):
                converter.convert(self.workspace, self.source.name, str(Path(tmp) / "out.md"))
            link = self.workspace / "link"
            try:
                link.symlink_to(tmp, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unsupported")
            with self.assertRaisesRegex(converter.ConversionError, "workspace"):
                converter.convert(self.workspace, self.source.name, "link/out.md")

    def test_remote_and_unsupported_sources_rejected(self):
        for name in ("https://example.com/test.pdf", "file:///tmp/test.pdf", "//server/file.pdf"):
            with self.subTest(name=name):
                with self.assertRaises(converter.ConversionError):
                    converter.extract(self.workspace, name)
        other = self.workspace / "archive.zip"
        other.touch()
        with self.assertRaisesRegex(converter.ConversionError, "Unsupported"):
            converter.extract(self.workspace, other.name)

    def test_size_limit(self):
        with patch.object(converter, "MAX_SOURCE_BYTES", 1), patch.object(converter, "_run_worker") as worker:
            with self.assertRaisesRegex(converter.ConversionError, "exceeds"):
                converter.extract(self.workspace, self.source.name)
        worker.assert_not_called()

    def test_failed_conversion_cleans_partial_result(self):
        with patch.object(converter, "_run_worker", side_effect=converter.ConversionError("failed")):
            with self.assertRaisesRegex(converter.ConversionError, "failed"):
                converter.convert(self.workspace, self.source.name)
        self.assertEqual(list(self.workspace.iterdir()), [self.source])

    def test_worker_timeout_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.md"
            with patch.object(converter.subprocess, "run", side_effect=subprocess.TimeoutExpired("cmd", 1)):
                with self.assertRaisesRegex(converter.ConversionError, "timed out"):
                    converter._run_worker(self.source, result, 1)
            with patch.object(converter.subprocess, "run", return_value=subprocess.CompletedProcess([], 4, b"", b"bad document")):
                with self.assertRaisesRegex(converter.ConversionError, "bad document"):
                    converter._run_worker(self.source, result, 1)

    def test_empty_and_oversized_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.md"
            for text, size, message in ((" \n", 100, "Empty"), ("too large", 1, "exceeds")):
                result.write_text(text, encoding="utf-8")
                with patch.object(converter, "MAX_OUTPUT_BYTES", size):
                    with patch.object(converter.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
                        with self.assertRaisesRegex(converter.ConversionError, message):
                            converter._run_worker(self.source, result, 1)

    def test_batch_success_and_independent_errors(self):
        folder = self.workspace / "input"
        folder.mkdir()
        (folder / "a.html").write_text("<h1>Hello</h1>", encoding="utf-8")
        (folder / "b.csv").write_text("a,b", encoding="utf-8")
        (folder / "skip.zip").touch()
        def worker(source, output, timeout):
            if source.name == "b.csv":
                raise converter.ConversionError("bad document")
            self.fake_worker(source, output, timeout)
        with patch.object(converter, "_run_worker", side_effect=worker):
            result = converter.batch(self.workspace, "input", "result")
        self.assertEqual(result["converted"], ["result/a.md"])
        self.assertEqual(result["failed"], [{"source": "b.csv", "error": "bad document"}])

    def test_batch_recursive_and_limit(self):
        nested = self.workspace / "input/nested"
        nested.mkdir(parents=True)
        (nested / "a.json").write_text('{"a":1}', encoding="utf-8")
        (nested / "b.csv").touch()
        def worker(source, output, timeout):
            if source.name == "b.csv":
                raise converter.ConversionError("bad document")
            self.fake_worker(source, output, timeout)
        with patch.object(converter, "_run_worker", side_effect=worker):
            self.assertEqual(converter.batch(self.workspace, "input", "result")["converted"], [])
            result = converter.batch(self.workspace, "input", "result", recursive=True)
        self.assertEqual(result["converted"], ["result/nested/a.md"])
        self.assertEqual(result["failed"], [{"source": "nested/b.csv", "error": "bad document"}])
        with patch.object(converter, "MAX_BATCH_FILES", 0):
            with self.assertRaisesRegex(converter.ConversionError, "limit"):
                converter.batch(self.workspace, "input", "result", recursive=True)
        with self.assertRaisesRegex(converter.ConversionError, "nested"):
            converter.batch(self.workspace, "input", "input/output")

    def test_batch_collision_rejected_before_publication(self):
        folder = self.workspace / "input"
        folder.mkdir()
        (folder / "same.html").write_text("<h1>One</h1>", encoding="utf-8")
        (folder / "same.txt").write_text("Two", encoding="utf-8")
        with patch.object(converter, "_run_worker") as worker:
            with self.assertRaisesRegex(converter.ConversionError, "collision"):
                converter.batch(self.workspace, "input", "output")
        worker.assert_not_called()
        self.assertFalse((self.workspace / "output").exists())

    def test_timeout_validation(self):
        for invalid in ("0", "301", "non-number"):
            with self.assertRaises(Exception):
                converter._timeout(invalid)
        self.assertEqual(converter._timeout("30"), 30)


if __name__ == "__main__":
    unittest.main()
