import argparse
import json

from .config import load_config
from .graph import GraphStore


def main():
    parser = argparse.ArgumentParser(description="Company Brain operator utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    sub.add_parser("ingest-snapshots").add_argument("directory")
    sub.add_parser("list-proposals")
    for command in ("inspect", "approve"):
        sub.add_parser(command).add_argument("decision_id")
    args = parser.parse_args()
    store = GraphStore(load_config())
    if args.command == "sync":
        from .ingest.sync import sync

        result = sync(store)
    elif args.command == "ingest-snapshots":
        from .ingest.snapshots import ingest_snapshots

        result = ingest_snapshots(store, args.directory)
    elif args.command == "approve":
        from .admin import approve

        result = approve(store, args.decision_id)
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
