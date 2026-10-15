"""Parameterized FalkorDB access. There is deliberately no offline query fallback."""

from falkordb import FalkorDB
from redis.exceptions import RedisError


class GraphUnavailable(RuntimeError):
    pass


LABELS = {
    "Project",
    "File",
    "Symbol",
    "Person",
    "Team",
    "Commit",
    "Issue",
    "PR",
    "Comment",
    "Document",
    "Source",
    "Decision",
}
EDGES = {
    "CONTAINS",
    "DECLARES",
    "CALLS",
    "IMPORTS",
    "AUTHORED",
    "MODIFIES",
    "REVIEWED",
    "CHANGES",
    "CODEOWNER_OF",
    "DISCUSSED_IN",
    "REFERENCES",
    "SUPPORTS",
    "SUPPORTED_BY",
    "CONSTRAINS",
    "APPLIES_TO",
    "SUPERSEDES",
}


class GraphStore:
    def __init__(self, cfg):
        self.cfg = cfg
        self.db = None

    def query(self, cypher, params=None, scope="org"):
        name = self.cfg.graph_name(scope)
        try:
            if self.db is None:
                self.db = FalkorDB(
                    host=self.cfg.host,
                    port=self.cfg.port,
                    socket_connect_timeout=2,
                    socket_timeout=10,
                )
            graph = self.db.select_graph(name)
            result = graph.query(cypher, params or {})
            names = [h[1] for h in result.header]
            return [dict(zip(names, row)) for row in result.result_set]
        except RedisError as exc:
            raise GraphUnavailable("FalkorDB query failed; graph context unavailable") from exc

    def bootstrap(self):
        for scope in ("org", "private"):
            rows = self.query("CALL db.indexes() YIELD label, type RETURN label, type", scope=scope)
            existing = {(r["label"], r["type"]) for r in rows}
            for label, fields in {
                "Decision": ["text"],
                "Document": ["text"],
                "Issue": ["title", "body"],
                "PR": ["title", "body"],
            }.items():
                if not any(l == label and "FULLTEXT" in str(t).upper() for l, t in existing):
                    args = ", ".join(repr(x) for x in [label, *fields])
                    self.query(f"CALL db.idx.fulltext.createNodeIndex({args})", scope=scope)
            self.query(
                "CALL db.idx.fulltext.queryNodes('Decision', 'bootstrap') "
                "YIELD node RETURN node.uid AS uid LIMIT 1",
                scope=scope,
            )

    def upsert(self, label, uid, properties, scope="org"):
        if label not in LABELS:
            raise ValueError("Unknown label")
        self.query(
            f"MERGE (n:{label} {{uid:$uid}}) SET n += $props",
            {"uid": uid, "props": {**properties, "uid": uid}},
            scope,
        )

    def edge(self, source, relation, target, properties=None, scope="org"):
        if relation not in EDGES:
            raise ValueError("Unknown relationship")
        self.query(
            f"MATCH (a {{uid:$a}}), (b {{uid:$b}}) MERGE (a)-[r:{relation}]->(b) SET r += $props",
            {"a": source, "b": target, "props": properties or {}},
            scope,
        )

    def revision(self):
        rows = self.query(
            "MATCH (p:Project {uid:$uid}) RETURN "
            "p.last_completed_sync_sha AS sha, p.syncing AS syncing",
            {"uid": self.cfg.repo_id},
        )
        return rows[0] if rows else {"sha": None, "syncing": True}
