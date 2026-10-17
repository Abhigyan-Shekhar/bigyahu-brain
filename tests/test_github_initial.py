"""Initial sampling never implies complete repository history or partial children."""

from unittest.mock import Mock

import pytest
from test_github_sync import store

from brain.ingest import github_initial as initial
from brain.ingest.snapshots import read_snapshot


class API(initial.GitHub):
    def get(self, path, params=None):
        if path == "repos/test/repo":
            return {"id": 1, "full_name": "test/repo", "private": False}
        if path.endswith("/issues"):
            assert params["per_page"] == 21
            return [{"number": n} for n in range(1, 22)]
        if "/issues/" in path and not path.endswith("/comments"):
            number = int(path.rsplit("/", 1)[1])
            return {
                "number": number,
                "title": "Bug cap" if number == 1 else "Bug",
                "body": "retry overflow",
                "state": "closed",
                "html_url": f"https://github.com/test/repo/issues/{number}",
                "updated_at": "2026-10-17T00:00:00Z",
                "comments": 125 if number == 1 else 0,
                **({"pull_request": {}} if number == 1 else {}),
            }
        if path.endswith("/pulls/1"):
            return {
                "updated_at": "2026-10-17T00:00:00Z",
                "changed_files": 125,
                "review_comments": 125,
                "head": {"sha": "pinned"},
                "merged_at": None,
            }
        if path.endswith(("/files", "/reviews", "/comments")):
            assert params["per_page"] == 100
            count = 125 if "/1/" in path else 0
            return [
                {
                    "id": n,
                    "filename": f"f{n}.py",
                    "html_url": f"https://github.com/test/repo/pull/1#c{n}",
                    "body": "retry overflow",
                }
                for n in range((params["page"] - 1) * 100, min(params["page"] * 100, count))
            ]
        raise AssertionError(path)


def test_more_than_twenty_items_and_children_are_explicitly_partial_but_indivisible(
    tmp_path, monkeypatch
):
    graph = store()
    monkeypatch.setattr(initial, "ingest_snapshots", Mock(return_value={"records": 20}))
    result = initial.sync_initial(graph, tmp_path / "capture", API())
    manifest, records = read_snapshot(tmp_path / "capture")
    assert len(records) == 20 and manifest["coverage"] == result["coverage"]
    assert result["coverage"]["more_candidates"]
    assert not result["coverage"]["complete_repository_history"]
    assert len(records[0]["comments_snapshot"]) == 250
    assert len(records[0]["reviews_snapshot"]) == len(records[0]["files_snapshot"]) == 125
    assert not any("github_cursor" in c.args[0] for c in graph.query.call_args_list)


def test_incomplete_item_is_skipped_whole_not_published_with_short_children(tmp_path, monkeypatch):
    api = API()
    original = api.pages
    api.pages = lambda path, **kw: [] if path.endswith("/files") else original(path, **kw)
    monkeypatch.setattr(initial, "ingest_snapshots", Mock(return_value={"records": 19}))
    result = initial.sync_initial(store(), tmp_path / "capture", api)
    _, records = read_snapshot(tmp_path / "capture")
    assert len(records) == 19 and all(r["number"] != 1 for r in records)
    assert result["coverage"]["skipped"][0]["number"] == 1


def test_all_incomplete_fails_before_graph_publication(tmp_path):
    graph, api = store(), API()
    api.pages = Mock(side_effect=ValueError("budget"))
    with pytest.raises(ValueError, match="No complete selected"):
        initial.sync_initial(graph, tmp_path / "capture", api)
    graph.query.assert_not_called()
    assert not (tmp_path / "capture").exists()


def test_budget_accepts_normal_hundred_item_pages_and_stops_before_request(monkeypatch):
    request = Mock(return_value=list(range(100)))
    monkeypatch.setattr(initial.GitHub, "get", request)
    api = initial.BoundedGitHub()
    assert len(api.get("repos/test/repo/issues")) == 100
    api.requests = 100
    with pytest.raises(ValueError, match="request limit"):
        api.get("repos/test/repo/issues")
    assert request.call_count == 1


def test_failed_initial_publication_keeps_reader_fence(tmp_path, monkeypatch):
    graph = store()
    monkeypatch.setattr(initial, "ingest_snapshots", Mock(side_effect=RuntimeError("write")))
    with pytest.raises(RuntimeError):
        initial.sync_initial(graph, tmp_path / "capture", API())
    assert len(graph.query.call_args_list) == 1
    assert "github_syncing=true" in graph.query.call_args.args[0]
