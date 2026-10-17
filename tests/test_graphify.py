"""Structural extraction keeps citations, confidence, revision and trust boundaries."""

import importlib.util
import os
from copy import deepcopy

import pytest
from test_integration import real as real  # noqa: PLC0414

from brain.ingest.graphify import ingest_graphify, normalize
from brain.ingest.sync import sync
from brain.services import Services


def test_non_utf8_python_rejected_before_extraction_or_mutation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from brain.ingest import graphify

    raw = b"# coding: latin-1\ndef cafe(): return 'caf\xe9'\n"
    compile(raw, "latin.py", "exec")  # Valid Python, outside this adapter's explicit constraint.
    (tmp_path / "latin.py").write_bytes(raw)
    monkeypatch.setattr(graphify, "revision", lambda root: "sha")
    monkeypatch.setattr(graphify, "clean", lambda root: True)
    monkeypatch.setattr(graphify, "git", lambda *args: "latin.py\0")
    cfg = SimpleNamespace(
        repo_root=tmp_path, repo_url="https://github.com/example/test", path=lambda p: p
    )
    store = SimpleNamespace(cfg=cfg, revision=lambda **kwargs: {"sha": "sha", "syncing": False})
    monkeypatch.setattr(
        graphify.subprocess, "run", lambda *a, **kw: pytest.fail("Extractor invoked")
    )
    with pytest.raises(ValueError, match="Graphify requires UTF-8 source files"):
        ingest_graphify(store, ["latin.py"])
    assert (tmp_path / "latin.py").read_bytes() == raw


def sample():
    return {
        "nodes": [{"id": "x", "label": "a()", "source_file": "x.py", "source_location": "L1"}],
        "edges": [],
        "failed_sources": [],
    }


@pytest.mark.parametrize(
    "change", ["escape", "range", "duplicate", "dangling", "confidence", "failure"]
)
def test_invalid_extraction_rejected(change):
    result = deepcopy(sample())
    if change == "escape":
        result["nodes"][0]["source_file"] = "../x.py"
    elif change == "range":
        result["nodes"][0]["source_location"] = "L2"
    elif change == "duplicate":
        result["nodes"] *= 2
    elif change == "dangling":
        result["edges"] = [
            {"source": "x", "target": "missing", "relation": "calls", "confidence": "EXTRACTED"}
        ]
    elif change == "confidence":
        result["edges"] = [{"source": "x", "target": "x", "relation": "calls", "confidence": []}]
    else:
        result["failed_sources"] = ["x.py"]
    with pytest.raises(ValueError):
        normalize(
            result,
            {"x.py": "def a(): pass\n"},
            "fixture",
            "sha",
            "https://github.com/example/fixture",
        )


def test_exact_bytes_and_nonbinding_structural_evidence():
    result = sample()
    result["nodes"].append({**result["nodes"][0], "id": "y", "label": "alias"})
    result["edges"] = [
        {"source": "x", "target": "y", "relation": "calls", "confidence": "INFERRED"}
    ]
    nodes, sources, edges = normalize(
        result, {"x.py": "def a(): pass\n"}, "fixture", "sha", "https://github.com/example/fixture"
    )
    assert len(nodes) == 2 and len(sources) == 1
    assert next(iter(sources.values()))["excerpt"] == "def a(): pass\n"
    assert edges[0][3] == "INFERRED"
    assert edges[0][5] == "graphify_origin_node_context"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("BRAIN_INTEGRATION") != "1" or importlib.util.find_spec("graphify") is None,
    reason="requires live FalkorDB and graphify extra",
)
def test_live_graphify_ingestion_retrieval_idempotency_and_bridge(real):
    sync(real)
    result = ingest_graphify(real, ["x.py"])
    assert result["nodes"] >= 4 and result["relationships"] >= 3
    assert result["semantic_extraction"] is False and result["binding"] is False
    assert ingest_graphify(real, ["x.py"]) == result
    nodes = real.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'graphify_structural',current:true}) RETURN d.uid AS uid",
        {"repo": real.cfg.repo_id},
    )
    context = Services(real).get_context(nodes[0]["uid"])
    assert context["untrusted_source_excerpts"]
    assert any("EXTRACTED_RELATION" in p["relationships"] for p in context["evidence"])
    assert real.revision()["syncing"] is False
    before = real.query(
        "MATCH (n {repo_id:$repo}) RETURN count(n) AS count", {"repo": real.cfg.repo_id}
    )
    with pytest.raises(ValueError):
        ingest_graphify(real, ["../x.py"])
    assert (
        real.query("MATCH (n {repo_id:$repo}) RETURN count(n) AS count", {"repo": real.cfg.repo_id})
        == before
    )
