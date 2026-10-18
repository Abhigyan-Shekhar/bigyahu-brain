"""Stream boundaries, terminal delivery and evidence-backed alert metadata."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from brain.app import evidence, relevance
from brain.app.findings import validate_finding
from brain.app.server import create_app
from brain.app.state import State
from brain.app.streaming import snapshots
from brain.config import Config
from brain.memory import digest


def finding(**changes):
    return {
        "title": "Untrusted command reaches shell",
        "severity": "high",
        "category": "security",
        "location": {"path": "unsafe.py", "line": 10},
        "recommendation": "Use an argument vector without a shell",
        **changes,
    }


@pytest.mark.asyncio
async def test_stream_delivers_changed_state_then_terminal_and_omits_unchanged():
    request = SimpleNamespace(is_disconnected=lambda: disconnected())

    async def disconnected():
        return False

    values = iter(
        [
            {"status": "running", "stage": "Checking"},
            {"status": "running", "stage": "Checking"},
            {"status": "complete", "claims": []},
        ]
    )
    events = [
        event async for event in snapshots(request, lambda: next(values), terminal=True, interval=0)
    ]
    assert len(events) == 2
    assert '"status":"complete"' in events[-1]


@pytest.mark.asyncio
async def test_disconnected_stream_does_not_keep_reading_job():
    async def disconnected():
        return True

    events = [
        event
        async for event in snapshots(
            SimpleNamespace(is_disconnected=disconnected),
            lambda: pytest.fail("read after disconnect"),
            interval=0,
        )
    ]
    assert events == []


def test_event_endpoints_require_auth_and_deliver_terminal_state_without_trace_prose(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository")
    turn = state.create("turn", project=project["id"], status="complete", tools=[], claims=[])
    action = state.create(
        "action", project=project["id"], status="failed", phase="planning", error="Review rejected"
    )
    trace = state.folder(project["id"]) / "actions" / action["id"] / "plan" / "trace.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "tool": "read_code",
                    "status": "completed",
                    "arguments": "PRIVATE_ARGUMENT",
                    "result": "PRIVATE_RESULT",
                },
            }
        )
    )
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    try:
        with TestClient(app) as client:
            for path in (f"/api/turns/{turn['id']}/events", f"/api/actions/{action['id']}/events"):
                assert client.get(path).status_code == 401
                response = client.get(path, headers={"Authorization": "Bearer token"})
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["cache-control"] == "no-store"
                assert "event: snapshot" in response.text
                assert "PRIVATE_" not in response.text
            assert (
                client.get(
                    "/api/turns/missing/events", headers={"Authorization": "Bearer token"}
                ).status_code
                == 404
            )
    finally:
        app.state.workers.shutdown()


def test_finding_metadata_is_in_reviewed_claim_and_current_code_location_is_checked(
    tmp_path, monkeypatch
):
    proof = {
        "kind": "code",
        "ref": {"path": "unsafe.py", "start": 8, "end": 12},
        "title": "unsafe.py:8–12",
        "text": "shell=True",
        "digest": digest("shell=True"),
        "revision": "sha",
        "graph": {"nodes": [], "edges": []},
    }
    saved = evidence.register(tmp_path, proof)
    monkeypatch.setattr(evidence, "resolve", lambda *_: proof)
    output = {
        "claims": [
            {
                "text": "Untrusted input reaches a shell",
                "finding": finding(),
                "support": [{"evidence_id": saved["id"], "quote": "shell=True"}],
            }
        ]
    }
    checked = evidence.verified_claims(None, tmp_path, output)
    assert checked[0]["finding"]["severity"] == "high"

    def review(prompt, *_):
        assert "assess its title, severity" in prompt
        assert "Use an argument vector" in prompt
        return {
            "assessments": [{"claim": 0, "verdict": "unsupported", "reason": "No input flow shown"}]
        }

    monkeypatch.setattr(relevance, "structured_extract", review)
    assert (
        relevance.assess("Review security", checked, tmp_path, "fixture")[0]["verdict"]
        == "unsupported"
    )
    output["claims"][0]["finding"]["location"]["line"] = 500
    with pytest.raises(ValueError, match="cited current code"):
        evidence.verified_claims(None, tmp_path, output)


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "catastrophic"},
        {"category": "guess"},
        {"title": ""},
        {"location": {"path": "other.py", "line": 10}},
        {"recommendation": "x" * 2001},
    ],
)
def test_invalid_findings_cannot_be_published(changes):
    with pytest.raises(ValueError):
        validate_finding(finding(**changes), [])
    assert validate_finding(finding(location=None), [])["location"] is None


@pytest.mark.parametrize("verdict", ["supported", "unsupported"])
def test_only_reviewed_supported_finding_is_published(tmp_path, monkeypatch, verdict):
    from brain.app import agent

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    session = state.create("session", project["id"])
    turn = state.create(
        "turn", session["id"], project=project["id"], question="Review security", status="queued"
    )
    monkeypatch.setattr(agent, "GraphStore", lambda *_: None)
    monkeypatch.setattr(state, "config", lambda *_: state.base)
    monkeypatch.setattr(agent.subprocess, "check_output", lambda *_a, **_k: "fixture-cli")
    proof = {
        "kind": "code",
        "ref": {"path": "unsafe.py", "start": 8, "end": 12},
        "title": "unsafe.py:10",
        "text": "shell=True",
        "digest": digest("shell=True"),
        "revision": "sha",
        "graph": {"nodes": [], "edges": []},
    }
    monkeypatch.setattr(evidence, "resolve", lambda *_: proof)

    def execute(args, **kwargs):
        from pathlib import Path

        run = Path(args[args.index("-o") + 1]).parent
        saved = evidence.register(run / "evidence", proof)
        (run / "answer.json").write_text(
            json.dumps(
                {
                    "limitations": [],
                    "claims": [
                        {
                            "text": "Untrusted input reaches shell",
                            "finding": finding(),
                            "support": [{"evidence_id": saved["id"], "quote": "shell=True"}],
                        }
                    ],
                }
            )
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(agent.subprocess, "run", execute)
    monkeypatch.setattr(
        agent, "assess", lambda *_: [{"claim": 0, "verdict": verdict, "reason": "Evidence review"}]
    )
    agent.run_turn(state, project["id"], session["id"], turn["id"])
    result = state.get(turn["id"])
    assert result["status"] == "complete"
    assert bool(result["claims"]) == (verdict == "supported")
    if result["claims"]:
        assert result["claims"][0]["finding"]["severity"] == "high"
