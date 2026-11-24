# Remote LLM Wiki — prompt examples

The agent must know the **dedicated memory repository and branch** from trusted user input or approved project context. Otherwise, it should ask for them before any remote access or write. The prompts below intentionally do not bake the repository URL into the skill.

## Initialize (Init)

> Use remote-llm-wiki to initialize the shared memory for this project. Use the memory repository and branch configured for this project; if that destination is not available in trusted context, ask me for it.

Expected: create the default layout once in a repository whose branch already has an initial commit; refuse to overwrite a partial or incompatible wiki.

## Remember a decision (Ingest)

> Remember that we chose PostgreSQL as the primary database. This supersedes our earlier MongoDB proposal. Record the date and provenance, update the existing architecture page if appropriate, and keep the previous decision traceable.

Expected: new immutable source capture, a matching `wiki/sources/` page with a link to the original, updated curated pages and index, and an appended `ingest` log entry. Do not invent reasons the user did not supply.

## Consult the memory (Query)

> Using the project's shared memory, what is our current database decision? Cite the supporting source and point out anything the memory does not explain. Do not change files.

Expected: evidence-backed answer from one commit snapshot, with no writes.

## Ingest meeting notes

> Incorporate the decisions in these meeting notes into our project's shared memory. Separate confirmed decisions from open questions; cite the notes. Avoid duplicate pages.

Expected: faithful source capture and contextualized wiki changes. The agent should ask for the notes if not provided.

## Check quality (Lint)

> Audit the shared memory for broken links, duplicate pages and contradictory decisions. Report the affected paths and evidence. Do not apply changes until I approve the proposed fixes.

Expected: structural lint followed by agent reasoning; no automatic resolution of ambiguous claims.

## Handle an unknown destination

> Summarize the project's shared memory.

If the agent has no trusted project-to-memory mapping, it should ask for the GitHub host, repository and branch rather than guessing or reading arbitrary repositories.

## Collaborate safely

> Add today's deployment decision to the shared wiki. If another collaborator changed the branch since your read, reload the relevant pages and recompute your update. Never force-push.

Expected: snapshot-based optimistic concurrency; no stale overwrite.

For the resulting file layout, see [the sample memory](sample-memory/).
