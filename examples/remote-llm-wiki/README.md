# Remote LLM Wiki examples

These examples show **how an agent can use** the skill, rather than changing the skill's target repository.

- [Prompts](prompts.md): Init, Ingest, Query, Lint, ambiguity and collaboration.
- [Sample memory](sample-memory/): a fully synthetic, self-contained wiki showing sources, index, pages and log.
- [Guide](../../docs/remote-llm-wiki.md): prerequisites, limits, security and workflow behavior.

The consuming agent is responsible for resolving the target repository and branch from trusted context. If it cannot do so, it must ask the user. These examples never authorize a destination or define a default repository.
