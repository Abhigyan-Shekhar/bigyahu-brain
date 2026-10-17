"""Local operator Personal Brain: reviewed catalog records and native FalkorDB reads.

Identity, tenant and paths come from managed app configuration, never HTTP/tool
arguments. Every repository has a separate private catalog; no grants are added.
"""

import json
import re
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from ..graph import GraphStore, GraphUnavailable
from ..memory import Identity, Memory, canonical, digest, now
from ..memory_graph import MemoryGraph
from ..memory_tools import MemoryTools
from ..services import Services


def config(cfg):
    if not cfg.tenant_id:
        raise ValueError("Personal Brain requires a managed repository tenant")
    return replace(
        cfg,
        memory_db=str(cfg.repo_root.parent / "personal.sqlite"),
        memory_graph_enabled=True,
        embedding_model_dir=None,
    )


@contextmanager
def catalog(cfg):
    cfg = config(cfg)
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, cfg.principal))
    try:
        yield memory, MemoryGraph(memory, GraphStore(cfg))
    finally:
        memory.close()


def brain(memory):
    return "private:" + memory.identity.principal


def rows(memory):
    memory.authorize(brain(memory))
    result = memory.db.execute(
        "SELECT uid,text,sources,state,hash,expires,collection FROM records WHERE tenant=? AND brain=? AND state!='deleted' ORDER BY rowid DESC LIMIT 101",
        (memory.identity.tenant, brain(memory)),
    ).fetchall()
    return [
        {**dict(r), "sources": json.loads(r["sources"]), "binding": False} for r in result[:100]
    ], len(result) > 100


def row(memory, uid):
    memory.authorize(brain(memory))
    result = memory.db.execute(
        "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=? AND state!='deleted'",
        (memory.identity.tenant, brain(memory), uid),
    ).fetchone()
    if not result:
        raise KeyError("Unknown private memory")
    return result


def snapshot(cfg, value):
    text = canonical(value)
    fingerprint = digest(text)
    folder = cfg.repo_root.parent / "memory-sources"
    folder.mkdir(exist_ok=True)
    (folder / fingerprint).write_text(text, encoding="utf-8")
    return fingerprint


def source_details(cfg, memory, record):
    """Verify immutable app source artifacts, including exact selected user spans."""
    result = []
    for source in json.loads(record["sources"]):
        uri = source["uri"]
        match = re.fullmatch(r"urn:company-brain:(note|lesson|transfer):([a-f0-9]{64})", uri)
        if match:
            text = (cfg.repo_root.parent / "memory-sources" / match[2]).read_text(encoding="utf-8")
            if digest(text) != source["digest"] or match[2] != source["digest"]:
                raise ValueError("Memory source snapshot changed")
            saved = json.loads(text)
            if saved["text"] != record["text"]:
                raise ValueError("Memory differs from its reviewed source snapshot")
            result.append({"kind": match[1], "uri": uri, "digest": source["digest"], "text": text})
            continue
        match = re.fullmatch(
            r"urn:codex-conversation:([A-Za-z0-9_-]+):([A-Za-z0-9_-]+):chars:([0-9]+):([0-9]+)", uri
        )
        if not match:
            raise ValueError("Memory does not have an app-verifiable source")
        # Imports record their exact consent digest in the catalog. Source envelopes
        # are content-addressed; never read a client-selected filesystem path.
        events = memory.db.execute(
            "SELECT detail FROM events WHERE tenant=? AND brain=? AND uid=? AND action='conversation_consent' ORDER BY rowid DESC LIMIT 100",
            (memory.identity.tenant, brain(memory), match[1]),
        ).fetchall()
        found = None
        for event in events:
            fingerprint = event[0]
            if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
                continue
            file = cfg.repo_root.parent / "memory-sources" / fingerprint
            if not file.exists():
                continue
            raw = file.read_text(encoding="utf-8")
            if digest(raw) != fingerprint:
                raise ValueError("Conversation snapshot changed")
            envelope = json.loads(raw)
            for turn in envelope["turns"]:
                if turn["id"] == match[2] and turn["role"] == "user":
                    span = turn["text"][int(match[3]) : int(match[4])]
                    if span == record["text"] and digest(span) == source["digest"]:
                        found = {
                            "kind": "selected_user_turn",
                            "uri": uri,
                            "digest": source["digest"],
                            "text": turn["text"],
                        }
                        break
            if found:
                break
        if not found:
            raise ValueError("Selected conversation span is unavailable or changed")
        result.append(found)
    return result


def company_enabled(memory):
    try:
        memory.authorize("company")
        return True
    except PermissionError:
        return False


def connect_company(cfg, enabled):
    """Explicit local operator grant; agent tools cannot create catalog permissions."""
    if cfg.principal != "app_operator":
        raise PermissionError("Only the managed local operator can connect company evidence")
    from . import team

    with catalog(cfg) as (memory, projection):
        with memory.db:
            if enabled:
                memory.db.execute(
                    "INSERT OR REPLACE INTO grants VALUES(?,?,?,?)",
                    (memory.identity.tenant, memory.identity.principal, "company", "reader"),
                )
            else:
                memory.db.execute(
                    "DELETE FROM grants WHERE tenant=? AND principal=? AND brain='company'",
                    (memory.identity.tenant, memory.identity.principal),
                )
            memory._event(brain(memory), "company", "app_company_bridge", str(enabled))
        results = {brain(memory): refresh(memory, projection)}
        for scope in team.retrieval_scopes(memory):
            if scope.startswith("team:") and memory._role(scope) == "reviewer":
                results[scope] = team.refresh(memory, projection, scope[5:])
        return {"company_enabled": enabled, "projections": results}


def refresh(memory, projection):
    try:
        projection.sync(brain(memory), include_company=company_enabled(memory))
        return {"status": "ok"}
    except (GraphUnavailable, ValueError):
        return {
            "status": "unavailable",
            "notice": "Catalog saved; refresh the private graph before retrieval. No catalog search fallback is used.",
        }


def propose_note(cfg, text):
    if not 1 <= len(text.strip()) <= 4000:
        raise ValueError("Enter 1–4000 characters")
    saved = {"kind": "operator_note", "text": text, "binding": False}
    fingerprint = snapshot(cfg, saved)
    with catalog(cfg) as (memory, projection):
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            result = memory.put(
                brain(memory),
                text,
                [{"uri": "urn:company-brain:note:" + fingerprint, "digest": fingerprint}],
                uid="note:" + fingerprint,
            )
        return {**result, "projection": refresh(memory, projection)}


def propose_lesson(state, action_id):
    from .actions import checked_action, verification_result

    action = state.get(action_id, "action")
    if (
        action["status"] != "complete"
        or not action.get("tests_passed")
        or not action.get("lesson_proposal", {}).get("text")
    ):
        raise ValueError("A completed action with passing tests and a draft lesson is required")
    if not action.get("tests") or any(
        not t.get("passed")
        or t.get("exit_code") != 0
        or t.get("outcome") != "exited"
        or t.get("tests_reported", 0) <= 0
        for t in action["tests"]
    ):
        raise ValueError("Verified passing test outcomes are required for lesson review")
    if not verification_result(action)["regression_demonstrated"]:
        raise ValueError(
            "Tests passed, but a baseline-failing regression has not been demonstrated"
        )
    checked_action(state, action)
    cfg = state.config(action["project"])
    report = {
        "kind": "coding_lesson",
        "action": action_id,
        "text": action["lesson_proposal"]["text"],
        "base_revision": action["base_revision"],
        "objective": action["objective"],
        "plan_digest": action["plan_digest"],
        "changed_files": action["changed_files"],
        "patch_sha256": digest(action["patch"]),
        "tests": [
            {k: t[k] for k in ("argv", "exit_code", "outcome", "passed", "tests_reported")}
            for t in action["tests"]
        ],
        "binding": False,
    }
    fingerprint = snapshot(cfg, report)
    with catalog(cfg) as (memory, projection):
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            result = memory.put(
                brain(memory),
                report["text"],
                [{"uri": "urn:company-brain:lesson:" + fingerprint, "digest": fingerprint}],
                uid="lesson:" + action_id,
                collection="coding-lessons",
            )
        return {**result, "projection": refresh(memory, projection)}


def review(cfg, uid, expected_hash, expected_state, action, reason):
    with catalog(cfg) as (memory, projection):
        memory.db.execute("BEGIN IMMEDIATE")
        current = row(memory, uid)
        if current["hash"] != expected_hash or current["state"] != expected_state:
            raise ValueError("Memory changed; refresh before reviewing")
        if (expected_state, action) not in {
            ("proposed", "accept"),
            ("proposed", "reject"),
            ("accepted", "rollback"),
        }:
            raise ValueError("This review transition is unavailable")
        if action == "accept":
            source_details(cfg, memory, current)
        result = memory.review(brain(memory), uid, action, expected_hash, reason)
        return {**result, "projection": refresh(memory, projection)}


def graph_view(view):
    nodes = [
        {
            "id": n["uid"],
            "labels": [n["kind"]],
            "label": n.get("name")
            or n.get("qualname")
            or n.get("path")
            or n.get("text", "")[:80]
            or n.get("uri")
            or n["kind"],
            **{
                k: n[k]
                for k in ("company_uid", "company_repo", "graph_revision", "path", "qualname")
                if k in n
            },
        }
        for n in view["nodes"][:150]
    ]
    ids = {n["id"] for n in nodes}
    edges = [
        {k: e[k] for k in ("source", "target", "relation")}
        for e in view["edges"]
        if e["source"] in ids and e["target"] in ids
    ][:300]
    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": len(view["nodes"]) > 150 or len(view["edges"]) > 300,
    }


def evidence_slice(view, root):
    """A selected record's sources and explicit company identity paths, bounded to three hops."""
    ids, frontier = {root}, {root}
    allowed = {n["uid"] for n in view["nodes"] if n["kind"] != "Memory" or n["uid"] == root}
    for _ in range(3):
        neighbors = set()
        for edge in view["edges"]:
            if edge["source"] in frontier and edge["target"] in allowed:
                neighbors.add(edge["target"])
            if edge["target"] in frontier and edge["source"] in allowed:
                neighbors.add(edge["source"])
        frontier = neighbors - ids
        ids.update(frontier)
    return graph_view(
        {
            "nodes": [n for n in view["nodes"] if n["uid"] in ids],
            "edges": [e for e in view["edges"] if e["source"] in ids and e["target"] in ids],
        }
    )


def memory_evidence(cfg, uid, expected_hash):
    if not Path(config(cfg).memory_db).is_file():
        raise ValueError("Personal Brain is not initialized")
    with catalog(cfg) as (memory, projection):
        record = row(memory, uid)
        if (
            record["state"] != "accepted"
            or record["hash"] != expected_hash
            or (record["expires"] and record["expires"] <= now())
        ):
            raise ValueError("Memory was changed, revoked or is not accepted")
        source_details(cfg, memory, record)
        view = projection.read([brain(memory)], include_company=company_enabled(memory))
        if view["status"] != "ok":
            raise ValueError("Personal graph is stale or unavailable; refresh before retrieval")
        selected = [
            n
            for n in view["nodes"]
            if n.get("record_uid") == uid and n.get("hash") == expected_hash
        ]
        if len(selected) != 1:
            raise ValueError("Accepted memory is absent from the native graph")
        graph = evidence_slice(view, selected[0]["uid"])
        return {
            "kind": "memory",
            "ref": {"uid": uid, "expected_hash": expected_hash},
            "title": "Personal Brain · reviewed coding lesson"
            if uid.startswith("lesson:")
            else "Personal Brain · reviewed memory",
            "text": record["text"],
            "digest": digest(record["text"]),
            "revision": "memory:" + expected_hash,
            "uri": json.loads(record["sources"])[0]["uri"],
            "verification": "accepted_private_memory_and_native_graph",
            "graph": graph,
            "binding": False,
        }


def search(cfg, query):
    if not Path(config(cfg).memory_db).is_file():
        return {
            "status": "unavailable",
            "warnings": ["personal_brain_not_initialized"],
            "items": [],
        }
    with catalog(cfg) as (memory, projection):
        result = MemoryTools(memory, Services(GraphStore(config(cfg))), projection).memory_search(
            query, [brain(memory)], backend="falkor", limit=8
        )
        if result.get("status") == "ok":
            try:
                for item in result.get("items", []):
                    source_details(cfg, memory, row(memory, item["uid"]))
            except (ValueError, OSError):
                return {
                    "status": "incomplete",
                    "backend": "falkor",
                    "items": [],
                    "graph": {"nodes": [], "edges": []},
                    "warnings": ["private_memory_source_unavailable"],
                }
        return result


def conversation_preview(state, project, session, selected):
    chat = state.get(session, "session")
    if (
        chat["project"] != project
        or not 1 <= len(selected) <= 20
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("Select one to twenty unique turns from this repository's conversation")
    turns = {t["id"]: t for t in state.list("turn", session) if t["status"] == "complete"}
    if not set(selected) <= set(turns):
        raise ValueError("Select completed conversation turns")
    payload = {
        "format": "conversation/1",
        "session": session,
        "turns": [
            {"id": uid, "role": "user", "text": turns[uid]["question"]} for uid in sorted(selected)
        ],
    }
    return {"payload": payload, "consent_digest": digest(canonical(payload))}


def import_selected(state, uid):
    from ..conversation import ingest_conversation

    job = state.get(uid, "memory_import")
    if not state.transition(
        uid,
        {"status": "queued"},
        status="running",
        stage="Extracting proposals from selected user turns",
    ):
        return
    try:
        preview = conversation_preview(state, job["project"], job["session"], job["turns"])
        if preview["consent_digest"] != job["consent_digest"]:
            raise ValueError("Selected turns changed; preview and consent again")
        cfg = state.config(job["project"])
        snapshot(cfg, preview["payload"])
        with catalog(cfg) as (memory, projection):
            result = ingest_conversation(
                memory,
                preview["payload"],
                job["consent_digest"],
                semantic_model=state.model if job["semantic"] else None,
            )
            projected = refresh(memory, projection)
        state.update(
            uid,
            status="complete",
            stage="Selected memories await review"
            if result.get("items")
            else "No durable memories found",
            result=result,
            projection=projected,
        )
    except Exception as exc:  # noqa: BLE001 - persistent background failure
        state.update(
            uid,
            status="failed",
            stage="Memory extraction stopped",
            error=str(exc)[:500]
            if isinstance(exc, ValueError)
            else "Memory import failed; inspect the Personal Brain and retry after review.",
        )
