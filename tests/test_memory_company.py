"""Verified native company bridges; all graphs and source text are disposable."""

import json
import os
import subprocess
import uuid
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastmcp import Client
from test_integration import real as real  # noqa: PLC0414
from test_memory import grant
from test_memory import memory as memory  # noqa: PLC0414

from brain.config import Config
from brain.graph import GraphStore
from brain.ingest.documents import delete_documents, ingest_documents
from brain.ingest.sync import sync
from brain.mcp_server import create_server
from brain.memory import Identity, Memory, digest
from brain.memory_company import CompanyBridge
from brain.memory_graph import MemoryGraph
from brain.memory_tools import MemoryTools
from brain.services import Services


def put(memory, text, sources, brain="private:alice", uid="example"):
    with memory.db:
        result = memory.put(brain, text, sources, uid)
    memory.review(brain, uid, "accept", result["hash"], "Synthetic company bridge review")
    return result


def test_company_access_checked_before_any_graph_io(memory, tmp_path):
    store = Mock(cfg=Config(tmp_path, "fixture", tenant_id="fixture", principal="alice"))
    projection = MemoryGraph(memory, store)
    tools = MemoryTools(memory, Mock(), projection)
    assert tools.memory_graph(include_company=True)["warnings"] == ["scope_unavailable"]
    with pytest.raises(PermissionError):
        projection.sync("private:alice", include_company=True)
    store.memory_query.assert_not_called()
    store.revision.assert_not_called()
    store.query.assert_not_called()


def test_bridge_refuses_mismatched_tenant_or_principal(memory, tmp_path):
    for tenant, principal in (("other", "alice"), ("fixture", "bob")):
        store = Mock(cfg=Config(tmp_path, "fixture", tenant_id=tenant, principal=principal))
        with pytest.raises(ValueError, match="identities must match"):
            CompanyBridge(memory, store)
        store.query.assert_not_called()


@pytest.fixture
def bridge(real):
    root = real.cfg.repo_root
    text = "# Uploads\nUse `x.a` to preserve café payloads.\n"
    (root / "guide.md").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "guide.md"], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-m",
            "Synthetic guide",
        ],
        check=True,
        capture_output=True,
    )
    cfg = replace(
        real.cfg,
        tenant_id="fixture_" + uuid.uuid4().hex,
        principal="alice",
        memory_db=str(root / ".git" / "memory.db"),
        memory_graph_enabled=True,
    )
    store = GraphStore(cfg)
    sync(store)
    ingest_documents(store, ["guide.md"])
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, "alice"))
    grant(memory, "alice", "company", "reader")
    src = store.query(
        "MATCH (d:Document {repo_id:$repo,current:true})-[:SUPPORTS]->(s:Source) "
        "RETURN s.uid AS uid, s.uri AS uri, s.excerpt AS text LIMIT 1",
        {"repo": cfg.repo_id},
    )[0]
    citation = [{"uri": src["uri"], "digest": digest(src["text"])}]
    yield memory, store, MemoryGraph(memory, store), citation, src
    memory.close()
    if store.db:
        prefix = cfg.graph_name("org").removesuffix("org_demo")
        for name in (cfg.graph_name("org"), prefix + "memory"):
            if name in store.db.list_graphs():
                store.db.select_graph(name).delete()


live_test = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")


@live_test
@pytest.mark.integration
def test_live_verified_sources_document_paths_and_exact_lexical_symbols(bridge):
    memory, store, projection, citation, src = bridge
    put(memory, "Preserve `x.a` and `x.py::a` uploads.", citation)
    before = store.query("MATCH (n) RETURN count(n) AS n")
    projection.sync("private:alice", include_company=True)
    assert store.query("MATCH (n) RETURN count(n) AS n") == before
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "ok", view
    assert {"CompanySource", "CompanyDocument", "CompanyFile", "CompanySymbol"} <= {
        n["kind"] for n in view["nodes"]
    }
    assert {"VERIFIED_SOURCE", "RESOLVES_TO", "DECLARES", "SUPPORTS"} <= {
        e["relation"] for e in view["edges"]
    }
    assert any(n.get("company_uid") == src["uid"] for n in view["nodes"])
    assert len([e for e in view["edges"] if e["relation"] == "RESOLVES_TO"]) == 2
    assert len([n for n in view["nodes"] if n["kind"] == "CompanySymbol"]) == 1
    assert not view["binding"]
    base = projection.read(["private:alice"])
    assert base["status"] == "ok", base
    assert not any(n["kind"].startswith("Company") for n in base["nodes"])
    assert "café" not in json.dumps(base)


@live_test
@pytest.mark.integration
def test_live_digest_mismatch_bare_unknown_and_ambiguous_names_remain_unresolved(bridge):
    memory, store, projection, citation, _src = bridge
    sha = store.revision()["sha"]
    store.upsert(
        "File",
        f"{store.cfg.repo_id}@{sha}:x/__init__.py",
        {
            "repo_id": store.cfg.repo_id,
            "revision": sha,
            "current": True,
            "path": "x/__init__.py",
        },
    )
    store.upsert(
        "Source",
        "foreign-source",
        {
            "repo_id": "foreign:repository",
            "uri": citation[0]["uri"],
            "excerpt": "different source version",
        },
    )
    put(
        memory,
        "Use `a`, `x.a`, or `nonexistent.method`.",
        [{"uri": citation[0]["uri"], "digest": digest("different source version")}],
    )
    projection.sync("private:alice", include_company=True)
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "ok", view
    assert len(view["unresolved_company_references"]) == 4
    assert not any(n["kind"].startswith("Company") for n in view["nodes"])
    assert "café" not in json.dumps(view)
    assert not any(e["relation"] in {"RESOLVES_TO", "VERIFIED_SOURCE"} for e in view["edges"])


@live_test
@pytest.mark.integration
def test_live_duplicate_source_versions_are_not_silently_coalesced(bridge):
    memory, store, projection, citation, src = bridge
    store.upsert(
        "Source",
        src["uid"] + ":duplicate",
        {
            "repo_id": store.cfg.repo_id,
            "uri": src["uri"],
            "excerpt": src["text"],
        },
    )
    put(memory, "Preserve uploads.", citation)
    store.upsert("Source", "missing-excerpt", {"repo_id": store.cfg.repo_id, "uri": "urn:missing"})
    put(
        memory,
        "Missing evidence must remain unresolved.",
        [{"uri": "urn:missing", "digest": digest("")}],
        uid="missing",
    )
    projection.sync("private:alice", include_company=True)
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "ok", view
    assert len(view["unresolved_company_references"]) == 2
    assert not any(n["kind"].startswith("Company") for n in view["nodes"])


@live_test
@pytest.mark.integration
def test_live_company_revocation_and_plain_views_never_query_company(bridge, monkeypatch):
    memory, store, projection, citation, _src = bridge
    put(memory, "Use `x.a`", citation)
    projection.sync("private:alice", include_company=True)
    with memory.db:
        memory.db.execute("DELETE FROM grants WHERE brain='company'")
    forbidden = Mock(side_effect=AssertionError("Unexpected company graph read"))
    monkeypatch.setattr(store, "query", forbidden)
    monkeypatch.setattr(store, "revision", forbidden)
    assert projection.read(["private:alice"])["status"] == "ok"
    tools = MemoryTools(memory, Mock(), projection)
    assert tools.memory_graph(include_company=True)["warnings"] == ["scope_unavailable"]
    forbidden.assert_not_called()


@live_test
@pytest.mark.integration
def test_live_missing_projection_changed_revision_and_incomplete_sync_fail_closed(bridge):
    memory, store, projection, citation, _src = bridge
    put(memory, "Use `x.a`", citation)
    projection.sync("private:alice")
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "incomplete" and not view["nodes"]
    projection.sync("private:alice", include_company=True)
    store.query(
        "MATCH (p:Project {uid:$repo}) SET p.last_completed_sync_sha=$sha",
        {"repo": store.cfg.repo_id, "sha": "f" * 40},
    )
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "incomplete" and not view["nodes"]
    store.query("MATCH (p:Project {uid:$repo}) SET p.syncing=true", {"repo": store.cfg.repo_id})
    tools = MemoryTools(memory, Mock(), projection)
    assert tools.memory_graph(include_company=True)["status"] == "unavailable"
    assert projection.read(["private:alice"])["status"] == "ok"


@live_test
@pytest.mark.integration
def test_live_retired_documents_and_replaced_source_bytes_are_not_returned(bridge):
    memory, store, projection, citation, src = bridge
    put(memory, "Use `x.a`", citation)
    projection.sync("private:alice", include_company=True)
    delete_documents(store, ["guide.md"])
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "ok", view
    assert not any(n["kind"] == "CompanyDocument" for n in view["nodes"])
    store.query(
        "MATCH (s:Source {uid:$uid}) SET s.excerpt='Replaced source bytes'", {"uid": src["uid"]}
    )
    view = projection.read(["private:alice"], include_company=True)
    assert view["status"] == "ok", view
    assert not any(n["kind"] in {"CompanySource", "CompanyDocument"} for n in view["nodes"])
    assert not any(e["relation"] == "VERIFIED_SOURCE" for e in view["edges"])


@live_test
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_mcp_company_join_and_team_member_gate(bridge):
    memory, store, projection, citation, _src = bridge
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    grant(memory, "bob", brain, "reader")
    put(memory, "Use `x.a`", citation, brain)
    projection.sync(brain, include_company=True)
    async with Client(create_server(Services(store), memory)) as client:
        data = (
            await client.call_tool("memory_graph", {"brains": [brain], "include_company": True})
        ).data
        assert data["status"] == "ok", data
        assert any(e["relation"] == "VERIFIED_SOURCE" for e in data["edges"])
    bob = Memory(store.cfg.memory_db, Identity(memory.identity.tenant, "bob"))
    try:
        graph = MemoryGraph(bob, GraphStore(replace(store.cfg, principal="bob")))
        assert graph.read([brain])["status"] == "ok"
        with pytest.raises(PermissionError):
            graph.read([brain], include_company=True)
    finally:
        bob.close()
