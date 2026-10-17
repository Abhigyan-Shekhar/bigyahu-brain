"""Citable native memory paths, distinct from quotations of memory prose."""

from ..memory import canonical, digest
from .evidence import canonical_graph, ready
from .personal import memory_evidence
from .team import memory_evidence as team_evidence


def path_evidence(cfg, brain, uid, expected_hash):
    from ..graph import GraphStore

    ready(GraphStore(cfg))
    if brain == "private:" + cfg.principal:
        record = memory_evidence(cfg, uid, expected_hash)
    elif brain.startswith("team:"):
        record = team_evidence(cfg, brain[5:], uid, expected_hash)
    else:
        raise PermissionError("Memory path scope unavailable")
    graph = canonical_graph(record["graph"])
    text = canonical(graph)
    if len(text) > 12000 or graph.get("truncated") or record["graph"].get("truncated"):
        raise ValueError("Selected native path exceeds citation bound")
    return {
        "kind": "memory_path",
        "ref": {"brain": brain, "uid": uid, "expected_hash": expected_hash},
        "title": "Native memory path · " + brain,
        "text": text,
        "digest": digest(text),
        "revision": record["revision"],
        "uri": record["uri"],
        "graph": graph,
        "verification": "current_catalog_and_native_path",
        "binding": False,
    }
