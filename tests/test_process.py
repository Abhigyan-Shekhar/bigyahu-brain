import os
import sys

import pytest
import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


@pytest.mark.asyncio
async def test_module_launch_from_other_cwd_and_database_failure(tmp_path):
    config = tmp_path / "brain.yaml"
    config.write_text(
        yaml.safe_dump({"repo_root": str(tmp_path), "repo_id": "test/process", "port": 1})
    )
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "brain.mcp_server"],
        env={**os.environ, "BRAIN_CONFIG": str(config)},
        cwd=str(tmp_path),
    )
    async with Client(transport) as client:
        assert len(await client.list_tools()) == 5
        result = await client.call_tool("check_change", {"files": ["x.py"]})
        assert result.data["status"] == "unavailable"
