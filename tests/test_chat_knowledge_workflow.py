"""Chat workflow: required Graphify, automatic upload jobs, literal links and graph pages."""

import os
from dataclasses import asdict

import pytest
import yaml
from fastapi.testclient import TestClient
from test_integration import real as real  # noqa: PLC0414

from brain.app import enrichment, sources
from brain.app.evidence import code_evidence, register, verified_claims
from brain.app.server import create_app
from brain.app.state import State
from brain.config import Config
from brain.ingest.sync import sync


def test_graphify_failure_stops_repository_before_ready(tmp_path, monkeypatch):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    monkeypatch.setattr(sources, "clone_public", lambda *_: None)
    monkeypatch.setattr(state, "configure", lambda *_: state.base)
    monkeypatch.setattr(sources, "sync", lambda *_: {})
    monkeypatch.setattr(sources, "GraphStore", lambda *_: object())
    monkeypatch.setattr(sources, "git", lambda *_: "x.py\0")

    def fail(*_):
        raise ValueError("Graphify unavailable")

    monkeypatch.setattr(sources, "ingest_graphify", fail)
    sources.onboard(state, project["id"], history=False)
    assert state.get(project["id"])["status"] == "failed"
    assert state.get(project["id"])["error"] == "Graphify unavailable"


@pytest.mark.parametrize("fail_batch", [None, 1])
def test_automatic_document_batches_cover_all_sections_and_record_partial_failure(
    tmp_path, monkeypatch, fail_batch
):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository")
    job = state.create(
        "enrichment",
        project["id"],
        project=project["id"],
        sources=[str(i) for i in range(19)],
        status="queued",
    )
    seen = []

    def worker(state, uid, kind):
        child = state.get(uid, kind)
        seen.append(child["sources"])
        if len(seen) - 1 == fail_batch:
            state.update(uid, status="failed", error="Model unavailable")
        else:
            state.update(uid, status="complete", result={"nodes": 2, "relationships": 1})

    monkeypatch.setattr(enrichment, "run_enrichment", worker)
    enrichment.run_document_enrichment(state, job["id"])
    result = state.get(job["id"])
    assert all(len(batch) <= 8 for batch in seen)
    if fail_batch is None:
        assert [s for batch in seen for s in batch] == job["sources"]
        assert result["status"] == "complete" and result["result"]["batches"] == 3
    else:
        assert result["status"] == "failed" and result["result"]["batches"] == 1
        assert "sources remain searchable" in result["error"]
    enrichment.run_document_enrichment(state, job["id"])
    assert len(seen) == (3 if fail_batch is None else 2)  # no duplicate execution


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_upload_queues_graphify_connects_code_and_paginates_native_graph(
    real, tmp_path_factory, monkeypatch
):
    tmp_path = tmp_path_factory.mktemp("chat-artifacts")
    sync(real)
    state = State(tmp_path / "app", real.cfg, "fixture")
    project = state.create("repository", status="ready")
    state.folder(project["id"]).mkdir()
    config = asdict(real.cfg)
    config["repo_root"] = str(real.cfg.repo_root)
    (state.folder(project["id"]) / "brain.local.yaml").write_text(yaml.safe_dump(config))
    queued = []
    monkeypatch.setattr(
        "brain.app.server.run_document_enrichment", lambda _state, uid: queued.append(uid)
    )
    app = create_app(state, "token", "http://testserver")
    headers = {"Authorization": "Bearer token"}
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/repositories/{project['id']}/documents",
                headers=headers,
                json={
                    "filename": "design.md",
                    "text": "# Design\nPreserve earlier behavior in x.py.\n",
                },
            )
            assert response.status_code == 200, response.text
            receipt = response.json()
            assert receipt["code_links"] == 1
            assert receipt["enrichment"]["engine"] == "graphify"
            assert receipt["enrichment"]["sources"]
            links = real.query(
                "MATCH (d:Document)-[r:MENTIONS]->(f:File {repo_id:$repo}) RETURN r.quote AS quote,r.binding AS binding",
                {"repo": real.cfg.repo_id},
            )
            assert links == [{"quote": "x.py", "binding": False}]
            # No natural-language short-name guessing.
            sources.upload_document(state, project["id"], "other.md", "a should be different")
            assert (
                real.query(
                    "MATCH (d:Document)-[:MENTIONS]->(s:Symbol {repo_id:$repo}) RETURN s.uid AS uid",
                    {"repo": real.cfg.repo_id},
                )
                == []
            )
            for i in range(105):
                real.upsert(
                    "Document",
                    f"{real.cfg.repo_id}:page:{i:03}",
                    {"repo_id": real.cfg.repo_id, "current": True, "title": str(i)},
                )
            first_response = client.get(f"/api/repositories/{project['id']}/graph", headers=headers)
            assert first_response.status_code == 200, first_response.text
            first = first_response.json()
            second = client.get(
                f"/api/repositories/{project['id']}/graph?offset=100", headers=headers
            ).json()
            assert first["next_offset"] == 100 and second["offset"] == 100
            assert any(c["kind"] == "Document" and c["count"] >= 107 for c in first["counts"])
            display_counts = {c["kind"]: c["count"] for c in first["entity_counts"]}
            assert display_counts["UploadedSection"] >= 1
            # Unclassified extracted entities must not appear as document sections.
            assert display_counts["OtherEntity"] == 105
            assert "Document" not in display_counts
            overview = client.get(
                f"/api/repositories/{project['id']}/graph/overview", headers=headers
            )
            assert overview.status_code == 200, overview.text
            assert overview.json()["total_nodes"] == sum(c["count"] for c in first["counts"])
            assert any(
                g["key"] == "Document" and g["count"] >= 107 for g in overview.json()["groups"]
            )
            folder_view = client.get(
                f"/api/repositories/{project['id']}/graph/overview?grouping=folder", headers=headers
            )
            assert folder_view.status_code == 200, folder_view.text
            assert any(g["key"] == "(root)" for g in folder_view.json()["groups"])
            only_files = client.get(
                f"/api/repositories/{project['id']}/graph?kind=File", headers=headers
            )
            assert only_files.status_code == 200, only_files.text
            file_uid = next(
                n["id"]
                for n in only_files.json()["nodes"]
                if "File" in n["labels"] and n["label"] == "x.py"
            )
            cluster = client.get(
                f"/api/repositories/{project['id']}/graph?kind=File&context_neighbors=true",
                headers=headers,
            )
            assert cluster.status_code == 200, cluster.text
            cluster_data = cluster.json()
            assert 0 < cluster_data["context_count"] <= 50
            assert cluster_data["root_count"] == len(only_files.json()["nodes"])
            assert any("File" not in n["labels"] for n in cluster_data["nodes"])
            assert any(
                e["source"] == file_uid or e["target"] == file_uid for e in cluster_data["edges"]
            )
            assert all(
                n["id"] in {n["id"] for n in cluster_data["nodes"]}
                for n in only_files.json()["nodes"]
            )
            node = client.get(
                f"/api/repositories/{project['id']}/graph/node",
                params={"uid": file_uid},
                headers=headers,
            )
            assert node.status_code == 200, node.text
            assert node.json()["evidence"]["kind"] == "code"
            assert "def a" in node.json()["evidence"]["text"]
            assert (
                client.get(
                    f"/api/repositories/{project['id']}/graph/node",
                    params={"uid": "other-repo:private"},
                    headers=headers,
                ).status_code
                == 404
            )
            assert (
                client.get(f"/api/repositories/{project['id']}/graph/overview").status_code == 401
            )
            assert (
                client.get(
                    f"/api/repositories/{project['id']}/graph/overview?grouping=invalid",
                    headers=headers,
                ).status_code
                == 400
            )
            assert second["nodes"] and {
                n["id"] for n in first["nodes"] if "Source" not in n["labels"]
            }.isdisjoint(n["id"] for n in second["nodes"] if "Source" not in n["labels"])
            assert (
                client.get(
                    f"/api/repositories/{project['id']}/graph?offset=-1", headers=headers
                ).status_code
                == 400
            )
        assert queued == [receipt["enrichment"]["id"]]
        evidence = register(tmp_path / "proofs", code_evidence(real, "x.py", 1, 2))
        claims = verified_claims(
            real,
            tmp_path / "proofs",
            {
                "claims": [
                    {
                        "text": "b calls a",
                        "support": [{"evidence_id": evidence["id"], "quote": "def b(): a()"}],
                    }
                ]
            },
        )
        assert claims[0]["support"][0]["nodes"] == evidence["graph"]["nodes"]
    finally:
        app.state.workers.shutdown()


def test_code_links_reject_ambiguous_qualified_names_and_file_substrings():
    from brain.app.knowledge import link_sources

    class Store:
        cfg = type("Config", (), {"repo_id": "fixture"})()
        mentions = None

        def query(self, query, params):
            if "d.text AS text" in query:
                return [
                    {
                        "uid": "doc",
                        "text": "Use Duplicate.run in foo/x.py. Avoid notfoo/x.pyx",
                        "source": "source",
                    }
                ]
            if "labels(n) AS labels" in query:
                return [
                    {"uid": "a", "qualname": "Duplicate.run", "labels": ["Symbol"]},
                    {"uid": "b", "qualname": "Duplicate.run", "labels": ["Symbol"]},
                    {"uid": "file", "path": "foo/x.py", "labels": ["File"]},
                    {"uid": "substring", "path": "x.py", "labels": ["File"]},
                ]
            self.mentions = params["mentions"]

    store = Store()
    assert link_sources(store, ["source"])["code_links"] == 1
    assert store.mentions == [{"a": "doc", "b": "file", "source": "source", "quote": "foo/x.py"}]
