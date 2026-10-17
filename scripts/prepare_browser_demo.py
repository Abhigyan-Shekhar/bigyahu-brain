"""Rebuild an isolated public-source Browser demo; never approve decisions."""

import argparse
import ast
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from falkordb import FalkorDB

from brain.config import Config
from brain.graph import GraphStore
from brain.ingest.git_parser import clean, revision
from brain.ingest.snapshots import ingest_snapshots, read_snapshot
from brain.ingest.sync import sync

ROOT = Path(__file__).resolve().parents[1]
SHA = "a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8"
REPO = "demo:urllib3:browser:eligible"
URL = "https://github.com/urllib3/urllib3"


class DemoStore(GraphStore):
    """Use the ordinary org schema without creating an unused private graph."""

    def bootstrap(self):
        existing = {
            (row["label"], field)
            for row in self.query("CALL db.indexes()")
            for field, kinds in row.get("types", {}).items()
            if "FULLTEXT" in kinds
        }
        for label, fields in {
            "Decision": ["text"], "Document": ["text"],
            "Issue": ["title", "body"], "PR": ["title", "body"],
        }.items():
            missing = [field for field in fields if (label, field) not in existing]
            if missing:
                args = ", ".join(repr(value) for value in [label, *missing])
                self.query(f"CALL db.idx.fulltext.createNodeIndex({args})")


def build(checkout, port, output, config=None):
    cfg = Config(checkout, REPO, URL, "browser_demo", port=port)
    # Complete local preflight before connecting or writing any graph data.
    original, fixture_records = read_snapshot(ROOT / "tests/fixtures/urllib3-history")
    records = [record for record in fixture_records if record["number"] in (3780, 5161)]
    if (sorted(record["number"] for record in records) != [3780, 5161]
            or not all(record["pull_request"]["merged_at"] for record in records)):
        raise ValueError("Expected both merged public fixture PRs")
    if (output / "corpus").exists():
        raise ValueError("Output corpus already exists; choose a fresh --output directory")
    if revision(checkout) != SHA or not clean(checkout):
        raise ValueError("Expected a clean checkout at the documented pinned revision")
    client = FalkorDB(host="127.0.0.1", port=port)
    graphs = client.list_graphs()
    if graphs:
        raise ValueError("Expected an empty isolated database; existing data is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    config = config or ROOT / "config/brain.browser-demo.local.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(yaml.safe_dump({
        "repo_root": str(checkout), "repo_id": REPO, "repo_url": URL,
        "principal": "browser_demo", "host": "127.0.0.1", "port": port,
    }), encoding="utf-8")
    store = DemoStore(cfg)
    sync_result = sync(store)
    corpus = output / "corpus"
    corpus.mkdir()
    raw = (json.dumps(records, indent=2) + "\n").encode()
    (corpus / "work.json").write_bytes(raw)
    manifest = {**original, "repo_id": REPO, "records": 2,
                "sources": [record["html_url"] for record in records],
                "work_sha256": hashlib.sha256(raw).hexdigest(),
                "reconstruction": "Fresh demo; not the original experiment database",
                "omitted_work_items": [5181, 5242]}
    (corpus / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    history_result = ingest_snapshots(store, corpus)

    def file(path):
        return f"{REPO}@{SHA}:{path}"

    def symbol(path, qualname):
        uid = f"{file(path)}::{qualname}"
        rows = store.query("MATCH (s:Symbol {uid:$uid, current:true}) RETURN s.uid AS uid",
                           {"uid": uid})
        assert len(rows) == 1, uid
        return uid

    def source(path, start, end):
        lines = (checkout / path).read_text(encoding="utf-8").splitlines()
        uid = f"{file(path)}:L{start}-L{end}:source"
        store.upsert("Source", uid, {
            "repo_id": REPO, "uri": f"{URL}/blob/{SHA}/{path}#L{start}-L{end}",
            "name": f"{Path(path).name}:L{start}",
            "excerpt": "\n".join(lines[start - 1:end]), "revision": SHA,
            "lineno": start, "end_lineno": end, "path": path,
            "provenance": "pinned_checkout_exact_lines", "scope": "org",
        })
        return uid

    pool = "src/urllib3/connectionpool.py"
    request = "src/urllib3/util/request.py"
    openssl = "src/urllib3/contrib/pyopenssl.py"
    init = "src/urllib3/util/__init__.py"
    wait = "src/urllib3/util/wait.py"
    caller = symbol(pool, "HTTPConnectionPool.urlopen")
    callee = symbol(request, "set_file_position")
    recv = symbol(openssl, "WrappedSocket.recv")
    wait_read = symbol(wait, "wait_for_read")
    for a, b, line in ((caller, callee, 772), (recv, wait_read, 324)):
        rows = store.query(
            "MATCH (a:Symbol {uid:$a})-[r:CALLS]->(b:Symbol {uid:$b}) "
            "RETURN r.line AS line, r.confidence AS confidence, r.resolution AS resolution",
            {"a": a, "b": b})
        assert rows == [{"line": line, "confidence": "static",
                         "resolution": "statically_resolved_import"}], rows

    # Add explicitly labeled import evidence; CALLS above comes from the real ingester.
    for path, target, line, module, names in (
        (openssl, init, 61, None, ["util"]),
        (init, wait, 20, "wait", ["wait_for_read", "wait_for_write"]),
    ):
        imports = [node for node in ast.walk(ast.parse((checkout / path).read_text(encoding="utf-8")))
                   if isinstance(node, ast.ImportFrom) and node.lineno == line]
        assert len(imports) == 1
        assert imports[0].module == module
        assert [name.name for name in imports[0].names] == names
        sid = source(path, line, line)
        store.edge(file(path), "IMPORTS", file(target), {
            "line": line, "source_uid": sid, "source_url": f"{URL}/blob/{SHA}/{path}#L{line}",
            "confidence": "static", "method": "demo_verified_ast_import",
            "basis": "reconstructed_demo_import_evidence", "revision": SHA, "is_demo": True,
        })

    for uid, name in (
        (caller, "urlopen"), (callee, "set_file_position"),
        (recv, "recv"), (wait_read, "wait_for_read"),
        (file(pool), "connectionpool.py"), (file(openssl), "pyopenssl.py"),
        (file(init), "util/__init__.py"), (file(wait), "util/wait.py"),
        (f"{REPO}:pr:5161", "#5161"),
        (f"{REPO}:pr:5161:source", "#5161 source"),
        (f"{REPO}:pr:3780:source", "#3780 source"),
    ):
        store.query("MATCH (n {uid:$uid}) SET n.name=$name", {"uid": uid, "name": name})

    document = f"{REPO}:document:redirect-review"
    document_source = document + ":source"
    text = (ROOT / "docs/browser-demo/document.md").read_text(encoding="utf-8")
    store.upsert("Document", document, {
        "repo_id": REPO, "name": "DEMO document", "text": text,
        "scope": "org", "is_demo": True, "provenance": "reconstructed_demo_document",
    })
    store.upsert("Source", document_source, {
        "repo_id": REPO, "uri": "urn:company-brain:browser-demo:redirect-review",
        "excerpt": text, "local_relative_path": "docs/browser-demo/document.md",
        "is_demo": True, "provenance": "local_demo_document_not_upstream",
    })
    store.edge(document, "SUPPORTS", document_source)
    store.edge(document, "REFERENCES", f"{REPO}:pr:5161", {
        "basis": "explicit_link_in_reconstructed_demo_document", "source_uid": document_source,
        "confidence": "explicit_text_reference", "resolution_verified": False,
    })
    cleanup = source(pool, 910, 922)
    rewind = source(request, 176, 230)
    now = datetime.now(UTC).isoformat()
    proposals = [
        ("D-1", ("Demo policy proposal: preserve 303 cleanup in HTTPConnectionPool.urlopen: "
         "drop the body, chunked framing, saved body position, and body-specific headers."),
         "", [f"{REPO}:pr:5161:source", cleanup]),
        ("D-2", ("Demo replacement proposal: preserve D-1's 303 cleanup and explicit "
         "UnrewindableBodyError when replay cannot rewind the body. A failed tell() alone "
         "must not reject the initial request before replay is required."),
         "D-1", [f"{REPO}:pr:5161:source", cleanup, f"{REPO}:pr:3780:source", rewind]),
    ]
    for uid, text, old, sources in proposals:
        store.upsert("Decision", uid, {
            "repo_id": REPO, "name": uid, "text": text,
            "scope": "org", "kind": "constraint", "status": "proposed", "approval": "none",
            "requested_supersedes": old, "created_at": now, "created_by": "Codex",
            "is_demo": True, "provenance": "reconstructed_demo_proposal",
        })
        for sid in sources:
            assert store.query("MATCH (s:Source {uid:$uid}) RETURN s.uid AS uid", {"uid": sid})
            store.edge(uid, "SUPPORTED_BY", sid)
        store.edge(uid, "CONSTRAINS", caller)

    report = {"repo_id": REPO, "revision": SHA, "reconstructed_demo": True,
              "sync": sync_result, "history": history_result,
              "native_ingestion": ["File", "Symbol", "DECLARES", "CALLS", "PR", "CHANGES"],
              "demo_seeded": ["Document", "document REFERENCES", "File IMPORTS",
                              "exact-line Sources", "Decision proposals and evidence links"],
              "proposals": [{"uid": uid, "text": text, "requested_supersedes": old,
                             "source_uids": sources} for uid, text, old, sources in proposals],
              "graph_counts": store.query("MATCH (n) RETURN count(n) AS nodes"),
              "approval": "pending_independent_human_operator"}
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--output", type=Path, default=ROOT / "data/validation/browser-demo")
    parser.add_argument("--config", type=Path,
                        default=ROOT / "config/brain.browser-demo.local.yaml")
    args = parser.parse_args()
    build(args.checkout.resolve(), args.port, args.output.resolve(), args.config.resolve())
