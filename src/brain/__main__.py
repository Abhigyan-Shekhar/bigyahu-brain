import argparse
import json

from .config import load_config
from .graph import GraphStore


def main():
    parser = argparse.ArgumentParser(description="Company Brain operator utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a standalone config for an existing local checkout")
    init.add_argument("--repo", required=True)
    init.add_argument("--config", required=True)
    init.add_argument("--repo-id", required=True)
    init.add_argument("--repo-url", default="", help="Public GitHub URL for source citations/enrichment")
    init.add_argument("--principal", required=True)
    init.add_argument("--host", default="127.0.0.1")
    init.add_argument("--port", type=int, default=6379)
    init.add_argument("--sync", action="store_true", help="Index using an already-running FalkorDB")
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("--registry")
    sync_parser.add_argument("--repo-root")
    register = sub.add_parser("register", help="Allowlist a repository config for native MCP routing")
    register.add_argument("--registry", required=True)
    register.add_argument("--config", required=True)
    sub.add_parser("health")
    sub.add_parser("ingest-snapshots").add_argument("directory")
    sub.add_parser("ingest-graphify").add_argument("paths", nargs="*")
    concepts = sub.add_parser("annotate-concepts")
    concepts.add_argument("--document", action="append", required=True)
    concepts.add_argument("--model", required=True)
    sub.add_parser("ingest-docs").add_argument("paths", nargs="*")
    sub.add_parser("retire-docs").add_argument("paths", nargs="+")
    github = sub.add_parser("sync-github")
    github.add_argument("--output", required=True)
    github.add_argument("--reconcile", action="store_true")
    sub.add_parser("list-proposals")
    for command in ("inspect", "approve", "review-history"):
        command_parser=sub.add_parser(command)
        command_parser.add_argument("decision_id")
        if command=="approve":
            command_parser.add_argument("--expires-at",default="")
    review=sub.add_parser("review-decision")
    review.add_argument("decision_id")
    review.add_argument("--action",choices=["reject","expire","rollback"],required=True)
    review.add_argument("--reason",required=True)
    args = parser.parse_args()
    if args.command == "register":
        from .registry import register_repository

        print(json.dumps(register_repository(args.registry, args.config), indent=2))
        return
    if args.command == "init":
        from .setup import initialize

        cfg, destination = initialize(
            args.repo, args.config, args.repo_id, args.principal, args.host, args.port, args.repo_url
        )
        result = {"config": str(destination), "repo_id": cfg.repo_id, "indexed": False}
        if args.sync:
            from .ingest.sync import sync

            result["sync"] = sync(GraphStore(cfg))
            result["indexed"] = True
        print(json.dumps(result, indent=2))
        return
    if args.command == "sync" and (args.registry or args.repo_root):
        if not args.registry or not args.repo_root:
            parser.error("Registry sync requires both --registry and --repo-root")
        from pathlib import Path

        from .registry import load_registry, select_repository

        _, cfg = select_repository(load_registry(Path(args.registry).expanduser().resolve()), args.repo_root)
    else:
        cfg = load_config()
    store = GraphStore(cfg)
    if args.command == "sync":
        from .ingest.sync import sync

        result = sync(store)
    elif args.command == "health":
        result={"graph_revision":store.revision(),"graph":store.cfg.graph_name("org")}
    elif args.command == "sync-github":
        from .ingest.github_sync import sync_github

        result = sync_github(store, args.output, reconcile=args.reconcile)
    elif args.command == "retire-docs":
        from .admin import require_operator
        from .ingest.documents import delete_documents

        require_operator("RETIRE DOCUMENTS")
        result = delete_documents(store, args.paths)
    elif args.command == "ingest-graphify":
        from .ingest.graphify import ingest_graphify

        result = ingest_graphify(store, args.paths or None)
    elif args.command == "annotate-concepts":
        from .ingest.concepts import annotate_concepts

        result = annotate_concepts(store, args.document, args.model)
    elif args.command == "ingest-docs":
        from .ingest.documents import ingest_documents

        result = ingest_documents(store, args.paths or None)
    elif args.command == "ingest-snapshots":
        from .ingest.snapshots import ingest_snapshots

        result = ingest_snapshots(store, args.directory)
    elif args.command == "approve":
        from .admin import approve

        result = approve(store, args.decision_id, args.expires_at)
    elif args.command == "review-decision":
        from .admin import review_decision

        result=review_decision(store,args.decision_id,args.action,args.reason)
    elif args.command == "review-history":
        result=store.query("MATCH (r:ReviewRecord {repo_id:$repo})-[:REVIEWS]->"
            "(d:Decision {uid:$id,repo_id:$repo}) RETURN r.uid AS uid,r.actor AS reviewer,"
            "r.at AS at,r.action AS action,r.reason AS reason,r.reviewed_text AS reviewed_text,"
            "r.source_uids AS source_uids,r.subject_uids AS subject_uids,r.revision AS revision "
            "ORDER BY at,uid LIMIT 100", {"repo":store.cfg.repo_id,"id":args.decision_id})
    elif args.command == "inspect":
        from .services import Services

        result = Services(store).trace_decision(decision_id=args.decision_id)
    else:
        result = store.query(
            "MATCH (d:Decision {repo_id:$repo, scope:'org', status:'proposed'}) "
            "RETURN d.uid AS uid LIMIT 100",
            {"repo": store.cfg.repo_id},
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
