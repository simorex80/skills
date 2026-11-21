# MarkItDown — prompt examples

The skill handles **local files inside the current workspace**. It does not download URLs or install dependencies automatically.

## Read without saving (Extract)

> Use markitdown to read `report.pdf` and summarize its conclusions. Do not create an output Markdown file.

Expected: convert to Markdown in memory and answer from the extracted data, identifying potential gaps from diagrams or scanned pages.

## Create a Markdown document (Convert)

> Convert `specification.docx` to `specification.md` using markitdown. Do not overwrite an existing destination.

Expected: one output file inside the workspace, or an explicit error if the destination exists.

## Convert an entire directory (Batch)

> Convert the supported files under `documents/` to Markdown in `converted/`, including subdirectories. Report which files failed.

Expected: batch conversion with per-file summary, no output directory nested within the source.

## Compare documents (Extract)

> Read `proposal-a.docx` and `proposal-b.docx` with markitdown, then compare their requirements. Note any tables or formatting that may have been lost.

Expected: two independent extracts; no persistent Markdown files unless specifically requested.

## Unavailable or scanned input

> Read `scanned-contract.pdf` and summarize it.

If the input is a scan without extractable text, report the limitation instead of claiming to have performed OCR. If the file is missing or outside the workspace, ask the user to provide an approved local copy.
