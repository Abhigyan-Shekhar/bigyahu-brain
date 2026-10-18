"""Small repository-scoped lifecycle snapshots for the persistent work indicator."""


def snapshot(state, project):
    repo = state.get(project, "repository")
    items = []

    def add(value, kind, session=None):
        if value.get("status") not in {"queued", "running"}:
            return
        items.append({
            "id": value["id"], "kind": kind, "status": value["status"],
            "stage": value.get("stage") or value["status"].replace("_", " "),
            "title": value.get("objective") or value.get("question")
            or value.get("instruction") or value.get("goal") or value.get("name") or kind,
            "phase": value.get("phase"), "session": session,
        })

    add(repo, "repository")
    for kind in ("action", "enrichment", "documentation_draft", "workflow", "documentation_patch"):
        for item in state.list(kind, project):
            add(item, kind)
    for session in state.list("session", project):
        for turn in state.list("turn", session["id"]):
            add(turn, "investigation", session["id"])
    return {"items": items[:50], "truncated": len(items) > 50}
