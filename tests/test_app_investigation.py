"""Historical evidence, explicit bridge/transfer boundaries and neighbor navigation."""

import os
from dataclasses import replace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_app_personal import managed
from test_integration import real as real  # noqa: PLC0414

from brain.app import history, personal, relevance, sources, team, transfers
from brain.app.evidence import register, resolve
from brain.app.server import create_app
from brain.graph import GraphStore
from brain.ingest.git_parser import git
from brain.ingest.sync import sync


def test_relevance_requires_complete_unique_ordered_assessments(tmp_path, monkeypatch):
    evidence = {
        "text": "Cache uses LRU eviction.",
        "kind": "source",
        "ref": {},
        "digest": "d",
        "revision": "s",
        "graph": {"nodes": [], "edges": []},
    }
    proof = register(tmp_path, evidence)
    claims = [
        {
            "text": "Retry overflow causes the crash.",
            "support": [{"evidence_id": proof["id"], "quote": "Cache uses LRU eviction."}],
        }
    ]

    def fake(prompt, schema, model):
        assert "unrelated quotation" in prompt and "Cache uses LRU eviction." in prompt
        return {
            "assessments": [
                {
                    "claim": 0,
                    "verdict": "unsupported",
                    "reason": "Cache evidence does not discuss retry overflow.",
                }
            ]
        }

    monkeypatch.setattr(relevance, "structured_extract", fake)
    assert (
        relevance.assess("Why does retry crash?", claims, tmp_path, "fixture")[0]["verdict"]
        == "unsupported"
    )
    monkeypatch.setattr(relevance, "structured_extract", lambda *_: {"assessments": []})
    with pytest.raises(ValueError, match="Incomplete"):
        relevance.assess("Why?", claims, tmp_path, "fixture")
    monkeypatch.setattr(
        relevance,
        "structured_extract",
        lambda *_: {"assessments": [{"claim": 1, "verdict": "supported", "reason": "Wrong index"}]},
    )
    with pytest.raises(ValueError, match="Invalid"):
        relevance.assess("Why?", claims, tmp_path, "fixture")


@pytest.mark.parametrize("review_fails", [False, True])
def test_turn_publishes_only_relevance_supported_claims(tmp_path, monkeypatch, review_fails):
    from types import SimpleNamespace

    from brain.app import agent
    from brain.app.state import State
    from brain.config import Config

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    state.folder(project["id"]).mkdir()
    chat = state.create("session", project["id"], project=project["id"])
    turn = state.create(
        "turn", chat["id"], question="Why does retry fail?", project=project["id"], status="queued"
    )
    monkeypatch.setattr(state, "config", lambda *_: state.base)
    claims = [
        {"text": "Unrelated diagnosis", "support": []},
        {"text": "Direct code fact", "support": []},
    ]
    monkeypatch.setattr(agent, "verified_claims", lambda *_: claims)
    monkeypatch.setattr(agent.subprocess, "check_output", lambda *_a, **_k: "fixture-cli")

    def execute(args, **kwargs):
        from pathlib import Path

        Path(args[args.index("-o") + 1]).write_text('{"claims": [], "limitations": []}')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(agent.subprocess, "run", execute)

    def review(*_):
        if review_fails:
            raise ValueError("Review unavailable")
        return [
            {"claim": 0, "verdict": "unsupported", "reason": "Unrelated source"},
            {"claim": 1, "verdict": "supported", "reason": "Direct return statement"},
        ]

    monkeypatch.setattr(agent, "assess", review)
    agent.run_turn(state, project["id"], chat["id"], turn["id"])
    result = state.get(turn["id"])
    if review_fails:
        assert result["status"] == "failed" and not result.get("claims")
    else:
        assert result["status"] == "complete" and result["claims"] == [claims[1]]
        assert result["limitations"] == [
            "Citation relevance review withheld a claim: Unrelated source"
        ]


def test_required_history_acquisition_cannot_silently_fall_back(tmp_path, monkeypatch):
    from brain.app.state import State
    from brain.config import Config

    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    monkeypatch.setattr(sources, "clone_public", lambda *_: None)
    monkeypatch.setattr(state, "configure", lambda *_: state.base)
    monkeypatch.setattr(sources, "sync", lambda *_: {})

    class Store:
        def __init__(self, *_):
            pass

        def revision(self):
            return {"sha": "a" * 40, "syncing": False}

    monkeypatch.setattr(sources, "GraphStore", Store)
    monkeypatch.setattr(
        sources,
        "sync_initial",
        lambda *_args, **_kw: (_ for _ in ()).throw(ValueError("rate limit")),
    )
    monkeypatch.setattr(sources, "git", lambda *_: "")
    sources.onboard(state, project["id"])
    assert state.get(project["id"])["status"] == "failed"
    assert "Required GitHub" in state.get(project["id"])["error"]
    other = state.create("repository", url="https://github.com/example/fixture")
    sources.onboard(state, other["id"], True, False)
    assert state.get(other["id"])["status"] == "ready"
    assert state.get(other["id"])["warnings"]


live = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")


@pytest.mark.integration
@live
def test_history_ranks_old_relevant_patch_over_new_noise_and_rechecks_git(real, tmp_path):
    _state, _project, cfg = managed(real, tmp_path)
    file = cfg.repo_root / "x.py"
    file.write_text("def b():\n    return min(2 ** 4, 8)\n")
    git(cfg.repo_root, "add", "x.py")
    git(
        cfg.repo_root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.com",
        "commit",
        "-m",
        "Fix retry overflow with bounded backoff cap",
    )
    fixed = git(cfg.repo_root, "rev-parse", "HEAD")
    (cfg.repo_root / "guide.md").write_text("Documentation only\n")
    git(cfg.repo_root, "add", "guide.md")
    git(
        cfg.repo_root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.com",
        "commit",
        "-m",
        "Refresh unrelated docs",
    )
    store = GraphStore(cfg)
    sync(store)
    result = history.search(
        store, tmp_path / "evidence", "retry failure overflow backoff", symbols=["b"]
    )
    assert result["status"] == "ok"
    assert result["items"][0]["sha"] == fixed
    assert result["items"][0]["matched_files"] == ["x.py"]
    assert any(n["name"] == "b" for n in result["items"][0]["current_file_symbols"])
    assert "github_issue_pr_coverage_unverified" in result["warnings"]
    patches = [e for e in result["checked_evidence"] if e["kind"] == "history_diff"]
    assert patches and "+    return min(2 ** 4, 8)" in patches[0]["text"]
    reopened = resolve(store, patches[0])
    assert reopened["digest"] == patches[0]["digest"]
    assert {"MODIFIES", "DECLARES"} <= {e["relation"] for e in reopened["graph"]["edges"]}
    assert any(n["label"] == "x.py" for n in reopened["graph"]["nodes"])
    assert reopened["association_status"] == "current_file_link"
    with pytest.raises(ValueError):
        history.patch_evidence(store, "HEAD~1", "x.py")
    with pytest.raises(ValueError):
        history.patch_evidence(store, fixed, "../outside")
    store.query("MATCH (p:Project {uid:$repo}) SET p.github_syncing=true", {"repo": cfg.repo_id})
    with pytest.raises(ValueError, match="stale or incomplete"):
        history.search(store, tmp_path, "retry")


@pytest.mark.integration
@live
def test_explicit_company_bridge_exposes_native_code_paths_without_granting_team_readers(
    real, tmp_path
):
    state, project, cfg = managed(real, tmp_path)
    note = personal.propose_note(cfg, "For overflow investigate `x.b` and cap the result.")
    personal.review(cfg, note["uid"], note["hash"], "proposed", "accept", "Checked")
    team.create(cfg, "platform")
    shared = team.share(cfg, "platform", note["uid"], note["hash"])
    team.review(cfg, "platform", shared["uid"], shared["hash"], "proposed", "accept", "Checked")
    team.membership(cfg, "platform", "bob", "reader", "", "Fixture")
    with personal.catalog(cfg) as (memory, projection):
        assert not personal.company_enabled(memory)
        assert not any(
            n["kind"] == "CompanySymbol" for n in projection.read([personal.brain(memory)])["nodes"]
        )
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    try:
        with TestClient(app) as client:
            url = f"/api/repositories/{project}/memory/company-bridge"
            assert client.post(url, json={"enabled": True}).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (
                client.post(
                    url, json={"enabled": True, "principal": "other"}, headers=headers
                ).status_code
                == 422
            )
            enabled = client.post(url, json={"enabled": True}, headers=headers)
            assert enabled.status_code == 200 and enabled.json()["company_enabled"]
            assert client.get(f"/api/repositories/{project}/memory", headers=headers).json()[
                "company_enabled"
            ]
    finally:
        app.state.workers.shutdown()
    with personal.catalog(cfg) as (memory, projection):
        native = projection.read(team.retrieval_scopes(memory), include_company=True)
        assert native["status"] == "ok"
        assert any(n["kind"] == "CompanySymbol" and n["qualname"] == "b" for n in native["nodes"])
        assert {"SAME_CITATION", "RESOLVES_TO"} <= {e["relation"] for e in native["edges"]}
    found = team.search(cfg, "x.b")
    assert found["status"] == "ok" and found["items"]
    assert any(n["kind"] == "CompanySymbol" for n in found["graph"]["nodes"])
    import asyncio

    from fastmcp import Client

    from brain.app.mcp import create_server

    async def agent_reads():
        async with Client(create_server(cfg, tmp_path / "checked")) as client:
            response = (await client.call_tool("memory_graph", {})).data
            assert response["status"] == "ok"
            assert any(e["kind"] == "memory_path" for e in response["checked_evidence"])
            assert any(
                n.get("company_uid", "").endswith("x.py::b") for n in response["graph"]["nodes"]
            )
            response = (await client.call_tool("memory_search", {"query": "x.b"})).data
            assert response["checked_evidence"]
            assert any(
                n.get("company_uid", "").endswith("x.py::b")
                for e in response["checked_evidence"]
                for n in e["graph"]["nodes"]
            )

    asyncio.run(agent_reads())
    bob = replace(cfg, principal="bob")
    with pytest.raises(PermissionError):
        personal.connect_company(bob, True)
    reader = team.search(bob, "overflow")
    assert reader["status"] == "ok"
    assert not any(n["kind"].startswith("Company") for n in reader["graph"]["nodes"])
    from brain.app.memory_paths import path_evidence

    proof = path_evidence(cfg, "team:platform", shared["uid"], shared["hash"])
    assert "RESOLVES_TO" in proof["text"] and "x.py::b" in proof["text"]
    assert resolve(GraphStore(cfg), proof)["digest"] == proof["digest"]
    personal.connect_company(cfg, False)
    assert resolve(GraphStore(cfg), proof)["digest"] != proof["digest"]
    assert not any(
        n["kind"].startswith("Company") for n in team.search(cfg, "overflow")["graph"]["nodes"]
    )


@pytest.mark.integration
@live
def test_transfer_exact_consent_separate_review_idempotency_and_independent_copy(real, tmp_path):
    state, origin, cfg = managed(real, tmp_path)
    # A second managed repository in this same application, with its own tenant.
    target_row = state.create("repository", status="ready", url=cfg.repo_url)
    target = target_row["id"]
    folder = state.folder(target)
    folder.mkdir()
    import subprocess

    subprocess.run(["git", "clone", "-q", str(cfg.repo_root), str(folder / "checkout")], check=True)
    target_cfg = state.configure(target, cfg.repo_url)
    sync(GraphStore(target_cfg))
    note = personal.propose_note(cfg, "Preserve exact integer behavior in retry caps.")
    with pytest.raises(ValueError):
        transfers.preview(state, target, origin, [note["uid"]])
    personal.review(cfg, note["uid"], note["hash"], "proposed", "accept", "Checked")
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    try:
        with TestClient(app) as client:
            url = f"/api/repositories/{target}/memory/transfers/preview"
            payload = {"origin": origin, "records": [note["uid"]]}
            assert client.post(url, json=payload).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (
                client.post(
                    url, json={**payload, "principal": "other"}, headers=headers
                ).status_code
                == 422
            )
            response = client.post(url, json=payload, headers=headers)
            assert response.status_code == 200
            preview = response.json()
            imported = client.post(
                url.removesuffix("/preview"),
                json={**payload, "consent_digest": preview["consent_digest"]},
                headers=headers,
            )
            assert (
                imported.status_code == 200 and imported.json()["items"][0]["state"] == "proposed"
            )
    finally:
        app.state.workers.shutdown()
    with pytest.raises(ValueError):
        transfers.import_selected(state, target, origin, [note["uid"]], "0" * 64)
    result = transfers.import_selected(
        state, target, origin, [note["uid"]], preview["consent_digest"]
    )
    copy = result["items"][0]
    assert copy["state"] == "proposed" and not personal.search(target_cfg, "integer")["items"]
    personal.review(
        target_cfg,
        copy["uid"],
        copy["hash"],
        "proposed",
        "accept",
        "Checked destination applicability",
    )
    assert personal.search(target_cfg, "integer")["items"]
    replay = transfers.import_selected(
        state, target, origin, [note["uid"]], preview["consent_digest"]
    )
    assert replay["items"][0]["state"] == "accepted"
    personal.review(cfg, note["uid"], note["hash"], "accepted", "rollback", "Revoke original")
    with pytest.raises(ValueError):
        transfers.import_selected(state, target, origin, [note["uid"]], preview["consent_digest"])
    assert personal.search(target_cfg, "integer")["items"]
    with personal.catalog(target_cfg) as (memory, _):
        source = personal.source_details(target_cfg, memory, personal.row(memory, copy["uid"]))[0]
    (target_cfg.repo_root.parent / "memory-sources" / source["digest"]).write_text("corrupt")
    assert not personal.search(target_cfg, "integer")["items"]


@pytest.mark.integration
@live
def test_neighbor_expansion_pages_and_rejects_other_repository(real, tmp_path):
    state, project, cfg = managed(real, tmp_path)
    store = GraphStore(cfg)
    store.query(
        "UNWIND range(1,55) AS i MERGE (d:Document {uid:$repo+':neighbor:'+toString(i)}) SET d.repo_id=$repo,d.title='Neighbor '+toString(i),d.current=true WITH d MATCH (p:Project {uid:$repo}) MERGE (p)-[:CONTAINS]->(d)",
        {"repo": cfg.repo_id},
    )
    app = create_app(state, "token", "http://testserver", assets=tmp_path)
    try:
        with TestClient(app) as client:
            url = f"/api/repositories/{project}/graph/neighbors"
            headers = {"Authorization": "Bearer token"}
            assert client.get(url, params={"uid": cfg.repo_id}).status_code == 401
            assert (
                client.get(url, params={"uid": "another-repo"}, headers=headers).status_code == 404
            )
            first = client.get(url, params={"uid": cfg.repo_id}, headers=headers).json()
            assert first["next_offset"] == 50 and len(first["nodes"]) == 51
            second = client.get(
                url, params={"uid": cfg.repo_id, "offset": 50}, headers=headers
            ).json()
            assert second["next_offset"] is None
            assert {n["id"] for n in first["nodes"]} & {n["id"] for n in second["nodes"]} == {
                cfg.repo_id
            }
    finally:
        app.state.workers.shutdown()


@pytest.mark.integration
@live
def test_history_returns_distinct_work_and_checked_comment_support(real, tmp_path):
    import json

    from test_github_initial import API

    from brain.ingest.github_initial import sync_initial

    _state, _project, cfg = managed(real, tmp_path)
    store = GraphStore(cfg)
    # Real graph publication with 21 selected candidates; the first PR has 375 children.
    api = API()
    original = api.get
    slug = cfg.repo_url.removeprefix("https://github.com/").rstrip("/")

    def get(path, params=None):
        if path == "repos/" + slug:
            return {"id": 1, "full_name": slug, "private": False}
        value = original(path.replace("repos/" + slug, "repos/test/repo"), params)
        return json.loads(json.dumps(value).replace("https://github.com/test/repo", cfg.repo_url))

    api.get = get
    acquired = sync_initial(store, tmp_path / "github", api)
    assert acquired["coverage"]["imported"] == 20
    result = history.search(store, tmp_path / "proofs", "retry overflow cap")
    assert len(result["items"]) == 10
    assert len({r["uid"] for r in result["items"]}) == 10
    first = next(r for r in result["items"] if r["uid"].endswith(":pr:1"))
    assert len(first["support_sources"]) == 376
    assert len(first["support_evidence_ids"]) == 3
    assert "github_history_partial_initial_sample" in result["warnings"]
    assert result["acquisition_coverage"] == acquired["coverage"]
    assert not result["acquisition_coverage"]["complete_repository_history"]
    for proof in result["checked_evidence"]:
        assert resolve(store, proof)["digest"] == proof["digest"]
    assert "github_cursor" not in json.dumps(acquired)


@pytest.mark.integration
@live
def test_conversation_transfer_excludes_unselected_user_text(real, tmp_path):
    import subprocess

    from brain.memory import canonical

    state, origin, cfg = managed(real, tmp_path)
    target = state.create("repository", status="ready", url=cfg.repo_url)["id"]
    folder = state.folder(target)
    folder.mkdir()
    subprocess.run(["git", "clone", "-q", str(cfg.repo_root), str(folder / "checkout")], check=True)
    target_cfg = state.configure(target, cfg.repo_url)
    sync(GraphStore(target_cfg))
    selected = "Preserve integer retry caps in regression tests."
    unrelated = "Unrelated private conversation detail: PRIVATE_EXTRA_68291"
    chat = state.create("session", project=origin)
    turn = state.create("turn", chat["id"], question=selected + "\n" + unrelated, status="complete")
    consent = personal.conversation_preview(state, origin, chat["id"], [turn["id"]])
    job = state.create(
        "memory_import",
        origin,
        project=origin,
        session=chat["id"],
        turns=[turn["id"]],
        semantic=False,
        consent_digest=consent["consent_digest"],
        status="queued",
    )
    personal.import_selected(state, job["id"])
    assert state.get(job["id"])["status"] == "complete"
    with personal.catalog(cfg) as (memory, _):
        rows, _ = personal.rows(memory)
        note = next(r for r in rows if r["text"] == selected)
        assert unrelated in canonical(
            personal.source_details(cfg, memory, personal.row(memory, note["uid"]))
        )
    personal.review(cfg, note["uid"], note["hash"], "proposed", "accept", "Selected only")
    preview = transfers.preview(state, target, origin, [note["uid"]])
    assert selected in canonical(preview) and unrelated not in canonical(preview)
    assert "source_snapshots" not in canonical(preview)
    copied = transfers.import_selected(
        state, target, origin, [note["uid"]], preview["consent_digest"]
    )["items"][0]
    with personal.catalog(target_cfg) as (memory, _):
        sources = personal.source_details(target_cfg, memory, personal.row(memory, copied["uid"]))
    assert selected in canonical(sources) and unrelated not in canonical(sources)
    for artifact in (target_cfg.repo_root.parent / "memory-sources").iterdir():
        assert unrelated not in artifact.read_text()
