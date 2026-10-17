"""Structured extractor configuration and UTF-8 output, without model calls."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from brain.semantic_model import structured_extract


def test_structured_extraction_has_no_shell_mcp_or_web_and_reads_utf8(monkeypatch):
    def run(command, **kwargs):
        assert kwargs["input"] == "synthetic user-selected data"
        assert kwargs["encoding"] == "utf-8" and kwargs["check"] is False
        assert command[command.index("-s") + 1] == "read-only"
        for feature in ("apps", "plugins", "multi_agent", "shell_tool", "unified_exec"):
            assert any(
                command[i : i + 2] == ["--disable", feature] for i in range(len(command) - 1)
            )
        assert "--ignore-user-config" in command
        assert 'web_search="disabled"' in command
        Path(command[command.index("-o") + 1]).write_text(
            json.dumps({"name": "café"}, ensure_ascii=False), encoding="utf-8"
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("brain.semantic_model.subprocess.run", run)
    assert structured_extract("synthetic user-selected data", {"type": "object"}, "fixture") == {
        "name": "café"
    }


def test_failed_extraction_does_not_return_partial_output(monkeypatch):
    monkeypatch.setattr(
        "brain.semantic_model.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )
    with pytest.raises(ValueError, match="failed"):
        structured_extract("synthetic", {}, "fixture")
