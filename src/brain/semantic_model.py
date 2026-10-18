"""Shared opt-in Codex structured extraction without catalog or shell tools."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .memory import canonical


def structured_extract(prompt, schema_definition, model, *, timeout_seconds=180):
    if not isinstance(model, str) or not 1 <= len(model) <= 100:
        raise ValueError("Explicit semantic model required")
    with tempfile.TemporaryDirectory(prefix="brain-semantic-") as temp:
        root = Path(temp)
        schema, output = root / "schema.json", root / "result.json"
        schema.write_text(canonical(schema_definition), encoding="utf-8")
        command = [
            "codex",
            "exec",
            "--ignore-user-config",
            "--strict-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "-s",
            "read-only",
            "-C",
            temp,
            "-m",
            model,
            "--disable",
            "plugins",
            "--disable",
            "apps",
            "--disable",
            "shell_tool",
            "--disable",
            "unified_exec",
            "--disable",
            "multi_agent",
            "-c",
            'approval_policy="never"',
            "-c",
            "project_doc_max_bytes=0",
            "-c",
            'web_search="disabled"',
            "--output-schema",
            str(schema),
            "-o",
            str(output),
            "-",
        ]
        env = dict(os.environ)
        env.pop("BRAIN_OPERATOR_SESSION", None)
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
        if result.returncode or not output.exists() or output.stat().st_size > 1_000_000:
            raise ValueError("Semantic extractor failed; no evidence was written")
        return json.loads(output.read_text(encoding="utf-8"))
