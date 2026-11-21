# Skills

A collection of agent skills for GitHub Copilot CLI.

## Available skills

| Skill | What it does |
| --- | --- |
| [MarkItDown](skills/markitdown/SKILL.md) | Converts local PDF, Word (`.docx`), PowerPoint (`.pptx`), and Excel (`.xlsx`) files to Markdown with Microsoft's MarkItDown CLI. |
| [Remote LLM Wiki](skills/remote-llm-wiki/SKILL.md) | Reads and updates a Markdown wiki directly in a GitHub or GitHub Enterprise repository. |

## Install in Copilot CLI

Install the collection as a plugin:

```sh
copilot plugin install simorex80/skills
```

Open a new Copilot CLI session and run `/skills info markitdown` to verify that the skill is available. To use only this skill in one project, copy the `skills/markitdown/` directory to `.github/skills/markitdown/` in that project and run `/skills reload` in an active session.

## Use MarkItDown

Use Python 3.10+ and install the converter in the same environment where Copilot CLI runs, with [pipx](https://pipx.pypa.io/stable/):

```sh
pipx install "markitdown[pdf,docx,pptx,xlsx]"
markitdown --help
```

Place a text-based PDF named `manual.pdf` in the working directory, then ask Copilot:

> Use the /markitdown skill to convert manual.pdf to manual.md.

Open `manual.md` and check that the extracted text and headings are present. If the destination already exists, provide a different filename. The destination filesystem must support hard links so the helper can publish the Markdown without overwriting an existing file. Image-only scans may need OCR, which this skill leaves disabled.

## Use Remote LLM Wiki

Install Python 3.10+ and [GitHub CLI](https://cli.github.com/) in the environment where Copilot runs. Authenticate `gh` for the wiki's GitHub hostname. If the collection is already installed, run `copilot plugin update simorex-skills`.

> Use /remote-llm-wiki to read the wiki at github.com/ORG/REPO on branch main and summarize the deployment notes.

Provide the hostname, repository and branch when requesting a wiki operation. For an update, describe the change and ask the skill to commit it to that branch. GitHub checks the active identity's repository permissions and branch rules. The skill fetches only the requested content and does not require a local checkout.

## Add a skill

Create `skills/<name>/SKILL.md` with YAML frontmatter containing `name` and `description`. Match `name` to the directory name, document any prerequisites, and add the skill to the table above. Run `/skills info <name>` and try a representative request before sharing it.

[Copilot CLI plugin documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing) · [Microsoft MarkItDown](https://github.com/microsoft/markitdown)
