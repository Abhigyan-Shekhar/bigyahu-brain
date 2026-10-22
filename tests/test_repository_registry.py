import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, replace

import pytest
import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from test_integration import real as real  # noqa: PLC0414

from brain.config import Config
from brain.graph import GraphStore
from brain.ingest.git_parser import revision
from brain.ingest.sync import sync
from brain.mcp_server import create_registry_server
from brain.registry import load_registry, register_repository, select_repository


def write_config(path, cfg):
    path.write_text(yaml.safe_dump({**asdict(cfg), "repo_root": str(cfg.repo_root)}))
    return path


def test_registry_roundtrip_and_atomic_conflict_checks(tmp_path):
    roots = [tmp_path / "a", tmp_path / "b"]
    for root in roots:
        root.mkdir()
    configs = [write_config(tmp_path / f"{i}.yaml", Config(root, f"repo-{i}")) for i, root in enumerate(roots)]
    registry = tmp_path / "registry.json"
    for config in configs:
        register_repository(registry, config)
    original = registry.read_bytes()
    register_repository(registry, configs[0])
    assert registry.read_bytes() == original
    entries = load_registry(registry)
    assert select_repository(entries, str(roots[1]))[1].repo_id == "repo-1"
    with pytest.raises(ValueError, match="not registered"):
        select_repository(entries, str(tmp_path))
    with pytest.raises(ValueError, match="absolute"):
        select_repository(entries, "../a")
    other = write_config(tmp_path / "conflict.yaml", Config(roots[0], "other"))
    with pytest.raises(ValueError, match="different config"):
        register_repository(registry, other)
    cfg = Config(roots[1], "repo-1", principal="different_operator")
    write_config(configs[1], cfg)
    with pytest.raises(ValueError, match="same trusted identity"):
        load_registry(registry)
    write_config(configs[1], replace(cfg, principal="demo_operator"))
    assert registry.read_bytes() == original
    registry.with_name(registry.name + ".lock").mkdir()
    with pytest.raises(FileExistsError):
        register_repository(registry, configs[0])
    assert registry.read_bytes() == original


def test_registry_rejects_bad_manifests_and_in_checkout_storage(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    config = write_config(tmp_path / "config.yaml", Config(root, "fixture"))
    with pytest.raises(ValueError, match="outside indexed"):
        register_repository(root / "registry.json", config)
    assert not (root / "registry.json").exists()
    path = tmp_path / "registry.json"
    for payload in ({"version": 2}, {"version": 1, "repositories": []},
                    {"version": 1, "repositories": ["relative"]},
                    {"version": 1, "repositories": [str(config), str(config)]}):
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            load_registry(path)
    path.write_text("x" * 65537)
    with pytest.raises(ValueError, match="size bound"):
        load_registry(path)


@pytest.mark.asyncio
async def test_routing_requires_root_and_parallel_calls_stay_isolated(tmp_path):
    entries, contexts = {}, {}
    for name in ("a", "b"):
        root = tmp_path / name
        root.mkdir()
        cfg = Config(root, name)
        entries[str(root)] = (tmp_path / f"{name}.yaml", cfg)

        def make_tools(identity):
            def get_context(query: str, scope: str = "org") -> dict:
                return {"status": "ok", "query": query, "context": identity, "scope": scope}

            return {"get_context": get_context}

        contexts[str(root)] = make_tools(name)
    async with Client(create_registry_server(entries, contexts)) as client:
        inventory = await client.list_tools()
        tool = next(t for t in inventory if t.name == "get_context")
        assert "repo_root" in tool.inputSchema["required"]
        listed = (await client.call_tool("list_repositories", {})).data
        assert {r["repo_id"] for r in listed["repositories"]} == {"a", "b"}
        results = await asyncio.gather(*[
            client.call_tool("get_context", {"query": f"q{i}", "repo_root": str(tmp_path / name)})
            for i, name in enumerate(["a", "b"] * 10)
        ])
        for result, name in zip(results, ["a", "b"] * 10, strict=True):
            assert result.data["context"] == result.data["repository"]["repo_id"] == name
        denied = (await client.call_tool("get_context", {"query": "secret", "repo_root": str(tmp_path)})).data
        assert denied["status"] == "error" and "context" not in denied


@pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB")
@pytest.mark.asyncio
async def test_real_stdio_two_roots_citations_and_registry_sync(real, tmp_path_factory):
    folder = tmp_path_factory.mktemp("routing")
    other = folder / "other"
    other.mkdir()
    await asyncio.to_thread(subprocess.run, ["git", "init", "-q", str(other)], check=True)
    text = "def second(): return 1\n"
    (other / "x.py").write_text(text)

    def commit():
        subprocess.run(["git", "-C", str(other), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(other), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.com", "commit", "-qm", "second fixture",
        ], check=True)

    commit()
    second = GraphStore(replace(real.cfg, repo_root=other, repo_id=real.cfg.repo_id + "-second"))
    sync(real)
    sync(second)
    registry = folder / "registry.json"
    register_repository(registry, write_config(folder / "first.yaml", real.cfg))
    register_repository(registry, write_config(folder / "second.yaml", second.cfg))
    transport = StdioTransport(
        command=sys.executable, args=["-m", "brain.mcp_server"],
        env={**os.environ, "BRAIN_REGISTRY": str(registry)}, cwd=str(folder),
    )
    root_a, root_b = str(real.cfg.repo_root), str(other)
    try:
        async with Client(transport) as client:
            listed = (await client.call_tool("list_repositories", {})).data
            assert len(listed["repositories"]) == 2
            assert listed["registry"] == str(registry)
            for root, cfg in ((root_a, real.cfg), (root_b, second.cfg)):
                status = (await client.call_tool("repository_status", {"repo_root": root})).data
                assert status["status"] == "ok" and status["repo_id"] == cfg.repo_id
            a = (await client.call_tool("read_code", {"repo_root": root_a, "path": "x.py"})).data
            evidence_id = a["checked_evidence"][0]["id"]
            cross = (await client.call_tool("resolve_evidence", {"repo_root": root_b, "evidence_id": evidence_id})).data
            assert cross["status"] == "unknown" and "checked_evidence" not in cross
            b = (await client.call_tool("read_code", {"repo_root": root_b, "path": "x.py"})).data
            assert b["checked_evidence"][0]["text"] == text
            old_id = b["checked_evidence"][0]["id"]
            dirty = "def second(): return 2\n"
            (other / "x.py").write_text(dirty)
            stale = (await client.call_tool("repository_status", {"repo_root": root_b})).data
            assert stale["status"] == "incomplete" and "stale_index" in stale["warnings"]
            assert (await client.call_tool("repository_status", {"repo_root": root_a})).data["status"] == "ok"
            command = [sys.executable, "-m", "brain", "sync", "--registry", str(registry), "--repo-root", root_b]
            failed = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, check=False)
            assert failed.returncode != 0 and (other / "x.py").read_text() == dirty
            commit()
            await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, check=True)
            refreshed = (await client.call_tool("repository_status", {"repo_root": root_b})).data
            assert refreshed["status"] == "ok" and refreshed["graph_revision"] == revision(other)
            old = (await client.call_tool("resolve_evidence", {"repo_root": root_b, "evidence_id": old_id})).data
            assert old["status"] == "incomplete" and "checked_evidence" not in old
            b = (await client.call_tool("read_code", {"repo_root": root_b, "path": "x.py"})).data
            assert b["checked_evidence"][0]["text"] == dirty
    finally:
        second.query("MATCH (n {repo_id:$repo}) DETACH DELETE n", {"repo": second.cfg.repo_id})
