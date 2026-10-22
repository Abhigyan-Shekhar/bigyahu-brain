import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastmcp import Client

from brain.config import Config, load_config
from brain.graph import GraphUnavailable
from brain.ingest.git_parser import revision
from brain.mcp_server import create_server
from brain.services import Services
from brain.setup import initialize

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_codex", ROOT / "scripts/install_codex.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "x.py").write_text("def target(): pass\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.com", "commit", "-qm", "fixture",
    ], check=True)
    return root


def test_init_roundtrip_and_no_overwrite(checkout, tmp_path):
    destination = tmp_path / "brain.yaml"
    cfg, path = initialize(
        checkout, destination, "github.com/example/project", "operator",
        repo_url="https://github.com/example/project",
    )
    assert load_config(path) == cfg
    assert cfg.repo_root == checkout
    assert cfg.repo_url == "https://github.com/example/project"
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        initialize(checkout, destination, "different", "operator")
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="gitignored"):
        initialize(checkout, checkout / "brain.yaml", "example", "operator")
    assert not (checkout / "brain.yaml").exists()


@pytest.mark.parametrize("state,dirty,warning", [
    ({"sha": "current", "syncing": False}, False, None),
    ({"sha": "old", "syncing": False}, False, "stale_index"),
    ({"sha": "current", "syncing": False}, True, "stale_index"),
    ({"sha": "current", "syncing": True}, False, "sync_in_progress"),
    ({"sha": None, "syncing": True}, False, "repository_not_indexed"),
    (None, False, "graph_unavailable"),
])
@pytest.mark.asyncio
async def test_status_over_mcp(checkout, state, dirty, warning):
    sha = revision(checkout)
    if state and state["sha"] == "current":
        state = {**state, "sha": sha}
    if dirty:
        (checkout / "x.py").write_text("def target(): return 1\n")
    store = Mock(cfg=Config(checkout, "fixture"))
    if state is None:
        store.revision.side_effect = GraphUnavailable("offline")
    else:
        store.revision.return_value = state
    async with Client(create_server(Services(store))) as client:
        data = (await client.call_tool("repository_status", {})).data
    assert data["repo_root"] == str(checkout)
    assert data["local_revision"] == sha
    assert data["working_tree_dirty"] is dirty
    if warning:
        assert warning in data["warnings"]
        assert data["status"] != "ok"
    else:
        assert data["status"] == "ok"


def test_skill_replacement_backed_up_and_idempotent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("new")
    target = tmp_path / "codex/skills/company-brain"
    installer.install_skill(source, target)
    installer.install_skill(source, target)
    assert not (tmp_path / "codex/skill-backups").exists()
    (target / "SKILL.md").write_text("custom")
    with pytest.raises(ValueError, match="Different skill"):
        installer.install_skill(source, target)
    installer.install_skill(source, target, force=True)
    assert (target / "SKILL.md").read_text() == "new"
    backups = list((tmp_path / "codex/skill-backups").rglob("SKILL.md"))
    assert len(backups) == 1 and backups[0].read_text() == "custom"


def test_installer_dry_run_and_invalid_config_do_not_write(tmp_path):
    home = tmp_path / "codex"
    installer.main(["--skill-only", "--dry-run", "--codex-home", str(home)])
    assert not home.exists()
    with pytest.raises(SystemExit):
        installer.main(["--config", str(tmp_path / "missing"), "--codex-home", str(home)])
    assert not home.exists()


def test_fresh_codex_home_registration_and_conflict_guard(checkout, tmp_path, monkeypatch):
    config = tmp_path / "brain.yaml"
    initialize(checkout, config, "fixture", "operator")
    home = tmp_path / "codex"
    monkeypatch.setattr(installer.shutil, "which", lambda _: "/fake/codex")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if "get" in command:
            return subprocess.CompletedProcess(command, 0, stdout='{"transport": {}, "enabled": true}')
        assert home.is_dir()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    installer.main(["--config", str(config), "--codex-home", str(home)])
    assert len(calls) == 1  # A new home cannot have an existing MCP entry.
    command, kwargs = calls[0]
    assert command[:4] == ["/fake/codex", "mcp", "add", "company-brain"]
    assert kwargs["env"]["CODEX_HOME"] == str(home)
    assert "BRAIN_CONFIG=" + str(config) in command
    target = home / "skills/company-brain"
    assert installer.same_tree(ROOT / "skills/company-brain", target)
    with pytest.raises(SystemExit):
        installer.main(["--config", str(config), "--codex-home", str(home)])
    assert len(calls) == 2 and "get" in calls[-1][0]
    assert installer.same_tree(ROOT / "skills/company-brain", target)


def test_init_cli_without_brain_config(checkout, tmp_path, monkeypatch, capsys):
    from brain.__main__ import main

    monkeypatch.delenv("BRAIN_CONFIG", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "brain", "init", "--repo", str(checkout), "--config", str(tmp_path / "brain.yaml"),
        "--repo-id", "fixture", "--principal", "operator",
    ])
    main()
    assert '"indexed": false' in capsys.readouterr().out


def test_registry_installer_uses_manifest_without_single_config(checkout, tmp_path, monkeypatch):
    from brain.registry import register_repository

    config = tmp_path / "brain.yaml"
    initialize(checkout, config, "fixture", "operator")
    registry = tmp_path / "registry.json"
    register_repository(registry, config)
    home = tmp_path / "codex"
    monkeypatch.setattr(installer.shutil, "which", lambda _: "/fake/codex")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    installer.main(["--registry", str(registry), "--codex-home", str(home)])
    assert len(calls) == 1
    assert "BRAIN_REGISTRY=" + str(registry) in calls[0]
    assert not any("BRAIN_CONFIG=" in part for part in calls[0])
