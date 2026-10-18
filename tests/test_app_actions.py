"""Approval integrity, constrained editing and actual OS sandbox isolation."""

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from brain.app import actions
from brain.app.action_mcp import read_file, target, write_file
from brain.app.server import create_app
from brain.app.state import State
from brain.app.test_sandbox import bounded_run, sandbox_command
from brain.app.test_sandbox import test_environment as sandbox_env
from brain.config import Config
from brain.memory import digest


@pytest.mark.parametrize("new_file", [False, True])
def test_downloaded_patch_applies_in_fresh_checkout(tmp_path, new_file):
    source, replay = tmp_path / "source", tmp_path / "replay"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "x.py").write_text("value = 1\n")
    subprocess.run(["git", "add", "x.py"], cwd=source, check=True)
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
    actions.clone_at(source, replay, "HEAD")
    # Whitespace is part of the artifact; exporting through a stripped helper
    # used to produce an invalid patch when the last hunk ended here.
    (source / "x.py").write_text("value = 2  \n")
    if new_file:
        (source / "test_x.py").write_text("assert True\n")
    _, patch = actions.patch_for(source, ["x.py", "test_x.py"])
    subprocess.run(["git", "apply", "-"], cwd=replay, input=patch.encode("utf-8"), check=True)
    assert (replay / "x.py").read_bytes() == (source / "x.py").read_bytes()
    if new_file:
        assert (replay / "test_x.py").read_bytes() == (source / "test_x.py").read_bytes()


@pytest.mark.parametrize("autocrlf", ["true", "false"])
@pytest.mark.parametrize("eol", [b"\n", b"\r\n"])
@pytest.mark.parametrize("attributes", [False, True])
def test_patch_preserves_source_bytes_across_git_normalization(tmp_path, autocrlf, eol, attributes):
    source, replay = tmp_path / "source", tmp_path / "replay"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "config", "core.autocrlf", autocrlf], cwd=source, check=True)
    if attributes:
        configured_eol = b"crlf" if eol == b"\r\n" else b"lf"
        (source / ".gitattributes").write_bytes(b"*.py text eol=" + configured_eol + b"\n")
    (source / "x.py").write_bytes(b"value = 1" + eol)
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
    actions.clone_at(source, replay, "HEAD")
    changed = b"value = 2  " + eol + b"# no final newline"
    added = b"assert True  " + eol
    (source / "x.py").write_bytes(changed)
    (source / "test_x.py").write_bytes(added)
    _, exported = actions.patch_for(source, ["x.py", "test_x.py"])
    # Mirror JSON transport, UTF-8 browser Blob download and binary git stdin.
    downloaded = json.loads(json.dumps({"patch": exported}))["patch"].encode("utf-8")
    artifact = tmp_path / "download.patch"
    artifact.write_bytes(downloaded)
    subprocess.run(["git", "apply", str(artifact)], cwd=replay, check=True)
    assert (replay / "x.py").read_bytes() == changed
    assert (replay / "test_x.py").read_bytes() == added


def test_editor_roundtrip_retains_crlf(tmp_path):
    raw = b"value = 1\r\n# no final newline"
    (tmp_path / "x.py").write_bytes(raw)
    previous = read_file(tmp_path, "x.py")
    assert previous["text"].encode() == raw
    write_file(tmp_path, ["x.py"], "x.py", previous["text"], previous["digest"])
    assert (tmp_path / "x.py").read_bytes() == raw


@pytest.mark.parametrize("corrupt_export", [False, True])
def test_execution_publishes_only_byte_equivalent_replay(tmp_path, monkeypatch, corrupt_export):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "x.py").write_bytes(b"value = 1\r\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "add", "."], cwd=source, check=True)
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
            "steps": ["Change value"],
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
    review = {
        "kind": "fallible_model_plan_review",
        "input_digest": actions.review_digest(action),
        "assessments": [{"claim": 0, "verdict": "supported"}],
        "action": {"verdict": "supported"},
    }
    action = state.update(action["id"], relevance_review=review)
    state.update(action["id"], plan_digest=actions.plan_digest(action))
    monkeypatch.setattr(actions, "checked_action", lambda *_: None)
    actions.approve(state, action["id"], actions.plan_digest(action))

    def editor(*_a, edit, **_k):
        work, allowed = edit
        write_file(work, allowed, "x.py", "value = 2  \r\n", read_file(work, "x.py")["digest"])
        write_file(work, allowed, "test_x.py", "assert True\r\n", digest(""))
        return {"summary": "Fixture edit", "lesson": "Fixture proposal"}

    monkeypatch.setattr(actions, "_codex", editor)
    monkeypatch.setattr(
        actions,
        "run_tests",
        lambda work, _run, commands: [
            {
                "argv": commands[0],
                "passed": True,
                "exit_code": 0,
                "outcome": "exited",
                "tests_reported": 1,
                "output": "OK",
            }
        ],
    )
    export = actions.patch_for
    if corrupt_export:

        def changed_export(*args):
            names, patch = export(*args)
            return names, patch.replace("+value = 2", "+value = 3")

        monkeypatch.setattr(actions, "patch_for", changed_export)
    actions.execute(state, action["id"])
    result = state.get(action["id"])
    if corrupt_export:
        assert result["status"] == "failed" and not result.get("patch_replay")
        assert "edited file bytes" in result["error"]
    else:
        assert result["status"] == "complete"
        assert result["patch_replay"]["kind"] == "git_apply_byte_comparison"
        assert result["patch_replay"]["tests_rerun"] is False
        assert (actions.action_folder(state, result) / "patch.diff").read_bytes() == result[
            "patch"
        ].encode()
    assert (source / "x.py").read_bytes() == b"value = 1\r\n"


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "/absolute.py",
        ".git/config",
        ".codex/settings.py",
        "a/../../bad.py",
        "a\\b.py",
        "C:/escape.py",
    ],
)
def test_editor_cannot_escape_or_edit_hidden_files(tmp_path, path):
    with pytest.raises(ValueError):
        target(tmp_path, path)


def test_editor_obeys_approved_paths_and_expected_digest(tmp_path):
    (tmp_path / "x.py").write_text("original")
    with pytest.raises(ValueError):
        write_file(tmp_path, ["x.py"], "other.py", "bad", digest(""))
    with pytest.raises(ValueError):
        write_file(tmp_path, ["x.py"], "x.py", "bad", digest("stale"))
    write_file(tmp_path, ["x.py"], "x.py", "updated", read_file(tmp_path, "x.py")["digest"])
    assert (tmp_path / "x.py").read_text() == "updated"


@pytest.mark.parametrize(
    "tests",
    [
        [{"runner": "shell", "path": "tests"}],
        [{"runner": "pytest", "path": "../host"}],
        [{"runner": "pytest", "path": "-c malicious.py"}],
        [{"runner": "pytest", "path": ".git"}],
        [],
    ],
)
def test_plan_cannot_request_arbitrary_commands(tmp_path, tests):
    with pytest.raises(ValueError):
        actions.commands_for(tests, tmp_path)


def test_approval_digest_consumed_once_and_tampered_plan_rejected(tmp_path, monkeypatch):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    plan = {
        "summary": "Fix calculation",
        "steps": ["Update calculation", "Add regression test"],
        "files": ["x.py", "tests/test_x.py"],
        "tests": [{"runner": "unittest", "path": "tests"}],
    }
    plan = actions.validate_plan(plan, tmp_path)
    action = state.create(
        "action",
        "project",
        project="project",
        turn="turn",
        objective="Fix bug",
        base_revision="sha",
        plan=plan,
        claims=[{"text": "Code fact", "support": [], "influence": "Fix calculation"}],
        status="awaiting_approval",
    )
    review = {
        "kind": "fallible_model_plan_review",
        "input_digest": actions.review_digest(action),
        "assessments": [{"claim": 0, "verdict": "supported", "reason": "Code fact"}],
        "action": {"verdict": "supported", "reason": "Narrow correction"},
    }
    action = state.update(action["id"], relevance_review=review)
    signature = actions.plan_digest(action)
    state.update(action["id"], plan_digest=signature)
    monkeypatch.setattr(actions, "checked_action", lambda *args: None)
    with pytest.raises(ValueError):
        actions.approve(state, action["id"], "f" * 64)
    approved = actions.approve(state, action["id"], signature)
    assert approved["approval"]["plan_digest"] == signature
    with pytest.raises(ValueError):
        actions.approve(state, action["id"], signature)
    assert actions.plan_digest({**action, "objective": "different"}) != signature


def test_atomic_transition_handles_concurrent_approval_retries(tmp_path):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    action = state.create("action", status="awaiting_approval")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: state.transition(
                    action["id"], {"status": "awaiting_approval"}, status="queued"
                ),
                range(4),
            )
        )
    assert results.count(True) == 1


def test_execution_without_approval_does_nothing_and_rejection_is_one_shot(tmp_path, monkeypatch):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    action = state.create("action", status="queued", phase="execution")
    monkeypatch.setattr(
        actions, "clone_at", lambda *a: pytest.fail("Execution started without approval")
    )
    actions.execute(state, action["id"])
    assert state.get(action["id"])["status"] == "queued"
    pending = state.create("action", status="awaiting_approval")
    app = create_app(state, "token", "http://testserver", assets=tmp_path / "unbuilt")
    try:
        with TestClient(app) as client:
            assert client.post(f"/api/actions/{pending['id']}/reject", json={}).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (
                client.post(
                    f"/api/actions/{pending['id']}/reject", headers=headers, json={}
                ).json()["status"]
                == "rejected"
            )
            assert (
                client.post(
                    f"/api/actions/{pending['id']}/reject", headers=headers, json={}
                ).status_code
                == 409
            )
    finally:
        app.state.workers.shutdown()


def test_patch_audit_detects_ignored_out_of_scope_file(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "x.py").write_text("original")
    (tmp_path / ".gitignore").write_text("hidden.py\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (tmp_path / "x.py").write_text("updated")
    (tmp_path / "hidden.py").write_text("unapproved")
    with pytest.raises(ValueError, match="outside the approved scope"):
        actions.patch_for(tmp_path, ["x.py"])


@pytest.mark.skipif(
    sys.platform != "darwin" or not shutil.which("codex"),
    reason="requires the local Codex macOS OS sandbox",
)
def test_real_sandbox_blocks_host_reads_writes_and_network(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    secret = tmp_path / "outside.txt"
    secret.write_text("host canary")
    probe = """import socket
from pathlib import Path
failures=[]
for name,op in [('read',lambda:Path('../outside.txt').read_text()),('write',lambda:Path('../outside.txt').write_text('changed')),('network',lambda:socket.socket().connect(('127.0.0.1',9)))]:
 try:op();failures.append(name)
 except PermissionError:pass
Path('allowed.txt').write_text('workspace write works')
print(failures)
raise SystemExit(bool(failures))
"""
    result = bounded_run(
        sandbox_command(work, scratch, ["python", "-c", probe]),
        work,
        sandbox_env(work, scratch),
        tmp_path / "probe.log",
        timeout=20,
    )
    assert result["passed"], result["output"]
    assert secret.read_text() == "host canary"
    assert (work / "allowed.txt").read_text() == "workspace write works"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group runner")
@pytest.mark.parametrize(
    ("program", "timeout", "outcome"),
    [
        ("import time; time.sleep(5)", 0.1, "timeout"),
        ("import sys; sys.stdout.write('x' * 600000)", 5, "output_limit"),
    ],
)
def test_test_process_bounds(tmp_path, program, timeout, outcome):
    log = tmp_path / "test.log"
    result = bounded_run([sys.executable, "-c", program], tmp_path, {}, log, timeout=timeout)
    assert result["outcome"] == outcome
    assert not result["passed"]
    assert log.stat().st_size <= 512000


def test_zero_tests_cannot_report_success(tmp_path, monkeypatch):
    from brain.app import test_sandbox

    monkeypatch.setattr(test_sandbox, "sandbox_command", lambda *args: [])
    monkeypatch.setattr(
        test_sandbox,
        "bounded_run",
        lambda *args: {"passed": True, "output": "Ran 0 tests in 0.000s\nOK"},
    )
    result = test_sandbox.run_tests(
        tmp_path, tmp_path, [["python", "-m", "unittest", "missing.py", "-v"]]
    )
    assert result[0]["tests_reported"] == 0
    assert not result[0]["passed"]


def test_local_history_retains_snapshot_when_citation_access_is_revoked(tmp_path, monkeypatch):
    """Characterize local retention; this is not a multi-user privacy guarantee."""
    from brain.app import server

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    project = state.create("repository")
    evidence_id = "a" * 24
    claims = [
        {
            "text": "Recorded claim",
            "support": [
                {"evidence_id": evidence_id, "quote": "Previously authorized fixture quote"}
            ],
        }
    ]
    action = state.create(
        "action", project["id"], project=project["id"], status="complete", claims=claims
    )

    def revoked(*_):
        raise PermissionError("Evidence access revoked")

    monkeypatch.setattr(server, "checked_action", revoked)
    app = create_app(state, "token", "http://testserver", assets=tmp_path / "unbuilt")
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            assert client.get(f"/api/actions/{action['id']}").status_code == 401
            history = client.get(f"/api/actions/{action['id']}", headers=headers)
            assert history.status_code == 200
            assert history.json()["claims"] == claims
            reopened = client.get(
                f"/api/actions/{action['id']}/evidence/{evidence_id}", headers=headers
            )
            assert reopened.status_code == 403
    finally:
        app.state.workers.shutdown(wait=True)
