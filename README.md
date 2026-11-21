# Skills

A collection of agent skills for GitHub Copilot CLI.

## Available skills

| Skill | What it does |
| --- | --- |
| [MarkItDown](skills/markitdown/SKILL.md) | Extracts, converts and batches local documents using Microsoft's MarkItDown Python API. |
| [Remote LLM Wiki](skills/remote-llm-wiki/SKILL.md) | Initializes, ingests, queries and lints project memory in a dedicated GitHub or GitHub Enterprise LLM Wiki repository. |

## Install in Copilot CLI

Install the collection as a plugin:

```sh
copilot plugin install simorex80/skills
```

Open a new Copilot CLI session and run `/skills info markitdown` to verify that the skill is available. To use only this skill in one project, copy the `skills/markitdown/` directory to `.github/skills/markitdown/` in that project and run `/skills reload` in an active session.

## Use MarkItDown (V2)

Install Microsoft MarkItDown in the Python environment used to invoke the skill script (a dedicated virtual environment is recommended). The skill requires Python 3.10 or newer. The current Microsoft MarkItDown release (0.1.9) independently declares support for Python 3.10–3.14 and excludes Python 3.15 in its package metadata; this is an upstream dependency constraint, not a restriction imposed by this skill. For example:

```sh
python -m pip install 'markitdown[pdf,docx,pptx,xlsx]'
```

The skill uses the official Python API, with plugins disabled. Three operations are available:

```sh
# Read a document into the agent without creating a persistent Markdown file
python skills/markitdown/scripts/convert.py extract document.pdf

# Create a Markdown file, without overwriting an existing destination
python skills/markitdown/scripts/convert.py convert document.pdf --output document.md

# Convert a directory, with one error report per failed file
python skills/markitdown/scripts/convert.py batch documents --output-dir converted --recursive
```

Supported local formats: PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML and TXT. Inputs must be inside the workspace. The wrapper limits document size (25 MiB), output size (4 MiB), and time (60 seconds by default). Batch operations process up to 100 files and return a JSON summary. URLs, network OCR and third-party plugins are not enabled. Linux workers also enforce resource limits; these do not provide OS or network isolation. For untrusted documents, use a sandbox provided by the execution environment.

Run MarkItDown V2 offline unit tests:

```sh
python -m unittest discover -s skills/markitdown/tests -v
```

The GitHub Actions workflow tests MarkItDown on Python 3.10–3.14 (the currently installable upstream range) and Remote LLM Wiki on Python 3.10–3.15, exercising real PDF, DOCX, PPTX, XLSX and HTML fixtures. An upstream release may introduce breaking API changes; CI should expose those without constraining installations to a fixed release.

## Use Remote LLM Wiki (V2)

Install Python 3.10+ and [GitHub CLI](https://cli.github.com/), then authenticate `gh` to the GitHub.com or GitHub Enterprise Server host that owns the dedicated memory repository. If already installed, refresh the Copilot plugin (`copilot plugin update simorex-skills`) and reload skills as needed.

The repository must already have a branch with at least one commit, for example a README created during repository provisioning. The skill does not create repositories or initialize a branch without a commit.

Ask Copilot naturally, specifying the trusted target repository and branch:

> Use /remote-llm-wiki to initialize project memory at github.com/ORG/MEMORY-REPO on branch main.

> Use /remote-llm-wiki to ingest this architecture decision into the project's shared memory.

> Use /remote-llm-wiki to answer which deployment strategy was agreed, citing the original source.

> Use /remote-llm-wiki to lint the project's knowledge base.

The skill runs **Init / Ingest / Query / Lint** over GitHub's remote APIs, without a clone. Ingest creates immutable original captures under `raw/` and updates Markdown wiki pages under `wiki/` in a single guarded commit. All writes use the active client's authenticated identity, repository permissions and branch rules. The project schema is `AGENTS.md`; `memory.yaml` declares the expected layout. Neither grants extra permissions.

Offline tests (no GitHub authentication required):

```sh
python -m unittest discover -s skills/remote-llm-wiki/tests -v
```

The dedicated [Remote LLM Wiki integration repository](https://github.com/simorex80/remote-llm-wiki-test) runs an authenticated end-to-end workflow against a disposable branch. The workflow references a reviewed source commit; keep its ref aligned when verifying a new PR. The repository workflow uses its ephemeral GitHub Actions token, not a personal access token. No production wiki data is used.

See [the skill instructions](skills/remote-llm-wiki/SKILL.md) for the exact procedures and limits.

## Add a skill

Create `skills/<name>/SKILL.md` with YAML frontmatter containing `name` and `description`. Match `name` to the directory name, document any prerequisites, and add the skill to the table above. Run `/skills info <name>` and try a representative request before sharing it.

[Copilot CLI plugin documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing) · [Microsoft MarkItDown](https://github.com/microsoft/markitdown)
