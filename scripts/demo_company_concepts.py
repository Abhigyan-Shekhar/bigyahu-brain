"""Real model extraction and agent use through a named concept, with no direct company citation.

Runs only on synthetic, disposable data. Both extraction calls and the guided
coding run consume explicitly selected Codex model usage; raw evidence stays local.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import yaml
from validate_memory_foundation import ROOT, engine
from verify_three_brain import verify

from brain.config import Config, load_config
from brain.conversation import ingest_conversation
from brain.graph import GraphStore
from brain.ingest.concepts import annotate_concepts, concept_key
from brain.ingest.documents import ingest_documents
from brain.ingest.graphify import ingest_graphify
from brain.ingest.sync import sync
from brain.memory import Identity, Memory, canonical, digest
from brain.memory_graph import MemoryGraph
from brain.memory_ingest import share_memory

POLICY = (
    "# Runtime policy\nThe backoff envelope defines the runtime team retry policy.\n"
    "`retry.delay_ms` must return min(base_ms * 2 ** attempt, 800).\n"
    "Reject negative attempts and negative base_ms with ValueError.\n"
    "Return an integer, including attempt zero and base_ms zero.\n"
)


def snapshot_hashes(run):
    """Seal local fixture inputs, not raw agent traces or mutable engine logs."""
    files = [
        run / name
        for name in (
            "engine/brain.rdb",
            "memory.db",
            "brain.local.yaml",
            "fixture.json",
            "operator-preflight.json",
            "selected-document-concepts.json",
        )
    ]
    files.extend(p for p in (run / "checkout").rglob("*") if p.is_file())
    files.extend(p for p in (run / "engine/appendonlydir").rglob("*") if p.is_file())
    if any(p.is_symlink() for p in (run / "checkout").rglob("*")):
        raise ValueError("Prepared fixture must not contain symlinks")
    return {
        str(p.relative_to(run)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)
    }


def seal_prepared(run):
    manifest = {"format": "concept-demo-prepared/1", "files": snapshot_hashes(run)}
    (run / "prepared.json").write_text(canonical(manifest), encoding="utf-8")
    return manifest


def validate_prepared(run):
    manifest = json.loads((run / "prepared.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "concept-demo-prepared/1" or manifest.get(
        "files"
    ) != snapshot_hashes(run):
        raise ValueError(
            "Prepared fixture changed; prepare and validate it again before presenting"
        )
    return manifest


def check_view(view):
    assert view["status"] == "ok", view["status"]
    assert any(e["relation"] == "MATCHES_MENTION" for e in view["edges"])
    assert not any(e["relation"] in {"VERIFIED_SOURCE", "RESOLVES_TO"} for e in view["edges"])
    assert not any(n["kind"] == "CompanySymbol" for n in view["nodes"])


def restore_prepared(prepared, run, port):
    """Copy the sealed fixture; no ingestion, extraction or review at presentation time."""
    validate_prepared(prepared)
    shutil.copytree(prepared / "checkout", run / "checkout")
    for name in (
        "memory.db",
        "fixture.json",
        "selected-document-concepts.json",
        "operator-preflight.json",
    ):
        shutil.copyfile(prepared / name, run / name)
    values = yaml.safe_load((prepared / "brain.local.yaml").read_text())
    values.update(repo_root=str(run / "checkout"), memory_db=str(run / "memory.db"), port=port)
    config = run / "brain.local.yaml"
    config.write_text(yaml.safe_dump(values))
    cfg = load_config(config)
    store = GraphStore(cfg)
    sha = json.loads((run / "fixture.json").read_text())["revision"]
    from brain.ingest.git_parser import clean, revision

    if not clean(cfg.repo_root) or revision(cfg.repo_root) != sha:
        raise ValueError("Prepared checkout must remain clean at the indexed revision")
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, cfg.principal))
    try:
        view = MemoryGraph(memory, store).read(
            ["private:alice", "team:runtime", "company"], include_company=True
        )
        check_view(view)
        if canonical(view) != canonical(json.loads((run / "operator-preflight.json").read_text())):
            raise ValueError("Restored graph differs from the validated preparation")
    finally:
        memory.close()
    (run / "preparation.json").write_text(
        canonical(
            {
                "manifest_digest": digest(canonical(validate_prepared(prepared))),
                "extraction_during_presentation": False,
            }
        )
    )
    return cfg.repo_root, sha, config


def setup(run, port, model):
    work = run / "checkout"
    work.mkdir()
    (work / "retry.py").write_text(
        "def delay_ms(attempt, base_ms=10):\n    return base_ms\n", encoding="utf-8"
    )
    (work / "policy.md").write_text(POLICY, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(work),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-qm",
            "Synthetic named concept fixture",
        ],
        check=True,
    )
    sha = subprocess.check_output(["git", "-C", str(work), "rev-parse", "HEAD"], text=True).strip()
    cfg = Config(
        work,
        "fixture:concept-agent",
        "https://github.com/example/concept-agent",
        "alice",
        port=port,
        tenant_id="concept_agent_fixture",
        memory_db=str(run / "memory.db"),
        memory_graph_enabled=True,
    )
    store = GraphStore(cfg)
    sync(store)
    ingest_documents(store, ["policy.md"])
    graphify = ingest_graphify(store, ["retry.py"])
    document = store.query(
        "MATCH (d:Document {repo_id:$repo,source_kind:'repository_document',current:true}) RETURN d.uid AS uid",
        {"repo": cfg.repo_id},
    )[0]
    print("Extracting company document concepts with the selected model", flush=True)
    extraction = annotate_concepts(store, [document["uid"]], model)
    mention_names = store.query(
        "MATCH (c:ConceptMention {repo_id:$repo,current:true}) RETURN c.name AS name",
        {"repo": cfg.repo_id},
    )
    (run / "selected-document-concepts.json").write_text(json.dumps(mention_names, indent=2))
    assert "backoff envelope" in {concept_key(n["name"]) for n in mention_names}, mention_names
    memory = Memory(cfg.memory_db, Identity(cfg.tenant_id, "alice"))
    with memory.db:
        for brain in ("team:runtime", "company"):
            memory.db.execute(
                "INSERT INTO grants VALUES(?,?,?,?)", (cfg.tenant_id, "alice", brain, "reviewer")
            )
    text = "Decision: follow the backoff envelope for retry timing."
    payload = {
        "format": "conversation/1",
        "session": "synthetic-named-concept",
        "turns": [{"id": "u1", "role": "user", "text": text}],
    }
    print("Extracting the consented personal decision and literal entity", flush=True)
    imported = ingest_conversation(
        memory, payload, digest(canonical(payload)), semantic_model=model
    )
    assert imported["items"], "No durable synthetic decision selected"
    for item in imported["items"]:
        memory.review(
            "private:alice", item["uid"], "accept", item["hash"], "Synthetic fixture only"
        )
        for brain in ("team:runtime", "company"):
            shared = share_memory(memory, item["uid"], item["hash"], brain)
            memory.review(brain, shared["uid"], "accept", shared["hash"], "Synthetic fixture only")
    other = Memory(cfg.memory_db, Identity(cfg.tenant_id, "bob"))
    with other.db:
        hidden = other.put(
            "private:bob",
            "HIDDEN_THREE_BRAIN_CANARY",
            [{"uri": "urn:synthetic:private", "digest": digest("private")}],
            uid="hidden",
        )
    other.review("private:bob", hidden["uid"], "accept", hidden["hash"], "Synthetic fixture only")
    other.close()
    projection = MemoryGraph(memory, store)
    for brain in ("private:alice", "team:runtime", "company"):
        projection.sync(brain, include_company=True)
    view = projection.read(["private:alice", "team:runtime", "company"], include_company=True)
    check_view(view)
    (run / "operator-preflight.json").write_text(json.dumps(view, indent=2))
    memory.close()
    values = asdict(cfg)
    values["repo_root"] = str(values["repo_root"])
    config = run / "brain.local.yaml"
    config.write_text(yaml.safe_dump(values))
    (run / "fixture.json").write_text(
        json.dumps(
            {"revision": sha, "graphify": graphify, "concept_extraction": extraction}, indent=2
        )
    )
    return work, sha, config


def report_for(run):
    report = verify(run, policy=POLICY, company_relation="MATCHES_MENTION")
    report.update(
        scope="guided_synthetic_named_concept_agent_demonstration",
        concept_link_without_shared_company_citation=True,
        no_explicit_code_identifier_in_personal_memory=True,
        actual_model_document_and_conversation_extraction=True,
    )
    fixture = json.loads((run / "fixture.json").read_text())
    graph = json.loads((run / "operator-preflight.json").read_text())
    assert not any(e["relation"] in {"VERIFIED_SOURCE", "RESOLVES_TO"} for e in graph["edges"])
    assert not any(n["kind"] == "CompanySymbol" for n in graph["nodes"])
    report["concept_extraction"] = fixture["concept_extraction"]
    report["matched_concept_labels"] = sorted(
        {n["name"] for n in graph["nodes"] if n["kind"] == "CompanyConceptMention"}
    )
    report["selected_document_concept_labels"] = [
        n["name"] for n in json.loads((run / "selected-document-concepts.json").read_text())
    ]
    if (run / "preparation.json").exists():
        report["preparation"] = json.loads((run / "preparation.json").read_text())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--prepare-only",
        action="store_true",
        help="Extract and validate once, then seal a reusable local fixture",
    )
    mode.add_argument(
        "--prepared-run", type=Path, help="Present a sealed preparation without extraction calls"
    )
    mode.add_argument("--verify-run", type=Path, help="Recheck a retained run without model calls")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.verify_run:
        report = report_for(args.verify_run)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print("Retained run reverified without model calls")
        return
    if not args.model:
        parser.error("A fresh run requires an explicit --model")
    runtime = ROOT / "data/validation"
    runtime.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="concept-agent-", dir=runtime))
    print("Local evidence directory: " + str(run), flush=True)
    if args.prepared_run:
        args.prepared_run = args.prepared_run.resolve()
        validate_prepared(args.prepared_run)
    seed = args.prepared_run / "engine" if args.prepared_run else None
    with engine(run / "engine", seed=seed) as port:
        if args.prepared_run:
            work, sha, config = restore_prepared(args.prepared_run, run, port)
        else:
            work, sha, config = setup(run, port, args.model)
        if not args.prepare_only:
            run_agent(run, work, sha, config, args.model)
    if args.prepare_only:
        # The owner has stopped with SAVE, so persistent bytes are ready to seal.
        manifest = seal_prepared(run)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"prepared_run": str(run), **manifest}, indent=2) + "\n")
        print("Validated preparation sealed at: " + str(run))
        return
    report = report_for(run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "scope",
                    "independent_oracle_cases",
                    "agent_test_count",
                    "concept_link_without_shared_company_citation",
                )
            },
            indent=2,
        )
    )
    print("Evidence retained at: " + str(run))


def run_agent(run, work, sha, config, model):
    task = run / "task.txt"
    task.write_text(
        "Fix retry.delay_ms to match the backoff envelope. Add and run regression tests. Start with my private memory, then use memory_graph to inspect private:alice, team:runtime and company with company evidence included. Follow the named concept to its cited company document before editing and cite the checked policy in your final answer. This association is advisory evidence, not identity or approved constraints.\n"
    )
    instructions = run / "instructions.txt"
    instructions.write_text(
        "Use the configured Company Brain MCP tools. Do not inspect the backend catalog/config/database directly, do not request another private brain, and do not modify policy.md. You may inspect/edit this synthetic checkout and run tests using python3. No external messages or network.\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_codex_agent.py"),
            "--work",
            str(work),
            "--out",
            str(run / "agent"),
            "--task",
            str(task),
            "--instructions",
            str(instructions),
            "--model",
            model,
            "--reasoning",
            "high",
            "--revision",
            sha,
            "--brain-config",
            str(config),
            "--brain-python",
            sys.executable,
            "--brain-src",
            str(ROOT / "src"),
            "--memory-graph",
            "--timeout",
            "600",
        ],
        check=False,
    )
    assert result.returncode == 0, "Agent run failed; raw evidence retained"


if __name__ == "__main__":
    main()
