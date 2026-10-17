"""Operator-owned onboarding. Downloaded repositories are data, never executed."""

import os
import re
import subprocess
from pathlib import Path

from ..graph import GraphStore
from ..ingest.documents import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    ingest_documents,
    sections,
)
from ..ingest.git_parser import git
from ..ingest.github_sync import GitHub, sync_github
from ..ingest.sync import sync
from ..memory import digest


def repository_url(url):
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", url
    )
    if not match or any(part in {".", ".."} or part.startswith("-") for part in match.groups()):
        raise ValueError("Enter a public https://github.com/owner/repository URL")
    return "https://github.com/" + "/".join(match.groups())


def clone_public(url, target):
    url = repository_url(url)
    metadata = GitHub().get("repos/" + url.removeprefix("https://github.com/"))
    if metadata.get("private", True) or metadata.get("size", 1_000_000) > 100_000:
        raise ValueError("Select a public repository smaller than 100 MB")
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    result = subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "core.hooksPath=" + os.devnull,
            "clone",
            "--depth",
            "100",
            "--single-branch",
            "--no-checkout",
            "--",
            url + ".git",
            str(target),
        ],
        env=env,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise ValueError("Public repository clone failed; check the URL and network")
    entries = git(target, "ls-tree", "-rlz", "HEAD").split("\0")
    sizes, total = [], 0
    for entry in filter(None, entries):
        header, _path = entry.split("\t", 1)
        mode, kind, _oid, size = header.split()
        if mode in {"120000", "160000"} or kind != "blob":
            raise ValueError("This milestone accepts repositories without symlinks or submodules")
        size = int(size)
        sizes.append(size)
        total += size
        if size > 5_000_000 or total > 50_000_000 or len(sizes) > 5000:
            raise ValueError("Checkout exceeds 5 MB/file, 50 MB total or 5000 files")
    subprocess.run(
        [
            "git",
            "-C",
            str(target),
            "-c",
            "core.hooksPath=" + os.devnull,
            "checkout",
            "--force",
            "HEAD",
        ],
        env=env,
        capture_output=True,
        timeout=60,
        check=True,
    )


class BoundedGitHub(GitHub):
    """Small onboarding batch; never claim partial history as complete."""

    def __init__(self):
        self.requests = 0

    def get(self, path, params=None):
        self.requests += 1
        if self.requests > 100:
            raise ValueError("GitHub onboarding request limit reached")
        result = super().get(path, params)
        if isinstance(result, list) and len(result) > 20:
            raise ValueError("GitHub onboarding accepts at most 20 items per collection")
        return result


def onboard(state, project, history=True):
    try:
        state.update(project, status="running", stage="Cloning public repository")
        folder = state.folder(project)
        folder.mkdir(mode=0o700)
        clone_public(state.get(project)["url"], folder / "checkout")
        cfg = state.configure(project, state.get(project)["url"])
        store = GraphStore(cfg)
        state.update(project, stage="Indexing code and Git history")
        result = sync(store)
        warnings = []
        if history:
            state.update(project, stage="Acquiring GitHub issues and pull requests")
            try:
                sync_github(store, folder / "github-snapshot", api=BoundedGitHub())
            except (ValueError, RuntimeError, OSError, subprocess.SubprocessError):
                if store.revision()["syncing"]:
                    raise ValueError(
                        "GitHub graph refresh interrupted; reconnect this source"
                    ) from None
                warnings.append(
                    "GitHub history unavailable or exceeds this milestone’s limits; code and Git history are indexed."
                )
        state.update(project, stage="Indexing repository documents")
        paths = [
            p
            for p in git(cfg.repo_root, "ls-files", "-z").split("\0")
            if Path(p).suffix.lower() in {".md", ".rst"}
        ]
        if paths:
            # Explicitly report bounded coverage, not silent complete-document claims.
            selected, total = [], 0
            for path in paths:
                size = (cfg.repo_root / path).stat().st_size
                if (
                    size <= MAX_FILE_BYTES
                    and total + size <= MAX_TOTAL_BYTES
                    and len(selected) < MAX_FILES
                ):
                    selected.append(path)
                    total += size
            if selected:
                ingest_documents(store, selected)
            if len(selected) != len(paths):
                warnings.append(
                    "Repository document coverage was bounded to 12 files, 256 KB/file and 1 MB total."
                )
        state.update(
            project,
            status="ready",
            stage="Ready",
            indexing=result,
            revision=store.revision()["sha"],
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001 - background jobs must persist failure states
        # No subprocess output or credentials are exposed in the UI.
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Indexing failed; check local operator logs/configuration and reconnect."
        )
        state.update(project, status="failed", stage="Indexing stopped", error=message[:500])


def upload_document(state, project, filename, text):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,99}\.(?:md|rst)", filename):
        raise ValueError("Upload a Markdown or RST file with a simple filename")
    raw = text.encode("utf-8")
    if not raw or len(raw) > 500_000 or "\0" in text:
        raise ValueError("Upload must contain 1–500000 UTF-8 bytes of text")
    prepared = list(sections(text))
    if not prepared or len(prepared) > 100:
        raise ValueError("Upload exceeds 100 sections")
    cfg = state.config(project)
    store = GraphStore(cfg)
    revision = store.revision()
    if revision["syncing"] or not revision["sha"]:
        raise ValueError("Wait for repository indexing to finish")
    sha = revision["sha"]
    content = digest(text)
    folder = state.folder(project) / "uploads"
    folder.mkdir(exist_ok=True)
    (folder / content).write_bytes(raw)
    for start, end, body in prepared:
        uid = f"{cfg.repo_id}@{sha}:upload:{content}:L{start}-L{end}"
        props = {
            "repo_id": cfg.repo_id,
            "revision": sha,
            "current": True,
            "source_kind": "app_upload",
            "path": filename,
            "line_start": start,
            "line_end": end,
            "digest": digest(body),
            "upload_digest": content,
        }
        store.upsert(
            "Source",
            uid + ":source",
            {
                **props,
                "excerpt": body,
                "uri": f"urn:company-brain:upload:{content}:L{start}-L{end}",
            },
        )
        store.upsert("Document", uid, {**props, "text": body})
        store.edge(uid, "SUPPORTS", uid + ":source")
    return {
        "filename": filename,
        "digest": content,
        "sections": len(prepared),
        "format": "text",
        "binding": False,
    }


def upload_binary(state, project, filename, raw):
    """Parse in a bounded child process and preserve an immutable extraction snapshot."""
    import hashlib
    import json
    import sys
    import tempfile

    from ..memory import canonical

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,99}\.(?:pdf|docx)", filename, re.IGNORECASE):
        raise ValueError("Upload a PDF or DOCX with a simple filename")
    if not raw or len(raw) > 1_400_000:
        raise ValueError("Binary upload exceeds 1.4 MB")
    with tempfile.TemporaryDirectory(prefix="brain-document-") as temp:
        root = Path(temp)
        source, output = root / "input", root / "result.json"
        source.write_bytes(raw)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "brain.ingest.binary_document",
                str(source),
                Path(filename).suffix.lower(),
                str(output),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode or not output.exists() or output.stat().st_size > 2_100_000:
            raise ValueError(
                "Document extraction failed: use a valid text-based PDF (no OCR/encryption) or DOCX within documented bounds"
            )
        extracted = json.loads(output.read_text())
    text = extracted["text"]
    prepared = list(sections(text))
    if not prepared or len(prepared) > 100:
        raise ValueError("Extracted document exceeds 100 sections")
    cfg = state.config(project)
    store = GraphStore(cfg)
    from .evidence import ready

    sha = ready(store)
    content = hashlib.sha256(raw).hexdigest()
    snapshot = {**extracted, "raw_digest": content, "text_digest": digest(text), "version": 1}
    serialized = canonical(snapshot)
    folder = state.folder(project) / "uploads"
    folder.mkdir(exist_ok=True)
    snapshot_digest = digest(serialized)
    # Content-address BOTH original bytes and parser output; runtime changes cannot rewrite old citations.
    (folder / content).write_bytes(raw)
    (folder / snapshot_digest).write_text(serialized, encoding="utf-8")
    sources, docs = [], []
    for start, end, body in prepared:
        uid = f"{cfg.repo_id}@{sha}:binary:{content}:{snapshot_digest}:L{start}-L{end}"
        props = {
            "repo_id": cfg.repo_id,
            "revision": sha,
            "current": True,
            "source_kind": "app_binary_upload",
            "path": filename,
            "line_start": start,
            "line_end": end,
            "digest": digest(body),
            "upload_digest": content,
            "snapshot_digest": snapshot_digest,
            "text_digest": digest(text),
            "format": extracted["format"],
        }
        sources.append(
            {
                "uid": uid + ":source",
                "props": {
                    **props,
                    "excerpt": body,
                    "uri": f"urn:company-brain:upload:{content}:extracted:L{start}-L{end}",
                },
            }
        )
        docs.append({"uid": uid, "props": {**props, "text": body}, "source": uid + ":source"})
    store.query(
        "UNWIND $sources AS item MERGE (s:Source {uid:item.uid}) SET s += item.props WITH count(s) AS loaded UNWIND $docs AS item MERGE (d:Document {uid:item.uid}) SET d += item.props WITH d,item MATCH (s:Source {uid:item.source}) MERGE (d)-[:SUPPORTS]->(s)",
        {"sources": sources, "docs": docs},
    )
    return {
        "filename": filename,
        "digest": content,
        "sections": len(prepared),
        "format": extracted["format"],
        "binding": False,
        "extraction": {k: v for k, v in extracted.items() if k != "text"},
    }
