"""Selected local operator copies across repositories; never tenant federation."""

from ..memory import canonical, digest, now
from . import personal


def preview(state, target, origin, uids):
    if target == origin or not 1 <= len(uids) <= 10 or len(set(uids)) != len(uids):
        raise ValueError("Select one to ten distinct memories from another repository")
    for project in (target, origin):
        if state.get(project, "repository")["status"] != "ready":
            raise ValueError("Both repositories must be ready")
        if state.config(project).principal != "app_operator":
            raise PermissionError("Transfers require the managed local operator")
    cfg = state.config(origin)
    records = []
    with personal.catalog(cfg) as (memory, _projection):
        for uid in sorted(uids):
            r = personal.row(memory, uid)
            if r["state"] != "accepted" or (r["expires"] and r["expires"] <= now()):
                raise ValueError("Only currently accepted unexpired memories can transfer")
            records.append(
                {
                    "origin_uid": uid,
                    "origin_hash": r["hash"],
                    "text": r["text"],
                    "expires": r["expires"],
                    "source_provenance": [
                        {
                            "kind": source["kind"],
                            "uri": source["uri"],
                            "digest": source["digest"],
                            "selected_text_digest": digest(r["text"]),
                            "verification": "origin_source_checked_at_transfer",
                        }
                        for source in personal.source_details(cfg, memory, r)
                    ],
                }
            )
    if len(canonical(records)) > 100000:
        raise ValueError("Transfer source snapshots exceed 100 KB")
    value = {
        "kind": "selected_repository_transfer",
        "origin": origin,
        "target": target,
        "records": records,
        "binding": False,
    }
    return {**value, "consent_digest": digest(canonical(value))}


def import_selected(state, target, origin, uids, consent):
    value = preview(state, target, origin, uids)
    if value["consent_digest"] != consent:
        raise ValueError("Transfer preview changed; inspect and confirm the new preview")
    cfg = state.config(target)
    with personal.catalog(cfg) as (memory, projection):
        with memory.db:
            memory.db.execute("BEGIN IMMEDIATE")
            results = []
            for record in value["records"]:
                saved = {"kind": value["kind"], "origin": origin, "target": target, **record}
                fingerprint = personal.snapshot(cfg, saved)
                results.append(
                    memory.put(
                        personal.brain(memory),
                        record["text"],
                        [
                            {
                                "uri": "urn:company-brain:transfer:" + fingerprint,
                                "digest": fingerprint,
                            }
                        ],
                        uid="transfer:" + fingerprint,
                        expires=record["expires"],
                    )
                )
            memory._event(personal.brain(memory), consent, "app_repository_transfer", origin)
        return {
            "items": results,
            "projection": personal.refresh(memory, projection),
            "binding": False,
        }
