"""Operator-owned repository allowlist for a single native MCP registration."""

import json
import os
import tempfile
from pathlib import Path

from .config import load_config


def registry_entries(paths):
    if not isinstance(paths, list) or not 1 <= len(paths) <= 64:
        raise ValueError("Registry must contain 1–64 config paths")
    entries, identity = {}, None
    for value in paths:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("Registry config paths must be absolute")
        cfg = load_config(value)
        # Routing may choose a repository, never another principal or catalog.
        current = (
            cfg.principal, cfg.tenant_id, cfg.memory_db, cfg.embedding_model_dir,
            cfg.memory_graph_enabled,
        )
        if identity is not None and identity != current:
            raise ValueError("All registered repositories must use the same trusted identity and memory settings")
        identity = current
        root = str(cfg.repo_root)
        if root in entries:
            raise ValueError("Registry contains duplicate repository roots")
        entries[root] = (Path(value).resolve(), cfg)
    return entries


def load_registry(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("BRAIN_REGISTRY must be absolute")
    if path.stat().st_size > 65536:
        raise ValueError("Registry exceeds size bound")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("Unsupported registry version")
    return registry_entries(value.get("repositories"))


def select_repository(entries, repo_root):
    root = Path(repo_root)
    if not root.is_absolute():
        raise ValueError("repo_root must be the absolute Git root")
    selected = entries.get(str(root.resolve()))
    if selected is None:
        raise ValueError("Repository is not registered; use list_repositories")
    return selected


def register_repository(registry, config):
    """Validate and atomically update an allowlist without overwriting another writer."""
    registry, config = Path(registry).expanduser().resolve(), Path(config).expanduser().resolve()
    cfg = load_config(config)
    registry.parent.mkdir(parents=True, exist_ok=True)
    lock = registry.with_name(registry.name + ".lock")
    lock.mkdir()  # An existing writer/stale lock fails explicitly instead of losing updates.
    pending = None
    try:
        entries = load_registry(registry) if registry.exists() else {}
        root = str(cfg.repo_root)
        if root in entries and entries[root][0] != config:
            raise ValueError("Root already registered with a different config")
        entries[root] = (config, cfg)
        if any(registry.is_relative_to(value[1].repo_root) for value in entries.values()):
            raise ValueError("Keep the registry outside indexed checkouts")
        paths = [str(value[0]) for _, value in sorted(entries.items())]
        registry_entries(paths)
        payload = json.dumps({"version": 1, "repositories": paths}, indent=2) + "\n"
        if len(payload.encode("utf-8")) > 65536:
            raise ValueError("Registry exceeds size bound")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=registry.parent, delete=False) as stream:
            pending = Path(stream.name)
            stream.write(payload)
        os.replace(pending, registry)
        return {"registry": str(registry), "repo_root": root, "repo_id": cfg.repo_id}
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
        lock.rmdir()
