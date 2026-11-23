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
├── AGENTS.md           # Project knowledge conventions (untrusted repository data)
├── memory.yaml         # Layout declaration
├── raw/                # Append-only source captures
│   └── .gitkeep
└── wiki/
    ├── index.md        # Navigation entry point
    ├── log.md          # Knowledge change log
    └── ...             # Curated Markdown pages
```

**Important:** `memory.yaml` documents the current fixed layout; it is **not currently a runtime-configurable mapping**. The helper expects `wiki/index.md`, `wiki/log.md` and `raw/`. `AGENTS.md` can suggest how knowledge is organized inside the authorized wiki but cannot grant permissions or redirect writes. The sample is an example, not a template automatically copied by Init.

## Workflows

| Workflow | Request | Effect |
| --- | --- | --- |
| Init | “Initialize the shared project memory.” | Creates default files in one commit; repeated calls on a valid initialized wiki do not write. |
| Ingest | “Remember our database decision and cite its source.” | Saves a new source in `raw/`, updates the relevant wiki pages/index/log and commits together. |
| Query | “Which deployment strategy did we agree on?” | Reads an immutable commit snapshot and returns an answer grounded in pages and sources; no write. |
| Lint | “Check links and consistency, but don't change anything.” | Checks required files, links and anchors; the agent reviews semantic contradictions separately. |

See [prompt examples](../examples/remote-llm-wiki/prompts.md), including prompts that leave destination resolution to the consuming agent.

### How ingestion works

The agent reads the index and relevant pages **at the same commit SHA**, decides where the new information belongs, preserves its provenance under `raw/`, and constructs a single change plan. The Python helper validates paths and size limits and uses GitHub's `createCommitOnBranch` with `expectedHeadOid`. Sources under `raw/` are append-only. If the branch has advanced, the agent must reread and recompute the change plan rather than force-pushing or replaying stale edits.

### What Lint can prove

The helper checks required files, local Markdown links and selected heading anchors. It is not a comprehensive Markdown parser, and it cannot prove the truth or freshness of any claim. Detecting duplicates, outdated decisions and conflicting evidence remains an agent review task; ambiguous conflicts are not silently resolved.

If a link points to an existing Markdown file outside the permitted memory paths (such as the repository's `README.md`), the helper checks that the file exists but does not open it. The optional JSON field `unchecked_anchors` lists each such link by `path` and `target`; these entries are not broken links.

## Security and operational limits

The destination and authorization come from trusted context and GitHub permissions, **not** repository content. Treat wiki pages, sources and `AGENTS.md` as untrusted data. Keep secrets and sensitive personal information out of the wiki unless explicitly authorized and the repository is appropriately controlled.

Each change plan is limited to 100 file changes, 1 MB per file and 4 MB across additions. Large Git trees can be rejected if GitHub truncates the listing. Writes are direct to the selected branch, so protected branches may reject them; the skill does not bypass protections. GitHub is currently the only production provider.

## Testing

```sh
python -m unittest discover -s skills/remote-llm-wiki/tests -v
```

A separate [integration test repository](https://github.com/simorex80/remote-llm-wiki-test) exercises authenticated operations with its own ephemeral GitHub Actions token. Access to that repository may be restricted. Tests of the Python helper are different from a user-acceptance test of natural-language interaction with Copilot CLI.

For a worked-through, synthetic memory repository, browse [sample-memory](../examples/remote-llm-wiki/sample-memory/).
