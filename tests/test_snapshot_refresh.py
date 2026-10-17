"""Real graph regressions for current comments versus historical citations."""

import hashlib
import json
import os

import pytest
from test_integration import approve_fixture
from test_integration import real as real  # noqa: PLC0414

from brain.ingest.snapshots import ingest_snapshots
from brain.ingest.sync import sync
from brain.services import Services

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"),
]


def test_comment_refresh_and_stable_source_versions(real, tmp_path, monkeypatch):
    sync(real)
    service = Services(real)
    uid = real.cfg.repo_id + ":pr:1"
    cid = uid + ":comment:issue:7"
    folder = tmp_path / "snapshots"
    folder.mkdir()

    def capture(text, day):
        records = [
            {
                "number": 1,
                "title": "Fixture PR",
                "body": "Fixture body",
                "state": "open",
                "html_url": "https://example.invalid/pull/1",
                "pull_request": {},
                "comments_snapshot": []
                if text is None
                else [
                    {
                        "id": "issue:7",
                        "body": text,
                        "html_url": "https://example.invalid/pull/1#comment-7",
                    }
                ],
            }
        ]
        raw = json.dumps(records).encode()
        (folder / "work.json").write_bytes(raw)
        (folder / "manifest.json").write_text(
            json.dumps(
                {
                    "repo_id": real.cfg.repo_id,
                    "repo_url": real.cfg.repo_url,
                    "sha": real.revision()["sha"],
                    "visibility": "public",
                    "collected_at": f"2026-10-{day:02d}T00:00:00Z",
                    "immutable_sources": True,
                    "work_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        )
        ingest_snapshots(real, folder)

    def comment_sources():
        return real.query(
            "MATCH (:Comment {uid:$uid})-[:SUPPORTS]->(s:Source) RETURN s.uid AS uid, s.excerpt AS text",
            {"uid": cid},
        )

    def source_count():
        return real.query(
            "MATCH (s:Source {repo_id:$repo}) RETURN count(s) AS n", {"repo": real.cfg.repo_id}
        )

    capture("OLD_COMMENT", 1)
    old = comment_sources()[0]["uid"]
    count = source_count()
    capture("OLD_COMMENT", 2)
    assert source_count() == count
    assert comment_sources()[0]["uid"] == old
    decision = service.remember(
        "Synthetic retained evidence",
        source_refs=[old],
        applies_to=[f"{real.cfg.repo_id}@{real.revision()['sha']}:x.py::b"],
    )
    approve_fixture(real, decision["decision_id"], monkeypatch)
    capture("NEW_COMMENT", 3)
    assert source_count()[0]["n"] == count[0]["n"] + 1
    assert [s["text"] for s in comment_sources()] == ["NEW_COMMENT"]
    for query in (uid, cid):
        excerpts = service.get_context(query)["untrusted_source_excerpts"]
        assert any(s["text"] == "NEW_COMMENT" for s in excerpts)
        assert not any(s["text"] == "OLD_COMMENT" for s in excerpts)
    # Simulate an orphan left by an older reconciliation; refresh repairs it too.
    real.query("MATCH (:PR {uid:$uid})-[r:DISCUSSED_IN]->() DELETE r", {"uid": uid})
    capture(None, 4)
    assert not comment_sources()
    assert not service.get_context(cid)["items"]
    assert not any(
        s["text"] == "NEW_COMMENT" for s in service.get_context(uid)["untrusted_source_excerpts"]
    )
    # Reviewed history is independent of deleted Comment projections.
    assert real.query(
        "MATCH (:Decision {uid:$decision})-[:SUPPORTED_BY]->(s:Source {uid:$source}) RETURN s.excerpt AS text",
        {"decision": decision["decision_id"], "source": old},
    ) == [{"text": "OLD_COMMENT"}]
