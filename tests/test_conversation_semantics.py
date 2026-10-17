"""Models propose literal user spans, never authority or automatic correction acceptance."""

import json
from unittest.mock import Mock

import pytest
from test_memory import accepted
from test_memory import memory as memory  # noqa: PLC0414
from test_memory_graph import conversation

from brain.conversation import ingest_conversation
from brain.conversation_semantics import validate_analysis
from brain.memory import canonical, digest
from brain.memory_graph import MemoryGraph


def candidate(payload, kind="decision", entities=None):
    text = payload["turns"][0]["text"]
    return {
        "turn": "u1",
        "start": 0,
        "end": len(text),
        "kind": kind,
        "entities": entities or ["upload"],
    }


def test_consent_before_model_and_no_casual_memory(memory, monkeypatch):
    model = Mock(return_value=[])
    monkeypatch.setattr("brain.conversation_semantics.analyze", model)
    payload = conversation(text="thanks, that was helpful")
    with pytest.raises(ValueError, match="consent"):
        ingest_conversation(memory, payload, "wrong", semantic_model="example")
    model.assert_not_called()
    result = ingest_conversation(
        memory, payload, digest(canonical(payload)), semantic_model="example"
    )
    assert result["items"] == [] and result["extractor"] == "semantic-spans/1"
    assert memory.db.execute("SELECT count(*) FROM records").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["assistant", "invented", "range", "question"])
def test_hallucinated_entities_assistant_assertions_and_spans_rejected(change):
    payload = conversation(text="Use upload")
    item = candidate(payload)
    if change == "assistant":
        item["turn"] = "a1"
    elif change == "invented":
        item["entities"] = ["fabricated"]
    elif change == "range":
        item["end"] = 100
    else:
        payload["turns"][0]["text"] = "Use upload?"
        item["end"] = 11
    with pytest.raises(ValueError):
        validate_analysis(payload, {"items": [item]})


def test_semantic_entities_and_explicit_correction_stay_proposals(memory, monkeypatch, tmp_path):
    old = accepted(memory, "Use `upload` with threshold 3", uid="old")
    payload = conversation(text="Correction: use `upload` with threshold 5 instead of 3.")
    item = candidate(payload, "correction", ["upload", "threshold"])
    monkeypatch.setattr("brain.conversation_semantics.analyze", lambda *_: [item])
    result = ingest_conversation(
        memory, payload, digest(canonical(payload)), semantic_model="example"
    )
    assert len(result["relationships"]) == 1 and result["relationships"][0]["state"] == "proposed"
    link = memory.db.execute("SELECT * FROM memory_links").fetchone()
    assert link["target_uid"] == old["uid"] and link["relation"] == "UPDATES"
    assert (
        memory.db.execute(
            "SELECT state FROM records WHERE uid=?", (result["items"][0]["uid"],)
        ).fetchone()[0]
        == "proposed"
    )
    from brain.config import Config

    projection = MemoryGraph(
        memory, Mock(cfg=Config(tmp_path, "fixture", tenant_id="fixture", principal="alice"))
    )
    rows = projection._rows("private:alice", True)
    nodes, edges = projection._snapshot("private:alice", rows, True)
    assert any(n["kind"] == "Entity" and n["name"] == "threshold" for n in nodes)
    assert any(e["basis"] == "model_selected_literal_entity" for e in edges)
    metadata = json.loads(
        memory.db.execute(
            "SELECT detail FROM events WHERE action='conversation_analysis'"
        ).fetchone()[0]
    )
    assert metadata["model"] == "example" and metadata["kind"] == "correction"


def test_selected_sharing_preserves_only_literal_record_entities(memory, monkeypatch):
    from test_memory import grant

    from brain.memory_ingest import share_memory

    payload = conversation(text="Decision: preserve café payloads.")
    entry = candidate(payload, entities=["café payloads"])
    monkeypatch.setattr("brain.conversation_semantics.analyze", lambda *_: [entry])
    item = ingest_conversation(
        memory, payload, digest(canonical(payload)), semantic_model="fixture"
    )["items"][0]
    memory.review("private:alice", item["uid"], "accept", item["hash"], "Synthetic fixture only")
    grant(memory, "alice", "team:runtime", "reviewer")
    shared = share_memory(memory, item["uid"], item["hash"], "team:runtime")
    assert shared["state"] == "proposed"
    metadata = json.loads(
        memory.db.execute(
            "SELECT detail FROM events WHERE brain='team:runtime' AND action='conversation_analysis'"
        ).fetchone()[0]
    )
    assert metadata["entities"] == ["café payloads"] and metadata["hash"] == shared["hash"]
    assert metadata["model"] == "fixture"
    assert share_memory(memory, item["uid"], item["hash"], "team:runtime") == shared
    assert (
        memory.db.execute(
            "SELECT count(*) FROM events WHERE brain='team:runtime' AND action='conversation_analysis'"
        ).fetchone()[0]
        == 1
    )
