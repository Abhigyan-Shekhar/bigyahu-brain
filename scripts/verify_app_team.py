"""Recheck an existing team-sharing browser run and real Codex recall.

Read-only: no model calls, role changes or review mutations. Raw text, runtime
paths and identity names remain outside the sanitized public report.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from brain.app import personal, team
from brain.app.evidence import resolve, verified_claims
from brain.app.state import State
from brain.config import load_config
from brain.graph import GraphStore


def verify(state, project, name, reader, turn, audit):
    cfg = state.config(project)
    reader_cfg = replace(cfg, principal=reader)
    result = team.search(reader_cfg, "retry")
    assert result["status"] == "ok" and result["backend"] == "falkor"
    assert not result["vector_enabled"] and len(result["items"]) == 1
    selected = result["items"][0]
    assert selected["brain"] == team.scope(name)
    evidence = team.memory_evidence(reader_cfg, name, selected["uid"], selected["hash"])
    assert any(e["relation"] == "SUPPORTED_BY" for e in evidence["graph"]["edges"])
    with personal.catalog(cfg) as (memory, projection):
        info = team.team_info(memory, name)
        assert info["can_administer"]
        source = team.source_details(cfg, memory, team.record(memory, name, selected["uid"]))
        snapshot = json.loads(
            (cfg.repo_root.parent / "memory-sources" / source["digest"]).read_text()
        )
        assert set(snapshot) == {"text", "sources", "hash", "author", "binding"}
        events = memory.db.execute(
            "SELECT detail FROM events WHERE tenant=? AND brain=? AND uid=? AND action='app_membership' ORDER BY rowid",
            (memory.identity.tenant, team.scope(name), reader),
        ).fetchall()
        roles = [json.loads(e[0])["role"] for e in events]
        assert roles == ["reader", "revoke", "reader"]
        author_view = team.graph(cfg, memory, projection, [team.scope(name)], member=cfg.principal)
        reader_view = team.graph(cfg, memory, projection, [team.scope(name)], member=reader)
        assert any(n["labels"] == ["Memory"] for n in author_view["graph"]["nodes"])
        assert not any(n["labels"] == ["Memory"] for n in reader_view["graph"]["nodes"])
        assert all(not n["label"].startswith("private:") for n in author_view["graph"]["nodes"])
    before = json.loads((audit / "pre-review.json").read_text())
    revoked = json.loads((audit / "revocation-check.json").read_text())
    assert before == {"status": "ok", "reader_items_before_acceptance": 0}
    assert revoked == {"revoked_reader_search_empty": True, "prior_citation_rejected": True}
    value = state.get(turn, "turn")
    assert value["status"] == "complete" and value["project"] == project
    with state.connect() as db:
        session = db.execute("SELECT parent FROM objects WHERE id=?", (turn,)).fetchone()[0]
    assert len(state.list("turn", session)) == 1
    folder = state.folder(project) / "turns" / turn
    manifest = json.loads((folder / "invocation.json").read_text())
    for path, expected in manifest["backend_source_sha256"].items():
        assert (
            hashlib.sha256((Path(__file__).parents[1] / "src" / path).read_bytes()).hexdigest()
            == expected
        )
    claims = verified_claims(GraphStore(cfg), folder / "evidence", {"claims": value["claims"]})
    team_supports = 0
    for claim in claims:
        for support in claim["support"]:
            saved = json.loads(
                (folder / "evidence" / (support["evidence_id"] + ".json")).read_text()
            )
            current = resolve(GraphStore(cfg), saved)
            if current["kind"] == "team_memory":
                assert current["ref"]["name"] == name and current["ref"]["uid"] == selected["uid"]
                team_supports += 1
    assert team_supports > 0
    calls = []
    for line in (folder / "trace.jsonl").read_text().splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "mcp_tool_call":
            calls.append(item)
    searches = [c for c in calls if c["tool"] == "memory_search" and c["status"] == "completed"]
    assert searches
    assert all(c["tool"] in manifest["tools"] for c in calls)
    payloads = [json.loads(c["result"]["content"][0]["text"]) for c in searches]
    assert any(
        p["backend"] == "falkor" and any(e["kind"] == "team_memory" for e in p["checked_evidence"])
        for p in payloads
    )
    return {
        "status": "passed",
        "fixture": "Disposable synthetic retry repository",
        "model": manifest["model_requested"],
        "independent_conversation_turns": 1,
        "checked_claims": len(claims),
        "team_memory_supports": team_supports,
        "native_memory_search_calls": len(searches),
        "vector_enabled": False,
        "backend_implementation_hashes_match_agent_run": True,
        "reader_items_before_acceptance": 0,
        "reader_items_after_acceptance": 1,
        "membership_lifecycle": roles,
        "revocation": revoked,
        "selected_shared_snapshot_excludes_private_envelope": True,
        "member_views_filter_only_shared_contributions": True,
        "source_snapshot_sha256": source["digest"],
        "limits": [
            "Trusted loopback operator and repository-scoped catalog principals; no hosted member login",
            "Member navigation filters authorized shared contributions, never another private brain",
            "Sharing is an independent proposal; team review and private review remain separate",
            "At most ten retrieval scopes; stale, unavailable or invalid evidence fails closed",
            "No automatic company semantic federation or general recall/coding-quality claim",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "data", "project", "team", "reader", "turn", "audit", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    state = State(
        args.data, load_config(Path(args.config).resolve()), "verification-only", recover=False
    )
    result = verify(state, args.project, args.team, args.reader, args.turn, Path(args.audit))
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Verified selected sharing, reader boundaries, member slices and real team-memory recall")


if __name__ == "__main__":
    main()
