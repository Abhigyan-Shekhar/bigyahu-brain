"""Bounded retrieval, fresh evidence reuse, accurate activity and actual write previews."""

import json
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from brain.app import actions, evidence
from brain.app.action_mcp import create_server
from brain.app.activity import tool_activity
from brain.app.live_changes import read_changes
from brain.app.retrieval import RetrievalBudget, retrieval_stats
from brain.app.state import State
from brain.app.timing import finish_stage, set_stage, stage_progress
from brain.config import Config
from brain.memory import digest


@pytest.mark.asyncio
async def test_retrieval_limits_block_work_and_survive_server_restart(tmp_path):
    budget = RetrievalBudget(tmp_path)
    executed = []

    async def call_next(context):
        executed.append(context.message.name)
        return {"result": "real lookup"}

    def context(name, q):
        return SimpleNamespace(message=SimpleNamespace(name=name, arguments={"query": q}))

    for _ in range(2):
        await budget.on_call_tool(context("search_code", "same"), call_next)
    with pytest.raises(ToolError, match="Identical lookup"):
        await budget.on_call_tool(context("search_code", "same"), call_next)
    for i in range(6):
        await budget.on_call_tool(context("get_context", str(i)), call_next)
    with pytest.raises(ToolError, match="context search budget"):
        await budget.on_call_tool(context("get_context", "extra"), call_next)
    # Reconnect/repair cannot reset the action's work budget.
    budget = RetrievalBudget(tmp_path)
    for i in range(12):
        await budget.on_call_tool(context("read_code", str(i)), call_next)
    with pytest.raises(ToolError, match="Retrieval budget"):
        await budget.on_call_tool(context("read_code", "extra"), call_next)
    stats = retrieval_stats(tmp_path)
    assert len(executed) == stats["used"] == stats["limit"] == 20
    assert stats["context_used"] == 6 and stats["blocked"] == 3
    assert "query" not in json.dumps(stats) and "fingerprints" not in stats


def test_newest_trace_window_and_review_phase_do_not_keep_stale_retrieval_spinner(tmp_path):
    trace = tmp_path / "trace.jsonl"
    start = {
        "type": "item.started",
        "item": {"id": "one", "type": "mcp_tool_call", "tool": "get_context"},
    }
    done = {"type": "item.completed", "item": {**start["item"], "status": "completed"}}
    trace.write_text(
        json.dumps(start)
        + "\n"
        + json.dumps({"reasoning": "x" * 2100000})
        + "\n"
        + json.dumps(done)
        + "\n"
    )
    result = tool_activity(trace, True)
    assert result["trace_bounded"] and result["current_tool"] is None
    assert result["completed_count"] == 1
    folder = tmp_path / "actions" / "a" / "plan"
    folder.mkdir(parents=True)
    (folder / "trace.jsonl").write_text(json.dumps(start))
    value = {
        "id": "a",
        "project": "p",
        "status": "running",
        "phase": "planning",
        "activity_phase": "review",
        "stage": "Reviewing plan claims and proposed action",
    }
    assert (
        actions.action_progress(SimpleNamespace(folder=lambda _: tmp_path), value)["current_tool"]
        is None
    )


def test_parallel_tool_completion_keeps_other_inflight_tool(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        "\n".join(
            json.dumps(
                {
                    "type": typ,
                    "item": {
                        "id": uid,
                        "type": "mcp_tool_call",
                        "tool": tool,
                        "status": "completed",
                    },
                }
            )
            for typ, uid, tool in [
                ("item.started", "a", "get_context"),
                ("item.started", "b", "read_code"),
                ("item.completed", "a", "get_context"),
            ]
        )
    )
    assert tool_activity(trace, True)["current_tool"] == "read_code"


def test_evidence_reuse_rechecks_access_and_content_before_minting_new_run_ids(
    tmp_path, monkeypatch
):
    source, destination = tmp_path / "old", tmp_path / "new"
    proof = {
        "kind": "memory",
        "ref": {},
        "title": "Checked lesson",
        "text": "Preserve signatures",
        "digest": digest("Preserve signatures"),
        "revision": "sha",
        "graph": {"nodes": [], "edges": []},
    }
    item = evidence.register(source, proof)
    claims = [{"support": [{"evidence_id": item["id"]}]}]
    monkeypatch.setattr(evidence, "resolve", lambda *_: proof)
    result = evidence.reuse_evidence(None, source, destination, claims)
    assert len(result) == 1 and (destination / (item["id"] + ".json")).exists()
    monkeypatch.setattr(evidence, "resolve", lambda *_: {**proof, "digest": "changed"})
    assert evidence.reuse_evidence(None, source, tmp_path / "changed", claims) == []

    def revoked(*_):
        raise PermissionError("Memory revoked")

    monkeypatch.setattr(evidence, "resolve", revoked)
    assert evidence.reuse_evidence(None, source, tmp_path / "revoked", claims) == []
    assert not (tmp_path / "revoked").exists()


def test_stage_boundaries_are_persisted_and_closed(tmp_path):
    state = State(tmp_path / "state", Config(tmp_path, "fixture"), "fixture")
    action = state.create("action", status="running")
    set_stage(state, action["id"], "retrieval", "Investigating")
    set_stage(state, action["id"], "review", "Reviewing")
    stages = stage_progress(state.get(action["id"]))
    assert [stage["active"] for stage in stages] == [False, True]
    assert all(stage["seconds"] >= 0 for stage in stages)
    finish_stage(state, action["id"])
    assert not any(stage["active"] for stage in stage_progress(state.get(action["id"])))


@pytest.mark.asyncio
async def test_actual_editor_writes_emit_cumulative_diff_and_explanation_only_after_success(
    tmp_path,
):
    work = tmp_path / "work"
    work.mkdir()
    (work / "x.py").write_text("value = 1\n")
    log = tmp_path / "editor" / "changes.jsonl"
    server = create_server(work, ["x.py", "test_x.py"], events=log)
    async with Client(server) as client:
        await client.call_tool("read_file", {"path": "x.py"})
        assert not log.exists()
        await client.call_tool(
            "write_file",
            {
                "path": "x.py",
                "text": "value = 2\n",
                "expected_digest": digest("stale"),
                "explanation": "Rejected stale write",
            },
        )
        assert not log.exists()
        await client.call_tool(
            "write_file",
            {
                "path": "x.py",
                "text": "value = 2\n",
                "expected_digest": digest("value = 1\n"),
                "explanation": "Apply approved normalization",
            },
        )
        preview = read_changes(log, ["x.py", "test_x.py"])
        assert len(preview["files"]) == 1 and "+value = 2" in preview["files"][0]["diff"]
        await client.call_tool(
            "write_file",
            {
                "path": "x.py",
                "text": "value = 3\n",
                "expected_digest": digest("value = 2\n"),
                "explanation": "Handle the approved edge case",
            },
        )
        latest = read_changes(log, ["x.py"])["files"][0]
        assert "-value = 1" in latest["diff"] and "+value = 3" in latest["diff"]
        assert "+value = 2" not in latest["diff"] and latest["additions"] == 1
        assert latest["explanation"] == "Handle the approved edge case"
    action = {"phase": "planning", "plan": {"files": ["x.py"]}}
    assert actions.live_changes(None, action)["files"] == []
    assert read_changes(log, ["other.py"])["files"] == []


def test_diff_preview_handles_missing_newline_and_incomplete_log_records(tmp_path):
    from brain.app.live_changes import record_change

    log = tmp_path / "changes.jsonl"
    log.write_text(json.dumps({"path": "x.py", "diff": "bad", "explanation": ""}) + "\n")
    assert read_changes(log, ["x.py"])["files"] == []
    record_change(log, "x.py", "old", "new", "Replace value", digest("new"))
    result = read_changes(log, ["x.py"])["files"][0]
    assert "-old\n\\ No newline at end of file\n+new\n" in result["diff"]
    assert result["additions"] == result["deletions"] == 1
