import os
from unittest.mock import Mock

import pytest
from fastmcp import Client
from test_integration import real as real  # noqa: PLC0414

from brain.config import Config
from brain.ingest.sync import sync
from brain.mcp_server import create_server
from brain.memory import Identity, Memory
from brain.services import Services
from brain.services.retrieval import RETRIEVAL_TOOLS, RepositoryRetrieval

live = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")


@live
@pytest.mark.asyncio
async def test_native_retrieval_and_reopened_history(real):
    sync(real)
    async with Client(create_server(Services(real))) as client:
        found = (await client.call_tool("search_code", {"query": "a"})).data
        assert found["status"] == "ok"
        assert any(row["symbol"] == "a" for row in found["items"])
        inventory = (await client.call_tool("repository_files", {"query": ".py"})).data
        assert '"x.py"' in inventory["checked_evidence"][0]["text"]
        read = (await client.call_tool("read_code", {"path": "x.py", "end": 3})).data
        proof = read["checked_evidence"][0]
        reopened = (await client.call_tool("resolve_evidence", {"evidence_id": proof["id"]})).data
        assert reopened["checked_evidence"] == [proof]
        history = (await client.call_tool("search_history", {"files": ["x.py"]})).data
        assert history["items"] and history["checked_evidence"]
        patches = [p for p in history["checked_evidence"] if p["kind"] == "history_diff"]
        assert patches
        for patch in patches:
            reopened = (await client.call_tool("resolve_evidence", {"evidence_id": patch["id"]})).data
            assert reopened["checked_evidence"] == [patch]
        source_uid = history["items"][0]["source_uid"]
        checked = (await client.call_tool("resolve_evidence", {"source_uid": source_uid})).data
        assert checked["checked_evidence"][0]["kind"] == "source"


@live
def test_citation_revocation_and_dirty_checkout_fail_closed(real):
    sync(real)
    tools = RepositoryRetrieval(real)
    inventory = tools.repository_files()["checked_evidence"][0]
    proof = tools.read_code("x.py")["checked_evidence"][0]
    real.query(
        "MATCH (p:Project {uid:$repo})-[r:CONTAINS]->(f:File {repo_id:$repo,path:'x.py'}) DELETE r",
        {"repo": real.cfg.repo_id},
    )
    changed = tools.resolve_evidence(evidence_id=inventory["id"])
    assert changed["status"] == "incomplete" and "checked_evidence" not in changed
    revoked = tools.resolve_evidence(evidence_id=proof["id"])
    assert revoked["status"] == "error" and "checked_evidence" not in revoked
    (real.cfg.repo_root / "x.py").write_text("secret = 'new unindexed data'\n")
    for result in (tools.search_code("secret"), tools.read_code("x.py"), tools.repository_files()):
        assert result["status"] == "error" and "checked_evidence" not in result
        assert "new unindexed data" not in str(result)
    assert tools.read_code("../outside.txt")["status"] == "error"


@live
def test_unknown_and_cross_repo_citations(real):
    sync(real)
    tools = RepositoryRetrieval(real)
    proof = tools.read_code("x.py")["checked_evidence"][0]
    fresh_process = RepositoryRetrieval(real)
    assert fresh_process.resolve_evidence(evidence_id=proof["id"])["status"] == "unknown"
    assert tools.resolve_evidence(evidence_id="../private")["status"] == "error"
    assert tools.resolve_evidence(source_uid="different-repo:source")["status"] == "error"
    assert tools.resolve_evidence(evidence_id=proof["id"], source_uid="also")["status"] == "error"


@pytest.mark.asyncio
async def test_every_retrieval_tool_checks_company_authorization(tmp_path):
    cfg = Config(tmp_path, "fixture", tenant_id="fixture", principal="alice")
    graph = Mock(cfg=cfg)
    memory = Memory(tmp_path / "memory.db", Identity("fixture", "alice"))
    arguments = {
        "search_code": {"query": "secret"}, "read_code": {"path": "secret.py"},
        "repository_files": {}, "search_history": {},
        "resolve_evidence": {"evidence_id": "a" * 24},
    }
    try:
        async with Client(create_server(Services(graph), memory)) as client:
            for name in RETRIEVAL_TOOLS:
                result = (await client.call_tool(name, arguments[name])).data
                assert result["warnings"] == ["scope_unavailable"]
                assert "checked_evidence" not in result
        graph.query.assert_not_called()
        graph.revision.assert_not_called()
    finally:
        memory.close()


def test_citation_descriptor_cache_is_bounded(tmp_path):
    tools = RepositoryRetrieval(Mock(cfg=Config(tmp_path, "fixture")))
    for index in range(130):
        tools._retain({
            "id": f"{index:024x}", "kind": "code", "ref": {"path": f"{index}.py"},
            "digest": "fixture", "revision": "fixture", "text": "SENSITIVE_SOURCE",
        })
    assert len(tools._citations) == 128
    assert "0" * 24 not in tools._citations
    assert "SENSITIVE_SOURCE" not in str(tools._citations)


@pytest.mark.asyncio
async def test_issued_citation_cannot_bypass_later_revocation(tmp_path, monkeypatch):
    cfg = Config(tmp_path, "fixture", tenant_id="fixture", principal="alice")
    memory = Memory(tmp_path / "memory.db", Identity("fixture", "alice"))
    proof = {
        "kind": "code", "ref": {"path": "x.py", "start": 1, "end": 1},
        "text": "sensitive source", "digest": "fixture", "revision": "fixture",
    }
    monkeypatch.setattr("brain.services.retrieval.code_evidence", lambda *_: proof)
    reopened = Mock(return_value=proof)
    monkeypatch.setattr("brain.services.retrieval.resolve", reopened)
    with memory.db:
        memory.db.execute("INSERT INTO grants VALUES(?,?,?,?)", ("fixture", "alice", "company", "reader"))
    try:
        async with Client(create_server(Services(Mock(cfg=cfg)), memory)) as client:
            issued = (await client.call_tool("read_code", {"path": "x.py"})).data
            evidence_id = issued["checked_evidence"][0]["id"]
            verified = (await client.call_tool("resolve_evidence", {"evidence_id": evidence_id})).data
            assert verified["status"] == "ok"
            reopened.reset_mock()
            with memory.db:
                memory.db.execute("DELETE FROM grants WHERE brain='company'")
            denied = (await client.call_tool("resolve_evidence", {"evidence_id": evidence_id})).data
            assert denied["warnings"] == ["scope_unavailable"]
            assert "sensitive source" not in str(denied)
            reopened.assert_not_called()
    finally:
        memory.close()
