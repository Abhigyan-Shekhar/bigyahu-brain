"""Read-only incremental GitHub acquisition, bounded pagination and retryable publication."""

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .snapshots import ingest_snapshots


class GitHub:
    """Use gh's configured credentials, never place tokens in argv or artifacts."""

    def get(self, path, params=None):
        if not path.startswith("repos/") or ".." in path or "?" in path:
            raise ValueError("Unexpected GitHub API route")
        endpoint = path + ("?" + urlencode(params) if params else "")
        result = subprocess.run(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                endpoint,
                "-H",
                "Accept: application/vnd.github+json",
                "-H",
                "X-GitHub-Api-Version: 2022-11-28",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(
                "GitHub request failed; check authentication/rate limits and retry; cursor unchanged"
            )
        if len(result.stdout) > 10_000_000:
            raise ValueError("GitHub response exceeds bounds")
        return json.loads(result.stdout)

    def pages(self, path, params=None, max_pages=100):
        result = []
        for page in range(1, max_pages + 1):
            rows = self.get(path, {**(params or {}), "per_page": 100, "page": page})
            if not isinstance(rows, list):
                raise TypeError("Expected a GitHub list")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise ValueError("GitHub pagination bound reached; no cursor advanced")


def sync_github(store, output, api=None, reconcile=False):
    """Fetch all input before graph mutation. Rerun after failure with unchanged cursor.

    Poll incremental issues and separately updated PRs. Full reconciliation is
    required periodically for edits/deletions not reflected in parent timestamps.
    """
    cfg = store.cfg
    slug = urlsplit(cfg.repo_url).path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise ValueError("Configured GitHub owner/repository required")
    state = store.revision(code_only=True)
    if not state["sha"] or state["syncing"]:
        raise ValueError("Complete code sync before GitHub sync")
    rows = store.query(
        "MATCH (p:Project {uid:$repo}) RETURN p.github_cursor AS cursor,p.github_repository_id AS repository_id",
        {"repo": cfg.repo_id},
    )
    cursor = rows[0]["cursor"] if rows else None
    started = datetime.now(UTC)
    since = (
        (datetime.fromisoformat(cursor) - timedelta(minutes=5)).isoformat()
        if cursor and not reconcile
        else None
    )
    api = api or GitHub()
    base = "repos/" + slug
    repository = api.get(base)
    if repository.get("full_name", "").casefold() != slug.casefold():
        raise ValueError("Repository identity changed; review configured URL")
    if rows and rows[0].get("repository_id") not in {None, repository["id"]}:
        raise ValueError("GitHub repository ID changed; reset scope only after operator review")
    private = repository.get("private", True)
    if private and not cfg.tenant_id:
        raise ValueError("Private GitHub acquisition requires a tenant namespace")
    params = {"state": "all", "sort": "updated", "direction": "asc"}
    if since:
        params["since"] = since
    work = {item["number"]: item for item in api.pages(base + "/issues", params)}
    # A review may update PR metadata independently of issue polling. Pulls has no
    # since parameter, so bound a descending scan and stop only beyond the overlap.
    for page in range(1, 101):
        pulls = api.get(
            base + "/pulls",
            {"state": "all", "sort": "updated", "direction": "desc", "per_page": 100, "page": page},
        )
        eligible = [p for p in pulls if not since or p["updated_at"] >= since]
        for pull in eligible:
            work.setdefault(pull["number"], {**pull, "pull_request": {}})
        if len(pulls) < 100 or (since and len(eligible) < len(pulls)):
            break
    else:
        raise ValueError("PR pagination bound reached; cursor unchanged")
    if len(work) > 2000:
        raise ValueError("Incremental batch too large; partition repositories")
    records = []
    for number, item in sorted(work.items()):
        record = {k: item.get(k) for k in (
            "number", "title", "body", "html_url", "state", "user",
            "created_at", "updated_at", "closed_at", "milestone",
        )}
        record["comments_snapshot"] = api.pages(base + f"/issues/{number}/comments")
        for comment in record["comments_snapshot"]:
            comment["id"] = "issue:" + str(comment["id"])
        if "pull_request" in item:
            pull = api.get(base + f"/pulls/{number}")
            record["pull_request"] = {"merged_at": pull.get("merged_at")}
            reviews = api.pages(base + f"/pulls/{number}/reviews")
            for review in reviews:
                review["id"] = "review:" + str(review["id"])
            inline = api.pages(base + f"/pulls/{number}/comments")
            for comment in inline:
                comment["id"] = "inline:" + str(comment["id"])
            record["reviews_snapshot"] = reviews
            record["comments_snapshot"].extend(inline)
            record["files_snapshot"] = api.pages(base + f"/pulls/{number}/files", max_pages=31)
            if len(record["files_snapshot"]) != pull.get("changed_files"):
                raise ValueError("GitHub changed-file coverage incomplete; cursor unchanged")
        records.append(record)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    raw = (json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode()
    (output / "work.json").write_bytes(raw)
    manifest = {
        "repo_id": cfg.repo_id,
        "repo_url": cfg.repo_url,
        "sha": state["sha"],
        "visibility": "private" if private else "public",
        "collected_at": started.isoformat(),
        "work_sha256": hashlib.sha256(raw).hexdigest(),
        "immutable_sources": True,
        "repository": {"id": repository["id"], "full_name": repository["full_name"]},
        "since": since,
        "reconcile": reconcile,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    store.query("MATCH (p:Project {uid:$repo}) SET p.github_syncing=true", {"repo": cfg.repo_id})
    result = ingest_snapshots(store, output, authorized_private=private)
    store.query(
        "MATCH (p:Project {uid:$repo}) SET p.github_syncing=false,p.github_cursor=$cursor, "
        "p.github_repository_id=$id",
        {"repo": cfg.repo_id, "cursor": started.isoformat(), "id": repository["id"]},
    )
    return {
        **result,
        "cursor": started.isoformat(),
        "reconcile": reconcile,
        "warnings": ["periodic_full_reconciliation_required_for_child_deletions"],
    }
