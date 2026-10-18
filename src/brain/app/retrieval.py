"""Per-run retrieval work limits; no cached authorization or model bypass."""

import asyncio
import json
from pathlib import Path

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from ..memory import canonical, digest

MAX_RETRIEVAL_CALLS = 20
MAX_CONTEXT_CALLS = 6
MAX_IDENTICAL_CALLS = 2


class RetrievalBudget(Middleware):
    def __init__(self, folder):
        self.folder = Path(folder)
        self.lock = asyncio.Lock()
        self.counts = {}
        self.repeated = {}
        self.blocked = 0
        try:
            saved = json.loads((self.folder / "retrieval.json").read_text(encoding="utf-8"))
            self.counts = saved.get("counts", {})
            self.repeated = saved.get("fingerprints", {})
            self.blocked = saved.get("blocked", 0)
        except (OSError, ValueError):
            pass

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        key = digest(canonical([name, context.message.arguments or {}]))
        async with self.lock:
            reason = None
            if sum(self.counts.values()) >= MAX_RETRIEVAL_CALLS:
                reason = "Retrieval budget reached"
            elif name == "get_context" and self.counts.get(name, 0) >= MAX_CONTEXT_CALLS:
                reason = (
                    "Company context search budget reached; use checked sources already returned"
                )
            elif self.repeated.get(key, 0) >= MAX_IDENTICAL_CALLS:
                reason = "Identical lookup already performed twice; use its checked evidence"
            if reason:
                self.blocked += 1
            else:
                self.counts[name] = self.counts.get(name, 0) + 1
                self.repeated[key] = self.repeated.get(key, 0) + 1
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / "retrieval.json"
            pending = path.with_suffix(".tmp")
            pending.write_text(
                canonical(
                    {
                        "limit": MAX_RETRIEVAL_CALLS,
                        "used": sum(self.counts.values()),
                        "context_limit": MAX_CONTEXT_CALLS,
                        "context_used": self.counts.get("get_context", 0),
                        "blocked": self.blocked,
                        "counts": self.counts,
                        "fingerprints": self.repeated,
                    }
                ),
                encoding="utf-8",
            )
            pending.replace(path)
        if reason:
            raise ToolError(
                reason
                + ". Finish the structured response with available evidence and explicit limitations; do not invent support."
            )
        return await call_next(context)


def retrieval_stats(folder):
    try:
        path = Path(folder) / "retrieval.json"
        if path.stat().st_size > 16000:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        keys = ("limit", "used", "context_limit", "context_used", "blocked")
        if any(type(value.get(key)) is not int or value[key] < 0 for key in keys):
            return None
        return {key: value[key] for key in keys}
    except (OSError, ValueError, TypeError):
        return None
