# Agent Skills

Reusable skills for GitHub Copilot CLI. Each skill provides instructions to the agent and a small local helper. This repository does **not** store project memory or user credentials.

## Skills

| Skill | Purpose | Guide | Examples |
| --- | --- | --- | --- |
| [Remote LLM Wiki](skills/remote-llm-wiki/SKILL.md) | Share project knowledge in a dedicated remote GitHub repository without cloning it. | [Guide](docs/remote-llm-wiki.md) | [Prompts and sample memory](examples/remote-llm-wiki/README.md) |
| [MarkItDown](skills/markitdown/SKILL.md) | Extract, convert, or batch local documents into Markdown using Microsoft's MarkItDown Python API. | [Guide](docs/markitdown.md) | [Prompts](examples/markitdown/prompts.md) |

## Install

Choose **one** installation method for a given Copilot environment; installing the same skills using both methods may produce duplicates.

### Agent Skills CLI (skills.sh ecosystem)

List the available skills before installation:

```sh
npx skills add simorex80/skills --list
```

Install both skills for GitHub Copilot (project scope):

```sh
npx skills add simorex80/skills --agent github-copilot
```

For other supported agents, select the corresponding `--agent` value. Check the [skills CLI documentation](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) for supported agents and global installation.

### GitHub Copilot CLI plugins (independent)

Register the marketplace, then install only the plugins you want:

```sh
copilot plugin marketplace add simorex80/skills
copilot plugin marketplace browse simorex-skills
copilot plugin install remote-llm-wiki@simorex-skills
copilot plugin install markitdown@simorex-skills
```

Each plugin is independent. Restart the session to verify skill discovery. To update an installed plugin, use `copilot plugin update remote-llm-wiki` or `copilot plugin update markitdown`. Refresh the catalog with `copilot plugin marketplace update simorex-skills`.

### Claude Code plugins (independent)

```sh
claude plugin marketplace add simorex80/skills
claude plugin install remote-llm-wiki@simorex-skills
claude plugin install markitdown@simorex-skills
```

The same `skills/<name>/SKILL.md` files are used by skills.sh, Copilot, and Claude Code; no skill content is duplicated.

`review-skill` is maintainer tooling, not a marketplace plugin. The `skills` CLI excludes it from discovery and installation by default.

See the [getting-started guide](docs/getting-started.md) for prerequisites and a quick first task.

## Documentation

- [Getting started](docs/getting-started.md)
- [Remote LLM Wiki guide](docs/remote-llm-wiki.md) · [prompt examples](examples/remote-llm-wiki/prompts.md) · [sample memory](examples/remote-llm-wiki/sample-memory/)
- [MarkItDown guide](docs/markitdown.md) · [prompt examples](examples/markitdown/prompts.md)

The `SKILL.md` files contain the operational instructions for agents. The guides explain usage for people; examples are illustrative and contain no real secrets or project data.

## Agent-assisted development

Development agents should follow [AGENTS.md](AGENTS.md), the single repository guide for architecture, contribution, security, tests, and plugin distribution. These instructions apply to maintaining this repository, not to users installing the skills.

## Development and tests

```sh
python -m unittest discover -s skills/remote-llm-wiki/tests -v
python -m unittest discover -s skills/markitdown/tests -v
python -m unittest discover -s tests -v
```

The unit and regression tests run without GitHub credentials or an installed MarkItDown converter. [GitHub Actions](.github/workflows/skill-tests.yml) separately installs MarkItDown and document-generation dependencies to run real converter integration smoke tests across its supported Python versions.

The root `tests/` suite checks marketplace metadata and shared skill documentation requirements without importing plugin code. Tests that exercise plugin code live in `skills/<name>/tests/`, including the Remote LLM Wiki check for its public example in the source checkout.

The [skill distribution workflow](.github/workflows/skills-distribution.yml) checks the root plugin manifest, discovers every `skills/*/SKILL.md`, and verifies standalone installation with the current skills CLI on relevant PRs, main branch changes, and weekly. It installs into a disposable directory with telemetry disabled; these are compatibility checks, not catalog registration or synthetic download events.

To **attempt** skills.sh indexing manually, open **Actions → Skill distribution → Run workflow**, select `main`, enable **request_indexing**, and run it. This makes one additional installation from the public GitHub repository with telemetry suppression flags disabled. GitHub Actions is still a CI environment, so skills.sh may disregard the event; neither a green workflow nor this input guarantees catalog listing. Leave the option unchecked for routine checks. Do not schedule indexing requests.

To contribute a new skill, follow [AGENTS.md](AGENTS.md): create `skills/<name>/SKILL.md` with matching `name` and a meaningful `description`, add any runtime-specific helpers and tests, and document prerequisites. Each skill is independently distributed as a plugin using its own `plugin.json` and `.claude-plugin/plugin.json`, plus an entry in both marketplace catalogs. Copilot marketplace versions must agree with the plugin manifests; Claude plugin versions live in `.claude-plugin/plugin.json`, not in its marketplace entry. The distribution checks discover skill directories automatically, but each new skill still needs appropriate behavioral and integration CI for its runtime. Keep operational instructions in SKILL.md and tutorials in `docs/` or `examples/`.

[GitHub Copilot CLI plugin documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing) · [Microsoft MarkItDown](https://github.com/microsoft/markitdown)
