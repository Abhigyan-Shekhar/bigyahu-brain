"""Inventory provenance and per-pass resolution cost/freshness regressions."""

from types import SimpleNamespace

import pytest

from brain.app import evidence
from brain.memory import canonical, digest


def test_inventory_is_citable_bounded_and_rechecked(tmp_path, monkeypatch):
    paths = [f"migrations/{i:03}.sql" for i in range(201)]
    queries = []
    store = SimpleNamespace(cfg=SimpleNamespace(repo_id="fixture"))
    monkeypatch.setattr(evidence, "ready", lambda *_: "sha")
    monkeypatch.setattr(evidence, "native_graph", lambda *_: {"nodes": [], "edges": []})

    def query(cypher, params):
        queries.append((cypher, params))
        return [{"path": p} for p in paths]

    store.query = query
    proof = evidence.repository_files_evidence(store, "migration")
    assert '"truncated":true' in proof["text"]
    assert "not a search of file contents" in proof["text"]
    assert "200.sql" not in proof["text"]
    assert queries[0][1] == {"repo": "fixture", "sha": "sha", "q": "migration"}
    assert "LIMIT 201" in queries[0][0]
    saved = evidence.register(tmp_path, proof)
    output = {
        "claims": [
            {
                "text": "Migration paths were found",
                "support": [{"evidence_id": saved["id"], "quote": "migrations/000.sql"}],
            }
        ]
    }
    assert evidence.verified_claims(store, tmp_path, output)
    paths.pop()
    with pytest.raises(ValueError, match="Evidence changed"):
        evidence.verified_claims(store, tmp_path, output)


def test_shared_evidence_resolves_once_per_pass_and_rechecks_after_revocation(
    tmp_path, monkeypatch
):
    proof = {
        "kind": "memory",
        "ref": {},
        "text": "Preserve validation",
        "title": "Fixture",
        "digest": digest("Preserve validation"),
        "revision": "sha",
        "graph": {"nodes": [], "edges": []},
    }
    saved = evidence.register(tmp_path, proof)
    calls = []

    def resolve(*_):
        calls.append(1)
        return proof

    monkeypatch.setattr(evidence, "resolve", resolve)
    output = {
        "claims": [
            {
                "text": f"Claim {i}",
                "support": [{"evidence_id": saved["id"], "quote": "Preserve validation"}],
            }
            for i in range(20)
        ]
    }
    result = evidence.verified_claims(None, tmp_path, output)
    assert len(calls) == 1 and len(result) == 20
    assert "Preserve validation" in canonical(result)

    def revoked(*_):
        raise PermissionError("Memory revoked")

    monkeypatch.setattr(evidence, "resolve", revoked)
    with pytest.raises(PermissionError, match="revoked"):
        evidence.verified_claims(None, tmp_path, output)


def test_inventory_bounds_long_unicode_paths_without_claiming_complete_coverage(monkeypatch):
    store = SimpleNamespace(
        cfg=SimpleNamespace(repo_id="fixture"),
        query=lambda *_: [{"path": "schema/" + "文" * 180 + str(i) + ".sql"} for i in range(200)],
    )
    monkeypatch.setattr(evidence, "ready", lambda *_: "sha")
    monkeypatch.setattr(evidence, "native_graph", lambda *_: {"nodes": [], "edges": []})
    proof = evidence.repository_files_evidence(store)
    assert len(proof["text"].encode("utf-8")) < 12000
    assert '"truncated":true' in proof["text"]
