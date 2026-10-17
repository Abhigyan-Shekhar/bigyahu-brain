"""Team app authorization, selected sharing, source privacy and native retrieval."""

import json
import os
from dataclasses import replace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_app_personal import managed
from test_integration import real as real  # noqa: PLC0414

from brain.app import personal, team
from brain.app.evidence import register, resolve, verified_claims
from brain.app.server import create_app
from brain.graph import GraphStore


@pytest.fixture
def shared(real, tmp_path):
    state, project, cfg = managed(real, tmp_path)
    note = personal.propose_note(
        cfg, "Retry Service must validate negative inputs before calculating delays."
    )
    personal.review(cfg, note["uid"], note["hash"], "proposed", "accept", "Checked original note")
    team.create(cfg, "platform")
    team.membership(cfg, "platform", "bob", "reader", "", "Disposable reader for permission checks")
    return state, project, cfg, note


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"),
]


def test_selected_share_requires_current_review_and_separate_team_acceptance(shared):
    _state, _project, cfg, note = shared
    with pytest.raises(ValueError):
        team.share(cfg, "platform", note["uid"], "f" * 64)
    result = team.share(cfg, "platform", note["uid"], note["hash"])
    assert result["state"] == "proposed"
    bob = replace(cfg, principal="bob")
    assert not team.search(bob, "negative inputs")["items"]
    with personal.catalog(bob) as (memory, projection):
        with pytest.raises(KeyError):
            team.record(memory, "platform", result["uid"])
        view = team.graph(bob, memory, projection, ["team:platform"], include_proposals=True)
        assert not any(n["labels"] == ["Memory"] for n in view["graph"]["nodes"])
    with pytest.raises(PermissionError):
        team.review(
            bob,
            "platform",
            result["uid"],
            result["hash"],
            "proposed",
            "accept",
            "Reader cannot review",
        )
    with pytest.raises(ValueError):
        team.review(
            cfg, "platform", result["uid"], "f" * 64, "proposed", "accept", "Wrong revision"
        )
    team.review(
        cfg,
        "platform",
        result["uid"],
        result["hash"],
        "proposed",
        "accept",
        "Reviewed selected team evidence",
    )
    found = team.search(bob, "negative inputs")
    assert found["status"] == "ok" and found["backend"] == "falkor" and not found["vector_enabled"]
    assert len(found["items"]) == 1 and found["items"][0]["brain"] == "team:platform"
    assert team.share(cfg, "platform", note["uid"], note["hash"])["state"] == "accepted"


def test_team_evidence_rechecks_membership_state_and_sources(shared, tmp_path):
    _state, _project, cfg, note = shared
    r = team.share(cfg, "platform", note["uid"], note["hash"])
    team.review(cfg, "platform", r["uid"], r["hash"], "proposed", "accept", "Checked")
    bob = replace(cfg, principal="bob")
    evidence = register(
        tmp_path / "evidence", team.memory_evidence(bob, "platform", r["uid"], r["hash"])
    )
    assert evidence["kind"] == "team_memory"
    output = {
        "claims": [
            {
                "text": "Preserve negative-input validation.",
                "support": [{"evidence_id": evidence["id"], "quote": "validate negative inputs"}],
            }
        ]
    }
    assert verified_claims(GraphStore(bob), tmp_path / "evidence", output)
    team.membership(cfg, "platform", "bob", "revoke", "reader", "Remove disposable membership")
    with pytest.raises(PermissionError):
        resolve(GraphStore(bob), evidence)
    assert not team.search(bob, "negative inputs")["items"]
    # Membership restoration changes the projection manifest; stale graph fails closed.
    team.membership(cfg, "platform", "bob", "reader", "", "Restore test membership")
    team.review(cfg, "platform", r["uid"], r["hash"], "accepted", "rollback", "Revoke team review")
    with pytest.raises(ValueError):
        resolve(GraphStore(bob), evidence)
    team.review(
        cfg, "platform", r["uid"], r["hash"], "proposed", "accept", "Restore reviewed evidence"
    )
    with personal.catalog(cfg) as (memory, _):
        source = team.source_details(cfg, memory, team.record(memory, "platform", r["uid"]))
    path = cfg.repo_root.parent / "memory-sources" / source["digest"]
    path.write_text("tampered")
    assert team.search(bob, "negative inputs")["items"] == []
    with pytest.raises((ValueError, json.JSONDecodeError)):
        resolve(GraphStore(bob), evidence)
    # Source corruption cannot prevent revocation.
    team.review(cfg, "platform", r["uid"], r["hash"], "accepted", "rollback", "Source lost")


def test_team_member_view_cannot_federate_private_records_or_other_teams(shared):
    _state, _project, cfg, note = shared
    personal.propose_note(cfg, "SECRET: unrelated private conversation envelope")
    r = team.share(cfg, "platform", note["uid"], note["hash"])
    team.review(cfg, "platform", r["uid"], r["hash"], "proposed", "accept", "Checked")
    bob = replace(cfg, principal="bob")
    with personal.catalog(bob) as (memory, projection):
        selected = team.record(memory, "platform", r["uid"])
        source = team.source_details(bob, memory, selected)
        assert set(source) == {"text", "sources", "author", "digest", "kind"}
        assert "SECRET" not in json.dumps(source)
        assert json.loads(selected["sources"]) == note_sources(cfg, note["uid"])
        view = team.graph(bob, memory, projection, ["team:platform"], member=cfg.principal)
        assert "SECRET" not in json.dumps(view) and "private:app_operator" not in json.dumps(view)
        assert any(n["labels"] == ["Memory"] for n in view["graph"]["nodes"])
        empty = team.graph(bob, memory, projection, ["team:platform"], member="bob")
        assert not any(n["labels"] == ["Memory"] for n in empty["graph"]["nodes"])
        with pytest.raises(PermissionError):
            team.record(memory, "unauthorized", r["uid"])
    with pytest.raises(PermissionError):
        team.membership(bob, "platform", "eve", "reviewer", "", "Escalation blocked")
    with pytest.raises(ValueError):
        team.membership(cfg, "platform", "bob", "writer", "reviewer", "Stale role")
    with pytest.raises(ValueError):
        team.membership(
            cfg, "platform", cfg.principal, "revoke", "reviewer", "Owner lockout blocked"
        )
    assert not team.search(replace(bob, tenant_id="other_tenant"), "negative inputs")["items"]


def note_sources(cfg, uid):
    with personal.catalog(cfg) as (memory, _):
        return json.loads(personal.row(memory, uid)["sources"])


def test_team_http_auth_identity_injection_and_reader_visibility(shared, tmp_path):
    state, project, cfg, note = shared
    r = team.share(cfg, "platform", note["uid"], note["hash"])
    # A distinct server configuration pins the reader identity; HTTP cannot select it.
    config_path = state.folder(project) / "brain.local.yaml"
    import yaml

    values = yaml.safe_load(config_path.read_text())
    values["principal"] = "bob"
    config_path.write_text(yaml.safe_dump(values))
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    base = f"/api/repositories/{project}/teams"
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            assert client.get(base).status_code == 401
            assert client.get(base, headers=headers).json()["items"][0]["role"] == "reader"
            assert (
                client.post(
                    base, headers=headers, json={"name": "evil", "principal": "owner"}
                ).status_code
                == 422
            )
            assert client.get(base + "/platform/memories", headers=headers).json()["items"] == []
            assert (
                client.get(base + "/platform/memories/" + r["uid"], headers=headers).status_code
                == 404
            )
            assert client.get(base + "/other/memories", headers=headers).status_code == 403
            assert client.post(
                base + "/platform/share",
                headers=headers,
                json={"uid": note["uid"], "expected_hash": note["hash"]},
            ).status_code in {403, 404}
            assert (
                client.get(base + "/platform/graph?member=unknown", headers=headers).status_code
                == 404
            )
    finally:
        app.state.workers.shutdown()


def test_writer_shares_selected_conversation_without_private_envelope(shared):
    _state, _project, cfg, _note = shared
    team.membership(cfg, "platform", "bob", "writer", "reader", "Allow selected contributions")
    bob = replace(cfg, principal="bob")
    from brain.conversation import ingest_conversation
    from brain.memory import canonical, digest

    payload = {
        "format": "conversation/1",
        "session": "writer-session",
        "turns": [
            {
                "id": "one",
                "role": "user",
                "text": "Prefer unittest for retry checks.\nHow can I hide SECRET_CONTEXT?",
            }
        ],
    }
    personal.snapshot(bob, payload)
    with personal.catalog(bob) as (memory, projection):
        result = ingest_conversation(memory, payload, digest(canonical(payload)))
        r = personal.row(memory, result["items"][0]["uid"])
        uid, fingerprint = r["uid"], r["hash"]
        personal.refresh(memory, projection)
    personal.review(bob, uid, fingerprint, "proposed", "accept", "Selected durable statement only")
    shared_record = team.share(bob, "platform", uid, fingerprint)
    assert shared_record["state"] == "proposed"
    assert shared_record["projection"]["status"] == "unavailable"
    # Writer saved a proposal, but cannot publish a reviewer-owned graph or accept it.
    with pytest.raises(PermissionError):
        team.review(
            bob,
            "platform",
            shared_record["uid"],
            shared_record["hash"],
            "proposed",
            "accept",
            "Blocked",
        )
    team.review(
        cfg,
        "platform",
        shared_record["uid"],
        shared_record["hash"],
        "proposed",
        "accept",
        "Reviewed selected span",
    )
    with personal.catalog(cfg) as (memory, projection):
        r = team.record(memory, "platform", shared_record["uid"])
        source = team.source_details(cfg, memory, r)
        assert "SECRET_CONTEXT" not in json.dumps(source)
        view = team.graph(cfg, memory, projection, ["team:platform"], member="bob")
        assert any(n["labels"] == ["Memory"] for n in view["graph"]["nodes"])
        assert "SECRET_CONTEXT" not in json.dumps(view)
    assert team.search(cfg, "unittest")["items"]
