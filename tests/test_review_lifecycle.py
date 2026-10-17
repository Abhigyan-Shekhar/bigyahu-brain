"""Extended review lifecycle against synthetic disposable graph fixtures only."""

from datetime import UTC, datetime, timedelta

import pytest
from test_integration import approve_fixture, propose_fixture
from test_integration import real as real  # noqa: PLC0414

from brain.admin import approve, review_decision
from brain.ingest.sync import sync
from brain.services import Services

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        __import__("os").getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"
    ),
]


def test_review_audit_rollback_expiry_and_rejection(real, monkeypatch):
    sync(real)
    uid = propose_fixture(real)
    approve_fixture(real, uid, monkeypatch)
    audit = real.query(
        "MATCH (r:ReviewRecord {repo_id:$repo,action:'approve'})-[:REVIEWS]->(d:Decision {uid:$uid}) "
        "RETURN r.source_uids AS sources,r.subject_uids AS subjects,r.actor AS actor",
        {"repo": real.cfg.repo_id, "uid": uid},
    )
    assert audit[0]["sources"] and audit[0]["subjects"] and audit[0]["actor"]
    monkeypatch.setattr("builtins.input", lambda prompt: "ROLLBACK " + uid)
    review_decision(real, uid, "rollback", "Synthetic revocation")
    assert not Services(real).check_change(["x.py"], ["a"])["must_preserve"]
    monkeypatch.setattr("builtins.input", lambda prompt: "APPROVE " + uid)
    approve(real, uid, (datetime.now(UTC) + timedelta(days=1)).isoformat())
    real.query(
        "MATCH (d:Decision {uid:$uid}) SET d.expires_at='2020-01-01T00:00:00+00:00'", {"uid": uid}
    )
    assert not Services(real).check_change(["x.py"], ["a"])["must_preserve"]
    rejected = propose_fixture(real, "Synthetic rejected proposal")
    monkeypatch.setattr("builtins.input", lambda prompt: "REJECT " + rejected)
    review_decision(real, rejected, "reject", "Evidence does not support this rule")
    assert Services(real).trace_decision(rejected)["items"][0]["status"] == "rejected"


def test_approval_rechecks_refresh_fence_after_human_review(real, monkeypatch):
    sync(real)
    uid = propose_fixture(real)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setenv("BRAIN_OPERATOR_SESSION", "1")

    def confirm(prompt):
        real.query(
            "MATCH (p:Project {uid:$repo}) SET p.documents_syncing=true", {"repo": real.cfg.repo_id}
        )
        return "APPROVE " + uid

    monkeypatch.setattr("builtins.input", confirm)
    with pytest.raises(ValueError, match="Approval conflict"):
        approve(real, uid)
    real.query(
        "MATCH (p:Project {uid:$repo}) SET p.documents_syncing=false", {"repo": real.cfg.repo_id}
    )
    assert Services(real).trace_decision(uid)["items"][0]["status"] == "proposed"
