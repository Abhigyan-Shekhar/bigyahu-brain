"""Opt-in local memory catalog. Identity comes from the server, never tool arguments.

SQLite owns proposals, ACLs, refresh transactions and derived vectors. FalkorDB
remains the authority for code/decision relationships and binding constraints.
"""

import hashlib
import json
import math
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def now():
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Identity:
    tenant: str
    principal: str

    def __post_init__(self):
        for value in (self.tenant, self.principal):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
                raise ValueError("Invalid server identity")


def citations(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise ValueError("One to twenty explicit citations required")
    for item in value:
        if not isinstance(item, dict) or set(item) != {"uri", "digest"}:
            raise ValueError("Citation requires uri and SHA-256 digest")
        uri, sha = item["uri"], item["digest"]
        if not isinstance(uri, str) or not 1 <= len(uri) <= 2000:
            raise ValueError("Invalid citation URI")
        parsed = urlsplit(uri)
        if parsed.scheme not in {"https", "urn"} or parsed.username or parsed.password:
            raise ValueError("Use credential-free HTTPS or URN citations")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("Citation digest must be SHA-256")
    return value


class Memory:
    """One operator-owned local catalog; direct file access is administrator access."""

    def __init__(self, path, identity, embedder=None):
        self.identity, self.embedder = identity, embedder
        path = Path(path)
        if not path.is_absolute() or path.is_symlink():
            raise ValueError("Memory database must be an absolute regular local path")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False)
        if __import__("os").name != "nt":
            path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA secure_delete=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1}:
            self.db.close()
            raise ValueError("Unsupported memory schema; restore compatible backup")
        if version == 0:
            self.db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE grants(tenant TEXT, principal TEXT, brain TEXT, role TEXT,
                    PRIMARY KEY(tenant,principal,brain));
                CREATE TABLE records(tenant TEXT, brain TEXT, uid TEXT, author TEXT,
                    text TEXT, sources TEXT, state TEXT, hash TEXT, previous TEXT,
                    expires TEXT, model TEXT, vector TEXT, collection TEXT,
                    PRIMARY KEY(tenant,brain,uid));
                CREATE TABLE events(tenant TEXT, brain TEXT, uid TEXT, actor TEXT,
                    action TEXT, at TEXT, detail TEXT);
                CREATE TABLE imports(tenant TEXT, brain TEXT, collection TEXT, hash TEXT,
                    PRIMARY KEY(tenant,brain,collection));
                PRAGMA user_version=1;
                COMMIT;
            """)
        if Path(path).stat().st_mode & 0o077 and __import__("os").name != "nt":
            path.chmod(0o600)

    def close(self):
        self.db.close()

    def _role(self, brain):
        if brain == "private:" + self.identity.principal:
            return "owner"
        if not re.fullmatch(r"(?:team:[A-Za-z0-9_-]{1,64}|company)", brain):
            raise PermissionError("Memory scope unavailable")
        row = self.db.execute(
            "SELECT role FROM grants WHERE tenant=? AND principal=? AND brain=?",
            (self.identity.tenant, self.identity.principal, brain),
        ).fetchone()
        if not row:
            raise PermissionError("Memory scope unavailable")
        return row[0]

    def authorize(self, brain, write=False, review=False):
        role = self._role(brain)
        if (write and role == "reader") or (review and role not in {"owner", "reviewer"}):
            raise PermissionError("Memory action unavailable")

    def _table(self, brain):
        # Hash-derived SQL identifier; authorization always precedes table selection.
        return "fts_" + digest(self.identity.tenant + ":" + brain)

    def _event(self, brain, uid, action, detail=""):
        self.db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
            (self.identity.tenant, brain, uid, self.identity.principal, action, now(), detail),
        )

    def _index(self, brain, uid, text):
        table = self._table(brain)
        self.db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING fts5(uid UNINDEXED,text)"
        )
        self.db.execute(f"DELETE FROM {table} WHERE uid=?", (uid,))
        if text:
            self.db.execute(f"INSERT INTO {table}(uid,text) VALUES(?,?)", (uid, text))

    def put(
        self, brain, text, sources, uid=None, expected="", expires="", collection="", accepted=False
    ):
        self.authorize(brain, write=True)
        if not isinstance(text, str) or not text.strip() or len(text) > 12000:
            raise ValueError("Memory text requires 1–12000 characters")
        citations(sources)
        if expires:
            expiry = datetime.fromisoformat(expires)
            if expiry.tzinfo is None or expiry <= datetime.now(UTC):
                raise ValueError("Expiry must be a future timezone-aware timestamp")
            expires = expiry.astimezone(UTC).isoformat()
        uid = uid or "M-" + uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", uid):
            raise ValueError("Invalid memory ID")
        row = self.db.execute(
            "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=?",
            (self.identity.tenant, brain, uid),
        ).fetchone()
        fingerprint = digest(canonical({"text": text, "sources": sources, "expires": expires}))
        if row and row["hash"] == fingerprint and row["state"] not in {"deleted", "rejected"}:
            return {"uid": uid, "hash": fingerprint, "state": row["state"]}
        if (row and row["hash"] != expected) or (not row and expected):
            raise ValueError("Memory revision conflict; inspect and reconcile explicitly")
        vector = self.embedder.encode(text) if self.embedder else []
        model = self.embedder.identity if self.embedder else ""
        state = "accepted" if accepted else "proposed"
        # Accepted is used only by explicit document/source ingestion, never agent memory.
        self.db.execute(
            "INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.identity.tenant,
                brain,
                uid,
                self.identity.principal,
                text,
                canonical(sources),
                state,
                fingerprint,
                row["hash"] if row else "",
                expires,
                model,
                canonical(vector),
                collection,
            ),
        )
        self._index(brain, uid, text)
        self._event(brain, uid, "refresh" if row else "create", fingerprint)
        return {"uid": uid, "hash": fingerprint, "state": state}

    def propose(self, text, sources, brain="", expires=""):
        brain = brain or "private:" + self.identity.principal
        with self.db:
            return self.put(brain, text, sources, expires=expires)

    def search(self, query, brains=None, limit=10, mode="hybrid", include_proposals=False):
        brains = list(dict.fromkeys(brains or ["private:" + self.identity.principal]))
        if len(brains) > 10 or not 1 <= limit <= 20 or not 1 <= len(query) <= 1000:
            raise ValueError("Search bounds exceeded")
        if mode not in {"hybrid", "exact", "fulltext", "vector"}:
            raise ValueError("Unknown retrieval mode")
        for brain in brains:
            self.authorize(brain)
        if mode == "vector" and not self.embedder:
            raise ValueError("Local embedding model is not configured")
        ranks, visible, warnings = {}, {}, set()
        query_vector = (
            self.embedder.encode(query) if self.embedder and mode in {"hybrid", "vector"} else None
        )
        for brain in brains:
            # ACL + state + expiry filter occurs before vector scoring or lexical ranking.
            states = ("accepted", "proposed") if include_proposals else ("accepted",)
            rows = self.db.execute(
                "SELECT * FROM records WHERE tenant=? AND brain=? AND state IN (?,?) "
                "AND (expires='' OR expires>?) ORDER BY uid LIMIT 10001",
                (self.identity.tenant, brain, states[0], states[-1], now()),
            ).fetchall()
            if len(rows) > 10000:
                raise ValueError("Scope exceeds flat-index bound; partition before searching")
            allowed = {r["uid"]: dict(r) for r in rows}
            # Build an ephemeral FTS index over exactly the eligible rows so expired,
            # rejected or hidden text cannot affect BM25 statistics or candidate limits.
            with sqlite3.connect(":memory:") as lexical:
                lexical.execute("CREATE VIRTUAL TABLE eligible USING fts5(uid UNINDEXED,text)")
                lexical.executemany(
                    "INSERT INTO eligible VALUES(?,?)",
                    ((uid, r["text"]) for uid, r in allowed.items()),
                )
                terms = re.findall(r"[\w]+", query, re.UNICODE)[:20]
                lists = []
                if mode in {"hybrid", "exact"}:
                    lists.append(
                        [
                            uid
                            for uid, r in allowed.items()
                            if uid == query
                            or any(s["uri"] == query for s in json.loads(r["sources"]))
                        ]
                    )
                if mode in {"hybrid", "fulltext"} and terms:
                    expression = " OR ".join('"' + t + '"' for t in terms)
                    lists.append(
                        [
                            r[0]
                            for r in lexical.execute(
                                "SELECT uid FROM eligible WHERE eligible MATCH ? ORDER BY rank,uid",
                                (expression,),
                            )
                        ]
                    )
                if query_vector is not None:
                    scored = []
                    for uid, row in allowed.items():
                        if row["model"] != self.embedder.identity:
                            if mode == "vector":
                                raise ValueError(
                                    "Vector model mismatch or missing embedding; reindex required"
                                )
                            warnings.add("vector_index_incomplete_reindex_required")
                            continue
                        value = json.loads(row["vector"])
                        if len(value) != len(query_vector):
                            raise ValueError("Vector dimension mismatch; reindex required")
                        scored.append((sum(a * b for a, b in zip(value, query_vector)), uid))
                    lists.append(
                        [
                            uid
                            for score, uid in sorted(scored, key=lambda p: (-p[0], p[1]))
                            if score > 0
                        ]
                    )
                for ranking in lists:
                    for position, uid in enumerate(ranking, 1):
                        key = (brain, uid)
                        ranks[key] = ranks.get(key, 0) + 1 / (60 + position)
                        visible[key] = allowed[uid]
        items = []
        for key in sorted(ranks, key=lambda k: (-ranks[k], k))[:limit]:
            row = visible[key]
            items.append(
                {
                    "uid": row["uid"],
                    "brain": key[0],
                    "text": row["text"][:2000],
                    "truncated": len(row["text"]) > 2000,
                    "hash": row["hash"],
                    "state": row["state"],
                    "sources": json.loads(row["sources"]),
                    "score": ranks[key],
                    "binding": False,
                    "trust_status": "untrusted_evidence",
                }
            )
        return {
            "items": items,
            "mode": mode,
            "binding": False,
            "vector_enabled": self.embedder is not None,
            "warnings": sorted(warnings) if self.embedder else ["vector_not_configured"],
        }

    def delete(self, brain, uid):
        self.authorize(brain, review=True)
        with self.db:
            self.db.execute(
                "UPDATE records SET text='',sources='[]',vector='[]',state='deleted' "
                "WHERE tenant=? AND brain=? AND uid=?",
                (self.identity.tenant, brain, uid),
            )
            self._index(brain, uid, "")
            self.db.execute(
                "UPDATE events SET detail='' WHERE tenant=? AND brain=? AND uid=?",
                (self.identity.tenant, brain, uid),
            )
            self._event(brain, uid, "delete")

    def review(self, brain, uid, action, expected, reason):
        self.authorize(brain, review=True)
        if action not in {"accept", "reject", "expire", "rollback"} or not reason.strip():
            raise ValueError("Review action and reason required")
        row = self.db.execute(
            "SELECT * FROM records WHERE tenant=? AND brain=? AND uid=?",
            (self.identity.tenant, brain, uid),
        ).fetchone()
        if not row or row["hash"] != expected or row["state"] == "deleted":
            raise ValueError("Review conflict")
        state = {
            "accept": "accepted",
            "reject": "rejected",
            "expire": "expired",
            "rollback": "proposed",
        }[action]
        # Rollback revokes acceptance; restoring erased/replaced prose requires a new proposal.
        with self.db:
            changed = self.db.execute(
                "UPDATE records SET state=? WHERE tenant=? AND brain=? AND uid=? AND hash=? AND state=?",
                (state, self.identity.tenant, brain, uid, expected, row["state"]),
            )
            if changed.rowcount != 1:
                raise ValueError("Concurrent review conflict; nothing reviewed")
            self._event(
                brain,
                uid,
                action,
                canonical(
                    {
                        "reason": reason,
                        "reviewed_hash": expected,
                        "evidence": json.loads(row["sources"]),
                    }
                ),
            )
        return {"uid": uid, "state": state, "binding": False}

    def health(self):
        return {
            "schema": self.db.execute("PRAGMA user_version").fetchone()[0],
            "integrity": self.db.execute("PRAGMA quick_check").fetchone()[0],
            "vector_model": self.embedder.identity if self.embedder else None,
        }

    def backup(self, target):
        target = Path(target)
        if target.exists() or target.is_symlink():
            raise ValueError("Backup target must not exist")
        with target.open("xb"):
            pass
        target.chmod(0o600)
        with sqlite3.connect(target) as backup:
            self.db.backup(backup)


class LocalEncoder:
    """Pinned local artifacts only. No implicit download or remote code execution."""

    def __init__(self, directory):
        from sentence_transformers import SentenceTransformer

        directory = Path(directory)
        manifest = json.loads((directory / "brain-model.json").read_text())
        if manifest.get("model") != "sentence-transformers/all-MiniLM-L6-v2":
            raise ValueError("Unsupported model manifest")
        actual = {
            p.relative_to(directory).as_posix()
            for p in directory.rglob("*")
            if p.is_file() and p.name != "brain-model.json"
        }
        if actual != set(manifest["files"]) or not actual:
            raise ValueError("Model manifest must cover every local artifact")
        for relative, expected in manifest["files"].items():
            raw_path = directory / relative
            path = raw_path.resolve()
            if not path.is_relative_to(directory.resolve()) or any(
                p.is_symlink() for p in (raw_path, *raw_path.parents)
            ):
                raise ValueError("Unsafe model file")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Local model artifact changed")
        self.identity = manifest["model"] + "@" + digest(canonical(manifest["files"]))
        self.model = SentenceTransformer(
            str(directory), local_files_only=True, trust_remote_code=False, device="cpu"
        )

    def encode(self, text):
        tokens = self.model.tokenizer.encode(text, add_special_tokens=False)
        chunks = [
            self.model.tokenizer.decode(tokens[start : start + 224])
            for start in range(0, len(tokens), 192)
        ] or [text]
        encoded = self.model.encode(chunks, normalize_embeddings=True).tolist()
        vector = [sum(row[i] for row in encoded) / len(encoded) for i in range(384)]
        norm = math.sqrt(sum(x * x for x in vector))
        if not norm or not math.isfinite(norm):
            raise ValueError("Embedding has no finite direction")
        vector = [x / norm for x in vector] if norm else vector
        if len(vector) != 384 or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid embedding output")
        return vector
