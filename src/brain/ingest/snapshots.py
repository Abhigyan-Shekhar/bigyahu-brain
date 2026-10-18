"""Ingest checked-in public snapshots as untrusted evidence, never active decisions."""

import hashlib
import json
from pathlib import Path

from .identity import identity_uid
from .references import issue_mentions


def read_snapshot(directory):
    """Verify the canonical UTF-8/LF snapshot; tolerate Git CRLF checkout conversion only."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    raw = (directory / "work.json").read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(raw).hexdigest() != manifest["work_sha256"]:
        raise ValueError("Snapshot content differs from manifest")
    return manifest, json.loads(raw)


def ingest_snapshots(store, directory, authorized_private=False):
    manifest, records = read_snapshot(directory)
    if manifest["repo_id"] != store.cfg.repo_id or (
        manifest["visibility"] != "public"
        and not (authorized_private and store.cfg.tenant_id and manifest["visibility"] == "private")
    ):
        raise ValueError("Snapshot scope does not match configured public repository")
    references = []
    source_urls = {}

    def source_id(uid, text, uri):
        # Acquisition time and checkout/status metadata do not identify content.
        content = json.dumps({"text": text or "", "uri": uri}, sort_keys=True)
        suffix = (
            ":" + hashlib.sha256(content.encode()).hexdigest()
            if manifest.get("immutable_sources")
            else ""
        )
        return uid + ":source" + suffix

    for record in records:
        label = "PR" if "pull_request" in record else "Issue"
        uid = f"{store.cfg.repo_id}:{label.lower()}:{record['number']}"
        if manifest.get("immutable_sources"):
            # Reconcile this parent's authoritative child lists. Old immutable
            # Sources remain if a reviewed Decision cites them, but not as current work.
            # Comments are current projections, not historical evidence. Detaching
            # them preserves Source nodes and independent Decision citations.
            store.query(
                "MATCH (c:Comment {repo_id:$repo}) "
                "WHERE c.uid STARTS WITH $prefix DETACH DELETE c",
                {"prefix": uid + ":comment:", "repo": store.cfg.repo_id},
            )
            store.query(
                "MATCH (w {uid:$uid, repo_id:$repo})-[r:SUPPORTS|DISCUSSED_IN|CHANGES]->() DELETE r",
                {"uid": uid, "repo": store.cfg.repo_id},
            )
            store.query(
                "MATCH (:Person {repo_id:$repo})-[r:REVIEWED]->(w:PR {uid:$uid}) DELETE r",
                {"uid": uid, "repo": store.cfg.repo_id},
            )
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
        # Event time is distinct from collection time. Updated_at does not identify
        # an editor; GitHub's issue API supplies only the original author here.
        activity = {
            "author": (record.get("user") or {}).get("login"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "closed_at": record.get("closed_at"),
            "due_at": (record.get("milestone") or {}).get("due_on"),
            "deadline_basis": "github_milestone"
            if (record.get("milestone") or {}).get("due_on") else None,
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
                **activity,
            },
        )
        source = source_id(uid, record["body"], record["html_url"])
        source_urls[source] = record["html_url"]
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
                **activity,
            },
        )
        store.edge(uid, "SUPPORTS", source)
        for comment in record.get("comments_snapshot", []) + record.get("reviews_snapshot", []):
            cid = f"{uid}:comment:{comment['id']}"
            comment_activity = {
                "author": (comment.get("user") or {}).get("login"),
                "created_at": comment.get("created_at") or comment.get("submitted_at"),
                "updated_at": comment.get("updated_at"),
            }
            store.upsert("Comment", cid, {
                "repo_id": store.cfg.repo_id, "url": comment["html_url"], **comment_activity,
            })
            sid = source_id(cid, comment.get("body"), comment["html_url"])
            source_urls[sid] = comment["html_url"]
            store.upsert(
                "Source",
                sid,
                {
                    "repo_id": store.cfg.repo_id,
                    "uri": comment["html_url"],
                    "excerpt": comment.get("body") or "",
                    "snapshot_at": manifest["collected_at"],
                    **provenance,
                    **comment_activity,
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
                {
                    "source_uid": source,
                    "confidence": "snapshot_path_only",
                    "basis": "historical_file_association",
                    "snapshot_at": manifest["collected_at"],
                    "revision": manifest["sha"],
                    "revision_basis": "indexed_checkout_not_source_revision",
                },
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
                "relationship_type": "REFERENCES",
                "snapshot_at": manifest["collected_at"],
                "provenance": "github_api_snapshot_text",
                "source_url": source_urls[sources[0]],
            },
        )
    return {
        "records": len(records),
        "references": len(linked),
        "missing_issue_references": sorted(missing)[:100],
    }
