"""Exercise real document conversions with deterministic generated fixtures.

Requires the MarkItDown optional extras and reportlab, python-docx, python-pptx,
and openpyxl. This is intentionally separate from offline unit tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from reportlab.pdfgen import canvas


CONVERTER = Path(__file__).resolve().parents[1] / "scripts" / "convert.py"
MARKER = "SkillIntegrationFixture2026"


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "input"
        root.mkdir()
        output_root = Path(tmp) / "output"
        pdf = root / "sample-pdf.pdf"
        document = root / "sample-docx.docx"
        slides = root / "sample-pptx.pptx"
        spreadsheet = root / "sample-xlsx.xlsx"
        html = root / "sample-html.html"

        page = canvas.Canvas(str(pdf))
        page.drawString(70, 750, MARKER)
        page.save()

        word = Document()
        word.add_paragraph(MARKER)
        word.save(document)

        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        textbox = slide.shapes.add_textbox(50, 50, 600, 100)
        textbox.text_frame.text = MARKER
        deck.save(slides)

        workbook = Workbook()
        workbook.active["A1"] = MARKER
        workbook.save(spreadsheet)

        html.write_text(f"<html><body><p>{MARKER}</p></body></html>", encoding="utf-8")
        sources = [pdf, document, slides, spreadsheet, html]
        for suffix, content in (
            ("csv", f"marker,value\n{MARKER},1\n"),
            ("json", json.dumps({"marker": MARKER})),
            ("xml", f"<root><marker>{MARKER}</marker></root>"),
            ("txt", MARKER),
            ("htm", f"<p>{MARKER}</p>"),
        ):
            source = root / f"sample-{suffix}.{suffix}"
            source.write_text(content, encoding="utf-8")
            sources.append(source)

        def run(*args, timeout=90):
            return subprocess.run(
                [sys.executable, str(CONVERTER), *map(str, args)],
                cwd=Path(tmp), capture_output=True, encoding="utf-8", timeout=timeout, check=False,
            )

        for source in sources:
            result = run("extract", source)
            if result.returncode != 0:
                raise AssertionError(f"{source.suffix} conversion failed: {result.stderr}")
            if MARKER not in result.stdout:
                raise AssertionError(f"{source.suffix} conversion missing fixture marker")

        single = output_root / "single.md"
        result = run("convert", pdf, "--output", single)
        if result.returncode or MARKER not in single.read_text(encoding="utf-8"):
            raise AssertionError(f"Single conversion failed: {result.stderr}")
        result = run("convert", pdf, "--output", single)
        if result.returncode != 1 or "already exists" not in result.stderr:
            raise AssertionError(f"Single conversion did not reject an existing output: {result.stderr}")

        batch_args = ("batch", root, "--output-dir", output_root)
        result = run(*batch_args, timeout=240)
        if result.returncode != 0:
            raise AssertionError(f"Batch smoke test failed: {result.stderr}")
        for source in sources:
            output = output_root / (source.stem + ".md")
            if MARKER not in output.read_text(encoding="utf-8"):
                raise AssertionError(f"Missing converted content: {output}")

        result = run(*batch_args, "--skip-existing", timeout=240)
        expected = [f"output/{source.stem}.md" for source in sorted(sources)]
        if result.returncode or json.loads(result.stdout) != {
            "converted": [], "skipped": expected, "failed": [],
        }:
            raise AssertionError(f"Batch resume failed: {result.stdout} {result.stderr}")


if __name__ == "__main__":
    main()
