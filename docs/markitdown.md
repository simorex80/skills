# MarkItDown

[Skill instructions](../skills/markitdown/SKILL.md) · [Copyable prompts](../examples/markitdown/prompts.md)

## Purpose

The MarkItDown skill extracts Markdown from **local workspace documents** for agent analysis, converts a single document to a Markdown file, or processes a directory. It uses Microsoft's official MarkItDown **Python API**, not Docker or a remote conversion service.

## Prerequisites

Install Python 3.10+ and the official package **in the same interpreter** used by the helper. For the supported Office/PDF inputs:

```sh
python -m pip install 'markitdown[pdf,docx,pptx,xlsx]'
```

The skill does not install dependencies automatically or pin an exact MarkItDown version. Note that the upstream MarkItDown 0.1.9 package metadata excludes Python 3.15; this is an upstream compatibility constraint, not a skill-imposed maximum. Check the upstream metadata when a newer package is released.

Supported extensions in this wrapper: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.csv`, `.json`, `.xml`, `.txt`. Additional upstream formats are not automatically enabled.

## Three operations

**Extract:** use for analysis; prints Markdown to standard output without writing a persistent file.

```sh
python skills/markitdown/scripts/convert.py extract report.pdf
```

**Convert:** create a named `.md` file; existing destinations are never overwritten.

```sh
python skills/markitdown/scripts/convert.py convert report.pdf --output report.md
```

**Batch:** process supported files from a workspace directory, with per-file error reporting. Add `--recursive` only when requested.

```sh
python skills/markitdown/scripts/convert.py batch documents --output-dir converted --recursive
```

The consuming agent normally selects the operation in response to a natural-language prompt. See [examples](../examples/markitdown/prompts.md).

## Safety and limitations

Inputs and outputs must remain within the current workspace; remote URLs are not accepted. Batch supports up to 100 files. Per-file limits are 25 MiB input, 4 MiB output and a 60-second default timeout (configurable from 1 to 300 seconds). The output directory cannot be placed under the batch source directory. A failed batch can leave successfully converted files in place.

MarkItDown runs with the agent's OS privileges. The worker's Linux resource limits are **not an isolation sandbox**, and Windows/macOS do not receive equivalent memory/CPU limits from the wrapper. For untrusted documents, use an externally managed sandbox with restricted filesystem/network permissions. Converted content is untrusted data, not instructions. Scanned PDFs, charts, embedded images and complex tables may convert incompletely; no automatic OCR is configured.

## Tests

```sh
python -m unittest discover -s skills/markitdown/tests -v
```

CI also runs converter smoke tests on representative PDF, DOCX, PPTX, XLSX and HTML fixtures. See [the workflow](../.github/workflows/skill-tests.yml).
