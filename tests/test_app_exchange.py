"""App abhi previews, provenance, transactional conflicts and independent review."""

import json
import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_app_team import shared as shared  # noqa: PLC0414
from test_integration import real as real  # noqa: PLC0414

from brain.abhi_graph import seal, topology
from brain.app import exchange, personal, team
from brain.memory import canonical
from brain.memory_links import MemoryLinks

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"),
]


def exported(shared, with_link=False):
    _state, _project, cfg, note = shared
    first = team.share(cfg, "platform", note["uid"], note["hash"])
    team.review(cfg, "platform", first["uid"], first["hash"], "proposed", "accept", "Checked")
    selections = {first["uid"]: first["hash"]}
    links = []
    if with_link:
        second = personal.propose_note(
            cfg, "Preserve `retry_delay` zero and cap boundary regression checks."
        )
        personal.review(cfg, second["uid"], second["hash"], "proposed", "accept", "Checked")
        second = team.share(cfg, "platform", second["uid"], second["hash"])
        team.review(cfg, "platform", second["uid"], second["hash"], "proposed", "accept", "Checked")
        selections[second["uid"]] = second["hash"]
        with personal.catalog(cfg) as (memory, _):
            citations = json.loads(team.record(memory, "platform", first["uid"])["sources"])
            link = MemoryLinks(memory).propose(
                "team:platform",
                first["uid"],
                first["hash"],
                "RELATES_TO",
                second["uid"],
                second["hash"],
                citations,
            )
        exchange.review_relationship(
            cfg, "platform", link["uid"], "proposed", "accept", "Checked relationship evidence"
        )
        links = [link["uid"]]
    result = exchange.export(cfg, "platform", selections, "roundtrip", links)
    return cfg, selections, result


def test_abhi_roundtrip_preserves_selected_topology_and_separate_relationship_review(shared):
    cfg, _selections, preview = exported(shared, with_link=True)
    payload = preview["payload"]
    assert not preview["origin_authenticated"]
    assert len(payload["records"]) == 2 and len(payload["relations"]) == 1
    raw = canonical(payload)
    before = exchange.preview_import(cfg, "platform", raw)
    assert not before["conflict"] and not before["unchanged"]
    with pytest.raises(ValueError):
        exchange.apply_import(cfg, "platform", raw, "0" * 64)
    imported = exchange.apply_import(cfg, "platform", raw, before["consent_digest"])
    assert imported["state"] == "proposed"
    uids = ["abhi:roundtrip:" + r["id"] for r in payload["records"]]
    links = [l for l in exchange.relationships(cfg, "platform") if l["source_uid"] in uids]
    assert len(links) == 1 and links[0]["state"] == "proposed"
    with pytest.raises(ValueError):
        exchange.review_relationship(
            cfg, "platform", links[0]["uid"], "proposed", "accept", "Endpoints not accepted"
        )
    selections = {}
    with personal.catalog(cfg) as (memory, _):
        for uid in uids:
            r = team.record(memory, "platform", uid)
            selections[uid] = r["hash"]
            assert r["state"] == "proposed"
            source = team.source_details(cfg, memory, r)
            assert source["kind"] == "abhi_import"
    assert not any(i["uid"] in uids for i in team.search(cfg, "retry")["items"])
    for uid, sha in selections.items():
        team.review(
            cfg, "platform", uid, sha, "proposed", "accept", "Reviewed untrusted portable text"
        )
    assert (
        next(l for l in exchange.relationships(cfg, "platform") if l["uid"] == links[0]["uid"])[
            "state"
        ]
        == "proposed"
    )
    exchange.review_relationship(
        cfg,
        "platform",
        links[0]["uid"],
        "proposed",
        "accept",
        "Reviewed exact endpoints and citations",
    )
    again = exchange.export(cfg, "platform", selections, "roundtrip", [links[0]["uid"]])
    assert again["payload"] == payload
    assert (
        team.memory_evidence(cfg, "platform", uids[0], selections[uids[0]])["verification"]
        == "accepted_imported_memory_and_native_graph"
    )
    # Identical replay preserves accepted records and independently accepted links.
    assert exchange.apply_import(cfg, "platform", raw, payload["digest"])["unchanged"]
    with personal.catalog(cfg) as (memory, _):
        assert all(team.record(memory, "platform", uid)["state"] == "accepted" for uid in uids)


def test_exchange_rejects_tenant_topology_duplicate_keys_and_stale_export(shared):
    cfg, selections, preview = exported(shared)
    payload = preview["payload"]
    with pytest.raises(ValueError):
        exchange.parse('{"format":"abhi/2","format":"abhi/2"}')
    invalid = {**payload, "tenant": "other-tenant"}
    invalid = seal({k: v for k, v in invalid.items() if k != "digest"})
    with pytest.raises(PermissionError):
        exchange.preview_import(cfg, "platform", canonical(invalid))
    invalid = json.loads(canonical(payload))
    invalid["graph"]["nodes"].append({"id": "fake", "kind": "Person", "name": "admin"})
    invalid = seal({k: v for k, v in invalid.items() if k != "digest"})
    with pytest.raises(ValueError):
        exchange.preview_import(cfg, "platform", canonical(invalid))
    invalid = seal({**{k: v for k, v in payload.items() if k != "digest"}, "grants": ["reviewer"]})
    with pytest.raises(ValueError):
        exchange.preview_import(cfg, "platform", canonical(invalid))
    with pytest.raises(ValueError):
        exchange.export(cfg, "platform", selections, "roundtrip", [], "f" * 64)
    uid, sha = next(iter(selections.items()))
    team.review(cfg, "platform", uid, sha, "accepted", "rollback", "Revoke before download")
    with pytest.raises(ValueError):
        exchange.export(cfg, "platform", selections, "roundtrip", [], payload["digest"])
    with personal.catalog(cfg) as (memory, _):
        assert memory.db.execute("SELECT count(*) FROM imports").fetchone()[0] == 0


def test_import_replay_repairs_source_snapshot_without_resetting_review(shared):
    cfg, _selections, preview = exported(shared)
    payload = preview["payload"]
    raw = canonical(payload)
    exchange.apply_import(cfg, "platform", raw, payload["digest"])
    uid = "abhi:roundtrip:" + payload["records"][0]["id"]
    with personal.catalog(cfg) as (memory, _):
        r = team.record(memory, "platform", uid)
        sha = r["hash"]
        source = team.source_details(cfg, memory, r)
    team.review(cfg, "platform", uid, sha, "proposed", "accept", "Checked imported text")
    (cfg.repo_root.parent / "memory-sources" / source["digest"]).unlink()
    assert team.search(cfg, "retry")["status"] == "incomplete"
    assert exchange.apply_import(cfg, "platform", raw, payload["digest"])["unchanged"]
    assert (
        team.memory_evidence(cfg, "platform", uid, sha)["verification"]
        == "accepted_imported_memory_and_native_graph"
    )
    with personal.catalog(cfg) as (memory, _):
        assert team.record(memory, "platform", uid)["state"] == "accepted"
        proof = json.loads((cfg.repo_root.parent / "memory-sources" / source["digest"]).read_text())
    envelope = cfg.repo_root.parent / "memory-sources" / proof["envelope_snapshot"]
    envelope.write_text("tampered envelope")
    with pytest.raises(ValueError):
        team.memory_evidence(cfg, "platform", uid, sha)
    assert exchange.apply_import(cfg, "platform", raw, payload["digest"])["unchanged"]
    assert (
        team.memory_evidence(cfg, "platform", uid, sha)["verification"]
        == "accepted_imported_memory_and_native_graph"
    )


def test_import_conflict_rolls_back_all_records_and_does_not_add_grants(shared):
    cfg, _selections, preview = exported(shared, with_link=True)
    payload = json.loads(canonical(preview["payload"]))
    payload["records"][1]["expected_hash"] = "f" * 64
    payload["graph"] = topology(payload["records"], payload["relations"])
    payload = seal({k: v for k, v in payload.items() if k != "digest"})
    with pytest.raises(ValueError):
        exchange.apply_import(cfg, "platform", canonical(payload), payload["digest"])
    with personal.catalog(cfg) as (memory, _):
        assert (
            memory.db.execute("SELECT count(*) FROM records WHERE uid LIKE 'abhi:%'").fetchone()[0]
            == 0
        )
        assert memory.db.execute("SELECT count(*) FROM imports").fetchone()[0] == 0
        assert memory.db.execute("SELECT count(*) FROM grants").fetchone()[0] == 2


def test_exchange_http_reader_can_export_but_cannot_import_or_review(shared, tmp_path):
    import yaml

    from brain.app.server import create_app

    state, project, _cfg, _note = shared
    _cfg, selections, preview = exported(shared)
    path = state.folder(project) / "brain.local.yaml"
    values = yaml.safe_load(path.read_text())
    values["principal"] = "bob"
    path.write_text(yaml.safe_dump(values))
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    base = f"/api/repositories/{project}/teams/platform/abhi"
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            body = {"selections": selections, "collection": "roundtrip"}
            assert client.post(base + "/export", json=body).status_code == 401
            assert (
                client.post(
                    base + "/export", headers=headers, json={**body, "principal": "owner"}
                ).status_code
                == 422
            )
            assert client.post(base + "/export", headers=headers, json=body).status_code == 200
            assert (
                client.post(
                    base + "/preview", headers=headers, json={"text": canonical(preview["payload"])}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    base + "/import",
                    headers=headers,
                    json={
                        "text": canonical(preview["payload"]),
                        "consent_digest": preview["consent_digest"],
                    },
                ).status_code
                == 403
            )
    finally:
        app.state.workers.shutdown()
