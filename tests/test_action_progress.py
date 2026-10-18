"""Safe activity projection must never return model prose or tool arguments."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from brain.app.actions import action_progress, validate_plan


def test_activity_projects_only_known_tool_events(tmp_path):
    state = SimpleNamespace(folder=lambda _: tmp_path)
    trace = tmp_path / "actions" / "action" / "plan" / "trace.jsonl"
    trace.parent.mkdir(parents=True)
    events = [
        {"type": "item.completed", "item": {"type": "reasoning", "text": "hidden"}},
        {
            "type": "item.completed",
            "item": {"type": "mcp_tool_call", "tool": "not_allowed", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "read_code",
                "status": "completed",
                "arguments": "secret",
                "result": "source text",
            },
        },
        {"type": "item.started", "item": {"type": "mcp_tool_call", "tool": "check_change"}},
        {"item": None},
        [],
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events) + '\n{"partial":', encoding="utf-8")
    action = {
        "id": "action",
        "project": "project",
        "phase": "planning",
        "status": "running",
        "phase_started_at": "2026-10-18T00:00:00+00:00",
        "phase_finished_at": "2026-10-18T00:01:30+00:00",
    }
    result = action_progress(state, action)
    assert result["completed_tools"] == [{"tool": "read_code", "status": "completed"}]
    assert result["current_tool"] == "check_change"
    assert result["elapsed_seconds"] == 90
    assert "secret" not in json.dumps(result) and "hidden" not in json.dumps(result)
    action["status"] = "failed"
    action.pop("phase_finished_at")
    assert action_progress(state, action)["elapsed_seconds"] is None
    assert action_progress(state, action)["current_tool"] is None


def test_missing_historical_trace_does_not_invent_activity(tmp_path):
    result = action_progress(
        SimpleNamespace(folder=lambda _: tmp_path), {"id": "old", "project": "project"}
    )
    assert result["elapsed_seconds"] is None
    assert result["completed_tools"] == []


def test_annotated_model_path_explains_retry(tmp_path):
    with pytest.raises(ValueError, match="literal.*without annotations"):
        validate_plan(
            {"summary": "Fix conversion", "files": ["tests/test_timed.py (new)"]}, tmp_path
        )


def test_investigation_activity_uses_only_safe_recorded_tools(tmp_path):
    from brain.app.activity import investigation_progress

    state = SimpleNamespace(folder=lambda _: tmp_path)
    result = investigation_progress(
        state,
        {
            "id": "turn",
            "project": "repo",
            "status": "complete",
            "tools": [
                {"tool": "read_code", "status": "completed", "arguments": "not public"},
                {"tool": "memory_search", "status": "unexpected model status"},
                {"tool": "private_reasoning", "status": "completed"},
            ],
        },
    )
    assert result["completed_count"] == 2
    assert result["completed_tools"][1]["status"] == "unverified"
    assert "not public" not in str(result)
    assert result["elapsed_seconds"] is None


def test_repair_progress_uses_current_attempt_trace(tmp_path):
    state = SimpleNamespace(folder=lambda _: tmp_path)
    folder = tmp_path / "actions" / "action" / "plan"
    (folder / "repair").mkdir(parents=True)
    for path, tool in [(folder, "search_history"), (folder / "repair", "repository_files")]:
        (path / "trace.jsonl").write_text(
            json.dumps({"type": "item.started", "item": {"type": "mcp_tool_call", "tool": tool}})
        )
    action = {
        "id": "action",
        "project": "project",
        "phase": "planning",
        "status": "running",
        "plan_attempt": 2,
    }
    assert action_progress(state, action)["current_tool"] == "repository_files"
    action.pop("plan_attempt")
    assert action_progress(state, action)["current_tool"] == "search_history"
