"""Review-bound Markdown patch export; the indexed checkout is never edited."""

import re
import subprocess
from pathlib import Path

from ..graph import GraphStore
from ..ingest.git_parser import git
from ..memory import canonical, digest
from . import document_store
from .action_mcp import read_file, target, write_file
from .actions import clone_at, patch_for
from .evidence import ready


def consent_digest(value):
    return digest(
        canonical(
            {
                key: value[key]
                for key in (
                    "project",
                    "document",
                    "target",
                    "source_revision",
                    "document_digest",
                    "original_digest",
                    "patch",
                )
            }
        )
    )


def validate_path(root, path, *, explicit=False):
    if (
        not isinstance(path, str)
        or len(path) > 180
        or not re.fullmatch(r"[A-Za-z0-9_./-]+\.md", path)
    ):
        raise ValueError("Choose a literal Markdown repository path")
    if not path.startswith("docs/") and not explicit:
        raise ValueError("Use docs/**/*.md, or explicitly choose another Markdown file")
    if Path(path).parts[0].casefold() in {"config", "secrets"}:
        raise ValueError("Configuration and secrets are outside documentation scope")
    file = target(root, path)
    if any(part.endswith((".", " ")) for part in Path(path).parts):
        raise ValueError("Ambiguous documentation path")
    for name in git(root, "ls-files", "-z").split("\0"):
        if name and name.casefold() == path.casefold() and name != path:
            raise ValueError("Documentation path has a case collision")
        for proposed, existing in zip(Path(path).parts[:-1], Path(name).parts[:-1]):
            if proposed.casefold() != existing.casefold():
                break
            if proposed != existing:
                raise ValueError("Documentation directory has a case collision")
    if file.exists() and (not file.is_file() or file.stat().st_size > 100000):
        raise ValueError("Existing documentation exceeds text limits")
    return path


def prepare(state, document, validate):
    validate(state, document)
    cfg = state.config(document["project"])
    path = validate_path(
        cfg.repo_root, document["proposed_repo_path"], explicit=document["explicit_path"]
    )
    text = document_store.content(state, document)
    old = read_file(cfg.repo_root, path)
    value = state.create(
        "documentation_patch",
        document["project"],
        project=document["project"],
        document=document["id"],
        status="preparing",
        kind="documentation",
        target=path,
        source_revision=document["source_revision"],
        document_digest=document["review_digest"],
        original_digest=old["digest"],
    )
    folder = state.folder(document["project"]) / "documentation" / "patches" / value["id"]
    folder.mkdir(parents=True)
    try:
        work, replay = folder / "checkout", folder / "replay"
        clone_at(cfg.repo_root, work, document["source_revision"])
        write_file(work, [path], path, text, read_file(work, path)["digest"])
        names, patch = patch_for(work, [path])
        clone_at(cfg.repo_root, replay, document["source_revision"])
        subprocess.run(
            ["git", "apply", "-"],
            cwd=replay,
            input=patch.encode(),
            capture_output=True,
            check=True,
            timeout=30,
        )
        if (replay / path).read_bytes() != (work / path).read_bytes():
            raise ValueError("Documentation patch does not replay exact bytes")
        validate(state, document)
        consent = consent_digest({**value, "patch": patch})
        return state.update(
            value["id"],
            status="awaiting_approval",
            patch=patch,
            changed_files=names,
            consent_digest=consent,
            replay="exact_bytes",
            checks=["bounded_markdown", "source_provenance", "git_apply_byte_comparison"],
            notice="Documentation-only patch. No Python tests were required; no code gate was bypassed. Original checkout unchanged.",
        )
    except Exception:
        state.update(value["id"], status="failed", error="Documentation patch preparation failed")
        raise


def approve(state, project, uid, consent, validate):
    value = state.get(uid, "documentation_patch")
    if value["project"] != project:
        raise KeyError("Unknown patch")
    if consent != value.get("consent_digest") or consent_digest(value) != consent:
        raise ValueError("Patch changed; review again")
    document = document_store.scoped(state, project, value["document"])
    validate(state, document)
    cfg = state.config(project)
    if (
        document["review_digest"] != value["document_digest"]
        or ready(GraphStore(cfg)) != value["source_revision"]
        or read_file(cfg.repo_root, value["target"])["digest"] != value["original_digest"]
    ):
        raise ValueError("Documentation patch is stale")
    if value["status"] == "complete":
        return value
    if not state.transition(
        uid,
        {"status": "awaiting_approval", "consent_digest": consent},
        status="complete",
        approved_at=document_store.now(),
    ):
        raise ValueError("Patch is not available for approval")
    return state.get(uid)
