"""PR7 search/provenance, deterministic citations and regression verification."""

import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_app_personal import managed
from test_integration import real as real  # noqa: PLC0414

from brain.app import evidence, personal
from brain.app.actions import verification_result
from brain.app.server import create_app
from brain.graph import GraphStore
from brain.ingest.documents import ingest_documents


def outcomes(before_output="FAILED (failures=1)", **changes):
    command = ["python", "-m", "unittest", "test_retry.py", "-v"]
    after = {
        "argv": command,
        "passed": True,
        "exit_code": 0,
        "outcome": "exited",
        "tests_reported": 2,
    }
    before = {**after, "passed": False, "exit_code": 1, "output": before_output}
    before.update(changes)
    return {"tests": [after], "baseline_tests": [before], "baseline_includes_proposed_tests": True}


@pytest.mark.parametrize(
    "changes",
    [
        {"passed": True, "exit_code": 0, "output": "OK"},
        {"outcome": "timed_out"},
        {"exit_code": 2},
        {"output": "FAILED (errors=1)"},
        {"output": "FAILED (failures=1, errors=1)"},
        {"tests_reported": 1},
        {"argv": ["different"]},
    ],
)
def test_passing_patch_without_matched_regression_is_explicitly_unverified(changes):
    result = verification_result(outcomes(**changes))
    assert result == {
        "tests_passed": True,
        "regression_demonstrated": False,
        "fix_verification": "tests_passed_fix_unverified",
    }


def test_regression_signal_requires_matched_failures_and_proposed_tests():
    assert verification_result(outcomes())["regression_demonstrated"]
    action = outcomes()
    action["baseline_includes_proposed_tests"] = False
    assert not verification_result(action)["regression_demonstrated"]
    action = outcomes()
    action["tests"][0]["passed"] = False
    assert not verification_result(action)["tests_passed"]
    action = outcomes()
    action["baseline_tests"][0].update(
        argv=["python", "-m", "pytest", "tests"], tests_reported=0, output="2 failed in 0.1s"
    )
    action["tests"][0]["argv"] = action["baseline_tests"][0]["argv"]
    assert verification_result(action)["regression_demonstrated"]


def test_unverified_passing_action_cannot_propose_fix_lesson(tmp_path, monkeypatch):
    from brain.app import actions
    from brain.app.state import State
    from brain.config import Config

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    action = state.create(
        "action",
        status="complete",
        tests_passed=True,
        lesson_proposal={"text": "Claimed fix"},
        **{k: v for k, v in outcomes(output="OK", exit_code=0).items()},
    )
    monkeypatch.setattr(
        actions, "checked_action", lambda *_: pytest.fail("Unverified fix reached source checks")
    )
    with pytest.raises(ValueError, match="regression"):
        personal.propose_lesson(state, action["id"])


def test_equivalent_reordered_graph_keeps_citation_valid_but_changed_metadata_fails(
    tmp_path, monkeypatch
):
    graph = {
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [
            {
                "source": "a",
                "target": "b",
                "relation": "IMPLEMENTS",
                "edge_type": "EXTRACTED_RELATION",
                "quote": "literal",
                "confidence": "INFERRED",
            },
            {"source": "b", "target": "a", "relation": "SUPPORTS"},
        ],
    }
    saved = evidence.register(
        tmp_path,
        {
            "kind": "source",
            "ref": {},
            "digest": "digest",
            "revision": "revision",
            "text": "literal source",
            "graph": graph,
            "title": "Fixture",
        },
    )
    current = {
        **saved,
        "graph": {"nodes": list(reversed(graph["nodes"])), "edges": list(reversed(graph["edges"]))},
    }
    monkeypatch.setattr(evidence, "resolve", lambda *_: current)
    output = {
        "claims": [
            {"text": "Fixture", "support": [{"evidence_id": saved["id"], "quote": "literal"}]}
        ]
    }
    assert evidence.verified_claims(None, tmp_path, output)
    current["graph"]["edges"][1] = {**current["graph"]["edges"][1], "confidence": "AMBIGUOUS"}
    with pytest.raises(ValueError):
        evidence.verified_claims(None, tmp_path, output)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_live_graph_name_search_semantic_labels_and_bounded_source_paths(real, tmp_path):
    state, project, cfg = managed(real, tmp_path)
    store = GraphStore(cfg)
    # Symbol b has path x.py: search must independently match its qualname.
    (cfg.repo_root / "guide.md").write_text(
        "# Retry policy\nRetry Service implements bounded backoff.\n"
    )
    from brain.ingest.git_parser import git
    from brain.ingest.sync import sync

    git(cfg.repo_root, "add", "guide.md")
    git(
        cfg.repo_root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.com",
        "commit",
        "-m",
        "Add fixture guide",
    )
    sync(store)
    ingest_documents(store, ["guide.md"])
    sources = store.query(
        "MATCH (d:Document {repo_id:$repo,path:'guide.md'})-[:SUPPORTS]->(s:Source) RETURN s.uid AS uid,s.excerpt AS text",
        {"repo": cfg.repo_id},
    )
    assert sources
    # Native publication shape: actual semantic name and span stay properties.
    store.query(
        "MATCH (s:Source {uid:$source}) MERGE (a:Document {uid:$a}) SET a.repo_id=$repo,a.title='Retry Service',a.current=true MERGE (b:Document {uid:$b}) SET b.repo_id=$repo,b.title='Bounded backoff',b.current=true MERGE (a)-[:SUPPORTS]->(s) MERGE (a)-[r:EXTRACTED_RELATION {relation:'IMPLEMENTS'}]->(b) SET r.quote='implements bounded backoff',r.confidence='INFERRED',r.source_uid=$source",
        {
            "repo": cfg.repo_id,
            "source": sources[0]["uid"],
            "a": cfg.repo_id + ":entity:a",
            "b": cfg.repo_id + ":entity:b",
        },
    )
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    try:
        with TestClient(app) as client:
            base = f"/api/repositories/{project}/graph"
            headers = {"Authorization": "Bearer token"}
            found = client.get(base, params={"query": "b"}, headers=headers).json()
            assert any(n["labels"] == ["Symbol"] and n["label"] == "b" for n in found["nodes"])
            graph = client.get(base, headers=headers).json()
            edge = next(e for e in graph["edges"] if e["relation"] == "IMPLEMENTS")
            assert (
                edge["edge_type"] == "EXTRACTED_RELATION"
                and edge["quote"] == "implements bounded backoff"
                and edge["confidence"] == "INFERRED"
            )
            assert edge["source_uid"] == sources[0]["uid"]
            assert any(n["labels"] == ["Source"] for n in graph["nodes"])
            assert any(e["relation"] == "SUPPORTS" for e in graph["edges"])
            assert len(graph["nodes"]) <= 150 and len(graph["edges"]) <= 300
            # The citation-click endpoint must also normalize legacy ordering/type.
            turn = state.create("turn", project=project, status="complete", claims=[])
            proof = evidence.code_evidence(store, "x.py")
            proof["graph"]["nodes"].reverse()
            for recorded in proof["graph"]["edges"]:
                recorded.pop("edge_type", None)
            saved = evidence.register(
                state.folder(project) / "turns" / turn["id"] / "evidence", proof
            )
            state.update(turn["id"], claims=[{"support": [{"evidence_id": saved["id"]}]}])
            citation = f"/api/turns/{turn['id']}/evidence/{saved['id']}"
            assert client.get(citation, headers=headers).status_code == 200
            proof["digest"] = "changed"
            # Alter the originally cited file rather than creating a new evidence ID.
            import json

            original = (
                state.folder(project) / "turns" / turn["id"] / "evidence" / (saved["id"] + ".json")
            )
            original.write_text(json.dumps(proof))
            assert client.get(citation, headers=headers).status_code == 409
            # Source neighbors reserve space and report overflow, not a silent cut.
            store.query(
                "UNWIND range(1,55) AS i MERGE (d:Document {uid:$doc}) SET d.repo_id=$repo,d.title='Many sources',d.current=true MERGE (s:Source {uid:$doc+':'+toString(i)}) SET s.repo_id=$repo MERGE (d)-[:SUPPORTS]->(s)",
                {"repo": cfg.repo_id, "doc": cfg.repo_id + ":many"},
            )
            bounded = client.get(base, params={"query": "Many sources"}, headers=headers).json()
            assert bounded["truncated"] and len(bounded["nodes"]) == 51
    finally:
        app.state.workers.shutdown()
