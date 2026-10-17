"""Relationship review, source versions, privacy, migration and portable topology."""

import copy
import json
import os
import sqlite3
import uuid
from dataclasses import replace

import pytest
from test_integration import real as real  # noqa: PLC0414
from test_memory import accepted, grant, source
from test_memory import memory as memory  # noqa: PLC0414

from brain.abhi_graph import export_graph, seal, topology
from brain.graph import GraphStore
from brain.memory import Identity, Memory
from brain.memory_graph import MemoryGraph
from brain.memory_ingest import import_abhi
from brain.memory_links import MemoryLinks


def pair(memory, brain="private:alice"):
    a = accepted(memory, "New `upload` behavior", brain, uid="new")
    b = accepted(memory, "Old `upload` behavior", brain, uid="old")
    return a, b


def proposal(memory, a, b, relation="UPDATES", brain="private:alice"):
    return MemoryLinks(memory).propose(
        brain, a["uid"], a["hash"], relation, b["uid"], b["hash"], source("New `upload` behavior")
    )


def visible(memory, brain="private:alice", include_proposals=False):
    with memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        records = memory.db.execute(
            "SELECT * FROM records WHERE tenant=? AND brain=? AND state IN ('accepted','proposed')",
            (memory.identity.tenant, brain),
        ).fetchall()
        return MemoryLinks(memory).visible(brain, records, include_proposals)


def test_relationship_review_is_separate_immutable_and_revocable(memory):
    a, b = pair(memory)
    links = MemoryLinks(memory)
    item = proposal(memory, a, b)
    assert item == proposal(memory, a, b)
    assert item["state"] == "proposed" and not item["binding"]
    assert not visible(memory)
    assert visible(memory, include_proposals=True)[0]["uid"] == item["uid"]
    links.review("private:alice", item["uid"], "accept", "proposed", "Checked exact sources")
    assert visible(memory)[0]["state"] == "accepted"
    with pytest.raises(ValueError, match="conflict"):
        links.review("private:alice", item["uid"], "reject", "proposed", "Stale review")
    links.review("private:alice", item["uid"], "rollback", "accepted", "Reconsider assertion")
    assert not visible(memory)
    links.review("private:alice", item["uid"], "reject", "proposed", "Unsupported inference")
    assert not visible(memory, include_proposals=True)
    # No older memory is silently erased or hidden by UPDATES.
    assert len(memory.search("upload")["items"]) == 2


def test_accept_requires_reviewed_exact_current_endpoints(memory):
    a, b = pair(memory)
    memory.review("private:alice", a["uid"], "rollback", a["hash"], "Review again")
    item = proposal(memory, a, b)
    links = MemoryLinks(memory)
    with pytest.raises(ValueError, match="Accept the exact"):
        links.review("private:alice", item["uid"], "accept", "proposed", "Attempt")
    memory.review("private:alice", a["uid"], "accept", a["hash"], "Checked")
    links.review("private:alice", item["uid"], "accept", "proposed", "Checked")
    with memory.db:
        memory.put("private:alice", "Changed `upload`", source("changed"), a["uid"], a["hash"])
    assert not visible(memory, include_proposals=True)
    with pytest.raises(ValueError, match="changed"):
        links.review("private:alice", item["uid"], "accept", "accepted", "Stale endpoints")


@pytest.mark.parametrize("kind", ["self", "wrong_hash", "invented_relation", "invented_evidence"])
def test_invalid_links_do_not_write(memory, kind):
    a, b = pair(memory)
    args = [
        "private:alice",
        a["uid"],
        a["hash"],
        "UPDATES",
        b["uid"],
        b["hash"],
        source("New `upload` behavior"),
    ]
    if kind == "self":
        args[4:6] = args[1:3]
    elif kind == "wrong_hash":
        args[2] = "0" * 64
    elif kind == "invented_relation":
        args[3] = "CONSTRAINS"
    else:
        args[-1] = source("not an endpoint source")
    with pytest.raises(ValueError):
        MemoryLinks(memory).propose(*args)
    assert memory.db.execute("SELECT count(*) FROM memory_links").fetchone()[0] == 0


def test_member_visibility_and_review_permissions(memory, tmp_path):
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    a, b = pair(memory, brain)
    item = proposal(memory, a, b, brain=brain)
    bob = Memory(tmp_path / "fixture.db", Identity("fixture", "bob"))
    try:
        for role in ("reader", "writer"):
            grant(memory, "bob", brain, role)
            assert not visible(bob, brain, True)
            with pytest.raises(PermissionError):
                MemoryLinks(bob).review(brain, item["uid"], "accept", "proposed", "Unauthorized")
        grant(memory, "bob", brain, "reviewer")
        assert visible(bob, brain, True)
        MemoryLinks(memory).review(brain, item["uid"], "accept", "proposed", "Checked")
        grant(memory, "bob", brain, "reader")
        assert visible(bob, brain)
        with memory.db:
            memory.db.execute("DELETE FROM grants WHERE principal='bob'")
        with pytest.raises(PermissionError):
            visible(bob, brain)
    finally:
        bob.close()


def test_suggestions_are_bounded_deterministic_proposals_not_updates(memory):
    a, b = pair(memory)
    unrelated = accepted(memory, "Use `pool`", uid="unrelated")
    links = MemoryLinks(memory)
    result = links.suggest("private:alice", {r["uid"]: r["hash"] for r in (a, b, unrelated)})
    assert len(result["items"]) == 1
    assert result["items"][0]["state"] == "proposed"
    assert visible(memory, include_proposals=True)[0]["relation"] == "RELATES_TO"
    assert (
        links.suggest("private:alice", {r["uid"]: r["hash"] for r in (a, b, unrelated)}) == result
    )
    assert not visible(memory)


def test_version_one_migration_and_backup_preserve_records_and_links(memory, tmp_path):
    a, b = pair(memory)
    with memory.db:
        memory.db.execute("DROP TABLE memory_links")
        memory.db.execute("PRAGMA user_version=1")
    path = tmp_path / "fixture.db"
    memory.close()
    migrated = Memory(path, Identity("fixture", "alice"))
    try:
        assert migrated.health()["schema"] == 2
        assert len(migrated.search("upload")["items"]) == 2
        item = proposal(migrated, a, b)
        backup = tmp_path / "backup.db"
        migrated.backup(backup)
        restored = Memory(backup, Identity("fixture", "alice"))
        try:
            assert visible(restored, include_proposals=True)[0]["uid"] == item["uid"]
        finally:
            restored.close()
    finally:
        # Restore fixture ownership so its teardown remains valid.
        migrated.close()
        memory.db = sqlite3.connect(path)


def test_endpoint_deletion_erases_relationships_and_their_audit_details(memory):
    a, b = pair(memory)
    item = proposal(memory, a, b)
    memory.delete("private:alice", b["uid"])
    assert not memory.db.execute("SELECT * FROM memory_links").fetchall()
    assert all(
        row[0] == ""
        for row in memory.db.execute("SELECT detail FROM events WHERE uid=?", (item["uid"],))
    )


def test_semantic_portability_requires_explicit_selection_and_new_review(memory, tmp_path):
    a, b = pair(memory)
    links = MemoryLinks(memory)
    item = proposal(memory, a, b)
    selected = {r["uid"]: r["hash"] for r in (a, b)}
    with pytest.raises(ValueError, match="accepted relationship"):
        export_graph(memory, "private:alice", selected, "backend", "semantic", [item["uid"]])
    links.review("private:alice", item["uid"], "accept", "proposed", "Fixture")
    assert "relations" not in export_graph(memory, "private:alice", selected, "backend", "semantic")
    payload = export_graph(memory, "private:alice", selected, "backend", "semantic", [item["uid"]])
    assert len(payload["relations"]) == 1
    destination = Memory(tmp_path / "destination.db", Identity("fixture", "bob"))
    try:
        grant(destination, "bob", "team:backend", "reviewer")
        import_abhi(destination, payload)
        assert not visible(destination, "team:backend")
        rows = destination.db.execute("SELECT uid,hash FROM records").fetchall()
        for row in rows:
            destination.review("team:backend", row["uid"], "accept", row["hash"], "Fixture")
        assert not visible(destination, "team:backend")
        imported = visible(destination, "team:backend", True)[0]
        MemoryLinks(destination).review(
            "team:backend", imported["uid"], "accept", "proposed", "Fixture"
        )
        output = export_graph(
            destination, "team:backend", dict(rows), "backend", "semantic", [imported["uid"]]
        )
        assert output == payload
    finally:
        destination.close()


def test_portable_assertion_fields_and_atomic_failure(memory):
    a, b = pair(memory)
    item = proposal(memory, a, b)
    MemoryLinks(memory).review("private:alice", item["uid"], "accept", "proposed", "Fixture")
    payload = export_graph(
        memory,
        "private:alice",
        {r["uid"]: r["hash"] for r in (a, b)},
        "backend",
        "semantic",
        [item["uid"]],
    )
    grant(memory, "alice", "team:backend", "reviewer")
    hostile = copy.deepcopy(payload)
    hostile["relations"][0]["state"] = "accepted"
    with pytest.raises(ValueError, match="relationship fields"):
        import_abhi(memory, seal({k: v for k, v in hostile.items() if k != "digest"}))
    # Invalid expiry in the second record rolls back earlier record writes and links.
    hostile = copy.deepcopy(payload)
    hostile["records"][-1]["expires"] = "2020-01-01T00:00:00Z"
    hostile["graph"] = topology(hostile["records"], hostile["relations"])
    with pytest.raises(ValueError, match="future"):
        import_abhi(memory, seal({k: v for k, v in hostile.items() if k != "digest"}))
    assert not memory.db.execute("SELECT * FROM records WHERE brain='team:backend'").fetchall()
    assert not memory.db.execute("SELECT * FROM memory_links WHERE brain='team:backend'").fetchall()


def test_failed_relationship_import_rolls_back_records_links_and_digest(memory, monkeypatch):
    a, b = pair(memory)
    link = proposal(memory, a, b)
    links = MemoryLinks(memory)
    links.review("private:alice", link["uid"], "accept", "proposed", "Fixture")
    payload = export_graph(
        memory,
        "private:alice",
        {r["uid"]: r["hash"] for r in (a, b)},
        "backend",
        "atomic",
        [link["uid"]],
    )
    grant(memory, "alice", "team:backend", "reviewer")

    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise ValueError("Synthetic failed relationship import")

    original = MemoryLinks.put
    monkeypatch.setattr(MemoryLinks, "put", fail_after_write)
    with pytest.raises(ValueError, match="Synthetic"):
        import_abhi(memory, payload)
    assert not memory.db.execute("SELECT * FROM records WHERE brain='team:backend'").fetchall()
    assert not memory.db.execute("SELECT * FROM memory_links WHERE brain='team:backend'").fetchall()
    assert not memory.db.execute("SELECT * FROM imports").fetchall()


@pytest.fixture
def live(real, tmp_path):
    cfg = replace(
        real.cfg,
        tenant_id="fixture_" + uuid.uuid4().hex,
        principal="alice",
        memory_db=str(tmp_path / "links.db"),
        memory_graph_enabled=True,
    )
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, "alice"))
    store = GraphStore(cfg)
    yield memory, store, MemoryGraph(memory, store)
    memory.close()
    if store.db:
        name = cfg.graph_name("org").removesuffix("org_demo") + "memory"
        if name in store.db.list_graphs():
            store.db.select_graph(name).delete()


live_test = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")


@live_test
@pytest.mark.integration
def test_live_reviewed_edges_are_distinct_and_version_pinned(live):
    memory, _store, projection = live
    a, b = pair(memory)
    links = MemoryLinks(memory)
    items = [proposal(memory, a, b, relation) for relation in ("UPDATES", "EXTENDS", "RELATES_TO")]
    projection.sync("private:alice")
    assert not any(e["assertion_uid"] for e in projection.read(["private:alice"])["edges"])
    for item in items:
        links.review("private:alice", item["uid"], "accept", "proposed", "Fixture")
    assert projection.read(["private:alice"])["status"] == "incomplete"
    projection.sync("private:alice")
    view = projection.read(["private:alice"])
    assert view["status"] == "ok", view
    assertions = [e for e in view["edges"] if e["assertion_uid"]]
    assert {e["relation"] for e in assertions} == {"UPDATES", "EXTENDS", "RELATES_TO"}
    assert all(json.loads(e["evidence_json"]) for e in assertions)
    links.review("private:alice", items[0]["uid"], "rollback", "accepted", "Fixture")
    projection.sync("private:alice")
    assert len([e for e in projection.read(["private:alice"])["edges"] if e["assertion_uid"]]) == 2
    memory.review("private:alice", a["uid"], "rollback", a["hash"], "Fixture")
    projection.sync("private:alice")
    view = projection.read(["private:alice"], True)
    assert not any(e["state"] == "accepted" for e in view["edges"])


@live_test
@pytest.mark.integration
def test_live_hidden_relationship_cannot_change_reader_topology(live):
    memory, store, projection = live
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    grant(memory, "bob", brain, "reader")
    a, b = pair(memory, brain)
    proposal(memory, a, b, brain=brain)
    projection.sync(brain)
    other = Memory(store.cfg.memory_db, Identity(memory.identity.tenant, "bob"))
    try:
        graph = MemoryGraph(other, GraphStore(replace(store.cfg, principal="bob")))
        view = graph.read([brain], True)
        assert view["status"] == "ok", view
        assert not any(e["assertion_uid"] for e in view["edges"])
    finally:
        other.close()


@live_test
@pytest.mark.integration
def test_live_semantic_roundtrip_preserves_parallel_assertions_and_review(live):
    memory, _store, projection = live
    a, b = pair(memory)
    links = MemoryLinks(memory)
    first = proposal(memory, a, b)
    second = links.propose(
        "private:alice",
        a["uid"],
        a["hash"],
        "UPDATES",
        b["uid"],
        b["hash"],
        source("Old `upload` behavior"),
    )
    for item in (first, second):
        links.review("private:alice", item["uid"], "accept", "proposed", "Fixture")
    projection.sync("private:alice")
    view = projection.read(["private:alice"])
    assert view["status"] == "ok", view
    assert len([e for e in view["edges"] if e["assertion_uid"]]) == 2
    payload = export_graph(
        memory,
        "private:alice",
        {r["uid"]: r["hash"] for r in (a, b)},
        "backend",
        "parallel",
        [first["uid"], second["uid"]],
    )
    brain = "team:backend"
    grant(memory, "alice", brain, "reviewer")
    import_abhi(memory, payload)
    records = memory.db.execute("SELECT uid,hash FROM records WHERE brain=?", (brain,)).fetchall()
    for row in records:
        memory.review(brain, row["uid"], "accept", row["hash"], "Fixture")
    projection.sync(brain)
    assert not any(e["assertion_uid"] for e in projection.read([brain])["edges"])
    imported = visible(memory, brain, True)
    assert len(imported) == 2
    for row in imported:
        links.review(brain, row["uid"], "accept", "proposed", "Fixture")
    projection.sync(brain)
    view = projection.read([brain])
    assert view["status"] == "ok", view
    assert len([e for e in view["edges"] if e["assertion_uid"]]) == 2
    assert (
        export_graph(
            memory, brain, dict(records), "backend", "parallel", [r["uid"] for r in imported]
        )
        == payload
    )
