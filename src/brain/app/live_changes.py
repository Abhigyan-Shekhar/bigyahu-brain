"""Actual successful approved-file writes, with bounded display-only diffs."""

import difflib
import json
from datetime import UTC, datetime
from pathlib import Path

from ..memory import canonical


def record_change(path, filename, original, updated, explanation, digest):
    lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="a/" + filename,
            tofile="b/" + filename,
        )
    )
    value = {
        "path": filename,
        "diff": "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in lines
        ),
        "explanation": explanation,
        "digest": digest,
        "at": datetime.now(UTC).isoformat(),
        "additions": sum(line.startswith("+") and not line.startswith("+++") for line in lines),
        "deletions": sum(line.startswith("-") and not line.startswith("---") for line in lines),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")


def read_changes(path, allowed):
    latest, bounded = {}, False
    try:
        with Path(path).open("rb") as stream:
            size = stream.seek(0, 2)
            offset = max(0, size - 2_000_000)
            bounded = offset > 0
            stream.seek(offset)
            data = stream.read(2_000_000)
            if offset:
                data = data.partition(b"\n")[2]
        for line in data.splitlines():
            try:
                item = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if (
                not isinstance(item, dict)
                or item.get("path") not in allowed
                or not isinstance(item.get("diff"), str)
                or not isinstance(item.get("explanation"), str)
                or len(item["explanation"]) > 1200
                or not isinstance(item.get("at"), str)
                or any(
                    type(item.get(key)) is not int or item[key] < 0
                    for key in ("additions", "deletions")
                )
            ):
                continue
            latest[item["path"]] = {
                key: item[key]
                for key in ("path", "diff", "explanation", "at", "additions", "deletions")
            }
    except OSError:
        pass
    files, remaining = [], 200000
    for name in allowed[:12]:
        if name not in latest:
            continue
        item = latest[name]
        limit = min(60000, remaining)
        content = item["diff"].encode("utf-8")
        item["truncated"] = len(content) > limit
        item["diff"] = content[:limit].decode("utf-8", errors="ignore")
        remaining -= min(len(content), limit)
        bounded |= item["truncated"]
        files.append(item)
    return {"files": files, "bounded": bounded, "kind": "recorded_editor_writes"}
