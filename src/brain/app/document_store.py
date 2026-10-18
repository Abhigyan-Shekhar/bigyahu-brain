"""Immutable Markdown artifacts and exact-content local review transitions."""

import re
from datetime import UTC, datetime

from ..memory import canonical, digest

KINDS = {"architecture", "runbook", "incident", "adr", "api_guide", "change_summary", "custom"}
MAX_BYTES = 60 * 1024


def now():
    return datetime.now(UTC).isoformat()


def markdown_check(text):
    if not isinstance(text, str) or not text.strip() or len(text.encode()) > MAX_BYTES:
        raise ValueError("Markdown must contain 1–61440 UTF-8 bytes")
    if "\0" in text or re.search(
        r"(?<!\\)<\s*(?:/?[A-Za-z]|!--)|(?<!\\)!\[|\]\(\s*(?:javascript|data|file):",
        text,
        re.IGNORECASE,
    ):
        raise ValueError("HTML, embedded images and unsafe links are not allowed")
    if re.search(
        r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|-----BEGIN .*PRIVATE KEY-----)",
        text,
    ):
        raise ValueError("Credential-shaped content cannot be published")
    return text


def artifact(state, project, markdown):
    markdown_check(markdown)
    folder = state.folder(project) / "documentation" / "blobs"
    folder.mkdir(parents=True, exist_ok=True)
    uid = digest(markdown)
    path = folder / (uid + ".md")
    try:
        with path.open("xb") as stream:
            stream.write(markdown.encode())
    except FileExistsError:
        if path.read_bytes() != markdown.encode():
            raise ValueError("Stored document bytes changed") from None
    return uid


def content(state, document):
    path = (
        state.folder(document["project"])
        / "documentation"
        / "blobs"
        / (document["content_digest"] + ".md")
    )
    value = path.read_bytes().decode("utf-8")
    if digest(value) != document["content_digest"]:
        raise ValueError("Stored document bytes changed")
    return markdown_check(value)


def review_digest(document):
    return digest(
        canonical(
            {
                key: document[key]
                for key in (
                    "project",
                    "kind",
                    "title",
                    "proposed_repo_path",
                    "content_digest",
                    "source_revision",
                    "claims",
                )
            }
        )
    )


def scoped(state, project, uid):
    value = state.get(uid, "documentation_draft")
    if value["project"] != project:
        raise KeyError("Unknown document")
    return value


def approve(state, project, uid, expected_digest, revision, validate):
    value = scoped(state, project, uid)
    if value.get("review_digest") != expected_digest or review_digest(value) != expected_digest:
        raise ValueError("Document changed; review its current content")
    if value["source_revision"] != revision:
        raise ValueError("Document approval revision changed")
    validate(state, value)
    if value["status"] == "approved":
        return value
    if not state.transition(
        uid,
        {"status": "draft", "review_digest": expected_digest},
        status="approved",
        approved_at=now(),
        binding=False,
    ):
        raise ValueError("Document is not available for approval")
    return state.get(uid)
