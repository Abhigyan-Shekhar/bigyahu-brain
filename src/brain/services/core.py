"""Five bounded operations; no administrative mutation is reachable here."""

import re
import subprocess
import uuid
from datetime import UTC, datetime
from functools import wraps

from ..graph import GraphUnavailable
from ..ingest.git_parser import clean, revision


def envelope(**kwargs):
    return {
        "status": "ok",
        "graph_revision": None,
        "evidence": [],
        "warnings": [],
        "untrusted_source_excerpts": [],
        "verification": "static_evidence",
        **kwargs,
    }


def operation(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except GraphUnavailable:
            return envelope(status="unavailable", warnings=["graph_unavailable"])
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return envelope(status="error", warnings=[str(exc)])

    return wrapped


class Services:
    def __init__(self, store):
        self.store, self.cfg = store, store.cfg

    def ready(self):
        state = self.store.revision()
        if not state["sha"] or state["syncing"]:
            raise GraphUnavailable("No completed sync")
        return state["sha"]

    @operation
    def remember(
        self,
        text: str,
        scope: str = "org",
        source_refs: list[str] | None = None,
        applies_to: list[str] | None = None,
        supersedes: str = "",
    ) -> dict:
        self.cfg.graph_name(scope)
        if not text.strip() or len(text) > 12000:
            raise ValueError("Proposal text must contain 1–12000 characters")
        source_refs, applies_to = source_refs or [], applies_to or []
        if len(source_refs) > 20 or len(applies_to) > 100:
            raise ValueError("Proposal exceeds reference limit")
        # References resolve only inside the chosen graph and configured repository.
        sources = self.store.query(
            "MATCH (s:Source {repo_id:$repo}) WHERE s.uid IN $ids RETURN s.uid AS uid",
            {"repo": self.cfg.repo_id, "ids": source_refs},
            scope,
        )
        subjects = self.store.query(
            "MATCH (s:Symbol {repo_id:$repo, current:true}) "
            "WHERE s.uid IN $ids RETURN s.uid AS uid",
            {"repo": self.cfg.repo_id, "ids": applies_to},
            scope,
        )
        if len(sources) != len(set(source_refs)) or len(subjects) != len(set(applies_to)):
            raise ValueError("Unknown or cross-scope evidence/subjects")
        uid = "D-" + uuid.uuid4().hex
        self.store.upsert(
            "Decision",
            uid,
            {
                "repo_id": self.cfg.repo_id,
                "text": text,
                "scope": scope,
                "kind": "constraint",
                "status": "proposed",
                "approval": "none",
                "requested_supersedes": supersedes,
                "created_at": datetime.now(UTC).isoformat(),
            },
            scope,
        )
        for source in source_refs:
            self.store.edge(uid, "SUPPORTED_BY", source, scope=scope)
        for symbol in applies_to:
            self.store.edge(uid, "CONSTRAINS", symbol, scope=scope)
        return envelope(
            decision_id=uid,
            decision_status="proposed",
            approval="none",
            warnings=[] if source_refs else ["needs_evidence"],
            message="Requires independent human approval before constraining edits.",
        )

    @operation
    def check_change(
        self, files: list[str], symbols: list[str] | None = None, diff: str = ""
    ) -> dict:
        if not files or len(files) > 50 or len(symbols or []) > 100 or len(diff) > 200000:
            raise ValueError("Expected 1–50 files and at most 100 symbols")
        files = [self.cfg.path(f) for f in files]
        sha = self.ready()
        candidates = self.store.query(
            "MATCH (s:Symbol {repo_id:$repo, current:true}) WHERE s.path IN $files "
            "RETURN s.uid AS uid, s.path AS path, s.qualname AS qualname, "
            "s.lineno AS lineno, s.end_lineno AS end_lineno LIMIT 1001",
            {"repo": self.cfg.repo_id, "files": files},
        )
        warnings, selected, precision = [], candidates, "file"
        if not candidates:
            return envelope(
                status="unknown",
                graph_revision=sha,
                precision="file",
                warnings=["no_indexed_symbols"],
            )
        stale = revision(self.cfg.repo_root) != sha or not clean(self.cfg.repo_root)
        if len(candidates) > 1000:
            return envelope(
                status="incomplete", graph_revision=sha, warnings=["symbol_limit_exceeded"]
            )
        if stale:
            warnings.append("stale_index")
        elif symbols:
            selected = []
            for name in symbols:
                matches = [
                    s
                    for s in candidates
                    if name in (s["uid"], s["qualname"], f"{s['path']}::{s['qualname']}")
                ]
                if len(matches) != 1:
                    return envelope(
                        status="unknown",
                        precision="ambiguous" if matches else "unknown",
                        graph_revision=sha,
                        candidates=matches,
                        warnings=["symbol_ambiguous" if matches else "symbol_not_found"],
                    )
                selected.extend(matches)
            precision = "symbol"
        elif diff:
            # Deliberately conservative until old-side consistency is fully verified.
            warnings.append("diff_mapping_unverified_file_fallback")
        else:
            warnings.append("file_level_coverage")
        ids = sorted({s["uid"] for s in selected})
        paths = (
            self.store.query(
                "MATCH p=(caller:Symbol)-[:CALLS*1..2]->(target:Symbol) "
                "WHERE target.uid IN $ids AND all(n IN nodes(p) WHERE n.current=true AND n.repo_id=$repo) "
                "RETURN DISTINCT [n IN nodes(p) | n.uid] AS path, "
                "[r IN relationships(p) | r.confidence] AS confidence LIMIT 101",
                {"ids": ids, "repo": self.cfg.repo_id},
            )
            if ids
            else []
        )
        if len(paths) > 100:
            return envelope(
                status="incomplete", graph_revision=sha, warnings=["caller_limit_exceeded"]
            )
        related = sorted(set(ids) | {uid for p in paths for uid in p["path"]})
        decisions = self._decisions(related)
        if len(decisions) > 100:
            return envelope(
                status="incomplete", graph_revision=sha, warnings=["decision_limit_exceeded"]
            )
        must, review, evidence, excerpts = [], [], [], []
        for d in decisions:
            sources = d.pop("sources") or []
            sources = [s for s in sources if s and s.get("uid")]
            excerpts.extend({"source_uid": s["uid"], "text": s.get("excerpt", "")} for s in sources)
            evidence.extend({"source_uid": s["uid"], "uri": s.get("uri")} for s in sources)
            # Decision prose is also untrusted. Structural applicability is separate.
            text = d.pop("text")
            excerpts.append({"decision_id": d["uid"], "text": text})
            d["source_uids"] = [s["uid"] for s in sources]
            binding = (
                d["status"] == "active"
                and d["approval"] == "human_approved"
                and d["kind"] == "constraint"
                and bool(sources)
                and d.get("approved_revision") == sha
                and not stale
            )
            if d["status"] != "superseded":
                (must if binding else review).append(d)
        owners = [self.find_owner(file=path) for path in files]
        return envelope(
            graph_revision=sha,
            precision=precision,
            targets=selected,
            caller_paths=paths,
            must_preserve=must,
            review=review,
            evidence=evidence,
            untrusted_source_excerpts=excerpts,
            warnings=warnings,
            owners=owners,
        )

    def _decisions(self, ids):
        return self.store.query(
            "MATCH (d:Decision {repo_id:$repo, scope:'org'})-[:CONSTRAINS]->(s:Symbol) "
            "WHERE s.uid IN $ids OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(src:Source) "
            "RETURN d.uid AS uid, d.text AS text, d.status AS status, d.approval AS approval, "
            "d.kind AS kind, d.approved_revision AS approved_revision, collect(DISTINCT s.uid) AS subjects, "
            "collect(DISTINCT {uid:src.uid, uri:src.uri, excerpt:src.excerpt}) AS sources LIMIT 101",
            {"repo": self.cfg.repo_id, "ids": ids},
        )

    @operation
    def find_owner(self, file: str = "", symbol: str = "") -> dict:
        sha = self.ready()
        if symbol:
            rows = self.store.query(
                "MATCH (s:Symbol {uid:$uid, repo_id:$repo, current:true}) RETURN s.path AS path",
                {"uid": symbol, "repo": self.cfg.repo_id},
            )
            if not rows:
                return envelope(status="unknown", graph_revision=sha, warnings=["symbol_not_found"])
            file = rows[0]["path"]
        file = self.cfg.path(file)
        params = {"repo": self.cfg.repo_id, "path": file}
        owners = self.store.query(
            "MATCH (p)-[r:CODEOWNER_OF]->(f:File {repo_id:$repo, path:$path, current:true}) "
            "RETURN p.uid AS uid, p.name AS name, r.source_uid AS source_uid, r.pattern AS pattern",
            params,
        )
        if owners:
            return envelope(graph_revision=sha, ownership="explicit_file_owner", items=owners)
        owners = self.store.query(
            "MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:MODIFIES]->"
            "(f:File {repo_id:$repo, path:$path, current:true}) "
            "RETURN p.uid AS uid, p.name AS name, count(DISTINCT c) AS commits, "
            "collect(DISTINCT c.uid) AS evidence_commits ORDER BY commits DESC LIMIT 5",
            params,
        )
        return envelope(
            graph_revision=sha,
            ownership="inferred_maintainer" if owners else "unknown",
            items=owners,
            warnings=["Git activity is not attested symbol ownership"],
        )

    @operation
    def get_context(
        self, query: str, keywords: list[str] | None = None, scope: str = "org"
    ) -> dict:
        self.cfg.graph_name(scope)
        sha = self.ready()
        if len(query) > 1000 or len(keywords or []) > 5:
            raise ValueError("Query exceeds bounds")
        rows = self.store.query(
            "MATCH (n {repo_id:$repo}) WHERE n.uid=$query RETURN n.uid AS uid LIMIT 10",
            {"repo": self.cfg.repo_id, "query": query},
            scope,
        )
        terms = keywords or query.split()[:5]
        terms = [t for t in terms if re.fullmatch(r"[A-Za-z0-9_]{1,64}", t)]
        if not rows and terms:
            for label in ("Decision", "Document", "Issue", "PR"):
                rows.extend(
                    self.store.query(
                        f"CALL db.idx.fulltext.queryNodes('{label}', $terms) YIELD node, score "
                        "WHERE node.repo_id=$repo RETURN node.uid AS uid, score LIMIT 5",
                        {"terms": " ".join(terms), "repo": self.cfg.repo_id},
                        scope,
                    )
                )
        ids = [r["uid"] for r in rows]
        paths = (
            self.store.query(
                "MATCH p=(a)-[*1..2]->(b) WHERE a.uid IN $ids "
                "RETURN [n IN nodes(p) | n.uid] AS path LIMIT 50",
                {"ids": ids},
                scope,
            )
            if ids
            else []
        )
        return envelope(
            graph_revision=sha, items=rows, evidence=paths, warnings=["keyword_search_not_semantic"]
        )

    @operation
    def trace_decision(self, decision_id: str = "", symbol_uid: str = "", topic: str = "") -> dict:
        sha = self.ready()
        rows = self.store.query(
            "MATCH (d:Decision {repo_id:$repo, scope:'org'}) "
            "WHERE ($id<>'' AND d.uid=$id) OR ($topic<>'' AND d.text CONTAINS $topic) "
            "OR ($symbol<>'' AND (d)-[:CONSTRAINS]->(:Symbol {uid:$symbol})) "
            "OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(s:Source) "
            "OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision) "
            "OPTIONAL MATCH (new:Decision)-[:SUPERSEDES]->(d) "
            "RETURN d.uid AS uid, d.status AS status, d.approval AS approval, "
            "d.approved_by AS approved_by, d.approved_at AS approved_at, "
            "d.text AS text, collect(DISTINCT {uid:s.uid, uri:s.uri, excerpt:s.excerpt}) AS sources, "
            "collect(DISTINCT old.uid) AS supersedes, collect(DISTINCT new.uid) AS replaced_by LIMIT 20",
            {
                "repo": self.cfg.repo_id,
                "id": decision_id,
                "topic": topic[:200],
                "symbol": symbol_uid,
            },
        )
        excerpts, evidence = [], []
        for row in rows:
            excerpts.append({"decision_id": row["uid"], "text": row.pop("text")})
            for s in row.pop("sources"):
                if s and s.get("uid"):
                    excerpts.append({"source_uid": s["uid"], "text": s["excerpt"]})
                    evidence.append({"source_uid": s["uid"], "uri": s["uri"]})
        return envelope(
            graph_revision=sha,
            status="ok" if rows else "unknown",
            items=rows,
            evidence=evidence,
            untrusted_source_excerpts=excerpts,
        )
