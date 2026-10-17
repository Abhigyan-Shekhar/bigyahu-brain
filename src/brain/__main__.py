import argparse
import json

from .config import load_config
from .graph import GraphStore


def main():
    parser = argparse.ArgumentParser(description="Company Brain operator utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    sub.add_parser("health")
    sub.add_parser("ingest-snapshots").add_argument("directory")
    sub.add_parser("ingest-docs").add_argument("paths", nargs="*")
    sub.add_parser("retire-docs").add_argument("paths", nargs="+")
    github = sub.add_parser("sync-github")
    github.add_argument("--output", required=True)
    github.add_argument("--reconcile", action="store_true")
    sub.add_parser("list-proposals")
    for command in ("inspect", "approve"):
        command_parser=sub.add_parser(command)
        command_parser.add_argument("decision_id")
        if command=="approve":
            command_parser.add_argument("--expires-at",default="")
    review=sub.add_parser("review-decision")
    review.add_argument("decision_id")
    review.add_argument("--action",choices=["reject","expire","rollback"],required=True)
    review.add_argument("--reason",required=True)
    args = parser.parse_args()
    store = GraphStore(load_config())
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
