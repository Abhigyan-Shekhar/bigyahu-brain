"""Bounded workspace navigation using current company evidence, never memory ACL bypasses."""

from .evidence import code_evidence, native_graph, ready, source_evidence

FOLDER = "CASE WHEN coalesce(n.path,'')='' THEN '(no path)' WHEN size(split(n.path,'/'))>1 THEN split(n.path,'/')[0] ELSE '(root)' END"


def overview(store, grouping):
    sha = ready(store)
    if grouping not in {"type", "folder"}:
        raise ValueError("Choose type or folder grouping")
    expression = "labels(n)[0]" if grouping == "type" else FOLDER
    groups = store.query(
        "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) "
        f"WITH {expression} AS key,count(n) AS count "
        "RETURN key,count ORDER BY count DESC,key LIMIT 101",
        {"repo": store.cfg.repo_id},
    )
    totals = store.query(
        "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) RETURN count(n) AS nodes",
        {"repo": store.cfg.repo_id},
    )
    target_expression = expression.replace("n.", "m.").replace("labels(n)", "labels(m)")
    links = store.query(
        "MATCH (n {repo_id:$repo})-[r]->(m {repo_id:$repo}) "
        "WHERE coalesce(n.current,true) AND coalesce(m.current,true) "
        f"WITH {expression} AS source,{target_expression} AS target,"
        "type(r) AS relation,count(r) AS count "
        "RETURN source,target,relation,count ORDER BY count DESC,source,target,relation LIMIT 201",
        {"repo": store.cfg.repo_id},
    )
    return {
        "relationships": links[:200],
        "relationships_truncated": len(links) > 200,
        "relationship_limit": 200,
        "grouping": grouping,
        "groups": groups[:100],
        "total_nodes": totals[0]["nodes"],
        "truncated": len(groups) > 100,
        "group_limit": 100,
        "revision": sha,
    }


def inspect_node(store, uid):
    sha = ready(store)
    rows = store.query(
        "MATCH (n {repo_id:$repo,uid:$uid}) WHERE coalesce(n.current,true) "
        "RETURN n.path AS path,n.qualname AS qualname,n.uri AS uri,n.revision AS revision,"
        "coalesce(n.line_start,n.start_line,n.lineno,1) AS start,n.source_kind AS source_kind LIMIT 1",
        {"repo": store.cfg.repo_id, "uid": uid},
    )
    if not rows:
        raise KeyError("Current company entity unavailable")
    topology = native_graph(store, [uid])
    node = topology["nodes"][0]
    sources = store.query(
        "MATCH (n {repo_id:$repo,uid:$uid})-[:SUPPORTS|SUPPORTED_BY]->(s:Source {repo_id:$repo}) "
        "RETURN DISTINCT s.uid AS uid ORDER BY uid LIMIT 11",
        {"repo": store.cfg.repo_id, "uid": uid},
    )
    result = {
        "node": node,
        "properties": rows[0],
        "revision": sha,
        "sources": [r["uid"] for r in sources[:10]],
        "sources_truncated": len(sources) > 10,
    }
    result["highlights"] = node_highlights(store, uid, rows[0])
    try:
        if "Source" in node["labels"]:
            result["evidence"] = source_evidence(store, uid)
        elif set(node["labels"]) & {"File", "Symbol"} and rows[0]["path"]:
            start = int(rows[0]["start"])
            result["evidence"] = code_evidence(store, rows[0]["path"], start, start + 79)
        elif sources:
            result["evidence"] = source_evidence(store, sources[0]["uid"])
        else:
            result["source_notice"] = (
                "No directly reopenable source is attached to this entity. Explore its recorded neighbors."
            )
    except (ValueError, OSError) as exc:
        result["source_notice"] = (
            str(exc)[:500] if isinstance(exc, ValueError) else "Source bytes unavailable"
        )
    return result


def work_timeline(store, uid=None):
    """Current GitHub work and explicitly linked decisions; never mine approval from prose."""
    sha = ready(store)
    params = {"repo": store.cfg.repo_id, "uid": uid}
    prefix = (
        "MATCH p=(n {repo_id:$repo,uid:$uid})"
        "-[:DECLARES|CHANGES|REFERENCES|SUPPORTS|SUPPORTED_BY|DISCUSSED_IN*0..3]-(w) "
        "WHERE all(x IN nodes(p) WHERE x.repo_id=$repo AND coalesce(x.current,true)) "
        "AND (w:Issue OR w:PR) "
        if uid else
        "MATCH (w {repo_id:$repo}) WHERE (w:Issue OR w:PR) AND coalesce(w.current,true) "
    )
    rows = store.query(
        prefix + "RETURN DISTINCT w.uid AS uid,labels(w)[0] AS kind,w.title AS title,"
        "w.url AS url,w.work_status AS status,w.author AS author,"
        "w.created_at AS created_at,w.updated_at AS updated_at,w.due_at AS due_at,"
        "w.deadline_basis AS deadline_basis,w.snapshot_at AS snapshot_at "
        "ORDER BY due_at IS NULL,due_at,uid LIMIT 201", params,
    )
    items = rows[:200]
    decisions = store.query(
        "MATCH p=(w {repo_id:$repo})-[:SUPPORTS|DISCUSSED_IN*1..2]->"
        "(s:Source {repo_id:$repo})<-[:SUPPORTED_BY]-(d:Decision {repo_id:$repo,scope:'org'}) "
        "WHERE w.uid IN $ids AND all(x IN nodes(p) WHERE x.repo_id=$repo "
        "AND coalesce(x.current,true)) "
        "RETURN DISTINCT w.uid AS work_uid,d.uid AS uid,d.text AS text,d.status AS status,"
        "d.created_at AS created_at,d.approved_at AS approved_at,d.approved_by AS approved_by,"
        "s.uid AS source_uid,s.uri AS source_url "
        "ORDER BY created_at DESC,uid LIMIT 501",
        {"repo": store.cfg.repo_id, "ids": [w["uid"] for w in items]},
    ) if items else []
    for item in items:
        item["decisions"] = [d for d in decisions[:500] if d["work_uid"] == item["uid"]]
    return {
        "items": items, "revision": sha, "truncated": len(rows) > 200,
        "decisions_truncated": len(decisions) > 500,
        "limits": {"work_items": 200, "decision_links": 500},
    }


def node_highlights(store, uid, properties):
    params = {"repo": store.cfg.repo_id, "uid": uid}
    commits = store.query(
        "MATCH p=(n {repo_id:$repo,uid:$uid})-[:DECLARES|MODIFIES*0..2]-"
        "(c:Commit {repo_id:$repo}) "
        "WHERE all(x IN nodes(p) WHERE x.repo_id=$repo AND coalesce(x.current,true)) "
        "OPTIONAL MATCH (a:Person {repo_id:$repo})-[:AUTHORED]->(c) "
        "RETURN DISTINCT c.uid AS uid,c.sha AS sha,c.timestamp AS timestamp,a.name AS author "
        "ORDER BY timestamp DESC,uid LIMIT 1", params,
    )
    metadata = store.query(
        "MATCH (n {repo_id:$repo,uid:$uid}) RETURN n.updated_at AS updated_at,"
        "n.created_at AS created_at,n.author AS author,n.snapshot_at AS snapshot_at LIMIT 1",
        params,
    )[0]
    return {
        "last_commit": commits[0] if commits else None,
        "metadata": metadata,
        "work": work_timeline(store, uid),
        "path": properties.get("path"),
        "live": [],
        "live_notice": "Human presence is unavailable. Active app runs show planned file scope.",
    }


def active_node_runs(state, project, path):
    if not path:
        return []
    return [
        {"id": run["id"], "stage": run.get("stage"), "phase": run.get("phase"),
         "started_at": run.get("phase_started_at"), "basis": "planned_file_scope"}
        for run in state.list("action", project)
        if run.get("status") == "running" and path in run.get("plan", {}).get("files", [])
    ]
