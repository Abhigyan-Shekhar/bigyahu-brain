"""Operator CLI only. Never imported by the MCP server or services."""

import getpass
import os
import sys
import uuid
from datetime import UTC, datetime


def require_operator(action):
    if not sys.stdin.isatty() or os.environ.get("BRAIN_OPERATOR_SESSION") != "1":
        raise ValueError("Administration requires an interactive, separate operator session")
    if input(f"After independent review, type {action}: ") != action:
        raise ValueError("Operation cancelled")


def approve(store, decision_id, expires_at=""):
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
    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None or expiry <= datetime.now(UTC):
            raise ValueError("Expiry must be timezone-aware and in the future")
        expires_at = expiry.astimezone(UTC).isoformat()
    proposal["expires_at"] = expires_at
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
        "expires": expires_at,
        "review": "review:" + uuid.uuid4().hex,
    }
    # A single atomic query revalidates the reviewed text/evidence/subjects and sync marker.
    guard = (
        "MATCH (p:Project {uid:$repo, syncing:false, last_completed_sync_sha:$sha}) "
        "WHERE NOT coalesce(p.documents_syncing,false) AND NOT coalesce(p.github_syncing,false) "
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
        "d.approved_by=$by, d.approved_at=$at, d.approved_revision=$sha,d.expires_at=$expires "
        "CREATE (r:ReviewRecord {uid:$review,repo_id:$repo,actor:$by,at:$at,action:'approve',"
        "reviewed_text:$text,source_uids:$sources,subject_uids:$subjects,revision:$sha,expires_at:$expires}) "
        "CREATE (r)-[:REVIEWS]->(d) "
        "RETURN d.uid AS uid",
        params,
    )
    if not result:
        raise ValueError("Approval conflict or unrelated supersession; nothing approved")
    return result


def review_decision(store, decision_id, action, reason):
    if action not in {"reject", "expire", "rollback"} or not reason.strip():
        raise ValueError("Review action and reason required")
    rows = store.query("MATCH (d:Decision {uid:$id,repo_id:$repo}) RETURN d.text AS text,d.status AS status",
                       {"id": decision_id,"repo":store.cfg.repo_id})
    if not rows:
        raise ValueError("Decision not found")
    expected = rows[0]
    if action=="reject" and expected["status"]!="proposed":
        raise ValueError("Only proposals may be rejected")
    if action in {"expire","rollback"} and expected["status"]!="active":
        raise ValueError("Only active decisions may expire or roll back")
    print(repr(expected))
    require_operator(action.upper()+" "+decision_id)
    status={"reject":"rejected","expire":"expired","rollback":"proposed"}[action]
    return store.query(
        "MATCH (d:Decision {uid:$id,repo_id:$repo,status:$old,text:$text}) "
        "SET d.status=$state,d.approval='none' "
        "CREATE (r:ReviewRecord {uid:$review,repo_id:$repo,actor:$by,at:$at,action:$action,"
        "reason:$reason,reviewed_text:$text,previous_status:$old}) CREATE (r)-[:REVIEWS]->(d) "
        "RETURN d.uid AS uid,d.status AS status",
        {"id":decision_id,"repo":store.cfg.repo_id,"old":expected["status"],"text":expected["text"],
         "state":status,"review":"review:"+uuid.uuid4().hex,"by":getpass.getuser(),
         "at":datetime.now(UTC).isoformat(),"action":action,"reason":reason})
