"""Navigation from current code to indexed work and source-backed decision history."""
import os

import pytest
from test_integration import real as real  # noqa: PLC0414

from brain.app.graph_workspace import inspect_node, work_timeline
from brain.ingest.sync import sync
from brain.services import Services

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")]


def test_current_node_activity_and_deadline_decision_links(real):
    sync(real)
    repo, sha = real.cfg.repo_id, real.revision()["sha"]
    file = f"{repo}@{sha}:x.py"
    pr, issue, source = repo + ":pr:1", repo + ":issue:2", repo + ":source:pr1"
    real.upsert("PR", pr, {"repo_id": repo, "title": "Work", "work_status": "open_proposal",
                          "due_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-18T00:00:00Z"})
    real.upsert("Issue", issue, {"repo_id": repo, "title": "Related issue"})
    real.upsert("Source", source, {"repo_id": repo, "uri": "https://example.invalid/pr1", "excerpt": "reason"})
    real.edge(pr, "CHANGES", file)
    real.edge(pr, "REFERENCES", issue)
    real.edge(pr, "SUPPORTS", source)
    decision = Services(real).remember("Reasoned proposal", source_refs=[source])["decision_id"]
    real.upsert("Decision", "foreign", {"repo_id": "foreign", "scope": "org", "text": "HIDDEN"})
    real.edge("foreign", "SUPPORTED_BY", source)
    detail = inspect_node(real, f"{file}::a")
    highlights = detail["highlights"]
    assert highlights["last_commit"]["author"] == "Fixture"
    assert highlights["live"] == []
    assert {w["uid"] for w in highlights["work"]["items"]} == {pr, issue}
    all_work = work_timeline(real)
    item = next(w for w in all_work["items"] if w["uid"] == pr)
    assert item["due_at"] == "2026-10-20T00:00:00Z"
    assert [d["uid"] for d in item["decisions"]] == [decision]
    assert item["decisions"][0]["created_at"]
    assert item["decisions"][0]["status"] == "proposed"
    real.query("MATCH (n {uid:'foreign'}) DETACH DELETE n")
