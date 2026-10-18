"""Cited immutable Markdown drafts, independent review and generated-source bounds."""

import json

import pytest
from fastapi.testclient import TestClient
from test_integration import real as real  # noqa: PLC0414

from brain.app import actions, document_store, documentation, evidence
from brain.app.server import create_app


def draft(authored, **overrides):
    values = {
        "kind": "incident",
        "instruction": "Document queue recovery",
        "destination": "app_docs",
        "proposed_repo_path": None,
        "source_turn_id": None,
        "source_action_id": None,
        **overrides,
    }
    value = documentation.create(authored.state, authored.project, values)
    documentation.generate(authored.state, value["id"])
    return authored.state.get(value["id"])


def test_cited_draft_is_immutable_nonbinding_and_does_not_require_python_tests(authored):
    value = draft(authored)
    assert value["status"] == "draft" and not value["binding"]
    text = document_store.content(authored.state, value)
    assert "in-memory dictionary" in text and "[^source-" in text
    assert (
        "not organizational policy" in text
        and "Restart behavior was not independently tested" in text
    )
    assert "tests" not in value and not value.get("indexing_result")
    documentation.validate(authored.state, value)
    again = document_store.artifact(authored.state, authored.project, text)
    assert again == value["content_digest"]
    changed = document_store.artifact(authored.state, authored.project, text + "\n")
    assert changed != again


@pytest.mark.parametrize(
    "change",
    ["fake_id", "wrong_quote", "changed_source", "unauthorized", "generated_source", "unsupported"],
)
def test_fabricated_changed_or_unauthorized_evidence_prevents_draft(authored, monkeypatch, change):
    def model(*args, **kwargs):
        result = authored.model(*args, **kwargs)
        support = result["claims"][0]["support"][0]
        if change == "fake_id":
            support["evidence_id"] = "a" * 24
        if change == "wrong_quote":
            support["quote"] = "durable queue"
        return result

    monkeypatch.setattr(actions, "_codex", model)
    if change == "changed_source":
        monkeypatch.setattr(evidence, "resolve", lambda *_: {**authored.proof, "digest": "changed"})
    if change == "unauthorized":

        def denied(*_):
            raise PermissionError("Revoked memory")

        monkeypatch.setattr(evidence, "resolve", denied)
    if change == "generated_source":
        authored.proof["source_kind"] = "agent_generated_document"
    if change == "unsupported":
        monkeypatch.setattr(
            documentation, "assess", lambda *_a, **_k: [{"claim": 0, "verdict": "uncertain"}]
        )
    value = draft(authored)
    assert value["status"] == "failed" and not value.get("content_digest")


def test_review_is_exact_idempotent_and_stale_revision_is_blocked(authored):
    value = draft(authored)
    with pytest.raises(ValueError, match="changed"):
        document_store.approve(
            authored.state,
            authored.project,
            value["id"],
            "0" * 64,
            authored.sha,
            documentation.validate,
        )
    accepted = document_store.approve(
        authored.state,
        authored.project,
        value["id"],
        value["review_digest"],
        authored.sha,
        documentation.validate,
    )
    assert accepted["status"] == "approved"
    assert (
        document_store.approve(
            authored.state,
            authored.project,
            value["id"],
            value["review_digest"],
            authored.sha,
            documentation.validate,
        )["approved_at"]
        == accepted["approved_at"]
    )
    authored.current["sha"] = "f" * 40
    with pytest.raises(ValueError, match="stale"):
        documentation.validate(authored.state, accepted)


@pytest.mark.parametrize(
    "text",
    [
        "<script>alert(1)</script>",
        "![tracking](https://example.com/x)",
        "[x](javascript:bad)",
        "x" * 61441,
    ],
)
def test_markdown_content_limits(text):
    with pytest.raises(ValueError):
        document_store.markdown_check(text)


def test_every_factual_section_requires_checked_claim_indices(authored, monkeypatch):
    def model(*args, **kwargs):
        result = authored.model(*args, **kwargs)
        result["sections"][0]["claim_indices"] = [99]
        return result

    monkeypatch.setattr(actions, "_codex", model)
    assert draft(authored)["status"] == "failed"


def test_artifact_tampering_is_detected(authored):
    value = draft(authored)
    path = (
        authored.state.folder(authored.project)
        / "documentation/blobs"
        / (value["content_digest"] + ".md")
    )
    path.write_text("Unreviewed replacement")
    with pytest.raises(ValueError, match="bytes changed"):
        document_store.content(authored.state, value)


def test_revised_version_needs_new_approval_and_preserves_old_approved_artifact(
    authored, monkeypatch
):
    old = draft(authored)
    document_store.approve(
        authored.state,
        authored.project,
        old["id"],
        old["review_digest"],
        authored.sha,
        documentation.validate,
    )
    text = document_store.content(authored.state, old)

    def model(*args, **kwargs):
        result = authored.model(*args, **kwargs)
        result["title"] = "Revised queue recovery"
        return result

    monkeypatch.setattr(actions, "_codex", model)
    new = draft(authored, instruction="Revise the title and keep checked facts")
    assert new["status"] == "draft" and new["review_digest"] != old["review_digest"]
    assert authored.state.get(old["id"])["status"] == "approved"
    assert document_store.content(authored.state, old) == text
    with pytest.raises(ValueError, match="changed"):
        document_store.approve(
            authored.state,
            authored.project,
            new["id"],
            old["review_digest"],
            authored.sha,
            documentation.validate,
        )


def test_api_scope_revision_review_download_and_explicit_generated_index(authored, monkeypatch):
    state, project = authored.state, authored.project
    app = create_app(state, "token", "http://testserver")
    indexed = []
    monkeypatch.setattr(
        "brain.app.authoring_api.upload_document",
        lambda *args, **kwargs: (
            indexed.append((args, kwargs)) or {"binding": False, "source_ids": ["fixture"]}
        ),
    )
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            route = f"/api/repositories/{project}/documentation/drafts"
            assert client.get(route).status_code == 401
            response = client.post(
                route,
                headers=headers,
                json={"instruction": "Document the queue", "kind": "incident"},
            )
            assert response.status_code == 202
            app.state.workers.shutdown(wait=True)
            value = client.get(route + "/" + response.json()["id"], headers=headers).json()
            assert value["status"] == "draft" and value["stale"] is False and value["diff"]
            base = route + "/" + value["id"]
            consent = {
                "expected_digest": value["review_digest"],
                "source_revision": value["source_revision"],
            }
            assert (
                client.post(base + "/index-approved", headers=headers, json=consent).status_code
                == 400
            )
            assert not indexed
            assert client.get(base + "/download", headers=headers).text == value["markdown"]
            assert (
                client.get(
                    f"/api/repositories/other/documentation/drafts/{value['id']}", headers=headers
                ).status_code
                == 404
            )
            assert (
                client.post(base + "/approve", headers=headers, json=consent).json()["status"]
                == "approved"
            )
            assert (
                client.post(base + "/index-approved", headers=headers, json=consent).status_code
                == 200
            )
            assert len(indexed) == 1 and "source_evidence_ids" in json.loads(
                indexed[0][1]["generated_provenance"]
            )
    finally:
        app.state.workers.shutdown(wait=True)


def test_revoked_sources_block_reuse_from_existing_turn(authored, monkeypatch):
    source = authored.source / "unused"
    source.mkdir()
    item = evidence.register(source, authored.proof)

    def denied(*_):
        raise PermissionError("Revoked")

    monkeypatch.setattr(evidence, "resolve", denied)
    with pytest.raises(PermissionError):
        documentation.seed_evidence(
            authored.state,
            authored.project,
            authored.source / "new",
            [
                (
                    source,
                    [
                        {
                            "text": "Fact",
                            "support": [{"evidence_id": item["id"], "quote": "jobs = {}"}],
                        }
                    ],
                )
            ],
        )


@pytest.mark.skipif(__import__("os").getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_live_generated_ingestion_has_reviewed_provenance_and_cannot_self_cite(
    real, tmp_path, monkeypatch
):
    from brain.app.sources import upload_document
    from brain.app.state import State
    from brain.ingest.sync import sync

    store, cfg = real, real.cfg
    sync(store)
    state = State(tmp_path.parent / (tmp_path.name + "-app"), cfg, "fixture")
    repo = state.create(
        "repository", name="fixture", url="https://github.com/example/project", status="ready"
    )
    # Uploaded-byte validation resolves beside the configured checkout.
    monkeypatch.setattr(state, "folder", lambda _project: cfg.repo_root.parent)
    monkeypatch.setattr(state, "config", lambda _project: cfg)
    result = upload_document(
        state,
        repo["id"],
        "generated.md",
        "# Queue\nQueue state is held in memory.\n",
        generated_provenance=json.dumps({"review_digest": "a" * 64}),
    )
    source_id = result["source_ids"][0]
    proof = evidence.source_evidence(store, source_id)
    assert proof["source_kind"] == "agent_generated_document" and not proof["binding"]
    rows = store.query(
        "MATCH (s:Source {uid:$uid}) RETURN s.reviewed AS reviewed,s.binding AS binding,s.generated_provenance AS provenance",
        {"uid": source_id},
    )
    assert rows[0]["reviewed"] is True and rows[0]["binding"] is False
    evidence_folder = tmp_path.parent / (tmp_path.name + "-evidence")
    saved = evidence.register(evidence_folder, proof)
    with pytest.raises(ValueError, match="independent factual"):
        documentation.checked(
            state,
            repo["id"],
            evidence_folder,
            {
                "claims": [
                    {
                        "text": "Queue state is held in memory",
                        "support": [
                            {"evidence_id": saved["id"], "quote": "Queue state is held in memory."}
                        ],
                    }
                ]
            },
        )
