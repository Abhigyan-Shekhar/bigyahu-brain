"""Persistent activity stays scoped and never turns a waiting approval into live work."""
from fastapi.testclient import TestClient

from brain.app.live_work import snapshot
from brain.app.server import create_app
from brain.app.state import State
from brain.config import Config


def test_workspace_activity_scope_and_auth(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "test")
    repo = state.create("repository", status="ready")
    other = state.create("repository", status="ready")
    session = state.create("session", repo["id"])
    state.create("turn", session["id"], status="running", question="Find issue", stage="Reading sources")
    action = state.create("action", repo["id"], status="running", objective="Fix issue", secret="never return", plan={"private": "hidden"})
    state.create("action", repo["id"], status="awaiting_approval", objective="Waiting")
    state.create("action", other["id"], status="running", objective="OTHER_PROJECT")
    for kind in ("enrichment", "workflow", "documentation_draft", "documentation_patch"):
        state.create(kind, repo["id"], status="queued")
    result = snapshot(state, repo["id"])
    assert len(result["items"]) == 6
    assert not result["truncated"]
    assert "OTHER_PROJECT" not in str(result)
    assert "secret" not in str(result) and "private" not in str(result)
    state.update(action["id"], status="complete")
    assert len(snapshot(state, repo["id"])["items"]) == 5
    with TestClient(create_app(state, "token", "http://testserver", assets=tmp_path / "unbuilt")) as client:
        route = f'/api/repositories/{repo["id"]}/activity'
        assert client.get(route).status_code == 401
        assert client.get(route, headers={"Authorization": "Bearer token"}).status_code == 200
        assert client.get('/api/repositories/missing/activity', headers={"Authorization": "Bearer token"}).status_code == 404


def test_activity_snapshot_discloses_truncation(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "test")
    repo = state.create("repository", status="running", stage="Indexing")
    for index in range(52):
        state.create("action", repo["id"], status="running", objective=f"Task {index}")
    result = snapshot(state, repo["id"])
    assert len(result["items"]) == 50
    assert result["truncated"]
    assert result["items"][0]["kind"] == "repository"
