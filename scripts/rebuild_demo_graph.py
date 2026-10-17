"""Rebuild eligible public inputs; human approval and freeze are explicit phases.

Run with PYTHONPATH=<company-brain>/src. Never invoke approve/supersede from an agent.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from brain.config import load_config
from brain.graph import GraphStore
from brain.ingest.documents import ingest_documents
from brain.ingest.git_parser import clean, revision
from brain.ingest.snapshots import ingest_snapshots
from brain.ingest.sync import sync
from brain.services import Services

PIN = "a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8"
REPO = "experiment:urllib3:5181:eligible"
D1 = (
    "On HTTP 303 redirects, PoolManager.urlopen must discard the request body "
    "and its framing and rewind state. This demo operator rule is grounded in upstream PR #5161."
)
D2 = (
    "In PoolManager.urlopen's HTTP 303 branch, preserve the switch to GET, body=None, "
    "chunked=False, body_pos=None, and removal of body framing headers. "
    "This rule applies only to body-discarding HTTP 303 redirects; it does not prescribe "
    "307/308 upload replay. Demo operator clarification grounded in upstream PR #5161."
)
ROOT = Path(__file__).resolve().parents[1]


def save(directory, name, payload):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    raw = json.dumps(payload, indent=2) + "\n"
    if path.exists() and path.read_text() != raw:
        raise ValueError(f"Refusing to overwrite evidence: {path.name}")
    if not path.exists():
        path.write_text(raw)


def proposal(store, text, sources, subject, supersedes=""):
    found = store.query(
        "MATCH (d:Decision {repo_id:$repo, scope:'org', text:$text}) "
        "RETURN d.uid AS uid ORDER BY uid LIMIT 2",
        {"repo": REPO, "text": text},
    )
    if len(found) > 1:
        raise ValueError("Multiple matching proposals; inspect manually")
    if found:
        return found[0]["uid"]
    result = Services(store).remember(
        text, source_refs=sources, applies_to=[subject], supersedes=supersedes
    )
    if result["status"] != "ok":
        raise ValueError(result)
    return result["decision_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=("prepare", "approve", "supersede", "freeze"), default="prepare"
    )
    args = parser.parse_args()
    store = GraphStore(load_config(args.config.resolve()))
    if store.cfg.repo_id != REPO or store.cfg.repo_url != "https://github.com/urllib3/urllib3":
        parser.error("Requires the eligible public urllib3 namespace")
    if revision(store.cfg.repo_root) != PIN or not clean(store.cfg.repo_root):
        parser.error("Requires a clean checkout at the documented pin")
    output = args.out.resolve()
    if output.is_relative_to(store.cfg.repo_root):
        parser.error("Evidence must stay outside the agent checkout")
    if (output / "corpus.json").exists():
        parser.error("Corpus already frozen: no more mutation phases in this directory")
    work = store.query(
        "MATCH (n {repo_id:$repo}) WHERE n:PR OR n:Issue RETURN n.number AS number", {"repo": REPO}
    )
    if any(n["number"] not in {3780, 5161} for n in work):
        parser.error("Namespace contains excluded work; use a fresh database")
    active = store.query(
        "MATCH (d:Decision {repo_id:$repo, status:'active'}) RETURN d.uid AS uid", {"repo": REPO}
    )
    if args.phase == "prepare":
        if active:
            parser.error("Already approved: do not rebuild a reviewed graph")
        results = {
            "sync": sync(store),
            "snapshots": ingest_snapshots(store, ROOT / "data/sources/urllib3"),
        }
        results["documents"] = ingest_documents(store)
        save(output, "rebuild.json", results)
    if store.revision() != {"sha": PIN, "syncing": False}:
        parser.error("Run prepare first")
    subject = f"{REPO}@{PIN}:src/urllib3/poolmanager.py::PoolManager.urlopen"
    source = REPO + ":pr:5161:source"
    service = Services(store)
    if args.phase != "freeze":
        first = proposal(store, D1, [source], subject)
    else:
        matching = store.query(
            "MATCH (d:Decision {repo_id:$repo, text:$text}) RETURN d.uid AS uid",
            {"repo": REPO, "text": D1},
        )
        if len(matching) != 1:
            parser.error("D-1 is missing or ambiguous")
        first = matching[0]["uid"]
    target = lambda: service.check_change(["src/urllib3/poolmanager.py"], ["PoolManager.urlopen"])
    if args.phase == "prepare":
        before = target()
        if before["must_preserve"]:
            parser.error("Unexpected active constraint before independent approval")
        save(output, "before-approval.json", before)
        save(output, "d1-review.json", service.trace_decision(decision_id=first))
        print(
            json.dumps(
                {
                    "decision_id": first,
                    "status": "proposed",
                    "text": D1,
                    "subject": subject,
                    "source": "https://github.com/urllib3/urllib3/pull/5161",
                    "next": "In a separate human terminal, rerun with --phase approve and BRAIN_OPERATOR_SESSION=1.",
                },
                indent=2,
            )
        )
    elif args.phase == "approve":
        from brain.admin import approve

        approve(store, first)
        after = target()
        if not after["must_preserve"]:
            raise ValueError("Approved constraint did not reach must_preserve")
        save(output, "after-d1-approval.json", after)
        save(output, "d1-approved-trace.json", service.trace_decision(decision_id=first))
        print("D-1 approved and verified. Next: --phase supersede in this human terminal.")
    elif args.phase == "supersede":
        from brain.admin import approve

        old = service.trace_decision(decision_id=first)
        if old["items"][0]["status"] != "active":
            parser.error("Approve D-1 first")
        second = proposal(store, D2, [source], subject, supersedes=first)
        save(
            output,
            "before-supersession.json",
            {"D-1": old, "D-2": service.trace_decision(decision_id=second)},
        )
        approve(store, second)
        save(
            output,
            "after-supersession.json",
            {
                "D-1": service.trace_decision(decision_id=first),
                "D-2": service.trace_decision(decision_id=second),
                "check_change": target(),
            },
        )
        print(
            "Operator lifecycle on real sources: D-1 superseded by narrower D-2; history retained."
        )
    else:
        current = target()
        decisions = store.query(
            "MATCH (d:Decision {repo_id:$repo, scope:'org'}) "
            "RETURN d.uid AS uid, d.text AS text, d.status AS status, "
            "d.approved_revision AS revision, d.approval AS approval",
            {"repo": REPO},
        )
        approved = [d for d in decisions if d["status"] == "active"]
        if (
            len(approved) != 1
            or approved[0]["text"] != D2
            or approved[0]["revision"] != PIN
            or approved[0]["approval"] != "human_approved"
            or not any(d["uid"] == first and d["status"] == "superseded" for d in decisions)
            or not current["must_preserve"]
        ):
            parser.error("Independent D-1 approval and D-2 supersession must precede freeze")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/capture_agent_corpus.py"),
                "--config",
                str(args.config.resolve()),
                "--out",
                str(output / "corpus.json"),
            ],
            check=True,
        )
        corpus = json.loads((output / "corpus.json").read_text())
        oracle = ROOT / "docs/demo/oracle.py"
        save(
            output,
            "frozen-manifest.json",
            {
                "corpus_sha256": corpus["snapshot_sha256"],
                "revision": PIN,
                "active_decision": approved[0]["uid"],
                "oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest(),
                "backend_files": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((ROOT / "src/brain").rglob("*.py"))
                },
                "protocol_sha256": hashlib.sha256(
                    (ROOT / "docs/v5-evaluation-protocol.md").read_bytes()
                ).hexdigest(),
                "input_files": {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                    for name in (
                        "docs/agent-task.txt",
                        "docs/v5-agent-instructions.txt",
                        "scripts/run_codex_agent.py",
                        "scripts/evaluate_agent_run.py",
                        "uv.lock",
                        "data/sources/urllib3/work.json",
                    )
                },
            },
        )
        print("Frozen. Use fresh paired sessions; compare the corpus hash after every pair.")


if __name__ == "__main__":
    main()
