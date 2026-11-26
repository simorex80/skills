"""Authenticated GitHub API integration suite on an ephemeral test-repository branch.

Run only with GH_TOKEN scoped to the dedicated disposable repository.
This file deliberately does not alter any default branch.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wiki.py"
HOST = "github.com"
TEST_REPO = "simorex80/remote-llm-wiki-test"


def gh(*arguments: str, payload: dict | None = None) -> str:
    command = ["gh", "api", "--hostname", HOST, *arguments]
    if payload is not None:
        command.extend(("--input", "-"))
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        capture_output=True, text=True, timeout=90, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"GitHub API call failed: {result.stderr[:400]}")
    return result.stdout.strip()


def wiki_call(repo: str, *arguments: str, stdin: str | None = None, ok: bool = True) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--host", HOST, "--repo", repo, *arguments],
        input=stdin, capture_output=True, text=True, timeout=180, check=False,
    )
    if ok and result.returncode:
        raise AssertionError(f"wiki {arguments[0]} failed: {result.stderr[:600]}")
    if not ok and result.returncode == 0:
        raise AssertionError(f"wiki {arguments[0]} unexpectedly succeeded")
    return result.stdout if ok and arguments[0] == "read" else (
        result.stdout.strip() if ok else result.stderr.strip())


def main() -> None:
    if os.environ.get("WIKI_TEST_REPO", "") != TEST_REPO:
        raise RuntimeError("Refusing to write outside the dedicated test repository.")
    repo = TEST_REPO
    run_id = secrets.token_hex(8)
    branch = f"ci-wiki-{run_id}"
    base_sha = json.loads(gh(f"repos/{repo}/git/ref/heads/main"))["object"]["sha"]
    # Seed without inheriting the default branch's trial-era memory.
    tree = json.loads(gh("--method", "POST", f"repos/{repo}/git/trees",
                         payload={"tree": [{"path": "README.md", "type": "blob",
                                            "mode": "100644", "content": "Disposable wiki test\n"}]}))["sha"]
    seed = json.loads(gh("--method", "POST", f"repos/{repo}/git/commits",
                         payload={"message": "Seed disposable wiki test",
                                  "tree": tree, "parents": [base_sha]}))["sha"]
    created = False
    try:
        gh("--method", "POST", f"repos/{repo}/git/refs", "-f", f"ref=refs/heads/{branch}",
           "-f", f"sha={seed}")
        created = True

        fresh = json.loads(wiki_call(repo, "init", branch))
        if fresh["status"] != "initialized":
            raise AssertionError(f"Unexpected fresh init outcome: {fresh}")
        initialized = json.loads(wiki_call(repo, "init", branch))
        if initialized["status"] != "already_initialized" or initialized["sha"] != fresh["oid"]:
            raise AssertionError(f"Unexpected init outcome: {initialized}")

        original = wiki_call(repo, "snapshot", branch)
        listing = json.loads(wiki_call(repo, "list", original))
        for required in ("AGENTS.md", "memory.yaml", "wiki/index.md", "wiki/log.md"):
            if required not in listing:
                raise AssertionError(f"Missing test fixture: {required}")
        index = wiki_call(repo, "read", original, "wiki/index.md")
        log = wiki_call(repo, "read", original, "wiki/log.md")
        plan = {
            "upsert": {
                f"raw/{branch}.md": "# Synthetic test source\n\nNo production data.\n",
                f"wiki/sources/{branch}.md": f"# Test\n\n[Source](../../raw/{branch}.md)\n",
                "wiki/index.md": index.replace("## Sources\n", f"## Sources\n\n- [CI test](sources/{branch}.md)\n"),
                "wiki/log.md": log + f"\n## [2026-11-24] ingest | Synthetic run {run_id}\n",
            }
        }
        outcome = json.loads(wiki_call(
            repo, "commit", branch, original, "--message", "Synthetic wiki CI validation",
            "--plan", "-", stdin=json.dumps(plan),
        ))
        new_sha = outcome["oid"]
        if new_sha == original:
            raise AssertionError("Commit did not advance HEAD.")
        captured = wiki_call(repo, "read", new_sha, f"raw/{branch}.md")
        if "Synthetic test source" not in captured:
            raise AssertionError("Missing immutable captured source.")
        lint = json.loads(wiki_call(repo, "lint", new_sha))
        if lint["issues"]:
            raise AssertionError(f"Lint found issues: {lint['issues']}")

        # The old expected HEAD must be rejected, not automatically retried.
        error = wiki_call(
            repo, "commit", branch, original, "--message", "Stale write",
            "--plan", "-", stdin=json.dumps(plan),
            ok=False,
        )
        if "advanced" not in error.lower():
            raise AssertionError(f"Stale commit failed for unexpected reason: {error}")

        # Original captures are append-only through the skill.
        error = wiki_call(
            repo, "commit", branch, new_sha, "--message", "Illegal overwrite",
            "--plan", "-", stdin=json.dumps({"upsert": {f"raw/{branch}.md": "overwritten"}}),
            ok=False,
        )
        if "immutable" not in error.lower():
            raise AssertionError(f"Raw overwrite failed for unexpected reason: {error}")
        print("Authenticated wiki snapshot/ingest/query/lint/conflict checks passed.")
    finally:
        if created:
            gh("--method", "DELETE", f"repos/{repo}/git/refs/heads/{branch}")


if __name__ == "__main__":
    main()
