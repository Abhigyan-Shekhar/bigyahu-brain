"""Selected current-memory graph interchange. No identities, grants or code execution.

The explicit topology is validated against source-backed deterministic extraction.
Import stores source records transactionally; the native projection rebuilds the
same topology after destination review. Arbitrary claimed semantic edges are not
silently promoted into the graph.
"""

import json
import re

from .memory import canonical, citations, digest, now
from .memory_graph import entities
from .memory_links import RELATIONS, MemoryLinks


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Invalid graph interchange identifier")
    return value


def portable_id(uid):
    # Preserve opaque IDs through destination UID remapping and subsequent export.
    match = re.fullmatch(r"abhi:[A-Za-z0-9_-]{1,64}:(r-[0-9a-f]{64})", uid)
    return match[1] if match else "r-" + digest(uid)


def topology(records, relations=()):
    """A bounded subgraph induced by only selected current records and citations."""
    nodes, edges = {}, {}
    for record in records:
        uid = record["id"]
        nodes[uid] = {"id": uid, "kind": "Memory", "record": uid}
        for citation in record["sources"]:
            target = "s-" + digest(canonical(citation))
            nodes[target] = {"id": target, "kind": "Source", **citation}
            edges[uid, "SUPPORTED_BY", target] = {
                "source": uid,
                "relation": "SUPPORTED_BY",
                "target": target,
            }
        for name in entities(record["text"]):
            target = "e-" + digest(name)
            nodes[target] = {"id": target, "kind": "Entity", "name": name}
            edges[uid, "MENTIONS", target] = {
                "source": uid,
                "relation": "MENTIONS",
                "target": target,
            }
    for link in relations:
        uid = "l-" + digest(canonical(link))
        edges[link["source"], link["relation"], link["target"], uid] = {
            "source": link["source"],
            "relation": link["relation"],
            "target": link["target"],
            "assertion": uid,
            "evidence": link["sources"],
        }
    if len(nodes) > 500 or len(edges) > 1000:
        raise ValueError("Portable graph exceeds 500 nodes or 1000 edges")
    return {"nodes": [nodes[k] for k in sorted(nodes)], "edges": [edges[k] for k in sorted(edges)]}


def validate_records(records):
    if not isinstance(records, list) or not 1 <= len(records) <= 200:
        raise ValueError("Select one to 200 portable records")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "id",
            "text",
            "sources",
            "expected_hash",
            "expires",
        }:
            raise ValueError("Invalid portable record fields")
        if (
            not isinstance(record["id"], str)
            or not re.fullmatch(r"r-[0-9a-f]{64}", record["id"])
            or record["id"] in seen
        ):
            raise ValueError("Invalid or duplicate portable record ID")
        seen.add(record["id"])
        if (
            not isinstance(record["text"], str)
            or not record["text"].strip()
            or len(record["text"]) > 12000
            or not isinstance(record["expires"], str)
            or not isinstance(record["expected_hash"], str)
            or not re.fullmatch(r"(?:[0-9a-f]{64})?", record["expected_hash"])
        ):
            raise ValueError("Invalid portable record content or revision")
        citations(record["sources"])


def seal(body):
    return {**body, "digest": digest(canonical(body))}


def validate_relations(records, relations):
    if not isinstance(relations, list) or not 1 <= len(relations) <= 200:
        raise ValueError("Select one to 200 portable relationships")
    selected = {r["id"]: r for r in records}
    seen = set()
    for link in relations:
        if not isinstance(link, dict) or set(link) != {"source", "relation", "target", "sources"}:
            raise ValueError("Invalid portable relationship fields")
        if (
            not all(isinstance(link[k], str) for k in ("source", "relation", "target"))
            or link["source"] not in selected
            or link["target"] not in selected
            or link["source"] == link["target"]
            or link["relation"] not in RELATIONS
        ):
            raise ValueError("Invalid portable relationship endpoints or type")
        citations(link["sources"])
        evidence = {
            canonical(s) for key in ("source", "target") for s in selected[link[key]]["sources"]
        }
        proof = [canonical(s) for s in link["sources"]]
        if proof != sorted(set(proof)) or any(s not in evidence for s in proof):
            raise ValueError("Portable relationship evidence must match selected endpoints")
        key = canonical(link)
        if key in seen:
            raise ValueError("Duplicate portable relationship")
        seen.add(key)
    if [canonical(link) for link in relations] != sorted(seen):
        raise ValueError("Portable relationships must use canonical order")


def validate(payload):
    if (
        not isinstance(payload, dict)
        or (set(payload) - {"relations"})
        != {
            "format",
            "tenant",
            "team",
            "collection",
            "parent_digest",
            "records",
            "graph",
            "digest",
        }
        or payload["format"] != "abhi/2"
    ):
        raise ValueError("Invalid abhi/2 envelope")
    if len(canonical(payload).encode()) > 1_000_000:
        raise ValueError("Portable graph exceeds 1 MB")
    for key in ("tenant", "team", "collection"):
        identifier(payload[key])
    if not isinstance(payload["parent_digest"], str) or not re.fullmatch(
        r"(?:[0-9a-f]{64})?", payload["parent_digest"]
    ):
        raise ValueError("Invalid graph parent digest")
    if payload["digest"] != digest(canonical({k: v for k, v in payload.items() if k != "digest"})):
        raise ValueError("Portable graph integrity mismatch")
    validate_records(payload["records"])
    if "relations" in payload:
        validate_relations(payload["records"], payload["relations"])
    # Exact canonical form rejects duplicate nodes/edges, dangling links, hidden
    # fields, executable hooks, ACL claims and invented unsupported relationships.
    if payload["graph"] != topology(payload["records"], payload.get("relations", [])):
        raise ValueError("Portable topology must exactly match the selected source records")


def export_graph(memory, brain, selections, team, collection, link_ids=None):
    """Selections map exact current record IDs to hashes; never expand neighbors."""
    identifier(team)
    identifier(collection)
    link_ids = [] if link_ids is None else link_ids
    if (
        not isinstance(link_ids, list)
        or len(link_ids) > 200
        or not all(isinstance(uid, str) for uid in link_ids)
        or len(set(link_ids)) != len(link_ids)
    ):
        raise ValueError("Select at most 200 unique relationship IDs")
    if (
        not isinstance(selections, dict)
        or not 1 <= len(selections) <= 200
        or not all(isinstance(uid, str) and isinstance(sha, str) for uid, sha in selections.items())
    ):
        raise ValueError("Select one to 200 exact record ID/hash pairs")
    with memory.lock, memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        memory.authorize(brain)
        records, native_records = [], []
        for uid, expected in sorted(selections.items()):
            row = memory.db.execute(
                "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=? "
                "AND hash=? AND state='accepted' AND (expires='' OR expires>?)",
                (memory.identity.tenant, brain, uid, expected, now()),
            ).fetchone()
            if row is None:
                raise ValueError("Export requires each exact current accepted record")
            native_records.append(row)
            records.append(
                {
                    "id": portable_id(uid),
                    "text": row["text"],
                    "sources": json.loads(row["sources"]),
                    "expected_hash": "",
                    "expires": row["expires"],
                }
            )
        records.sort(key=lambda r: r["id"])
        visible = {r["uid"]: r for r in MemoryLinks(memory).visible(brain, native_records)}
        if any(uid not in visible for uid in link_ids):
            raise ValueError("Export requires each exact accepted relationship and both endpoints")
        relations = sorted(
            [
                {
                    "source": portable_id(visible[uid]["source_uid"]),
                    "target": portable_id(visible[uid]["target_uid"]),
                    "relation": visible[uid]["relation"],
                    "sources": json.loads(visible[uid]["sources"]),
                }
                for uid in link_ids
            ],
            key=canonical,
        )
        body = {
            "format": "abhi/2",
            "tenant": memory.identity.tenant,
            "team": team,
            "collection": collection,
            "parent_digest": "",
            "records": records,
            "graph": topology(records, relations),
        }
        if relations:
            body["relations"] = relations
        payload = seal(body)
        validate(payload)
        memory._event(brain, collection, "graph_export", payload["digest"])
        return payload


def import_graph(memory, payload):
    # Authorize destination before processing text or topology. File-supplied
    # destination cannot create a grant or cross the configured tenant boundary.
    if not isinstance(payload, dict) or payload.get("tenant") != memory.identity.tenant:
        raise PermissionError("Import tenant unavailable")
    team = identifier(payload.get("team"))
    memory.authorize("team:" + team, write=True)
    validate(payload)
    from .memory_ingest import _import_records

    envelope = {
        k: payload[k]
        for k in (
            "tenant",
            "team",
            "collection",
            "parent_digest",
            "records",
        )
    }
    envelope["format"] = "abhi/1"

    def import_links():
        brain = "team:" + team
        for link in payload.get("relations", []):
            source, target = [
                "abhi:" + payload["collection"] + ":" + link[k] for k in ("source", "target")
            ]
            hashes = [
                memory.db.execute(
                    "SELECT hash FROM records WHERE tenant=? AND brain=? AND uid=?",
                    (memory.identity.tenant, brain, uid),
                ).fetchone()[0]
                for uid in (source, target)
            ]
            MemoryLinks(memory).put(
                brain, source, hashes[0], link["relation"], target, hashes[1], link["sources"]
            )

    with memory.lock:
        # Reuse exact CAS/transaction semantics and the envelope's actual digest.
        result = _import_records(memory, envelope, payload["digest"], import_links)
    return {
        **result,
        "format": "abhi/2",
        "nodes": len(payload["graph"]["nodes"]),
        "edges": len(payload["graph"]["edges"]),
        "binding": False,
    }


def write_graph(path, payload):
    """Never overwrite an existing file or follow a final-component symlink."""
    import os

    validate(payload)
    raw = canonical(payload).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
