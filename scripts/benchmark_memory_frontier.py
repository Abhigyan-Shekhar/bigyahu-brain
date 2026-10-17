"""Synthetic connected-memory stress check; not an enterprise-scale benchmark."""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path

from benchmark_falkor_memory import accepted
from validate_memory_foundation import ROOT, engine

from brain.config import Config
from brain.graph import GraphStore
from brain.memory import Identity, Memory
from brain.memory_graph import MemoryGraph
from brain.memory_tools import MemoryTools
from brain.services import Services


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = ROOT / "data/validation"
    runtime.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="frontier-scale-", dir=runtime))
    results = []
    with engine(folder / "engine") as port:
        for size in (10, 50, 100):
            cfg = Config(
                folder,
                "fixture:frontier",
                principal="fixture",
                tenant_id="frontier_" + str(size),
                port=port,
                memory_db=str(folder / f"memory-{size}.db"),
                memory_graph_enabled=True,
            )
            memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, cfg.principal))
            try:
                for i in range(size):
                    accepted(
                        memory,
                        str(i),
                        ("anchor " if i == 0 else "related ") + f"item {i} uses `shared_hub`.",
                    )
                projection = MemoryGraph(memory, GraphStore(cfg))
                projection.sync("private:fixture")
                start = time.perf_counter()
                result = MemoryTools(memory, Services(projection.store), projection).memory_search(
                    "anchor", limit=20
                )
                elapsed = (time.perf_counter() - start) * 1000
                assert result["status"] == "ok", result["warnings"]
                assert len(result["items"]) == min(size, 20)
                results.append(
                    {
                        "memory_records": size,
                        "status": result["status"],
                        "returned": len(result["items"]),
                        "elapsed_ms": elapsed,
                        **result["traversal"],
                    }
                )
            finally:
                memory.close()
    report = {
        "scope": "synthetic_connected_memory_frontier",
        "results": results,
        "implementation_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (
                "src/brain/memory_walk.py",
                "src/brain/memory_search.py",
                "scripts/benchmark_memory_frontier.py",
            )
        },
        "limits": [
            "One query per size on a synthetic shared-identifier corpus",
            "Current eligible-view limits remain; no enterprise-scale claim",
            "No variable-length path enumeration; at most four native frontier queries",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
