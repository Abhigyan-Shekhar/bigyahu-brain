"""Explicit app previews around strict abhi/2 interchange and review contracts."""

import json
from datetime import UTC, datetime

from ..abhi_graph import export_graph, import_graph, validate
from ..memory import canonical, digest
from ..memory_links import MemoryLinks
from . import personal, team


def parse(text):
    if len(text.encode("utf-8")) > 1_000_000:
        raise ValueError("An .abhi file must be at most 1 MB of UTF-8")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON keys are not allowed")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("Non-finite JSON values are not allowed")

    value = json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)
    validate(value)
    if len(value["records"]) > 50 or len(value.get("relations", [])) > 100:
        raise ValueError("The app accepts at most 50 selected records and 100 relationships")
    return value


def preview_import(cfg, name, text):
    with personal.catalog(cfg) as (memory, _):
        memory.authorize(team.scope(name), write=True)
        payload = parse(text)
        if payload["tenant"] != memory.identity.tenant or payload["team"] != name:
            raise PermissionError("File tenant and team must match the authorized destination")
        prior = memory.db.execute(
            "SELECT hash FROM imports WHERE tenant=? AND brain=? AND collection=?",
            (memory.identity.tenant, team.scope(name), payload["collection"]),
        ).fetchone()
        previous = prior[0] if prior else ""
    return {
        "payload": payload,
        "consent_digest": payload["digest"],
        "current_collection_digest": previous,
        "unchanged": previous == payload["digest"],
        "conflict": previous != payload["digest"] and previous != payload["parent_digest"],
        "origin_authenticated": False,
        "binding": False,
    }


def apply_import(cfg, name, text, consent_digest):
    preview = preview_import(cfg, name, text)
    payload = preview["payload"]
    if payload["digest"] != consent_digest:
        raise ValueError("Consent must match the exact validated preview")
    if preview["conflict"]:
        raise ValueError("Collection conflict; reconcile the parent digest before importing")
    with personal.catalog(cfg) as (memory, projection):
        result = import_graph(memory, payload)
        envelope_snapshot = personal.snapshot(cfg, payload)
        # The existing importer commits records/assertions atomically. App source
        # snapshots are derived afterwards. If interrupted here, acceptance stays
        # blocked until an identical replay repairs the missing snapshot proofs.
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            for item in payload["records"]:
                uid = "abhi:" + payload["collection"] + ":" + item["id"]
                r = memory.db.execute(
                    "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=?",
                    (memory.identity.tenant, team.scope(name), uid),
                ).fetchone()
                expires = (
                    datetime.fromisoformat(item["expires"]).astimezone(UTC).isoformat()
                    if item["expires"]
                    else ""
                )
                expected = digest(
                    canonical(
                        {"text": item["text"], "sources": item["sources"], "expires": expires}
                    )
                )
                if not r or r["hash"] != expected:
                    raise ValueError("Imported record changed; reconcile before replaying")
                proof = personal.snapshot(
                    cfg,
                    {
                        "kind": "abhi_import",
                        "envelope_snapshot": envelope_snapshot,
                        "record_id": item["id"],
                        "envelope_digest": payload["digest"],
                        "text": r["text"],
                        "sources": json.loads(r["sources"]),
                        "hash": r["hash"],
                        "author": r["author"],
                        "binding": False,
                    },
                )
                memory._event(team.scope(name), uid, "app_share_snapshot", proof)
        return {
            **result,
            "origin_authenticated": False,
            "projection": team.refresh(memory, projection, name),
        }


def export(cfg, name, selections, collection, links, expected_digest=""):
    if not 1 <= len(selections) <= 50 or len(links) > 100:
        raise ValueError("Select one to 50 exact accepted records and at most 100 relationships")
    with personal.catalog(cfg) as (memory, _):
        for uid in selections:
            team.source_details(cfg, memory, team.record(memory, name, uid))
        payload = export_graph(memory, team.scope(name), selections, name, collection, links)
        if expected_digest and payload["digest"] != expected_digest:
            raise ValueError("Export changed; preview the exact selection again")
        return {
            "payload": payload,
            "consent_digest": payload["digest"],
            "origin_authenticated": False,
            "binding": False,
        }


def relationships(cfg, name):
    with personal.catalog(cfg) as (memory, projection):
        rows = projection._rows(team.scope(name), True)
        return [
            {**dict(r), "sources": json.loads(r["sources"])}
            for r in MemoryLinks(memory).visible(team.scope(name), rows, True)
        ]


def review_relationship(cfg, name, uid, expected_state, action, reason):
    with personal.catalog(cfg) as (memory, projection):
        if (expected_state, action) not in {
            ("proposed", "accept"),
            ("proposed", "reject"),
            ("accepted", "rollback"),
        }:
            raise ValueError("This relationship transition is unavailable")
        if action == "accept":
            memory.authorize(team.scope(name), review=True)
            r = memory.db.execute(
                "SELECT * FROM memory_links WHERE tenant=? AND brain=? AND uid=?",
                (memory.identity.tenant, team.scope(name), uid),
            ).fetchone()
            if not r:
                raise KeyError("Unknown team relationship")
            for key in ("source_uid", "target_uid"):
                team.source_details(cfg, memory, team.record(memory, name, r[key]))
        result = MemoryLinks(memory).review(team.scope(name), uid, action, expected_state, reason)
        return {**result, "projection": team.refresh(memory, projection, name)}
