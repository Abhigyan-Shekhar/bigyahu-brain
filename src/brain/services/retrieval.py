"""Shared read-only repository retrieval, without application session state.

The existing pure provenance/history engines remain the source of truth for
byte checks. The application optionally persists evidence; standalone MCP keeps
only bounded, process-local citation descriptors and rechecks them on every read.
"""

import re
from collections import OrderedDict
from copy import deepcopy
from threading import RLock

from ..app.evidence import (
    code_evidence,
    ready,
    register,
    repository_files_evidence,
    resolve,
    source_evidence,
)
from ..app.history import search
from ..memory import canonical, digest
from .core import envelope, operation

RETRIEVAL_TOOLS = (
    "search_code", "read_code", "repository_files", "search_history", "resolve_evidence",
)


class RepositoryRetrieval:
    def __init__(self, store, folder=None):
        self.store, self.cfg, self.folder = store, store.cfg, folder
        self._citations = OrderedDict()
        self._lock = RLock()

    def _retain(self, proof):
        # Store descriptors, not trusted cached source text. Topology changes
        # also invalidate a reopened citation even if its quoted bytes match.
        original = {k: v for k, v in proof.items() if k != "id"}
        descriptor = {
            "kind": proof["kind"], "ref": deepcopy(proof["ref"]),
            "fingerprint": digest(canonical(original)),
        }
        with self._lock:
            self._citations[proof["id"]] = descriptor
            self._citations.move_to_end(proof["id"])
            while len(self._citations) > 128:
                self._citations.popitem(last=False)
        return proof

    def _register(self, proof):
        return self._retain(register(self.folder, proof))

    def add_evidence(self, result):
        """Enrich public graph results with independently checked sources."""
        checked = []
        for source in result.get("untrusted_source_excerpts", []):
            if source.get("source_uid"):
                try:
                    checked.append(self._register(source_evidence(self.store, source["source_uid"])))
                except (ValueError, OSError, UnicodeError):
                    pass
        result["checked_evidence"] = checked
        return result

    @operation
    def search_code(self, query: str) -> dict:
        """Find current indexed file paths and Python symbols by literal substring."""
        if not 1 <= len(query) <= 100:
            raise ValueError("Use a 1–100 character substring")
        sha = ready(self.store)
        rows = self.store.query(
            "MATCH (n {repo_id:$repo,current:true,revision:$sha}) "
            "WHERE (n:File OR n:Symbol) AND "
            "(toLower(coalesce(n.path,'')) CONTAINS toLower($q) OR "
            "toLower(coalesce(n.qualname,'')) CONTAINS toLower($q)) "
            "RETURN n.uid AS uid,n.path AS path,n.qualname AS symbol,"
            "n.lineno AS start,n.end_lineno AS end ORDER BY path,symbol LIMIT 21",
            {"repo": self.cfg.repo_id, "sha": sha, "q": query},
        )
        return envelope(graph_revision=sha, items=rows[:20], truncated=len(rows) > 20)

    @operation
    def read_code(self, path: str, start: int = 1, end: int = 80) -> dict:
        """Read at most 120 lines checked against indexed file bytes and revision."""
        proof = code_evidence(self.store, path, start, end)
        return envelope(graph_revision=proof["revision"], checked_evidence=[self._register(proof)])

    @operation
    def repository_files(self, query: str = "") -> dict:
        """Return a citable bounded path inventory; this does not search contents."""
        proof = repository_files_evidence(self.store, query)
        return envelope(graph_revision=proof["revision"], checked_evidence=[self._register(proof)])

    @operation
    def search_history(
        self, query: str = "", files: list[str] | None = None, symbols: list[str] | None = None
    ) -> dict:
        """Rank indexed history and return verified messages/patches with coverage gaps."""
        result = search(self.store, self.folder, query, files, symbols)
        for proof in result.get("checked_evidence", []):
            self._retain(proof)
        return result

    @operation
    def resolve_evidence(self, evidence_id: str = "", source_uid: str = "") -> dict:
        """Recheck an issued citation, or verify an org source UID from graph retrieval.

        Supply exactly one input. Citation IDs last for this server process; after
        reconnecting, retrieve again. Changed or evicted citations return no text.
        """
        if bool(evidence_id) == bool(source_uid):
            raise ValueError("Supply exactly one evidence_id or source_uid")
        if source_uid:
            if len(source_uid) > 1000:
                raise ValueError("Source UID exceeds bound")
            proof = source_evidence(self.store, source_uid)
        else:
            if not re.fullmatch(r"[a-f0-9]{24}", evidence_id):
                raise ValueError("Invalid evidence ID")
            with self._lock:
                descriptor = deepcopy(self._citations.get(evidence_id))
            if descriptor is None:
                return envelope(status="unknown", warnings=["citation_unknown_or_expired"])
            proof = resolve(self.store, descriptor)
            if digest(canonical(proof)) != descriptor["fingerprint"]:
                return envelope(status="incomplete", warnings=["citation_changed_retrieve_again"])
        return envelope(
            graph_revision=proof["revision"], checked_evidence=[self._register(proof)],
        )
