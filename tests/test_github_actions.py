"""Reviewed GitHub writes stay scoped, one-shot and credential-free."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from brain.app import github_actions as gh
from brain.app.server import create_app
from brain.app.state import State
from brain.config import Config

REAL_REQUEST = gh.request


@pytest.mark.asyncio
async def test_chat_tool_prepares_local_draft_but_cannot_publish(connected, tmp_path, monkeypatch):
    from brain.app.mcp import create_server

    state, project, calls, _ = connected
    turn = state.create("turn", project=project, status="running")
    monkeypatch.setenv("BRAIN_APP_BUDGET_DIR", str(tmp_path / "budget"))
    server = create_server(
        state.base, tmp_path / "evidence", app_state=state, project=project, turn=turn["id"]
    )
    async with Client(server) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert "draft_github_action" in names
        assert not any("publish" in name for name in names)
        result = await client.call_tool(
            "draft_github_action", {"kind": "issue", "title": "Fix", "body": "Details"}
        )
        assert result.data["status"] == "draft" and "Not published" in result.data["notice"]
        saved = state.get(result.data["id"], "github_action")
        assert saved["status"] == "draft" and saved["project"] == project
        assert state.get(turn["id"])["github_drafts"][0]["id"] == saved["id"]
        state.update(turn["id"], status="complete")
        result = await client.call_tool(
            "draft_github_action", {"kind": "issue", "title": "Fix", "body": "Details"}
        )
        assert result.data["status"] == "error"
    assert not any(method == "POST" for method, *_ in calls)


def test_only_chat_invocations_receive_local_github_drafting(connected, tmp_path):
    import json

    from brain.app.agent import command

    state, project, _, _ = connected
    for folder, expected in [(tmp_path / "turns" / "turn-id", True), (tmp_path / "plan", False)]:
        argv = command(state, project, folder)
        config = {
            arg.split("=", 1)[0]: json.loads(arg.split("=", 1)[1])
            for i, arg in enumerate(argv)
            if i and argv[i - 1] == "-c"
        }
        assert (
            "draft_github_action" in config["mcp_servers.company-brain.enabled_tools"]
        ) is expected
        assert ("mcp_servers.company-brain.env.BRAIN_APP_ROOT" in config) is expected


@pytest.fixture
def connected(tmp_path, monkeypatch):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    repo = state.create("repository", url="https://github.com/example/project", status="ready")
    calls = []
    control = {"login": "alice", "fail_write": False, "has_issues": True}

    def request(method, endpoint, payload=None):
        calls.append((method, endpoint, payload))
        if endpoint == "user":
            return {"login": control["login"]}
        if method == "GET" and endpoint == "repos/example/project":
            return {
                "id": 123,
                "full_name": "example/project",
                "default_branch": "main",
                "has_issues": control["has_issues"],
            }
        if method == "GET" and endpoint == "repos/example/project/issues/42":
            return {"number": 42}
        if method == "POST":
            if control["fail_write"]:
                raise gh.GitHubConnectionError("request timed out")
            suffix = "pull/43" if endpoint.endswith("/pulls") else "issues/43"
            if endpoint.endswith("/comments"):
                suffix = "issues/42#issuecomment-7"
            return {"html_url": "https://github.com/example/project/" + suffix}
        raise AssertionError((method, endpoint))

    monkeypatch.setattr(gh, "request", request)
    return state, repo["id"], calls, control


@pytest.mark.parametrize(
    "kind,fields,endpoint,payload",
    [
        (
            "issue",
            {"title": "Recover ingestion"},
            "/issues",
            {"title": "Recover ingestion", "body": "Reviewed evidence"},
        ),
        (
            "pull_request",
            {"title": "Repair", "head": "alice:recovery"},
            "/pulls",
            {
                "title": "Repair",
                "body": "Reviewed evidence",
                "head": "alice:recovery",
                "base": "main",
                "draft": True,
            },
        ),
        ("comment", {"number": 42}, "/issues/42/comments", {"body": "Reviewed evidence"}),
    ],
)
def test_preview_is_read_only_and_publish_uses_exact_reviewed_payload(
    connected, kind, fields, endpoint, payload
):
    state, project, calls, _ = connected
    draft = gh.preview(state, project, {"kind": kind, "body": "Reviewed evidence", **fields})
    assert draft["payload"] == payload and draft["status"] == "draft"
    assert all(method == "GET" for method, *_ in calls)
    result = gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert result["status"] == "published" and result["url"].startswith(
        "https://github.com/example/project/"
    )
    assert calls[-1] == ("POST", "repos/example/project" + endpoint, payload)
    gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert sum(method == "POST" for method, *_ in calls) == 1


@pytest.mark.parametrize("change", ["digest", "payload", "account", "project"])
def test_publish_rejects_stale_or_cross_project_approval(connected, change):
    state, project, calls, control = connected
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    digest = draft["consent_digest"]
    if change == "digest":
        digest = "0" * 64
    if change == "payload":
        state.update(draft["id"], payload={"title": "Different", "body": "Changed"})
    if change == "account":
        control["login"] = "bob"
    if change == "project":
        project = "different-project"
    with pytest.raises((ValueError, KeyError)):
        gh.publish(state, project, draft["id"], digest)
    assert not any(method == "POST" for method, *_ in calls)


def test_timeout_is_unknown_and_never_automatically_retried(connected):
    state, project, calls, control = connected
    draft = gh.preview(state, project, {"kind": "comment", "number": 42, "body": "Details"})
    control["fail_write"] = True
    with pytest.raises(ValueError, match="outcome is unknown"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert state.get(draft["id"])["status"] == "unknown"
    with pytest.raises(ValueError, match="already attempted"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert sum(method == "POST" for method, *_ in calls) == 1


def test_disabled_issues_block_preview_without_writing(connected):
    state, project, calls, control = connected
    control["has_issues"] = False
    with pytest.raises(ValueError, match="Issues are disabled.*No issue was submitted"):
        gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    assert state.list("github_action", project) == []
    assert not any(method == "POST" for method, *_ in calls)


def test_issues_disabled_after_preview_block_publication_without_writing(connected):
    state, project, calls, control = connected
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    control["has_issues"] = False
    with pytest.raises(ValueError, match="Issues are disabled"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert state.get(draft["id"])["status"] == "draft"
    assert not any(method == "POST" for method, *_ in calls)


@pytest.mark.parametrize(
    "kind,fields",
    [("comment", {"number": 42}), ("pull_request", {"title": "Fix", "head": "fix"})],
)
def test_disabled_issues_do_not_block_prs_or_comments(connected, kind, fields):
    state, project, calls, control = connected
    control["has_issues"] = False
    draft = gh.preview(state, project, {"kind": kind, "body": "Details", **fields})
    assert gh.publish(state, project, draft["id"], draft["consent_digest"])["status"] == "published"
    assert sum(method == "POST" for method, *_ in calls) == 1


def test_explicit_github_rejection_is_saved_and_never_retried(connected, monkeypatch):
    state, project, calls, _ = connected
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    original = gh.request

    def rejected(method, endpoint, payload=None):
        if method == "POST":
            calls.append((method, endpoint, payload))
            raise gh.GitHubRejectedError("GitHub denied this operation (HTTP 403).")
        return original(method, endpoint, payload)

    monkeypatch.setattr(gh, "request", rejected)
    with pytest.raises(gh.GitHubRejectedError, match="HTTP 403"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    saved = state.get(draft["id"])
    assert saved["status"] == "rejected" and "HTTP 403" in saved["error"]
    with pytest.raises(ValueError, match="already attempted"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert sum(method == "POST" for method, *_ in calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 410, 415, 422, 429])
def test_cli_distinguishes_structured_rejection_without_exposing_remote_text(monkeypatch, status):
    monkeypatch.setattr(
        gh.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=1,
            stdout=__import__("json").dumps({"status": str(status), "message": "secret-token"}),
            stderr="secret-token",
        ),
    )
    with pytest.raises(gh.GitHubRejectedError) as error:
        gh.request("POST", "repos/example/project/issues", {"title": "Fix", "body": "Details"})
    assert f"HTTP {status}" in str(error.value)
    assert "secret-token" not in str(error.value)


@pytest.mark.parametrize("output", ['{"status":"500"}', '{"status":"408"}', "bad response"])
def test_cli_ambiguous_failures_remain_unknown(connected, monkeypatch, output):
    state, project, _calls, _ = connected
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    original = gh.request

    def post_using_cli(method, endpoint, payload=None):
        return original(method, endpoint, payload) if method == "GET" else cli(method, endpoint, payload)

    # The fixture replaces request; retain the actual CLI adapter for the POST.
    cli = REAL_REQUEST
    monkeypatch.setattr(gh, "request", post_using_cli)
    monkeypatch.setattr(
        gh.subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=1, stdout=output)
    )
    with pytest.raises(ValueError, match="outcome is unknown"):
        gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert state.get(draft["id"])["status"] == "unknown"


def test_repository_url_casing_uses_github_canonical_identity(connected, monkeypatch):
    state, project, _, _ = connected
    calls = []

    def request(method, endpoint, payload=None):
        calls.append((method, endpoint))
        if endpoint == "user":
            return {"login": "alice"}
        if method == "GET":
            return {"id": 123, "full_name": "Example/Project", "default_branch": "main"}
        return {"html_url": "https://github.com/Example/Project/issues/5"}

    monkeypatch.setattr(gh, "request", request)
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})
    result = gh.publish(state, project, draft["id"], draft["consent_digest"])
    assert result["status"] == "published"
    assert calls[-1] == ("POST", "repos/Example/Project/issues")


def test_concurrent_publish_retries_create_only_one_remote_item(connected):
    state, project, calls, _ = connected
    draft = gh.preview(state, project, {"kind": "issue", "title": "Fix", "body": "Details"})

    def publish(_):
        try:
            return gh.publish(state, project, draft["id"], draft["consent_digest"])["status"]
        except ValueError:
            return "already_attempted"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(publish, range(4)))
    assert "published" in results
    assert sum(method == "POST" for method, *_ in calls) == 1


@pytest.mark.parametrize(
    "head", ["../other", "-bad", "main?x=y", "main;echo bad", "a//b", "bad.lock"]
)
def test_pr_branch_is_literal_and_cannot_inject_routes(connected, head):
    state, project, calls, _ = connected
    with pytest.raises(ValueError, match="literal existing"):
        gh.preview(
            state,
            project,
            {"kind": "pull_request", "title": "Fix", "body": "Details", "head": head},
        )
    assert not any(method == "POST" for method, *_ in calls)


def test_api_requires_session_and_only_publishes_after_review(connected):
    state, project, calls, _ = connected
    app = create_app(state, "token", "http://testserver")
    try:
        with TestClient(app) as client:
            route = f"/api/repositories/{project}/github/actions"
            assert client.get("/api/github/connection").status_code == 401
            headers = {"Authorization": "Bearer token"}
            draft = client.post(
                route, headers=headers, json={"kind": "issue", "title": "Fix", "body": "Details"}
            )
            assert draft.status_code == 201
            assert not any(method == "POST" for method, *_ in calls)
            value = draft.json()
            assert (
                client.post(
                    route + "/" + value["id"] + "/publish",
                    headers=headers,
                    json={"consent_digest": value["consent_digest"]},
                ).json()["status"]
                == "published"
            )
            assert client.get(route, headers=headers).json()["items"][0]["status"] == "published"
    finally:
        app.state.workers.shutdown(wait=True)


def test_cli_transports_body_as_json_stdin_and_never_echoes_credentials(monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0, stdout='{"html_url":"https://github.com/example/project/issues/1"}'
        )

    monkeypatch.setattr(gh.subprocess, "run", run)
    body = "Literal `code` and $(not-a-command)\nNext line"
    gh.request("POST", "repos/example/project/issues", {"body": body})
    argv, kwargs = calls[0]
    assert argv[-2:] == ["--input", "-"] and body not in argv
    assert "shell" not in kwargs
    assert __import__("json").loads(kwargs["input"])["body"] == body
    monkeypatch.setattr(
        gh.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stdout="", stderr="secret-token"),
    )
    with pytest.raises(gh.GitHubConnectionError) as error:
        gh.request("GET", "user")
    assert "secret-token" not in str(error.value)
