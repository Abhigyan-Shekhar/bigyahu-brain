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
    for name in ("import-abhi", "import-session"):
        cmd = sub.add_parser(name)
        cmd.add_argument("path", type=Path)
        if name == "import-session":
            cmd.add_argument("--consent-digest", required=True)
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
                    or source.execute("PRAGMA user_version").fetchone()[0] != 1
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
        elif args.command == "import-session":
            payload = read_json(args.path)
            print("Curated export digest:", digest(canonical(payload)))
            operator("CONSENT " + args.consent_digest)
            result = ingest_session(memory, payload, args.consent_digest)
        elif args.command == "ingest-docs":
            result = ingest_local_documents(
                memory, args.brain, cfg.repo_root, args.paths, args.source_base
            )
        else:
            lines = args.path.read_text(encoding="utf-8").splitlines(keepends=True)
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
