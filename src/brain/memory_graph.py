"""Rebuildable, permission-filtered FalkorDB projections of local memory.

This graph has no decision approval authority. Identity and eligibility are
always obtained from the live catalog, including when a projection is stale.
"""

import json
import re
from collections import defaultdict

from .memory import canonical, digest, now
from .memory_links import MemoryLinks

RELATIONS = {
    "HAS_MEMBER",
    "HAS_BRAIN",
    "CONTAINS",
    "AUTHORED",
    "SUPPORTED_BY",
    "MENTIONS",
    "MENTIONS_CONCEPT",
    "MATCHES_MENTION",
    "UPDATES",
    "EXTENDS",
    "RELATES_TO",
    "VERIFIED_SOURCE",
    "RESOLVES_TO",
    "DECLARES",
    "SUPPORTS",
}


def entities(text):
    """Extract explicit code identifiers only; never invent semantic entities."""
    return sorted(set(re.findall(r"`([A-Za-z_][A-Za-z0-9_./:-]{0,159})`", text)))[:20]


class MemoryGraph:
    def __init__(self, memory, store):
        if (
            memory.identity.tenant != store.cfg.tenant_id
            or memory.identity.principal != store.cfg.principal
        ):
            raise ValueError("Graph and catalog identities must match")
        self.memory, self.store = memory, store

    def slot(self, brain):
        return "memory:" + digest(canonical([self.memory.identity.tenant, brain]))

    def _annotations(self, brain):
        rows = self.memory.db.execute(
            "SELECT e.uid,e.detail FROM events e WHERE e.tenant=? AND e.brain=? "
            "AND e.action='conversation_analysis' AND e.rowid=(SELECT max(x.rowid) "
            "FROM events x WHERE x.tenant=e.tenant AND x.brain=e.brain AND x.uid=e.uid "
            "AND x.action='conversation_analysis') ORDER BY e.uid LIMIT 1001",
            (self.memory.identity.tenant, brain),
        ).fetchall()
        if len(rows) > 1000:
            raise ValueError("Conversation annotation bound exceeded")
        return {row["uid"]: json.loads(row["detail"]) for row in rows if row["detail"]}

    def _manifest(self, brain):
        rows = self.memory.db.execute(
            "SELECT uid,hash,state,expires,author,previous FROM records "
            "WHERE tenant=? AND brain=? ORDER BY uid",
            (self.memory.identity.tenant, brain),
        ).fetchall()
        members = self.memory.db.execute(
            "SELECT principal,role FROM grants WHERE tenant=? AND brain=? ORDER BY principal",
            (self.memory.identity.tenant, brain),
        ).fetchall()
        links = self.memory.db.execute(
            "SELECT * FROM memory_links WHERE tenant=? AND brain=? ORDER BY uid LIMIT 2001",
            (self.memory.identity.tenant, brain),
        ).fetchall()
        if len(rows) > 1000 or len(members) > 500 or len(links) > 2000:
            raise ValueError("Graph projection bound exceeded; partition this brain")
        return digest(
            canonical(
                [
                    list(map(tuple, rows)),
                    list(map(tuple, members)),
                    list(map(tuple, links)),
                    self._annotations(brain),
                ]
            )
        )

    def _rows(self, brain, include_proposals):
        reviewer = self.memory._role(brain) in {"owner", "reviewer"}
        return self.memory.db.execute(
            "SELECT * FROM records WHERE tenant=? AND brain=? "
            "AND (state='accepted' OR (state='proposed' AND ? AND (author=? OR ?))) "
            "AND (expires='' OR expires>?) ORDER BY uid LIMIT 1001",
            (
                self.memory.identity.tenant,
                brain,
                include_proposals,
                self.memory.identity.principal,
                reviewer,
                now(),
            ),
        ).fetchall()

    def _snapshot(self, brain, rows, include_proposals=False):
        slot = self.slot(brain)
        nodes, edges = {}, {}

        def node(kind, key, **props):
            uid = slot + ":" + kind + ":" + digest(key)
            nodes[uid] = {"uid": uid, "kind": kind, "brain": brain, **props}
            return uid

        def edge(a, relation, b, basis="catalog", assertion_uid="", state="", evidence_json="[]"):
            edges[a, relation, b, assertion_uid] = {
                "source": a,
                "relation": relation,
                "target": b,
                "basis": basis,
                "assertion_uid": assertion_uid,
                "state": state,
                "evidence_json": evidence_json,
            }

        root = node("Brain", brain, name=brain)
        if brain.startswith("private:"):
            person = node(
                "Person", self.memory.identity.principal, name=self.memory.identity.principal
            )
            edge(person, "HAS_BRAIN", root)
        if brain.startswith("team:"):
            team = node("Team", brain, name=brain[5:])
            edge(team, "HAS_BRAIN", root)
            members = self.memory.db.execute(
                "SELECT principal FROM grants WHERE tenant=? AND brain=? "
                "AND role IN ('reader','writer','reviewer') ORDER BY principal",
                (self.memory.identity.tenant, brain),
            )
            for member in members:
                person = node("Person", member[0], name=member[0])
                edge(team, "HAS_MEMBER", person)
        memory_nodes = {}
        annotations = self._annotations(brain)
        for row in rows:
            uid = node(
                "Memory",
                row["uid"] + ":" + row["hash"],
                record_uid=row["uid"],
                hash=row["hash"],
                text=row["text"],
                state=row["state"],
            )
            memory_nodes[row["uid"]] = uid
            author = node("Person", row["author"], name=row["author"])
            edge(root, "CONTAINS", uid)
            edge(author, "AUTHORED", uid)
            for source in json.loads(row["sources"]):
                target = node("Source", canonical(source), **source)
                edge(uid, "SUPPORTED_BY", target)
            if row["previous"]:
                previous = node(
                    "Version",
                    row["uid"] + ":" + row["previous"],
                    hash=row["previous"],
                    record_uid=row["uid"],
                )
                edge(uid, "UPDATES", previous, "explicit_record_revision")
            for name in entities(row["text"]):
                entity = node("Entity", name, name=name)
                edge(uid, "MENTIONS", entity, "explicit_backtick_mention")
            analysis = annotations.get(row["uid"], {})
            if analysis.get("hash") == row["hash"]:
                for name in analysis.get("entities", []):
                    if (
                        not isinstance(name, str)
                        or not 1 <= len(name) <= 160
                        or name not in row["text"]
                    ):
                        raise ValueError("Invalid literal conversation entity")
                    entity = node("Entity", name, name=name)
                    edge(uid, "MENTIONS", entity, "model_selected_literal_entity")
        for link in MemoryLinks(self.memory).visible(brain, rows, include_proposals):
            edge(
                memory_nodes[link["source_uid"]],
                link["relation"],
                memory_nodes[link["target_uid"]],
                "source_cited_memory_assertion",
                link["uid"],
                link["state"],
                link["sources"],
            )
        return list(nodes.values()), list(edges.values())

    def sync(self, brain, include_company=False):
        """Operator/reviewer write; interrupted refreshes stay fenced until retry."""
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            self.memory.authorize(brain, review=True)
            if include_company:
                self.memory.authorize("company")
            manifest = self._manifest(brain)
            nodes, edges = self._snapshot(brain, self._rows(brain, True), True)
            company = None
            if include_company:
                from .memory_company import CompanyBridge

                company = CompanyBridge(self.memory, self.store).snapshot(
                    brain, self.slot(brain), nodes
                )
                nodes.extend(company["nodes"])
                edges.extend(company["edges"])
            slot = self.slot(brain)
            query = self.store.memory_query
            query(
                "MERGE (p:MemoryProjection {uid:$slot}) SET p.ready=false, p.company_ready=false",
                {"slot": slot},
            )
            query("MATCH (n:MemoryNode {slot:$slot}) DETACH DELETE n", {"slot": slot})
            query(
                "UNWIND $nodes AS item MERGE (n:MemoryNode {uid:item.uid}) "
                "SET n += item, n.slot=$slot",
                {"nodes": nodes, "slot": slot},
            )
            for relation in sorted(RELATIONS):
                selected = [e for e in edges if e["relation"] == relation]
                if selected:
                    query(
                        "UNWIND $edges AS item "
                        "MATCH (a:MemoryNode {uid:item.source}), "
                        "(b:MemoryNode {uid:item.target}) "
                        f"MERGE (a)-[r:{relation} {{assertion_uid:item.assertion_uid}}]->(b) "
                        "SET r.basis=item.basis, r.state=item.state, r.evidence_json=item.evidence_json",
                        {"edges": selected},
                    )
            # Connect source proxies across brains by the exact *claimed* source
            # version. These are provenance associations, not verified truth.
            query(
                "MATCH (a:MemoryNode {kind:'Source'}), (b:MemoryNode {kind:'Source'}) "
                "WHERE (a.slot=$slot OR b.slot=$slot) AND a.slot<>b.slot "
                "AND a.uid<b.uid AND a.uri=b.uri AND a.digest=b.digest "
                "MERGE (a)-[r:SAME_CITATION]->(b) SET r.basis='exact_uri_and_digest'",
                {"slot": slot},
            )
            self.ensure_search_index()
            query(
                "MATCH (p:MemoryProjection {uid:$slot}) SET p.ready=true, p.manifest=$manifest, "
                "p.company_ready=$company_ready, p.company_revision=$company_revision",
                {
                    "slot": slot,
                    "manifest": manifest,
                    "company_ready": company is not None,
                    "company_revision": company["revision"] if company else "",
                },
            )
            return {
                "brain": brain,
                "nodes": len(nodes),
                "edges": len(edges),
                "manifest": manifest,
                "binding": False,
                "company_revision": company["revision"] if company else None,
                "unresolved_company_references": company["unresolved"] if company else [],
            }

    def _search_index_fields(self):
        rows = self.store.memory_query("CALL db.indexes()")
        fields = {
            field
            for row in rows
            if row.get("label") == "MemoryNode"
            for field, kinds in row.get("types", {}).items()
            if "FULLTEXT" in kinds
        }
        return fields

    def search_index_ready(self):
        return {"text", "name"} <= self._search_index_fields()

    def ensure_search_index(self):
        missing = sorted({"text", "name"} - self._search_index_fields())
        if missing:
            fields = ", ".join(repr(field) for field in missing)
            self.store.memory_query(f"CALL db.idx.fulltext.createNodeIndex('MemoryNode', {fields})")

    def read(self, brains, include_proposals=False, include_company=False):
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            return self._read(brains, include_proposals, include_company)

    def _read(self, brains, include_proposals=False, include_company=False):
        """Return bounded native graph edges only between currently eligible nodes."""
        if (
            not isinstance(brains, list)
            or not 1 <= len(brains) <= 10
            or not all(isinstance(brain, str) for brain in brains)
        ):
            raise ValueError("Select one to ten brains")
        # Authorize the entire request before the first graph access.
        for brain in brains:
            self.memory.authorize(brain)
        if include_company:
            self.memory.authorize("company")
        result = {
            "status": "ok",
            "nodes": [],
            "edges": [],
            "warnings": [],
            "binding": False,
            "trust_status": "untrusted_evidence",
        }
        for brain in dict.fromkeys(brains):
            manifest = self._manifest(brain)
            projection = self.store.memory_query(
                "MATCH (p:MemoryProjection {uid:$slot}) "
                "RETURN p.ready AS ready, p.manifest AS manifest, "
                "p.company_ready AS company_ready, p.company_revision AS company_revision",
                {"slot": self.slot(brain)},
            )
            if (
                not projection
                or not projection[0]["ready"]
                or (projection[0]["manifest"] != manifest)
            ):
                result["status"] = "incomplete"
                result["warnings"].append("projection_refresh_required:" + brain)
                continue
            expected_nodes, expected_edges = self._snapshot(
                brain, self._rows(brain, include_proposals), include_proposals
            )
            if include_company:
                from .memory_company import CompanyBridge

                company = CompanyBridge(self.memory, self.store).snapshot(
                    brain, self.slot(brain), expected_nodes
                )
                if (
                    not projection[0].get("company_ready")
                    or projection[0].get("company_revision") != company["revision"]
                ):
                    result["status"] = "incomplete"
                    result["warnings"].append("company_projection_refresh_required:" + brain)
                    continue
                result["company_revision"] = company["revision"]
                result.setdefault("unresolved_company_references", []).extend(company["unresolved"])
                if company["unresolved"]:
                    result["warnings"].append("unresolved_company_references:" + brain)
                expected_nodes.extend(company["nodes"])
                expected_edges.extend(company["edges"])
            if len(expected_nodes) > 500 or len(expected_edges) > 1000:
                raise ValueError("Graph view exceeds 500 nodes or 1000 edges")
            allowed = {n["uid"]: n for n in expected_nodes}
            assertion_ids = [e["assertion_uid"] for e in expected_edges if e["assertion_uid"]]
            rows = self.store.memory_query(
                "MATCH (a:MemoryNode {slot:$slot})-[r]->(b:MemoryNode {slot:$slot}) "
                "WHERE a.uid IN $allowed AND b.uid IN $allowed "
                "AND (r.assertion_uid='' OR r.assertion_uid IN $assertions) "
                "RETURN a.uid AS source, type(r) AS relation, b.uid AS target, "
                "r.basis AS basis, r.assertion_uid AS assertion_uid, r.state AS state, "
                "r.evidence_json AS evidence_json "
                "ORDER BY source,relation,target,assertion_uid LIMIT 1001",
                {
                    "slot": self.slot(brain),
                    "allowed": list(allowed),
                    "assertions": assertion_ids,
                },
            )
            # Validate returned graph topology against the live catalog projection.
            # This also prevents a tampered/incomplete projection inventing edges.
            edge_key = lambda e: (e["source"], e["relation"], e["target"], e["assertion_uid"])
            expected = {edge_key(e): e for e in expected_edges}
            actual = {edge_key(e): e for e in rows}
            if actual != expected:
                result["status"] = "incomplete"
                result["warnings"].append("projection_topology_mismatch:" + brain)
                continue
            result["nodes"].extend(allowed.values())
            result["edges"].extend(rows)
        sources = [n for n in result["nodes"] if n["kind"] == "Source"]
        expected = []
        by_citation = defaultdict(list)
        for source in sources:
            by_citation[source["uri"], source["digest"]].append(source)
        for group in by_citation.values():
            for i, a in enumerate(group):
                for b in group[i + 1 :]:
                    if a["brain"] == b["brain"]:
                        continue
                    if len(expected) >= 1000:
                        raise ValueError("Cross-brain citation edge bound exceeded")
                    left, right = sorted([a["uid"], b["uid"]])
                    expected.append(
                        {
                            "source": left,
                            "relation": "SAME_CITATION",
                            "target": right,
                            "basis": "exact_uri_and_digest",
                        }
                    )
        if sources:
            rows = self.store.memory_query(
                "MATCH (a:MemoryNode)-[r:SAME_CITATION]->(b:MemoryNode) "
                "WHERE a.uid IN $allowed AND b.uid IN $allowed "
                "RETURN a.uid AS source, type(r) AS relation, b.uid AS target, "
                "r.basis AS basis ORDER BY source,target LIMIT 1001",
                {"allowed": [n["uid"] for n in sources]},
            )
            key = lambda e: (e["source"], e["target"])
            if sorted(rows, key=key) != sorted(expected, key=key):
                result["status"] = "incomplete"
                result["warnings"].append("cross_brain_projection_mismatch")
            else:
                result["edges"].extend(rows)
        return result
