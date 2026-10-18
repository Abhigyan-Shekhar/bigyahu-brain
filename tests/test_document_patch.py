"""New/existing Markdown patch transport and exact review boundaries."""

import subprocess

import pytest
from test_documentation import draft

from brain.app import actions, document_patch, document_store, documentation


@pytest.mark.parametrize("path", ["docs/new.md", "docs/existing.md"])
def test_patch_replays_new_or_existing_doc_without_mutating_original(authored, path):
    before = (authored.source / path).read_bytes() if (authored.source / path).exists() else None
    value = draft(authored, proposed_repo_path=path)
    patch = document_patch.prepare(authored.state, value, documentation.validate)
    assert patch["status"] == "awaiting_approval" and patch["replay"] == "exact_bytes"
    assert patch["kind"] == "documentation" and "tests" not in patch
    folder = authored.state.folder(authored.project) / "documentation/patches" / patch["id"]
    assert (folder / "replay" / path).read_bytes() == document_store.content(
        authored.state, value
    ).encode()
    assert (
        (authored.source / path).read_bytes() if (authored.source / path).exists() else None
    ) == before
    approved = document_patch.approve(
        authored.state,
        authored.project,
        patch["id"],
        patch["consent_digest"],
        documentation.validate,
    )
    assert approved["status"] == "complete"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=authored.source) == b""


@pytest.mark.parametrize(
    "path",
    [
        "../bad.md",
        "/tmp/bad.md",
        "docs/../bad.md",
        ".github/guide.md",
        ".secrets/a.md",
        "docs/a.py",
        "docs/.private.md",
        "config/config.md",
    ],
)
def test_paths_fail_closed(authored, path):
    with pytest.raises(ValueError):
        document_patch.validate_path(authored.source, path)


def test_readme_requires_explicit_user_choice_and_case_collisions_are_rejected(authored):
    with pytest.raises(ValueError):
        document_patch.validate_path(authored.source, "README.md")
    assert document_patch.validate_path(authored.source, "README.md", explicit=True) == "README.md"
    with pytest.raises(ValueError, match="case collision"):
        document_patch.validate_path(authored.source, "docs/EXISTING.md")


def test_symlink_path_cannot_escape_docs(authored, tmp_path):
    (authored.source / "docs/link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        document_patch.validate_path(authored.source, "docs/link/x.md")


@pytest.mark.parametrize("change", ["patch", "document", "revision"])
def test_approval_binds_patch_content_document_and_revision(authored, change):
    value = draft(authored)
    patch = document_patch.prepare(authored.state, value, documentation.validate)
    if change == "patch":
        authored.state.update(patch["id"], patch=patch["patch"] + "Unreviewed")
    if change == "document":
        authored.state.update(value["id"], title="Unreviewed title")
    if change == "revision":
        authored.current["sha"] = "0" * 40
    with pytest.raises(ValueError):
        document_patch.approve(
            authored.state,
            authored.project,
            patch["id"],
            patch["consent_digest"],
            documentation.validate,
        )


def test_normal_code_plan_still_requires_python_test_selection(authored):
    with pytest.raises(ValueError, match="test selections"):
        actions.validate_plan(
            {"summary": "Fix code", "files": ["queue.py"], "steps": ["Fix"], "tests": []},
            authored.source,
        )
