"""Offline portability and preflight regression checks; these do not test Browser UI."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from brain.ingest.snapshots import read_snapshot

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("crlf", [False, True])
def test_snapshot_line_endings_preserve_integrity(tmp_path, crlf):
    fixture = ROOT / "tests/fixtures/urllib3-history"
    raw = (fixture / "work.json").read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "manifest.json").write_bytes((fixture / "manifest.json").read_bytes())
    (tmp_path / "work.json").write_bytes(raw.replace(b"\n", b"\r\n") if crlf else raw)
    assert read_snapshot(tmp_path) == read_snapshot(fixture)
    (tmp_path / "work.json").write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="differs from manifest"):
        read_snapshot(tmp_path)


def test_fixture_failure_precedes_database_access(tmp_path, monkeypatch):
    prepare = script("prepare_browser_demo")
    driver = Mock()
    monkeypatch.setattr(prepare, "FalkorDB", driver)
    monkeypatch.setattr(prepare, "read_snapshot", Mock(side_effect=ValueError("bad fixture")))
    with pytest.raises(ValueError, match="bad fixture"):
        prepare.build(tmp_path, 6379, tmp_path / "output")
    driver.assert_not_called()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("port", [6379, 6390, 16379])
def test_any_valid_port_still_refuses_existing_graphs(tmp_path, monkeypatch, port):
    prepare = script("prepare_browser_demo")
    driver = Mock()
    driver.return_value.list_graphs.return_value = ["existing_graph"]
    monkeypatch.setattr(prepare, "FalkorDB", driver)
    monkeypatch.setattr(prepare, "revision", lambda _: prepare.SHA)
    monkeypatch.setattr(prepare, "clean", lambda _: True)
    with pytest.raises(ValueError, match="existing data is never overwritten"):
        prepare.build(tmp_path, port, tmp_path / "output")
    assert driver.call_args.kwargs["port"] == port
    assert not (tmp_path / "output").exists()


def test_lite_help_without_loading_native_dependencies():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run_lite.py"), "--help"],
                            capture_output=True, text=True, check=True)
    assert "--db" in result.stdout


def test_windows_lite_explains_docker_alternative(tmp_path, monkeypatch, capsys):
    lite = script("run_lite")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["run_lite.py", "--db", str(tmp_path / "brain.rdb")])
    with pytest.raises(SystemExit) as error:
        lite.main()
    assert error.value.code == 2
    assert "Docker Desktop Linux containers" in capsys.readouterr().err
