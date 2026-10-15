"""Offline transport/security contracts; these do not establish Cloud compatibility."""

import json
from unittest.mock import Mock

import pytest
import yaml
from redis.exceptions import AuthenticationError, ConnectionError

from brain.config import Config, load_config
from brain.graph import GraphStore
from brain.services import Services


def remote(tmp_path, **kwargs):
    return Config(tmp_path, "test/repo", host="unit-test.invalid", tls=True, **kwargs)


def test_driver_receives_verified_tls_and_file_secret(tmp_path, monkeypatch):
    secret = tmp_path / "password"
    secret.write_text("synthetic-secret\n")
    secret.chmod(0o600)
    cfg = remote(tmp_path, port=16379, username="test-user", password_file=str(secret))
    driver = Mock()
    driver.return_value.select_graph.return_value.query.return_value = Mock(
        header=[[1, "value"]], result_set=[[1]]
    )
    monkeypatch.setattr("brain.graph.FalkorDB", driver)
    assert GraphStore(cfg).query("RETURN 1 AS value") == [{"value": 1}]
    options = driver.call_args.kwargs
    assert options["host"] == "unit-test.invalid" and options["port"] == 16379
    assert options["username"] == "test-user" and options["password"] == "synthetic-secret"
    assert options["ssl"] is True
    assert options["ssl_check_hostname"] is True
    assert options["ssl_cert_reqs"] == "required"
    assert "synthetic-secret" not in repr(cfg)


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o666])
def test_world_or_group_readable_secret_rejected(tmp_path, mode):
    secret = tmp_path / "password"
    secret.write_text("synthetic-secret")
    secret.chmod(mode)
    with pytest.raises(ValueError, match="mode"):
        remote(tmp_path, password_file=str(secret)).connection_options()


@pytest.mark.parametrize("contents", ["", "\n", "a" * 16385])
def test_empty_or_oversized_secret_rejected(tmp_path, contents):
    secret = tmp_path / "password"
    secret.write_text(contents)
    secret.chmod(0o600)
    with pytest.raises(ValueError):
        remote(tmp_path, password_file=str(secret)).connection_options()


def test_missing_secret_rejected_before_connect(tmp_path, monkeypatch):
    driver = Mock()
    monkeypatch.setattr("brain.graph.FalkorDB", driver)
    service = Services(GraphStore(remote(tmp_path, password_file=str(tmp_path / "missing"))))
    result = service.get_context("query")
    assert result["status"] == "error"
    driver.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"host": "remote.invalid"},
        {"port": 0},
        {"port": True},
        {"port": "6379"},
        {"tls": "false"},
        {"host": "rediss://user:secret@host"},
        {"password_file": "relative.secret"},
        {"ca_file": "/tmp/ca.pem"},
    ],
)
def test_invalid_connection_configuration(tmp_path, overrides):
    with pytest.raises(ValueError):
        Config(tmp_path, "test/repo", **overrides)


def test_ca_and_remote_yaml_loading(tmp_path):
    path = tmp_path / "cloud.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "repo_root": str(tmp_path),
                "repo_id": "test/repo",
                "host": "unit-test.invalid",
                "port": 16379,
                "tls": True,
                "ca_file": str(tmp_path / "provider.pem"),
            }
        )
    )
    assert load_config(path).connection_options()["ssl_ca_certs"] == str(tmp_path / "provider.pem")


@pytest.mark.parametrize("error", [AuthenticationError, ConnectionError])
def test_transport_failure_redacted_in_tool_response(tmp_path, monkeypatch, error):
    monkeypatch.setattr("brain.graph.FalkorDB", Mock(side_effect=error("synthetic-secret")))
    response = Services(GraphStore(remote(tmp_path))).get_context("query")
    assert response["status"] == "unavailable"
    assert "synthetic-secret" not in json.dumps(response)
    assert "must_preserve" not in response


def test_local_default_compatibility(tmp_path):
    options = Config(tmp_path, "test/repo").connection_options()
    assert options["host"] == "127.0.0.1" and options["port"] == 6379
    assert options["ssl"] is False and "password" not in options


@pytest.mark.asyncio
async def test_all_five_mcp_tools_fail_closed_without_remote_db(tmp_path, monkeypatch):
    from fastmcp import Client

    from brain.mcp_server import create_server

    driver = Mock(side_effect=ConnectionError("synthetic-secret"))
    monkeypatch.setattr("brain.graph.FalkorDB", driver)
    async with Client(create_server(Services(GraphStore(remote(tmp_path))))) as client:
        assert len(await client.list_tools()) == 5
        driver.assert_not_called()
        calls = {
            "get_context": {"query": "auth"},
            "trace_decision": {"decision_id": "D-missing"},
            "find_owner": {"file": "x.py"},
            "check_change": {"files": ["x.py"], "symbols": ["target"]},
            "remember": {"text": "Unverified proposal", "scope": "private"},
        }
        for name, args in calls.items():
            result = await client.call_tool(name, args)
            assert result.data["status"] == "unavailable"
            assert "synthetic-secret" not in json.dumps(result.data)
