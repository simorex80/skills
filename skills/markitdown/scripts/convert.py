"""Bounded, local-only MarkItDown document extraction and publication.

The parent process checks paths and publishes completed files without replacing them.
The worker imports Microsoft's MarkItDown Python API in a timeout-controlled process.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

FORMATS = frozenset({".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".csv", ".json", ".xml", ".txt"})
MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_BATCH_FILES = 100
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300


class ConversionError(Exception):
    """Validation, conversion, or publication failed."""


def local_path(value: str) -> Path:
    if not value or value.startswith(("//", "\\\\")) or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and os.name != "nt":
        raise ConversionError("Only local filesystem paths are supported.")
    return Path(value)


def source_path(workspace: Path, value: str) -> Path:
    try:
        path = (workspace / local_path(value)).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ConversionError(f"Cannot resolve source: {exc}") from exc
    if not path.is_relative_to(workspace) or not path.is_file():
        raise ConversionError("Source must be a regular file inside the workspace.")
    if path.suffix.lower() not in FORMATS:
        raise ConversionError(f"Unsupported source format: {path.suffix}.")
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise ConversionError(f"Source exceeds {MAX_SOURCE_BYTES} byte limit.")
    return path


def destination_path(workspace: Path, value: str) -> Path:
    proposed = workspace / local_path(value)
    if proposed.suffix.lower() != ".md":
        raise ConversionError("Destination must end with .md.")
    parent = proposed.parent.resolve(strict=True) if proposed.parent.exists() else proposed.parent.resolve()
    if not parent.is_relative_to(workspace):
        raise ConversionError("Destination must be inside the workspace.")
    return parent / proposed.name


def _run_worker(source: Path, temporary: Path, timeout: int) -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "_worker", str(source), str(temporary)]
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(f"Conversion timed out after {timeout} seconds.") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[:500].strip()
        raise ConversionError(f"MarkItDown failed (exit {result.returncode}): {detail}")
    if not temporary.is_file():
        raise ConversionError("MarkItDown did not produce Markdown.")
    if temporary.stat().st_size > MAX_OUTPUT_BYTES:
        raise ConversionError(f"Markdown exceeds {MAX_OUTPUT_BYTES} byte limit.")
    if not temporary.read_text(encoding="utf-8").strip():
        raise ConversionError("Empty Markdown (the source may require OCR).")


def _worker(source: Path, temporary: Path) -> int:
    """Invoked in a separate child process; never enables plugins or remote services."""
    try:
        from markitdown import MarkItDown
        result = MarkItDown(enable_plugins=False).convert_local(str(source))
        markdown = result.text_content
        if not isinstance(markdown, str):
            raise ConversionError("MarkItDown returned no text content.")
        content = markdown.encode("utf-8")
        if len(content) > MAX_OUTPUT_BYTES:
            raise ConversionError("Markdown exceeds output size limit.")
        temporary.write_bytes(content)
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def extract(workspace: Path, source_value: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    source = source_path(workspace, source_value)
    with TemporaryDirectory(prefix="markitdown-") as directory:
        temporary = Path(directory) / "result.md"
        _run_worker(source, temporary, timeout)
        return temporary.read_text(encoding="utf-8")


def convert(workspace: Path, source_value: str, destination_value: str | None = None,
            timeout: int = DEFAULT_TIMEOUT) -> Path:
    source = source_path(workspace, source_value)
    destination = destination_path(workspace, destination_value or str(source.with_suffix(".md")))
    if os.path.lexists(destination):
        raise ConversionError(f"Destination already exists: {destination}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = destination_path(workspace, str(destination))
    with TemporaryDirectory(prefix=".markitdown-", dir=destination.parent) as directory:
        temporary = Path(directory) / "result.md"
        _run_worker(source, temporary, timeout)
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ConversionError(f"Destination already exists: {destination}.") from exc
    return destination


def batch(workspace: Path, input_dir: str, output_dir: str, *, recursive: bool = False,
          timeout: int = DEFAULT_TIMEOUT) -> dict:
    directory = (workspace / local_path(input_dir)).resolve(strict=True)
    if not directory.is_relative_to(workspace) or not directory.is_dir():
        raise ConversionError("Input directory must be inside the workspace.")
    target_root = (workspace / local_path(output_dir)).resolve()
    if not target_root.is_relative_to(workspace) or target_root == directory:
        raise ConversionError("Output directory must be inside the workspace and differ from input.")
    if target_root.is_relative_to(directory):
        raise ConversionError("Output directory cannot be nested inside input directory.")
    candidates = sorted(directory.rglob("*") if recursive else directory.iterdir())
    sources = [p for p in candidates if p.is_file() and p.suffix.lower() in FORMATS]
    # Two distinct formats can map to the same Markdown destination.
    # Reject the whole batch before publishing any output.
    destinations: dict[str, Path] = {}
    for entry in sources:
        target = str(entry.relative_to(directory).with_suffix(".md")).casefold()
        if target in destinations:
            other = destinations[target]
            raise ConversionError(
                f"Batch destination collision: {other.relative_to(directory)} and "
                f"{entry.relative_to(directory)}."
            )
        destinations[target] = entry
    if len(sources) > MAX_BATCH_FILES:
        raise ConversionError(f"Batch exceeds {MAX_BATCH_FILES} file limit.")
    summary: dict = {"converted": [], "failed": []}
    for entry in sources:
        relative = entry.relative_to(directory)
        destination = target_root / relative.with_suffix(".md")
        try:
            path = convert(workspace, str(entry), str(destination), timeout)
            summary["converted"].append(str(path.relative_to(workspace)))
        except (ConversionError, OSError, ValueError) as exc:
            summary["failed"].append({"source": str(relative), "error": str(exc)})
    return summary


def _timeout(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Timeout must be an integer.") from exc
    if not 1 <= number <= MAX_TIMEOUT:
        raise argparse.ArgumentTypeError(f"Timeout must be between 1 and {MAX_TIMEOUT} seconds.")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("extract", "convert", "batch"):
        command = subcommands.add_parser(name)
        command.add_argument("--timeout", type=_timeout, default=DEFAULT_TIMEOUT)
        if name == "batch":
            command.add_argument("directory")
            command.add_argument("--output-dir", required=True)
            command.add_argument("--recursive", action="store_true")
        else:
            command.add_argument("source")
            if name == "convert":
                command.add_argument("--output")
    worker = subcommands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("source")
    worker.add_argument("temporary")
    args = parser.parse_args(argv)
    if args.command == "_worker":
        return _worker(Path(args.source), Path(args.temporary))
    try:
        workspace = Path.cwd().resolve()
        if args.command == "extract":
            sys.stdout.write(extract(workspace, args.source, args.timeout))
        elif args.command == "convert":
            print(convert(workspace, args.source, args.output, args.timeout))
        else:
            result = batch(workspace, args.directory, args.output_dir,
                           recursive=args.recursive, timeout=args.timeout)
            print(json.dumps(result, ensure_ascii=False))
            return 1 if result["failed"] else 0
    except (ConversionError, OSError, RuntimeError, ValueError) as exc:
        print(f"markitdown skill: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
