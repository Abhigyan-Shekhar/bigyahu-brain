"""Verify completed real semantic jobs, native FalkorDB storage and binary citations.

Read-only verification; no extraction calls or graph mutations. The report omits
runtime paths, tokens, full model output and uploaded source contents.
"""

import argparse
import hashlib
import json
from pathlib import Path

from brain.app.enrichment import validate_output
from brain.app.evidence import ready, source_evidence, verified_claims
from brain.app.state import State
from brain.config import load_config
from brain.graph import GraphStore
from brain.memory import canonical, digest
from brain.services import Services


def verify(state, project, turn=None):
    store = GraphStore(state.config(project))
    sha = ready(store)
    jobs = state.list("enrichment", project)
    verified = {}
    for engine in ("sdk", "graphify"):
        matching = [j for j in jobs if j["engine"] == engine and j["status"] == "complete"]
        assert matching, f"No complete {engine} job"
        job = matching[-1]
        audit = state.folder(project) / "enrichments" / job["id"]
        manifest = json.loads((audit / "manifest.json").read_text())
        extracted = json.loads((audit / "extraction.json").read_text())
        assert manifest["extraction_sha256"] == digest(canonical(extracted))
        for path, expected in manifest["implementation_sha256"].items():
            assert (
                hashlib.sha256((Path(__file__).parents[1] / "src" / path).read_bytes()).hexdigest()
                == expected
            ), "Implementation changed since model run"
        documents = [{**source_evidence(store, uid), "source": uid} for uid in job["sources"]]
        assert manifest["source_digests"] == {d["source"]: d["digest"] for d in documents}
        validate_output(extracted, {f"source{i}.txt": d["text"] for i, d in enumerate(documents)})
        key = digest(
            canonical([engine, job["model"], [(d["source"], d["digest"]) for d in documents]])
        )
        rows = store.query(
            "MATCH (d:Document {repo_id:$repo,semantic_batch:$key,current:true})-[:SUPPORTS]->(s:Source) RETURN d.uid AS uid,s.uid AS source",
            {"repo": store.cfg.repo_id, "key": key},
        )
        edges = store.query(
            "MATCH (a:Document {repo_id:$repo,semantic_batch:$key,current:true})-[r:EXTRACTED_RELATION]->(b:Document {repo_id:$repo,semantic_batch:$key,current:true}) RETURN r.relation AS relation,r.binding AS binding,r.confidence AS confidence,r.quote AS quote",
            {"repo": store.cfg.repo_id, "key": key},
        )
        assert len(rows) == job["result"]["nodes"] > 0
        assert len(edges) == job["result"]["relationships"] > 0
        assert all(
            e["binding"] is False and e["confidence"] in {"INFERRED", "AMBIGUOUS"} for e in edges
        )
        assert all(
            source_evidence(store, r["source"])["verification"]
            == "original_file_digest_and_extraction_snapshot"
            for r in rows
        )
        context = Services(store).get_context(rows[0]["uid"])
        assert context["untrusted_source_excerpts"]
        assert any("EXTRACTED_RELATION" in p["relationships"] for p in context["evidence"])
        verified[engine] = {
            **job["result"],
            "model": job["model"],
            "revision": sha,
            "native_nodes_checked": len(rows),
            "native_relationships_checked": len(edges),
            "source_citations_reverified": len(rows),
            "retrieval_contains_native_paths": True,
            "source_titles": [d["title"] for d in documents],
            "source_digests": [d["digest"] for d in documents],
            "extraction_sha256": manifest["extraction_sha256"],
            "implementation_sha256": manifest["implementation_sha256"],
        }
    chat = None
    if turn:
        value = state.get(turn, "turn")
        assert value["project"] == project and value["status"] == "complete"
        folder = state.folder(project) / "turns" / turn / "evidence"
        claims = verified_claims(store, folder, {"claims": value["claims"]})
        assert len(claims) > 0
        titles = {s["title"] for c in claims for s in c["support"]}
        assert any(t.endswith(".pdf") for t in titles) and any(t.endswith(".docx") for t in titles)
        chat = {
            "status": "passed",
            "checked_claims": len(claims),
            "source_titles": sorted(titles),
            "model": value["model"],
        }
    return {
        "status": "passed",
        "document_chat": chat,
        "scope": "Small synthetic PDF/Word browser acceptance, not extraction accuracy or enterprise scale evaluation",
        "engines": verified,
        "limits": [
            "No OCR, legacy .doc, images or layout-fidelity guarantee",
            "SDK uses its real ingestion pipeline with staged storage adapter and explicit graph-only indexing; no SDK vector retrieval/completion is claimed",
            "Semantic source spans establish provenance, not semantic entailment or identity",
            "Selected sections only; no automatic whole-repository semantic pass or multi-user hosting",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "data", "project", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--turn", help="Optional completed chat turn citing both PDF and Word")
    args = parser.parse_args()
    state = State(
        args.data, load_config(Path(args.config).resolve()), "verification-only", recover=False
    )
    result = verify(state, args.project, args.turn)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Verified both engines, native graph paths, original files and extraction snapshots")


if __name__ == "__main__":
    main()
