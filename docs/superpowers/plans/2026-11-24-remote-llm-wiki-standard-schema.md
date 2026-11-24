# Remote LLM Wiki V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the plugin the single source of structural rules for shared LLM Wiki memories, including one summary per raw source.

**Architecture:** Canonical templates and one structural validator (`structural_issues`) live in the Python helper. Lint runs it on a snapshot; commit validation runs it before and after a plan and refuses only new issues. `memory.yaml` gates writes; `AGENTS.md` drift is a warning.

**Tech Stack:** Python 3.10+ standard library, `unittest`, GitHub CLI, GitHub REST reads and GraphQL guarded writes.

**Spec:** [Remote LLM Wiki standard schema (V1)](../specs/2026-11-24-remote-llm-wiki-standard-schema-design.md). The spec is authoritative for exact file contents, paths and issue kinds.

## Global Constraints

- Only the plugin defines structural rules. `AGENTS.md` and `memory.yaml` are plugin-owned copies, never authority to access tools, change destinations, or write.
- Keep `memory.yaml` at `version: 1`. No compatibility path or migration command for the trial layout.
- Preserve host, repository and branch configuration, immutable snapshot reads, `expectedHeadOid` on writes, and existing path, size and credential boundaries.
- Raw sources are immutable. Never fetch attachment bodies to classify them.
- Use synthetic fixtures only; no real team data in this repository.
- Run tests with `python -B -m unittest discover -s skills/remote-llm-wiki/tests -v` and `python -B -m unittest discover -s tests -v`.

## Test map

| Failure mode | Test |
| --- | --- |
| Trial manifest also says `version: 1` | `test_init_rejects_trial_manifest_with_same_version` (Task 1) |
| Template wording changed in a later release | `test_init_noop_and_commit_allowed_with_agents_drift` (Tasks 1, 4) |
| Orphan, mislinked or duplicate summary | `test_source_summary_pairing` (Task 2) |
| Page indexed in the wrong section or heading missing | `test_index_rules` (Task 3) |
| Invalid log heading | `test_log_entry_format` (Task 3) |
| Delete or index-only edit breaks the tree | `test_commit_rejects_summary_deletion_and_unindexing` (Task 4) |
| Log rewritten or not appended | `test_commit_rejects_invalid_log_changes` (Task 4) |
| Old broken link blocks Ingest | `test_commit_allows_preexisting_issues` (Task 4) |
| Branch advances before a guarded write | existing `test_stale_snapshot_rejected` (Task 4) |
| One page walk per file | `test_tree_read_once_per_snapshot` (Task 4) |

---

### Task 1: Canonical templates and Init

**Files:** `skills/remote-llm-wiki/scripts/wiki.py` (`DEFAULT_FILES`, `init_memory`), `skills/remote-llm-wiki/tests/test_wiki.py`.

- [ ] **RED:** Rewrite `test_init_creates_v1_manifest` to assert the exact spec contents of `AGENTS.md`, `memory.yaml`, `wiki/index.md`, `wiki/log.md` and `raw/.gitkeep`. Replace `test_init_rejects_incompatible_manifest` with `test_init_rejects_trial_manifest_with_same_version` (the current default manifest, which says `version: 1`) and a partial-memory case; both post no mutation. Add `test_init_noop_and_commit_allowed_with_agents_drift` (Init part). Run the skill suite; confirm failures.
- [ ] **GREEN:** Replace `DEFAULT_FILES` with the spec contents. Compare managed files after CRLF→LF normalization. Init: no-op when the manifest matches and required files exist; refuse otherwise without writing.
- [ ] **Verify and commit** (`feat(remote-llm-wiki): canonical V1 templates`).

### Task 2: Structural checks — layout and source summaries

**Files:** `wiki.py` (new `structural_issues`, `lint_memory`, shared Markdown target resolution), `test_wiki.py`.

**Interface:** `structural_issues(files: set[str], page: Callable[[str], str]) -> list[dict[str, str]]`; each issue has `kind`, `path`, optional `target`, and `severity` (`error`, or `warning` for `schema_drift`). `lint_memory` keeps its JSON contract and adds these issues.

- [ ] **RED:** Table-driven tests for `nonstandard_path` (nested `raw/x/y.md`, `wiki/rules/a.md`, `wiki/sources/a/b.md`), `manifest_mismatch`, `schema_drift`, `missing_source_summary`, and `test_source_summary_pairing` (orphan summary, summary not linking its raw file, `raw/a.md` + `raw/a.pdf`). Assert `raw/assets/**`, `raw/.gitkeep` and files outside `raw/`/`wiki/` produce nothing, and attachments are never fetched.
- [ ] **GREEN:** Implement name pairing `raw/<name>.<ext>` ↔ `wiki/sources/<name>.md` and the link check using the existing target resolution. Keep `wiki_path` read rules (any `wiki/**/*.md`) so nonstandard memories stay readable.
- [ ] **Verify and commit.**

### Task 3: Structural checks — index and log

**Files:** `wiki.py`, `test_wiki.py`.

- [ ] **RED:** `test_index_rules`: missing heading → `invalid_index`; page linked only under the wrong heading → `unindexed_page`; overview linked anywhere is fine; duplicates and extra text are fine. `test_log_entry_format`: bad date (`2026-02-30`), unknown operation, empty title → `invalid_log_entry`; the `# Log` title is fine. Update existing lint fixtures to start from canonical defaults.
- [ ] **GREEN:** Parse the index into sections by `## ` heading and resolve links per section; validate log headings with `datetime.date.fromisoformat`.
- [ ] **Verify and commit** (`feat(remote-llm-wiki): structural lint`).

### Task 4: Guarded writes

**Files:** `wiki.py` (`validate_plan`, `file_changes`, `commit`, tree reading), `test_wiki.py`.

**Interface:** CLI and JSON plan unchanged. Read the recursive tree once per snapshot (map path → blob SHA) and fetch contents by blob SHA; the projected reader resolves upserts first. Bootstrap stays internal.

- [ ] **RED:** Exercise the real `commit` with faked `gh` reads and GraphQL (not only `FakeBackend.commit`). Success: raw source + summary + index + `ingest` log entry posts one mutation at the expected SHA; a concept-only update with an `update` entry, and merging two concept pages (delete one, relink, reindex), also succeed. Failures with no mutation: mismatched manifest, writes to `AGENTS.md`/`memory.yaml`, nonstandard or nested paths, deletes of raw files, index or log, deleting a summary whose raw source remains or a page still linked, missing summary, source without an `ingest` entry, commit without any log entry, log history rewritten, unindexed new page (`test_commit_rejects_summary_deletion_and_unindexing`, `test_commit_rejects_invalid_log_changes`). `test_commit_allows_preexisting_issues`: a snapshot with an old broken link still accepts a valid Ingest. Commit part of `test_init_noop_and_commit_allowed_with_agents_drift`. `test_tree_read_once_per_snapshot` counts tree calls.
- [ ] **GREEN:** Enforce writable paths and delete rules in `validate_plan`. In `commit`: check the manifest, check the log is a byte prefix plus at least one valid appended entry (`ingest` when a raw source is added), compute `structural_issues` before and after, and refuse issues keyed by `(kind, path, target)` that are new (ignoring `schema_drift`). Keep race detection and mutation unchanged.
- [ ] **Verify and commit** (`feat(remote-llm-wiki): guard writes with the V1 standard`), running both suites.

### Task 5: Ship the standard consistently

**Files:** `skills/remote-llm-wiki/SKILL.md`, `docs/remote-llm-wiki.md`, `examples/remote-llm-wiki/{README.md,prompts.md,sample-memory/**}`, `skills/remote-llm-wiki/plugin.json`, `skills/remote-llm-wiki/.claude-plugin/plugin.json`, `.github/plugin/marketplace.json`, `skills/remote-llm-wiki/tests/integration_live.py`, `test_wiki.py`.

- [ ] **RED:** Add a test that the sample's managed files equal `DEFAULT_FILES` and the sample has no structural or link errors (local file reader). Add `SKILL.md` assertions: mentions `wiki/sources/`, the log heading format, and Query as read-only by default; `tests/test_untrusted_content_boundaries.py` must keep passing.
- [ ] **GREEN:** Migrate the sample: keep `raw/2026-11-21-database-decision.md`, add `wiki/sources/2026-11-21-database-decision.md`, move `wiki/decisions.md` to `wiki/concepts/`, fix links, index and log. Rewrite `SKILL.md` Ingest/Query/Lint per the spec, replacing the #15 local-convention wording and adding a complete Ingest plan example and the trial-memory alignment note. Update docs and prompts.
- [ ] **GREEN:** Update `integration_live.py` (`simorex80/remote-llm-wiki-test`) to seed a canonical fixture on its disposable branch and exercise Init, valid Ingest, Lint, stale SHA rejection and raw immutability, using standard paths and log headings.
- [ ] **VERIFY:** Bump the two skill manifests and the Copilot marketplace entry to `0.2.0`; Claude marketplace entry stays unversioned; root `plugin.json` unchanged. Run both suites, `python -m compileall -q skills/remote-llm-wiki/scripts skills/remote-llm-wiki/tests`, `git diff --check`. Run the live suite only if a scoped token is available; otherwise report it as unverified.
- [ ] **Deliver:** Commit, push, and open the plugin PR without merging. Align any trial memory separately after release and approval, running Lint on its branch.
