"""Viewer API never supplies caller-controlled identities or raw graph access."""

import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from unittest.mock import Mock

from test_memory import grant
from test_memory import memory as memory  # noqa: PLC0414

from brain.memory_tools import MemoryTools
from brain.memory_viewer import authorized_brains, handler


def test_viewer_catalog_lists_only_current_trusted_identity(memory):
    grant(memory, "alice", "team:runtime", "reader")
    grant(memory, "bob", "team:hidden", "reader")
    assert authorized_brains(memory) == ["private:alice", "team:runtime"]
    grant(memory, "alice", "team:runtime", "revoked")
    assert authorized_brains(memory) == ["private:alice"]


def test_http_auth_origin_and_scope_checks_precede_graph_io(memory):
    projection = Mock()
    projection.read.side_effect = PermissionError("scope unavailable")
    tools = MemoryTools(memory, Mock(), projection)
    server = HTTPServer(("127.0.0.1", 0), handler(memory, tools, "fixture-token"))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)

    def get(path, headers=None):
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    auth = {"Authorization": "Bearer fixture-token"}
    try:
        assert get("/api/brains")[0] == 401
        assert get("/api/brains", {**auth, "Origin": "https://evil.invalid"})[0] == 403
        assert get("/api/brains", {**auth, "Host": "evil.invalid"})[0] == 403
        projection.read.assert_not_called()
        status, result = get("/api/brains", auth)
        assert status == 200 and result["brains"] == ["private:alice"]
        status, result = get("/api/graph?brain=private%3Abob", auth)
        assert status == 409 and result["warnings"] == ["scope_unavailable"]
        projection.read.assert_called_once_with(["private:bob"], False, False)
        assert get("/api/graph?brain=company&principal=bob", auth)[0] == 404
    finally:
        connection.close()
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
