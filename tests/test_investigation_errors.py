"""Investigation failures expose a useful category without leaking CLI diagnostics."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from brain.app import agent
from brain.app.state import State
from brain.config import Config


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("This content was flagged for possible cybersecurity risk.", "policy block"),
        ("401 Unauthorized: private-token", "authentication failed"),
        ("You have reached a usage limit", "usage or rate limit"),
        ("Unknown failure involving private-token", "Inspect this run's local"),
    ],
)
def test_failed_turn_classification_uses_errors_without_exposing_details(
    tmp_path, message, expected
):
    (tmp_path / "trace.jsonl").write_text(
        "incomplete json\n" + json.dumps({"type": "turn.failed", "error": {"message": message}})
    )
    result = agent.codex_failure(tmp_path)
    assert expected in result
    assert "private-token" not in result


def test_source_content_does_not_masquerade_as_a_cli_failure(tmp_path):
    (tmp_path / "trace.jsonl").write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"text": "401 Unauthorized content_policy_violation"},
            }
        )
    )
    assert "Inspect this run's local" in agent.codex_failure(tmp_path)


@pytest.mark.parametrize("failure", ["policy", "timeout"])
def test_investigation_persists_actual_failure_and_never_publishes_claims(
    tmp_path, monkeypatch, failure
):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    session = state.create("session", project["id"])
    turn = state.create("turn", session["id"], question="Explain code", status="queued")
    monkeypatch.setattr(agent.subprocess, "check_output", lambda *_a, **_kw: "fixture-cli")

    def execute(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 240)
        run = Path(command[command.index("-o") + 1]).parent
        (run / "trace.jsonl").write_text(
            json.dumps(
                {
                    "type": "turn.failed",
                    "error": {
                        "message": "This content was flagged for possible cybersecurity risk."
                    },
                }
            )
        )
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(agent.subprocess, "run", execute)
    agent.run_turn(state, project["id"], session["id"], turn["id"])
    result = state.get(turn["id"])
    assert result["status"] == "failed" and not result.get("claims")
    assert ("policy block" if failure == "policy" else "time limit") in result["error"]
    assert "Check local Codex authentication" not in result["error"]
