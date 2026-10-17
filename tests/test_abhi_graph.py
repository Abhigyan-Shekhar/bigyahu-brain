"""Portable graph round trips preserve selected topology and destination review."""

import copy
import json
import os
import stat
import uuid
from dataclasses import replace

import pytest
from test_integration import real as real  # noqa: PLC0414
from test_memory import accepted, grant, source
from test_memory import memory as memory  # noqa: PLC0414

from brain.abhi_graph import export_graph, seal, validate, write_graph
from brain.graph import GraphStore
from brain.memory import Identity, Memory, digest
from brain.memory_graph import MemoryGraph
from brain.memory_ingest import import_abhi, read_json


@pytest.fixture
def bundle(memory):
    first = accepted(memory, "Preserve `upload` payloads.", uid="first")
    second = accepted(memory, "Test `upload` with `rewind`.", uid="second")
    accepted(memory, "UNSELECTED_PRIVATE_SENTINEL `upload`", uid="secret")
    grant(memory, "alice", "team:backend", "reviewer")
    return export_graph(
        memory,
        "private:alice",
        {
            first["uid"]: first["hash"],
            second["uid"]: second["hash"],
        },
        "backend",
        "roundtrip",
    )


def reseal(payload):
    return seal({k: v for k, v in payload.items() if k != "digest"})


def review_imports(memory, brain="team:backend"):
    records = memory.db.execute(
        "SELECT uid,hash FROM records WHERE tenant=? AND brain=?",
        (memory.identity.tenant, brain),
    ).fetchall()
    for row in records:
        memory.review(brain, row["uid"], "accept", row["hash"], "Synthetic round-trip review")
    return dict(records)


def test_roundtrip_selected_topology_and_proposal_boundary(memory, bundle, tmp_path):
    assert "UNSELECTED_PRIVATE_SENTINEL" not in json.dumps(bundle)
    assert {n["kind"] for n in bundle["graph"]["nodes"]} == {"Memory", "Source", "Entity"}
    assert "private:alice" not in json.dumps(bundle)
    assert len([e for e in bundle["graph"]["edges"] if e["relation"] == "MENTIONS"]) == 3
    destination = Memory(tmp_path / "destination.db", Identity("fixture", "bob"))
    try:
        grant(destination, "bob", "team:backend", "reviewer")
        result = import_abhi(destination, bundle)
        assert result["state"] == "proposed" and not result["binding"]
        assert result["digest"] == bundle["digest"]
        assert import_abhi(destination, bundle)["unchanged"]
        assert not destination.search("upload", ["team:backend"])["items"]
        chosen = review_imports(destination)
        reexport = export_graph(destination, "team:backend", chosen, "backend", "roundtrip")
        assert reexport == bundle
        assert destination.db.execute("SELECT count(*) FROM grants").fetchone()[0] == 1
        assert not destination.db.execute(
            "SELECT * FROM records WHERE brain LIKE 'private:%'"
        ).fetchall()
    finally:
        destination.close()


def test_export_requires_exact_current_accepted_selection(memory):
    item = memory.propose("Do not share a pending `upload` note", source("pending"))
    with pytest.raises(ValueError, match="accepted"):
        export_graph(memory, "private:alice", {item["uid"]: item["hash"]}, "backend", "sample")
    item = accepted(memory, "Selected `upload`", uid="selected")
    with pytest.raises(ValueError, match="exact"):
        export_graph(memory, "private:alice", {item["uid"]: "wrong"}, "backend", "sample")
    with pytest.raises(PermissionError):
        export_graph(memory, "private:bob", {item["uid"]: item["hash"]}, "backend", "sample")
    memory.review("private:alice", item["uid"], "expire", item["hash"], "Retention complete")
    with pytest.raises(ValueError, match="accepted"):
        export_graph(memory, "private:alice", {item["uid"]: item["hash"]}, "backend", "sample")


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_node",
        "duplicate_edge",
        "missing_node",
        "dangling_edge",
        "invented_edge",
        "hidden_node",
        "approval",
        "top_level_acl",
        "record_acl",
        "citation_mismatch",
    ],
)
def test_resealed_hostile_topology_is_rejected_atomically(memory, bundle, mutation):
    hostile = copy.deepcopy(bundle)
    graph = hostile["graph"]
    if mutation == "duplicate_node":
        graph["nodes"].append(copy.deepcopy(graph["nodes"][0]))
    elif mutation == "duplicate_edge":
        graph["edges"].append(copy.deepcopy(graph["edges"][0]))
    elif mutation == "missing_node":
        graph["nodes"].pop()
    elif mutation == "dangling_edge":
        graph["edges"][0]["target"] = "missing"
    elif mutation == "invented_edge":
        graph["edges"][0]["relation"] = "CONSTRAINS"
    elif mutation == "hidden_node":
        graph["nodes"].append({"id": "hidden", "kind": "Person", "name": "secret"})
    elif mutation == "approval":
        graph["nodes"][0]["approval"] = "active"
    elif mutation == "top_level_acl":
        hostile["role"] = "reviewer"
    elif mutation == "record_acl":
        hostile["records"][0]["state"] = "accepted"
    elif mutation == "citation_mismatch":
        hostile["records"][0]["sources"][0]["digest"] = digest("different bytes")
    with pytest.raises(ValueError):
        import_abhi(memory, reseal(hostile))
    assert not memory.db.execute("SELECT * FROM records WHERE brain='team:backend'").fetchall()
    assert not memory.db.execute("SELECT * FROM imports").fetchall()


def test_integrity_acl_tenant_and_size_bounds(memory, bundle, tmp_path):
    bad = copy.deepcopy(bundle)
    bad["records"][0]["text"] = "Changed source text"
    with pytest.raises(ValueError, match="integrity"):
        import_abhi(memory, bad)
    with memory.db:
        memory.db.execute("DELETE FROM grants")
    with pytest.raises(PermissionError):
        import_abhi(memory, bundle)
    grant(memory, "alice", "team:backend", "reader")
    with pytest.raises(PermissionError):
        import_abhi(memory, bundle)
    grant(memory, "alice", "team:backend", "reviewer")
    foreign = copy.deepcopy(bundle)
    foreign["tenant"] = "foreign"
    with pytest.raises(PermissionError):
        import_abhi(memory, reseal(foreign))
    large = copy.deepcopy(bundle)
    large["graph"]["padding"] = "x" * 1_000_000
    with pytest.raises(ValueError, match="1 MB"):
        validate(reseal(large))
    path = tmp_path / "duplicate.abhi"
    path.write_text('{"format":"abhi/2","format":"abhi/1"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_json(path)


def test_updates_require_parent_and_per_record_hash_with_atomic_rollback(memory, bundle):
    first = import_abhi(memory, bundle)
    chosen = review_imports(memory)
    changed = copy.deepcopy(bundle)
    changed["parent_digest"] = first["digest"]
    for record in changed["records"]:
        uid = "abhi:roundtrip:" + record["id"]
        record["expected_hash"] = chosen[uid]
        # Preserve code mentions so portable topology need not change.
        record["text"] += " Revised requirement."
    changed["records"][-1]["expected_hash"] = "0" * 64
    with pytest.raises(ValueError, match="revision conflict"):
        import_abhi(memory, reseal(changed))
    assert memory.db.execute("SELECT hash FROM imports").fetchone()[0] == first["digest"]
    assert all(
        row[0] == "accepted"
        for row in memory.db.execute("SELECT state FROM records WHERE brain='team:backend'")
    )
    record = changed["records"][-1]
    record["expected_hash"] = chosen["abhi:roundtrip:" + record["id"]]
    result = import_abhi(memory, reseal(changed))
    assert result["state"] == "proposed"
    assert not memory.search("upload", ["team:backend"])["items"]
    stale = copy.deepcopy(changed)
    stale["parent_digest"] = first["digest"]
    stale["records"][0]["text"] += " Yet another edit."
    with pytest.raises(ValueError, match="Collection conflict"):
        import_abhi(memory, reseal(stale))


def test_export_file_is_private_never_overwrites_or_follows_symlink(bundle, tmp_path):
    path = tmp_path / "graph.abhi"
    write_graph(path, bundle)
    assert read_json(path) == bundle
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_graph(path, bundle)
    if os.name != "nt":
        link = tmp_path / "link.abhi"
        link.symlink_to(path)
        with pytest.raises(FileExistsError):
            write_graph(link, bundle)
        with pytest.raises(ValueError, match="regular"):
            read_json(link)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_live_import_reconstructs_exported_edges_after_review(real, memory, bundle, tmp_path):
    cfg = replace(
        real.cfg,
        tenant_id="fixture_" + uuid.uuid4().hex,
        principal="bob",
        memory_db=str(tmp_path / "live-import.db"),
        memory_graph_enabled=True,
    )
    # The exported tenant is an explicit namespace binding, not an identity grant.
    payload = copy.deepcopy(bundle)
    payload["tenant"] = cfg.tenant_id
    payload = reseal(payload)
    destination = Memory(cfg.memory_db, Identity(cfg.tenant_id, "bob"))
    store = GraphStore(cfg)
    projection = MemoryGraph(destination, store)
    try:
        grant(destination, "bob", "team:backend", "reviewer")
        import_abhi(destination, payload)
        projection.sync("team:backend")
        view = projection.read(["team:backend"])
        assert not any(n["kind"] == "Memory" for n in view["nodes"])
        chosen = review_imports(destination)
        assert projection.read(["team:backend"])["status"] == "incomplete"
        projection.sync("team:backend")
        view = projection.read(["team:backend"])
        assert view["status"] == "ok", view
        native = {n["uid"]: n for n in view["nodes"]}

        def normalize_node(uid):
            node = native[uid]
            if node["kind"] == "Memory":
                return node["record_uid"].split(":")[-1]
            if node["kind"] == "Source":
                from brain.memory import canonical

                return "s-" + digest(canonical({k: node[k] for k in ("uri", "digest")}))
            return "e-" + digest(node["name"])

        actual = sorted(
            (normalize_node(e["source"]), e["relation"], normalize_node(e["target"]))
            for e in view["edges"]
            if e["relation"] in {"SUPPORTED_BY", "MENTIONS"}
        )
        expected = sorted(
            (e["source"], e["relation"], e["target"]) for e in payload["graph"]["edges"]
        )
        assert actual == expected
        assert export_graph(destination, "team:backend", chosen, "backend", "roundtrip") == payload
        assert "UNSELECTED_PRIVATE_SENTINEL" not in json.dumps(view)
    finally:
        destination.close()
        if store.db:
            name = cfg.graph_name("org").removesuffix("org_demo") + "memory"
            if name in store.db.list_graphs():
                store.db.select_graph(name).delete()
