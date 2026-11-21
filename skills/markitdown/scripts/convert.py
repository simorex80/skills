"""Convert a local workspace document and publish the Markdown without overwriting."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}


class ConversionError(Exception):
    """The document could not be converted or published."""


def local_path(value: str) -> Path:
    path = Path(value)
    if value.startswith(("//", "\\\\")) or (
        re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value)
        and not (path.drive and path.is_absolute())
    ):
        raise ConversionError("Use a local filesystem path.")
    return path


def convert(workspace: Path, source_value: str, destination_value: str | None) -> Path:
    source = (workspace / local_path(source_value)).resolve(strict=True)
    if not source.is_relative_to(workspace) or not source.is_file() or not os.access(source, os.R_OK):
        raise ConversionError("The source must be a readable regular file inside the workspace.")
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ConversionError("Use a PDF, Word (.docx), PowerPoint (.pptx), or Excel (.xlsx) file.")

    requested = (
        workspace / local_path(destination_value)
        if destination_value is not None
        else source.with_suffix(".md")
    )
    if requested.suffix.lower() != ".md":
        raise ConversionError("Use an .md destination.")
    parent = requested.parent.resolve()
    if not parent.is_relative_to(workspace):
        raise ConversionError("The destination must be inside the workspace.")
    destination = parent / requested.name
    collision = f"Destination already exists: {destination}. Choose a different filename."
    if os.path.lexists(destination):
        raise ConversionError(collision)
    parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix=".markitdown-", dir=parent) as directory:
        temporary = Path(directory) / "output.md"
        try:
            result = subprocess.run(
                ["markitdown", str(source), "-o", str(temporary)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ConversionError("Install the MarkItDown CLI in this environment.") from exc
        if result.returncode:
            raise ConversionError(f"MarkItDown exited with status {result.returncode}.")
        if not temporary.is_file():
            raise ConversionError("MarkItDown did not create an output file.")
        with temporary.open(encoding="utf-8") as output:
            if not any(line.strip() for line in output):
                message = "MarkItDown produced empty Markdown."
                if source.suffix.lower() == ".pdf":
                    message += " The PDF may be an image-only scan."
                raise ConversionError(message)

        # A hard link publishes the completed file only if the destination name is free.
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ConversionError(collision) from exc
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("-o", "--output", help="Markdown destination, relative to the workspace or absolute.")
    args = parser.parse_args()
    try:
        print(convert(Path.cwd().resolve(), args.source, args.output))
    except (ConversionError, OSError, RuntimeError, ValueError) as exc:
        print(f"markitdown skill: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
