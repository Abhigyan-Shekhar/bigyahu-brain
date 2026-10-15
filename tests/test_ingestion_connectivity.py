"""Real ingestion tests, using the existing isolated per-repository fixture."""

import hashlib
import json
import os
import subprocess

import pytest
from test_integration import ingest_real_history_fixture
from test_integration import real as real  # noqa: PLC0414 - re-export pytest fixture

from brain.ingest.snapshots import ingest_snapshots
from brain.ingest.sync import sync

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"),
]


def commit(root):
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-m",
            "connectivity fixture",
        ],
        check=True,
        capture_output=True,
    )


def test_reexports_idempotency_failure_and_revision_recovery(real, monkeypatch):
    root = real.cfg.repo_root
    (root / "caller.py").write_text("from pkg import target\ndef caller(): target()\n")
    (root / "pkg").mkdir()
    (root / "pkg/__init__.py").write_text("from .util import target\n")
    (root / "pkg/util.py").write_text("def target(): pass\n")
    commit(root)
    first = sync(real)
    assert first["statically_resolved_imports"] == 1
    assert first["files"] == 5
    historical = real.query(
        "MATCH (:Commit {repo_id:$repo})-[r:MODIFIES]->(:File) "
        "RETURN r.basis AS basis, r.source_uid AS source LIMIT 1",
        {"repo": real.cfg.repo_id},
    )
    assert historical[0]["basis"] == "git_diff_tree_path_at_indexed_revision"
    assert historical[0]["source"].endswith(":source")
    query = (
        "MATCH (a:Symbol {repo_id:$repo})-[r:CALLS]->(b:Symbol {repo_id:$repo}) "
        "RETURN a.qualname AS caller, b.qualname AS target, r.resolution AS resolution"
    )
    params = {"repo": real.cfg.repo_id}
    before = real.query(query, params)
    assert sync(real) == first
    assert real.query(query, params) == before
    old = first["revision"]
    (root / "pkg/util.py").write_text("def target():\n    return 42\n")
    commit(root)
    edge = real.edge
    with monkeypatch.context() as patch:

        def fail(*args, **kwargs):
            raise RuntimeError("injected write failure")

        patch.setattr(real, "edge", fail)
        with pytest.raises(RuntimeError, match="injected"):
            sync(real)
    assert real.revision() == {"sha": old, "syncing": True}
    assert real.edge == edge
    done = sync(real)
    assert done["revision"] != old and real.revision()["syncing"] is False
    assert real.query(
        "MATCH (s:Symbol {repo_id:$repo, revision:$sha}) "
        "RETURN collect(DISTINCT s.current) AS flags",
        {**params, "sha": old},
    ) == [{"flags": [False]}]
    assert real.query(query, params) == before
    assert not real.query(
        "MATCH (a:Symbol {repo_id:$repo})-[:CALLS]->(b:Symbol) "
        "WHERE a.current=false OR b.current=false RETURN a.uid",
        params,
    )


def test_reference_provenance_and_refresh(real, tmp_path):
    ingest_real_history_fixture(real, tmp_path)
    params = {"repo": real.cfg.repo_id}
    query = (
        "MATCH (p:PR {repo_id:$repo, number:5242})-[r:REFERENCES]->"
        "(i:Issue {repo_id:$repo, number:5181}) "
        "RETURN r.source_url AS url, r.snapshot_at AS snapshot, "
        "r.relationship_type AS type, r.provenance AS provenance"
    )
    rows = real.query(query, params)
    assert rows and rows[0]["snapshot"]
    assert rows[0]["url"] == "https://github.com/urllib3/urllib3/pull/5242"
    assert rows[0]["type"] == "REFERENCES"
    assert rows[0]["provenance"] == "github_api_snapshot_text"
    directory = tmp_path / "snapshots"
    records = json.loads((directory / "work.json").read_text())
    pr = next(record for record in records if record["number"] == 5242)
    pr["body"] = "No issue reference in refreshed snapshot"
    pr["comments_snapshot"] = [
        {
            "id": 9000000000001,
            "html_url": "https://example.invalid/synthetic-comment",
            "body": "Synthetic test mention of #5181",
        }
    ]
    pr["reviews_snapshot"] = []
    manifest = json.loads((directory / "manifest.json").read_text())

    def refresh():
        raw = json.dumps(records).encode()
        (directory / "work.json").write_bytes(raw)
        manifest["work_sha256"] = hashlib.sha256(raw).hexdigest()
        (directory / "manifest.json").write_text(json.dumps(manifest))
        ingest_snapshots(real, directory)

    refresh()
    assert real.query(query, params)[0]["url"] == "https://example.invalid/synthetic-comment"
    provenance = real.query(
        "MATCH (p:PR {repo_id:$repo, number:5242})-[r:REFERENCES]->"
        "(:Issue {repo_id:$repo, number:5181}) "
        "RETURN r.source_uid AS source, r.resolution_verified AS verified",
        params,
    )
    assert provenance == [
        {
            "source": f"{real.cfg.repo_id}:pr:5242:comment:9000000000001:source",
            "verified": False,
        }
    ]
    refresh()
    assert len(real.query(query, params)) == 1
    pr["comments_snapshot"] = []
    refresh()
    assert not real.query(query, params)
    assert not real.query("MATCH (:PR {repo_id:$repo})-[:CONSTRAINS]->(:Symbol) RETURN 1", params)
