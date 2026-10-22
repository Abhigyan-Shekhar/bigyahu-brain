"""Source provenance checks and native graph paths, independent of model prose."""

import hashlib
import io
import json
import re
import tokenize
from pathlib import Path
from urllib.parse import quote, urlsplit

from ..ingest.git_parser import clean, revision
from ..memory import canonical, digest
from .findings import validate_finding


def native_graph(store, uids):
    params = {"repo": store.cfg.repo_id, "ids": uids}
    nodes = store.query(
        "MATCH (n {repo_id:$repo}) WHERE n.uid IN $ids "
        "RETURN n.uid AS id, labels(n) AS labels, coalesce(n.qualname,n.title,n.path,n.name,n.uid) AS label ORDER BY id",
        params,
    )
    edges = store.query(
        "MATCH (a {repo_id:$repo})-[r]->(b {repo_id:$repo}) "
        "WHERE a.uid IN $ids AND b.uid IN $ids "
        "RETURN a.uid AS source,b.uid AS target,type(r) AS edge_type,coalesce(r.relation,type(r)) AS relation, "
        "r.quote AS quote,r.confidence AS confidence,r.source_uid AS source_uid "
        "ORDER BY source,relation,target,edge_type,quote,confidence,source_uid LIMIT 301",
        params,
    )
    return canonical_graph({"nodes": nodes, "edges": edges})


def canonical_graph(graph):
    """Stable topology and metadata, including legacy edges without edge_type."""
    edges = []
    for original in graph["edges"]:
        edge = {k: v for k, v in original.items() if v is not None}
        edge.setdefault("edge_type", edge["relation"])
        edges.append(edge)
    return {
        "nodes": sorted(graph["nodes"], key=lambda n: n["id"]),
        "edges": sorted(edges, key=canonical),
    }


def ready(store):
    state = store.revision()
    if (
        not state["sha"]
        or state["syncing"]
        or revision(store.cfg.repo_root) != state["sha"]
        or not clean(store.cfg.repo_root)
    ):
        raise ValueError("Evidence unavailable: checkout/index is stale or incomplete")
    return state["sha"]


def code_evidence(store, path, start=1, end=80):
    sha = ready(store)
    path = store.cfg.path(path)
    if (
        type(start) is not int
        or type(end) is not int
        or not 1 <= start <= end
        or end - start >= 120
    ):
        raise ValueError("Select 1–120 source lines")
    rows = store.query(
        "MATCH (p:Project {uid:$repo})-[:CONTAINS]->(f:File {repo_id:$repo,current:true,revision:$sha,path:$path}) "
        "RETURN f.uid AS uid,f.digest AS digest",
        {"repo": store.cfg.repo_id, "sha": sha, "path": path},
    )
    if len(rows) != 1:
        raise ValueError("File is not in the current graph")
    file = store.cfg.repo_root / path
    if file.is_symlink() or file.stat().st_size > 1_000_000:
        raise ValueError("Unsupported source file")
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rows[0]["digest"]:
        raise ValueError("Source bytes differ from indexed bytes")
    encoding = (
        tokenize.detect_encoding(io.BytesIO(raw).readline)[0] if path.endswith(".py") else "utf-8"
    )
    lines = raw.decode(encoding).splitlines(keepends=True)
    if start > len(lines):
        raise ValueError("Source line is out of range")
    end = min(end, len(lines))
    text = "".join(lines[start - 1 : end])
    if len(text) > 12000 or not text:
        raise ValueError("Source excerpt exceeds bound")
    return {
        "kind": "code",
        "ref": {"path": path, "start": start, "end": end},
        "title": f"{path}:{start}–{end}",
        "text": text,
        "digest": digest(text),
        "revision": sha,
        "uri": f"{store.cfg.repo_url}/blob/{sha}/{quote(path, safe='/')}#L{start}-L{end}",
        "graph": native_graph(store, [store.cfg.repo_id, rows[0]["uid"]]),
        "verification": "source_bytes_and_native_graph",
        "binding": False,
    }


def repository_files_evidence(store, query=""):
    """Citable bounded path inventory, without implying content-search coverage."""
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError("Use a literal path substring of at most 100 characters")
    sha = ready(store)
    rows = store.query(
        "MATCH (p:Project {uid:$repo})-[:CONTAINS]->"
        "(f:File {repo_id:$repo,current:true,revision:$sha}) "
        "WHERE toLower(f.path) CONTAINS toLower($q) "
        "RETURN f.path AS path ORDER BY path LIMIT 201",
        {"repo": store.cfg.repo_id, "sha": sha, "q": query},
    )
    paths, size = [], 0
    for row in rows[:200]:
        cost = len(canonical(row["path"]).encode("utf-8")) + 1
        if size + cost > 10000:
            break
        paths.append(row["path"])
        size += cost
    text = canonical(
        {
            "path_substring": query,
            "paths": paths,
            "truncated": len(rows) > len(paths),
            "coverage": "Current indexed file paths only; not a search of file contents or proof that no convention exists.",
        }
    )
    return {
        "kind": "repository_files",
        "ref": {"query": query},
        "title": "Repository file inventory: " + (query or "all paths"),
        "text": text,
        "digest": digest(text),
        "revision": sha,
        "graph": native_graph(store, [store.cfg.repo_id]),
        "verification": "current_native_file_inventory",
        "binding": False,
    }


def source_evidence(store, source_uid):
    ready(store)
    rows = store.query(
        "MATCH (p {repo_id:$repo})-[:SUPPORTS|SUPPORTED_BY]->(s:Source {uid:$uid,repo_id:$repo}) "
        "WHERE NOT p:Document OR coalesce(p.current,true) "
        "RETURN DISTINCT p.uid AS parent,s.uri AS uri,s.excerpt AS text,s.digest AS digest, "
        "s.path AS path,s.line_start AS start,s.line_end AS end,s.source_kind AS kind, "
        "s.upload_digest AS upload_digest,s.snapshot_digest AS snapshot_digest,s.text_digest AS text_digest,s.revision AS revision LIMIT 11",
        {"repo": store.cfg.repo_id, "uid": source_uid},
    )
    if not rows or len(rows) > 10:
        raise ValueError("No unambiguous current source relationship")
    row = rows[0]
    text = row["text"] or ""
    if not text or len(text) > 12000 or (row["digest"] and digest(text) != row["digest"]):
        raise ValueError("Source evidence missing, changed or exceeds bounds")
    if row["kind"] in {"repository_document", "graphify_structural"}:
        proof = code_evidence(store, row["path"], row["start"], row["end"])
        if proof["text"] != text:
            raise ValueError("Document source differs from current file bytes")
    elif row["kind"] in {"app_upload", "agent_generated_document"}:
        upload = row["upload_digest"]
        if not isinstance(upload, str) or not re.fullmatch("[a-f0-9]{64}", upload):
            raise ValueError("Invalid upload identity")
        raw = (store.cfg.repo_root.parent / "uploads" / upload).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != upload
            or "".join(raw.decode("utf-8").splitlines(keepends=True)[row["start"] - 1 : row["end"]])
            != text
        ):
            raise ValueError("Uploaded source bytes changed")
    elif row["kind"] == "app_binary_upload":
        upload, snapshot_id = row["upload_digest"], row["snapshot_digest"]
        if not all(
            isinstance(v, str) and re.fullmatch("[a-f0-9]{64}", v) for v in (upload, snapshot_id)
        ):
            raise ValueError("Invalid extracted document identity")
        folder = store.cfg.repo_root.parent / "uploads"
        raw, saved = (
            (folder / upload).read_bytes(),
            (folder / snapshot_id).read_text(encoding="utf-8"),
        )
        if hashlib.sha256(raw).hexdigest() != upload or digest(saved) != snapshot_id:
            raise ValueError("Original document or extraction snapshot changed")
        snapshot = json.loads(saved)
        extracted = snapshot["text"]
        if (
            snapshot["raw_digest"] != upload
            or digest(extracted) != row["text_digest"]
            or "".join(extracted.splitlines(keepends=True)[row["start"] - 1 : row["end"]]) != text
        ):
            raise ValueError("Extracted document text differs from saved evidence")
    else:
        # Historical GitHub sources are immutable recorded snapshots, not proof of current web content.
        url = urlsplit(row["uri"] or "")
        if (
            url.scheme != "https"
            or url.netloc != "github.com"
            or not (row["uri"] or "").startswith(store.cfg.repo_url + "/")
        ):
            raise ValueError("Unsupported source provenance")
    ids = [source_uid, *[r["parent"] for r in rows]]
    return {
        "kind": "source",
        "source_kind": row["kind"],
        "ref": {"source_uid": source_uid},
        "title": row["path"] or row["uri"],
        "text": text,
        "digest": digest(text),
        "uri": row["uri"],
        "revision": row["revision"],
        "graph": native_graph(store, ids),
        "verification": "original_file_digest_and_extraction_snapshot"
        if row["kind"] == "app_binary_upload"
        else "source_bytes_and_native_graph"
        if row["kind"]
        in {"repository_document", "graphify_structural", "app_upload", "app_binary_upload"}
        else "recorded_snapshot_and_native_graph",
        "binding": False,
    }


def resolve(store, evidence):
    if evidence["kind"] == "repository_files":
        return repository_files_evidence(store, **evidence["ref"])
    if evidence["kind"] == "team_memory":
        from .team import memory_evidence

        return memory_evidence(store.cfg, **evidence["ref"])
    if evidence["kind"] == "memory":
        from .personal import memory_evidence

        return memory_evidence(store.cfg, **evidence["ref"])
    if evidence["kind"] == "memory_path":
        from .memory_paths import path_evidence

        return path_evidence(store.cfg, **evidence["ref"])
    if evidence["kind"] == "history_diff":
        from .history import patch_evidence

        return patch_evidence(store, **evidence["ref"])
    if evidence["kind"] == "code":
        return code_evidence(store, **evidence["ref"])
    return source_evidence(store, **evidence["ref"])


def register(folder, evidence):
    uid = digest(
        canonical([evidence["kind"], evidence["ref"], evidence["digest"], evidence["revision"]])
    )[:24]
    if folder is not None:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (uid + ".json")).write_text(canonical({"id": uid, **evidence}), encoding="utf-8")
    return {"id": uid, **evidence}


def verified_claims(store, folder, output):
    """Reject invented IDs/quotes and changed evidence. Does not prove semantic entailment."""
    claims = []
    # Reuse only within this verification pass. Later review/approval passes
    # must resolve again to detect revocation and source changes.
    resolved = {}
    for claim in output.get("claims", [])[:20]:
        if not isinstance(claim.get("text"), str) or not 1 <= len(claim["text"]) <= 3000:
            raise ValueError("Invalid answer claim")
        supporting = []
        for support in claim.get("support", [])[:8]:
            uid, quoted = support.get("evidence_id", ""), support.get("quote", "")
            if not re.fullmatch("[a-f0-9]{24}", uid):
                raise ValueError("Unknown evidence ID")
            if uid not in resolved:
                saved = json.loads((Path(folder) / (uid + ".json")).read_text(encoding="utf-8"))
                resolved[uid] = saved, resolve(store, saved)
            saved, current = resolved[uid]
            if (
                current["digest"] != saved["digest"]
                or canonical(canonical_graph(current["graph"]))
                != canonical(canonical_graph(saved["graph"]))
                or not isinstance(quoted, str)
                or not quoted.strip()
                or quoted not in current["text"]
            ):
                raise ValueError("Evidence changed or quotation unsupported")
            supporting.append(
                {
                    "evidence_id": uid,
                    "quote": quoted,
                    "title": current["title"],
                    "kind": current["kind"],
                    "source_kind": current.get("source_kind"),
                    "brain": current.get("ref", {}).get("brain"),
                    "nodes": current["graph"]["nodes"],
                }
            )
        if not supporting:
            raise ValueError("Repository claims require checked source support")
        checked = {"text": claim["text"], "support": supporting}
        if claim.get("finding") is not None:
            checked["finding"] = validate_finding(
                claim["finding"], [resolved[s["evidence_id"]][1] for s in supporting]
            )
        claims.append(checked)
    return claims


def reuse_evidence(store, source_folder, destination, claims, *, max_items=8, max_bytes=40000):
    """Mint current run evidence only after rechecking bytes, graph and access."""
    reused, seen, size = [], set(), 0
    for claim in claims[:20]:
        for support in claim.get("support", [])[:8]:
            uid = support.get("evidence_id", "")
            if not isinstance(uid, str) or not re.fullmatch("[a-f0-9]{24}", uid) or uid in seen:
                continue
            seen.add(uid)
            if len(reused) >= max_items:
                return reused
            try:
                path = Path(source_folder) / (uid + ".json")
                if path.stat().st_size > 150000:
                    continue
                saved = json.loads(path.read_text(encoding="utf-8"))
                current = resolve(store, saved)
                if (
                    current["digest"] != saved["digest"]
                    or current["revision"] != saved["revision"]
                    or canonical(canonical_graph(current["graph"]))
                    != canonical(canonical_graph(saved["graph"]))
                ):
                    continue
                encoded = canonical(current).encode("utf-8")
                if size + len(encoded) > max_bytes:
                    continue
                item = register(destination, current)
                reused.append(item)
                size += len(encoded)
            except (OSError, ValueError, KeyError, PermissionError):
                # Unavailable/changed/revoked sources are never copied or exposed.
                continue
    return reused
