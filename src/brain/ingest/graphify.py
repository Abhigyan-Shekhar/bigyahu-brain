"""Opt-in Graphify structural evidence, separate from authoritative Python calls."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from ..memory import canonical, digest
from .git_parser import clean, git, revision
from .graphify_worker import PIN

SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".h", ".cpp"}


def normalize(result, texts, repo, sha, url):
    """Validate the complete extractor output before the first database mutation."""
    if not isinstance(result, dict) or result.get("failed_sources"):
        raise ValueError("Graphify extraction failed; existing graph unchanged")
    nodes, edges = result.get("nodes"), result.get("edges")
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or len(nodes) > 10000
        or len(edges) > 20000
    ):
        raise ValueError("Graphify output bound exceeded")
    line_map = {path: text.splitlines(keepends=True) for path, text in texts.items()}
    prepared, sources, ids, originals = [], {}, {}, {}

    def provenance(path, location):
        if not isinstance(path, str) or path not in line_map or not isinstance(location, str):
            raise ValueError("Invalid Graphify source path")
        match = re.fullmatch(r"L([1-9][0-9]*)(?:-L?([1-9][0-9]*))?", location)
        if not match:
            raise ValueError("Invalid Graphify source location")
        start, end = int(match[1]), int(match[2] or match[1])
        lines = line_map[path]
        if not 1 <= start <= end <= len(lines) or end - start > 100:
            raise ValueError("Graphify source range exceeds bounds")
        text = "".join(lines[start - 1 : end])
        if not text or len(text) > 12000:
            raise ValueError("Graphify source excerpt exceeds bounds")
        source = f"{repo}@{sha}:graphify-source:{digest(canonical([path, start, end]))}"
        props = {
            "repo_id": repo,
            "revision": sha,
            "current": True,
            "source_kind": "graphify_structural",
            "extractor": "graphifyy/" + PIN,
            "path": path,
            "line_start": start,
            "line_end": end,
            "digest": digest(text),
            "text": text,
        }
        sources[source] = {
            **props,
            "excerpt": text,
            "uri": f"{url}/blob/{sha}/{path}#L{start}-L{end}",
        }
        return source, props

    for node in nodes:
        if not isinstance(node, dict):
            raise TypeError("Invalid Graphify node")
        key, label = node.get("id"), node.get("label")
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 1000
            or key in ids
            or not isinstance(label, str)
            or not 1 <= len(label) <= 1000
        ):
            raise ValueError("Invalid Graphify node identity")
        source, props = provenance(node.get("source_file"), node.get("source_location"))
        uid = f"{repo}@{sha}:graphify:{digest(key)}"
        prepared.append((uid, source, {**props, "title": label, "external_id": key}))
        ids[key], originals[key] = uid, node
    relationships = []
    for edge in edges:
        if not isinstance(edge, dict):
            raise TypeError("Invalid Graphify relationship")
        a, b, relation, confidence = (
            edge.get(k) for k in ("source", "target", "relation", "confidence")
        )
        if (
            not isinstance(a, str)
            or not isinstance(b, str)
            or a not in ids
            or b not in ids
            or not isinstance(relation, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", relation)
            or not isinstance(confidence, str)
            or confidence not in {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
        ):
            raise ValueError("Invalid Graphify relationship")
        origin = originals[a]
        source, _props = provenance(
            edge.get("source_file", origin["source_file"]),
            edge.get("source_location", origin["source_location"]),
        )
        basis = (
            "graphify_reported_location"
            if edge.get("source_location")
            else "graphify_origin_node_context"
        )
        relationships.append((ids[a], ids[b], relation, confidence, source, basis))
    return prepared, sources, sorted(set(relationships))


def ingest_graphify(store, paths=None):
    cfg = store.cfg
    state = store.revision(code_only=True)
    sha = revision(cfg.repo_root)
    if not clean(cfg.repo_root) or state != {"sha": sha, "syncing": False} or not cfg.repo_url:
        raise ValueError("Graphify requires a clean checkout, repository URL and current code sync")
    tracked = set(filter(None, git(cfg.repo_root, "ls-files", "-z").split("\0")))
    paths = sorted(
        set(paths if paths is not None else [p for p in tracked if Path(p).suffix in SUFFIXES])
    )
    if not 1 <= len(paths) <= 500:
        raise ValueError("Select one to 500 tracked code files")
    texts, total = {}, 0
    for path in paths:
        cfg.path(path)
        file = cfg.repo_root / path
        if path not in tracked or file.is_symlink() or file.suffix not in SUFFIXES:
            raise ValueError("Graphify only accepts selected tracked regular code files")
        raw = file.read_bytes()
        total += len(raw)
        if len(raw) > 1_000_000 or total > 10_000_000 or b"\0" in raw:
            raise ValueError("Graphify input bound exceeded")
        try:
            texts[path] = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(
                "Graphify requires UTF-8 source files; declared alternative Python encodings "
                "are not supported. Existing graph unchanged"
            ) from None
    with tempfile.TemporaryDirectory(prefix="brain-graphify-") as temp:
        root = Path(temp) / "input"
        root.mkdir()
        for path, text in texts.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        manifest, output = Path(temp) / "files.json", Path(temp) / "result.json"
        manifest.write_text(canonical(paths))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "brain.ingest.graphify_worker",
                str(root),
                str(Path(temp) / "cache"),
                str(output),
                str(manifest),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode or not output.exists() or output.stat().st_size > 20_000_000:
            raise ValueError(
                "Graphify failed; install the pinned graphify extra and check supported inputs"
            )
        nodes, sources, edges = normalize(
            json.loads(output.read_text()), texts, cfg.repo_id, sha, cfg.repo_url
        )
    if (
        not clean(cfg.repo_root)
        or revision(cfg.repo_root) != sha
        or store.revision(code_only=True) != state
    ):
        raise ValueError("Checkout changed during extraction; existing graph unchanged")
    params = {"repo": cfg.repo_id, "paths": paths}
    store.query("MATCH (p:Project {uid:$repo}) SET p.graphify_syncing=true", params)
    store.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'graphify_structural'}) "
        "WHERE d.path IN $paths SET d.current=false",
        params,
    )
    store.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'graphify_structural'})"
        "-[r:EXTRACTED_RELATION]->() WHERE d.path IN $paths DELETE r",
        params,
    )
    for source, props in sources.items():
        store.upsert("Source", source, props)
    for uid, source, props in nodes:
        store.upsert("Document", uid, props)
        store.edge(uid, "SUPPORTS", source)
    for a, b, relation, confidence, source, basis in edges:
        # Fixed relationship type; upstream prose never becomes executable Cypher.
        store.query(
            "MATCH (a:Document {uid:$a}), (b:Document {uid:$b}) "
            "MERGE (a)-[r:EXTRACTED_RELATION {relation:$relation}]->(b) "
            "SET r.confidence=$confidence, r.binding=false, r.basis=$basis, r.source_uid=$source, r.revision=$sha",
            {
                "a": a,
                "b": b,
                "relation": relation,
                "confidence": confidence,
                "source": source,
                "basis": basis,
                "sha": sha,
            },
        )
    if (
        not clean(cfg.repo_root)
        or revision(cfg.repo_root) != sha
        or store.revision(code_only=True) != state
    ):
        raise ValueError("Checkout changed; Graphify remains fenced until retry")
    store.query("MATCH (p:Project {uid:$repo}) SET p.graphify_syncing=false", params)
    return {
        "extractor": "graphifyy/" + PIN,
        "revision": sha,
        "files": len(paths),
        "nodes": len(nodes),
        "relationships": len(edges),
        "binding": False,
        "semantic_extraction": False,
    }
