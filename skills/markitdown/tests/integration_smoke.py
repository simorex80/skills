"""Exercise real document conversions with deterministic generated fixtures.

Requires the MarkItDown optional extras and reportlab, python-docx, python-pptx,
and openpyxl. This is intentionally separate from offline unit tests.
"""
from __future__ import annotations

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

        for source in (pdf, document, slides, spreadsheet, html):
            result = subprocess.run(
                [sys.executable, str(CONVERTER), "extract", str(source)],
                cwd=root, capture_output=True, text=True, timeout=90, check=False,
            )
            if result.returncode != 0:
                raise AssertionError(f"{source.suffix} conversion failed: {result.stderr}")
            if MARKER not in result.stdout:
                raise AssertionError(f"{source.suffix} conversion missing fixture marker")

        # Test publication and batch against actual converter API, too.
        result = subprocess.run(
            [sys.executable, str(CONVERTER), "batch", str(root), "--output-dir", str(output_root)],
            cwd=root, capture_output=True, text=True, timeout=240, check=False,
        )
        if result.returncode != 0:
            raise AssertionError(f"Batch smoke test failed: {result.stderr}")
        for source in (pdf, document, slides, spreadsheet, html):
            output = output_root / (source.stem + ".md")
            if MARKER not in output.read_text(encoding="utf-8"):
                raise AssertionError(f"Missing converted content: {output}")


if __name__ == "__main__":
    main()
