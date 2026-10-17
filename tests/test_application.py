"""Application boundaries and real graph-backed evidence, without model/network calls."""

import json
from dataclasses import replace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_integration import real as real  # noqa: PLC0414

from brain.app.agent import command
from brain.app.evidence import code_evidence, register, source_evidence, verified_claims
from brain.app.server import create_app
from brain.app.sources import repository_url, upload_document
from brain.app.state import State
from brain.config import Config
from brain.ingest.sync import sync


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/repo",
        "https://github.com.evil.test/org/repo",
        "https://github.com/org/repo/tree/main",
        "https://github.com/a/../b",
        "https://user:secret@github.com/a/b",
        "ssh://github.com/a/b",
        "https://github.com/-a/b",
    ],
)
def test_repository_url_rejects_unsafe_inputs(url):
    with pytest.raises(ValueError):
        repository_url(url)


def test_repository_url_normalizes_clone_suffix():
    assert (
        repository_url("https://github.com/pallets/itsdangerous.git/")
        == "https://github.com/pallets/itsdangerous"
    )


def test_local_auth_origin_and_no_unapproved_action_api(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "example-model")
    app = create_app(state, "fixture-token", "http://testserver", assets=tmp_path / "unbuilt")
    try:
        with TestClient(app) as client:
            assert client.get("/api/repositories").status_code == 401
            headers = {"Authorization": "Bearer fixture-token"}
            assert client.get("/api/repositories", headers=headers).json() == []
            assert (
                client.get(
                    "/api/repositories", headers={**headers, "Origin": "https://evil.test"}
                ).status_code
                == 403
            )
            assert (
                client.get(
                    "/api/repositories", headers={**headers, "Host": "evil.test"}
                ).status_code
                == 403
            )
            assert (
                client.get("/api/status", headers=headers).json()["mode"]
                == "read_only_investigation"
            )
            assert client.post("/api/actions/approve", headers=headers, json={}).status_code == 404
            assert (
                client.post(
                    "/api/repositories", headers=headers, json={"url": "file:///tmp/repo"}
                ).status_code
                == 400
            )
    finally:
        app.state.workers.shutdown()


def test_restarted_job_is_failed_and_readonly_runner_has_no_shell(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "example-model")
    project = state.create("repository", status="running")
    state = State(state.root, state.base, state.model)
    assert state.get(project["id"])["status"] == "failed"
    args = command(state, project["id"], tmp_path / "turn")
    assert args[args.index("-s") + 1] == "read-only"
    assert "--ignore-user-config" in args
    for feature in ("shell_tool", "unified_exec", "multi_agent", "plugins", "apps"):
        assert args[args.index(feature) - 1] == "--disable"
    settings = dict(arg.split("=", 1) for i, arg in enumerate(args) if i and args[i - 1] == "-c")
    tools = json.loads(settings["mcp_servers.company-brain.enabled_tools"])
    assert "remember" not in tools and "memory_propose" not in tools
    assert settings["approval_policy"] == '"never"'


def test_unready_repository_cannot_start_session(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "example-model")
    project = state.create("repository", status="queued")
    app = create_app(state, "token", "http://testserver", assets=tmp_path / "unbuilt")
    try:
        with TestClient(app) as client:
            result = client.post(
                f"/api/repositories/{project['id']}/sessions",
                headers={"Authorization": "Bearer token"},
                json={},
            )
            assert result.status_code == 409
    finally:
        app.state.workers.shutdown()


@pytest.mark.integration
@pytest.mark.skipif(__import__("os").getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_live_source_proofs_claim_rejection_upload_and_citation_endpoint(real, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("application-artifacts")
    sync(real)
    proof = code_evidence(real, "x.py", 1, 2)
    assert proof["text"] == "def a(): pass\ndef b(): a()\n"
    assert any(e["relation"] == "CONTAINS" for e in proof["graph"]["edges"])
    folder = tmp_path / "evidence"
    registered = register(folder, proof)
    output = {
        "claims": [
            {
                "text": "The function a is defined in x.py.",
                "support": [{"evidence_id": registered["id"], "quote": "def a(): pass"}],
            }
        ]
    }
    assert len(verified_claims(real, folder, output)) == 1
    output["claims"][0]["support"][0]["quote"] = "Invented source text"
    with pytest.raises(ValueError):
        verified_claims(real, folder, output)
    output["claims"][0]["support"][0].update(evidence_id="f" * 24, quote="def a(): pass")
    with pytest.raises(FileNotFoundError):
        verified_claims(real, folder, output)
    with pytest.raises(ValueError):
        code_evidence(real, "../outside.py")
    # Application config gets its own tenant while remaining on this test's isolated server.
    state = State(tmp_path / "app", real.cfg, "example-model")
    project = state.create("repository", status="ready")
    work = state.folder(project["id"])
    work.mkdir()
    values = replace(real.cfg, repo_root=real.cfg.repo_root)
    from dataclasses import asdict

    import yaml

    config = asdict(values)
    config["repo_root"] = str(values.repo_root)
    (work / "brain.local.yaml").write_text(yaml.safe_dump(config))
    # The production upload folder is outside its managed checkout.
    uploaded = upload_document(
        state, project["id"], "retry-policy.md", "# Retry policy\nUse exponential backoff.\n"
    )
    assert uploaded["sections"] == 1
    sources = real.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'app_upload'})-[:SUPPORTS]->(s:Source) RETURN s.uid AS uid",
        {"repo": real.cfg.repo_id},
    )
    # Move fixture upload bytes to the path used by the source resolver (real checkout's parent).
    import shutil

    destination = real.cfg.repo_root.parent / "uploads"
    destination.mkdir(exist_ok=True)
    shutil.copyfile(work / "uploads" / uploaded["digest"], destination / uploaded["digest"])
    source = source_evidence(real, sources[0]["uid"])
    assert source["text"] == "# Retry policy\nUse exponential backoff.\n"
    assert source["graph"]["edges"][0]["relation"] == "SUPPORTS"
    turn = state.create(
        "turn",
        project=project["id"],
        status="complete",
        claims=[{"support": [{"evidence_id": registered["id"]}]}],
    )
    target = work / "turns" / turn["id"] / "evidence"
    target.mkdir(parents=True)
    (target / (registered["id"] + ".json")).write_text(json.dumps(registered))
    app = create_app(state, "token", "http://testserver", assets=tmp_path / "unbuilt")
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            assert (
                client.get(
                    f"/api/turns/{turn['id']}/evidence/{registered['id']}", headers=headers
                ).status_code
                == 200
            )
            assert (
                client.get(
                    f"/api/turns/{turn['id']}/evidence/{'f' * 24}", headers=headers
                ).status_code
                == 404
            )
            (real.cfg.repo_root / "x.py").write_text("def changed(): pass\n")
            assert (
                client.get(
                    f"/api/turns/{turn['id']}/evidence/{registered['id']}", headers=headers
                ).status_code
                == 400
            )
    finally:
        app.state.workers.shutdown()
