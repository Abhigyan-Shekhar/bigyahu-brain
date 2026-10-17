"""Concept matches require literal current bytes, company grants and native evidence."""

import os
from unittest.mock import Mock

import pytest
from test_integration import real as real  # noqa: PLC0414
from test_memory import grant
from test_memory_company import bridge as bridge  # noqa: PLC0414

from brain.conversation import ingest_conversation
from brain.graph import GraphUnavailable
from brain.ingest.concepts import annotate_concepts, validate_mentions
from brain.ingest.documents import delete_documents
from brain.memory import canonical, digest
from brain.memory_ingest import share_memory
from brain.memory_tools import MemoryTools
from brain.services import Services


def docs(store):
    return store.query(
        "MATCH (d:Document {repo_id:$repo,current:true}) RETURN d.uid AS uid,d.text AS text ORDER BY uid",
        {"repo": store.cfg.repo_id},
    )


def analysis(doc, name="café payloads"):
    start = doc["text"].index(name)
    return {
        "items": [{"document": doc["uid"], "name": name, "start": start, "end": start + len(name)}]
    }


@pytest.mark.parametrize("change", ["invented", "source", "offset", "duplicate"])
def test_mentions_must_be_literal_and_unambiguous(change):
    documents = [{"uid": "doc", "text": "Preserve café payloads."}]
    result = analysis(documents[0])
    if change == "invented":
        result["items"][0]["name"] = "invented"
    elif change == "source":
        result["items"][0]["document"] = "unknown"
    elif change == "offset":
        result["items"][0]["start"] = True
    else:
        result["items"] *= 2
    with pytest.raises(ValueError):
        validate_mentions(documents, result)


live = pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires live graph")


def import_concept(memory, monkeypatch):
    text = "Decision: preserve café payloads."
    payload = {
        "format": "conversation/1",
        "session": "concept-fixture",
        "turns": [{"id": "u1", "role": "user", "text": text}],
    }
    monkeypatch.setattr(
        "brain.conversation_semantics.analyze",
        lambda *_: [
            {
                "turn": "u1",
                "start": 0,
                "end": len(text),
                "kind": "decision",
                "entities": ["café payloads"],
            }
        ],
    )
    result = ingest_conversation(
        memory, payload, digest(canonical(payload)), semantic_model="fixture-model"
    )
    item = result["items"][0]
    memory.review(
        "private:alice", item["uid"], "accept", item["hash"], "Synthetic concept fixture only"
    )
    return item


@live
@pytest.mark.integration
def test_live_semantic_entity_reaches_company_without_shared_citation_or_code_identifier(
    bridge, monkeypatch
):
    memory, store, projection, _citation, source = bridge
    document = docs(store)[0]
    monkeypatch.setattr("brain.ingest.concepts.structured_extract", lambda *_: analysis(document))
    result = annotate_concepts(store, [document["uid"]], "fixture-model")
    assert result["mentions"] == 1 and result["identity_resolution"] is False
    assert annotate_concepts(store, [document["uid"]], "fixture-model") == result
    item = import_concept(memory, monkeypatch)
    projection.sync("private:alice", include_company=True)
    tools = MemoryTools(memory, Services(store), projection)
    view = tools.memory_graph(include_company=True)
    assert view["status"] == "ok"
    kinds = {n["kind"] for n in view["nodes"]}
    assert {"CompanyConceptMention", "CompanySource", "CompanyDocument"} <= kinds
    assert any(e["relation"] == "MATCHES_MENTION" for e in view["edges"])
    assert not any(e["relation"] == "RESOLVES_TO" for e in view["edges"])
    assert not any(e["relation"] == "VERIFIED_SOURCE" for e in view["edges"])
    assert any(n["kind"] == "CompanySource" and n["text"] == source["text"] for n in view["nodes"])
    found = tools.memory_search(document["uid"], include_graph=True, backend="falkor")
    assert found["status"] == "ok" and found["items"][0]["uid"] == item["uid"]
    assert "MATCHES_MENTION" in found["items"][0]["graph_paths"][0]["relationships"]
    assert tools.memory_graph(include_company=False)["nodes"]
    assert not any(n["kind"].startswith("Company") for n in tools.memory_graph()["nodes"])
    grant(memory, "alice", "team:runtime", "reviewer")
    shared = share_memory(memory, item["uid"], item["hash"], "team:runtime")
    memory.review(
        "team:runtime", shared["uid"], "accept", shared["hash"], "Synthetic shared concept only"
    )
    projection.sync("team:runtime", include_company=True)
    team = tools.memory_graph(["team:runtime"], include_company=True)
    assert team["status"] == "ok" and any(e["relation"] == "MATCHES_MENTION" for e in team["edges"])
    delete_documents(store, ["guide.md"])
    retired = tools.memory_graph(include_company=True)
    assert not any(n["kind"] == "CompanyConceptMention" for n in retired["nodes"])


@live
@pytest.mark.integration
@pytest.mark.parametrize("changed", ["span", "bytes", "source_edge"])
def test_live_concept_bytes_and_spans_rechecked_on_every_read(bridge, monkeypatch, changed):
    memory, store, projection, _citation, source = bridge
    document = docs(store)[0]
    monkeypatch.setattr("brain.ingest.concepts.structured_extract", lambda *_: analysis(document))
    annotate_concepts(store, [document["uid"]], "fixture-model")
    import_concept(memory, monkeypatch)
    projection.sync("private:alice", include_company=True)
    if changed == "span":
        store.query(
            "MATCH (c:ConceptMention {repo_id:$repo}) SET c.start=0", {"repo": store.cfg.repo_id}
        )
    elif changed == "bytes":
        store.query(
            "MATCH (s:Source {uid:$source}) SET s.excerpt='changed source'",
            {"source": source["uid"]},
        )
    else:
        store.query(
            "MATCH (d:Document {uid:$doc})-[r:SUPPORTS]->() DELETE r", {"doc": document["uid"]}
        )
    view = projection.read(["private:alice"], include_company=True)
    assert not any(n["kind"] == "CompanyConceptMention" for n in view["nodes"])
    if changed != "source_edge":
        assert any(
            r["reason"] == "concept_source_span_unverified"
            for r in view["unresolved_company_references"]
        )


@live
@pytest.mark.integration
def test_live_failed_annotation_stays_fenced_and_retry_recovers(bridge, monkeypatch):
    _memory, store, _projection, _citation, _source = bridge
    document = docs(store)[0]
    model = Mock(return_value=analysis(document))
    monkeypatch.setattr("brain.ingest.concepts.structured_extract", model)
    query = store.query

    def fail(cypher, *args, **kwargs):
        if "SET d.concepts_json" in cypher:
            raise GraphUnavailable("Synthetic interruption")
        return query(cypher, *args, **kwargs)

    monkeypatch.setattr(store, "query", fail)
    with pytest.raises(GraphUnavailable):
        annotate_concepts(store, [document["uid"]], "fixture-model")
    assert store.revision()["syncing"] is True
    monkeypatch.setattr(store, "query", query)
    annotate_concepts(store, [document["uid"]], "fixture-model")
    assert store.revision()["syncing"] is False


@live
@pytest.mark.integration
def test_live_invalid_document_prevents_model_egress(bridge, monkeypatch):
    _memory, store, _projection, _citation, _source = bridge
    model = Mock()
    monkeypatch.setattr("brain.ingest.concepts.structured_extract", model)
    with pytest.raises(ValueError):
        annotate_concepts(store, ["missing"], "fixture-model")
    model.assert_not_called()
