# Agent Skills

Reusable skills for GitHub Copilot CLI. Each skill provides instructions to the agent and a small local helper. This repository does **not** store project memory or user credentials.

## Skills

| Skill | Purpose | Guide | Examples |
| --- | --- | --- | --- |
| [Remote LLM Wiki](skills/remote-llm-wiki/SKILL.md) | Share project knowledge in a dedicated remote GitHub repository without cloning it. | [Guide](docs/remote-llm-wiki.md) | [Prompts and sample memory](examples/remote-llm-wiki/README.md) |
| [MarkItDown](skills/markitdown/SKILL.md) | Extract, convert, or batch local documents into Markdown using Microsoft's MarkItDown Python API. | [Guide](docs/markitdown.md) | [Prompts](examples/markitdown/prompts.md) |

## Install

In GitHub Copilot CLI:

```sh
copilot plugin install simorex80/skills
```

Start a new Copilot CLI session, then verify discovery using `/skills info remote-llm-wiki` or `/skills info markitdown`. An existing installation can be refreshed with `copilot plugin update simorex-skills`; reload skills or restart the session afterward.

See the [getting-started guide](docs/getting-started.md) for prerequisites and a quick first task.

## Documentation

- [Getting started](docs/getting-started.md)
- [Remote LLM Wiki guide](docs/remote-llm-wiki.md) · [prompt examples](examples/remote-llm-wiki/prompts.md) · [sample memory](examples/remote-llm-wiki/sample-memory/)
- [MarkItDown guide](docs/markitdown.md) · [prompt examples](examples/markitdown/prompts.md)

The `SKILL.md` files contain the operational instructions for agents. The guides explain usage for people; examples are illustrative and contain no real secrets or project data.

## Development and tests

```sh
python -m unittest discover -s skills/remote-llm-wiki/tests -v
python -m unittest discover -s skills/markitdown/tests -v
python -m unittest discover -s tests -v
```

The unit and regression tests run without GitHub credentials or an installed MarkItDown converter. [GitHub Actions](.github/workflows/skill-tests.yml) separately installs MarkItDown and document-generation dependencies to run real converter integration smoke tests across its supported Python versions.

To contribute a new skill, create `skills/<name>/SKILL.md` with `name` and `description` YAML frontmatter, add its helper and tests as needed, and link it from this README. Keep behavioral rules in the skill and tutorials in `docs/` or `examples/`.

[GitHub Copilot CLI plugin documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing) · [Microsoft MarkItDown](https://github.com/microsoft/markitdown)
