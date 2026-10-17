"""Paired retrieval benchmark on a new, empty, synthetic FalkorDB endpoint only."""

import argparse
import hashlib
import json
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from brain.config import Config
from brain.graph import GraphStore
from brain.ingest.sync import sync
from brain.memory import Identity, LocalEncoder, Memory, digest
from brain.memory_tools import MemoryTools
from brain.services import Services

ROOT = Path(__file__).resolve().parents[1]


def evaluate(port, model_dir, output, repeats=5):
    corpus = json.loads((ROOT / "benchmarks/memory-retrieval.json").read_text())
    encoder = LocalEncoder(model_dir)
    with tempfile.TemporaryDirectory(prefix="brain-benchmark-") as directory:
        root = Path(directory)
        checkout = root / "repo"
        checkout.mkdir()
        (checkout / "app.py").write_text("def caller(): return target()\ndef target(): return 1\n")
        subprocess.run(["git", "init", str(checkout)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(checkout), "add", "."], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(checkout),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-m",
                "Synthetic retrieval fixture",
            ],
            check=True,
            capture_output=True,
        )
        cfg = Config(
            checkout, "benchmark:memory", repo_url="https://github.com/example/fixture", port=port
        )
        store = GraphStore(cfg)
        from falkordb import FalkorDB

        if FalkorDB(port=port).list_graphs():
            raise ValueError("Benchmark requires a dedicated empty database")
        sync(store)
        memory = Memory(root / "memory.db", Identity("benchmark", "reader"), encoder)
        try:
            with memory.db:
                memory.db.execute(
                    "INSERT INTO grants VALUES('benchmark','reader','company','reviewer')"
                )
                for document in corpus["documents"]:
                    uid = document["id"]
                    uri = "urn:benchmark:document:" + uid
                    sources = [{"uri": uri, "digest": digest(document["text"])}]
                    memory.put("company", document["text"], sources, uid=uid, accepted=True)
                    store.upsert(
                        "Document", uid, {"repo_id": cfg.repo_id, "text": document["text"]}
                    )
                    store.upsert(
                        "Source",
                        uid + ":source",
                        {"repo_id": cfg.repo_id, "uri": uri, "excerpt": document["text"]},
                    )
                    store.edge(uid, "SUPPORTS", uid + ":source")
            services = Services(store)
            tools = MemoryTools(memory, services)
            modes = {
                "no_retrieval": lambda q: {"items": []},
                "graph_only": lambda q: services.get_context(q),
                "exact_fulltext": lambda q: memory.search(q, ["company"], mode="fulltext", limit=3),
                "hybrid": lambda q: tools.memory_search(
                    q, ["company"], include_graph=True, limit=3
                ),
            }
            report = {
                "corpus": "synthetic",
                "queries": len(corpus["queries"]),
                "repeats": repeats,
                "model": encoder.identity,
                "model_revision": json.loads((Path(model_dir) / "brain-model.json").read_text())[
                    "revision"
                ],
                "corpus_sha256": hashlib.sha256(
                    (ROOT / "benchmarks/memory-retrieval.json").read_bytes()
                ).hexdigest(),
                "metrics": {},
                "details": [],
                "limits": [
                    "Small authored corpus, not independent production relevance judgments",
                    "No coding-agent improvement inferred from retrieval results",
                    "Latency excludes model loading and indexing",
                ],
            }
            # Warm model/tokenizer before timed query measurements.
            encoder.encode("warm retrieval")
            originals = {
                "urn:benchmark:document:" + d["id"]: d["text"] for d in corpus["documents"]
            }
            for name, search in modes.items():
                hits, reciprocal, grounded, total, latencies = 0, 0.0, 0, 0, []
                verified = 0
                for case in corpus["queries"]:
                    result = None
                    for _ in range(repeats):
                        start = time.perf_counter()
                        result = search(case["query"])
                        latencies.append((time.perf_counter() - start) * 1000)
                    if name == "graph_only":
                        sources = result.get("untrusted_source_excerpts", [])[:3]
                        found = [s["uri"].rsplit(":", 1)[-1] for s in sources if s.get("uri")]
                        grounded += sum(bool(s.get("uri") and s.get("source_uid")) for s in sources)
                        total += len(sources)
                        verified += sum(
                            source.get("text") == originals.get(source.get("uri"))
                            for source in sources
                        )
                    else:
                        found = []
                        for item in result["items"]:
                            source_uris = [s["uri"] for s in item.get("sources", [])] or [
                                item.get("uri", "")
                            ]
                            found.extend(uri.rsplit(":", 1)[-1] for uri in source_uris if uri)
                            grounded += bool(source_uris and all(source_uris))
                            valid = bool(source_uris) and all(
                                uri in originals for uri in source_uris
                            )
                            valid = valid and any(
                                item.get("text") == originals[uri] for uri in source_uris
                            )
                            valid = valid and all(
                                s["digest"] == digest(originals[s["uri"]])
                                for s in item.get("sources", [])
                            )
                            verified += valid
                            total += 1
                    positions = [found.index(uid) + 1 for uid in case["relevant"] if uid in found]
                    hits += bool(positions)
                    reciprocal += 1 / min(positions) if positions else 0
                    report["details"].append(
                        {
                            "mode": name,
                            "query": case["query"],
                            "retrieved": found,
                            "hit": bool(positions),
                        }
                    )
                ordered = sorted(latencies)
                report["metrics"][name] = {
                    "hit_at_3": hits / len(corpus["queries"]),
                    "mrr_at_3": reciprocal / len(corpus["queries"]),
                    "citation_coverage": grounded / total if total else None,
                    "returned_source_integrity": verified / total if total else None,
                    "returned_items_checked": total,
                    "latency_ms_p50": statistics.median(ordered),
                    "latency_ms_p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
                }
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report["metrics"], indent=2))
        finally:
            memory.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.port, args.model_dir, args.output)
