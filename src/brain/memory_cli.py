"""Local catalog administration. Never registered as MCP tools.

Operator capabilities are intentionally separate from agent environments.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .config import load_config
from .memory import Identity, LocalEncoder, Memory, canonical, digest
from .memory_ingest import import_abhi, ingest_local_documents, ingest_session, read_json


def operator(action):
    if not sys.stdin.isatty() or os.environ.get("BRAIN_OPERATOR_SESSION") != "1":
        raise ValueError("Administration requires a separate interactive operator session")
    if input(f"Type {action} after independent review: ") != action:
        raise ValueError("Operation cancelled")


def selections(entries):
    pairs = [entry.split("=", 1) for entry in entries]
    if any(len(pair) != 2 for pair in pairs) or len({p[0] for p in pairs}) != len(pairs):
        raise ValueError("Select unique UID=HASH pairs")
    return dict(pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    reindex = sub.add_parser("reindex")
    reindex.add_argument("--brain", required=True)
    purge = sub.add_parser("purge-expired")
    purge.add_argument("--brain", required=True)
    grant = sub.add_parser("grant")
    grant.add_argument("--principal", required=True)
    grant.add_argument("--brain", required=True)
    grant.add_argument("--role", choices=["reader", "writer", "reviewer", "revoke"], required=True)
    review = sub.add_parser("review")
    review.add_argument("--brain", required=True)
    review.add_argument("--uid", required=True)
    review.add_argument("--hash", required=True)
    review.add_argument(
        "--action", choices=["accept", "reject", "expire", "rollback"], required=True
    )
    review.add_argument("--reason", required=True)
    share = sub.add_parser("share")
    share.add_argument("--uid", required=True)
    share.add_argument("--hash", required=True)
    share.add_argument("--target", required=True)
    share.add_argument("--expected-target", default="")
    export = sub.add_parser("export-abhi")
    export.add_argument("target", type=Path)
    export.add_argument("--brain", required=True)
    export.add_argument("--record", action="append", required=True, metavar="UID=HASH")
    export.add_argument("--team", required=True)
    export.add_argument("--collection", required=True)
    export.add_argument("--link", action="append", default=[], help="Explicit accepted link UID")
    propose_link = sub.add_parser("propose-link")
    propose_link.add_argument("--brain", required=True)
    propose_link.add_argument("--source", required=True)
    propose_link.add_argument("--source-hash", required=True)
    propose_link.add_argument("--target", required=True)
    propose_link.add_argument("--target-hash", required=True)
    propose_link.add_argument("--relation", choices=["UPDATES", "EXTENDS", "RELATES_TO"], required=True)
    propose_link.add_argument("--sources", type=Path, required=True)
    suggest_links = sub.add_parser("suggest-links")
    suggest_links.add_argument("--brain", required=True)
    suggest_links.add_argument("--record", action="append", required=True, metavar="UID=HASH")
    review_link = sub.add_parser("review-link")
    review_link.add_argument("--brain", required=True)
    review_link.add_argument("--uid", required=True)
    review_link.add_argument("--expected-state", choices=["proposed", "accepted", "rejected"], required=True)
    review_link.add_argument("--action", choices=["accept", "reject", "rollback"], required=True)
    review_link.add_argument("--reason", required=True)
    for name in ("import-abhi", "import-session", "import-conversation"):
        cmd = sub.add_parser(name)
        cmd.add_argument("path", type=Path)
        if name in {"import-session", "import-conversation"}:
            cmd.add_argument("--consent-digest", required=True)
    for name in ("sync-graph", "graph-view"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--brain", required=True)
        cmd.add_argument("--include-company", action="store_true")
        if name == "graph-view":
            cmd.add_argument("--include-proposals", action="store_true")
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--brain", action="append")
    search.add_argument("--backend", choices=["auto", "falkor", "catalog"], default="auto")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--include-graph", action="store_true")
    search.add_argument("--include-proposals", action="store_true")
    docs = sub.add_parser("ingest-docs")
    docs.add_argument("--brain", required=True)
    docs.add_argument("--source-base", required=True)
    docs.add_argument("paths", nargs="+")
    delete = sub.add_parser("delete")
    delete.add_argument("--brain", required=True)
    delete.add_argument("--uid", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("target", type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("target", type=Path)
    restore.add_argument("--sha256", required=True)
    verify = sub.add_parser("verify-citation")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--start", type=int, default=1)
    verify.add_argument("--end", type=int)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if not cfg.memory_db:
        parser.error("Explicit memory_db and tenant_id configuration required")
    memory = Memory(
        cfg.memory_db,
        Identity(cfg.tenant_id, cfg.principal),
        LocalEncoder(cfg.embedding_model_dir) if cfg.embedding_model_dir else None,
    )
    try:
        if args.command == "health":
            result = memory.health()
        elif args.command == "search":
            from .graph import GraphStore
            from .memory_graph import MemoryGraph
            from .memory_tools import MemoryTools
            from .services import Services

            store = GraphStore(cfg)
            projection = MemoryGraph(memory, store) if cfg.memory_graph_enabled else None
            result = MemoryTools(memory, Services(store), projection).memory_search(
                args.query, args.brain, args.include_graph,
                args.include_proposals, args.limit, args.backend)
        elif args.command == "reindex":
            memory.authorize(args.brain, review=True)
            if not memory.embedder:
                raise ValueError("Local model required for reindex")
            operator("REINDEX " + args.brain)
            with memory.db:
                rows = memory.db.execute(
                    "SELECT uid,text FROM records WHERE tenant=? AND brain=? AND state!='deleted'",
                    (cfg.tenant_id, args.brain),
                ).fetchall()
                for row in rows:
                    memory.db.execute(
                        "UPDATE records SET vector=?,model=? WHERE tenant=? AND brain=? AND uid=?",
                        (
                            canonical(memory.embedder.encode(row["text"])),
                            memory.embedder.identity,
                            cfg.tenant_id,
                            args.brain,
                            row["uid"],
                        ),
                    )
            result = {"reindexed": len(rows)}
        elif args.command == "purge-expired":
            from .memory import now

            memory.authorize(args.brain, review=True)
            operator("PURGE EXPIRED " + args.brain)
            rows = memory.db.execute(
                "SELECT uid FROM records WHERE tenant=? AND brain=? AND "
                "(state='expired' OR (expires!='' AND expires<=?))",
                (cfg.tenant_id, args.brain, now()),
            ).fetchall()
            for row in rows:
                memory.delete(args.brain, row["uid"])
            result = {"purged": len(rows)}
        elif args.command == "grant":
            Identity(cfg.tenant_id, args.principal)
            if args.brain != "company" and not __import__("re").fullmatch(
                r"team:[A-Za-z0-9_-]{1,64}", args.brain
            ):
                raise ValueError("Only shared brains have membership grants")
            operator("GRANT " + args.principal + " " + args.brain + " " + args.role)
            with memory.db:
                memory.db.execute(
                    "DELETE FROM grants WHERE tenant=? AND principal=? AND brain=?",
                    (cfg.tenant_id, args.principal, args.brain),
                )
                if args.role != "revoke":
                    memory.db.execute(
                        "INSERT INTO grants VALUES(?,?,?,?)",
                        (cfg.tenant_id, args.principal, args.brain, args.role),
                    )
                memory._event(args.brain, args.principal, "membership", args.role)
            result = {"membership": args.role}
        elif args.command == "export-abhi":
            from .abhi_graph import export_graph, write_graph

            payload = export_graph(memory, args.brain, selections(args.record),
                                   args.team, args.collection, args.link)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            operator("EXPORT GRAPH " + payload["digest"])
            write_graph(args.target, payload)
            result = {"exported": "abhi/2", "digest": payload["digest"],
                      "records": len(payload["records"]), "binding": False}
        elif args.command in {"propose-link", "review-link", "suggest-links"}:
            from .memory_links import MemoryLinks

            links = MemoryLinks(memory)
            if args.command == "propose-link":
                result = links.propose(args.brain, args.source, args.source_hash, args.relation,
                                       args.target, args.target_hash, read_json(args.sources))
            elif args.command == "suggest-links":
                result = links.suggest(args.brain, selections(args.record))
            else:
                memory.authorize(args.brain, review=True)
                row = memory.db.execute(
                    "SELECT * FROM memory_links WHERE tenant=? AND brain=? AND uid=?",
                    (cfg.tenant_id, args.brain, args.uid),
                ).fetchone()
                print(json.dumps(dict(row) if row else {}, indent=2))
                if row:
                    endpoints = memory.db.execute(
                        "SELECT uid,hash,state,text,sources FROM records WHERE tenant=? AND brain=? "
                        "AND uid IN (?,?)",
                        (cfg.tenant_id, args.brain, row["source_uid"], row["target_uid"]),
                    ).fetchall()
                    print(json.dumps([dict(r) for r in endpoints], indent=2))
                operator(args.action.upper() + " LINK " + args.uid + " " + args.expected_state)
                result = links.review(args.brain, args.uid, args.action,
                                      args.expected_state, args.reason)
        elif args.command == "share":
            from .memory_ingest import share_memory

            memory.authorize(args.target, write=True)
            record = memory.db.execute(
                "SELECT text,sources,hash FROM records WHERE tenant=? AND brain=? AND uid=?",
                (cfg.tenant_id, "private:" + cfg.principal, args.uid),
            ).fetchone()
            print(json.dumps(dict(record) if record else {}, indent=2))
            operator("SHARE " + args.uid + " " + args.target + " " + args.hash)
            result = share_memory(memory, args.uid, args.hash, args.target, args.expected_target)
        elif args.command == "review":
            # Print the exact private/team record and citations only in the operator terminal.
            memory.authorize(args.brain, review=True)
            record = memory.db.execute(
                "SELECT uid,text,sources,state,hash FROM records WHERE tenant=? AND brain=? AND uid=?",
                (cfg.tenant_id, args.brain, args.uid),
            ).fetchone()
            print(json.dumps(dict(record) if record else {}, indent=2))
            operator(args.action.upper() + " " + args.uid + " " + args.hash)
            result = memory.review(args.brain, args.uid, args.action, args.hash, args.reason)
        elif args.command == "delete":
            operator("DELETE " + args.uid)
            memory.delete(args.brain, args.uid)
            result = {"deleted": args.uid}
        elif args.command == "backup":
            operator("BACKUP")
            memory.backup(args.target)
            result = {"backup": "complete"}
        elif args.command == "restore":
            import hashlib

            if (
                not args.backup.is_file()
                or hashlib.sha256(args.backup.read_bytes()).hexdigest() != args.sha256
            ):
                raise ValueError("Backup checksum mismatch")
            if args.target.exists() or args.target.resolve() == Path(cfg.memory_db).resolve():
                raise ValueError("Restore requires a new database path, never the active catalog")
            operator("RESTORE ISOLATED BACKUP")
            with sqlite3.connect(args.backup.resolve().as_uri() + "?mode=ro", uri=True) as source:
                if (
                    source.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                    or source.execute("PRAGMA user_version").fetchone()[0] not in {1, 2}
                ):
                    raise ValueError("Backup integrity or schema check failed")
                with args.target.open("x"):
                    pass
                args.target.chmod(0o600)
                with sqlite3.connect(args.target) as target:
                    source.backup(target)
            result = {
                "restored": "isolated copy; replay later deletion/revocation records before use"
            }
        elif args.command == "import-abhi":
            result = import_abhi(memory, read_json(args.path))
        elif args.command in {"sync-graph", "graph-view"}:
            from .graph import GraphStore
            from .memory_graph import MemoryGraph

            projection = MemoryGraph(memory, GraphStore(cfg))
            if args.command == "sync-graph":
                operator("SYNC MEMORY GRAPH " + args.brain)
                result = projection.sync(args.brain, args.include_company)
            else:
                result = projection.read([args.brain], args.include_proposals, args.include_company)
        elif args.command in {"import-session", "import-conversation"}:
            payload = read_json(args.path)
            print("Export digest:", digest(canonical(payload)))
            operator("CONSENT " + args.consent_digest)
            if args.command == "import-conversation":
                from .conversation import ingest_conversation

                result = ingest_conversation(memory, payload, args.consent_digest)
            else:
                result = ingest_session(memory, payload, args.consent_digest)
        elif args.command == "ingest-docs":
            result = ingest_local_documents(
                memory, args.brain, cfg.repo_root, args.paths, args.source_base
            )
        else:
            lines = args.path.read_bytes().decode("utf-8").splitlines(keepends=True)
            if args.start < 1 or (args.end is not None and args.end < args.start):
                raise ValueError("Invalid citation line range")
            raw = "".join(lines[args.start - 1 : args.end]).encode()
            if __import__("hashlib").sha256(raw).hexdigest() != args.sha256:
                raise ValueError("Citation changed; reread evidence and revise the plan")
            result = {"citation": "verified"}
        print(json.dumps(result, indent=2))
    finally:
        memory.close()


if __name__ == "__main__":
    main()
