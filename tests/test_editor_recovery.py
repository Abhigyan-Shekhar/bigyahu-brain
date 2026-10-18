"""A timed-out editor preserves partial work but never bypasses verification."""

import os
import subprocess
import sys
import time

import pytest

from brain.app import actions
from brain.app.action_mcp import read_file, write_file
from brain.app.process import model_process
from brain.app.state import State
from brain.config import Config
from brain.memory import digest


@pytest.fixture
def approved(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "x.py").write_text("value = 1\n")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=source,
        check=True,
    )
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source).decode().strip()
    state = State(tmp_path / "app", Config(source, "fixture"), "fixture")
    project = state.create("repository")
    state.folder(project["id"]).mkdir()
    monkeypatch.setattr(state, "config", lambda *_: state.base)
    plan = actions.validate_plan(
        {
            "summary": "Update value",
            "steps": ["Change x.py"],
            "files": ["x.py", "test_x.py"],
            "tests": [{"runner": "unittest", "path": "test_x.py"}],
        },
        source,
    )
    action = state.create(
        "action",
        project["id"],
        project=project["id"],
        turn="fixture",
        objective="Update value",
        base_revision=sha,
        plan=plan,
        claims=[{"text": "Fixture fact", "support": []}],
        status="awaiting_approval",
    )
    action = state.update(
        action["id"],
        relevance_review={
            "kind": "fallible_model_plan_review",
            "input_digest": actions.review_digest(action),
            "assessments": [{"claim": 0, "verdict": "supported"}],
            "action": {"verdict": "supported"},
        },
    )
    action = state.update(action["id"], plan_digest=actions.plan_digest(action))
    checks = []
    monkeypatch.setattr(actions, "checked_action", lambda *args: checks.append(args))
    actions.approve(state, action["id"], action["plan_digest"])
    return state, action, checks


def stop_editor(monkeypatch):
    def editor(*_args, edit, **_kwargs):
        work, allowed = edit
        write_file(work, allowed, "x.py", "value = 2\n", read_file(work, "x.py")["digest"])
        raise subprocess.TimeoutExpired("editor", 900)

    monkeypatch.setattr(actions, "_codex", editor)


def test_timeout_then_resume_preserves_work_and_runs_all_verification(approved, monkeypatch):
    state, action, checks = approved
    uid = action["id"]
    stop_editor(monkeypatch)
    tests = []

    def run_tests(work, _run, commands):
        tests.append(work)
        return [
            {
                "argv": commands[0],
                "passed": True,
                "exit_code": 0,
                "outcome": "exited",
                "tests_reported": 1,
                "output": "OK",
            }
        ]

    monkeypatch.setattr(actions, "run_tests", run_tests)
    actions.execute(state, uid)
    stopped = state.get(uid)
    assert stopped["status"] == "failed" and stopped["failure_kind"] == "editor_timeout"
    assert stopped["recovery"]["available"] and not tests
    assert "900-second" in stopped["error"] and "Tests have not started" in stopped["error"]
    assert (
        not stopped.get("patch_replay") and not actions.verification_result(stopped)["tests_passed"]
    )
    root = actions.action_folder(state, action)
    assert (root / "checkout/x.py").read_text() == "value = 2\n"
    assert (state.base.repo_root / "x.py").read_text() == "value = 1\n"
    queued = actions.resume_execution(state, uid, action["plan_digest"])
    assert queued["status"] == "queued" and queued["approval"] == stopped["approval"]
    with pytest.raises(ValueError):
        actions.resume_execution(state, uid, action["plan_digest"])

    def finish(_state, _project, run, *_args, edit, **_kwargs):
        assert run.name == "editor-attempt-2"
        work, allowed = edit
        assert (work / "x.py").read_text() == "value = 2\n"
        write_file(work, allowed, "test_x.py", "assert True\n", digest(""))
        return {"summary": "Finished", "lesson": ""}

    monkeypatch.setattr(actions, "_codex", finish)
    actions.execute(state, uid)
    result = state.get(uid)
    assert result["status"] == "complete" and result["editor_attempt"] == 2
    assert len(tests) == 2 and result["patch_replay"]["status"] == "applies_to_base"
    assert len(checks) >= 5
    assert (state.base.repo_root / "x.py").read_text() == "value = 1\n"


@pytest.mark.parametrize(
    "change", ["approved_bytes", "outside_scope", "base", "approval", "evidence", "limit"]
)
def test_resume_rejects_changed_or_stale_recovery(approved, monkeypatch, change):
    state, action, _ = approved
    stop_editor(monkeypatch)
    actions.execute(state, action["id"])
    work = actions.action_folder(state, action) / "checkout"
    if change == "approved_bytes":
        (work / "x.py").write_text("tampered\n")
    elif change == "outside_scope":
        (work / "unexpected.py").write_text("not approved\n")
    elif change == "base":
        state.update(action["id"], base_revision="changed")
    elif change == "approval":
        state.update(action["id"], approval={"plan_digest": "wrong"})
    elif change == "evidence":

        def stale(*_):
            raise ValueError("Evidence changed")

        monkeypatch.setattr(actions, "checked_action", stale)
    else:
        state.update(action["id"], editor_attempt=actions.MAX_EDITOR_ATTEMPTS)
    with pytest.raises(ValueError):
        actions.resume_execution(state, action["id"], action["plan_digest"])
    assert state.get(action["id"])["status"] == "failed"


@pytest.mark.skipif(os.name == "nt", reason="POSIX process group integration")
def test_deadline_stops_editor_and_its_tool_child(tmp_path):
    child_script = (
        'import time,pathlib; time.sleep(1); pathlib.Path("late-write").write_text("bad")'
    )
    script = (
        "import subprocess,sys,time,os; os.chdir(sys.argv[1]); "
        'subprocess.Popen([sys.executable,"-c",sys.argv[2]]); time.sleep(30)'
    )
    with (
        (tmp_path / "trace").open("w") as trace,
        (tmp_path / "err").open("w") as err,
        pytest.raises(subprocess.TimeoutExpired),
    ):
        model_process(
            [sys.executable, "-c", script, str(tmp_path), child_script],
            "",
            trace,
            err,
            dict(os.environ),
            0.3,
        )
    time.sleep(1.1)
    assert not (tmp_path / "late-write").exists()


@pytest.mark.parametrize("editing", [False, True])
def test_model_runner_uses_separate_plan_and_editor_deadlines(approved, monkeypatch, editing):
    import json
    from pathlib import Path

    state, action, _ = approved
    root = actions.action_folder(state, action)
    run = root / ("editor" if editing else "plan")
    deadlines = []

    def process(argv, prompt, trace, err, env, timeout):
        deadlines.append(timeout)
        Path(argv[argv.index("-o") + 1]).write_text(json.dumps({"summary": "Fixture"}))
        return 0

    monkeypatch.setattr(actions, "model_process", process)
    actions._codex(
        state,
        action["project"],
        run,
        "Fixture",
        {},
        edit=(root / "checkout", action["plan"]["files"]) if editing else None,
    )
    assert deadlines == [900 if editing else 240]


def test_resume_api_requires_auth_blocks_active_work_and_consumes_recovery_once(
    approved, monkeypatch
):
    from fastapi.testclient import TestClient

    from brain.app.server import create_app

    state, action, _ = approved
    state.update(action["project"], status="ready")
    stop_editor(monkeypatch)
    actions.execute(state, action["id"])
    app = create_app(state, "fixture-token", "http://testserver")
    submitted = []
    monkeypatch.setattr(app.state.workers, "submit", lambda *args: submitted.append(args))
    try:
        with TestClient(app) as client:
            url = "/api/actions/" + action["id"] + "/resume"
            body = {"plan_digest": action["plan_digest"]}
            assert client.post(url, json=body).status_code == 401
            headers = {"Authorization": "Bearer fixture-token", "Origin": "http://testserver"}
            other = state.create("action", action["project"], status="running", phase="planning")
            assert client.post(url, json=body, headers=headers).status_code == 409
            state.update(other["id"], status="failed")
            assert client.post(url, json=body, headers=headers).status_code == 202
            assert client.post(url, json=body, headers=headers).status_code == 409
            assert len(submitted) == 1
    finally:
        app.state.workers.shutdown()


@pytest.mark.asyncio
async def test_resumed_editor_diff_keeps_original_baseline(tmp_path):
    from fastmcp import Client

    from brain.app.action_mcp import create_server
    from brain.app.live_changes import read_changes

    (tmp_path / "x.py").write_text("value = 2\n")
    log = tmp_path / "events.jsonl"
    # A new MCP server resumes already-edited bytes, with the pre-edit baseline.
    server = create_server(tmp_path, ["x.py"], log, {"x.py": "value = 1\n"})
    async with Client(server) as client:
        await client.call_tool(
            "write_file",
            {
                "path": "x.py",
                "text": "value = 3\n",
                "expected_digest": digest("value = 2\n"),
                "explanation": "Complete approved edit",
            },
        )
    diff = read_changes(log, ["x.py"])["files"][0]["diff"]
    assert "-value = 1" in diff and "+value = 3" in diff and "-value = 2" not in diff
