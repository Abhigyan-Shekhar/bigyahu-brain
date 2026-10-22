import hashlib
import importlib.util
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastmcp import Client

from brain import plugin_server

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_plugin", ROOT / "scripts/build_plugin.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_archive_is_reproducible_and_excludes_local_state(tmp_path):
    first = builder.build_plugin(tmp_path / "first")
    second = builder.build_plugin(tmp_path / "second")
    archive = Path(first["archive"])
    assert archive.read_bytes() == Path(second["archive"]).read_bytes()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == first["sha256"]
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert "company-brain/src/brain/plugin_server.py" in names
        assert "company-brain/skills/company-brain-setup/SKILL.md" in names
        for name in names:
            parts = Path(name).parts
            assert not {".git", ".venv", ".secrets", "data", "tests", "__pycache__"} & set(parts)
            assert not name.endswith((".local.yaml", ".pyc"))
        portable = json.loads(bundle.read("company-brain/mcp.json"))
        legacy = json.loads(bundle.read("company-brain/.codex-plugin/plugin.json"))
        metadata = json.loads(bundle.read("company-brain/plugin.json"))
        onboarding = metadata["extensions"]["com.openai"]["onboardingSkill"]
        assert legacy["extensions"]["com.openai"]["onboardingSkill"] == onboarding
        assert "company-brain/" + onboarding.removeprefix("./") in names
        assert legacy["mcpServers"] == "./mcp.json"
        assert portable["mcpServers"]["company-brain"]["command"] == "uv"
        assert "${PLUGIN_ROOT}" in portable["mcpServers"]["company-brain"]["args"]
    marketplace = Path(first["marketplace"])
    catalog = json.loads((marketplace / ".agents/plugins/marketplace.json").read_text())
    plugin = marketplace / catalog["plugins"][0]["source"]["path"]
    assert (plugin / "plugin.json").is_file()
    with pytest.raises(FileExistsError):
        builder.build_plugin(tmp_path / "first")


def test_configuration_precedence_and_default_home(tmp_path):
    registry, config = tmp_path / "registry.json", tmp_path / "brain.yaml"
    assert plugin_server.plugin_configuration({"BRAIN_REGISTRY": str(registry), "BRAIN_CONFIG": str(config)}) == ("BRAIN_REGISTRY", registry)
    assert plugin_server.plugin_configuration({"BRAIN_CONFIG": str(config)}) == ("BRAIN_CONFIG", config)
    assert plugin_server.plugin_configuration({"CODEX_HOME": str(tmp_path)}) == ("BRAIN_REGISTRY", tmp_path / "company-brain/registry.json")
    cached = tmp_path / "profile/plugins/cache/source/company-brain/0.1.0"
    assert plugin_server.plugin_configuration({}, cached) == ("BRAIN_REGISTRY", tmp_path / "profile/company-brain/registry.json")


@pytest.mark.asyncio
async def test_missing_setup_exposes_only_diagnostic(tmp_path):
    path = tmp_path / "company-brain/registry.json"
    async with Client(plugin_server.create_setup_server("BRAIN_REGISTRY", path, "configuration_missing")) as client:
        assert [t.name for t in await client.list_tools()] == ["setup_status"]
        value = (await client.call_tool("setup_status", {})).data
        assert value["status"] == "setup_required"
        assert value["configuration_path"] == str(path)
    assert not path.exists()


def test_configured_launcher_reuses_existing_server(tmp_path, monkeypatch):
    config = tmp_path / "brain.yaml"
    config.write_text(f"repo_root: {tmp_path.as_posix()}\nrepo_id: fixture\n")
    monkeypatch.delenv("BRAIN_REGISTRY", raising=False)
    monkeypatch.setenv("BRAIN_CONFIG", str(config))
    serve = Mock()
    monkeypatch.setattr("brain.mcp_server.main", serve)
    plugin_server.main()
    serve.assert_called_once_with()


def test_invalid_config_stays_in_setup_without_exposing_contents(tmp_path, monkeypatch):
    config = tmp_path / "invalid.yaml"
    config.write_text("invalid: [PRIVATE_CONFIGURATION_TEXT")
    monkeypatch.delenv("BRAIN_REGISTRY", raising=False)
    monkeypatch.setenv("BRAIN_CONFIG", str(config))
    create_setup = Mock(return_value=Mock())
    monkeypatch.setattr(plugin_server, "create_setup_server", create_setup)
    plugin_server.main()
    assert create_setup.call_args.args == ("BRAIN_CONFIG", config, "configuration_invalid")
    assert "PRIVATE_CONFIGURATION_TEXT" not in str(create_setup.call_args)


def test_manifest_excludes_untracked_files_inside_source_directories(tmp_path):
    source = tmp_path / "source"
    files = json.loads((ROOT / "packaging/company-brain/files.json").read_text())
    for name in (*files, "packaging/company-brain/files.json"):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    # Untracked files alongside the declared inputs must never ship.
    for name in ("src/brain/private-settings.yaml", "src/brain/private.py",
                 "skills/company-brain/private-notes.md"):
        (source / name).write_text("PRIVATE_LOCAL_SENTINEL")
    artifact = builder.build_plugin(tmp_path / "output", root=source)
    with zipfile.ZipFile(artifact["archive"]) as bundle:
        assert all(b"PRIVATE_LOCAL_SENTINEL" not in bundle.read(n) for n in bundle.namelist())
        assert "company-brain/src/brain/private-settings.yaml" not in bundle.namelist()


@pytest.mark.parametrize("name", ["../escape.py", "src/brain/settings.local.yaml", "src/brain/.env"])
def test_manifest_rejects_sensitive_or_escaping_paths(tmp_path, name):
    source = tmp_path / "source"
    (source / "packaging/company-brain").mkdir(parents=True)
    shutil.copyfile(ROOT / "packaging/company-brain/plugin.json", source / "packaging/company-brain/plugin.json")
    shutil.copyfile(ROOT / "pyproject.toml", source / "pyproject.toml")
    (source / "packaging/company-brain/files.json").write_text(json.dumps({name: name}))
    with pytest.raises(ValueError):
        builder.build_plugin(tmp_path / "output", root=source)


@pytest.mark.parametrize("site_path", [".venv/lib/python3.12/site-packages", ".venv/Lib/site-packages"])
def test_wheel_install_retains_owning_profile(tmp_path, monkeypatch, site_path):
    plugin = tmp_path / "profile/plugins/cache/catalog/company-brain/0.1.0"
    monkeypatch.setattr(plugin_server, "__file__", str(plugin / site_path / "brain/plugin_server.py"))
    assert plugin_server.plugin_configuration({}) == (
        "BRAIN_REGISTRY", tmp_path / "profile/company-brain/registry.json",
    )
