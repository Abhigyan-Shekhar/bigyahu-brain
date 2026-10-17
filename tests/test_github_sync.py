"""Incremental acquisition failures cannot advance state or partially mutate graphs."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from brain.ingest.github_sync import GitHub, sync_github


def store():
    result = Mock(
        cfg=SimpleNamespace(
            repo_id="fixture", repo_url="https://github.com/test/repo", tenant_id=""
        )
    )
    result.revision.return_value = {"sha": "pinned", "syncing": False}
    result.query.return_value = [{"cursor": None}]
    return result


class API:
    def get(self, path, params=None):
        if path == "repos/test/repo":
            return {"id": 1, "full_name": "test/repo", "private": False}
        if path.endswith("/pulls"):
            return [{"number": 7, "updated_at": "2026-10-17T00:00:00Z"}]
        if path.endswith("/pulls/7"):
            return {"merged_at": None, "changed_files": 1}
        raise AssertionError(path)

    def pages(self, path, params=None, max_pages=100):
        if path.endswith("/issues"):
            return [
                {
                    "number": 7,
                    "title": "Replay",
                    "body": "untrusted",
                    "html_url": "https://github.com/test/repo/pull/7",
                    "state": "open",
                    "pull_request": {},
                }
            ]
        if path.endswith("/files"):
            return [{"filename": "x.py"}]
        if path.endswith("/reviews"):
            return [
                {
                    "id": 1,
                    "html_url": "https://github.com/test/repo/pull/7#review-1",
                    "body": "review",
                    "state": "APPROVED",
                }
            ]
        if path.endswith("/comments"):
            return [
                {
                    "id": 1,
                    "html_url": "https://github.com/test/repo/pull/7#comment-1",
                    "body": "comment",
                }
            ]
        raise AssertionError(path)


def test_acquisition_failure_does_not_write_or_advance_cursor(tmp_path):
    graph = store()
    api = API()
    api.pages = Mock(side_effect=RuntimeError("rate limit"))
    with pytest.raises(RuntimeError, match="rate limit"):
        sync_github(graph, tmp_path / "capture", api)
    assert len(graph.query.call_args_list) == 1
    assert not (tmp_path / "capture").exists()


def test_complete_batch_has_disjoint_comment_ids_and_immutable_sources(tmp_path, monkeypatch):
    import brain.ingest.github_sync as module

    graph = store()
    publish = Mock(return_value={"records": 1})
    monkeypatch.setattr(module, "ingest_snapshots", publish)
    result = sync_github(graph, tmp_path / "capture", API())
    from brain.ingest.snapshots import read_snapshot

    manifest, records = read_snapshot(tmp_path / "capture")
    assert manifest["immutable_sources"] is True
    assert records[0]["reviews_snapshot"][0]["id"] == "review:1"
    assert {c["id"] for c in records[0]["comments_snapshot"]} == {"issue:1", "inline:1"}
    assert result["cursor"]
    assert "github_cursor" in graph.query.call_args_list[-1].args[0]


def test_failed_graph_publish_keeps_reader_fence_and_cursor(tmp_path, monkeypatch):
    import brain.ingest.github_sync as module

    graph = store()
    monkeypatch.setattr(module, "ingest_snapshots", Mock(side_effect=RuntimeError("write failed")))
    with pytest.raises(RuntimeError, match="write failed"):
        sync_github(graph, tmp_path / "capture", API())
    mutations = [call.args[0] for call in graph.query.call_args_list if "SET" in call.args[0]]
    assert mutations == ["MATCH (p:Project {uid:$repo}) SET p.github_syncing=true"]


def test_pagination_refuses_silent_truncation():
    api = GitHub()
    api.get = Mock(return_value=[{}] * 100)
    with pytest.raises(ValueError, match="pagination bound"):
        api.pages("repos/test/repo/issues", max_pages=2)


def test_repository_recreation_cannot_reuse_old_cursor(tmp_path):
    graph = store()
    graph.query.return_value = [{"cursor": None, "repository_id": 999}]
    with pytest.raises(ValueError, match="repository ID changed"):
        sync_github(graph, tmp_path / "capture", API())
    assert len(graph.query.call_args_list) == 1


def test_missing_changed_files_fails_before_graph_writes(tmp_path):
    graph = store()
    api = API()
    original = api.get
    api.get = lambda path, params=None: (
        {"changed_files": 2} if path.endswith("/pulls/7") else original(path, params)
    )
    with pytest.raises(ValueError, match="coverage incomplete"):
        sync_github(graph, tmp_path / "capture", api)
    assert len(graph.query.call_args_list) == 1
