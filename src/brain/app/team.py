"""Authorized local team views and explicit selected-memory sharing.

The loopback operator administers teams they create. A member filter selects
shared contributions only; it never changes the configured identity.
"""

import json
import re
from pathlib import Path

from ..graph import GraphStore, GraphUnavailable
from ..memory import canonical, digest, now
from ..memory_ingest import share_memory
from ..memory_tools import MemoryTools
from ..services import Services
from . import personal


def scope(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ValueError("Use a team identifier with 1–64 letters, digits, underscores or hyphens")
    return "team:" + name


def authorized(memory):
    return [
        r[0]
        for r in memory.db.execute(
            "SELECT brain FROM grants WHERE tenant=? AND principal=? AND brain LIKE 'team:%' "
            "AND role IN ('reader','writer','reviewer') ORDER BY brain LIMIT 101",
            (memory.identity.tenant, memory.identity.principal),
        )
    ]


def retrieval_scopes(memory):
    # An untouched private brain has no evidence to retrieve and no projection.
    # Do not let it mask an otherwise valid authorized team projection.
    private = personal.brain(memory)
    exists = memory.db.execute(
        "SELECT 1 FROM records WHERE tenant=? AND brain=? LIMIT 1",
        (memory.identity.tenant, private),
    ).fetchone()
    return ([private] if exists else []) + authorized(memory)


def team_info(memory, name):
    brain = scope(name)
    memory.authorize(brain)
    members = memory.db.execute(
        "SELECT principal,role FROM grants WHERE tenant=? AND brain=? ORDER BY principal LIMIT 501",
        (memory.identity.tenant, brain),
    ).fetchall()
    if len(members) > 500:
        raise ValueError("Team membership exceeds the local view bound")
    owner = memory.db.execute(
        "SELECT actor FROM events WHERE tenant=? AND brain=? AND action='app_team_create' LIMIT 1",
        (memory.identity.tenant, brain),
    ).fetchone()
    return {
        "id": name,
        "role": memory._role(brain),
        "members": [dict(r) for r in members],
        "can_administer": bool(owner and owner[0] == memory.identity.principal),
    }


def create(cfg, name):
    brain = scope(name)
    with personal.catalog(cfg) as (memory, projection):
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            exists = memory.db.execute(
                "SELECT 1 FROM grants WHERE tenant=? AND brain=? UNION ALL "
                "SELECT 1 FROM records WHERE tenant=? AND brain=? LIMIT 1",
                (memory.identity.tenant, brain, memory.identity.tenant, brain),
            ).fetchone()
            if exists:
                raise ValueError("Team already exists; use your authorized team list")
            memory.db.execute(
                "INSERT INTO grants VALUES(?,?,?,?)",
                (memory.identity.tenant, memory.identity.principal, brain, "reviewer"),
            )
            memory._event(brain, name, "app_team_create")
        return {**team_info(memory, name), "projection": refresh(memory, projection, name)}


def refresh(memory, projection, name):
    memory.authorize(scope(name))
    if memory._role(scope(name)) != "reviewer":
        return {
            "status": "unavailable",
            "notice": "Catalog saved; a team reviewer must refresh the shared graph before retrieval.",
        }
    try:
        projection.sync(scope(name))
        return {"status": "ok"}
    except (ValueError, GraphUnavailable):
        return {
            "status": "unavailable",
            "notice": "Catalog saved; refresh the team graph before retrieval. No vector fallback is used.",
        }


def membership(cfg, name, principal, role, expected_role, reason):
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal)
        or role not in {"reader", "writer", "reviewer", "revoke"}
        or not reason.strip()
    ):
        raise ValueError("A valid principal, role and review reason are required")
    with personal.catalog(cfg) as (memory, projection):
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            info = team_info(memory, name)
            if not info["can_administer"]:
                raise PermissionError("Only this team's local creator can administer membership")
            if principal == memory.identity.principal:
                raise ValueError("The local creator's reviewer role must be preserved")
            current = next((m["role"] for m in info["members"] if m["principal"] == principal), "")
            if current != expected_role:
                raise ValueError("Membership changed; refresh before updating")
            if not current and len(info["members"]) >= 100:
                raise ValueError("The app supports at most 100 members per team")
            memory.db.execute(
                "DELETE FROM grants WHERE tenant=? AND principal=? AND brain=?",
                (memory.identity.tenant, principal, scope(name)),
            )
            if role != "revoke":
                memory.db.execute(
                    "INSERT INTO grants VALUES(?,?,?,?)",
                    (memory.identity.tenant, principal, scope(name), role),
                )
            memory._event(
                scope(name),
                principal,
                "app_membership",
                canonical({"previous": current, "role": role, "reason": reason}),
            )
        return {**team_info(memory, name), "projection": refresh(memory, projection, name)}


def record(memory, name, uid):
    brain = scope(name)
    memory.authorize(brain)
    r = memory.db.execute(
        "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=? AND state!='deleted'",
        (memory.identity.tenant, brain, uid),
    ).fetchone()
    reviewer = memory._role(brain) == "reviewer"
    if not r or (
        r["state"] != "accepted" and not reviewer and r["author"] != memory.identity.principal
    ):
        raise KeyError("Unknown shared memory")
    return r


def source_details(cfg, memory, r):
    """Validate selected shared text without exposing its private source envelope."""
    proof = memory.db.execute(
        "SELECT detail FROM events WHERE tenant=? AND brain=? AND uid=? AND action='app_share_snapshot' ORDER BY rowid DESC LIMIT 1",
        (memory.identity.tenant, r["brain"], r["uid"]),
    ).fetchone()
    if not proof or not re.fullmatch(r"[a-f0-9]{64}", proof[0]):
        raise ValueError("Shared memory needs an app-verifiable selected-source snapshot")
    raw = (cfg.repo_root.parent / "memory-sources" / proof[0]).read_text(encoding="utf-8")
    value = json.loads(raw)
    if (
        digest(raw) != proof[0]
        or value["text"] != r["text"]
        or value["hash"] != r["hash"]
        or canonical(value["sources"]) != r["sources"]
        or value["author"] != r["author"]
    ):
        raise ValueError("Shared source snapshot changed")
    return {
        "text": value["text"],
        "sources": value["sources"],
        "author": value["author"],
        "digest": proof[0],
        "kind": "selected_shared_memory",
    }


def share(cfg, name, uid, expected_hash, expected_target=""):
    with personal.catalog(cfg) as (memory, projection):
        selected = personal.row(memory, uid)
        personal.source_details(cfg, memory, selected)
        # Existing sharing contract requires an accepted, current private revision
        # and writer/reviewer access to the destination. It retains source citations.
        shared = share_memory(memory, uid, expected_hash, scope(name), expected_target)
        r = record(memory, name, shared["uid"])
        snapshot = personal.snapshot(
            cfg,
            {
                "text": r["text"],
                "sources": json.loads(r["sources"]),
                "hash": r["hash"],
                "author": r["author"],
                "binding": False,
            },
        )
        with memory.db:
            memory._event(scope(name), r["uid"], "app_share_snapshot", snapshot)
        return {**shared, "projection": refresh(memory, projection, name)}


def review(cfg, name, uid, expected_hash, expected_state, action, reason):
    with personal.catalog(cfg) as (memory, projection):
        memory.db.execute("BEGIN IMMEDIATE")
        memory.authorize(scope(name), review=True)
        r = record(memory, name, uid)
        if r["hash"] != expected_hash or r["state"] != expected_state:
            raise ValueError("Shared memory changed; refresh before review")
        if (expected_state, action) not in {
            ("proposed", "accept"),
            ("proposed", "reject"),
            ("accepted", "rollback"),
        }:
            raise ValueError("This review transition is unavailable")
        if action == "accept":
            source_details(cfg, memory, r)
        result = memory.review(scope(name), uid, action, expected_hash, reason)
        return {**result, "projection": refresh(memory, projection, name)}


def graph(cfg, memory, projection, brains, *, include_proposals=False, member=""):
    view = projection.read(brains, include_proposals=include_proposals)
    if view["status"] == "ok":
        for node in view["nodes"]:
            if node["kind"] == "Memory":
                r = record(memory, node["brain"][5:], node["record_uid"])
                source_details(cfg, memory, r)
        if member:
            # Induce a slice around visible contributions, not the member's private brain.
            authors = {
                n["uid"] for n in view["nodes"] if n["kind"] == "Person" and n.get("name") == member
            }
            roots = {
                e["target"]
                for e in view["edges"]
                if e["relation"] == "AUTHORED" and e["source"] in authors
            }
            ids = set(authors) | roots
            for e in view["edges"]:
                if (
                    e["source"] in roots
                    or e["target"] in roots
                    or (e["relation"] == "HAS_MEMBER" and e["target"] in authors)
                ):
                    ids.update([e["source"], e["target"]])
            view = {
                **view,
                "nodes": [n for n in view["nodes"] if n["uid"] in ids],
                "edges": [e for e in view["edges"] if e["source"] in ids and e["target"] in ids],
            }
    if view["status"] != "ok":
        return {
            "status": view["status"],
            "warnings": view["warnings"],
            "graph": {"nodes": [], "edges": []},
            "binding": False,
        }
    return {
        "status": view["status"],
        "warnings": view["warnings"],
        "graph": personal.graph_view(view),
        "binding": False,
    }


def memory_evidence(cfg, name, uid, expected_hash):
    with personal.catalog(cfg) as (memory, projection):
        try:
            r = record(memory, name, uid)
        except KeyError as exc:
            raise ValueError("Shared memory is no longer available") from exc
        if (
            r["state"] != "accepted"
            or r["hash"] != expected_hash
            or (r["expires"] and r["expires"] <= now())
        ):
            raise ValueError("Shared memory changed, expired or revoked")
        source_details(cfg, memory, r)
        view = graph(cfg, memory, projection, [scope(name)])
        if view["status"] != "ok":
            raise ValueError("Shared graph is unavailable or stale")
        native = projection.read([scope(name)])
        selected = [
            n
            for n in native["nodes"]
            if n.get("record_uid") == uid and n.get("hash") == expected_hash
        ]
        if len(selected) != 1:
            raise ValueError("Shared memory is absent from native graph")
        roots = {selected[0]["uid"]}
        ids = set(roots)
        for e in native["edges"]:
            if e["source"] in roots or e["target"] in roots:
                ids.update([e["source"], e["target"]])
        return {
            "kind": "team_memory",
            "ref": {"name": name, "uid": uid, "expected_hash": expected_hash},
            "title": "Team Brain · " + name + " · reviewed memory",
            "text": r["text"],
            "digest": digest(r["text"]),
            "revision": "memory:" + expected_hash,
            "uri": json.loads(r["sources"])[0]["uri"],
            "verification": "accepted_team_memory_and_native_graph",
            "graph": personal.graph_view(
                {
                    "nodes": [n for n in native["nodes"] if n["uid"] in ids],
                    "edges": [
                        e for e in native["edges"] if e["source"] in ids and e["target"] in ids
                    ],
                }
            ),
            "binding": False,
        }


def search(cfg, query):
    if not Path(personal.config(cfg).memory_db).exists():
        return {
            "status": "unavailable",
            "items": [],
            "warnings": ["personal_brain_not_initialized"],
        }
    with personal.catalog(cfg) as (memory, projection):
        brains = retrieval_scopes(memory)
        if not brains:
            return {
                "status": "ok",
                "backend": "falkor",
                "vector_enabled": False,
                "items": [],
                "graph": {"nodes": [], "edges": []},
            }
        if len(brains) > 10:
            return {
                "status": "incomplete",
                "items": [],
                "warnings": ["Select fewer than ten memory scopes before agent retrieval"],
            }
        result = MemoryTools(
            memory, Services(GraphStore(personal.config(cfg))), projection
        ).memory_search(query, brains, backend="falkor", limit=8)
        if result.get("status") != "ok":
            return {**result, "items": [], "graph": {"nodes": [], "edges": []}}
        try:
            candidates = [
                *result.get("items", []),
                *[
                    {"brain": n["brain"], "uid": n["record_uid"]}
                    for n in result.get("graph", {}).get("nodes", [])
                    if n["kind"] == "Memory"
                ],
            ]
            for item in candidates:
                if item["brain"].startswith("team:"):
                    source_details(cfg, memory, record(memory, item["brain"][5:], item["uid"]))
                else:
                    personal.source_details(cfg, memory, personal.row(memory, item["uid"]))
        except (ValueError, OSError, KeyError, PermissionError):
            return {
                "status": "incomplete",
                "items": [],
                "graph": {"nodes": [], "edges": []},
                "warnings": ["memory_source_unavailable"],
            }
        return result
