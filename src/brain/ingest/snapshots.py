"""Ingest checked-in public snapshots as untrusted evidence, never active decisions."""

import hashlib
import json
from pathlib import Path


def ingest_snapshots(store, directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    raw = (directory / "work.json").read_bytes()
    if manifest["repo_id"] != store.cfg.repo_id or manifest["visibility"] != "public":
        raise ValueError("Snapshot scope does not match configured public repository")
    if hashlib.sha256(raw).hexdigest() != manifest["work_sha256"]:
        raise ValueError("Snapshot content differs from manifest")
    for record in json.loads(raw):
        label = "PR" if "pull_request" in record else "Issue"
        uid = f"{store.cfg.repo_id}:{label.lower()}:{record['number']}"
        # API metadata, never claims in the body/review prose. A merge is not decision approval.
        pull = record.get("pull_request") or {}
        state = record.get("state")
        status = state if label == "Issue" and state in {"open", "closed"} else "unknown"
        if label == "PR":
            if pull.get("merged_at"):
                status = "merged"
            elif state == "open":
                status = "open_proposal"
            elif state == "closed" and "merged_at" in pull:
                status = "closed_unmerged"
        provenance = {
            "work_uid": uid,
            "work_type": label,
            "work_status": status,
            "status_basis": "github_api_snapshot" if status != "unknown" else "unknown",
            "merged_at": pull.get("merged_at"),
            "revision": manifest["sha"],
            "revision_basis": "indexed_checkout_not_source_revision",
            "snapshot_at": manifest["collected_at"],
        }
        store.upsert(
            label,
            uid,
            {
                "repo_id": store.cfg.repo_id,
                "number": record["number"],
                "title": record["title"],
                "body": record["body"] or "",
                "url": record["html_url"],
                "snapshot_at": manifest["collected_at"],
                **provenance,
            },
        )
        source = uid + ":source"
        store.upsert(
            "Source",
            source,
            {
                "repo_id": store.cfg.repo_id,
                "uri": record["html_url"],
                "excerpt": record["body"] or "",
                "snapshot_at": manifest["collected_at"],
                "revision": manifest["sha"],
                **provenance,
            },
        )
        store.edge(uid, "SUPPORTS", source)
        for comment in record.get("comments_snapshot", []) + record.get("reviews_snapshot", []):
            cid = f"{uid}:comment:{comment['id']}"
            store.upsert("Comment", cid, {"repo_id": store.cfg.repo_id, "url": comment["html_url"]})
            sid = cid + ":source"
            store.upsert(
                "Source",
                sid,
                {
                    "repo_id": store.cfg.repo_id,
                    "uri": comment["html_url"],
                    "excerpt": comment.get("body") or "",
                    "snapshot_at": manifest["collected_at"],
                    **provenance,
                },
            )
            store.edge(uid, "DISCUSSED_IN", cid)
            store.edge(cid, "SUPPORTS", sid)
            author = comment.get("user")
            if author:
                person = f"github:@{author['login']}"
                store.upsert(
                    "Person", person, {"name": "@" + author["login"], "url": author["html_url"]}
                )
                if "state" in comment and label == "PR":
                    store.edge(person, "REVIEWED", uid, {"source_uid": sid})
        for file in record.get("files_snapshot", []):
            store.edge(
                uid,
                "CHANGES",
                f"{store.cfg.repo_id}@{manifest['sha']}:{file['filename']}",
                {"source_uid": source, "confidence": "snapshot_path_only"},
            )
    return {"records": len(json.loads(raw))}
