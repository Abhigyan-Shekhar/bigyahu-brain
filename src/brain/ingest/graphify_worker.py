"""Isolated deterministic Graphify invocation; never executes repository code."""

import json
import sys
from importlib.metadata import version
from pathlib import Path

PIN = "0.9.92"


def main():
    if version("graphifyy") != PIN:
        raise ValueError("Install the pinned graphify extra")
    from graphify.extract import extract

    root, cache, output = map(Path, sys.argv[1:4])
    root = root.resolve()
    paths = json.loads(Path(sys.argv[4]).read_text())
    result = extract([root / p for p in paths], root=root, cache_root=cache, parallel=False)
    # External type/import references have no definition location. Keep repository
    # definitions with real source locations; explicitly account for excluded topology.
    nodes = [
        n
        for n in result["nodes"]
        if n.get("source_file") != "" and n.get("source_location") not in (None, "")
    ]
    ids = {n["id"] for n in nodes}
    edges = [e for e in result["edges"] if e.get("source") in ids and e.get("target") in ids]
    output.write_text(
        json.dumps(
            {
                "nodes": nodes,
                "edges": edges,
                "failed_sources": result["failed_sources"],
                "coverage": {
                    "unlocated_nodes_excluded": len(result["nodes"]) - len(nodes),
                    "relationships_without_located_endpoints": len(result["edges"]) - len(edges),
                },
            }
        )
    )


if __name__ == "__main__":
    main()
