"""Database-only acceptance checks; this script does not drive or test the Browser UI."""

import argparse
import json
from pathlib import Path

from prepare_browser_demo import REPO, ROOT, SHA

from brain.config import load_config
from brain.graph import GraphStore


def verify(config, require_approved=False, output=None):
    cfg = load_config(config)
    if cfg.repo_id != REPO or cfg.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Expected the reconstructed demo namespace on a loopback connection")
    store = GraphStore(cfg)
    assert store.revision() == {"sha": SHA, "syncing": False}
    queries = {}
    for path in sorted((ROOT / "docs/browser-demo").glob("*.cypher")):
        rows = store.query(path.read_text(encoding="utf-8"))
        queries[path.name] = {"row_count": len(rows)}
        if path.name.startswith(("04", "06", "07", "08", "09", "10")):
            queries[path.name]["result"] = rows
        assert rows or path.name.startswith("05"), path.name
    assert queries["01-document.cypher"]["row_count"] == 1
    assert queries["02-direct-caller.cypher"]["row_count"] == 1
    assert queries["03-reexport.cypher"]["row_count"] == 1
    assert queries["04-proposals.cypher"]["row_count"] == 6
    assert queries["09-call-resolution.cypher"]["result"] == [
        {"caller_path": "HTTPConnectionPool.urlopen → set_file_position", "call_line": 772,
         "definition_line": 176, "confidence": "static",
         "resolution": "statically_resolved_import"},
        {"caller_path": "WrappedSocket.recv → wait_for_read", "call_line": 324,
         "definition_line": 113, "confidence": "static",
         "resolution": "statically_resolved_import"},
    ]
    source_rows = store.query(
        "MATCH (d:Decision {repo_id:$repo})-[:SUPPORTED_BY]->(s:Source) "
        "RETURN d.uid AS decision,s.uid AS source ORDER BY decision,source",
        {"repo": REPO})
    base = f"{REPO}@{SHA}:"
    cleanup = base + "src/urllib3/connectionpool.py:L910-L922:source"
    rewind = base + "src/urllib3/util/request.py:L176-L230:source"
    expected = {
        "D-1": {f"{REPO}:pr:5161:source", cleanup},
        "D-2": {f"{REPO}:pr:5161:source", cleanup, f"{REPO}:pr:3780:source", rewind},
    }
    for decision, sources in expected.items():
        assert {row["source"] for row in source_rows if row["decision"] == decision} == sources
    decisions = store.query(
        "MATCH (d:Decision {repo_id:$repo}) RETURN d.uid AS uid,d.status AS status,"
        "d.approval AS approval,d.approved_by AS approved_by,d.approved_at AS approved_at,"
        "d.approved_revision AS approved_revision ORDER BY uid", {"repo": REPO})
    assert [row["uid"] for row in decisions] == ["D-1", "D-2"]
    approved = [row["status"] for row in decisions] == ["superseded", "active"]
    if approved:
        assert queries["05-supersession.cypher"]["row_count"] == 8
        assert all(row["approval"] == "human_approved" and row["approved_by"]
                   and row["approved_at"] and row["approved_revision"] == SHA for row in decisions)
    else:
        assert queries["05-supersession.cypher"]["row_count"] == 0
    assert store.db.list_graphs() == ["org_demo"]
    report = {"verification_layer": "database", "browser_ui_tested_by_this_script": False,
              "connection": {"host": cfg.host, "port": cfg.port}, "repo_id": REPO, "revision": SHA, "queries": queries,
              "source_links_retained": True, "approved_supersession_verified": approved,
              "decisions": decisions}
    output = output or ROOT / "data/validation/browser-demo/verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verification_layer": "database",
                      "browser_ui_tested_by_this_script": False, "query_files": len(queries), "source_links_retained": True,
                      "approved_supersession_verified": approved,
                      "decision_statuses": {row["uid"]: row["status"] for row in decisions}},
                     indent=2))
    if require_approved and not approved:
        raise SystemExit("Independent human approval is still pending")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=ROOT / "config/brain.browser-demo.local.yaml")
    parser.add_argument("--require-approved", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/validation/browser-demo/verification.json")
    args = parser.parse_args()
    verify(args.config.resolve(), args.require_approved, args.output.resolve())
