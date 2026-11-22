# MarkItDown — copyable prompt examples

These prompts target **GitHub Copilot CLI**, with the plugin installed and a compatible Microsoft MarkItDown package available to the helper's Python interpreter. Document paths are examples: the files must already exist **inside the current workspace**. The skill does not download remote URLs, install dependencies or enable OCR services.

Copilot may select MarkItDown automatically for a document task, but selection is not guaranteed. Name the skill explicitly when you need this particular converter.

## Read and summarize a PDF (Extract)

> Use the markitdown skill to read `documents/architecture.pdf` and summarize the main architectural decisions. Do not create a persistent Markdown file. Mention any content that may not have been extracted reliably.

Expected: extract the PDF as Markdown and let Copilot summarize it. The helper uses a temporary file internally, then removes it; no converted `.md` remains in the workspace. Citations should refer to the source document where possible, not imply the extracted text is an exact visual reproduction.

## Create a Markdown file (Convert)

> Use markitdown to convert `manual.pdf` into `docs/manual.md`. Do not overwrite the destination if it exists.

Expected: one persistent `.md` file, or an explicit error if the destination already exists. The parent directory must stay inside the workspace.

## Compare two Word documents (Extract)

> Use markitdown to read `requirements-v1.docx` and `requirements-v2.docx`. Compare them and show added, removed and changed requirements. Note any tables or formatting that may have been lost during extraction.

Expected: two separate extracts followed by Copilot's comparison. No Markdown files are saved unless requested.

## Understand an Excel workbook (Extract)

> Use markitdown to read `reports/summary.xlsx`. Describe its sheets, main columns and noteworthy values. Flag any information that is unclear from the extraction.

Expected: a qualitative overview based on the extracted representation. **For precise arithmetic, formula evaluation, or full-fidelity spreadsheet analysis, use a spreadsheet-aware tool instead**; Markdown extraction can lose workbook semantics.

## Convert a directory (Batch)

> Use markitdown to convert all supported documents from `documents/` into `converted/`, including subdirectories. Report how many succeeded and list failed files with their errors.

Expected: a recursive batch and a per-file summary. The output directory must remain inside the workspace but **outside** the input directory. Existing destinations are not overwritten. Successful outputs remain even if another file fails. The current batch limit is 100 supported files.

## Read a document and update shared project memory (composed workflow)

> Use markitdown to read `documents/architecture-decisions.pdf`. Distinguish confirmed decisions from open questions and retain the document's provenance. Then use remote-llm-wiki to ingest the findings into the dedicated memory repository `github.com/ORG/MEMORY-REPO` on branch `main`, preserving the source reference. Before writing, confirm that this repository and branch are the intended destination.

Expected: MarkItDown extracts local content; Copilot interprets it; Remote LLM Wiki performs an authorized GitHub commit using the authenticated `gh` identity. **The original PDF is not uploaded automatically**. If preserving the original binary is required, arrange that separately; wiki ingestion may store a faithful Markdown source capture instead. The repository, host and branch in this prompt are placeholders to replace with a real trusted target.

## Ask naturally without naming the skill

> Summarize `documents/architecture.pdf` and identify any unresolved design decisions.

Expected: Copilot can choose MarkItDown if available and relevant. It may instead choose another suitable tool; explicitly request markitdown when use of this skill is important.

## Missing, scanned or unsupported input

> Read `scanned-contract.pdf` and summarize it using markitdown. If text extraction fails or seems incomplete, explain the limitation instead of inventing missing content.

Expected: image-only scans may produce empty or incomplete Markdown. No OCR is configured. If a file is missing, outside the workspace, or supplied only as a URL, the agent should request an approved local copy.

## Supported formats and boundaries

The wrapper accepts `pdf`, `docx`, `pptx`, `xlsx`, `html`, `htm`, `csv`, `json`, `xml` and `txt`. Each file is limited to 25 MiB input and 4 MiB extracted output, with a default timeout of 60 seconds (configurable up to 300 seconds). MarkItDown processes document content with the agent's OS permissions: use an externally isolated environment for untrusted documents.
