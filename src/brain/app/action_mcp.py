"""Constrained editor for an already-approved isolated checkout; no command execution."""

import json
import os
import threading
from pathlib import Path

from fastmcp import FastMCP

from ..memory import digest
from .live_changes import record_change


def target(work, path):
    if (
        not isinstance(path, str)
        or not path
        or "\\" in path
        or ":" in path
        or any(p in {"", "..", "."} or p.startswith(".") for p in path.split("/"))
    ):
        raise ValueError("Use a non-hidden relative file path")
    file = work / path
    if Path(path).is_absolute() or not file.resolve().is_relative_to(work.resolve()):
        raise ValueError("Path escapes the action workspace")
    if any(p.is_symlink() for p in (file, *file.parents)):
        raise ValueError("Symlinks are not editable")
    return file


def read_file(work, path):
    file = target(work, path)
    if not file.exists():
        return {"path": path, "exists": False, "text": "", "digest": digest("")}
    if not file.is_file() or file.stat().st_size > 100000:
        raise ValueError("Select a text file under 100 KB")
    text = file.read_bytes().decode("utf-8")
    return {"path": path, "exists": True, "text": text, "digest": digest(text)}


def write_file(work, allowed, path, text, expected_digest):
    if (
        path not in allowed
        or not isinstance(text, str)
        or len(text.encode()) > 100000
        or "\0" in text
    ):
        raise ValueError("Edit is outside the approved file/size scope")
    previous = read_file(work, path)
    if previous["digest"] != expected_digest:
        raise ValueError("File changed; read its current digest before editing")
    file = target(work, path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(text.encode("utf-8"))
    return {"path": path, "digest": digest(text), "bytes": len(text.encode())}


def create_server(work, allowed, events=None, originals=None):
    originals = dict(originals or {})
    write_lock = threading.Lock()
    mcp = FastMCP(
        "Approved patch workspace",
        instructions="Only the approved file scope may be edited. No shell, network, approvals or original-workspace writes are available.",
    )

    @mcp.tool(name="read_file")
    def read(path: str) -> dict:
        try:
            return read_file(work, path)
        except (ValueError, OSError, UnicodeError) as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool(name="write_file")
    def write(path: str, text: str, expected_digest: str, explanation: str = "") -> dict:
        """Write an approved file and explain the change briefly for the user (not private reasoning)."""
        try:
            if not isinstance(explanation, str) or len(explanation) > 1200:
                raise ValueError("Use a change explanation of at most 1200 characters")
            with write_lock:
                before = read_file(work, path)
                result = write_file(work, allowed, path, text, expected_digest)
                originals.setdefault(path, before["text"])
                if events:
                    record_change(
                        events, path, originals[path], text, explanation, result["digest"]
                    )
                return result
        except (ValueError, OSError, UnicodeError) as exc:
            return {"status": "error", "error": str(exc)}

    return mcp


def main():
    create_server(
        Path(os.environ["BRAIN_ACTION_WORKSPACE"]),
        json.loads(os.environ["BRAIN_ACTION_FILES"]),
        os.environ.get("BRAIN_ACTION_EVENTS"),
        json.loads(Path(os.environ["BRAIN_ACTION_ORIGINALS"]).read_text(encoding="utf-8"))
        if os.environ.get("BRAIN_ACTION_ORIGINALS")
        else None,
    ).run()


if __name__ == "__main__":
    main()
