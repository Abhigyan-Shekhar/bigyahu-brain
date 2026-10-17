"""Recheck a reviewed coding lesson and its independent real-agent recall.

Reads an existing disposable app run. Does not invoke a model or mutate reviews.
Only sanitized counts, hashes and verification outcomes enter the output report.
"""

import argparse
import hashlib
import json
from pathlib import Path

from brain.app.evidence import resolve, verified_claims
from brain.app.personal import brain, catalog, row, search, source_details
from brain.app.state import State
from brain.config import load_config
from brain.graph import GraphStore


def verify(state, project, action, turn, revocation):
    cfg = state.config(project)
    uid = "lesson:" + action
    with catalog(cfg) as (memory, _):
        record = row(memory, uid)
        assert record["state"] == "accepted"
        sources = source_details(cfg, memory, record)
        reviews = memory.db.execute(
            "SELECT action FROM events WHERE tenant=? AND brain=? AND uid=? ORDER BY rowid",
            (memory.identity.tenant, brain(memory), uid),
        ).fetchall()
        lifecycle = [r["action"] for r in reviews]
        assert lifecycle.count("accept") >= 2 and "rollback" in lifecycle
        rejected = memory.db.execute(
            "SELECT count(*) FROM records WHERE tenant=? AND brain=? AND state='rejected'",
            (memory.identity.tenant, brain(memory)),
        ).fetchone()[0]
        assert rejected > 0
    result = search(cfg, "retry delays")
    assert result["status"] == "ok" and result["backend"] == "falkor"
    assert not result["vector_enabled"]
    assert uid in {r["uid"] for r in result["items"]}
    value = state.get(turn, "turn")
    assert value["project"] == project and value["status"] == "complete"
    with state.connect() as db:
        parent = db.execute("SELECT parent FROM objects WHERE id=?", (turn,)).fetchone()[0]
    assert len(state.list("turn", parent)) == 1, "Recall must use an independent conversation"
    folder = state.folder(project) / "turns" / turn
    invocation = json.loads((folder / "invocation.json").read_text())
    for path, expected in invocation["backend_source_sha256"].items():
        assert (
            hashlib.sha256((Path(__file__).parents[1] / "src" / path).read_bytes()).hexdigest()
            == expected
        )
    store = GraphStore(cfg)
    claims = verified_claims(store, folder / "evidence", {"claims": value["claims"]})
    assert len(claims) >= 1
    checked = []
    for claim in claims:
        for support in claim["support"]:
            saved = json.loads(
                (folder / "evidence" / (support["evidence_id"] + ".json")).read_text()
            )
            current = resolve(store, saved)
            assert current["kind"] == "memory" and current["ref"]["uid"] == uid
            assert any(e["relation"] == "SUPPORTED_BY" for e in current["graph"]["edges"])
            checked.append(current["digest"])
    calls = []
    for line in (folder / "trace.jsonl").read_text().splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            calls.append(item)
    assert calls and all(c["tool"] in invocation["tools"] for c in calls)
    native = [c for c in calls if c["tool"] == "memory_search" and c["status"] == "completed"]
    assert native
    payload = json.loads(native[0]["result"]["content"][0]["text"])
    assert payload["backend"] == "falkor" and payload["checked_evidence"]
    assert revocation == {"native_search_empty": True, "old_citation_rejected": True}
    return {
        "status": "passed",
        "fixture": "Disposable synthetic retry repository; local operator private brain",
        "model": invocation["model_requested"],
        "independent_conversation_turns": 1,
        "checked_claims": len(claims),
        "memory_search_calls": len(native),
        "retrieval_backend": "falkor",
        "vector_enabled": False,
        "native_source_relationship_checked": True,
        "coding_report_snapshot_checked": bool(sources),
        "memory_text_sha256": sorted(set(checked)),
        "backend_implementation_hashes_match_agent_run": True,
        "rejected_proposals": rejected,
        "review_lifecycle": [a for a in lifecycle if a in {"accept", "rollback", "reject"}],
        "revocation_check": revocation,
        "limits": [
            "Personal catalog and identity are local and repository-scoped; no team UI or hosted identity",
            "Rejected and proposed memories are excluded from chat; accepted memory remains advisory",
            "Consent covers selected completed user turns only; no automatic transcript scraping",
            "Semantic relationship proposals still require separate backend review",
            "This verifies one synthetic workflow, not general recall or coding quality",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "data", "project", "action", "turn", "revocation", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    state = State(
        args.data, load_config(Path(args.config).resolve()), "verification-only", recover=False
    )
    result = verify(
        state, args.project, args.action, args.turn, json.loads(Path(args.revocation).read_text())
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "Verified reviewed lesson, independent native recall, source citations and review lifecycle"
    )


if __name__ == "__main__":
    main()
