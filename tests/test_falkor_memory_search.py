"""Native search must rank only eligible candidates and return real graph paths."""

import json
import os
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastmcp import Client
from test_integration import real as real  # noqa: PLC0414
from test_memory import accepted, grant, source
from test_memory import memory as memory  # noqa: PLC0414
from test_memory_company import bridge as bridge  # noqa: PLC0414
from test_memory_graph import live as live  # noqa: PLC0414

from brain.config import Config
from brain.graph import GraphStore, GraphUnavailable
from brain.mcp_server import create_server
from brain.memory import Identity, Memory
from brain.memory_graph import MemoryGraph
from brain.memory_ingest import share_memory
from brain.memory_links import MemoryLinks
from brain.memory_tools import MemoryTools
from brain.services import Services


def tools(memory, projection):
    return MemoryTools(memory, Mock(), projection)


def test_backend_selection_and_authorization_before_graph_io(memory, tmp_path):
    store = Mock(cfg=Config(tmp_path, "fixture", tenant_id="fixture", principal="alice"))
    extension = tools(memory, MemoryGraph(memory, store))
    denied = extension.memory_search("secret", ["private:bob"], backend="falkor")
    assert denied["warnings"] == ["scope_unavailable"]
    denied = extension.memory_search("secret", include_graph=True)
    assert denied["warnings"] == ["scope_unavailable"]
    store.memory_query.assert_not_called()
    accepted(memory, "upload rule", uid="baseline")
    assert extension.memory_search("upload", backend="catalog")["items"]
    store.memory_query.assert_not_called()
    assert tools(memory, None).memory_search("upload")["backend"] == "catalog"
    assert tools(memory, None).memory_search("upload", backend="falkor")["status"] == "unavailable"


def test_invalid_search_bounds_and_backend_fail_without_queries(memory, tmp_path):
    store = Mock(cfg=Config(tmp_path, "fixture", tenant_id="fixture", principal="alice"))
    extension = tools(memory, MemoryGraph(memory, store))
    for query, limit in (("", 1), ("x" * 1001, 1), ("x", 0), ("x", True)):
        assert extension.memory_search(query, limit=limit)["status"] == "error"
    assert extension.memory_search("x", backend="unknown")["status"] == "error"
    store.memory_query.assert_not_called()


def test_catalog_exact_fulltext_baseline_does_not_encode_with_model_configured(memory):
    accepted(memory, "upload baseline", uid="exact-baseline")
    memory.embedder = Mock()
    result = memory.search("exact-baseline", mode="exact_fulltext")
    assert result["items"][0]["uid"] == "exact-baseline"
    memory.embedder.encode.assert_not_called()


live_test = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")


@live_test
@pytest.mark.integration
def test_live_exact_fulltext_and_entity_paths_without_embedding_or_sql_search(live, monkeypatch):
    memory, _store, projection = live
    first = accepted(memory, "Preserve `upload` payload", uid="replay")
    accepted(memory, "Test `upload` under redirects", uid="tests")
    projection.sync("private:alice")
    memory.embedder = Mock()
    monkeypatch.setattr(
        memory, "search", Mock(side_effect=AssertionError("Catalog retrieval used"))
    )
    extension = tools(memory, projection)
    exact = extension.memory_search(first["uid"])
    assert exact["status"] == "ok", exact
    assert exact["backend"] == "falkor" and not exact["vector_enabled"]
    assert exact["items"][0]["uid"] == "replay"
    assert exact["items"][0]["graph_paths"][0]["path"]
    lexical = extension.memory_search("payload")
    assert lexical["status"] == "ok", lexical
    assert {i["uid"] for i in lexical["items"]} == {"replay", "tests"}
    associated = next(i for i in lexical["items"] if i["uid"] == "tests")
    assert "graph_expansion" in associated["retrieval_channels"]
    assert associated["graph_paths"][0]["relationships"] == ["MENTIONS", "MENTIONS"]
    assert all(not i["binding"] for i in lexical["items"])
    memory.embedder.encode.assert_not_called()
    memory.search.assert_not_called()
    unknown = extension.memory_search("zzzzirrelevant")
    assert unknown["status"] == "ok" and unknown["items"] == []


@live_test
@pytest.mark.integration
def test_live_hidden_drafts_expiry_and_other_scopes_cannot_change_ranking(live):
    memory, store, projection = live
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    grant(memory, "bob", brain, "reader")
    accepted(memory, "upload payload replay", brain, uid="public")
    projection.sync(brain)
    bob = Memory(store.cfg.memory_db, Identity(memory.identity.tenant, "bob"))
    try:
        bob_projection = MemoryGraph(bob, GraphStore(replace(store.cfg, principal="bob")))
        extension = tools(bob, bob_projection)
        before = extension.memory_search("upload", [brain], include_proposals=True)
        assert before["status"] == "ok", before
        for number in range(55):
            with memory.db:
                memory.put(
                    brain,
                    "upload " * 100 + "HIDDEN_DRAFT",
                    source("draft"),
                    uid="hidden-" + str(number),
                )
        expired = accepted(memory, "upload EXPIRED_MARKER", brain, uid="expired")
        memory.review(brain, expired["uid"], "expire", expired["hash"], "Fixture")
        accepted(memory, "upload PRIVATE_MARKER", uid="private")
        projection.sync(brain)
        projection.sync("private:alice")
        after = extension.memory_search("upload", [brain], include_proposals=True)
        assert after["status"] == "ok", after
        assert [(i["uid"], i["score"]) for i in after["items"]] == [
            (i["uid"], i["score"]) for i in before["items"]
        ]
        assert "HIDDEN_DRAFT" not in json.dumps(after) and "PRIVATE_MARKER" not in json.dumps(after)
        assert "EXPIRED_MARKER" not in json.dumps(after)
        with memory.db:
            memory.db.execute("DELETE FROM grants WHERE principal='bob'")
        assert extension.memory_search("upload", [brain])["warnings"] == ["scope_unavailable"]
    finally:
        bob.close()


@live_test
@pytest.mark.integration
def test_live_reviewed_update_expands_and_reports_original_without_suppressing_it(live):
    memory, _store, projection = live
    old = accepted(memory, "Original zebra rule", uid="old")
    new = accepted(memory, "Corrected preference", uid="new")
    links = MemoryLinks(memory)
    link = links.propose(
        "private:alice",
        new["uid"],
        new["hash"],
        "UPDATES",
        old["uid"],
        old["hash"],
        source("Corrected preference"),
    )
    links.review("private:alice", link["uid"], "accept", "proposed", "Fixture")
    projection.sync("private:alice")
    result = tools(memory, projection).memory_search("zebra")
    assert result["status"] == "ok", result
    items = {i["uid"]: i for i in result["items"]}
    assert set(items) == {"new", "old"}
    assert items["old"]["updated_by"] == ["new"]
    assert items["new"]["graph_paths"][0]["relationships"] == ["UPDATES"]
    links.review("private:alice", link["uid"], "rollback", "accepted", "Fixture")
    projection.sync("private:alice")
    result = tools(memory, projection).memory_search("zebra")
    assert [i["uid"] for i in result["items"]] == ["old"]


@live_test
@pytest.mark.integration
def test_live_cross_brain_sharing_path_requires_both_current_scopes(live):
    memory, _store, projection = live
    entry = accepted(memory, "Distinctive cobalt source", uid="private-entry")
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    shared = share_memory(memory, entry["uid"], entry["hash"], brain)
    memory.review(brain, shared["uid"], "accept", shared["hash"], "Fixture")
    projection.sync("private:alice")
    projection.sync(brain)
    result = tools(memory, projection).memory_search(entry["uid"], ["private:alice", brain])
    assert result["status"] == "ok", result
    team = next(i for i in result["items"] if i["brain"] == brain)
    assert team["graph_paths"][0]["relationships"] == [
        "SUPPORTED_BY",
        "SAME_CITATION",
        "SUPPORTED_BY",
    ]
    only_private = tools(memory, projection).memory_search(entry["uid"])
    assert {i["brain"] for i in only_private["items"]} == {"private:alice"}


@live_test
@pytest.mark.integration
def test_live_stale_deleted_backend_failure_and_content_mismatch_never_fall_back(live, monkeypatch):
    memory, store, projection = live
    accepted(memory, "upload marker", uid="stable")
    projection.sync("private:alice")
    extension = tools(memory, projection)
    store.memory_query("MATCH (n:MemoryNode {kind:'Memory'}) SET n.text='fabricated marker'")
    result = extension.memory_search("fabricated")
    assert result["status"] == "incomplete" and result["items"] == []
    projection.sync("private:alice")
    memory.delete("private:alice", "stable")
    result = extension.memory_search("upload")
    assert result["status"] == "incomplete" and not result["items"]
    projection.sync("private:alice")
    assert extension.memory_search("upload")["items"] == []
    monkeypatch.setattr(store, "memory_query", Mock(side_effect=GraphUnavailable("Synthetic")))
    memory.search = Mock(side_effect=AssertionError("Unsafe silent fallback"))
    assert extension.memory_search("upload")["status"] == "unavailable"
    memory.search.assert_not_called()


@live_test
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_native_mcp_search_returns_company_paths(bridge):
    memory, store, projection, citations, _src = bridge
    with memory.db:
        record = memory.put(
            "private:alice", "Remember the corporate upload guidance", citations, uid="note"
        )
    memory.review("private:alice", record["uid"], "accept", record["hash"], "Fixture")
    projection.sync("private:alice", include_company=True)
    symbol = store.query(
        "MATCH (s:Symbol {repo_id:$repo,qualname:'a',current:true}) RETURN s.uid AS uid",
        {"repo": store.cfg.repo_id},
    )[0]["uid"]
    async with Client(create_server(Services(store), memory)) as client:
        result = (
            await client.call_tool("memory_search", {"query": symbol, "include_graph": True})
        ).data
        assert result["status"] == "ok", result
        assert result["items"][0]["uid"] == "note"
        path = result["items"][0]["graph_paths"][0]
        assert "VERIFIED_SOURCE" in path["relationships"]
        assert any(n["kind"] == "CompanySymbol" for n in result["graph"]["nodes"])


@live_test
@pytest.mark.integration
def test_live_partial_index_repair_missing_index_and_literal_query_safety(live, monkeypatch):
    memory, store, projection = live
    accepted(memory, "upload rule", uid="safe")
    store.memory_query("CALL db.idx.fulltext.createNodeIndex('MemoryNode','text')")
    projection.sync("private:alice")
    assert projection.search_index_ready()
    extension = tools(memory, projection)
    assert extension.memory_search("upload")["status"] == "ok"
    count = store.memory_query("MATCH (n) RETURN count(n) AS n")
    literal = extension.memory_search("MATCH (n) DETACH DELETE n; * | @name:secret")
    assert literal["status"] == "ok", literal
    assert store.memory_query("MATCH (n) RETURN count(n) AS n") == count
    monkeypatch.setattr(projection, "search_index_ready", lambda: False)
    result = extension.memory_search("upload")
    assert result["status"] == "incomplete" and not result["items"]
    assert "memory_search_index_refresh_required" in result["warnings"]


@live_test
@pytest.mark.integration
def test_live_evidence_text_budget_and_truncation_are_explicit(live):
    memory, _store, projection = live
    accepted(memory, "upload " + "x" * 3000, uid="long")
    projection.sync("private:alice")
    result = tools(memory, projection).memory_search("upload")
    assert result["status"] == "ok", result
    item = result["items"][0]
    assert item["truncated"] and len(item["text"]) == 2000
    node = next(n for n in result["graph"]["nodes"] if n["uid"] == item["graph_uid"])
    assert node["truncated"] and node["original_chars"] == 3007 and len(node["text"]) == 1000
    assert sum(len(n.get("text", "")) for n in result["graph"]["nodes"]) <= 16000


@live_test
@pytest.mark.integration
def test_live_eligibility_change_during_search_discards_results(live, monkeypatch):
    memory, _store, projection = live
    accepted(memory, "upload expiring rule", uid="expires-during-query")
    projection.sync("private:alice")
    original = projection._rows
    calls = 0

    def expires(brain, proposals):
        nonlocal calls
        calls += 1
        return original(brain, proposals) if calls == 1 else []

    monkeypatch.setattr(projection, "_rows", expires)
    result = tools(memory, projection).memory_search("upload")
    assert result["status"] == "incomplete" and not result["items"]
    assert not result["graph"]["nodes"]
    assert "memory_eligibility_changed_retry" in result["warnings"]
