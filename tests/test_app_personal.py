"""Private app review boundaries, source integrity and real native memory recall."""

import json
import os
import subprocess
from dataclasses import replace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_integration import real as real  # noqa: PLC0414

from brain.app import personal
from brain.app.agent import TOOLS, command
from brain.app.evidence import register, verified_claims
from brain.app.server import create_app
from brain.app.state import State
from brain.config import Config
from brain.graph import GraphStore
from brain.ingest.sync import sync
from brain.memory import canonical, digest


def test_readonly_agent_exposes_private_reads_without_review_or_scope_arguments(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    project = state.create("repository", status="ready")
    args = command(state, project["id"], tmp_path)
    assert {"memory_search", "memory_graph"} <= set(TOOLS)
    for tool in ("memory_propose", "memory_review", "grant", "remember", "share"):
        assert tool not in TOOLS
    assert args[args.index("-s") + 1] == "read-only"


def test_conversation_preview_requires_exact_project_completed_user_selection(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    chat = state.create("session", project="project")
    turn = state.create(
        "turn",
        chat["id"],
        question="Use unittest for retry changes.",
        status="complete",
        claims=[{"text": "Assistant invented policy"}],
    )
    preview = personal.conversation_preview(state, "project", chat["id"], [turn["id"]])
    assert preview["payload"]["turns"] == [
        {"id": turn["id"], "role": "user", "text": turn["question"]}
    ]
    assert preview["consent_digest"] == digest(canonical(preview["payload"]))
    with pytest.raises(ValueError):
        personal.conversation_preview(state, "other", chat["id"], [turn["id"]])
    with pytest.raises(ValueError):
        personal.conversation_preview(state, "project", chat["id"], [turn["id"], turn["id"]])


def test_personal_http_requires_auth_and_rejects_identity_injection_or_wrong_consent(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    project = state.create("repository", status="ready")
    chat = state.create("session", project=project["id"])
    turn = state.create("turn", chat["id"], question="Use unittest.", status="complete")
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    url = f"/api/repositories/{project['id']}/memory"
    try:
        with TestClient(app) as client:
            assert client.get(url).status_code == 401
            assert client.post(url, json={"text": "Hello"}).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (
                client.post(
                    url, headers=headers, json={"text": "Hello", "brain": "private:other"}
                ).status_code
                == 422
            )
            assert (
                client.post(
                    url + "/imports",
                    headers=headers,
                    json={"session": chat["id"], "turns": [turn["id"]], "consent_digest": "f" * 64},
                ).status_code
                == 400
            )
            assert state.list("memory_import", project["id"]) == []
    finally:
        app.state.workers.shutdown()


def managed(real, tmp_path):
    state = State(tmp_path / "app", real.cfg, "fixture-model")
    project = state.create("repository", status="ready", url=real.cfg.repo_url)
    folder = state.folder(project["id"])
    folder.mkdir()
    subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", str(real.cfg.repo_root), str(folder / "checkout")],
        check=True,
    )
    cfg = state.configure(project["id"], real.cfg.repo_url)
    sync(GraphStore(cfg))
    return state, project["id"], cfg


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_private_review_native_search_evidence_and_revocation(real, tmp_path):
    _state, _project, cfg = managed(real, tmp_path)
    proposed = personal.propose_note(
        cfg, "For retry fixes, use unittest and verify zero-base integer behavior."
    )
    assert proposed["state"] == "proposed"
    assert personal.search(cfg, "retry")["items"] == []
    with pytest.raises(ValueError):
        personal.review(cfg, proposed["uid"], "f" * 64, "proposed", "accept", "Checked")
    accepted = personal.review(
        cfg,
        proposed["uid"],
        proposed["hash"],
        "proposed",
        "accept",
        "Verified original operator note",
    )
    assert accepted["state"] == "accepted"
    with pytest.raises(ValueError):
        personal.review(cfg, proposed["uid"], proposed["hash"], "proposed", "accept", "Replay")
    found = personal.search(cfg, "retry")
    assert found["backend"] == "falkor" and found["items"][0]["uid"] == proposed["uid"]
    evidence = personal.memory_evidence(cfg, proposed["uid"], proposed["hash"])
    assert evidence["binding"] is False and any(
        e["relation"] == "SUPPORTED_BY" for e in evidence["graph"]["edges"]
    )
    saved = register(tmp_path / "evidence", evidence)
    output = {
        "claims": [
            {
                "text": "The private note recommends unittest.",
                "support": [{"evidence_id": saved["id"], "quote": "use unittest"}],
            }
        ]
    }
    assert verified_claims(GraphStore(cfg), tmp_path / "evidence", output)
    other = replace(cfg, tenant_id="unrelated_tenant")
    assert personal.search(other, "retry")["items"] == []
    personal.review(
        cfg, proposed["uid"], proposed["hash"], "accepted", "rollback", "Preference revoked"
    )
    assert personal.search(cfg, "retry")["items"] == []
    with pytest.raises(ValueError):
        verified_claims(GraphStore(cfg), tmp_path / "evidence", output)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_tampered_source_blocks_acceptance_and_stale_graph_never_falls_back(real, tmp_path):
    _state, _project, cfg = managed(real, tmp_path)
    result = personal.propose_note(
        cfg, "Remember the retry sentinel: use capped exponential delay."
    )
    with personal.catalog(cfg) as (memory, _projection):
        record = personal.row(memory, result["uid"])
        fingerprint = json.loads(record["sources"])[0]["digest"]
    artifact = cfg.repo_root.parent / "memory-sources" / fingerprint
    raw = artifact.read_text()
    artifact.write_text("tampered")
    with pytest.raises(ValueError, match="snapshot changed"):
        personal.review(cfg, result["uid"], result["hash"], "proposed", "accept", "Bad source")
    artifact.write_text(raw)
    personal.review(cfg, result["uid"], result["hash"], "proposed", "accept", "Verified")
    artifact.write_text("tampered")
    assert personal.search(cfg, "retry")["status"] == "incomplete"
    assert personal.search(cfg, "retry")["items"] == []
    artifact.write_text(raw)
    with personal.catalog(cfg) as (memory, _projection):
        memory.propose(
            "Unprojected proposal", [{"uri": "urn:test:unprojected", "digest": digest("x")}]
        )
    found = personal.search(cfg, "retry")
    assert found["status"] == "incomplete" and found["items"] == []
    # Revocation still works after the underlying original source is lost.
    artifact.unlink()
    assert (
        personal.review(cfg, result["uid"], result["hash"], "accepted", "rollback", "Withdraw")[
            "state"
        ]
        == "proposed"
    )


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_selected_conversation_import_is_verbatim_and_reviewable(real, tmp_path):
    state, project, cfg = managed(real, tmp_path)
    chat = state.create("session", project=project)
    turn = state.create(
        "turn",
        chat["id"],
        question="Prefer unittest for retry regression checks.",
        status="complete",
    )
    preview = personal.conversation_preview(state, project, chat["id"], [turn["id"]])
    job = state.create(
        "memory_import",
        project,
        project=project,
        session=chat["id"],
        turns=[turn["id"]],
        semantic=False,
        consent_digest=preview["consent_digest"],
        status="queued",
    )
    personal.import_selected(state, job["id"])
    assert state.get(job["id"])["status"] == "complete"
    with personal.catalog(cfg) as (memory, _projection):
        records, _ = personal.rows(memory)
        assert len(records) == 1 and records[0]["state"] == "proposed"
        assert (
            personal.source_details(cfg, memory, personal.row(memory, records[0]["uid"]))[0]["kind"]
            == "selected_user_turn"
        )
    assert personal.search(cfg, "retry")["items"] == []


@pytest.mark.parametrize("passing,count", [(False, 6), (True, 0)])
def test_failed_or_zero_test_action_cannot_become_a_lesson(tmp_path, monkeypatch, passing, count):
    from brain.app import actions

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    action = state.create(
        "action",
        status="complete",
        tests_passed=passing,
        lesson_proposal={"text": "Try retry fixes"},
        tests=[{"passed": True, "exit_code": 0, "outcome": "exited", "tests_reported": count}],
    )
    monkeypatch.setattr(
        actions,
        "checked_action",
        lambda *args: pytest.fail("Invalid action reached source verification"),
    )
    with pytest.raises(ValueError):
        personal.propose_lesson(state, action["id"])


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_lesson_snapshot_review_and_repeated_send_do_not_reset_acceptance(
    real, tmp_path, monkeypatch
):
    from brain.app import actions

    state, project, cfg = managed(real, tmp_path)
    monkeypatch.setattr(actions, "checked_action", lambda *args: None)
    action = state.create(
        "action",
        project=project,
        status="complete",
        tests_passed=True,
        lesson_proposal={"text": "For retry changes, test zero-base integer behavior."},
        base_revision="fixture-sha",
        objective="Fix retry",
        plan_digest="f" * 64,
        changed_files=["retry.py"],
        patch="fixture patch",
        tests=[
            {
                "argv": ["python", "-m", "unittest", "test_retry.py"],
                "exit_code": 0,
                "outcome": "exited",
                "passed": True,
                "tests_reported": 6,
            }
        ],
    )
    proposed = personal.propose_lesson(state, action["id"])
    assert proposed["state"] == "proposed"
    assert personal.search(cfg, "retry")["items"] == []
    with personal.catalog(cfg) as (memory, _projection):
        sources = personal.source_details(cfg, memory, personal.row(memory, proposed["uid"]))
        report = json.loads(sources[0]["text"])
        assert report["patch_sha256"] == digest("fixture patch")
        assert report["tests"][0]["tests_reported"] == 6
    personal.review(
        cfg, proposed["uid"], proposed["hash"], "proposed", "accept", "Checked coding report"
    )
    assert personal.propose_lesson(state, action["id"])["state"] == "accepted"
    assert personal.search(cfg, "retry")["items"][0]["uid"] == proposed["uid"]
