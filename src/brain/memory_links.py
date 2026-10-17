"""Version-pinned, independently reviewed memory relationship assertions.

Relationships describe evidence; they never approve decisions or erase an older
memory. Both endpoints are in one authorized brain. Cross-brain provenance stays
with the separate SAME_CITATION projection.
"""

import json
import re

from .memory import canonical, citations, digest, now

RELATIONS = {"UPDATES", "EXTENDS", "RELATES_TO"}


class MemoryLinks:
    def __init__(self, memory):
        self.memory = memory

    def endpoint(self, brain, uid, expected):
        self.memory.authorize(brain)
        reviewer = self.memory._role(brain) in {"owner", "reviewer"}
        row = self.memory.db.execute(
            "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=? AND hash=? "
            "AND (state='accepted' OR (state='proposed' AND (author=? OR ?))) "
            "AND (expires='' OR expires>?)",
            (
                self.memory.identity.tenant,
                brain,
                uid,
                expected,
                self.memory.identity.principal,
                reviewer,
                now(),
            ),
        ).fetchone()
        if row is None:
            raise ValueError("Relationship endpoint unavailable or changed")
        return row

    def put(self, brain, source, source_hash, relation, target, target_hash, sources):
        """Write inside the caller's transaction, including transactional imports."""
        self.memory.authorize(brain, write=True)
        if not isinstance(relation, str) or relation not in RELATIONS:
            raise ValueError("Unsupported memory relationship")
        if (
            not all(isinstance(x, str) for x in (source, target, source_hash, target_hash))
            or source == target
            or not all(re.fullmatch(r"[0-9a-f]{64}", x) for x in (source_hash, target_hash))
        ):
            raise ValueError("Distinct exact-version endpoints required")
        citations(sources)
        a = self.endpoint(brain, source, source_hash)
        b = self.endpoint(brain, target, target_hash)
        evidence = {canonical(s) for row in (a, b) for s in json.loads(row["sources"])}
        if any(canonical(s) not in evidence for s in sources):
            raise ValueError("Relationship citations must belong to the selected endpoints")
        sources = sorted({canonical(s) for s in sources})
        body = [source, source_hash, relation, target, target_hash, sources]
        uid = "L-" + digest(canonical(body))
        row = self.memory.db.execute(
            "SELECT * FROM memory_links WHERE tenant=? AND brain=? AND uid=?",
            (self.memory.identity.tenant, brain, uid),
        ).fetchone()
        if row:
            if row["state"] != "accepted" and row["author"] != self.memory.identity.principal:
                self.memory.authorize(brain, review=True)
            return {"uid": uid, "state": row["state"], "binding": False}
        count = self.memory.db.execute(
            "SELECT count(*) FROM memory_links WHERE tenant=? AND brain=?",
            (self.memory.identity.tenant, brain),
        ).fetchone()[0]
        if count >= 2000:
            raise ValueError("Relationship bound exceeded; partition this brain")
        self.memory.db.execute(
            "INSERT INTO memory_links VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.memory.identity.tenant,
                brain,
                uid,
                source,
                source_hash,
                target,
                target_hash,
                relation,
                canonical([json.loads(s) for s in sources]),
                self.memory.identity.principal,
                "proposed",
            ),
        )
        self.memory._event(brain, uid, "relationship_proposed", canonical(body))
        return {"uid": uid, "state": "proposed", "binding": False}

    def propose(self, brain, source, source_hash, relation, target, target_hash, sources):
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            return self.put(brain, source, source_hash, relation, target, target_hash, sources)

    def suggest(self, brain, selections):
        """Propose RELATES_TO for explicit shared identifiers; never infer updates."""
        from .memory_graph import entities

        if (
            not isinstance(selections, dict)
            or not 2 <= len(selections) <= 50
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in selections.items())
        ):
            raise ValueError("Select two to 50 exact current records")
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            self.memory.authorize(brain, write=True)
            rows = [self.endpoint(brain, uid, sha) for uid, sha in sorted(selections.items())]
            if any(row["state"] != "accepted" for row in rows):
                raise ValueError("Suggestions require accepted endpoints")
            candidates = [
                (a, b)
                for i, a in enumerate(rows)
                for b in rows[i + 1 :]
                if set(entities(a["text"])) & set(entities(b["text"]))
            ]
            if len(candidates) > 200:
                raise ValueError("More than 200 suggestions; narrow the selection")
            result = []
            for a, b in candidates:
                proof = [json.loads(a["sources"])[0], json.loads(b["sources"])[0]]
                result.append(
                    self.put(brain, a["uid"], a["hash"], "RELATES_TO", b["uid"], b["hash"], proof)
                )
            return {
                "items": result,
                "binding": False,
                "basis": "shared_explicit_code_identifier",
            }

    def review(self, brain, uid, action, expected_state, reason):
        if (
            action not in {"accept", "reject", "rollback"}
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError("Relationship review action and reason required")
        with self.memory.lock, self.memory.db:
            self.memory.db.execute("BEGIN IMMEDIATE")
            self.memory.authorize(brain, review=True)
            row = self.memory.db.execute(
                "SELECT * FROM memory_links WHERE tenant=? AND brain=? AND uid=? AND state=?",
                (self.memory.identity.tenant, brain, uid, expected_state),
            ).fetchone()
            if row is None:
                raise ValueError("Relationship review conflict")
            if action == "accept":
                a = self.endpoint(brain, row["source_uid"], row["source_hash"])
                b = self.endpoint(brain, row["target_uid"], row["target_hash"])
                if any(r["state"] != "accepted" for r in (a, b)):
                    raise ValueError("Accept the exact endpoint records before their relationship")
            state = {"accept": "accepted", "reject": "rejected", "rollback": "proposed"}[action]
            self.memory.db.execute(
                "UPDATE memory_links SET state=? WHERE tenant=? AND brain=? AND uid=? AND state=?",
                (state, self.memory.identity.tenant, brain, uid, expected_state),
            )
            self.memory._event(
                brain,
                uid,
                "relationship_" + action,
                canonical({"reason": reason, "expected_state": expected_state}),
            )
            return {"uid": uid, "state": state, "binding": False}

    def visible(self, brain, records, include_proposals=False):
        """Caller holds a catalog transaction; hidden/stale endpoints never join."""
        self.memory.authorize(brain)
        reviewer = self.memory._role(brain) in {"owner", "reviewer"}
        eligible = {
            r["uid"]: r
            for r in records
            if r["tenant"] == self.memory.identity.tenant
            and r["brain"] == brain
            and (not r["expires"] or r["expires"] > now())
            and (
                r["state"] == "accepted"
                or (
                    r["state"] == "proposed"
                    and include_proposals
                    and (r["author"] == self.memory.identity.principal or reviewer)
                )
            )
        }
        rows = self.memory.db.execute(
            "SELECT * FROM memory_links WHERE tenant=? AND brain=? "
            "AND (state='accepted' OR (state='proposed' AND ? AND (author=? OR ?))) "
            "ORDER BY uid LIMIT 2001",
            (
                self.memory.identity.tenant,
                brain,
                include_proposals,
                self.memory.identity.principal,
                reviewer,
            ),
        ).fetchall()
        if len(rows) > 2000:
            raise ValueError("Relationship bound exceeded")
        result = []
        for row in rows:
            a, b = eligible.get(row["source_uid"]), eligible.get(row["target_uid"])
            if (
                a is None
                or b is None
                or a["hash"] != row["source_hash"]
                or b["hash"] != row["target_hash"]
            ):
                continue
            if row["state"] == "accepted" and any(r["state"] != "accepted" for r in (a, b)):
                continue
            result.append(dict(row))
        return result
