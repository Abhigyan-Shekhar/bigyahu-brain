"""Install and exercise the exact ZIP against an already-running loopback FalkorDB."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path


def run(command, **kwargs):
    subprocess.run(command, check=True, timeout=180, **kwargs)


async def exercise(plugin, work, port):
    # This branch is re-executed with the extracted package's Python environment.
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    import brain

    if not Path(brain.__file__).resolve().is_relative_to(plugin):
        raise RuntimeError("Smoke test imported source outside the installed artifact")
    spec = json.loads((plugin / "mcp.json").read_text())["mcpServers"]["company-brain"]
    arguments = [arg.replace("${PLUGIN_ROOT}", str(plugin)) for arg in spec["args"]]
    def transport():
        return StdioTransport(
            command=spec["command"], args=arguments, cwd=str(plugin), env=dict(os.environ),
        )
    registry = work / "profile/company-brain/registry.json"
    async with Client(transport()) as client:
        if [tool.name for tool in await client.list_tools()] != ["setup_status"]:
            raise RuntimeError("Fresh installation did not expose only setup_status")
        setup = (await client.call_tool("setup_status", {})).data
        if setup["status"] != "setup_required" or Path(setup["configuration_path"]) != registry:
            raise RuntimeError("Fresh installation used an unexpected configuration")
    if registry.exists():
        raise RuntimeError("Setup diagnostic unexpectedly wrote configuration")

    # Reproduce clients hiding cached .pth files: Python will no longer process
    # them on restart. The installed server must work without editable imports.
    for path in (plugin / ".venv").rglob("*.pth"):
        path.rename(path.with_suffix(".pth.disabled"))
    async with Client(transport()) as client:
        setup = (await client.call_tool("setup_status", {})).data
        if setup["status"] != "setup_required" or Path(setup["configuration_path"]) != registry:
            raise RuntimeError("Restart without .pth files lost the isolated profile")

    repo = work / "fixture"
    repo.mkdir()
    source = "def packaged_target():\n    return 'artifact_smoke_sentinel'\n"
    (repo / "fixture.py").write_text(source, encoding="utf-8")
    for args in (["init", "--quiet"], ["add", "fixture.py"],
                 ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                  "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Fixture"]):
        run(["git", "-C", str(repo), *args])
    config = work / "brain.yaml"
    run([sys.executable, "-m", "brain", "init", "--repo", str(repo), "--config", str(config),
         "--repo-id", "artifact-smoke:" + uuid.uuid4().hex, "--principal", "demo_operator",
         "--port", str(port), "--sync"], cwd=work)
    run([sys.executable, "-m", "brain", "register", "--registry", str(registry),
         "--config", str(config)], cwd=work)
    async with Client(transport()) as client:
        value = (await client.call_tool("read_code", {
            "repo_root": str(repo), "path": "fixture.py",
        })).data
        if value["status"] != "ok" or not value["checked_evidence"]:
            raise RuntimeError("Configured artifact failed MCP retrieval")
        if source not in value["checked_evidence"][0]["text"]:
            raise RuntimeError("Retrieved evidence differs from the fixture source")
    print(json.dumps({"setup_status_verified": True, "restart_without_pth_verified": True, "packaged_mcp_retrieval_verified": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--installed", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.installed:
        asyncio.run(exercise(args.installed.resolve(), args.archive.resolve(), args.port))
        return
    archive = args.archive.resolve()
    expected = archive.with_suffix(".zip.sha256").read_text().split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("ZIP checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="company-brain-artifact-") as temporary:
        work = Path(temporary).resolve()
        cache = work / "profile/plugins/cache/smoke/company-brain"
        cache.mkdir(parents=True)
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                path = Path(item.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                        or path.parts[0] != "company-brain" or item.external_attr >> 16 != 0o100644):
                    raise ValueError("Unexpected package ZIP entry")
            bundle.extractall(cache)
        plugin = cache / "company-brain"
        # Use the same profile/cache layout as a native installation.
        version = json.loads((plugin / "plugin.json").read_text())["version"]
        installed = cache / version
        plugin.rename(installed)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("BRAIN_", "UV_")) and k not in {"PYTHONPATH", "VIRTUAL_ENV", "CODEX_HOME"}}
        env["PYTHONNOUSERSITE"] = "1"
        run(["uv", "sync", "--frozen", "--no-dev", "--no-editable", "--project", str(installed)], cwd=work, env=env)
        run(["uv", "run", "--frozen", "--no-dev", "--no-editable", "--project", str(installed), "python",
             str(Path(__file__).resolve()), str(work), "--installed", str(installed),
             "--port", str(args.port)], cwd=work, env=env)


if __name__ == "__main__":
    main()
