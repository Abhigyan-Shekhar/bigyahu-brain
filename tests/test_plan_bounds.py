"""Executable plans and displayed drafts share the planner's declared limits."""

import pytest

from brain.app import actions


def plan():
    return {
        "summary": "Recover ingestion after restart",
        "steps": [f"Recovery step {i}" for i in range(13)],
        "files": ["backend/app/ingestion.py", "backend/migrations/001_recovery.sql"],
        "tests": [{"runner": "unittest", "path": "backend/test_ingestion_recovery.py"}],
    }


def test_thirteen_step_migration_plan_is_preserved_and_validated(tmp_path):
    candidate = plan()
    validated = actions.validate_plan(candidate, tmp_path)
    draft = actions.draft_plan("Recover ingestion", {"plan": candidate})
    assert validated["steps"] == draft["steps"] == candidate["steps"]
    assert validated["files"] == candidate["files"]
    assert validated["commands"] == [
        ["python", "-m", "unittest", "backend/test_ingestion_recovery.py", "-v"]
    ]
    assert "commands" not in draft and "plan_digest" not in draft


def test_schema_and_validator_agree_on_step_limit(tmp_path):
    schema = actions.PLAN_SCHEMA["properties"]["plan"]["anyOf"][1]["properties"]
    assert schema["steps"]["maxItems"] == actions.MAX_PLAN_STEPS
    assert schema["steps"]["items"]["maxLength"] == actions.MAX_STEP_CHARS
    candidate = plan()
    candidate["steps"] = ["step"] * actions.MAX_PLAN_STEPS
    actions.validate_plan(candidate, tmp_path)
    candidate["steps"].append("excess")
    with pytest.raises(ValueError, match="21 steps; select 1 to 20"):
        actions.validate_plan(candidate, tmp_path)


@pytest.mark.parametrize("step", ["", "   ", None, "x" * 2001])
def test_step_error_identifies_the_invalid_step(tmp_path, step):
    candidate = plan()
    candidate["steps"][5] = step
    with pytest.raises(ValueError, match="Plan step 6"):
        actions.validate_plan(candidate, tmp_path)


def test_aggregate_limit_still_bounds_review_input(tmp_path):
    candidate = plan()
    candidate["steps"] = ["x" * 2000] * 11
    with pytest.raises(ValueError, match="20000 characters in total"):
        actions.validate_plan(candidate, tmp_path)


@pytest.mark.parametrize(
    "path", ["backend/migration.sql (new)", "../migration.sql", ".env", "script.sh"]
)
def test_file_scope_still_rejects_annotations_escape_and_unsupported_files(tmp_path, path):
    candidate = plan()
    candidate["files"] = [path]
    with pytest.raises(ValueError):
        actions.validate_plan(candidate, tmp_path)


def test_npm_sandbox_launcher_resolves_node_without_expanding_child_path(tmp_path, monkeypatch):
    from brain.app import test_sandbox

    cli = tmp_path / "codex.js"
    cli.write_text("#!/usr/bin/env node\n// fixture\n")
    node = tmp_path / "node"
    node.touch()
    monkeypatch.setattr(
        test_sandbox.shutil, "which", lambda name: str(cli if name == "codex" else node)
    )
    command = test_sandbox.sandbox_command(
        tmp_path, tmp_path / "scratch", ["python", "-m", "unittest"]
    )
    assert command[:3] == [str(node), str(cli), "sandbox"]
    assert test_sandbox.test_environment(tmp_path, tmp_path / "scratch")["PATH"] == "/usr/bin:/bin"
    assert "network.enabled=false" in " ".join(command)


def test_npm_sandbox_launcher_reports_missing_node(tmp_path, monkeypatch):
    from brain.app import test_sandbox

    cli = tmp_path / "codex.js"
    cli.write_text("#!/usr/bin/env node\n")
    monkeypatch.setattr(
        test_sandbox.shutil, "which", lambda name: str(cli) if name == "codex" else None
    )
    with pytest.raises(ValueError, match="requires Node.js"):
        test_sandbox.sandbox_command(tmp_path, tmp_path / "scratch", ["python", "-m", "unittest"])
