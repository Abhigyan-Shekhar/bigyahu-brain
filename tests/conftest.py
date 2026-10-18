"""Shared disposable source/evidence fixture for authoring and orchestration."""

import subprocess
from types import SimpleNamespace

import pytest

from brain.app import actions, document_patch, documentation, evidence, orchestrator, workflow_api
from brain.app.state import State
from brain.config import Config
from brain.memory import digest


@pytest.fixture
def authored(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "queue.py").write_text("jobs = {}\n")
    (source / "docs").mkdir()
    (source / "docs/existing.md").write_bytes(b"# Existing\r\nOld description.\r\n")
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
            "Fixture",
        ],
        cwd=source,
        check=True,
    )
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source).decode().strip()
    state = State(
        tmp_path / "app",
        Config(source, "fixture", repo_url="https://github.com/example/project"),
        "fixture-model",
    )
    repo = state.create(
        "repository",
        status="ready",
        name="example/project",
        url="https://github.com/example/project",
    )
    state.folder(repo["id"]).mkdir()
    monkeypatch.setattr(state, "config", lambda *_: state.base)
    current = {"sha": sha}
    for module in (documentation, document_patch, actions, orchestrator, workflow_api):
        monkeypatch.setattr(module, "ready", lambda *_: current["sha"])
    proof = {
        "kind": "code",
        "ref": {"path": "queue.py", "start": 1, "end": 1},
        "text": "jobs = {}\n",
        "digest": digest("jobs = {}\n"),
        "revision": sha,
        "title": "queue.py:1",
        "uri": f"https://github.com/example/project/blob/{sha}/queue.py#L1",
        "graph": {"nodes": [], "edges": []},
        "binding": False,
    }
    monkeypatch.setattr(evidence, "resolve", lambda *_: proof)
    calls = []

    def model(_state, _project, run, prompt, schema, **kwargs):
        calls.append((run, prompt, kwargs))
        item = evidence.register(run / "evidence", proof)
        result = {
            "claims": [
                {
                    "text": "The job queue is an in-memory dictionary.",
                    "support": [{"evidence_id": item["id"], "quote": "jobs = {}"}],
                    "finding": None,
                }
            ],
            "limitations": ["Restart behavior was not independently tested."],
        }
        if schema is documentation.DOC_SCHEMA:
            result.update(
                title="Job queue recovery",
                proposed_repo_path="docs/queue-recovery.md",
                sections=[{"heading": "Current design", "claim_indices": [0]}],
                suggested_next_actions=["Consider durable queue storage."],
            )
        return result

    monkeypatch.setattr(actions, "_codex", model)

    def assess(_objective, claims, *_args, **kwargs):
        results = [
            {"claim": i, "verdict": "supported", "reason": "Source supports the assertion"}
            for i in range(len(claims))
        ]
        return (
            {
                "assessments": results,
                "document_assessment": {
                    "verdict": "supported",
                    "reason": "Outline follows evidence",
                },
            }
            if kwargs.get("document")
            else results
        )

    monkeypatch.setattr(documentation, "assess", assess)
    return SimpleNamespace(
        state=state,
        project=repo["id"],
        source=source,
        sha=sha,
        current=current,
        proof=proof,
        calls=calls,
        model=model,
    )
