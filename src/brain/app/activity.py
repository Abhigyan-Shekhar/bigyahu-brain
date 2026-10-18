"""Safe observable activity derived from bounded existing model tool traces."""

import json
from datetime import UTC, datetime

TOOLS = [
    "get_context",
    "check_change",
    "find_owner",
    "trace_decision",
    "search_code",
    "read_code",
    "search_history",
    "memory_search",
    "memory_graph",
]


def tool_activity(trace, running):
    completed, current, bounded = [], None, False
    try:
        with trace.open("rb") as stream:
            # Bound polling work and ignore incomplete lines at the read boundary.
            data = stream.read(2_000_000)
            bounded = bool(stream.read(1))
        for line in data.splitlines():
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(event, dict):
                continue
            item = event.get("item", {})
            if not isinstance(item, dict):
                continue
            if not isinstance(item.get("tool"), str):
                continue
            if item.get("type") != "mcp_tool_call" or item.get("tool") not in {
                *TOOLS,
                "read_file",
                "write_file",
            }:
                continue
            if event.get("type") == "item.started":
                current = item["tool"]
            elif event.get("type") == "item.completed":
                completed.append(
                    {
                        "tool": item["tool"],
                        "status": item.get("status")
                        if item.get("status") in {"completed", "failed"}
                        else "unverified",
                    }
                )
                current = None
    except OSError:
        pass
    return {
        "completed_tools": completed[-12:],
        "completed_count": len(completed),
        "current_tool": current if running else None,
        "trace_bounded": bounded,
    }


def elapsed_seconds(start, finish, running):
    if not start or not (finish or running):
        return None
    beginning = datetime.fromisoformat(start)
    end = datetime.fromisoformat(finish) if finish else datetime.now(UTC)
    return max(0, (end - beginning).total_seconds())


def investigation_progress(state, turn):
    running = turn.get("status") in {"queued", "running"}
    trace = state.folder(turn["project"]) / "turns" / turn["id"] / "trace.jsonl"
    if turn.get("status") == "complete" and isinstance(turn.get("tools"), list):
        tools = [
            {
                "tool": t["tool"],
                "status": t.get("status")
                if t.get("status") in {"completed", "failed"}
                else "unverified",
            }
            for t in turn["tools"]
            if isinstance(t, dict) and isinstance(t.get("tool"), str) and t["tool"] in TOOLS
        ]
        activity = {
            "completed_tools": tools[-12:],
            "completed_count": len(tools),
            "current_tool": None,
            "trace_bounded": False,
        }
    else:
        activity = tool_activity(trace, running)
    return {
        **activity,
        "elapsed_seconds": elapsed_seconds(
            turn.get("started_at"), turn.get("finished_at"), running
        ),
    }
