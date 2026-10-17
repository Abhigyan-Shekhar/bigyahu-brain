"""Binary extraction and real SDK pipeline contracts, with explicit source grounding."""

import asyncio
import io
import os
from copy import deepcopy

import pytest
from test_integration import real as real  # noqa: PLC0414

from brain.app.enrichment import publish, validate_output
from brain.ingest.binary_document import extract


def pdf_bytes(text="Acme owns Retry Service."):
    # Small real text PDF; no fixture-generation dependency or embedded executable content.
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(
        f"{n:010d} 00000 n \n".encode() for n in offsets[1:]
    )
    result += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return result


def test_pdf_extracts_real_page_text_and_rejects_blank_or_invalid():
    pytest.importorskip("pypdf")
    result = extract(pdf_bytes(), ".pdf")
    assert "# Page 1\nAcme owns Retry Service." in result["text"]
    assert result["units"] == 1
    with pytest.raises(ValueError):
        extract(b"not pdf", ".pdf")
    with pytest.raises(ValueError, match="without extractable text"):
        extract(pdf_bytes(""), ".pdf")


def test_word_extracts_paragraph_table_order_and_rejects_archive_bomb():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Before table")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Retry", "800 ms"
    document.add_paragraph("After table")
    stream = io.BytesIO()
    document.save(stream)
    assert (
        extract(stream.getvalue(), ".docx")["text"] == "Before table\nRetry | 800 ms\nAfter table\n"
    )
    import zipfile

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"x" * 10_000_001)
    with pytest.raises(ValueError, match="expanded archive"):
        extract(stream.getvalue(), ".docx")


def sample():
    return {
        "nodes": [
            {"id": "a", "name": "Acme", "unit": "source0.txt", "quote": "Acme"},
            {"id": "b", "name": "Retry Service", "unit": "source0.txt", "quote": "Retry Service"},
        ],
        "edges": [
            {
                "a": "a",
                "b": "b",
                "relation": "OWNS",
                "unit": "source0.txt",
                "quote": "Acme owns Retry Service.",
            }
        ],
    }


@pytest.mark.parametrize(
    "case", ["invented", "range", "dangling", "cypher", "duplicate", "oversize"]
)
def test_invalid_semantics_never_reach_publication(case):
    value = deepcopy(sample())
    if case == "invented":
        value["nodes"][0]["name"] = "Invented"
    elif case == "range":
        value["edges"][0]["quote"] = "invented evidence"
    elif case == "dangling":
        value["edges"][0]["a"] = "missing"
    elif case == "cypher":
        value["edges"][0]["relation"] = "X]->() DELETE n //"
    elif case == "duplicate":
        value["nodes"].append(value["nodes"][0])
    else:
        value["nodes"] *= 101
    with pytest.raises(ValueError):
        validate_output(value, {"source0.txt": "Acme owns Retry Service."})


def test_real_sdk_ingestion_pipeline_uses_llm_and_emits_grounded_relations(monkeypatch):
    pytest.importorskip("graphrag_sdk")
    from brain.ingest import semantic_worker as worker

    text = "Acme owns Retry Service."
    calls = []

    def response(prompt, model):
        calls.append(prompt)
        if "Pre-extracted Entities" not in prompt:
            return {
                "entities": [
                    {"name": "Acme", "type": "organization"},
                    {"name": "Retry Service", "type": "product"},
                ]
            }
        return {
            "entities": [
                {"name": "Acme", "type": "organization", "description": "Acme"},
                {"name": "Retry Service", "type": "product", "description": "Retry Service"},
            ],
            "relationships": [
                {
                    "source": "Acme",
                    "target": "Retry Service",
                    "type": "OWNS",
                    "description": text,
                    "span_start": 0,
                    "span_end": len(text),
                }
            ],
        }

    monkeypatch.setattr(worker, "model_json", response)
    result = asyncio.run(worker.sdk_extract({"source0.txt": text}, "explicit-model"))
    nodes, edges = validate_output(result, {"source0.txt": text})
    assert len(calls) == 2 and len(nodes) == 2 and len(edges) == 1
    assert result["engine"] == "graphrag-sdk/1.4.0" and result["vectors"] is False


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_native_publication_idempotency_and_copied_source_provenance(real):
    from brain.app.evidence import source_evidence
    from brain.ingest.sync import sync
    from brain.memory import digest

    sync(real)
    text = "Acme owns Retry Service."
    source = real.cfg.repo_id + ":test-recorded-source"
    real.upsert(
        "Source",
        source,
        {
            "repo_id": real.cfg.repo_id,
            "excerpt": text,
            "digest": digest(text),
            "uri": real.cfg.repo_url + "/issues/1",
            "revision": real.revision()["sha"],
        },
    )
    real.upsert("Document", source + ":doc", {"repo_id": real.cfg.repo_id, "current": True})
    real.edge(source + ":doc", "SUPPORTS", source)
    documents = [{"text": text, "digest": digest(text), "source": source, "title": "Policy"}]
    result = {**sample(), "engine": "test-provider", "pipeline": "test"}
    for _ in range(2):
        assert (
            publish(real, result, documents, "sdk", "explicit-model", real.revision()["sha"])[
                "relationships"
            ]
            == 1
        )
    rows = real.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'semantic_advisory',current:true})-[:SUPPORTS]->(s:Source) RETURN s.uid AS uid",
        {"repo": real.cfg.repo_id},
    )
    assert len(rows) == 2
    assert all(source_evidence(real, r["uid"])["text"] == text for r in rows)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
def test_binary_citation_revalidates_original_and_snapshot(real):
    pytest.importorskip("pypdf")
    from types import SimpleNamespace

    from brain.app.evidence import source_evidence
    from brain.app.sources import upload_binary
    from brain.ingest.sync import sync

    sync(real)
    state = SimpleNamespace(config=lambda _: real.cfg, folder=lambda _: real.cfg.repo_root.parent)
    receipt = upload_binary(state, "fixture", "policy.pdf", pdf_bytes())
    assert receipt["format"] == "pdf" and receipt["sections"] == 1
    row = real.query(
        "MATCH (s:Source {repo_id:$repo,source_kind:'app_binary_upload'}) RETURN s.uid AS uid,s.snapshot_digest AS snapshot",
        {"repo": real.cfg.repo_id},
    )[0]
    proof = source_evidence(real, row["uid"])
    assert proof["verification"] == "original_file_digest_and_extraction_snapshot"
    assert "Acme owns Retry Service." in proof["text"]
    folder = real.cfg.repo_root.parent / "uploads"
    original = folder / receipt["digest"]
    raw = original.read_bytes()
    original.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Original document"):
        source_evidence(real, row["uid"])
    original.write_bytes(raw)
    (folder / row["snapshot"]).write_text("tampered")
    with pytest.raises(ValueError, match="extraction snapshot"):
        source_evidence(real, row["uid"])
