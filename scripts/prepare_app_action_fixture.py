"""Add one explicitly synthetic coding source to a local application for acceptance testing.

Creates a new namespace only; never modifies existing sources, approves actions,
or runs repository code. Use with the operator's existing local app config/data.
"""

import argparse
import subprocess

from brain.app.state import State
from brain.config import load_config
from brain.graph import GraphStore
from brain.ingest.documents import ingest_documents
from brain.ingest.sync import sync

POLICY = (
    "# Retry policy\n"
    "`retry.delay_ms` returns min(base_ms * 2 ** attempt, 800).\n"
    "Reject negative attempts or negative base_ms with ValueError.\n"
    "Return an integer, including attempt zero and base_ms zero.\n"
    "This source is a synthetic coding acceptance fixture, not a real hosted repository.\n"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    state = State(args.data, load_config(args.config), args.model, recover=False)
    project = state.create(
        "repository",
        url="https://github.com/example/company-brain-action-fixture",
        name="Synthetic coding acceptance fixture",
        status="queued",
        stage="Preparing synthetic fixture",
        warnings=[
            "Synthetic fixture. Source citations refer to local indexed bytes; the example GitHub URL is not a hosted repository."
        ],
    )
    folder = state.folder(project["id"])
    folder.mkdir()
    work = folder / "checkout"
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
            "Introduce documented retry helper",
        ],
        check=True,
    )
    cfg = state.configure(project["id"], project["url"])
    store = GraphStore(cfg)
    result = sync(store)
    ingest_documents(store, ["policy.md"])
    state.update(
        project["id"],
        status="ready",
        stage="Synthetic fixture ready",
        revision=result["revision"],
        indexing=result,
    )
    print("Synthetic source ready: " + project["id"])


if __name__ == "__main__":
    main()
