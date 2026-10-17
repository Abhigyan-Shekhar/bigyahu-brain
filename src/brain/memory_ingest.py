"""Transactional .abhi, document and consented session imports."""

import json
import re
from collections import Counter
from pathlib import Path

from .ingest.documents import sections
from .memory import canonical, citations, digest


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("Expected a regular import of at most 1 MB")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def import_abhi(memory, payload):
    required = {"format", "tenant", "team", "collection", "parent_digest", "records"}
    if not isinstance(payload, dict) or set(payload) != required or payload["format"] != "abhi/1":
        raise ValueError("Invalid .abhi envelope")
    if payload["tenant"] != memory.identity.tenant:
        raise PermissionError("Import tenant unavailable")
    team, collection = payload["team"], payload["collection"]
    if not isinstance(team, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", team):
        raise ValueError("Invalid team")
    if not isinstance(collection, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", collection):
        raise ValueError("Invalid collection")
    brain = "team:" + team
    memory.authorize(brain, write=True)
    records = payload["records"]
    if not isinstance(records, list) or len(records) > 512:
        raise ValueError("Import record bound exceeded")
    fingerprint = digest(canonical(payload))
    keys = (memory.identity.tenant, brain, collection)
    memory.db.execute("BEGIN IMMEDIATE")
    try:
        prior = memory.db.execute(
            "SELECT hash FROM imports WHERE tenant=? AND brain=? AND collection=?", keys
        ).fetchone()
        if prior and prior[0] == fingerprint:
            memory.db.rollback()
            return {"digest": fingerprint, "unchanged": True}
        if payload["parent_digest"] != (prior[0] if prior else ""):
            raise ValueError("Collection conflict; merge against the current digest")
        seen = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {
                "id",
                "text",
                "sources",
                "expected_hash",
                "expires",
            }:
                raise ValueError("Invalid .abhi record; ACL and approval fields are forbidden")
            uid = "abhi:" + collection + ":" + record["id"]
            if uid in seen:
                raise ValueError("Duplicate .abhi record")
            seen.add(uid)
            memory.put(
                brain,
                record["text"],
                record["sources"],
                uid,
                record["expected_hash"],
                record["expires"],
                collection,
            )
        memory.db.execute("INSERT OR REPLACE INTO imports VALUES(?,?,?,?)", (*keys, fingerprint))
        memory._event(brain, collection, "import", fingerprint)
        memory.db.commit()
    except BaseException:
        memory.db.rollback()
        raise
    return {"digest": fingerprint, "records": len(records), "state": "proposed"}


def document_sections(path, text):
    """Stable logical IDs separate from immutable content/source hashes.

    Heading identity survives preceding line insertions and prose edits. Duplicate
    headings use occurrence ordinals; long sections use bounded chunk ordinals.
    """
    heading, counts, chunk = "preamble", Counter(), 0
    for start, end, body in sections(text):
        lines = body.splitlines()
        first = lines[0].strip()
        title = None
        if re.match(r"^#{1,6}\s+", first):
            title = re.sub(r"^#{1,6}\s+", "", first).strip(" #")
        elif len(lines) > 1 and re.fullmatch(r"[=~^\-`:#*+]{3,}\s*", lines[1]):
            title = first
        if title is not None:
            counts[title] += 1
            heading, chunk = title + ":" + str(counts[title]), 0
        chunk += 1
        yield {
            "id": "doc:" + digest(path + ":" + heading + ":" + str(chunk)),
            "text": body,
            "start": start,
            "end": end,
            "digest": digest(body),
        }


def ingest_local_documents(memory, brain, root, paths, source_base):
    memory.authorize(brain, write=True)
    root = Path(root).resolve()
    if not 1 <= len(paths) <= 100:
        raise ValueError("Expected 1–100 explicitly selected document paths")
    prepared, total = [], 0
    for relative in paths:
        path = root / relative
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or path.suffix not in {".md", ".rst"}
            or any(p.is_symlink() for p in (path, *path.parents))
            or not path.resolve().is_relative_to(root)
            or not path.is_file()
        ):
            raise ValueError("Unsafe Markdown/RST document")
        raw = path.read_bytes()
        total += len(raw)
        if len(raw) > 256000 or total > 1_000_000 or b"\0" in raw:
            raise ValueError("Document byte bound exceeded")
        for section in document_sections(relative, raw.decode("utf-8")):
            section.update(
                collection="document:" + relative,
                sources=[
                    {
                        "uri": source_base.rstrip("/")
                        + "/"
                        + relative
                        + f"#L{section['start']}-L{section['end']}",
                        "digest": section["digest"],
                    }
                ],
            )
            citations(section["sources"])
            prepared.append(section)
    if len(prepared) > 2048:
        raise ValueError("Document section bound exceeded")
    with memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        for relative in paths:
            collection = "document:" + relative
            old = memory.db.execute(
                "SELECT uid,hash FROM records WHERE tenant=? AND brain=? AND collection=?",
                (memory.identity.tenant, brain, collection),
            ).fetchall()
            old = {row["uid"]: row["hash"] for row in old}
            selected = [r for r in prepared if r["collection"] == collection]
            for section in selected:
                memory.put(
                    brain,
                    section["text"],
                    section["sources"],
                    section["id"],
                    old.pop(section["id"], ""),
                    collection=collection,
                    accepted=True,
                )
            # Refresh never retains removed section text or vectors in the search catalog.
            for uid in old:
                memory.db.execute(
                    "DELETE FROM records WHERE tenant=? AND brain=? AND uid=?",
                    (memory.identity.tenant, brain, uid),
                )
                memory._index(brain, uid, "")
                memory._event(brain, uid, "document_section_removed")
    return {"files": len(paths), "sections": len(prepared), "binding": False}


def ingest_session(memory, payload, consent_digest):
    if not isinstance(payload, dict) or set(payload) != {"format", "session", "selected_memories"}:
        raise ValueError("Expected curated session/1 export, never raw agent trace")
    if payload["format"] != "session/1" or digest(canonical(payload)) != consent_digest:
        raise ValueError("Explicit consent must cover this exact curated export")
    if not isinstance(payload["session"], str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,100}", payload["session"]
    ):
        raise ValueError("Invalid session identifier")
    items = payload["selected_memories"]
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError("Session proposal limit exceeded")
    brain = "private:" + memory.identity.principal
    with memory.db:
        memory.db.execute("BEGIN IMMEDIATE")
        result = []
        for number, item in enumerate(items):
            if not isinstance(item, str):
                raise TypeError("Selected memories must be strings")
            result.append(
                memory.put(
                    brain,
                    item,
                    [
                        {
                            "uri": f"urn:codex-session:{payload['session']}:{number}",
                            "digest": digest(item),
                        }
                    ],
                    uid="session:" + payload["session"] + ":" + str(number),
                )
            )
        memory._event(brain, payload["session"], "consent", consent_digest)
    return {"items": result, "brain": brain, "binding": False}
