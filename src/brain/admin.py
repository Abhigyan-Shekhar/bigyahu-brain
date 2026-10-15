"""Operator CLI only. Never imported by the MCP server or services."""

import getpass
import os
import sys
from datetime import UTC, datetime


def approve(store, decision_id):
    if not sys.stdin.isatty() or os.environ.get("BRAIN_OPERATOR_SESSION") != "1":
        raise ValueError("Approval requires an interactive, separate operator session")
    state = store.revision()
    if state["syncing"] or not state["sha"]:
        raise ValueError("A completed sync is required")
    rows = store.query(
        "MATCH (d:Decision {uid:$id, repo_id:$repo, scope:'org', status:'proposed'}) "
        "MATCH (d)-[:SUPPORTED_BY]->(src:Source) "
        "MATCH (d)-[:CONSTRAINS]->(s:Symbol {current:true}) "
        "RETURN d.text AS text, d.kind AS kind, d.requested_supersedes AS replacement, "
        "collect(DISTINCT src.uid) AS sources, collect(DISTINCT src.uri) AS uris, "
        "collect(DISTINCT s.uid) AS subjects",
        {"id": decision_id, "repo": store.cfg.repo_id},
    )
    if not rows or rows[0]["kind"] != "constraint":
        raise ValueError("Proposal requires evidence and current symbol scope")
    proposal = rows[0]
    print("UNTRUSTED PROPOSAL — review original sources independently:")
    print(repr(proposal))
    if (
        input(f"After inspecting source, scope, and text, type APPROVE {decision_id}: ")
        != f"APPROVE {decision_id}"
    ):
        raise ValueError("Approval cancelled")
    params = {
        "id": decision_id,
        "repo": store.cfg.repo_id,
        "sha": state["sha"],
        "text": proposal["text"],
        "sources": proposal["sources"],
        "subjects": proposal["subjects"],
        "old": proposal["replacement"] or "",
        "by": getpass.getuser(),
        "at": datetime.now(UTC).isoformat(),
    }
    # A single atomic query revalidates the reviewed text/evidence/subjects and sync marker.
    guard = (
        "MATCH (p:Project {uid:$repo, syncing:false, last_completed_sync_sha:$sha}) "
        "MATCH (d:Decision {uid:$id, repo_id:$repo, scope:'org', status:'proposed', kind:'constraint'}) "
        "WHERE d.text=$text AND coalesce(d.requested_supersedes,'')=$old "
        "MATCH (d)-[:SUPPORTED_BY]->(src:Source) "
        "MATCH (d)-[:CONSTRAINS]->(s:Symbol {current:true, revision:$sha, repo_id:$repo}) "
        "WITH d, collect(DISTINCT src.uid) AS sources, collect(DISTINCT s.uid) AS subjects "
        "WHERE size(sources)=size($sources) AND all(x IN sources WHERE x IN $sources) "
        "AND size(subjects)=size($subjects) AND all(x IN subjects WHERE x IN $subjects) "
    )
    if params["old"]:
        guard += (
            "MATCH (old:Decision {uid:$old, repo_id:$repo, scope:'org', status:'active'}) "
            "MATCH (old)-[:CONSTRAINS]->(os:Symbol) "
            "WITH d, old, collect(DISTINCT os.uid) AS old_subjects "
            "WHERE size(old_subjects)=size($subjects) AND all(x IN old_subjects WHERE x IN $subjects) "
            "SET old.status='superseded' MERGE (d)-[:SUPERSEDES]->(old) "
        )
    result = store.query(
        guard + "SET d.status='active', d.approval='human_approved', "
        "d.approved_by=$by, d.approved_at=$at, d.approved_revision=$sha "
        "RETURN d.uid AS uid",
        params,
    )
    if not result:
        raise ValueError("Approval conflict or unrelated supersession; nothing approved")
    return result
