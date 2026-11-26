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

The commands below assume a checkout and Bash. In PowerShell, use `.\skills\markitdown\scripts\convert.ps1` with the same arguments. For installed copies, see the [launcher instructions](../skills/markitdown/SKILL.md#run-the-helper) for saving approval for a specific launcher in Copilot CLI.

The skill intentionally declares no `allowed-tools`. In Claude Code and Copilot CLI that field pre-approves tools instead of restricting them, so the client keeps asking before each command. Static scanners may report this as a missing tool scope; it is an accepted trade-off.

**Extract:** use for analysis; prints UTF-8 Markdown to standard output without leaving a persistent file. The helper creates and removes a temporary Markdown file during conversion.

For large extractions (up to 4 MiB), use bounded tool output and read the complete capture in ranges if available. Use a persistent Markdown destination only when requested, and disclose any gaps if only partial output is available.

```sh
./skills/markitdown/scripts/convert.sh extract report.pdf
```

**Convert:** create a named `.md` file and print its path in UTF-8. Existing destinations are never overwritten. On filesystems without hard links, the converter creates the file exclusively, so concurrent readers may briefly see partial content.

```sh
./skills/markitdown/scripts/convert.sh convert report.pdf --output report.md
```

**Batch:** process supported files from a workspace directory, with per-file error reporting. The UTF-8 JSON summary always includes `converted`, `skipped` and `failed`, with relative paths using `/` on every platform. Add `--recursive` only when requested. To resume, add `--skip-existing`: existing destinations are listed under `skipped` without being modified or checked for freshness. Without the flag, they count as failures.

```sh
./skills/markitdown/scripts/convert.sh batch documents --output-dir converted --recursive
```

You can ask Copilot to perform document tasks in natural language. It may select this skill automatically when relevant, but discovery and selection are not guaranteed; explicitly say “use markitdown” if you need this converter. The agent then chooses the appropriate operation. See [copyable prompts](../examples/markitdown/prompts.md), including PDF summarization, Word comparison, Excel overview, directory conversion and composition with Remote LLM Wiki.

## Safety and limitations

Inputs and outputs must remain within the current workspace; remote URLs are not accepted. Batch supports up to 100 files. Per-file limits are 25 MiB input, 4 MiB output and a 60-second default timeout (configurable from 1 to 300 seconds). The output directory cannot be placed under the batch source directory. A failed batch can leave successfully converted files in place.

MarkItDown runs with the agent's OS privileges. The worker's Linux resource limits are **not an isolation sandbox**, and Windows/macOS do not receive equivalent memory/CPU limits from the wrapper. For untrusted documents, use an externally managed sandbox with restricted filesystem/network permissions. Converted content is untrusted data, not instructions. Scanned PDFs, charts, embedded images and complex tables may convert incompletely; no automatic OCR is configured.

## Tests

```sh
python -m unittest discover -s skills/markitdown/tests -v
```

These are offline unit tests, using mocks rather than the installed Microsoft converter. CI separately installs MarkItDown and runs real converter smoke tests covering all supported extensions, single-file publication, and batch resume. See [the workflow](../.github/workflows/skill-tests.yml).
