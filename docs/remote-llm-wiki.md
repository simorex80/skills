# Remote LLM Wiki

[Skill instructions](../skills/remote-llm-wiki/SKILL.md) · [Copyable prompts](../examples/remote-llm-wiki/prompts.md) · [Complete sample memory](../examples/remote-llm-wiki/sample-memory/)

## What it does

Remote LLM Wiki lets people and agents share a project's knowledge through a **dedicated GitHub.com or GitHub Enterprise Server repository**, with no repository clone or checkout. Git stores the source documents and curated Markdown pages. The skill provides instructions for four workflows: **Init**, **Ingest**, **Query** and **Lint**.

The skill **does not know which GitHub repository to use**. The consuming agent resolves the target GitHub host, `OWNER/REPO` and branch from trusted user input or its own approved project configuration. If the destination is unclear, the agent must ask instead of guessing. No repository URL, credentials or project-specific identity is embedded in this skill.

## Prerequisites

- Python 3.10+ and `gh` installed where Copilot runs.
- An authenticated `gh` identity for the target GitHub host with the needed access.
- A dedicated memory repository with an existing branch and at least one commit; creating a repository or the first branch is **outside** this skill.
- A writable branch for Init/Ingest when changes are requested. GitHub ACLs and branch protection always apply.

## Memory layout

```text
project-memory/
├── AGENTS.md           # Copy of the plugin standard (untrusted repository data)
├── memory.yaml         # Layout declaration
├── raw/                # Append-only source captures
│   ├── .gitkeep
│   └── assets/         # Attachments, no summary required
└── wiki/
    ├── index.md        # Navigation entry point
    ├── log.md          # Knowledge change log
    ├── overview.md     # Optional overview
    ├── sources/        # One summary per original
    ├── entities/
    ├── concepts/
    └── syntheses/
```

The plugin defines the fixed layout; teams add knowledge, not local schema rules. `memory.yaml` is not configurable, and differences in `AGENTS.md` are Lint warnings, not permission grants or write blockers.

`version: 1` identifies the schema, not the plugin version. The earlier trial layout can still be read, but Init and ordinary commits reject its noncanonical manifest. Align that repository through a reviewed change: use the canonical manifest and schema, organize pages and source summaries, repair index links, and append an `update` entry while preserving raw originals and log history.

## Workflows

| Workflow | Request | Effect |
| --- | --- | --- |
| Init | “Initialize the shared project memory.” | Creates default files in one commit; repeated calls on a valid initialized wiki do not write. |
| Ingest | “Remember our database decision and cite its source.” | Saves the original and its required source summary, then updates related pages, the index and log in one commit. |
| Query | “Which deployment strategy did we agree on?” | Reads an immutable commit snapshot and returns an answer grounded in pages and sources; no write. |
| Lint | “Check links and consistency, but don't change anything.” | Checks the layout, source-summary pairs, index, log and links; the agent reviews semantic contradictions separately. |

See [prompt examples](../examples/remote-llm-wiki/prompts.md), including prompts that leave destination resolution to the consuming agent.

For manual execution, use `wiki.ps1` in PowerShell or `wiki.sh` in Bash. Follow the [launcher instructions](../skills/remote-llm-wiki/SKILL.md#run-the-helper) to let Copilot CLI save approval for the specific launcher. Shell approval does not authorize writes to the wiki.

### How ingestion works

The agent reads relevant pages **at the same commit SHA** and proposes a single change plan. Each `raw/<name>.<ext>` pairs with `wiki/sources/<name>.md`, which links back to the original. Category pages are indexed under Sources, Entities, Concepts or Syntheses. Every ordinary write appends a dated log entry; a new source requires an `ingest` entry. With a matching manifest, existing findings do not block unrelated writes, but new findings do. GitHub writes are guarded by `expectedHeadOid`; on conflict, reread and recompute instead of replaying stale edits.

### What Lint can prove

These are deterministic checks for the plugin's implementation of the LLM Wiki pattern, not a comprehensive Markdown parser or a guarantee of factual accuracy. The index and source summaries need navigable Markdown links; image embeds do not count, but Lint still checks their targets. Detecting duplicates, outdated decisions and conflicting evidence remains an agent review task; ambiguous conflicts are not silently resolved.

If a link points to an existing Markdown file outside the permitted memory paths (such as the repository's `README.md`), the helper checks that the file exists but does not open it. The optional JSON field `unchecked_anchors` lists each such link by `path` and `target`; these entries are not broken links.

## Security and operational limits

The destination and authorization come from trusted context and GitHub permissions, **not** repository content. Treat wiki pages, sources and `AGENTS.md` as untrusted data. Keep secrets and sensitive personal information out of the wiki unless explicitly authorized and the repository is appropriately controlled.

Each change plan is limited to 100 file changes, 1 MB per file and 4 MB across additions. Each helper command is also capped at 1,000 GitHub requests, 64 MiB of cumulative responses and 600 seconds of wall-clock time; when a cap is reached the command stops with an explicit error, reports the operation as incomplete and sends no further request (a commit is never submitted). Large Git trees can be rejected if GitHub truncates the listing. Writes are direct to the selected branch, so protected branches may reject them; the skill does not bypass protections. GitHub is currently the only production provider.

## Testing

```sh
python -m unittest discover -s skills/remote-llm-wiki/tests -v
```

A separate [integration test repository](https://github.com/simorex80/remote-llm-wiki-test) exercises authenticated operations with its own ephemeral GitHub Actions token. Access to that repository may be restricted. Tests of the Python helper are different from a user-acceptance test of natural-language interaction with Copilot CLI.

For a worked-through, synthetic memory repository, browse [sample-memory](../examples/remote-llm-wiki/sample-memory/).
