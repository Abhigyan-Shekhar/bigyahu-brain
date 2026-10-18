"""GitHub metadata remains evidence; running file scopes never imply human presence."""
from types import SimpleNamespace

from brain.app.graph_workspace import active_node_runs
from brain.app.state import State
from brain.ingest.snapshots import ingest_snapshots


def test_live_runs_require_running_matching_repository_and_file(tmp_path):
    state = State(tmp_path, None, "test")
    run = state.create("action", "one", status="running", phase="execution", plan={"files": ["a.py"]})
    state.create("action", "two", status="running", plan={"files": ["a.py"]})
    state.create("action", "one", status="queued", plan={"files": ["a.py"]})
    assert [r["id"] for r in active_node_runs(state, "one", "a.py")] == [run["id"]]
    assert not active_node_runs(state, "one", "b.py")
    assert not active_node_runs(state, "one", None)
    state.update(run["id"], status="complete")
    assert not active_node_runs(state, "one", "a.py")


def test_snapshot_metadata_keeps_event_time_separate_from_collection(monkeypatch):
    from brain.ingest import snapshots

    class Store:
        cfg = SimpleNamespace(repo_id="fixture")
        def __init__(self):
            self.nodes = {}
        def query(self, *_):
            return []
        def upsert(self, label, uid, props):
            self.nodes[uid] = props
        def edge(self, *_):
            pass

    record = {
        "number": 1, "title": "Deadline", "body": "untrusted", "state": "open",
        "html_url": "https://github.com/test/repo/issues/1", "user": {"login": "author"},
        "updated_at": "2026-10-17T01:00:00Z", "created_at": "2026-10-16T00:00:00Z",
        "milestone": {"due_on": "2026-10-20T00:00:00Z"},
        "comments_snapshot": [{"id": 3, "html_url": "https://github.com/test/repo/issues/1#3",
                               "body": "decision candidate", "created_at": "2026-10-17T02:00:00Z"}],
    }
    manifest = {"repo_id": "fixture", "repo_url": "https://github.com/test/repo",
                "visibility": "public", "sha": "rev", "collected_at": "2026-10-18T00:00:00Z"}
    monkeypatch.setattr(snapshots, "read_snapshot", lambda _: (manifest, [record]))
    store = Store()
    ingest_snapshots(store, "unused")
    assert store.nodes["fixture:issue:1"]["due_at"] == "2026-10-20T00:00:00Z"
    assert store.nodes["fixture:issue:1"]["updated_at"] != manifest["collected_at"]
    assert store.nodes["fixture:issue:1:comment:3:source"]["created_at"] == "2026-10-17T02:00:00Z"
    assert "modified_by" not in store.nodes["fixture:issue:1"]
    record["milestone"] = None
    ingest_snapshots(store, "unused")
    assert store.nodes["fixture:issue:1"]["due_at"] is None
