"""Embedding-free FalkorDB exact/full-text retrieval and native path expansion.

Full-text matching uses FalkorDB's index. Corpus-wide relevance scores are
deliberately ignored: hidden/expired text must not influence authorized ranking.
Eligible candidates are sorted by query-local overlap before candidate limits.
"""

import json
import re
from collections import defaultdict, deque

from .memory import canonical

EXPAND = {
    "UPDATES",
    "EXTENDS",
    "RELATES_TO",
    "MENTIONS",
    "SUPPORTED_BY",
    "SAME_CITATION",
    "VERIFIED_SOURCE",
    "RESOLVES_TO",
    "DECLARES",
    "SUPPORTS",
}
SEED_KINDS = {
    "Memory",
    "Entity",
    "Source",
    "CompanySource",
    "CompanyDocument",
    "CompanySymbol",
    "CompanyFile",
}
FIELDS = ("text", "name", "uri", "path", "record_uid", "company_uid")
RETURN_FIELDS = ", ".join("n." + field + " AS " + field for field in FIELDS)


class FalkorMemorySearch:
    def __init__(self, projection):
        self.projection = projection
        self.memory, self.store = projection.memory, projection.store

    def search(self, query, brains, limit=10, include_proposals=False, include_company=False):
        if (
            not isinstance(query, str)
            or not 1 <= len(query) <= 1000
            or type(limit) is not int
            or not 1 <= limit <= 20
        ):
            raise ValueError("Search bounds exceeded")
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            view = self.projection._read(brains, include_proposals, include_company)
            base = {
                "backend": "falkor",
                "mode": "exact_fulltext_graph",
                "vector_enabled": False,
                "binding": False,
                "trust_status": "untrusted_evidence",
                "items": [],
                "warnings": view["warnings"] + ["source_prose_is_untrusted"],
                "status": view["status"],
                "graph": {"nodes": [], "edges": []},
            }
            if view["status"] != "ok":
                return base
            if len(view["nodes"]) > 1000 or len(view["edges"]) > 2000:
                raise ValueError("Search exceeds 1000 eligible nodes or 2000 edges; narrow scopes")
            if not self.projection.search_index_ready():
                base.update(status="incomplete")
                base["warnings"].append("memory_search_index_refresh_required")
                return base
            nodes = {n["uid"]: n for n in view["nodes"]}
            memory_nodes = {uid: n for uid, n in nodes.items() if n["kind"] == "Memory"}
            eligible = [uid for uid, n in nodes.items() if n["kind"] in SEED_KINDS]
            if not memory_nodes:
                return base
            terms = list(dict.fromkeys(re.findall(r"\w+", query.lower(), re.UNICODE)))[:20]
            seeds, contributions = defaultdict(dict), defaultdict(dict)
            proofs = defaultdict(list)
            params = {"allowed": eligible, "q": query, "terms": terms}
            exact = self.store.memory_query(
                "MATCH (n:MemoryNode) WHERE n.uid IN $allowed AND "
                "(n.uid=$q OR n.record_uid=$q OR n.uri=$q OR n.name=$q OR n.path=$q OR n.company_uid=$q) "
                "RETURN n.uid AS uid, " + RETURN_FIELDS + " ORDER BY uid LIMIT 51",
                params,
            )
            lexical = []
            if terms:
                lexical = self.store.memory_query(
                    "CALL db.idx.fulltext.queryNodes('MemoryNode',$expression) YIELD node AS n "
                    "WHERE n.uid IN $allowed "
                    "WITH n, size([term IN $terms WHERE "
                    "toLower(coalesce(n.text,'')+' '+coalesce(n.name,'')) CONTAINS term]) AS overlap "
                    "RETURN n.uid AS uid, " + RETURN_FIELDS + ", overlap "
                    "ORDER BY overlap DESC, uid LIMIT 51",
                    {**params, "expression": "|".join(terms)},
                )
            for channel, rows in (("falkor_exact", exact), ("falkor_fulltext", lexical)):
                if len(rows) > 50:
                    base["warnings"].append("seed_candidates_truncated:" + channel)
                for rank, row in enumerate(rows[:50], 1):
                    node = nodes.get(row["uid"])
                    if node is None or any(
                        (row.get(f) or "") != (node.get(f) or "") for f in FIELDS
                    ):
                        base["status"] = "incomplete"
                        base["warnings"].append("search_projection_content_mismatch")
                        return base
                    seeds[row["uid"]][channel] = (3 if channel == "falkor_exact" else 1) / (
                        60 + rank
                    )
            seed_order = sorted(seeds, key=lambda uid: (-sum(seeds[uid].values()), uid))[:50]
            seeds = {uid: seeds[uid] for uid in seed_order}

            def add(target, seed, path, relations, assertions, directions):
                hops = len(relations)
                for channel, weight in seeds[seed].items():
                    value = weight / (2**hops)
                    contributions[target][channel] = max(
                        contributions[target].get(channel, 0), value
                    )
                    proofs[target].append(
                        {
                            "path": path,
                            "relationships": relations,
                            "assertion_uids": assertions,
                            "directions": directions,
                            "seed_channel": channel,
                            "contribution": value,
                        }
                    )

            for uid in seeds:
                if uid in memory_nodes:
                    add(uid, uid, [uid], [], [], [])
            if seeds:
                paths = self.store.memory_query(
                    "MATCH p=(start:MemoryNode)-[*1..4]-(target:MemoryNode) "
                    "WHERE start.uid IN $seeds AND target.uid IN $memories AND start.uid<>target.uid "
                    "AND all(n IN nodes(p) WHERE n.uid IN $allowed) "
                    "AND all(r IN relationships(p) WHERE type(r) IN $types "
                    "AND (coalesce(r.assertion_uid,'')='' OR r.assertion_uid IN $assertions)) "
                    "RETURN [n IN nodes(p) | n.uid] AS path, "
                    "[r IN relationships(p) | type(r)] AS relations, "
                    "[r IN relationships(p) | coalesce(r.assertion_uid,'')] AS assertions LIMIT 1001",
                    {
                        "seeds": list(seeds),
                        "memories": list(memory_nodes),
                        "allowed": list(nodes),
                        "types": sorted(EXPAND),
                        "assertions": [
                            e["assertion_uid"] for e in view["edges"] if e.get("assertion_uid")
                        ],
                    },
                )
                if len(paths) > 1000:
                    base["status"] = "incomplete"
                    base["warnings"].append("graph_path_bound_exceeded_narrow_query")
                    return base
                expected = {
                    (e["source"], e["relation"], e["target"], e.get("assertion_uid", ""))
                    for e in view["edges"]
                }
                for row in paths:
                    ids, relations, assertions = row["path"], row["relations"], row["assertions"]
                    if len(ids) != len(set(ids)):
                        continue
                    if (
                        not ids
                        or ids[0] not in seeds
                        or ids[-1] not in memory_nodes
                        or any(uid not in nodes for uid in ids)
                        or not 1 <= len(relations) <= 4
                        or len(ids) != len(relations) + 1
                        or len(assertions) != len(relations)
                    ):
                        raise ValueError("Unexpected native retrieval path")
                    directions = []
                    for i, (relation, assertion) in enumerate(zip(relations, assertions)):
                        if relation not in EXPAND:
                            raise ValueError("Unexpected native retrieval relationship")
                        if (ids[i], relation, ids[i + 1], assertion) in expected:
                            directions.append("outgoing")
                        elif (ids[i + 1], relation, ids[i], assertion) in expected:
                            directions.append("incoming")
                        else:
                            base["status"] = "incomplete"
                            base["warnings"].append("retrieval_path_projection_mismatch")
                            return base
                    add(ids[-1], ids[0], ids, relations, assertions, directions)
            ordered = sorted(
                contributions,
                key=lambda uid: (
                    -sum(contributions[uid].values()),
                    memory_nodes[uid]["brain"],
                    memory_nodes[uid]["record_uid"],
                ),
            )[:limit]
            keep, required_edges = set(), set()
            for uid in ordered:
                node = memory_nodes[uid]
                row = self.memory.db.execute(
                    "SELECT sources FROM records WHERE tenant=? AND brain=? AND uid=? AND hash=?",
                    (self.memory.identity.tenant, node["brain"], node["record_uid"], node["hash"]),
                ).fetchone()
                best = min(
                    proofs[uid],
                    key=lambda p: (-p["contribution"], len(p["relationships"]), canonical(p)),
                )
                best = {k: v for k, v in best.items() if k != "contribution"}
                channels = sorted(contributions[uid])
                if best["relationships"]:
                    channels.append("graph_expansion")
                base["items"].append(
                    {
                        "uid": node["record_uid"],
                        "graph_uid": uid,
                        "brain": node["brain"],
                        "hash": node["hash"],
                        "text": node["text"][:2000],
                        "truncated": len(node["text"]) > 2000,
                        "state": node["state"],
                        "sources": json.loads(row["sources"]),
                        "score": sum(contributions[uid].values()),
                        "retrieval_channels": channels,
                        "graph_paths": [best],
                        "updated_by": sorted(
                            {
                                nodes[e["source"]]["record_uid"]
                                for e in view["edges"]
                                if e["target"] == uid
                                and e["relation"] == "UPDATES"
                                and e.get("state") == "accepted"
                                and nodes[e["source"]]["kind"] == "Memory"
                            }
                        ),
                        "binding": False,
                        "trust_status": "untrusted_evidence",
                    }
                )
                keep.update(best["path"])
                for i, (relation, assertion, direction) in enumerate(
                    zip(best["relationships"], best["assertion_uids"], best["directions"])
                ):
                    a, b = best["path"][i : i + 2]
                    if direction == "incoming":
                        a, b = b, a
                    required_edges.add((a, relation, b, assertion))
            # Bounded evidence neighborhood, excluding shared authorship/containers
            # so context cannot expand to every unrelated note in a brain.
            adjacency = defaultdict(list)
            for edge in view["edges"]:
                if edge["relation"] in EXPAND:
                    adjacency[edge["source"]].append(edge["target"])
                    adjacency[edge["target"]].append(edge["source"])
            pending = deque((uid, 0) for uid in sorted(keep))
            seen = set(keep)
            while pending:
                uid, depth = pending.popleft()
                if depth == 2:
                    continue
                for neighbor in sorted(set(adjacency[uid])):
                    if neighbor not in seen:
                        if len(keep) >= 200:
                            base["warnings"].append("evidence_neighborhood_truncated")
                            pending.clear()
                            break
                        keep.add(neighbor)
                        seen.add(neighbor)
                        pending.append((neighbor, depth + 1))
            evidence = [
                e
                for e in view["edges"]
                if e["source"] in keep and e["target"] in keep and e["relation"] in EXPAND
            ]
            if len(evidence) > 400:
                base["warnings"].append("evidence_neighborhood_truncated")
                key = lambda e: (
                    e["source"],
                    e["relation"],
                    e["target"],
                    e.get("assertion_uid", ""),
                )
                mandatory = [e for e in evidence if key(e) in required_edges]
                optional = [e for e in evidence if key(e) not in required_edges]
                evidence = mandatory + optional[: 400 - len(mandatory)]
            rendered, budget = [], 16000
            for uid in sorted(keep):
                node = dict(nodes[uid])
                if "text" in node:
                    original = node["text"]
                    node["text"] = original[: min(1000, budget)]
                    node["original_chars"] = len(original)
                    node["truncated"] = len(node["text"]) < len(original)
                    budget -= len(node["text"])
                rendered.append(node)
            base["graph"] = {"nodes": rendered, "edges": evidence}
            base["warnings"] = sorted(set(base["warnings"]))
            base["seed_count"] = len(seeds)
            base["company_revision"] = view.get("company_revision")
            base["unresolved_company_references"] = view.get("unresolved_company_references", [])
            # Expiry can advance while native queries run, even though the
            # catalog transaction prevents concurrent record/grant writes.
            initial = {(n["brain"], n["record_uid"], n["hash"]) for n in memory_nodes.values()}
            current = {
                (brain, row["uid"], row["hash"])
                for brain in dict.fromkeys(brains)
                for row in self.projection._rows(brain, include_proposals)
            }
            if initial != current:
                base.update(status="incomplete", items=[], graph={"nodes": [], "edges": []})
                base["warnings"].append("memory_eligibility_changed_retry")
            if include_company and self.store.revision() != {
                "sha": view.get("company_revision"),
                "syncing": False,
            }:
                base.update(status="incomplete", items=[], graph={"nodes": [], "edges": []})
                base["warnings"].append("company_revision_changed_retry")
            return base
