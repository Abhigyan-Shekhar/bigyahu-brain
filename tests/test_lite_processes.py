"""Separate processes share one owner; verify shutdown/restart persistence, not file sharing."""

import json
import os
import selectors
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from falkordb import FalkorDB

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform == "win32", reason="Native Windows uses Docker, not Lite"),
    pytest.mark.skipif(os.getenv("BRAIN_LITE_TESTS") != "1", reason="opt-in Lite lifecycle test"),
]
LAUNCHER = Path(__file__).resolve().parents[1] / "scripts/run_lite.py"


def start_owner(path, port):
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER), "--db", str(path), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        if not selector.select(30):
            raise RuntimeError("Lite startup timed out")
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(proc.stderr.read())
        assert json.loads(line)["status"] == "ready"
        return proc
    except BaseException:
        proc.terminate()
        proc.wait(timeout=15)
        raise
    finally:
        selector.close()


def stop_owner(proc):
    proc.terminate()
    out, err = proc.communicate(timeout=20)
    assert proc.returncode == 0, err
    assert "Lite stopped with SAVE" in out


def test_two_clients_one_owner_and_restart(tmp_path):
    pytest.importorskip("redislite")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    path = tmp_path / "engine.rdb"
    owner = start_owner(path, port)
    try:
        db = FalkorDB(port=port)
        graph = db.select_graph("org_process_fixture")
        graph.query("CREATE (:Counter {uid:'shared', count:0})")
        graph.query("CALL db.idx.fulltext.createNodeIndex('Note','text')")
        graph.query("CREATE (:Note {text:'persistedmarker'})")
        # A second owner must fail before opening the same data file.
        duplicate = subprocess.run(
            [sys.executable, str(LAUNCHER), "--db", str(path), "--port", str(port)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert duplicate.returncode != 0 and "already has a Lite owner" in duplicate.stderr
        code = """import sys
from falkordb import FalkorDB
g=FalkorDB(port=int(sys.argv[1])).select_graph('org_process_fixture')
for _ in range(30):
    g.query("MATCH (n:Counter {uid:'shared'}) SET n.count=n.count+1")
print(g.query("MATCH (n:Counter) RETURN n.count").result_set)
"""
        clients = [
            subprocess.Popen(
                [sys.executable, "-c", code, str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        for client in clients:
            _, err = client.communicate(timeout=20)
            assert client.returncode == 0, err
        assert graph.query("MATCH (n:Counter) RETURN n.count").result_set == [[60]]
        assert db.connection.ping()  # Client exits did not terminate the shared engine.
        db.connection.close()
    finally:
        stop_owner(owner)
    assert path.exists()
    owner = start_owner(path, port)
    try:
        db = FalkorDB(port=port)
        graph = db.select_graph("org_process_fixture")
        assert graph.query("MATCH (n:Counter) RETURN n.count").result_set == [[60]]
        assert graph.query(
            "CALL db.idx.fulltext.queryNodes('Note','persistedmarker') YIELD node RETURN node.text"
        ).result_set == [["persistedmarker"]]
        db.connection.close()
    finally:
        stop_owner(owner)
