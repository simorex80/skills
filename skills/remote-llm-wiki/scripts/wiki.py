"""Read and commit a remote Markdown wiki through authenticated GitHub CLI."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from urllib.parse import quote


COMMIT_QUERY = """
mutation CommitWiki($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit { oid url }
  }
}
"""


class WikiError(Exception):
    """A command could not complete safely."""


def parse_host(value: str) -> str:
    host = value.lower()
    labels = host.split(".")
    if len(host) > 253 or len(labels) < 2 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise argparse.ArgumentTypeError("Use a GitHub hostname without a scheme or port.")
    return host


def parse_repo(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value):
        raise argparse.ArgumentTypeError("Use OWNER/REPO.")
    if value.split("/")[1] in {".", ".."}:
        raise argparse.ArgumentTypeError("Use a valid repository name.")
    return value


def parse_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise argparse.ArgumentTypeError("Use a full 40-character commit SHA.")
    return value.lower()


def wiki_path(value: str, *, writable: bool = False) -> str:
    parts = value.split("/")
    if (
        any(part in {"", ".", ".."} for part in parts)
        or "\\" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise WikiError("Use a canonical repository-relative path.")
    if value == "log.md" or (value.startswith("wiki/") and value.lower().endswith(".md")):
        return value
    if not writable and value.startswith("raw/"):
        return value
    raise WikiError("Path is outside the permitted wiki files.")


def gh_api(host: str, args: list[str], payload: dict | None = None) -> str:
    command = ["gh", "api", "--hostname", host, *args]
    try:
        result = subprocess.run(
            command,
            input=None if payload is None else json.dumps(payload).encode("utf-8"),
            stdin=subprocess.DEVNULL if payload is None else None,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise WikiError("Install GitHub CLI (gh) in this environment.") from exc
    except subprocess.TimeoutExpired as exc:
        raise WikiError("GitHub request timed out. Verify the branch before retrying a write.") from exc
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
        raise WikiError(diagnostic or f"gh exited with status {result.returncode}.")
    return result.stdout.decode("utf-8")


def snapshot(host: str, repo: str, branch: str) -> str:
    if not branch or branch.startswith("refs/") or branch == "HEAD":
        raise WikiError("Use the existing branch name without the refs/heads/ prefix.")
    endpoint = f"repos/{repo}/git/ref/heads/{quote(branch, safe='/')}"
    return parse_sha(gh_api(host, [endpoint, "--jq", ".object.sha"]).strip())


def read_file(host: str, repo: str, sha: str, path: str) -> str:
    parts = wiki_path(path).split("/")
    endpoint = f"repos/{repo}/git"
    commit_object = json.loads(gh_api(host, [f"{endpoint}/commits/{sha}"]))
    object_sha = parse_sha(commit_object["tree"]["sha"])
    for index, part in enumerate(parts):
        tree = json.loads(gh_api(host, [f"{endpoint}/trees/{object_sha}"]))
        entry = next((item for item in tree["tree"] if item["path"] == part), None)
        if entry is None:
            if tree.get("truncated"):
                raise WikiError(f"Cannot verify {path!r} because GitHub truncated the tree.")
            raise WikiError(f"File not found: {path!r}.")
        if index == len(parts) - 1:
            if entry["type"] != "blob" or entry["mode"] not in {"100644", "100755"}:
                raise WikiError(f"Not a regular file: {path!r}.")
        elif entry["type"] != "tree" or entry["mode"] != "040000":
            raise WikiError(f"Path does not traverse only directories: {path!r}.")
        object_sha = parse_sha(entry["sha"])
    return gh_api(host, [f"{endpoint}/blobs/{object_sha}", "-H", "Accept: application/vnd.github.raw+json"])


def unique_plan_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise WikiError(f"Duplicate key in JSON plan: {key!r}.")
        result[key] = value
    return result


def file_changes(plan: object) -> dict[str, list[dict[str, str]]]:
    if not isinstance(plan, dict) or set(plan) - {"upsert", "delete"}:
        raise WikiError("Provide a JSON object containing upsert and/or delete.")
    upsert = plan.get("upsert", {})
    delete = plan.get("delete", [])
    if not isinstance(upsert, dict) or not isinstance(delete, list):
        raise WikiError("Use an object for upsert and an array for delete.")
    if not upsert and not delete:
        raise WikiError("Provide at least one file change.")
    if not all(isinstance(path, str) for path in delete):
        raise WikiError("Every deletion must name a file.")
    if len(set(delete)) != len(delete) or set(delete).intersection(upsert):
        raise WikiError("Provide each changed path once.")
    if {"wiki/index.md", "wiki/log.md", "log.md"}.intersection(delete):
        raise WikiError("The wiki index and log cannot be deleted.")

    additions = []
    for path, content in upsert.items():
        if not isinstance(content, str):
            raise WikiError("Each upsert value must contain the complete Markdown text.")
        additions.append({
            "path": wiki_path(path, writable=True),
            "contents": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        })
    changes = {}
    if additions:
        changes["additions"] = additions
    if delete:
        changes["deletions"] = [{"path": wiki_path(path, writable=True)} for path in delete]
    return changes


def commit(host: str, repo: str, branch: str, sha: str, message: str, plan: object) -> dict:
    if not message.strip() or "\n" in message or "\r" in message:
        raise WikiError("Provide a single-line commit message.")
    changes = file_changes(plan)
    if snapshot(host, repo, branch) != sha:
        raise WikiError("Branch advanced. Read a new snapshot and recompute the changes.")
    payload = {
        "query": COMMIT_QUERY,
        "variables": {
            "input": {
                "branch": {"repositoryNameWithOwner": repo, "refName": f"refs/heads/{branch}"},
                "expectedHeadOid": sha,
                "message": {"headline": message},
                "fileChanges": changes,
            },
        },
    }
    response = json.loads(gh_api(host, ["graphql", "--input", "-"], payload))
    if response.get("errors"):
        raise WikiError("GitHub rejected the commit. Check the branch head and permissions.")
    result = response.get("data", {}).get("createCommitOnBranch", {}).get("commit")
    if not result or not result.get("oid") or not result.get("url"):
        raise WikiError("Commit outcome is unconfirmed. Check the branch before retrying.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, type=parse_host)
    parser.add_argument("--repo", required=True, type=parse_repo)
    commands = parser.add_subparsers(dest="command", required=True)
    get_snapshot = commands.add_parser("snapshot")
    get_snapshot.add_argument("branch")
    read = commands.add_parser("read")
    read.add_argument("sha", type=parse_sha)
    read.add_argument("path")
    write = commands.add_parser("commit")
    write.add_argument("branch")
    write.add_argument("sha", type=parse_sha)
    write.add_argument("--message", required=True)
    write.add_argument("--plan", required=True, help="UTF-8 JSON file, or - for stdin.")
    args = parser.parse_args()

    try:
        if args.command == "snapshot":
            print(snapshot(args.host, args.repo, args.branch))
        elif args.command == "read":
            content = read_file(args.host, args.repo, args.sha, args.path)
            sys.stdout.buffer.write(content.encode("utf-8"))
        else:
            if args.plan == "-":
                plan = json.load(sys.stdin.buffer, object_pairs_hook=unique_plan_keys)
            else:
                with open(args.plan, encoding="utf-8") as plan_file:
                    plan = json.load(plan_file, object_pairs_hook=unique_plan_keys)
            print(json.dumps(commit(args.host, args.repo, args.branch, args.sha, args.message, plan)))
    except (WikiError, OSError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"remote-llm-wiki: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
