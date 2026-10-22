"""Plugin entry point: existing configured MCP, or a read-only setup diagnostic."""

import os
from pathlib import Path

import yaml
from fastmcp import FastMCP

from .config import load_config
from .registry import load_registry


def plugin_configuration(environ=None, plugin_root=None):
    env = os.environ if environ is None else environ
    if env.get("BRAIN_REGISTRY"):
        return "BRAIN_REGISTRY", Path(env["BRAIN_REGISTRY"])
    if env.get("BRAIN_CONFIG"):
        return "BRAIN_CONFIG", Path(env["BRAIN_CONFIG"])
    module = Path(__file__).resolve()
    # Wheel installs live below the plugin's uv-managed .venv. Editable imports
    # cannot be used here: macOS clients can hide cached .pth files, which Python
    # then skips on a subsequent launch.
    installed_root = next((p.parent for p in module.parents if p.name == ".venv"), module.parents[2])
    root = Path(plugin_root or installed_root)
    parents = root.parents
    cached_home = (
        parents[4]
        if len(parents) >= 5 and parents[2].name == "cache" and parents[3].name == "plugins"
        else Path.home() / ".codex"
    )
    # Codex plugin transports filter extra environment variables. Its documented
    # cache layout still identifies the owning profile without reading another
    # profile's default registry when CODEX_HOME was not forwarded.
    home = Path(env.get("CODEX_HOME", str(cached_home))).expanduser()
    return "BRAIN_REGISTRY", home / "company-brain/registry.json"


def create_setup_server(variable, path, reason):
    mcp = FastMCP("Company Brain setup", instructions="Use the company-brain-setup skill to configure the local plugin. This server never indexes or approves changes.")

    @mcp.tool
    def setup_status() -> dict:
        """Report missing/invalid plugin configuration without reading repository content."""
        return {
            "status": "setup_required", "reason": reason,
            "configuration_variable": variable, "configuration_path": str(path),
            "next_step": "Use company-brain-setup, then restart the MCP server or start a fresh chat.",
        }

    return mcp


def main():
    variable, path = plugin_configuration()
    try:
        (load_registry if variable == "BRAIN_REGISTRY" else load_config)(path)
    except FileNotFoundError:
        create_setup_server(variable, path, "configuration_missing").run()
        return
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        create_setup_server(variable, path, "configuration_invalid").run()
        return
    # An explicit single-config selection must not inherit a different registry.
    os.environ[variable] = str(path)
    if variable == "BRAIN_CONFIG":
        os.environ.pop("BRAIN_REGISTRY", None)
    from .mcp_server import main as serve

    serve()


if __name__ == "__main__":
    main()
