"""Explicitly partial public GitHub onboarding; selected items are indivisible."""

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .github_sync import GitHub
from .snapshots import ingest_snapshots


class BoundedGitHub(GitHub):
    """Budget requests, never shorten a child collection or reject an ordinary page."""

    def __init__(self):
        self.requests = 0

    def get(self, path, params=None):
        if self.requests >= 100:
            raise ValueError("GitHub onboarding request limit reached")
        self.requests += 1
        return super().get(path, params)


def selected_item(api, base, number):
    item = api.get(base + f"/issues/{number}")
    if item.get("number") != number:
        raise ValueError("Work identity mismatch")
    comments = api.pages(base + f"/issues/{number}/comments", max_pages=10)
    if len(comments) != item.get("comments"):
        raise ValueError("Issue comment coverage incomplete")
    record = {k: item.get(k) for k in (
        "number", "title", "body", "html_url", "state", "user",
        "created_at", "updated_at", "closed_at", "milestone",
    )}
    record["comments_snapshot"] = [{**c, "id": "issue:" + str(c["id"])} for c in comments]
    pull = None
    if "pull_request" in item:
        pull = api.get(base + f"/pulls/{number}")
        record["pull_request"] = {"merged_at": pull.get("merged_at")}
        reviews = api.pages(base + f"/pulls/{number}/reviews", max_pages=10)
        inline = api.pages(base + f"/pulls/{number}/comments", max_pages=10)
        files = api.pages(base + f"/pulls/{number}/files", max_pages=31)
        if len(files) != pull.get("changed_files") or len(inline) != pull.get("review_comments"):
            raise ValueError("Pull request child coverage incomplete")
        record["reviews_snapshot"] = [{**r, "id": "review:" + str(r["id"])} for r in reviews]
        record["comments_snapshot"].extend({**c, "id": "inline:" + str(c["id"])} for c in inline)
        record["files_snapshot"] = files
    # A changed parent invalidates this item, not previously completed neighbors.
    after = api.get(base + f"/issues/{number}")
    if (
        not item.get("updated_at")
        or after.get("updated_at") != item["updated_at"]
        or after.get("comments") != item["comments"]
    ):
        raise ValueError("Work changed during acquisition")
    if pull is not None:
        after_pull = api.get(base + f"/pulls/{number}")
        if not pull.get("updated_at") or any(
            after_pull.get(k) != pull.get(k)
            for k in ("updated_at", "changed_files", "review_comments", "merged_at", "head")
        ):
            raise ValueError("Pull request changed during acquisition")
    return record


def sync_initial(store, output, api=None):
    """Import up to twenty recently updated issue/PR items without advancing the full-sync cursor."""
    cfg = store.cfg
    slug = urlsplit(cfg.repo_url).path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise ValueError("Configured public GitHub repository required")
    state = store.revision(code_only=True)
    if not state["sha"] or state["syncing"]:
        raise ValueError("Complete code sync before initial GitHub acquisition")
    api, base = api or BoundedGitHub(), "repos/" + slug
    repository = api.get(base)
    if (
        repository.get("private", True)
        or repository.get("full_name", "").casefold() != slug.casefold()
    ):
        raise ValueError("Public repository identity changed")
    started = datetime.now(UTC).isoformat()
    candidates = api.get(
        base + "/issues",
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": 21, "page": 1},
    )
    if not isinstance(candidates, list) or len(candidates) > 21:
        raise ValueError("Unexpected initial GitHub selection response")
    numbers = [r["number"] for r in candidates[:20]]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Duplicate work items in selection")
    records, skipped = [], []
    for number in numbers:
        try:
            records.append(selected_item(api, base, number))
        except (ValueError, KeyError, TypeError, RuntimeError, OSError, subprocess.SubprocessError):
            skipped.append(
                {"number": number, "reason": "item_not_complete_or_stable_within_budget"}
            )
    if numbers and not records:
        raise ValueError(
            "No complete selected GitHub work items acquired; retry or explicitly choose code/Git-only indexing"
        )
    coverage = {
        "mode": "bounded_initial_sample",
        "complete_repository_history": False,
        "selection": "most_recently_updated_issues_including_pull_requests",
        "work_limit": 20,
        "selected": len(numbers),
        "imported": len(records),
        "skipped": skipped,
        "observed_candidates": len(candidates),
        "more_candidates": len(candidates) > 20,
        "imported_children_complete": True,
        "collection_page_size": 100,
        "request_limit": 100,
        "requests_used": getattr(api, "requests", None),
        "collected_at": started,
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    raw = (json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode()
    (output / "work.json").write_bytes(raw)
    manifest = {
        "repo_id": cfg.repo_id,
        "repo_url": cfg.repo_url,
        "sha": state["sha"],
        "visibility": "public",
        "collected_at": started,
        "work_sha256": hashlib.sha256(raw).hexdigest(),
        "immutable_sources": True,
        "repository": {"id": repository["id"], "full_name": repository["full_name"]},
        "coverage": coverage,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    store.query("MATCH (p:Project {uid:$repo}) SET p.github_syncing=true", {"repo": cfg.repo_id})
    result = ingest_snapshots(store, output)
    store.query(
        "MATCH (p:Project {uid:$repo}) SET p.github_syncing=false,p.github_initial_coverage=$coverage,p.github_repository_id=$id",
        {
            "repo": cfg.repo_id,
            "coverage": json.dumps(coverage, sort_keys=True),
            "id": repository["id"],
        },
    )
    return {**result, "coverage": coverage}
