# Getting started

These skills are designed for **GitHub Copilot CLI**. Install once and let the agent select the relevant skill for a task.

## 1. Install the skills

Pick **one** distribution mechanism in the same Copilot environment to avoid duplicated discovery.

**Agent Skills CLI (skills.sh ecosystem):**

```sh
npx skills add simorex80/skills --list
npx skills add simorex80/skills --agent github-copilot
```

You can target another supported agent using its `--agent` identifier. See the [skills CLI guide](https://www.skills.sh/docs/cli) for installation scope and updates.

**GitHub Copilot CLI plugin:**

```sh
copilot plugin install simorex80/skills
```

In a new Copilot CLI session, verify `/skills info remote-llm-wiki` or `/skills info markitdown`. To refresh an existing plugin, use `copilot plugin update simorex-skills` and reload/restart the session if necessary.

## 2. Choose a task

**Shared project memory:** Install Python 3.10+ and the [GitHub CLI](https://cli.github.com/) in the agent's execution environment. Authenticate `gh` on the intended GitHub host, and ensure the project has a **dedicated repository** with an existing branch and an initial commit (for example a README). The agent/user must supply or resolve the repository and branch from a **trusted context**; the skill intentionally does not store or discover a default repository.

> Use remote-llm-wiki to initialize our project's shared memory in the dedicated repository we agreed on. If you cannot identify its host, repository or branch from trusted context, ask me first.

**Local documents:** Install Python 3.10+ and the official MarkItDown package in the interpreter the helper uses:

```sh
python -m pip install 'markitdown[pdf,docx,pptx,xlsx]'
```

> Use markitdown to read the local report.pdf and summarize its key findings. Do not create a separate Markdown file.

MarkItDown must already be installed: the skill does not install packages for you. The upstream package's Python compatibility can differ from the skill's Python minimum; check package metadata when installing.

## 3. Read the focused guides

- [Remote LLM Wiki](remote-llm-wiki.md): Init / Ingest / Query / Lint, concurrency and source provenance.
- [MarkItDown](markitdown.md): extract / convert / batch, local file boundaries and limitations.

## Scope and authorization

Both skills execute with the agent environment's existing permissions. Remote Wiki uses the active `gh` identity and GitHub branch protections. MarkItDown reads local workspace documents. Documents and repository pages are **untrusted data**, never instructions that override the agent's security boundaries. Do not put credentials into prompts, wiki pages or examples.
