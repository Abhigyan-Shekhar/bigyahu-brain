"""Compare native memory retrieval with catalog retrieval on disposable graphs."""

import argparse
import hashlib
import json
import statistics
import tempfile
import time
import uuid
from pathlib import Path

from validate_memory_foundation import ROOT, engine

from brain.config import Config
from brain.graph import GraphStore
from brain.memory import Identity, LocalEncoder, Memory, digest
from brain.memory_graph import MemoryGraph
from brain.memory_links import MemoryLinks
from brain.memory_tools import MemoryTools
from brain.services import Services


def accepted(memory, uid, text):
    sources = [{"uri": "urn:synthetic:falkor-benchmark:" + uid, "digest": digest(text)}]
    with memory.db:
        record = memory.put("private:fixture", text, sources, uid=uid)
    memory.review("private:fixture", uid, "accept", record["hash"], "Synthetic fixture only")
    return record, sources


def evaluate(memory, projection, cases):
    tools = MemoryTools(memory, Services(projection.store), projection)
    modes = {
        "catalog_exact_fulltext": lambda q: memory.search(q, mode="exact_fulltext", limit=3),
        "falkor_exact_fulltext_graph": lambda q: tools.memory_search(q, limit=3, backend="falkor"),
    }
    if memory.embedder:
        modes["catalog_hybrid_vectors"] = lambda q: memory.search(q, limit=3)
    result = {}
    for mode, search in modes.items():
        details, latencies = [], []
        hits, rr, recall = [], [], []
        for case in cases:
            start = time.perf_counter()
            response = search(case["query"])
            latencies.append((time.perf_counter() - start) * 1000)
            if response.get("status", "ok") != "ok":
                raise RuntimeError(
                    "Benchmark retrieval was incomplete: " + json.dumps(response["warnings"])
                )
            found = [item["uid"] for item in response["items"]]
            relevant = set(case["relevant"])
            hits.append(bool(relevant & set(found)))
            recall.append(len(relevant & set(found)) / len(relevant))
            rr.append(next((1 / rank for rank, uid in enumerate(found, 1) if uid in relevant), 0))
            details.append(
                {
                    **case,
                    "retrieved": found,
                    "relationships": [
                        [p["relationships"] for p in item.get("graph_paths", [])]
                        for item in response["items"]
                    ],
                }
            )
        result[mode] = {
            "hit_at_3": statistics.mean(hits),
            "recall_at_3": statistics.mean(recall),
            "mrr_at_3": statistics.mean(rr),
            "latency_ms_p50": statistics.median(latencies),
            "details": details,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    raw = (ROOT / "benchmarks/memory-retrieval.json").read_bytes()
    corpus = json.loads(raw)
    runtime = ROOT / "data/validation"
    runtime.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="falkor-memory-", dir=runtime))
    encoder = LocalEncoder(args.model_dir.resolve()) if args.model_dir else None
    with engine(folder / "engine") as port:
        cfg = Config(
            folder,
            "fixture:native-retrieval",
            principal="fixture",
            tenant_id="fixture_" + uuid.uuid4().hex,
            port=port,
            memory_db=str(folder / "memory.db"),
            memory_graph_enabled=True,
        )
        memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, cfg.principal), encoder)
        store = GraphStore(cfg)
        projection = MemoryGraph(memory, store)
        try:
            for doc in corpus["documents"]:
                accepted(memory, doc["id"], doc["text"])
            projection.sync("private:fixture")
            report = {
                "format": "falkor-memory-evaluation/1",
                "corpus": "synthetic",
                "corpus_sha256": hashlib.sha256(raw).hexdigest(),
                "embedding_model": encoder.identity if encoder else None,
                "implementation_sha256": {
                    path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in (
                        "scripts/benchmark_falkor_memory.py",
                        "src/brain/memory.py",
                        "src/brain/memory_search.py",
                        "src/brain/memory_walk.py",
                        "src/brain/memory_graph.py",
                        "src/brain/memory_tools.py",
                        "src/brain/memory_links.py",
                    )
                },
                "natural_language": {
                    "queries": len(corpus["queries"]),
                    "results": evaluate(memory, projection, corpus["queries"]),
                },
            }
            graph_records = [
                ("incident", "Incident amber beacon: uploads need diagnosis."),
                ("correction", "Use a fresh request buffer."),
                ("detail", "Retain a failed seek diagnostic."),
                ("entity-seed", "Quasar policy for `replay_buffer`."),
                ("entity-detail", "Always retain byte boundaries in `replay_buffer`."),
            ]
            records = {uid: accepted(memory, uid, text) for uid, text in graph_records}
            links = MemoryLinks(memory)
            for a, relation, b in (
                ("correction", "UPDATES", "incident"),
                ("detail", "EXTENDS", "correction"),
            ):
                item = links.propose(
                    "private:fixture",
                    a,
                    records[a][0]["hash"],
                    relation,
                    b,
                    records[b][0]["hash"],
                    records[a][1],
                )
                links.review(
                    "private:fixture", item["uid"], "accept", "proposed", "Synthetic fixture only"
                )
            projection.sync("private:fixture")
            graph_cases = [
                {"query": "amber beacon", "relevant": ["correction", "detail"]},
                {"query": "correction", "relevant": ["detail"]},
                {"query": "Quasar", "relevant": ["entity-detail"]},
            ]
            report["graph_acceptance"] = {
                "queries": len(graph_cases),
                "results": evaluate(memory, projection, graph_cases),
            }
            report["limits"] = [
                "Small authored synthetic corpus; no production relevance or coding advantage claim",
                "Graph acceptance questions deliberately require authored reviewed links or shared identifiers",
                "Natural-language group evaluated before graph fixtures are added",
                "Single query timing includes authorized graph validation; model loading/indexing excluded",
                "Falkor mode uses no embeddings; optional vector baseline remains catalog-based",
            ]
        finally:
            memory.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                group: {
                    name: {k: v for k, v in metrics.items() if k != "details"}
                    for name, metrics in report[group]["results"].items()
                }
                for group in ("natural_language", "graph_acceptance")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
