"""Ingest checked-in public snapshots as untrusted evidence, never active decisions."""

import hashlib
import json
from pathlib import Path

from .identity import identity_uid
from .references import issue_mentions


def ingest_snapshots(store, directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    raw = (directory / "work.json").read_bytes()
    if manifest["repo_id"] != store.cfg.repo_id or manifest["visibility"] != "public":
        raise ValueError("Snapshot scope does not match configured public repository")
    if hashlib.sha256(raw).hexdigest() != manifest["work_sha256"]:
        raise ValueError("Snapshot content differs from manifest")
    records = json.loads(raw)
    references = []
    for record in records:
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
        if label == "PR":
            references.extend(
                (uid, number, source)
                for number in issue_mentions(record["body"] or "", manifest["repo_url"])
            )
            store.query(
                "MATCH (p:Person)-[r:REVIEWED]->(w:PR {uid:$uid, repo_id:$repo}) "
                "WHERE p.repo_id IS NULL DELETE r",
                {"uid": uid, "repo": store.cfg.repo_id},
            )
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
            if label == "PR":
                references.extend(
                    (uid, number, sid)
                    for number in issue_mentions(comment.get("body") or "", manifest["repo_url"])
                )
            author = comment.get("user")
            if author:
                identity = f"github:@{author['login']}"
                person = identity_uid(store.cfg.repo_id, identity)
                store.upsert(
                    "Person",
                    person,
                    {
                        "name": "@" + author["login"],
                        "url": author["html_url"],
                        "repo_id": store.cfg.repo_id,
                        "identity_uid": identity,
                        "identity_basis": "github_api_snapshot",
                    },
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
    # Second pass makes reference edges independent of snapshot record order.
    linked, missing = {}, set()
    for pr, number, source in references:
        issue = f"{store.cfg.repo_id}:issue:{number}"
        found = store.query(
            "MATCH (i:Issue {uid:$uid, repo_id:$repo}) RETURN i.uid AS uid",
            {"uid": issue, "repo": store.cfg.repo_id},
        )
        if not found:
            missing.add(issue)
            continue
        linked.setdefault((pr, issue), set()).add(source)
    for record in records:
        if "pull_request" in record:
            store.query(
                "MATCH (p:PR {uid:$uid, repo_id:$repo})-[r:REFERENCES]->"
                "(i:Issue {repo_id:$repo}) WHERE r.basis='untrusted_source_mention' DELETE r",
                {"uid": f"{store.cfg.repo_id}:pr:{record['number']}", "repo": store.cfg.repo_id},
            )
    for (pr, issue), sources in linked.items():
        sources = sorted(sources, key=lambda source: (source != pr + ":source", source))
        store.edge(
            pr,
            "REFERENCES",
            issue,
            {
                "source_uid": sources[0],
                "source_uids": sources[:20],
                "confidence": "explicit_text_reference",
                "basis": "untrusted_source_mention",
                "resolution_verified": False,
            },
        )
    return {
        "records": len(records),
        "references": len(linked),
        "missing_issue_references": sorted(missing)[:100],
    }
