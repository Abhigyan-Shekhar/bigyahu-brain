"""Verify browser abhi round-trip and an optional integrated synthetic coding run.

Existing live state only. --action also replays its patch in a disposable clone
through the fail-closed sandbox and 15 held-out cases; no review or grant is made.
"""

import argparse
import hashlib
import json
from pathlib import Path

from brain.abhi_graph import validate
from brain.app import personal, team
from brain.app.agent import TOOLS
from brain.app.evidence import resolve, verified_claims
from brain.app.state import State
from brain.config import load_config
from brain.graph import GraphStore


def verify(state, project, name, audit, turn=None, action=None, recall=None):
    original = json.loads((audit / "original.abhi").read_text())
    reexported = json.loads((audit / "reexported.abhi").read_text())
    validate(original)
    validate(reexported)
    assert original == reexported
    observed = json.loads((audit / "pre-review.json").read_text())
    assert (
        observed["envelope_digest"] == original["digest"] and observed["absent_from_native_search"]
    )
    cfg = state.config(project)
    assert original["tenant"] == cfg.tenant_id and original["team"] == name
    uid = observed["imported_uid"]
    with personal.catalog(cfg) as (memory, _):
        record = team.record(memory, name, uid)
        assert record["state"] == "accepted"
        source = team.source_details(cfg, memory, record)
        assert source["kind"] == "abhi_import"
        fingerprint = record["hash"]
        batch = memory.db.execute(
            "SELECT hash FROM imports WHERE tenant=? AND brain=? AND collection=?",
            (cfg.tenant_id, team.scope(name), original["collection"]),
        ).fetchone()
        assert batch[0] == original["digest"]
        exports = memory.db.execute(
            "SELECT count(*) FROM events WHERE tenant=? AND brain=? AND action='graph_export' AND detail=?",
            (cfg.tenant_id, team.scope(name), original["digest"]),
        ).fetchone()[0]
        assert exports >= 4
    evidence = team.memory_evidence(cfg, name, uid, fingerprint)
    assert evidence["verification"] == "accepted_imported_memory_and_native_graph"
    assert any(e["relation"] == "SUPPORTED_BY" for e in evidence["graph"]["edges"])
    result = team.search(cfg, uid)
    assert (
        result["status"] == "ok" and result["backend"] == "falkor" and not result["vector_enabled"]
    )
    assert uid in {r["uid"] for r in result["items"]}
    report = {
        "status": "passed",
        "fixture": "Existing indexed disposable synthetic retry repository",
        "format": "abhi/2",
        "records": len(original["records"]),
        "portable_nodes": len(original["graph"]["nodes"]),
        "portable_edges": len(original["graph"]["edges"]),
        "envelope_digest": original["digest"],
        "browser_reexport_preserves_entire_envelope": True,
        "imported_proposal_excluded_before_review": True,
        "accepted_import_retrieved_natively": True,
        "original_envelope_and_selected_record_snapshots_checked": True,
        "origin_authenticated": False,
    }

    def check_claims(folder, value):
        claims = verified_claims(GraphStore(cfg), folder / "evidence", {"claims": value["claims"]})
        kinds = set()
        for claim in claims:
            for support in claim["support"]:
                saved = json.loads(
                    (folder / "evidence" / (support["evidence_id"] + ".json")).read_text()
                )
                current = resolve(GraphStore(cfg), saved)
                kinds.add(
                    "reviewed_import"
                    if current.get("verification") == "accepted_imported_memory_and_native_graph"
                    and current["ref"]["uid"] == uid
                    else current["kind"]
                )
        assert {"reviewed_import", "source"} <= kinds
        manifest = json.loads((folder / "invocation.json").read_text())
        for path, expected in manifest["backend_source_sha256"].items():
            assert (
                hashlib.sha256((Path(__file__).parents[1] / "src" / path).read_bytes()).hexdigest()
                == expected
            )
        calls = []
        for line in (folder / "trace.jsonl").read_text().splitlines():
            event = json.loads(line)
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
                calls.append(item)
        assert {"memory_search", "check_change"} <= {c["tool"] for c in calls}
        assert all(c["tool"] in manifest.get("tools", TOOLS) for c in calls)
        return {
            "checked_claims": len(claims),
            "verified_source_kinds": sorted(kinds),
            "actual_read_tool_calls": len(calls),
            "backend_hashes_match_run": True,
            "model": manifest["model_requested"],
        }

    if turn:
        value = state.get(turn, "turn")
        assert value["project"] == project and value["status"] == "complete"
        with state.connect() as db:
            parent = db.execute("SELECT parent FROM objects WHERE id=?", (turn,)).fetchone()[0]
        assert len(state.list("turn", parent)) == 1
        report["fresh_integrated_investigation"] = check_claims(
            state.folder(project) / "turns" / turn, value
        )
    if action:
        from verify_app_actions import verify as verify_action

        from brain.app.actions import action_folder

        value = state.get(action, "action")
        assert value["project"] == project and value["turn"] == turn
        plan = check_claims(action_folder(state, value) / "plan", value)
        downloaded = (audit / "downloaded.patch").read_text()
        assert downloaded == value["patch"]
        checked = verify_action(state, action)
        report["integrated_coding_action"] = {
            k: v for k, v in checked.items() if k not in {"invocations", "limits"}
        }
        report["integrated_coding_action"]["planning_evidence"] = plan
        with personal.catalog(cfg) as (memory, _):
            lesson = personal.row(memory, "lesson:" + action)
            assert lesson["state"] == "accepted"
            assert personal.source_details(cfg, memory, lesson)[0]["kind"] == "lesson"
            personal.memory_evidence(cfg, lesson["uid"], lesson["hash"])
        report["new_coding_lesson_independently_accepted_and_graph_verified"] = True
    if recall:
        assert action, "A final lesson recall needs its coding action"
        value = state.get(recall, "turn")
        assert value["project"] == project and value["status"] == "complete"
        with state.connect() as db:
            parent = db.execute("SELECT parent FROM objects WHERE id=?", (recall,)).fetchone()[0]
        assert len(state.list("turn", parent)) == 1
        folder = state.folder(project) / "turns" / recall
        claims = verified_claims(GraphStore(cfg), folder / "evidence", {"claims": value["claims"]})
        assert claims
        for claim in claims:
            for support in claim["support"]:
                saved = json.loads(
                    (folder / "evidence" / (support["evidence_id"] + ".json")).read_text()
                )
                current = resolve(GraphStore(cfg), saved)
                assert current["kind"] == "memory" and current["ref"]["uid"] == "lesson:" + action
        manifest = json.loads((folder / "invocation.json").read_text())
        for path, expected in manifest["backend_source_sha256"].items():
            assert (
                hashlib.sha256((Path(__file__).parents[1] / "src" / path).read_bytes()).hexdigest()
                == expected
            )
        calls = [
            json.loads(line).get("item", {})
            for line in (folder / "trace.jsonl").read_text().splitlines()
            if json.loads(line).get("type") == "item.completed"
        ]
        assert any(
            i.get("type") == "mcp_tool_call"
            and i.get("tool") == "memory_search"
            and i.get("status") == "completed"
            for i in calls
        )
        report["fresh_new_lesson_recall"] = {
            "checked_claims": len(claims),
            "independent_conversation_turns": 1,
            "query_mode": "User explicitly referenced the newly reviewed memory ID",
            "actual_memory_search_verified": True,
            "backend_hashes_match_run": True,
        }
    report["limits"] = [
        "App supports abhi/2 only, matching configured tenant/team; no automatic tenant remapping",
        "Origin signatures, permissions, identities and approval are not imported",
        "Relationships retain separate review after endpoint acceptance; browser fixture exported one record, relationship round-trip covered by live tests",
        "Integrated coding run starts from an existing indexed synthetic fixture; public onboarding and PDF/Word semantic ingestion have separate reports",
        "No production readiness, general recall quality or causal coding advantage is claimed",
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "data", "project", "team", "audit", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--turn")
    parser.add_argument("--action")
    parser.add_argument("--recall")
    args = parser.parse_args()
    state = State(
        args.data, load_config(Path(args.config).resolve()), "verification-only", recover=False
    )
    report = verify(
        state, args.project, args.team, Path(args.audit), args.turn, args.action, args.recall
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "Verified browser portability, native imported evidence and requested integrated workflow"
    )


if __name__ == "__main__":
    main()
