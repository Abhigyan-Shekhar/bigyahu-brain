"""Explicit semantic ingestion jobs; model output never becomes dynamic Cypher or policy."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from ..graph import GraphStore
from ..memory import canonical, digest
from .evidence import ready, source_evidence


def active_ingestions(state, project):
    return [j for j in state.list("enrichment", project) if j["status"] in {"queued", "running"}]


def validate_output(result, units):
    nodes, edges = result.get("nodes"), result.get("edges")
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or len(nodes) > 200
        or len(edges) > 400
    ):
        raise ValueError("Semantic graph exceeds 200 nodes or 400 relationships")
    ids = set()
    for n in nodes:
        if (
            not isinstance(n, dict)
            or not isinstance(n.get("id"), str)
            or not 1 <= len(n["id"]) <= 1000
            or n["id"] in ids
        ):
            raise ValueError("Invalid semantic entity identity")
        ids.add(n["id"])
        if (
            n.get("unit") not in units
            or not isinstance(n.get("name"), str)
            or not 1 <= len(n["name"]) <= 1000
            or not isinstance(n.get("quote"), str)
            or not n["quote"]
            or n["quote"] not in units[n["unit"]]
            or n["name"] not in n["quote"]
        ):
            raise ValueError("Semantic entity lacks literal source evidence")
    for e in edges:
        if (
            e.get("a") not in ids
            or e.get("b") not in ids
            or not isinstance(e.get("relation"), str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", e["relation"])
            or e.get("confidence", "INFERRED") not in {"INFERRED", "AMBIGUOUS"}
            or e.get("unit") not in units
            or not isinstance(e.get("quote"), str)
            or not e["quote"]
            or e["quote"] not in units[e["unit"]]
        ):
            raise ValueError("Semantic relationship lacks valid endpoints or source span")
    return nodes, edges


def publish(store, result, documents, engine, model, sha):
    units = {f"source{i}.txt": d["text"] for i, d in enumerate(documents)}
    nodes, edges = validate_output(result, units)
    key = digest(canonical([engine, model, [(d["source"], d["digest"]) for d in documents]]))
    prefix = f"{store.cfg.repo_id}@{sha}:semantic:{key}:{digest(canonical(result))}:"
    sources = {f"source{i}.txt": d for i, d in enumerate(documents)}
    prepared = []
    for n in nodes:
        d = sources[n["unit"]]
        prepared.append(
            {
                "uid": prefix + digest(n["id"]),
                "props": {
                    "repo_id": store.cfg.repo_id,
                    "revision": sha,
                    "current": True,
                    "source_kind": "semantic_advisory",
                    "title": n["name"],
                    "text": d["text"],
                    "digest": d["digest"],
                    "engine": engine,
                    "model": model,
                    "binding": False,
                    "semantic_batch": key,
                },
                "source": d["source"],
            }
        )
    relationships = [
        {
            "a": prefix + digest(e["a"]),
            "b": prefix + digest(e["b"]),
            "relation": e["relation"],
            "confidence": e.get("confidence", "INFERRED"),
            "source_uid": sources[e["unit"]]["source"],
            "quote": e["quote"],
        }
        for e in edges
    ]
    # One atomic query after ALL output validation. Source nodes are never overwritten.
    store.query(
        "MATCH (p:Project {uid:$repo}) OPTIONAL MATCH (old:Document {repo_id:$repo,semantic_batch:$key}) SET old.current=false WITH count(old) AS retired "
        "UNWIND $nodes AS item MERGE (d:Document {uid:item.uid}) SET d += item.props,d.path=null "
        "WITH d,item MATCH (s:Source {uid:item.source,repo_id:$repo}) "
        "MERGE (copy:Source {uid:item.uid+':source'}) SET copy += properties(s),copy.uid=item.uid+':source' "
        "MERGE (d)-[:SUPPORTS]->(copy) "
        "WITH count(d) AS written UNWIND $edges AS item "
        "MATCH (a:Document {uid:item.a}), (b:Document {uid:item.b}) "
        "MERGE (a)-[r:EXTRACTED_RELATION {relation:item.relation}]->(b) "
        "SET r.binding=false,r.confidence=item.confidence,r.basis='semantic_source_span',r.source_uid=item.source_uid,r.quote=item.quote,r.revision=$sha",
        {
            "repo": store.cfg.repo_id,
            "sha": sha,
            "key": key,
            "nodes": prepared,
            "edges": relationships,
        },
    )
    return {
        "nodes": len(nodes),
        "relationships": len(edges),
        "engine": result["engine"],
        "pipeline": result["pipeline"],
        "vectors": False,
        "binding": False,
    }


def run_enrichment(state, uid):
    job = state.get(uid, "enrichment")
    if not state.transition(
        uid,
        {"status": "queued"},
        status="running",
        stage="Extracting semantic entities and relationships",
    ):
        return
    try:
        store = GraphStore(state.config(job["project"]))
        sha = ready(store)
        documents = []
        for source in job["sources"]:
            evidence = source_evidence(store, source)
            documents.append({**evidence, "source": source})
        if sum(len(d["text"]) for d in documents) > 40000:
            raise ValueError("Select at most 40000 characters of source text")
        request = {
            "engine": job["engine"],
            "model": state.model,
            "units": {f"source{i}.txt": d["text"] for i, d in enumerate(documents)},
        }
        with tempfile.TemporaryDirectory(prefix="brain-enrichment-") as temp:
            root = Path(temp)
            manifest, output = root / "request.json", root / "result.json"
            manifest.write_text(canonical(request), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "brain.ingest.semantic_worker", str(manifest), str(output)],
                capture_output=True,
                env={**os.environ, "GRAPHIFY_MAX_RETRIES": "0", "GRAPHIFY_API_TIMEOUT": "200"},
                timeout=600,
                check=False,
            )
            if result.returncode or not output.exists() or output.stat().st_size > 1_000_000:
                raise ValueError(
                    "Semantic pipeline failed; check optional ingestion/graphify dependencies and model access. No semantic graph was published."
                )
            extracted = json.loads(output.read_text())
            audit = state.folder(job["project"]) / "enrichments" / uid
            audit.mkdir(parents=True, exist_ok=True)
            (audit / "extraction.json").write_text(canonical(extracted), encoding="utf-8")
            (audit / "manifest.json").write_text(
                canonical(
                    {
                        "engine": job["engine"],
                        "model": state.model,
                        "source_digests": {d["source"]: d["digest"] for d in documents},
                        "extraction_sha256": digest(canonical(extracted)),
                        "implementation_sha256": {
                            str(p.relative_to(Path(__file__).parents[2])): hashlib.sha256(
                                p.read_bytes()
                            ).hexdigest()
                            for p in [
                                Path(__file__),
                                Path(__file__).parents[1] / "ingest/semantic_worker.py",
                                Path(__file__).parents[1] / "semantic_model.py",
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
        if ready(store) != sha or any(
            source_evidence(store, d["source"])["digest"] != d["digest"] for d in documents
        ):
            raise ValueError("Sources changed during semantic extraction")
        result = publish(store, extracted, documents, job["engine"], state.model, sha)
        state.update(uid, status="complete", stage="Semantic graph indexed", result=result)
    except Exception as exc:  # noqa: BLE001 - durable background result
        state.update(
            uid,
            status="failed",
            stage="Semantic extraction stopped",
            error=str(exc)[:500]
            if isinstance(exc, ValueError)
            else "Semantic extraction failed; no semantic graph was published.",
        )
